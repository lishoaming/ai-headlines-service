# 新闻分类CRUD操作
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.news import NewsCategory, News
from sqlalchemy import func, select


# 获取新闻分类列表
async def get_news_categories(db: AsyncSession):
    # 构建查询语句
    stmt = select(NewsCategory)
    # 执行查询
    result = await db.execute(stmt)
    # 提取结果
    list = result.scalars().all() or []
    return list

# 根据分类id 获取新闻列表
async def get_news_list(db: AsyncSession, category_id: int, page: int = 1, page_size: int = 10):
    # 构建查询语句
    stmt = select(News).where(News.category_id == category_id).offset((page - 1) * page_size).limit(page_size)
    # 执行查询
    result = await db.execute(stmt)
    # 提取结果
    list = result.scalars().all() or []
    # 计算总条数    
    total = await db.execute(select(func.count(News.id)).where(News.category_id == category_id))
    total = total.scalar() or 0
    return {
        "list": list,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasMore": total > page * page_size,
    }


# 根据id 查询新闻详情
async def get_news_detail(db: AsyncSession, id: int):
    # 构建查询语句
    stmt = select(News).where(News.id == id)
    # 执行查询
    result = await db.execute(stmt)
    # 提取结果
    detail = result.scalar() or None
    return detail
