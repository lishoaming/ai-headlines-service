"""数据库初始化脚本：建库 + 建表 + 写入初始数据（分类、示例新闻、管理员）

用法：
    1. 先把 ai-headlines-service/.env.example 复制为 .env，并填好 MySQL/Redis 配置；
    2. 确认 MySQL 已启动、账号密码可登录；
    3. 运行：  .\\venv\\Scripts\\python init_db.py

说明：
- 本脚本用 ORM 元数据自动建表（user / news / news_category / favorite / history）；
- 幂等：表已存在则跳过，不会重复建；但会补充缺失的初始数据（分类、管理员）；
- 示例新闻仅作演示，后续可在"更多/后台"里维护真实内容。
"""

import asyncio  # 异步入口
import sys  # 读取命令行参数
from pathlib import Path  # 定位项目根目录

from sqlalchemy import text  # 用于执行 raw SQL

# 确保以项目根目录运行时可导入 app 包（把本文件所在目录加入 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # 加载 .env

load_dotenv()  # 读取本地配置

from sqlalchemy.ext.asyncio import create_async_engine  # 创建异步引擎
from sqlalchemy.dialects import mysql  # 生成 MySQL 方言的建表 DDL

from app.config import settings  # 读取数据库连接配置
from app.utils.encrypt import hash_password  # 密码哈希（bcrypt）

# 导入全部模型，确保各自的 metadata 里已登记表
from app.models.user import User, UserBase
from app.models.news import News, NewsCategory, NewsBase
from app.models.favorite import Favorite, FavoriteBase
from app.models.history import History, HistoryBase


async def ensure_database_exists() -> None:
    """数据库本身不存在时先创建（不带库名连接 server 一次）"""
    # 拼一个不带 database 的连接串去连 MySQL server
    base = f"mysql+aiomysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}"
    server_engine = create_async_engine(base, pool_pre_ping=False)
    try:
        async with server_engine.connect() as conn:
            # 用反引号包裹库名，兼容库名含特殊字符的情况
            await conn.execute(
                text(f"CREATE DATABASE IF NOT EXISTS `{settings.MYSQL_DATABASE}` "
                     "CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")
            )
            await conn.commit()
        print(f"[1/4] 数据库 `{settings.MYSQL_DATABASE}` 已就绪（不存在则已创建）")
    finally:
        await server_engine.dispose()


async def create_tables() -> None:
    """按各模型的 metadata 建表（表已存在会自动跳过）"""
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        # 收集所有业务的元数据合并去重
        metas = {UserBase.metadata, NewsBase.metadata, FavoriteBase.metadata, HistoryBase.metadata}
        for meta in metas:
            async with engine.begin() as conn:
                # 每个 metadata 单独 create_all；dialect 用 MySQL，保证字段类型与线上一致
                await conn.run_sync(meta.create_all)
        print("[2/4] 数据表已就绪（user / news / news_category / favorite / history）")
    finally:
        await engine.dispose()


async def seed() -> None:
    """写入初始数据：新闻分类、示例新闻、管理员账号（幂等，已存在则跳过）"""
    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with SessionLocal() as db:
            # ---------- 新闻分类 ----------
            categories = ["头条", "社会", "国内", "国际", "科技"]
            for name in categories:
                exists = (await db.execute(select(NewsCategory).where(NewsCategory.name == name))).scalar_one_or_none()
                if not exists:
                    db.add(NewsCategory(name=name))
            await db.commit()
            print("[3/4] 新闻分类已就绪：" + "、".join(categories))

            # ---------- 示例新闻（每类一条，内容从简，符合 String(255) 列宽）----------
            samples = [
                ("科技", "首个国产AI大模型开源", "国产大模型正式开源，推动行业应用。", "详见正文。"),
                ("国际", "全球气候峰会达成新共识", "各国就减排目标达成阶段性共识。", "详见正文。"),
            ]
            cat_map = {}
            for name in categories:
                c = (await db.execute(select(NewsCategory).where(NewsCategory.name == name))).scalar_one()
                cat_map[name] = c.id
            for cat_name, title, desc, content in samples:
                cid = cat_map[cat_name]
                exists = (await db.execute(select(News).where(News.title == title))).scalar_one_or_none()
                if not exists:
                    db.add(News(
                        title=title, description=desc, content=content, image="",
                        author="AI新闻头条", category_id=cid, views=0,
                    ))
            await db.commit()
            print("[3/4] 示例新闻已写入")

            # ---------- 管理员 / 示例账号：admin / 123456 ----------
            admin = (await db.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
            if not admin:
                db.add(User(username="admin", password=hash_password("123456")))
                await db.commit()
                print("[4/4] 管理员已创建：admin / 123456")
            else:
                # 保证示例密码可用（可选，注释掉即可保留原密码）
                # await db.execute(update(User).where(User.id == admin.id).values(password=hash_password("123456")))
                # await db.commit()
                print("[4/4] 管理员已存在，跳过")
    finally:
        await engine.dispose()


async def main() -> None:
    print("开始初始化数据库 ...")
    await ensure_database_exists()  # 1. 确保库存在
    await create_tables()  # 2. 建表
    await seed()  # 3. 初始数据
    print("\n初始化完成。后端可直接启动：  .\\venv\\Scripts\\python run.py")


if __name__ == "__main__":
    asyncio.run(main())
