from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # 导入异步会话类、异步会话工厂、异步引擎
from app.config import settings  # 导入项目全局配置对象（数据库地址等参数来自这里）

# 引擎创建
engine = create_async_engine(  # 创建异步数据库引擎（内部维护连接池）
    settings.DATABASE_URL,  # 数据库连接串，如 mysql+aiomysql://用户:密码@主机:端口/库名
    pool_pre_ping=True,  # 每次从池中取连接前先探活，避免拿到已断开的连接
    pool_recycle=3600,  # 连接存活超过 3600 秒即回收重建，防止 MySQL 主动断连
    echo=settings.DEBUG,  # DEBUG 为真时打印实际执行的 SQL，便于调试
)

# 会话工厂创建
AsyncSessionLocal = async_sessionmaker(  # 创建异步会话工厂，用于按需生产会话
    engine,  # 绑定上面创建的引擎
    class_=AsyncSession,  # 指定生成 AsyncSession 类型的会话对象
    expire_on_commit=False  # 提交后不让对象属性过期，提交后仍可读取数据
)  


# 数据库会话依赖函数
async def get_db():  # 数据库会话依赖函数，供 FastAPI 依赖注入使用
    async with AsyncSessionLocal() as session:  # 打开一个异步会话，代码块结束后自动关闭
        try:  # 正常流程分支
            yield session  # 把会话交给接口函数使用
        except Exception:  # 接口执行过程中抛出异常时
            await session.rollback()  # 回滚当前事务，避免脏数据写入
            raise  # 把异常继续向上抛出，交由全局异常处理
