# 跨域（CORS）配置
import os

from dotenv import load_dotenv

load_dotenv()

# 允许访问的前端来源：多个用英文逗号分隔，可通过 .env 的 CORS_ORIGINS 覆盖
_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
origins = [
    item.strip()
    for item in os.getenv("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if item.strip()
]

# 允许的请求方法
methods = [
    "GET",
    "POST",
    "PUT",
    "DELETE",
]

# 允许的请求头
headers = [
    "Content-Type",
    "Authorization",
    "Accept",  # SSE/流式请求需要
]
