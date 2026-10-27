from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, Integer, String, Index
from datetime import datetime


class HistoryBase(DeclarativeBase):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="主键ID", autoincrement=True)
    news_id: Mapped[str] = mapped_column(String(255), comment="新闻ID")
    user_id: Mapped[str] = mapped_column(String(255), comment="用户ID")
    view_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="查看时间")


class History(HistoryBase):
    __tablename__ = "history"
    __table_args__ = {"comment": "历史记录表"}
    Index("idx_news_id", "news_id")
    Index("idx_user_id", "user_id")
    Index("idx_view_time", "view_time")
    Index("idx_id", "id")
