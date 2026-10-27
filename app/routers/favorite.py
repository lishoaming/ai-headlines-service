from fastapi import APIRouter

from app.config.db import get_db
from app.crud.favorite import check_is_favorite as check_is_favorite_crud, get_favorite_list as get_favorite_list_crud, add_favorite as add_favorite_crud, remove_favorite as remove_favorite_crud # 导入检查是否收藏函数
from app.dependencies import get_current_user
from app.schemas.base import ResponseModel  # 导入统一响应模型
from app.schemas.favorite import FavoriteAddIn  # 导入收藏入参模型
from sqlalchemy.ext.asyncio import AsyncSession  # 导入异步会话类型
from app.crud.news import get_news_detail as get_news_detail_crud  # 导入获取文章详细内容函数
from app.schemas.favorite import NewsDetailOut, FavoriteRemoveIn  # 导入文章详细内容出参模型
from fastapi import Depends, Query
from app.models.user import User



favorite_router = APIRouter(prefix='/api/favorite', tags=['收藏'])
PAGE_SIZE = 10  # 收藏列表每页条数

# 检查是否收藏该文章
@favorite_router.get('/check')
async def check_is_favorite(news_id: int = Query(..., description='新闻id', alias='newsId'), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """检查是否收藏该文章"""
    is_favorite = await check_is_favorite_crud(db, user.id, news_id)
    return ResponseModel(message="检查成功", data={"isFavorite": is_favorite})

# 查询收藏列表
@favorite_router.get('/list')
async def get_favorite_list(page: int = Query(1, ge=1, description='页码'), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """查询收藏列表（按收藏时间倒序分页）"""
    favorite_list = await get_favorite_list_crud(db, user.id)  # Favorite ORM 对象列表
    total = len(favorite_list)  # 收藏总数
    # 分页
    page_offset = (page - 1) * PAGE_SIZE
    page_favorites = favorite_list[page_offset:page_offset + PAGE_SIZE]
    # 文章列表
    news_details = []
    for favorite in page_favorites:
        news_detail_one = await get_news_detail_crud(db, favorite.news_id)
        if news_detail_one is None:  # 新闻已被删除，跳过
            continue
        item = NewsDetailOut.model_validate(news_detail_one)  # ORM 对象转出参模型
        item.favorite_time = favorite.created_at  # 补充收藏时间
        item.collection_id = favorite.id  # 补充收藏id
        news_details.append(item)
    has_more = page * PAGE_SIZE < total  # 是否还有下一页
    return ResponseModel(message="查询成功", data={"list": news_details, "total": total, "hasMore": has_more})

# 添加收藏
@favorite_router.post('/add')
async def add_favorite(body: FavoriteAddIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """添加收藏"""
    favorite = await add_favorite_crud(db, user.id, body.news_id)
    # 不能直接返回 ORM 对象：Pydantic 无法序列化，会抛 PydanticSerializationError
    return ResponseModel(message="添加成功", data={"id": favorite.id, "newsId": favorite.news_id, "favoriteTime": favorite.created_at})

# 删除单条收藏
@favorite_router.post('/remove')
async def remove_favorite(body: FavoriteRemoveIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """删除收藏"""
    await remove_favorite_crud(db, user.id, body.news_id)
    return ResponseModel(message="删除成功")
