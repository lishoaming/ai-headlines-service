from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, Integer, Index
from datetime import datetime


class FavoriteBase(DeclarativeBase):
    id = mapped_column(Integer, primary_key=True, comment="主键ID", autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")


class Favorite(FavoriteBase):
    __tablename__ = 'favorite'
    Index('idx_favorite_user_id', 'user_id')
    Index('idx_favorite_id', 'id')
    Index("inx_favorite_news_id", "news_id")
    Index("idx_favorite_created_at", "created_at")

    # 外键约束由数据库 DDL 维护（fk_favorite_user / fk_favorite_news）。
    # 这里不声明 ForeignKey：user/news 模型各自使用独立的 DeclarativeBase，
    # 跨 registry 的 FK 无法解析表名，会在 flush 时抛 NoReferencedTableError。
    user_id: Mapped[int] = mapped_column(Integer, comment="用户ID")
    news_id: Mapped[int] = mapped_column(Integer, comment="新闻ID")