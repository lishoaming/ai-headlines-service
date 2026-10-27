"""图形验证码接口

GET /api/captcha     获取一张验证码图片（无需登录）
POST 校验统一走 app.utils.captcha.verify_captcha，由登录/注册等业务接口内部调用，
不直接对外暴露校验接口，避免被拿来暴力试错。
"""

import logging  # 记录生成失败等异常

from fastapi import APIRouter  # 导入路由
from fastapi.concurrency import run_in_threadpool  # 把 CPU 密集的绘图放到线程池，避免阻塞事件循环

from app.config import settings  # 读取验证码 TTL
from app.schemas.base import ResponseModel  # 导入统一响应模型
from app.schemas.captcha import CaptchaOut  # 导入验证码出参模型
from app.utils import captcha as captcha_utils  # 导入验证码生成/存储工具

logger = logging.getLogger(__name__)  # 创建本模块的日志记录器

captcha_router = APIRouter(prefix="/api/captcha", tags=["验证码"])  # 创建验证码路由


@captcha_router.get("", response_model=ResponseModel[CaptchaOut])  # 获取图形验证码
async def get_captcha():  # 定义异步处理函数
    """生成图形验证码，返回 captchaId 与图片（PNG data URI）"""
    code, image = await run_in_threadpool(captcha_utils.generate_captcha)  # 绘图在线程池执行
    captcha_id = await captcha_utils.save_captcha(code)  # 明文只存服务端 Redis，TTL 120 秒
    return ResponseModel(  # 返回统一响应
        message="获取验证码成功",
        data=CaptchaOut(captcha_id=captcha_id, image=image, expires_in=settings.CACHE_TTL_CAPTCHA),
    )
