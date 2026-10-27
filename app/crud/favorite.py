from sqlalchemy.ext.asyncio import AsyncSession  # 导入异步会话类型
from app.models.favorite import Favorite  # 导入收藏模型
from sqlalchemy import select, delete  # 导入查询和删除语句类型
from app.utils.exceptions import BusinessException


# 根据用户id及新闻id查询是否收藏
async def check_is_favorite(db: AsyncSession, user_id: int, news_id: int) -> bool:
    """根据用户id及新闻id查询是否收藏"""
    stmt = select(Favorite).where((Favorite.user_id == user_id) & (Favorite.news_id == news_id))
    result = (await db.execute(stmt)).scalar_one_or_none()
    return result is not None

# 根据用户id查询收藏列表
async def get_favorite_list(db: AsyncSession, user_id: int,) -> list[Favorite]:
    """根据用户id查询收藏列表（按收藏时间倒序）"""
    stmt = select(Favorite).where(Favorite.user_id == user_id).order_by(Favorite.created_at.desc(), Favorite.id.desc())
    result = (await db.execute(stmt)).scalars().all()
    return result

# 添加收藏
async def add_favorite(db: AsyncSession, user_id: int, news_id: int) -> Favorite:
    """添加收藏：已收藏则直接返回已有记录，避免唯一键冲突"""
    stmt = select(Favorite).where((Favorite.user_id == user_id) & (Favorite.news_id == news_id))
    favorite = (await db.execute(stmt)).scalar_one_or_none()
    if favorite is not None:
        return favorite
    favorite = Favorite(user_id=user_id, news_id=news_id)
    db.add(favorite)
    await db.commit()
    await db.refresh(favorite)
    return favorite

# 删除单条收藏
async def remove_favorite(db: AsyncSession, user_id: int, news_id: int) -> None:
    """删除收藏"""
    # 检查收藏是否存在
    stmt = select(Favorite).where((Favorite.user_id == user_id) & (Favorite.news_id == news_id))
    favorite = (await db.execute(stmt)).scalar_one_or_none()
    if favorite is None:
        raise BusinessException("收藏不存在，无法删除")
    stmt = delete(Favorite).where((Favorite.user_id == user_id) & (Favorite.news_id == news_id))
    await db.execute(stmt)
    await db.commit()
    