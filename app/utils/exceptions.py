class BusinessException(Exception):  # 定义业务异常基类
    """业务异常：业务规则校验失败时抛出，由全局异常处理器转成统一响应"""

    def __init__(self, message: str, code: int = 400):  # 初始化函数，接收提示信息与业务码
        self.code = code  # 业务码，同时作为 HTTP 状态码
        self.message = message  # 提示信息
        super().__init__(message)  # 调用父类初始化，保存错误信息