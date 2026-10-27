"""验证码相关出参模型"""

from app.schemas.base import CamelModel  # 导入业务模型基类（自动驼峰序列化）


class CaptchaOut(CamelModel):
    """图形验证码出参"""
    captcha_id: str  # 验证码唯一标识，提交表单时需一并回传
    image: str  # PNG 图片 data URI，前端可直接作为 <img src> 使用
    expires_in: int  # 有效期（秒）
