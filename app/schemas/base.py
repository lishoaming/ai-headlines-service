from typing import Any, Generic, Optional, TypeVar  # 导入泛型相关类型工具

from pydantic import BaseModel, ConfigDict  # 导入 Pydantic 基类与配置字典
from pydantic.alias_generators import to_camel  # 导入字段名转驼峰的别名生成器
from typing import Annotated
from datetime import datetime
from pydantic import PlainSerializer  # 导入原始序列化器，用于自定义日期时间格式化

T = TypeVar("T", default=Any)  # 定义泛型类型变量，未指定时不限制 data 类型


class CamelModel(BaseModel):  # 定义业务模型基类：字段用 snake_case，序列化自动转 camelCase
    """业务模型基类：Python 侧保持 snake_case，JSON 序列化自动转 camelCase"""
    model_config = ConfigDict(  # 配置模型行为
        alias_generator=to_camel,  # 序列化时字段名自动转为 camelCase
        populate_by_name=True,  # 反序列化时同时接受原字段名与别名
    )

DateTimeStr = Annotated[
                  datetime,
                  PlainSerializer(lambda v: v.strftime("%Y-%m-%d %H:%M:%S"), return_type=str),
              ]


class ResponseModel(CamelModel, Generic[T]):  # 定义统一响应结构：继承驼峰序列化，data 类型用泛型指定
    """统一响应结构（驼峰序列化 + code/message/data）"""
    code: int = 200  # 业务状态码，默认 200
    message: str = "success"  # 提示信息，默认 success
    data: Optional[T] = None  # 业务数据，可为空