from __future__ import annotations

from http import HTTPStatus


class LLMSettingsError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: HTTPStatus = HTTPStatus.BAD_REQUEST,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


SECRET_STORE_HINT = (
    "本机安全凭据存储不可用。请先安装 Python 包 keyring（python -m pip install keyring），"
    "并确认 Windows 凭据管理器可用，然后重启服务。"
)


USER_MESSAGES = {
    "LLM_NOT_CONFIGURED": "尚未配置大模型服务",
    "INVALID_API_KEY": "API Key 无效或已失效",
    "MODEL_NOT_FOUND": "当前账号无法使用该模型，请检查模型 ID",
    "INVALID_BASE_URL": "API 地址格式或接口路径不正确",
    "NETWORK_UNREACHABLE": "无法连接服务，请检查网络和 API 地址",
    "REQUEST_TIMEOUT": "连接超时，可稍后重试或调整超时时间",
    "RATE_LIMITED": "请求过于频繁或额度受限",
    "INSUFFICIENT_QUOTA": "账户额度不足",
    "PROVIDER_ERROR": "模型服务暂时异常",
    "SECRET_STORE_UNAVAILABLE": SECRET_STORE_HINT,
    "CONFIG_VERSION_CONFLICT": "配置已在其他页面更新，请刷新后重试",
    "VALIDATION_ERROR": "配置内容不完整或格式不正确",
}
