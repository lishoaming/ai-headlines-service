import asyncio  # 导入 asyncio，用于把 CPU 密集的哈希操作丢到线程池

from fastapi import APIRouter, Depends  # 导入路由器类与依赖注入装饰器
from fastapi.security import HTTPAuthorizationCredentials  # 导入 Bearer 鉴权凭据类型
from redis.asyncio import Redis  # 导入 Redis 类型，用于类型标注
from sqlalchemy.ext.asyncio import AsyncSession  # 导入异步会话类型

from app.config.db import get_db  # 导入数据库会话依赖
from app.config.redis import get_redis  # 导入 Redis 依赖
from app.crud.user import get_user_by_username, register as register_user_db, update_user_password, \
    update_user_info_db, update_user_bio_db  # 导入用户数据库操作
from app.dependencies import get_current_user, security  # 导入当前用户依赖与 Bearer 鉴权实例
from app.models.user import User  # 导入 User ORM 模型
from app.schemas.base import ResponseModel  # 导入统一响应模型
from app.schemas.user import (  # 导入用户相关入参/出参模型
    ChangePasswordIn,
    RefreshIn,
    RefreshTokenOut,
    UserIn,
    UserLoginData,
    UserOut, UserUpdateIn, UserUpdateBioIn,
)
from app.utils.encrypt import hash_password, verify_password  # 导入密码哈希与校验函数
from app.utils.captcha import verify_captcha  # 导入图形验证码校验
from app.utils.exceptions import BusinessException  # 导入业务异常基类
from app.utils.security import decode_access_token  # 导入 JWT 解码函数
from app.utils.token_store import blacklist_jti, issue_tokens, revoke_all_user_tokens, rotate_refresh  # 导入 token 存储操作

user_router = APIRouter(prefix="/api/user", tags=["用户"])  # 创建用户路由，统一前缀 /api/user


async def _revoke_access(redis: Redis, token: str):  # 把当前 access token 的 jti 加入黑名单
    payload = decode_access_token(token)  # 解码取出令牌载荷
    if payload and payload.get("jti"):  # 载荷有效且包含 jti
        await blacklist_jti(redis, payload["jti"], payload.get("exp", 0))  # 将该 jti 加入黑名单


async def _ensure_captcha(body: UserIn) -> None:  # 校验图形验证码
    """登录/注册前校验验证码：放在账号密码校验之前，避免被用来枚举用户名"""
    if not body.captcha_id or not body.captcha_code:  # 未填验证码
        raise BusinessException("请输入验证码")
    if not await verify_captcha(body.captcha_id, body.captcha_code):  # 校验失败（错误/过期/已使用）
        raise BusinessException("验证码错误或已过期，请刷新后重试")


@user_router.post("/register", response_model=ResponseModel[None])  # 注册接口，POST /api/user/register
async def register_user(user_info: UserIn, db: AsyncSession = Depends(get_db)):  # 定义异步注册处理函数
    await _ensure_captcha(user_info)  # 先校验验证码
    if not user_info.username or not user_info.password:  # 校验用户名或密码是否为空
        raise BusinessException("用户名或密码不能为空")  # 为空则抛业务异常
    existing = await get_user_by_username(db, user_info.username)  # 按用户名查询是否已存在
    if existing:  # 判断用户是否已存在
        raise BusinessException("用户名已存在")  # 已存在则抛业务异常
    await register_user_db(db, user_info)  # 创建用户（数据库异常由全局处理器统一兜底）
    return ResponseModel(message="注册成功")  # 注册成功（无业务数据）


@user_router.post("/login", response_model=ResponseModel[UserLoginData])  # 登录接口，POST /api/user/login
async def login_user(  # 定义异步登录处理函数
    user_info: UserIn,  # 登录入参（用户名 + 密码）
    db: AsyncSession = Depends(get_db),  # 数据库会话
    redis: Redis = Depends(get_redis),  # Redis 客户端
):
    await _ensure_captcha(user_info)  # 先校验验证码（同时起到防暴力破解作用）
    if not user_info.username or not user_info.password:  # 校验用户名或密码是否为空
        raise BusinessException("用户名或密码不能为空")  # 为空则抛业务异常
    existing = await get_user_by_username(db, user_info.username)  # 按用户名查询用户
    if not existing:  # 判断用户是否存在
        raise BusinessException("用户名不存在")  # 不存在则抛业务异常
    if not verify_password(user_info.password, existing.password):  # 校验明文密码与库中哈希是否匹配
        raise BusinessException("密码错误")  # 密码错误则抛业务异常
    tokens = await issue_tokens(redis, existing.id)  # 签发 access + refresh 令牌对并写入 Redis
    user_info_out = UserOut.model_validate(existing)  # 把 ORM 用户对象转成出参模型
    return ResponseModel[UserLoginData](  # 登录成功，返回 token 对 + 用户信息
        message="登录成功",  # 提示登录成功
        data=UserLoginData(  # 数据体
            token=tokens["token"],  # 访问令牌
            refresh_token=tokens["refresh_token"],  # 刷新令牌
            user_info=user_info_out,  # 用户信息
        ),
    )


@user_router.post("/refresh", response_model=ResponseModel[RefreshTokenOut])  # 刷新接口，POST /api/user/refresh
async def refresh_token(body: RefreshIn, redis: Redis = Depends(get_redis)):  # 定义异步刷新处理函数
    tokens = await rotate_refresh(redis, body.refresh_token)  # 用旧 refresh 换新 token 对（旋转，单次使用）
    if tokens is None:  # 刷新令牌无效或已过期
        raise BusinessException("refresh token 无效或已过期", code=401)  # 抛 401 业务异常
    return ResponseModel(message="刷新成功", data=tokens)  # 返回新 token 对


@user_router.post("/logout", response_model=ResponseModel[None])  # 登出接口，POST /api/user/logout
async def logout_user(  # 定义异步登出处理函数
    credentials: HTTPAuthorizationCredentials = Depends(security),  # 读取当前 access token
    current_user: User = Depends(get_current_user),  # 当前登录用户
    redis: Redis = Depends(get_redis),  # Redis 客户端
):
    await revoke_all_user_tokens(redis, current_user.id)  # 吊销该用户所有 refresh
    await _revoke_access(redis, credentials.credentials)  # 把当前 access 的 jti 加入黑名单
    return ResponseModel(message="登出成功")  # 登出成功（无业务数据）


@user_router.post("/change-password", response_model=ResponseModel[None])  # 修改密码接口，POST /api/user/change-password
async def change_password(  # 定义异步修改密码处理函数
    body: ChangePasswordIn,  # 修改密码入参（旧密码 + 新密码）
    credentials: HTTPAuthorizationCredentials = Depends(security),  # 读取当前 access token
    current_user: User = Depends(get_current_user),  # 当前登录用户
    db: AsyncSession = Depends(get_db),  # 数据库会话
    redis: Redis = Depends(get_redis),  # Redis 客户端
):
    if not verify_password(body.old_password, current_user.password):  # 校验旧密码是否正确
        raise BusinessException("旧密码错误")  # 旧密码错误则抛业务异常
    new_hashed = await asyncio.to_thread(hash_password, body.new_password)  # 在线程池中哈希新密码
    await update_user_password(db, current_user, new_hashed)  # 更新数据库中的密码哈希
    await revoke_all_user_tokens(redis, current_user.id)  # 吊销该用户所有 refresh
    await _revoke_access(redis, credentials.credentials)  # 黑名单当前 access
    return ResponseModel(message="修改密码成功，请重新登录")  # 修改成功（无业务数据）

# 获取当前登陆用户信息
@user_router.get("/info", response_model=ResponseModel[UserOut])  # 获取用户信息接口，GET /api/user/info
async def get_user_info(  # 定义异步获取用户信息处理函数
    current_user: User = Depends(get_current_user),  # 当前登录用户
):
    return ResponseModel(message="获取用户信息成功", data=UserOut.model_validate(current_user))  # 把 ORM 用户对象转成出参模型

 # 修改用户信息
@user_router.put("/update", response_model=ResponseModel[None])  # 定义异步修改用户信息处理函数
async def update_user_info(  # 定义异步修改用户信息处理函数
    body: UserUpdateIn,  # 修改用户信息入参（用户名 + 手机号 + 邮箱）
    current_user: User = Depends(get_current_user),  # 当前登录用户
    db: AsyncSession = Depends(get_db),  # 数据库会话
):
    if not current_user.username:  # 校验用户名是否为空
        raise BusinessException("用户名不能为空")  # 为空则抛业务异常
    user = await update_user_info_db(db, current_user, body)  # 更新数据库中的用户信息
    if not user:  # 判断是否更新成功
        raise BusinessException("用户不存在")  # 失败则抛业务异常
    return ResponseModel(message="修改用户信息成功", data=UserOut.model_validate(user))  # 把 ORM 用户对象转成出参模型  # 修改成功（无业务数据）

# 修改简介
@user_router.put('/info', response_model=ResponseModel[None])
async def update_user_bio(  # 定义异步修改用户简介处理函数
    body: UserUpdateBioIn,  # 修改用户简介入参（个人简介等）
    current_user: User = Depends(get_current_user),  # 当前登录用户
    db: AsyncSession = Depends(get_db),  # 数据库会话
):
    user = await update_user_bio_db(db, current_user, body.bio)  # 更新数据库中的用户简介
    if not user:  # 判断是否更新成功
        raise BusinessException("用户不存在")  # 失败则抛业务异常
    return ResponseModel(message="修改用户简介成功")  # 修改成功（无业务数据）