# 配置历史记录请求体
from app.schemas.base import CamelModel, ConfigDict, DateTimeStr
from pydantic import  Field
from typing import List


class HistoryAddIn(CamelModel):
    news_id: int = Field(description="新闻ID", alias='newsId')


# 文章详细内容（历史记录列表项）
class HistoryDetailOut(CamelModel):
    """文章详细内容出参：字段用 snake_case，序列化自动转 camelCase"""
    model_config = ConfigDict(from_attributes=True)  # 允许直接从 News ORM 对象转换
    id: int
    title: str
    description: str | None = None
    author: str | None = None
    publish_time: DateTimeStr | None = Field(default=None, alias="publishTime")  # 发布时间，来自 News.publish_time
    category_id: int | None = Field(default=None, alias="categoryId")  # 分类id，来自 Category.id
    views: int | None = None
    view_time: DateTimeStr | None = Field(default=None, alias="viewTime")  # 查看时间，来自 History.view_time
    content: str
    image: str | None = None



# 返回历史记录列表
class HistoryListOut(CamelModel):
    """历史记录列表出参"""
    list: List[HistoryDetailOut] = Field(default_factory=list)
    total: int = 0
    has_more: bool = Field(default=False, alias="hasMore")