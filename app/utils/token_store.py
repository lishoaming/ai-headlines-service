import secrets  # 导入 secrets，生成安全的随机刷新令牌
import time  # 导入 time，用于计算 access token 剩余有效期
import uuid  # 导入 uuid，用于生成 access token 的 jti

from redis.asyncio import Redis  # 导入 Redis 类型，用于类型标注

from app.utils.security import create_access_token, refresh_token_expiry_seconds  # 导入签发与有效期工具

REFRESH_PREFIX = "rt:"  # refresh token 的 key 前缀：单个 refresh -> user_id
USER_REFRESH_PREFIX = "rtu:"  # 用户 refresh 集合的 key 前缀：user_id -> 该用户所有 refresh
BLACKLIST_PREFIX = "bl:"  # access token 黑名单的 key 前缀：jti -> 已吊销标记


def _refresh_key(token: str) -> str:  # 构造 refresh token 的 key
    return f"{REFRESH_PREFIX}{token}"


def _user_refresh_key(user_id: int) -> str:  # 构造用户 refresh 集合的 key
    return f"{USER_REFRESH_PREFIX}{user_id}"


def _blacklist_key(jti: str) -> str:  # 构造 access 黑名单的 key
    return f"{BLACKLIST_PREFIX}{jti}"


async def issue_tokens(redis: Redis, user_id: int) -> dict:  # 签发一对 token 并写入 Redis
    """签发 access + refresh 令牌对"""
    jti = uuid.uuid4().hex  # 生成本次 access token 的唯一 id
    access_token = create_access_token(user_id, jti=jti)  # 签发 access token（短命）
    refresh_token = secrets.token_urlsafe(32)  # 生成不透明 refresh token（随机串）
    await redis.set(_refresh_key(refresh_token), str(user_id), ex=refresh_token_expiry_seconds())  # refresh -> user_id，设 TTL
    await redis.sadd(_user_refresh_key(user_id), refresh_token)  # 把 refresh 加入该用户集合，便于吊销
    return {"token": access_token, "refresh_token": refresh_token}  # 返回 token 对


async def rotate_refresh(redis: Redis, refresh_token: str):  # 用旧 refresh 换新 token 对（含旋转）
    """刷新令牌：单次使用 + 旋转，返回新 token 对或 None"""
    user_id = await redis.getdel(_refresh_key(refresh_token))  # 原子地取出并删除，保证 refresh 只能使用一次
    if user_id is None:  # 查不到：说明已过期或已被使用过
        return None
    await redis.srem(_user_refresh_key(int(user_id)), refresh_token)  # 从用户集合移除已消费的旧 refresh
    return await issue_tokens(redis, int(user_id))  # 签发新 token 对（旋转）


async def revoke_all_user_tokens(redis: Redis, user_id: int):  # 吊销某用户所有 refresh
    """吊销用户全部刷新令牌（登出 / 改密时调用）"""
    tokens = await redis.smembers(_user_refresh_key(user_id))  # 取出该用户所有 refresh
    if tokens:  # 有记录才清理
        await redis.delete(_user_refresh_key(user_id))  # 删除集合 key
        for t in tokens:  # 逐个删除 refresh
            await redis.delete(_refresh_key(t))


async def blacklist_jti(redis: Redis, jti: str, exp: int):  # 把 access 的 jti 加入黑名单
    """将 access token 的 jti 加入黑名单，TTL 为其剩余有效期"""
    await redis.set(_blacklist_key(jti), "1", ex=max(int(exp) - int(time.time()), 1))  # 黑名单存到 access 过期为止


async def is_blacklisted(redis: Redis, jti: str) -> bool:  # 判断 jti 是否在黑名单
    """判断 access token 是否已被吊销"""
    return await redis.exists(_blacklist_key(jti)) == 1  # exists 返回 1 表示在黑名单