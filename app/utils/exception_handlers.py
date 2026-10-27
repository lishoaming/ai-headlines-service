import logging  # 导入日志模块，用于记录异常堆栈

from fastapi import FastAPI, Request  # 导入 FastAPI 应用与请求类型
from fastapi.exceptions import RequestValidationError  # 导入请求参数校验异常
from fastapi.responses import JSONResponse  # 导入 JSON 响应，用于返回统一错误体
from pydantic import ValidationError  # 导入 Pydantic 数据模型校验异常
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError  # 导入 SQLAlchemy 约束冲突、连接与通用异常
from redis.exceptions import RedisError  # 导入 Redis 异常基类（含连接、超时等）
from starlette.exceptions import HTTPException as StarletteHTTPException  # 导入 HTTP 异常（FastAPI 的 HTTPException 是其子类）

from app.schemas.base import ResponseModel  # 导入统一响应模型
from app.utils.exceptions import BusinessException  # 导入业务异常基类

logger = logging.getLogger(__name__)  # 创建本模块的日志记录器


def _error_response(status_code: int, code: int, message: str) -> JSONResponse:  # 构造统一 JSON 错误响应
    return JSONResponse(  # 返回 JSON 响应对象
        status_code=status_code,  # 设置 HTTP 状态码
        content=ResponseModel(code=code, message=str(message)).model_dump(by_alias=True),  # 统一响应体（code/message/data）
    )


async def business_exception_handler(request: Request, exc: BusinessException) -> JSONResponse:  # 处理业务异常
    """业务规则校验失败抛出的异常"""
    return _error_response(exc.code, exc.code, exc.message)  # 复用异常携带的业务码与提示信息


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:  # 处理接口 HTTP 异常
    """接口主动抛出的 HTTPException（401/404/422 等）"""
    return _error_response(exc.status_code, exc.status_code, exc.detail)  # 复用异常自带的状态码与信息


async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:  # 处理请求参数校验异常
    """请求参数/body 校验失败"""
    errors = exc.errors()  # 取出所有校验错误
    first = errors[0] if errors else {}  # 取第一条错误
    loc = ".".join(str(x) for x in first.get("loc", []))  # 出错的字段路径
    msg = first.get("msg", "请求参数校验失败")  # 出错原因
    message = f"{loc}: {msg}" if loc else str(msg)  # 拼出可读提示
    return _error_response(422, 422, message)  # 返回 422


async def data_validation_handler(request: Request, exc: ValidationError) -> JSONResponse:  # 处理数据模型校验异常
    """Pydantic 数据模型校验失败"""
    message = "数据校验失败：" + "; ".join(str(e.get("msg", "")) for e in exc.errors()[:3])  # 汇总前三条错误原因
    return _error_response(422, 422, message)  # 返回 422


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:  # 处理 SQL 约束冲突异常
    """唯一/外键等约束冲突"""
    logger.warning("约束冲突 [%s %s]: %s", request.method, request.url.path, exc)  # 记录约束冲突日志
    return _error_response(400, 400, "数据冲突，请检查请求内容")  # 对外返回通用冲突提示


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:  # 处理数据库/SQL 通用异常
    """数据库连接、SQL 语法等通用异常"""
    logger.error("数据库异常 [%s %s]: %s", request.method, request.url.path, exc, exc_info=(type(exc), exc, exc.__traceback__))  # 记录完整堆栈
    return _error_response(500, 500, "数据库操作异常")  # 对外返回通用信息，不暴露内部细节


async def operational_error_handler(request: Request, exc: OperationalError) -> JSONResponse:  # 处理数据库连接异常
    """数据库连接失败/超时等操作层异常"""
    logger.error("数据库连接异常 [%s %s]: %s", request.method, request.url.path, exc, exc_info=(type(exc), exc, exc.__traceback__))  # 记录完整堆栈
    return _error_response(503, 503, "数据库连接不可用，请稍后重试")  # 返回服务暂不可用


async def redis_error_handler(request: Request, exc: RedisError) -> JSONResponse:  # 处理 Redis 缓存异常
    """Redis 连接/操作异常"""
    logger.error("缓存异常 [%s %s]: %s", request.method, request.url.path, exc, exc_info=(type(exc), exc, exc.__traceback__))  # 记录完整堆栈
    return _error_response(503, 503, "缓存服务异常，请稍后重试")  # 返回服务暂不可用


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # 兜底处理未预期的异常
    """未预期异常的兜底处理"""
    logger.error("未处理异常 [%s %s]: %s", request.method, request.url.path, exc, exc_info=(type(exc), exc, exc.__traceback__))  # 记录完整堆栈
    return _error_response(500, 500, "服务器内部错误")  # 对外返回通用信息


def register_exception_handlers(app: FastAPI) -> None:  # 把所有异常处理器注册到应用
    """注册全局异常处理器"""
    app.add_exception_handler(BusinessException, business_exception_handler)  # 业务异常
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # 接口 HTTP 异常
    app.add_exception_handler(RequestValidationError, request_validation_handler)  # 请求参数校验异常
    app.add_exception_handler(ValidationError, data_validation_handler)  # 数据模型校验异常
    app.add_exception_handler(IntegrityError, integrity_error_handler)  # SQL 约束冲突异常
    app.add_exception_handler(OperationalError, operational_error_handler)  # 数据库连接异常
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)  # 数据库/SQL 通用异常
    app.add_exception_handler(RedisError, redis_error_handler)  # Redis 缓存异常
    app.add_exception_handler(Exception, unhandled_exception_handler)  # 兜底异常