import asyncio  # 导入 asyncio，用于把 CPU 密集操作丢到线程池

from sqlalchemy import select, update  # 导入 select 和 update 语句构造器
from sqlalchemy.ext.asyncio import AsyncSession, result  # 导入异步会话类型

from app.models.user import User  # 导入用户的 ORM 模型
from app.schemas.user import UserIn, UserUpdateIn  # 导入注册入参模型
from app.utils.encrypt import hash_password  # 导入密码哈希函数


async def get_user_info(db: AsyncSession, id: int) -> User | None:  # 根据主键 id 查询单个用户
    return await db.get(User, id)  # 用主键查询并返回用户对象，无则返回 None


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:  # 根据用户名查询用户
    stmt = select(User).where(User.username == username)  # 构造查询：筛选指定用户名的用户
    result = await db.execute(stmt)  # 异步执行查询
    return result.scalars().first()  # 取第一条结果返回，无则返回 None


async def register(db: AsyncSession, user_info: UserIn) -> User:  # 创建新用户
    hashed = await asyncio.to_thread(hash_password, user_info.password)  # bcrypt 是 CPU 密集操作，放线程池避免阻塞事件循环
    user = User(  # 构造用户 ORM 对象
        username=user_info.username,  # 用户名
        password=hashed,  # 存哈希后的密码
    )
    db.add(user)  # 加入会话，登记待插入
    await db.commit()  # 提交事务，真正写入数据库
    await db.refresh(user)  # 刷新对象，获取数据库生成的主键等字段
    return user  # 返回创建好的用户对象


async def update_user_password(db: AsyncSession, user: User, new_hashed: str) -> User:  # 更新用户密码哈希
    user.password = new_hashed  # 设置新密码哈希
    db.add(user)  # 加入会话，登记待更新
    await db.commit()  # 提交事务，真正更新数据库记录
    await db.refresh(user)  # 刷新对象，获取数据库生成的主键等字段
    return user  # 返回更新后的用户

# 修改用户信息
async def update_user_info_db(db: AsyncSession, user: User, body: UserUpdateIn) -> User | None:  # 更新用户信息
    body = body.model_dump(exclude_unset=True, exclude_none=True)  # 排除所有 None 值，只更新有值的字段
    stmt = update(User).where(User.id == user.id).values(**body)  # 构造更新语句，更新用户表
    result =  await db.execute(stmt)  # 异步执行更新语句
    await db.commit()  # 提交事务
    await db.refresh(user)  # 刷新对象

    if result.rowcount == 0:
        return None  # 无更新行，返回 None
    return user  # 返回更新后的用户

# 修改用户简介
async def update_user_bio_db(db: AsyncSession, user: User, bio: str) -> User | None:  # 更新用户简介
    stmt = update(User).where(User.id == user.id).values(bio=bio)  # 构造更新语句，更新用户表
    result = await db.execute(stmt)  # 异步执行更新语句
    await db.commit()  # 提交事务
    await db.refresh(user)  # 刷新对象

    if result.rowcount == 0:
        return None  # 无更新行，返回 None
    return user  # 返回更新后的用户
