"""LLM integration stand-ins and providers.

Import DeepSeekLLMGateway from novel_agent.integrations.llm.deepseek
(or via adapters_remote) to avoid package-init cycles with http_transport.
"""

from novel_agent.integrations.llm.disabled import DisabledRemoteGateway
from novel_agent.integrations.llm.offline import OfflineLLMGateway

__all__ = ["DisabledRemoteGateway", "OfflineLLMGateway"]
