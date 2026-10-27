from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, Integer, String, Index, ForeignKey
from datetime import datetime


class NewsBase(DeclarativeBase):
    id = mapped_column(Integer, primary_key=True, comment="主键ID", autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class NewsCategory(NewsBase):
    __tablename__ = "news_category"
    __table_args__ = (
        Index("idx_name", "name"),
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True, comment="分类名称")

    def __repr__(self):
        return f"NewsCategory(id={self.id}, name={self.name!r}, created_at={self.created_at!r}, updated_at={self.updated_at!r})"


class News(NewsBase):
    __tablename__ = "news"
    __table_args__ = (
        Index("idx_category_id", "category_id"),
        Index("idx_publish_time", "publish_time"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="新闻标题")
    description: Mapped[str] = mapped_column(String(255), nullable=False, comment="新闻描述")
    content: Mapped[str] = mapped_column(String(255), nullable=False, comment="新闻内容")
    image: Mapped[str] = mapped_column(String(255), nullable=False, comment="新闻图片")
    author: Mapped[str] = mapped_column(String(255), nullable=False, comment="新闻作者")
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("news_category.id"), nullable=False, comment="新闻分类ID")
    views: Mapped[int] = mapped_column(Integer, default=0, comment="新闻点击量")
    publish_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True, default=datetime.now, comment="新闻发布时间时间")

    def __repr__(self):
        return f"News(id={self.id}, title={self.title!r}, description={self.description!r}, content={self.content!r}, category_id={self.category_id!r}, created_at={self.created_at!r}, updated_at={self.updated_at!r}, publish_time={self.publish_time!r})"