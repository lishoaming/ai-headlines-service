"""提示词注入防护（服务端）

作用：在把用户消息发给大模型之前做一次检查，拦截常见的"越狱"手法，例如：
- 让模型忽略/遗忘系统规则；
- 让模型改变身份、扮演其它角色（"你现在是……"）；
- 套取系统提示词、密钥、序列号、接口地址等内部信息；
- 用 "system:"、"<|im_start|>" 之类的角色标记伪造对话结构。

注意：正则只能挡住常见表达，真正兜底的是系统提示词里的规则 + 服务端不给外部任何 system 角色入口。
"""

import re
import unicodedata  # 用于 NFKC 归一化，防止全角/兼容字符绕过

# 零宽字符：常被用来把敏感词拆开（如 "忽\u200b略"）
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)
# 不可见控制字符
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# 各条规则：(正则, 命中后的原因描述)
_RULES: list[tuple[re.Pattern, str]] = [
    # ---------- 1. 越权指令：要求忽略既有规则 ----------
    (
        re.compile(
            r"(忽略|无视|忘记|忘掉|抛弃|跳过)(掉)?(之前|以上|前面|先前|上述|所有|全部|原有|既有)的?(所有|全部)?"
            r"(指令|指示|规则|设定|约束|提示词|要求)"
        ),
        "越权指令",
    ),
    (
        re.compile(
            r"(ignore|disregard|forget)\s+(all\s+)?(the\s+)?(previous|above|prior|earlier)\s+"
            r"(instructions?|rules?|prompts?|constraints?)",
            re.IGNORECASE,
        ),
        "越权指令",
    ),
    # ---------- 2. 身份改写：让模型扮演别的角色 ----------
    (
        re.compile(r"(从现在开始|从现在起|接下来|以后)[，,]?\s*(你|您)(是|要|必须|只能|将)"),
        "身份改写",
    ),
    (
        re.compile(r"你(现在)?(就是|扮演|假装|充当)(一个|一位|一名|一只)?"),
        "身份改写",
    ),
    (
        re.compile(r"你的(新)?身份(是|改为|变成)|(切换|更改)你的?(身份|角色|设定)"),
        "身份改写",
    ),
    (
        re.compile(r"(act|pretend)\s+as\s+(a|an|the)\b|you\s+are\s+now\s+", re.IGNORECASE),
        "身份改写",
    ),
    # ---------- 3. 套取系统提示词 / 内部设定 ----------
    (
        re.compile(
            r"(输出|显示|打印|复述|重复|背诵|背出|告诉我|列出|透露|泄露|展示|贴出).{0,12}"
            r"(系统提示词|系统提示|系统设定|系统指令|初始指令|隐藏规则|prompt|你的设定|你的规则)"
        ),
        "提示词窃取",
    ),
    (
        re.compile(
            r"(show|print|repeat|reveal|tell\s+me|list).{0,12}"
            r"(system\s+prompt|your\s+(instructions|rules|prompt|settings))",
            re.IGNORECASE,
        ),
        "提示词窃取",
    ),
    # ---------- 4. 套取密钥 / 序列号 / 内部配置 ----------
    (
        re.compile(
            r"(输出|显示|打印|告诉我|列出|透露|泄露|展示|提供|发我|背).{0,12}"
            r"(api[\s_-]?key|access[\s_-]?token|密钥|私钥|序列号|license|环境变量|\.env|"
            r"数据库密码|服务器地址|接口地址|内部配置|系统配置)",
            re.IGNORECASE,
        ),
        "内部信息获取",
    ),
    (
        # 语序反过来："把 API KEY 和序列号发我" / "序列号是多少"
        re.compile(
            r"(api[\s_-]?key|access[\s_-]?token|密钥|私钥|序列号|license|环境变量|\.env|"
            r"数据库密码|服务器地址|接口地址|内部配置|系统配置).{0,12}"
            r"(发我|给我|告诉我|输出|贴出|列出|打印|展示|提供|是多少|是多少？)",
            re.IGNORECASE,
        ),
        "内部信息获取",
    ),
    (
        re.compile(r"(api[\s_-]?key|secret\s*key)\s*[:=]", re.IGNORECASE),
        "内部信息获取",
    ),
    # ---------- 5. 越狱模式 ----------
    (
        re.compile(r"(开发者|调试|上帝|越狱|无限制|DAN)\s*模式|jailbreak|do\s+anything\s+now", re.IGNORECASE),
        "越权指令",
    ),
    # ---------- 6. 伪造对话角色标记 ----------
    (
        re.compile(r"(^|\n)\s*(system|assistant|developer)\s*[:：]", re.IGNORECASE),
        "角色伪造",
    ),
    (
        re.compile(r"<\|im_(start|end)\|>|\[/?INST\]|###\s*(system|instruction)", re.IGNORECASE),
        "角色伪造",
    ),
]


def normalize(text: str) -> str:
    """归一化文本：全角转半角、去零宽/控制字符、压缩空白，避免用字符变形绕过规则"""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.translate(_ZERO_WIDTH)
    text = _CONTROL_CHARS.sub("", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def inspect(text: str) -> str | None:
    """检查单条文本，命中返回原因描述，未命中返回 None"""
    normalized = normalize(text)
    if not normalized:
        return None
    for pattern, reason in _RULES:
        if pattern.search(normalized):
            return reason
    return None


def inspect_messages(messages: list[dict]) -> str | None:
    """检查对话历史中用户发出的消息，命中返回原因

    只检查 role=user 的消息：助手历史里可能正常引用"忽略之前的指令"之类的示例
    （例如用户问"什么是提示词注入"），一起检查会把正常追问也拦掉。
    """
    for message in messages:
        if message.get("role") != "user":
            continue
        reason = inspect(message.get("content", ""))
        if reason:
            return reason
    return None
