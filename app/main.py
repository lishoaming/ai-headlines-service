from contextlib import asynccontextmanager  # 导入异步上下文管理器，用于应用生命周期

from fastapi import FastAPI  # 导入 FastAPI 框架
from fastapi.middleware.cors import CORSMiddleware  # 导入 CORS 中间件

from app.routers.ai import ai_router  # 导入 AI 问答路由
from app.routers.captcha import captcha_router  # 导入验证码路由
from app.routers.favorite import favorite_router
from app.routers.history import history_router
from app.routers.news import news_router  # 导入新闻路由
from app.routers.user import user_router  # 导入用户路由

from app.config import settings  # 导入全局配置
from app.config.cors import headers, methods, origins  # 导入 CORS 配置
from app.config.redis import redis_client  # 导入 Redis 客户端
from app.utils.exception_handlers import register_exception_handlers  # 导入全局异常处理器注册函数


@asynccontextmanager  # 定义应用生命周期
async def lifespan(app: FastAPI):  # 启动/关闭时的钩子
    yield  # 应用运行期间直接放行
    await redis_client.aclose()  # 应用关闭时释放 Redis 连接（优雅退出）


app = FastAPI(  # 创建应用实例
    title=settings.APP_NAME,  # 应用名称
    version=settings.APP_VERSION,  # 应用版本
    debug=settings.DEBUG,  # 调试开关
    lifespan=lifespan,  # 挂载生命周期
)

app.add_middleware(  # 挂载 CORS 中间件
    CORSMiddleware,
    allow_origins=origins,  # 允许的来源
    allow_credentials=True,  # 允许携带凭据
    allow_methods=methods,  # 允许的方法
    allow_headers=headers,  # 允许的请求头
)


@app.get("/")  # 根路径
async def root():  # 返回服务信息
    return {"service": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/health")  # 健康检查路径
async def health():  # 返回健康状态
    return {"status": "ok"}


app.include_router(news_router)  # 注册新闻路由
app.include_router(user_router)  # 注册用户路由
app.include_router(history_router)  # 注册历史路由
app.include_router(favorite_router)  # 注册收藏路由
app.include_router(ai_router)  # 注册 AI 问答路由（Key 只保存在服务端 .env，前端不再持有）
app.include_router(captcha_router)  # 注册验证码路由

register_exception_handlers(app)  # 注册全局异常处理器