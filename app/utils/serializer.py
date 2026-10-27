"""JSON 序列化/反序列化工具（与缓存解耦，可复用于导出、日志等场景）

使用约定（避免误用）：
1. 本模块只负责“对象 <-> JSON 字符串”，不处理 key 前缀、TTL、Redis；
   写缓存请直接用 cache.set_json / cache.get_or_set，不要先 dumps 再交给缓存（会二次编码）；
2. Pydantic 模型按别名（camelCase）导出；读回后需要用 response_model 或 model_validate 还原；
3. datetime/Decimal 等非标准类型用 str 兜底，读回是字符串而不是原类型；
4. loads 只用于本模块 dumps 产生的数据；非法 JSON 会抛 ValueError。
"""

import json  # 导入 json，提供底层的序列化/反序列化能力
from typing import Any  # 导入类型标注

from pydantic import BaseModel  # 导入 Pydantic 基类，用于把出参模型转成可 JSON 化的结构


def to_jsonable(value: Any) -> Any:  # 把 Pydantic 模型等对象递归转成可 JSON 序列化的结构
    """把 Pydantic 模型/列表/字典转成只含基础类型的结构（模型按别名 camelCase 导出）"""
    if isinstance(value, BaseModel):  # Pydantic 模型：按别名（camelCase）导出
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, (list, tuple)):  # 列表/元组：递归处理每个元素
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):  # 字典：递归处理每个值
        return {k: to_jsonable(v) for k, v in value.items()}
    return value  # 其它基础类型原样返回


def dumps(value: Any) -> str:  # 序列化成 JSON 字符串
    """序列化为 JSON 字符串：保留中文，非标准类型（datetime/Decimal 等）用 str 兜底"""
    return json.dumps(to_jsonable(value), ensure_ascii=False, default=str)


def loads(raw: str) -> Any:  # 从 JSON 字符串反序列化
    """反序列化 JSON 字符串；非法 JSON 会抛 ValueError（json.JSONDecodeError 是其子类）"""
    return json.loads(raw)
