from sqlalchemy.ext.asyncio import AsyncSession  # 导入异步会话类型
from app.models.history import History  # 导入历史记录模型
from app.utils.exceptions import BusinessException
from sqlalchemy import delete, func, select  # 导入查询、删除语句与聚合函数


# 历史记录 CRUD
# 添加历史记录
async def add_history(db: AsyncSession, history: History):
    db.add(history)
    await db.commit()
    await db.refresh(history)
    # 判断入库是否成功：refresh 后 id 有值说明写入成功
    if not history.id:
        raise BusinessException("历史记录添加失败")
    return history


# 获取历史记录列表
async def get_history_list(db: AsyncSession, user_id: int) -> list:
    """获取历史记录列表：同一条新闻只保留最近一次浏览时间，按浏览时间倒序"""
    stmt = (
        select(History.news_id, func.max(History.view_time).label("view_time"))
        .where(History.user_id == user_id)
        .group_by(History.news_id)
        .order_by(func.max(History.view_time).desc())
    )
    result = (await db.execute(stmt)).all()
    return result


# 删除浏览历史
async def remove_history(db: AsyncSession, user_id: int, news_id: int) -> None:
    """删除某条新闻的全部浏览记录（只能删除自己的记录）"""
    stmt = delete(History).where((History.user_id == user_id) & (History.news_id == news_id))
    result = await db.execute(stmt)
    await db.commit()
    if result.rowcount == 0:  # 没有可删除的记录
        raise BusinessException("历史记录不存在，无法删除")


# 清空浏览历史
async def clear_history(db: AsyncSession, user_id: int) -> int:
    """清空当前用户的全部浏览记录，返回删除条数"""
    stmt = delete(History).where(History.user_id == user_id)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount
