from typing import Annotated, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.news import get_news_categories, get_news_list, get_news_detail
from app.config.db import get_db

from app.schemas.news import (
    ResponseModel,
    get_categories_schema_out,
    get_list_schema_in,
    get_list_schema_out,
    get_detail_schema_in,
    get_detail_schema_out,
)



news_router = APIRouter(prefix="/api/news", tags=["新闻"])

# 获取新闻分类列表
@news_router.get("/categories", response_model=ResponseModel[List[get_categories_schema_out]])
async def get_categories(db: AsyncSession = Depends(get_db)):
    # 从数据库中获取新闻分类列表
    categories = await get_news_categories(db)
    return {
        "code": 200,
        "message": "获取新闻分类列表成功",
        "data": categories,
    } 
    
# 根据分类id 获取新闻列表
@news_router.get("/list", response_model=ResponseModel[get_list_schema_out])
async def list_news(params: Annotated[get_list_schema_in, Query()], db: AsyncSession = Depends(get_db)):
    # 从数据库中获取新闻列表
    obj = await get_news_list(db, params.category_id, params.page, params.page_size)
    return {
        "code": 200,
        "message": "获取新闻列表成功",
        "data": obj,
    }

# 根据id 查询新闻详情
@news_router.get("/detail", response_model=ResponseModel[get_detail_schema_out])
async def get_detail(params: Annotated[get_detail_schema_in, Query()], db: AsyncSession = Depends(get_db)):
    # 从数据库中获取新闻详情
    detail = await get_news_detail(db, params.id)
    return {
        "code": 200,
        "message": "获取新闻详情成功",
        "data": detail,
    }
