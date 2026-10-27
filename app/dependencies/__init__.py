from app.dependencies.auth import get_current_user, security  # 重新导出鉴权依赖，保持 from app.dependencies import ... 的用法不变

__all__ = ["get_current_user", "security"]  # 对外暴露的名称，便于 from ... import * 时控制范围