"""图形验证码：生成图片 + Redis 存储 + 一次性校验

设计要点：
- 图片由 Pillow 绘制（随机旋转/颜色/干扰线/噪点），返回 data URI，前端可直接当 <img src> 用；
- 验证码文本只存在服务端 Redis（key: captcha:<id>），TTL 使用 CACHE_TTL_CAPTCHA（默认 120 秒）；
- 校验成功后立即删除，保证一次性使用；
- 前端只拿到 captchaId + 图片，无法从响应中直接读出答案。
"""

import base64
import hmac  # 常量时间比较，避免时序攻击
import io
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont  # 图片绘制库

from app.config import settings  # 读取验证码 TTL
from app.utils import cache  # 复用缓存封装（自动前缀 + 降级）

# 去掉 0/O、1/I/L 等易混淆字符
CHARS = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"

# 常见字体候选路径（Windows / Linux / macOS），找不到则用内置字体
_FONT_PATHS = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _load_font(size: int) -> ImageFont.ImageFont:
    """按候选路径加载字体，全部不可用时退回 Pillow 内置字体"""
    for path in _FONT_PATHS:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def _random_dark() -> tuple[int, int, int, int]:
    """随机深色，用于字符，保证与浅色背景有足够对比度"""
    return random.randint(20, 110), random.randint(20, 110), random.randint(20, 110), 255


def _random_light() -> tuple[int, int, int]:
    """随机浅色，用于干扰线与噪点，避免盖住字符"""
    return random.randint(150, 220), random.randint(150, 220), random.randint(150, 220)


def generate_captcha(length: int = 4, width: int = 120, height: int = 44) -> tuple[str, str]:
    """生成验证码

    Returns:
        (code, data_uri)：明文验证码（仅服务端保存）与可直接渲染的 PNG data URI
    """
    code = "".join(random.choices(CHARS, k=length))  # 随机验证码文本

    image = Image.new("RGB", (width, height), (245, 246, 248))  # 浅色背景
    draw = ImageDraw.Draw(image)

    # 干扰线
    for _ in range(4):
        draw.line(
            [
                (random.randint(0, width), random.randint(0, height)),
                (random.randint(0, width), random.randint(0, height)),
            ],
            fill=_random_light(),
            width=1,
        )

    # 逐字符绘制：随机字号、颜色、旋转角度，按槽位居中排布，避免重叠或超出边界
    margin = 4  # 左右留白
    slot = (width - margin * 2) // length  # 每个字符占据的宽度
    for index, char in enumerate(code):
        size = random.randint(24, 30)  # 字号
        font = _load_font(size)
        layer = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))  # 单独画布，便于旋转
        # anchor="mm"：以画布中心为锚点绘制，保证旋转后仍在画布内
        ImageDraw.Draw(layer).text((size, size), char, font=font, fill=_random_dark(), anchor="mm")
        layer = layer.rotate(random.uniform(-28, 28), resample=Image.Resampling.BICUBIC)  # 随机倾斜

        center_x = margin + slot * index + slot // 2  # 槽位中心
        center_y = height // 2 + random.randint(-2, 2)  # 轻微上下抖动
        image.paste(layer, (center_x - layer.width // 2, center_y - layer.height // 2), layer)  # 居中叠加

    # 噪点
    for _ in range(120):
        draw.point((random.randrange(width), random.randrange(height)), fill=_random_light())

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")  # 编码为 PNG
    data_uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    return code, data_uri


def _key(captcha_id: str) -> str:
    return f"captcha:{captcha_id}"


async def save_captcha(code: str) -> str:
    """保存验证码并返回 captchaId（随机 uuid），TTL 由配置决定"""
    import uuid  # 局部导入，避免与图片生成职责混在一起

    captcha_id = uuid.uuid4().hex
    await cache.set_json(_key(captcha_id), code.upper(), ttl=settings.CACHE_TTL_CAPTCHA)
    return captcha_id


async def verify_captcha(captcha_id: str, code: str) -> bool:
    """校验验证码：不区分大小写，校验成功后立即删除（一次性）"""
    if not captcha_id or not code:
        return False
    stored = await cache.get_json(_key(captcha_id))
    if not stored:
        return False
    if hmac.compare_digest(str(stored), code.strip().upper()):
        await cache.delete(_key(captcha_id))  # 用完即删，防止重复使用
        return True
    return False
