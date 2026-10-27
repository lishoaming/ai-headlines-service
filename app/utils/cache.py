"""业务缓存封装：只负责 Redis 读写、key 前缀、TTL、降级，JSON 编解码见 app.utils.serializer

使用约定（避免误用）：
1. 传入的 key 是业务 key（如 "news:list:1:1:10"），不要自带 app: 前缀，函数内部会统一拼接；
2. 存对象直接传对象（Pydantic 模型/list/dict）给 set_json / get_or_set，不要先 serializer.dumps，
   否则会把 JSON 字符串再序列化一次，读出来是字符串而不是对象；
3. get_json 无法区分“未命中”和“缓存的 None”；需要区分时用 get_or_set(..., cache_none=True)；
4. 用户维度的数据必须把 user_id 拼进 key，并在写操作后显式 delete 对应 key；
5. delete / delete_prefix 不受 CACHE_ENABLED 影响（用于清理遗留数据）；delete_prefix 空前缀会被拒绝。
"""

import logging  # 导入日志模块，用于记录缓存降级、脏数据等情况
from typing import Any, Awaitable, Callable  # 导入类型标注工具

from redis.exceptions import RedisError  # 导入 Redis 异常基类（连接、超时等）

from app.config import settings  # 导入全局配置
from app.config.redis import redis_client  # 导入全局 Redis 客户端（模块级单例）
from app.utils import serializer  # 导入 JSON 序列化/反序列化工具（与缓存操作解耦）

logger = logging.getLogger(__name__)  # 创建本模块的日志记录器

_CACHE_PREFIX = settings.CACHE_PREFIX.strip().strip(":") or "app"  # 读取可配置前缀，去掉首尾冒号，空则用默认值
CACHE_PREFIX = f"{_CACHE_PREFIX}:"  # 业务缓存统一 key 前缀，与 token 相关的 rt:/rtu:/bl: 区分开
_NONE_MARKER = {"__cache_none__": True}  # 空值（None）缓存标记，用于防缓存穿透
_DELETE_CHUNK_SIZE = 500  # 按前缀删除时单次 DEL 的最大 key 数量，避免单条命令过大


def _key(key: str) -> str:  # 拼接带前缀的完整 key
    if key.startswith(CACHE_PREFIX):  # 调用方误带了前缀：自动去掉，避免产生 app:app:xxx 脏 key
        logger.warning("缓存 key 不应自带前缀 %s，已自动去除 key=%s", CACHE_PREFIX, key)
        key = key[len(CACHE_PREFIX):]
    return f"{CACHE_PREFIX}{key}"


async def _load(key: str) -> tuple[bool, Any]:  # 读取缓存并区分“未命中”和“空值命中”
    """内部方法：返回 (是否命中, 缓存值)；未启用缓存或 Redis 异常时视为未命中"""
    if not settings.CACHE_ENABLED:  # 缓存开关关闭：视为未命中
        return False, None
    try:
        raw = await redis_client.get(_key(key))  # 读原始字符串
    except RedisError as exc:  # Redis 故障：降级为未命中，让调用方回源数据库
        logger.warning("读取缓存失败，降级查库 key=%s: %s", _key(key), exc)
        return False, None
    if raw is None:  # key 不存在
        return False, None
    try:
        data = serializer.loads(raw)  # 反序列化为 Python 对象
    except ValueError:  # 脏数据（非法 JSON）：删掉，避免一直反序列化失败
        logger.warning("缓存数据无法反序列化，已删除 key=%s", _key(key))
        await delete(key)
        return False, None
    if data == _NONE_MARKER:  # 空值缓存：算命中，但值为 None
        return True, None
    return True, data  # 正常命中


async def get_json(key: str) -> Any | None:  # 读取缓存并反序列化
    """读取 JSON 缓存：未命中、空值缓存、已禁用或 Redis 异常时返回 None"""
    hit, value = await _load(key)  # 读取并区分命中状态
    return value if hit else None  # 未命中统一返回 None


async def exists(key: str) -> bool:  # 判断缓存 key 是否存在
    """判断缓存 key 是否存在：未启用缓存或 Redis 异常时返回 False"""
    if not settings.CACHE_ENABLED:  # 缓存开关关闭：视为不存在
        return False
    try:
        return bool(await redis_client.exists(_key(key)))  # 返回 0/1，转成布尔值
    except RedisError as exc:  # Redis 故障：降级为不存在
        logger.warning("判断缓存存在失败 key=%s: %s", _key(key), exc)
        return False


async def set_json(key: str, value: Any, ttl: int | None = None) -> bool:  # 写入缓存
    """写入 JSON 缓存并设置 TTL，成功返回 True；序列化失败或 Redis 异常返回 False"""
    if not settings.CACHE_ENABLED:  # 缓存开关关闭：不写
        return False
    expire = ttl if ttl and ttl > 0 else settings.CACHE_DEFAULT_TTL  # 非法 TTL 回退到默认值
    try:
        # 序列化交给 serializer：Pydantic 模型按 camelCase 导出，datetime 等用 str 兜底
        payload = serializer.dumps(value)
        await redis_client.set(_key(key), payload, ex=expire)  # 写入并设置过期时间
        return True
    except (RedisError, TypeError, ValueError) as exc:  # Redis 异常或值不可序列化：降级为不缓存
        logger.warning("写入缓存失败 key=%s: %s", _key(key), exc)
        return False


async def delete(*keys: str) -> int:  # 删除一个或多个缓存 key
    """删除指定缓存 key（自动补前缀），返回实际删除数量"""
    if not keys:  # 没有 key 直接返回
        return 0
    try:
        return int(await redis_client.delete(*[_key(key) for key in keys]) or 0)  # 批量删除
    except RedisError as exc:  # Redis 故障：删除失败不影响主流程
        logger.warning("删除缓存失败 keys=%s: %s", keys, exc)
        return 0


async def delete_prefix(prefix: str) -> int:  # 按前缀批量删除缓存
    """按前缀批量删除缓存 key（SCAN 分批 + DEL 分批），返回实际删除数量

    删除类操作不检查 CACHE_ENABLED：即使缓存被临时关闭，也应能清理遗留的旧数据。
    空前缀会被拒绝，避免误清空全部业务缓存。
    """
    normalized = prefix.strip().strip(":")  # 去掉首尾空白和冒号
    if normalized.startswith(CACHE_PREFIX):  # 调用方误带前缀（如 app:news）
        normalized = normalized[len(CACHE_PREFIX):]
    if not normalized or normalized == _CACHE_PREFIX:  # 空前缀或只有环境前缀：拒绝执行
        logger.warning("按前缀删除被拒绝：前缀不能为空 prefix=%r", prefix)
        return 0
    pattern = f"{_key(normalized)}*"  # 拼出匹配模式
    deleted = 0  # 累计删除数量
    batch: list[str] = []  # 当前待删除的 key 批次
    try:
        async for key in redis_client.scan_iter(match=pattern, count=_DELETE_CHUNK_SIZE):  # 用 SCAN 避免 KEYS 阻塞
            batch.append(key)  # 收集 key
            if len(batch) >= _DELETE_CHUNK_SIZE:  # 达到批次上限就删除，防止单条 DEL 命令过大
                deleted += int(await redis_client.delete(*batch) or 0)
                batch.clear()  # 清空批次
        if batch:  # 处理最后不足一批的 key
            deleted += int(await redis_client.delete(*batch) or 0)
        return deleted
    except RedisError as exc:  # Redis 故障：降级为删除失败
        logger.warning("按前缀删除缓存失败 pattern=%s: %s", pattern, exc)
        return deleted  # 返回已经删除的数量


async def get_or_set(key: str, factory: Callable[[], Awaitable[Any]], ttl: int | None = None,  # cache-aside 模式
                     cache_none: bool = False) -> Any:
    """先读缓存，未命中则执行 factory 回源，成功结果写回缓存并返回

    cache_none=True 时会把回源得到的 None 也缓存一小段时间（CACHE_NONE_TTL），
    用于防止“数据不存在”的请求反复穿透到数据库。
    """
    hit, cached = await _load(key)  # 尝试命中缓存
    if hit:  # 命中：直接返回（模型会被调用方的 response_model 重新校验）
        return cached
    value = await factory()  # 未命中：执行回源逻辑（如查数据库）
    if value is not None:  # 有值：按正常 TTL 缓存
        await set_json(key, value, ttl)
    elif cache_none:  # 空值且允许负缓存：写入较短 TTL 的空值标记
        await set_json(key, _NONE_MARKER, settings.CACHE_NONE_TTL)
    return value
