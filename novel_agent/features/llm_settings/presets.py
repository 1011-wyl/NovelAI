from __future__ import annotations

from novel_agent.features.llm_settings.models import LLMProvider

PROVIDER_LABELS = {
    LLMProvider.DEEPSEEK: "DeepSeek",
    LLMProvider.DASHSCOPE: "阿里云百炼 DashScope",
    LLMProvider.OPENAI: "OpenAI",
    LLMProvider.OPENAI_COMPATIBLE: "自定义 OpenAI 兼容接口",
}

PROVIDER_PRESETS: dict[LLMProvider, dict[str, str]] = {
    LLMProvider.DEEPSEEK: {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    LLMProvider.DASHSCOPE: {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    LLMProvider.OPENAI: {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    LLMProvider.OPENAI_COMPATIBLE: {
        "base_url": "",
        "model": "",
    },
}

ADAPTER_NAMES = {
    LLMProvider.DEEPSEEK: "deepseek",
    LLMProvider.DASHSCOPE: "dashscope",
    LLMProvider.OPENAI: "openai",
    LLMProvider.OPENAI_COMPATIBLE: "openai-compatible",
}


def presets_payload() -> list[dict[str, str]]:
    return [
        {
            "provider": provider.value,
            "provider_label": PROVIDER_LABELS[provider],
            "base_url": values["base_url"],
            "model": values["model"],
        }
        for provider, values in PROVIDER_PRESETS.items()
    ]
