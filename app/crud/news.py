from sqlalchemy import func, select, update  # 导入 SQL 函数与语句构造器
from sqlalchemy.ext.asyncio import AsyncSession  # 导入异步会话类型

from app.models.news import News, NewsCategory  # 导入新闻与新闻分类的 ORM 模型
from app.schemas.news import CategoryOut, NewsItemOut, NewsListOut  # 导入新闻出参模型


async def get_news_categories(db: AsyncSession) -> list[CategoryOut]:  # 获取新闻分类列表
    stmt = select(NewsCategory)  # 构造查询：查全部分类
    result = await db.execute(stmt)  # 执行查询
    items = result.scalars().all() or []  # 提取结果
    return [CategoryOut.model_validate(item) for item in items]  # 转成出参模型返回


async def get_news_list(db: AsyncSession, category_id: int, page: int = 1, page_size: int = 10) -> NewsListOut:  # 根据分类分页获取新闻列表
    stmt = select(News).where(News.category_id == category_id).offset((page - 1) * page_size).limit(page_size)  # 分页查询当前页
    result = await db.execute(stmt)  # 执行查询
    items = result.scalars().all() or []  # 当前页数据
    total = await db.execute(select(func.count(News.id)).where(News.category_id == category_id))  # 查询该分类总条数
    total = total.scalar() or 0  # 提取总数
    return NewsListOut(  # 组装分页出参模型
        list=[NewsItemOut.model_validate(item) for item in items],  # 当前页条目
        total=total,  # 总条数
        page=page,  # 页码
        page_size=page_size,  # 每页数量
        has_more=total > page * page_size,  # 是否还有下一页
    )


async def get_news_detail(db: AsyncSession, id: int) -> News | None:  # 根据 id 查询新闻详情
    return await db.get(News, id)  # 用主键查询并返回，无则 None


async def get_related_news(db: AsyncSession, category_id: int, id: int) -> list[NewsItemOut]:  # 获取相关推荐新闻
    stmt = select(News).where(  # 构造查询：同分类、排除自身
        News.category_id == category_id, News.id != id,
    ).order_by(News.views.desc(), News.created_at.desc()).limit(5)  # 按浏览量与时间倒序取 5 条
    result = await db.execute(stmt)  # 执行查询
    items = result.scalars().all() or []  # 提取结果
    return [NewsItemOut.model_validate(item) for item in items]  # 转成出参模型返回


async def increment_view_count(db: AsyncSession, id: int) -> int | None:  # 浏览量 +1，并返回最新浏览量
    try:  # 开始尝试
        await db.execute(update(News).where(News.id == id).values(views=News.views + 1))  # 原子自增浏览量
        await db.commit()  # 提交事务
    except Exception:  # 出错则回滚并继续抛出
        await db.rollback()  # 回滚事务
        raise  # 重新抛出异常
    # 详情正文走缓存后，浏览量必须实时读取，不能沿用缓存里的旧值
    result = await db.execute(select(News.views).where(News.id == id))  # 查询最新浏览量
    return result.scalar_one_or_none()  # 新闻不存在返回 None