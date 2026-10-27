from datetime import datetime  # 导入 datetime 类型，用于时间字段
from typing import Optional  # 导入 Optional，用于可空字段类型

from pydantic import ConfigDict, Field  # 导入配置字典与字段约束

from app.schemas.base import CamelModel, DateTimeStr  # 导入驼峰序列化基类


class UserIn(CamelModel):  # 定义注册/登录入参模型
    """用户注册/登录入参"""
    username: str = Field(..., min_length=1, max_length=10, description="用户名（最多 10 个字符，与数据库一致）")
    password: str = Field(..., min_length=1, max_length=72, description="密码（bcrypt 最多 72 字节）")
    captcha_id: Optional[str] = None  # 图形验证码 id（由 GET /api/captcha 返回）
    captcha_code: Optional[str] = None  # 用户输入的验证码（不区分大小写）


class UserOut(CamelModel):  # 定义用户出参模型（不含密码）
    """用户出参（不含密码）"""
    id: int  # 用户主键 id
    username: str  # 用户名
    email: Optional[str] = None  # 邮箱，可空
    nickname: Optional[str] = None  # 昵称，可空
    avatar: Optional[str] = None  # 头像，可空
    gender: Optional[str] = None  # 性别，可空
    bio: Optional[str] = None  # 个人简介，可空
    phone: Optional[int] = None  # 手机号，可空
    created_at: DateTimeStr  # 创建时间，必填
    updated_at: Optional[DateTimeStr] = None  # 更新时间，可空
    model_config = ConfigDict(from_attributes=True)  # 允许直接从 ORM 对象读取属性


class UserLoginData(CamelModel):  # 定义登录成功数据模型
    """登录成功数据"""
    token: str  # 访问令牌（access token）
    refresh_token: str  # 刷新令牌（refresh token）
    user_info: UserOut  # 用户信息


class RefreshIn(CamelModel):  # 定义刷新令牌入参模型
    """刷新令牌入参"""
    refresh_token: str  # 刷新令牌，必填


class RefreshTokenOut(CamelModel):  # 定义刷新后返回的新 token 对
    """刷新后的新 token 对"""
    token: str  # 新访问令牌
    refresh_token: str  # 新刷新令牌


class ChangePasswordIn(CamelModel):  # 定义修改密码入参模型
    """修改密码入参"""
    old_password: str  # 旧密码，必填
    new_password: str  # 新密码，必填

# 修改用户信息入参
class UserUpdateIn(CamelModel):  # 定义修改用户信息入参模型
    """修改用户信息入参"""
    nickname: Optional[str] = None  # 昵称，可空
    avatar: Optional[str] = None  # 头像，可空
    gender: Optional[str] = None  # 性别，可空
    bio: Optional[str] = None  # 个人简介，可空
    phone: Optional[int] = None  # 手机号，可空

# 修改用户简介入参
class UserUpdateBioIn(CamelModel):  # 定义修改用户简介入参模型
    """修改用户简介入参"""
    bio: str  # 个人简介，必填
