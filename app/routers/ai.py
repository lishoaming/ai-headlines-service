"""AI 问答接口

- POST /api/ai/chat        非流式：一次性返回完整回答
- POST /api/ai/chat/stream 流式（SSE）：逐段推送回答，格式兼容 OpenAI 的 delta 结构
两个接口都需要登录，避免匿名用户无限制调用大模型（产生费用）。
"""

import json  # 构造 SSE 数据行
import logging  # 记录流式中断等情况

from fastapi import APIRouter, Depends  # 导入路由与依赖注入
from fastapi.responses import StreamingResponse  # 导入流式响应

from app.config import settings  # 导入全局配置（模型名等）
from app.dependencies import get_current_user  # 导入当前登录用户依赖
from app.models.user import User  # 导入用户模型
from app.schemas.ai import AIChatIn, AIChatOut  # 导入 AI 问答入参/出参模型
from app.schemas.base import ResponseModel  # 导入统一响应模型
from app.utils import ai_client, prompt_guard  # 导入大模型调用封装与提示词注入防护
from app.utils.exceptions import BusinessException  # 导入业务异常

logger = logging.getLogger(__name__)  # 创建本模块的日志记录器

ai_router = APIRouter(prefix="/api/ai", tags=["AI问答"])  # 创建 AI 路由，统一前缀 /api/ai


def _to_messages(body: AIChatIn) -> list[dict]:  # 把入参模型转成大模型需要的消息列表
    return [{"role": item.role, "content": item.content} for item in body.messages]


def _ensure_no_injection(messages: list[dict]) -> None:  # 提示词注入检查
    """拦截越权指令、身份改写、系统提示词/密钥套取等常见注入手法"""
    reason = prompt_guard.inspect_messages(messages)  # 命中返回原因描述
    if reason:
        logger.warning("拦截疑似提示词注入 reason=%s messages=%s", reason, messages[-1]["content"][:100])
        raise BusinessException(
            f"抱歉，这条消息涉及「{reason}」，我无法处理。可以换个方式提问，比如让我解读一条新闻。",
            code=400,
        )


@ai_router.post("/chat", response_model=ResponseModel[AIChatOut])  # 非流式问答接口
async def ai_chat(body: AIChatIn, user: User = Depends(get_current_user)):  # 定义异步处理函数
    """非流式问答：等待模型生成完整回答后一次性返回"""
    messages = _to_messages(body)  # 入参转消息列表
    _ensure_no_injection(messages)  # 注入检查（命中直接返回 400）
    content = await ai_client.chat(messages)  # 调用大模型
    return ResponseModel(message="回答成功", data=AIChatOut(content=content, model=settings.AI_MODEL))  # 返回统一响应


@ai_router.post(  # 流式问答接口（SSE）
    "/chat/stream",
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},  # 让文档标注为 SSE 而非 JSON
)
async def ai_chat_stream(body: AIChatIn, user: User = Depends(get_current_user)):  # 定义异步处理函数
    """流式问答：逐段返回模型输出，格式为 OpenAI 兼容的 SSE delta"""
    messages = _to_messages(body)  # 先在进入流之前完成入参转换，校验错误能正常返回 422
    _ensure_no_injection(messages)  # 注入检查放在开流之前，命中可正常返回 400

    async def event_generator():  # 定义 SSE 生成器
        try:
            async for chunk in ai_client.chat_stream(messages):  # 逐段读取模型输出
                payload = {"choices": [{"delta": {"content": chunk}}]}  # 兼容前端现有的 delta 解析逻辑
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"  # 推送给前端
        except BusinessException as exc:  # 上游/配置异常：流已开始，只能通过事件告知前端
            logger.warning("AI 流式问答中断 user_id=%s: %s", user.id, exc.message)
            payload = {"error": {"message": exc.message}}  # 错误事件
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception as exc:  # 兜底，避免流异常中断导致前端一直等待
            logger.error("AI 流式问答异常 user_id=%s: %s", user.id, exc, exc_info=True)
            payload = {"error": {"message": "AI 服务异常，请稍后重试"}}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"  # 结束标记，前端据此收尾（客户端主动断开时不会走到这里）

    return StreamingResponse(  # 返回流式响应
        event_generator(),
        media_type="text/event-stream",  # SSE 类型
        headers={
            "Cache-Control": "no-cache",  # 禁止缓存
            "X-Accel-Buffering": "no",  # 关闭 Nginx 缓冲，保证逐段下发
        },
    )
