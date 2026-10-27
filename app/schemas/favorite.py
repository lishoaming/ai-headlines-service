from typing import List

from pydantic import ConfigDict, Field

from app.schemas.base import CamelModel, DateTimeStr


class FavoriteAddIn(CamelModel):
    """添加收藏入参"""
    news_id: int = Field(..., description='新闻id', alias='newsId')

class FavoriteRemoveIn(CamelModel):
    """删除收藏入参"""
    news_id: int = Field(..., description='新闻id', alias='newsId')



# 文章详细内容（收藏列表项）
class NewsDetailOut(CamelModel):
    """文章详细内容出参：字段用 snake_case，序列化自动转 camelCase"""
    model_config = ConfigDict(from_attributes=True)  # 允许直接从 News ORM 对象转换
    id: int
    title: str
    description: str | None = None
    author: str | None = None
    publish_time: DateTimeStr | None = None
    category_id: int | None = None
    views: int | None = None
    favorite_time: DateTimeStr | None = None  # 收藏时间，来自 Favorite.created_at
    content: str
    image: str | None = None
    collection_id: int | None = Field(default=None, alias="collectionId")  # 收藏id，来自 Favorite.id


# 返回收藏列表
class FavoriteListOut(CamelModel):
    """收藏列表出参"""
    list: List[NewsDetailOut] = Field(default_factory=list)
    total: int = 0
    has_more: bool = Field(default=False, alias="hasMore")