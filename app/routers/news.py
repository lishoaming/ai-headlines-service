from typing import Annotated, List  # 导入类型标注工具

from fastapi import APIRouter, Depends, Query  # 导入路由、依赖注入与查询参数
from sqlalchemy.ext.asyncio import AsyncSession  # 导入异步会话类型

from app.config import settings  # 导入全局配置（读取分场景缓存 TTL）
from app.config.db import get_db  # 导入数据库会话依赖
from app.crud.news import get_news_categories, get_news_list, get_news_detail, get_related_news, increment_view_count  # 导入新闻 CRUD
from app.schemas.base import ResponseModel  # 导入统一响应模型
from app.utils.exceptions import BusinessException  # 导入业务异常基类
from app.utils.cache import get_or_set as cache_get_or_set  # 导入 cache-aside 缓存封装
from app.schemas.news import (  # 导入新闻出参模型
    CategoryOut,
    NewsListIn,
    NewsListOut,
    NewsDetailIn,
    NewsDetailOut,
)

news_router = APIRouter(prefix="/api/news", tags=["新闻"])  # 创建新闻路由，统一前缀 /api/news

# 缓存 TTL 统一在配置中维护（.env 可覆盖）：数据越稳定，缓存越持久
CACHE_TTL_CATEGORIES = settings.CACHE_TTL_CATEGORY  # 分类：7200s
CACHE_TTL_NEWS_LIST = settings.CACHE_TTL_LIST  # 列表：600s
CACHE_TTL_NEWS_DETAIL = settings.CACHE_TTL_DETAIL  # 详情：1800s

# 写后失效约定（以后新增/修改/删除新闻、分类的写接口时必须执行，且要在 db.commit() 之后）：
#   await cache.delete_prefix("news:list")          # 所有分类+分页组合的列表缓存
#   await cache.delete(f"news:detail:{news_id}")    # 该篇详情缓存
#   await cache.delete("news:categories")           # 仅分类发生变动时才需要
# 当前 news 模块只有读接口，没有失效点，暂时由上面的 TTL 兜底。


async def _load_detail(db: AsyncSession, news_id: int) -> dict | None:  # 回源加载详情（含相关推荐），返回可 JSON 化的字典
    """从数据库加载详情并组装相关推荐；新闻不存在返回 None（会被负缓存，防止反复穿透）"""
    detail = await get_news_detail(db, news_id)  # 查询新闻详情
    if detail is None:  # 新闻不存在
        return None
    related = await get_related_news(db, detail.category_id, news_id)  # 查询相关推荐
    data = NewsDetailOut.model_validate(detail)  # ORM 转出参模型
    data.related_news = related  # 填充相关推荐
    return data.model_dump(by_alias=True, mode="json")  # 统一成 camelCase 字典，命中/未命中结构一致


@news_router.get("/categories", response_model=ResponseModel[List[CategoryOut]])  # 获取新闻分类列表接口
async def get_categories(db: AsyncSession = Depends(get_db)):  # 定义异步处理函数
    categories = await cache_get_or_set("news:categories", lambda: get_news_categories(db), ttl=CACHE_TTL_CATEGORIES)  # 优先读缓存，未命中再查库
    return ResponseModel(message="获取新闻分类列表成功", data=categories)  # 返回统一响应


@news_router.get("/list", response_model=ResponseModel[NewsListOut])  # 根据分类分页获取新闻列表接口
async def list_news(params: Annotated[NewsListIn, Query()], db: AsyncSession = Depends(get_db)):  # 定义异步处理函数
    cache_key = f"news:list:{params.category_id}:{params.page}:{params.page_size}"  # 按分类+分页维度构造缓存 key
    obj = await cache_get_or_set(cache_key, lambda: get_news_list(db, params.category_id, params.page, params.page_size), ttl=CACHE_TTL_NEWS_LIST)  # 优先读缓存，未命中再查库
    return ResponseModel(message="获取新闻列表成功", data=obj)  # 返回统一响应


@news_router.get("/detail", response_model=ResponseModel[NewsDetailOut])  # 根据 id 查询新闻详情接口
async def get_detail(params: Annotated[NewsDetailIn, Query()], db: AsyncSession = Depends(get_db)):  # 定义异步处理函数
    cache_key = f"news:detail:{params.id}"  # 按新闻 id 构造缓存 key
    data = await cache_get_or_set(  # 正文 + 相关推荐走缓存
        cache_key,
        lambda: _load_detail(db, params.id),
        ttl=CACHE_TTL_NEWS_DETAIL,
        cache_none=True,  # 不存在的新闻缓存 30s，防止刷不存在的 id 打穿数据库
    )
    if data is None:  # 缓存/数据库都没有该新闻
        raise BusinessException("新闻不存在", code=404)  # 抛 404 业务异常

    # 浏览量是高频变化的实时数据：不缓存，每次请求 +1 并覆盖到响应里
    views = await increment_view_count(db, params.id)  # 浏览量 +1，返回最新值
    if views is not None:  # 正常情况都能取到
        data["views"] = views  # 覆盖缓存里的旧浏览量
    return ResponseModel(message="获取新闻详情成功", data=data)  # 返回统一响应
