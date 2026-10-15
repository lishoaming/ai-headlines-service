from datetime import datetime
from typing import Generic, List, TypeVar
from fastapi import Query
from pydantic import BaseModel

# 泛型占位符，用于统一响应结构中的 data
T = TypeVar("T")


# 统一响应结构：{code, message, data}
class ResponseModel(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: T | None = None


# 获取新闻分类列表返回参数
class get_categories_schema_out(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime


# 获取新闻列表请求参数
class get_list_schema_in(BaseModel):
    category_id: int = Query(..., description="新闻分类id", alias="categoryId")
    page: int = Query(1, description="页码", alias="page")
    page_size: int = Query(10, description="每页数量", alias="pageSize")


# 新闻列表项出参
class news_item_schema_out(BaseModel):
    id: int
    title: str
    description: str
    image: str
    author: str
    category_id: int
    views: int
    publish_time: datetime


# 新闻列表接口出参
class get_list_schema_out(BaseModel):
    list: List[news_item_schema_out] = []
    total: int = 0
    page: int = Query(1, description="页码", alias="page")
    page_size: int = Query(10, description="每页数量", alias="pageSize")


# 新闻详情接口入参
class get_detail_schema_in(BaseModel):
    id: int


# 新闻详情接口出参
class get_detail_schema_out(BaseModel):
    id: int
    title: str
    description: str
    content: str
    image: str
    author: str
    category_id: int
    views: int
    publish_time: datetime
