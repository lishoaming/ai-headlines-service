from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, Integer, String, Index
from sqlalchemy.dialects.mysql import INTEGER
from datetime import datetime


class UserBase(DeclarativeBase):
    id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True, index=True, comment="主键ID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")


class User(UserBase):
    __tablename__ = "user"
    __table_args__ = (
        Index("idx_user_username", "username", unique=True),
        Index("idx_user_email", "email", unique=True),
        Index("idx_user_phone", "phone", unique=True),
    )

    username: Mapped[str] = mapped_column(String(10), index=True, unique=True, nullable=False, comment="用户名")
    email: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=True, comment="邮箱")
    password: Mapped[str] = mapped_column(String(100), index=True, nullable=False, comment="密码")
    nickname: Mapped[str] = mapped_column(String(10), index=True, nullable=True, comment="昵称")
    avatar: Mapped[str] = mapped_column(String(20), index=True, nullable=True, comment="头像")
    gender: Mapped[str] = mapped_column(String(5), index=True, nullable=True, comment="性别")
    bio: Mapped[str] = mapped_column(String(200), index=True, nullable=True, comment="个人简介")
    phone: Mapped[int] = mapped_column(Integer(), unique=True, index=True, nullable=True, comment="手机号")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")