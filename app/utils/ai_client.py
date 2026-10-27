"""AI 大模型调用封装（OpenAI 兼容协议，默认阿里云百炼 DashScope 兼容模式）

职责：
1. 统一拼接请求体（系统提示词、上下文截断、是否流式）；
2. 统一处理上游异常，转成项目内的 BusinessException，避免把上游细节暴露给前端；
3. 同时提供非流式（一次返回完整回答）与流式（逐段 yield 内容）两种调用方式。

注意：API Key 只保存在服务端配置中，前端不再直接访问大模型。
"""

import json  # 解析上游返回的 JSON
import logging  # 记录上游异常，便于排查
from typing import AsyncIterator, Dict, List

import httpx  # 异步 HTTP 客户端

from app.config import settings  # 导入全局配置
from app.utils.exceptions import BusinessException  # 导入业务异常（由全局处理器转成统一响应）

logger = logging.getLogger(__name__)  # 创建本模块的日志记录器

_CHAT_PATH = "/chat/completions"  # OpenAI 兼容协议的对话补全路径


def _ensure_configured() -> None:  # 校验 AI 配置是否完整
    if not settings.AI_API_KEY:  # 未配置密钥时直接拒绝，避免发出必然失败的请求
        raise BusinessException("AI 服务未配置，请联系管理员", code=503)


def _build_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:  # 组装最终发送给模型的消息列表
    """在对话历史前拼接系统提示词，并只保留最近 N 条历史以控制上下文长度"""
    history = messages[-settings.AI_MAX_HISTORY_MESSAGES:] if settings.AI_MAX_HISTORY_MESSAGES > 0 else messages  # 截断历史
    system_prompt = settings.AI_SYSTEM_PROMPT.strip()  # 系统提示词
    if system_prompt:  # 配置了系统提示词才拼接，避免空内容
        return [{"role": "system", "content": system_prompt}, *history]
    return list(history)


def _build_payload(messages: List[Dict[str, str]], stream: bool) -> Dict:  # 构造请求体
    return {
        "model": settings.AI_MODEL,  # 模型名称
        "messages": _build_messages(messages),  # 系统提示 + 历史对话
        "stream": stream,  # 是否流式返回
    }


def _handle_status_error(status_code: int, body: str) -> None:  # 把上游 HTTP 错误转成业务异常
    logger.warning("AI 上游返回异常 status=%s body=%s", status_code, body[:500])  # 只截取前 500 字符，避免日志过大
    if status_code in (401, 403):  # 密钥无效或无权限
        raise BusinessException("AI 服务鉴权失败，请联系管理员", code=502)
    if status_code == 429:  # 触发限流
        raise BusinessException("AI 服务繁忙，请稍后重试", code=429)
    raise BusinessException("AI 服务暂时不可用，请稍后重试", code=502)


def _extract_content(data: Dict) -> str:  # 从非流式响应中取出回答文本
    choices = data.get("choices") or []  # 兼容 OpenAI 结构
    if not choices:
        return ""
    return (choices[0].get("message") or {}).get("content") or ""


async def chat(messages: List[Dict[str, str]]) -> str:  # 非流式调用：一次性拿到完整回答
    """非流式调用，返回模型完整回答文本"""
    _ensure_configured()  # 配置校验
    url = f"{settings.AI_BASE_URL}{_CHAT_PATH}"  # 完整上游地址
    payload = _build_payload(messages, stream=False)  # 构造非流式请求体
    headers = {"Authorization": f"Bearer {settings.AI_API_KEY}", "Content-Type": "application/json"}  # 鉴权头

    try:
        async with httpx.AsyncClient(timeout=settings.AI_TIMEOUT_SECONDS) as client:  # 使用独立超时
            response = await client.post(url, json=payload, headers=headers)  # 发起请求
    except httpx.TimeoutException:  # 超时
        logger.warning("AI 请求超时 model=%s", settings.AI_MODEL)
        raise BusinessException("AI 响应超时，请稍后重试", code=504)
    except httpx.HTTPError as exc:  # 网络层错误（DNS、连接失败等）
        logger.warning("AI 请求失败: %s", exc)
        raise BusinessException("AI 服务连接失败，请稍后重试", code=502)

    if response.status_code != 200:  # 上游返回非 200
        _handle_status_error(response.status_code, response.text)

    try:
        data = response.json()  # 解析响应
    except json.JSONDecodeError:  # 上游返回非 JSON（如网关错误页）
        logger.warning("AI 返回非 JSON 内容: %s", response.text[:500])
        raise BusinessException("AI 服务返回异常，请稍后重试", code=502)

    content = _extract_content(data)  # 取出回答文本
    if not content:  # 上游未给出内容
        raise BusinessException("AI 未能生成回复，请换个问法重试", code=502)
    return content


def _parse_sse_line(line: str) -> str:  # 解析一行 SSE 数据，返回增量文本（无内容时返回空串）
    line = line.strip()  # 去掉首尾空白（含 \r）
    if not line.startswith("data:"):  # 忽略 event/id/comment 等其它字段
        return ""
    data = line[len("data:"):].strip()  # 取出 data 内容
    if not data or data == "[DONE]":  # 结束标记
        return ""
    try:
        chunk = json.loads(data)  # 解析增量 JSON
    except json.JSONDecodeError:  # 异常行直接跳过，不影响整体流
        logger.debug("忽略无法解析的 SSE 数据: %s", data[:200])
        return ""
    choices = chunk.get("choices") or []  # 兼容 OpenAI 结构
    if not choices:
        return ""
    return (choices[0].get("delta") or {}).get("content") or ""


async def chat_stream(messages: List[Dict[str, str]]) -> AsyncIterator[str]:  # 流式调用：逐段产出文本
    """流式调用，逐段 yield 模型输出文本；上游异常时抛 BusinessException"""
    _ensure_configured()  # 配置校验
    url = f"{settings.AI_BASE_URL}{_CHAT_PATH}"  # 完整上游地址
    payload = _build_payload(messages, stream=True)  # 构造流式请求体
    headers = {"Authorization": f"Bearer {settings.AI_API_KEY}", "Content-Type": "application/json"}  # 鉴权头

    try:
        async with httpx.AsyncClient(timeout=settings.AI_TIMEOUT_SECONDS) as client:  # 使用独立超时
            async with client.stream("POST", url, json=payload, headers=headers) as response:  # 流式读取响应
                if response.status_code != 200:  # 上游返回错误：先读完错误体再抛异常
                    body = (await response.aread()).decode(errors="ignore")
                    _handle_status_error(response.status_code, body)
                async for line in response.aiter_lines():  # 逐行读取 SSE
                    content = _parse_sse_line(line)  # 解析增量文本
                    if content:  # 有内容才产出
                        yield content
    except httpx.TimeoutException:  # 超时（含读取超时）
        logger.warning("AI 流式请求超时 model=%s", settings.AI_MODEL)
        raise BusinessException("AI 响应超时，请稍后重试", code=504)
    except httpx.HTTPError as exc:  # 网络层错误
        logger.warning("AI 流式请求失败: %s", exc)
        raise BusinessException("AI 服务连接失败，请稍后重试", code=502)
