import redis.asyncio as aioredis  # 导入 redis 的异步客户端

from app.config import settings  # 导入全局配置

redis_client = aioredis.Redis(  # 创建全局 Redis 异步客户端（模块级单例）
    host=settings.REDIS_HOST,  # Redis 主机地址
    port=settings.REDIS_PORT,  # Redis 端口
    password=settings.REDIS_PASSWORD,  # Redis 密码
    db=settings.REDIS_DB,  # 使用的数据库编号
    decode_responses=True,  # 返回 str 而不是 bytes，方便直接读写
)


async def get_redis():  # FastAPI 依赖：yield 出 Redis 客户端
    yield redis_client  # 把客户端交给接口使用