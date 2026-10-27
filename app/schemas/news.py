
from typing import List

from fastapi import Query

from pydantic import ConfigDict, Field

from app.schemas.base import CamelModel, DateTimeStr


# ==================== 分类 ====================
class CategoryOut(CamelModel):
    """新闻分类出参"""
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


# ==================== 新闻条目基础 ====================
class _NewsItemBase(CamelModel):
    """新闻条目公共字段"""
    id: int
    title: str
    description: str
    image: str
    author: str
    category_id: int
    views: int
    publish_time: DateTimeStr

# ==================== 新闻列表 ====================
class NewsListIn(CamelModel):
    """新闻列表入参"""
    category_id: int = Query(..., ge=1, description="新闻分类ID")
    page: int = Query(1, ge=1, description="页码")
    page_size: int = Query(10, ge=1, le=100, description="每页数量")


class NewsItemOut(_NewsItemBase):
    """新闻列表项出参"""
    model_config = ConfigDict(from_attributes=True)


class NewsListOut(CamelModel):
    """新闻列表出参"""
    list: List[NewsItemOut] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10
    has_more: bool = False


# ==================== 新闻详情 ====================
class NewsDetailIn(CamelModel):
    """新闻详情入参"""
    id: int = Query(..., ge=1, description="新闻ID")


class NewsDetailOut(_NewsItemBase):
    """新闻详情出参"""
    content: str
    related_news: List[NewsItemOut] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)