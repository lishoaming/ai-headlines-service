from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.db import get_db
from app.crud.history import add_history as crud_add_history, get_history_list as crud_get_history_list, remove_history as crud_remove_history, clear_history as crud_clear_history  # 导入历史记录创建、查询、删除、清空函数
from app.dependencies import get_current_user
from app.models.history import History  # 导入 History ORM 模型
from app.schemas.base import ResponseModel
from app.schemas.history import HistoryAddIn, HistoryDetailOut
from app.models.user import User  # 导入 User ORM 模型
from app.crud.news import get_news_detail as crud_get_news_detail  # 导入新闻详情查询函数

history_router = APIRouter(prefix="/api/history", tags=["历史记录"])  # 创建历史记录路由，统一前缀 /api/history
PAGE_SIZE = 10  # 历史记录列表每页条数

# 添加历史记录
@history_router.post("/add", response_model=ResponseModel)
async def add_history(history: HistoryAddIn,
                      db: AsyncSession = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    history_orm = History(
        news_id=history.news_id,
        user_id=current_user.id,
    )
    await crud_add_history(db, history_orm)
    return ResponseModel(message="历史记录添加成功")

# 获取历史记录列表
@history_router.get("/list", response_model=ResponseModel)
async def get_history_list(page: int = Query(1, ge=1, description="页码"),
                          db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    """获取历史记录列表（同一条新闻只保留最近一次浏览时间）"""
    history_rows = await crud_get_history_list(db, current_user.id)  # [(news_id, view_time)]
    total = len(history_rows)
    # 分页
    start = (page - 1) * PAGE_SIZE
    page_rows = history_rows[start:start + PAGE_SIZE]

    # 获取文章列表
    news_detail = []
    for news_id, view_time in page_rows:
        news = await crud_get_news_detail(db, news_id)
        if news is None:  # 新闻已被删除，跳过
            continue
        item = HistoryDetailOut.model_validate(news)  # ORM 对象转出参模型
        item.view_time = view_time  # 补充浏览时间
        news_detail.append(item)

    has_more = page * PAGE_SIZE < total  # 是否还有下一页

    return ResponseModel(
          data= {
            "list": news_detail,
            "total": total,
            "hasMore": has_more,
          }
        )

# 删除浏览历史
@history_router.delete("/remove", response_model=ResponseModel)
async def remove_history(id: int = Query(..., ge=1, description="新闻ID"),
                         db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    """删除某条新闻的浏览历史（该新闻的全部浏览记录）"""
    await crud_remove_history(db, current_user.id, id)  # 没有可删除的记录会抛业务异常
    return ResponseModel(message="删除成功")

# 清空浏览历史
@history_router.delete("/clear", response_model=ResponseModel)
async def clear_history(db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    """清空当前用户的全部浏览历史"""
    deleted = await crud_clear_history(db, current_user.id)  # 返回删除条数
    return ResponseModel(message="清空成功", data={"deleted": deleted})
