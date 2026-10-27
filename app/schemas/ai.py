"""AI 问答相关入参/出参模型"""

from typing import List, Literal  # 导入列表与字面量类型

from pydantic import Field, field_validator  # 导入字段约束与校验器

from app.schemas.base import CamelModel  # 导入业务模型基类（自动驼峰序列化）


class ChatMessageIn(CamelModel):  # 单条对话消息
    """单条对话消息：角色只允许 user/assistant，system 由服务端统一注入，不接受客户端传入"""
    role: Literal["user", "assistant"] = Field(..., description="消息角色：user/assistant")
    content: str = Field(..., min_length=1, max_length=4000, description="消息内容")

    @field_validator("content")  # 去除首尾空白并拒绝纯空白内容
    @classmethod
    def _strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("消息内容不能为空")
        return value


class AIChatIn(CamelModel):  # AI 问答入参
    """AI 问答入参：完整对话历史，最后一条必须是用户提问"""
    messages: List[ChatMessageIn] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="对话历史（含本轮提问），最后一条必须是 user",
    )

    @field_validator("messages")  # 校验对话历史上限与最后一条角色
    @classmethod
    def _check_messages(cls, messages: List[ChatMessageIn]) -> List[ChatMessageIn]:
        if not messages:
            raise ValueError("对话历史不能为空")
        if messages[-1].role != "user":
            raise ValueError("最后一条消息必须是用户提问")
        return messages


class AIChatOut(CamelModel):  # AI 问答出参（非流式）
    """AI 问答出参（非流式）"""
    content: str  # 模型回答内容
    model: str  # 实际使用的模型名称
