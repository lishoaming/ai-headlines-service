from fastapi import FastAPI
from fastapi.testclient import TestClient
import app.main
from app.utils.exception_handlers import register_exception_handlers
from app.utils.exceptions import BusinessException

print("main handlers count:", len(app.main.app.exception_handlers))
print("BusinessException registered:", BusinessException in app.main.app.exception_handlers)

app = FastAPI()
register_exception_handlers(app)


@app.get("/biz")
async def biz():
    raise BusinessException("用户名已存在")


@app.get("/biz404")
async def biz404():
    raise BusinessException("新闻不存在", code=404)


client = TestClient(app, raise_server_exceptions=False)
print("biz:", client.get("/biz").status_code, client.get("/biz").json())
print("biz404:", client.get("/biz404").status_code, client.get("/biz404").json())
print("DONE")