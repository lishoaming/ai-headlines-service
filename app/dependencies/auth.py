from fastapi import Depends, HTTPException, status  # 导入依赖注入、HTTP 异常类与状态码常量
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer  # 导入 HTTP Bearer 鉴权相关类
from redis.asyncio import Redis  # 导入 Redis 类型，用于类型标注
from sqlalchemy.ext.asyncio import AsyncSession  # 导入异步数据库会话类型

from app.config.db import get_db  # 导入数据库会话依赖工厂
from app.config.redis import get_redis  # 导入 Redis 依赖工厂
from app.crud.user import get_user_info  # 导入按 id 查用户的方法
from app.models.user import User  # 导入 User ORM 模型
from app.utils.security import decode_access_token  # 导入 JWT 解码函数
from app.utils.token_store import is_blacklisted  # 导入黑名单校验函数

security = HTTPBearer(auto_error=False)  # 关闭自动报错，改为返回统一的中文提示

# 登录态失效统一提示（前端会据此清理登录态并跳转登录页）
_AUTH_EXPIRED_MESSAGE = "登录已过期，请重新登录"


async def get_current_user(  # 定义依赖函数：返回当前登录用户
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # 依赖注入：解析请求头里的 Bearer token
    db: AsyncSession = Depends(get_db),  # 依赖注入：获取数据库会话
    redis: Redis = Depends(get_redis),  # 依赖注入：获取 Redis 客户端
) -> User:  # 返回值类型为 User ORM 对象
    """从 Authorization: Bearer <token> 解析当前登录用户，并校验黑名单"""
    if credentials is None:  # 未携带 Authorization 头
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或登录已过期，请重新登录")
    payload = decode_access_token(credentials.credentials)  # 解码并校验 token，得到载荷（失败返回 None）
    if payload is None or "sub" not in payload:  # 判断 token 是否有效且包含用户 id 字段
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_AUTH_EXPIRED_MESSAGE)  # 无效则抛 401
    jti = payload.get("jti")  # 取出令牌唯一 id
    if jti and await is_blacklisted(redis, jti):  # 判断该令牌是否已被吊销（黑名单）
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_AUTH_EXPIRED_MESSAGE)  # 已过期则抛 401
    user = await get_user_info(db, int(payload["sub"]))  # 用载荷中的 sub（用户 id）查询用户
    if user is None:  # 判断用户是否存在
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在或已被删除，请重新登录")  # 不存在则抛 401
    return user  # 校验通过，返回用户对象供接口使用