import uuid  # 导入 uuid，用于生成 access token 的唯一 id（jti）
from datetime import datetime, timedelta, timezone  # 导入日期时间工具，用于计算令牌时间

import jwt  # 导入 PyJWT，用于签发和解析 JWT

from app.config import settings  # 导入全局配置，读取密钥、算法与有效期


def access_token_expiry() -> datetime:  # 定义函数：计算访问令牌过期时间
    """访问令牌过期时间（返回 naive UTC）"""
    return (  # 返回计算出的过期时间
        datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)  # 当前 UTC 时间 + 访问令牌有效期分钟数
    ).replace(tzinfo=None)  # 去掉时区信息转成 naive UTC


def refresh_token_expiry_seconds() -> int:  # 定义函数：返回刷新令牌有效期（秒）
    """刷新令牌有效期（秒）"""
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400  # 天数换算成秒


def create_access_token(user_id: int, jti: str | None = None) -> str:  # 定义函数：签发访问令牌
    """签发访问令牌（HS256，含 sub / jti / iat / exp）"""
    payload = {  # 构造令牌载荷
        "sub": str(user_id),  # subject：用户 id
        "jti": jti or uuid.uuid4().hex,  # JWT 唯一 id，用于精确吊销（黑名单）
        "iat": datetime.now(timezone.utc).replace(tzinfo=None),  # 签发时间
        "exp": access_token_expiry(),  # 过期时间
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)  # 用密钥与算法签名，返回令牌字符串


def decode_access_token(token: str) -> dict | None:  # 定义函数：解析并校验令牌
    """解析并校验令牌，无效或过期返回 None"""
    try:  # 开始尝试解码
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])  # 校验签名并解码，成功返回载荷字典
    except jwt.PyJWTError:  # 捕获签名错误、过期等所有 JWT 相关异常
        return None  # 解析失败统一返回 None，交由上层处理