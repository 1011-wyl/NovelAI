# External Integrations / Provider Adapters 详细拆分实施文档

> 适用项目：NovelAI  
> 目标读者：负责实施的 Cursor / 开发人员  
> 文档性质：结构重构实施规范，不是功能需求文档  
> 建议前置条件：Analytics / Dashboard 拆分与回归测试已完成

## 1. 结论：下一个拆分模块

Analytics / Dashboard 完成后，建议下一步拆分 **External Integrations / Provider Adapters（外部能力适配器）**。

本模块负责把 NovelAI 对外部服务的依赖，从两个体量过大、职责混杂的文件中拆到稳定的端口层与独立的 Provider 实现中，包括：

- LLM 端口、离线实现、禁用实现与 DeepSeek 实现；
- 搜索端口、禁用实现与 Tavily 实现；
- Embedding 端口、禁用实现与 OpenAI-compatible 实现；
- 发布端口、Mock 实现与 Fanqie 安全边界实现；
- HTTP transport、响应解析、重试与 Provider 异常分类；
- Provider 工厂与 `bootstrap` 依赖装配；
- LLM 调用与 token usage telemetry 的公开注入接口；
- 旧导入路径的兼容 Facade。

选择该模块作为下一步的原因：

1. 它对应 `docs/MODULAR_CODEBASE_SPLIT_PLAN.md` 中的阶段 3；
2. 当前 `adapters.py` 与 `adapters_remote.py` 已同时承担端口、实现、HTTP、工厂和装配职责，边界最需要稳定；
3. 先固定 Ports，后续 Project、Workflow、Revision 等业务模块拆分时不会继续依赖具体 Provider；
4. DeepSeek、Research、Embedding 已有较完整测试，可支撑渐进迁移；
5. 相比直接拆 Workflow，本次主要是结构迁移，业务状态和数据模型风险更低。

---

## 2. 本次目标与非目标

### 2.1 目标

完成后应达到以下状态：

- 业务层只依赖 `novel_agent.ports`，不依赖具体 Provider；
- 每个 Provider 位于自己的模块，单文件职责清晰；
- 工厂集中选择实现，`bootstrap` 只负责装配，不探测或修改对象私有字段；
- Provider 错误具有稳定、可测试的公共异常契约；
- `novel_agent.adapters` 与 `novel_agent.adapters_remote` 继续兼容旧代码和旧测试；
- 原有 API 行为、默认 Provider、默认 URL、模型名、Prompt、重试行为和离线能力保持不变；
- 每一阶段均能独立运行测试并可单独回滚。

### 2.2 非目标

本次禁止顺带进行以下变更：

- 不重写 DeepSeek Prompt，不调整 structured output 的业务 schema；
- 不改变生成内容质量策略、温度、token 上限或模型选择规则；
- 不改变现有重试次数、退避策略、超时与错误映射；
- 不改变 Tavily 请求协议或搜索结果归一化格式；
- 不改变 Embedding 请求/响应格式与向量校验规则；
- 不实现真实番茄小说发布，不扩大 `FanqiePublisherAdapter` 的能力边界；
- 不新增 `httpx`、`requests` 或其他网络依赖；
- 不修改前端页面、HTTP API 路由、数据库结构或工作流状态；
- 不删除旧模块或旧导入路径；
- 不以“清理代码”为名进行与拆分无关的大规模重命名。

若 Cursor 在实施中发现现有缺陷，应先增加能够复现当前行为的测试，并单独记录为后续修复项；本次不得静默改变行为。

---

## 3. 当前代码审计

### 3.1 当前核心文件

| 文件 | 当前体量（约） | 当前职责 | 主要问题 |
|---|---:|---|---|
| `novel_agent/adapters.py` | 883 行 / 37 KB | Ports、离线/禁用实现、Mock Publisher、Provider 工厂 | 抽象与实现混放，业务层被迫依赖历史聚合模块 |
| `novel_agent/adapters_remote.py` | 1403 行 / 63 KB | Provider 异常、HTTP helper、DeepSeek、Tavily、Embedding、Fanqie | 多个外部系统共用单文件，测试和修改影响面过大 |
| `novel_agent/bootstrap.py` | 装配入口 | 创建 Provider、注册 telemetry | 通过 `_on_call`、`_on_usage` 私有字段进行运行时装配 |
| `novel_agent/config.py` | 配置入口 | Provider、key、base URL、model 等配置 | 配置本身合理，但工厂签名与 Settings 装配边界不统一 |

### 3.2 `adapters.py` 当前职责

需要迁移但必须保持兼容的公共对象：

- `APIConfigurationRequired`
- `LLMGateway`
- `SearchAdapter`
- `EmbeddingGateway`
- `PublisherAdapter`
- `DisabledSearchAdapter`
- `DisabledEmbeddingGateway`
- `MockPublisher`
- `DisabledRemoteGateway`
- `OfflineLLMGateway`
- `build_gateway`
- `build_search_adapter`
- `build_embedding_gateway`

### 3.3 `adapters_remote.py` 当前职责

需要按 Provider 拆分的对象：

- `LLMProviderError`
- `LLMAuthenticationError`
- `LLMRateLimitError`
- `LLMTimeoutError`
- `LLMResponseError`
- `_urllib_transport`
- `_compact_json`
- `_tail`
- `DeepSeekLLMGateway`
- `RemoteSearchAdapter`
- `TavilySearchAdapter`
- `OpenAICompatibleEmbeddingGateway`
- `FanqiePublisherAdapter`

### 3.4 当前关键耦合

1. `adapters_remote.py` 从 `adapters.py` 导入 `APIConfigurationRequired`；
2. `adapters.py` 的工厂在函数内部导入 `adapters_remote.py`，借此规避循环依赖；
3. `service.py`、`workflow.py`、`story_skills.py` 仍从 `novel_agent.adapters` 导入 Ports；
4. `api.py` 从 `adapters` 导入 `APIConfigurationRequired`，并从 `adapters_remote` 导入 Provider errors；
5. `bootstrap.py` 检查并修改 Gateway 的 `_on_call`、`_on_usage` 私有字段；
6. 多个测试直接继承 `OfflineLLMGateway`，或直接从旧模块导入具体实现。

这些耦合决定了本次必须采用“新模块成为真源、旧模块做兼容 re-export”的渐进方案，不能直接删除或整体改名。

---

## 4. 必须冻结的现有契约

拆分前先用测试冻结以下契约。若当前代码与本节描述存在细节差异，以当前代码和现有测试为准，先补 characterization test，再迁移。

### 4.1 Ports 契约

- 保持各抽象类/Protocol 的公开方法名、同步/异步方式、参数语义与返回类型不变；
- 业务层不得通过 `isinstance` 依赖具体 Provider；
- 禁用实现必须继续返回或抛出当前约定结果；
- `OfflineLLMGateway` 必须继续可被测试子类继承；
- `MockPublisher` 必须保持当前测试与离线运行行为。

### 4.2 Provider 异常契约

异常继承关系、构造参数、错误消息和 API 层映射不得因文件移动而变化：

```text
LLMProviderError
├── LLMAuthenticationError
├── LLMRateLimitError
├── LLMTimeoutError
└── LLMResponseError
```

`APIConfigurationRequired` 作为配置缺失类错误，应迁到稳定公共位置并由旧路径 re-export。不得将认证失败、限流、超时、响应损坏全部折叠为同一种异常。

### 4.3 配置契约

以下变量名称、读取优先级、空值行为以及现有默认值必须保持不变：

- `LLM_PROVIDER`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `SEARCH_PROVIDER`
- `SEARCH_API_KEY`
- `SEARCH_BASE_URL`
- `EMBEDDING_PROVIDER`
- `EMBEDDING_API_KEY`
- `EMBEDDING_BASE_URL`
- `EMBEDDING_MODEL`
- `PUBLISHER_PROVIDER`
- `PUBLISHER_API_KEY`
- `PUBLISHER_BASE_URL`

尤其要冻结 DeepSeek、Tavily、SiliconFlow/OpenAI-compatible Embedding 的默认 URL 和模型选择逻辑。不得因为“统一工厂”而要求用户新增配置。

### 4.4 网络与重试契约

- 继续使用现有 urllib transport；
- 保持请求 method、headers、body、编码和 timeout；
- 保持可重试状态码、最大尝试次数和退避策略；
- 保持 HTTP/URL/timeout 异常到 Provider 异常的映射；
- 保持 JSON 提取、修复和 schema example 的当前行为；
- 保持 usage 数据缺失时的兼容行为；
- 不在日志或异常中暴露 API key、Authorization header 或完整敏感 Prompt。

### 4.5 导入兼容契约

以下旧代码在整个拆分完成后仍必须可用：

```python
from novel_agent.adapters import (
    APIConfigurationRequired,
    DisabledSearchAdapter,
    OfflineLLMGateway,
    build_gateway,
)

from novel_agent.adapters_remote import (
    DeepSeekLLMGateway,
    TavilySearchAdapter,
    OpenAICompatibleEmbeddingGateway,
)
```

兼容层至少保留一个完整发布周期。在确认仓库内与外部调用方均完成迁移前，不得删除。

---

## 5. 目标目录结构

```text
novel_agent/
├── ports/
│   ├── __init__.py
│   ├── llm.py
│   ├── search.py
│   ├── embedding.py
│   ├── publishing.py
│   └── telemetry.py
├── integrations/
│   ├── __init__.py
│   ├── factories.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── errors.py
│   │   ├── http_transport.py
│   │   ├── disabled.py
│   │   ├── offline.py
│   │   └── deepseek.py
│   ├── search/
│   │   ├── __init__.py
│   │   ├── disabled.py
│   │   └── tavily.py
│   ├── embedding/
│   │   ├── __init__.py
│   │   ├── disabled.py
│   │   └── openai_compatible.py
│   └── publishing/
│       ├── __init__.py
│       ├── mock.py
│       └── fanqie.py
├── adapters.py                 # 兼容 Facade，不再包含真实实现
├── adapters_remote.py          # 兼容 Facade，不再包含真实实现
├── bootstrap.py
└── config.py
```

### 5.1 依赖方向

```text
service / workflow / story_skills / api
                    │
                    ▼
                  ports
                    ▲
                    │ implements
             integrations/*
                    ▲
                    │ selects and wires
          integrations/factories + bootstrap
```

强制规则：

- `ports` 不得导入 `integrations`、`bootstrap`、`service` 或 `workflow`；
- Provider 实现可以导入 Ports、领域模型、标准库和必要公共工具；
- Provider 之间不得互相导入具体实现；
- `factories.py` 可以导入各实现，但实现不得反向导入工厂；
- 兼容 Facade 只做 import/re-export 或薄 wrapper，不承载业务逻辑；
- 禁止再次使用函数内 import 来掩盖循环依赖，除非有明确注释和测试证明无法避免。

---

## 6. 逐对象迁移表

| 当前对象 | 当前文件 | 目标文件 | 迁移要求 |
|---|---|---|---|
| `LLMGateway` | `adapters.py` | `ports/llm.py` | 原签名不变，旧路径 re-export |
| `SearchAdapter` | `adapters.py` | `ports/search.py` | 原签名不变，旧路径 re-export |
| `EmbeddingGateway` | `adapters.py` | `ports/embedding.py` | 原签名不变，旧路径 re-export |
| `PublisherAdapter` | `adapters.py` | `ports/publishing.py` | 原签名不变，旧路径 re-export |
| telemetry callable/type | 隐含在实现中 | `ports/telemetry.py` | 定义公开 sink 类型，不依赖 Analytics 实现 |
| `APIConfigurationRequired` | `adapters.py` | `integrations/llm/errors.py` 或公共 errors 模块 | 所有旧路径 re-export，避免重复定义 |
| `DisabledRemoteGateway` | `adapters.py` | `integrations/llm/disabled.py` | 行为不变 |
| `OfflineLLMGateway` | `adapters.py` | `integrations/llm/offline.py` | 保持可继承性和测试替身能力 |
| Provider errors | `adapters_remote.py` | `integrations/llm/errors.py` | 类身份必须唯一，禁止兼容层重新声明类 |
| `_urllib_transport` | `adapters_remote.py` | `integrations/llm/http_transport.py` | 先保持函数签名和标准库实现 |
| `_compact_json`, `_tail` | `adapters_remote.py` | 优先放 `llm/http_transport.py` 或 DeepSeek 私有模块 | 只在确有复用时公开 |
| `DeepSeekLLMGateway` | `adapters_remote.py` | `integrations/llm/deepseek.py` | Prompt、重试、JSON 修复、telemetry 行为全部冻结 |
| `DisabledSearchAdapter` | `adapters.py` | `integrations/search/disabled.py` | 行为不变 |
| `RemoteSearchAdapter` | `adapters_remote.py` | `integrations/search/tavily.py` 或搜索私有 base | 不建立无实际价值的公共基类 |
| `TavilySearchAdapter` | `adapters_remote.py` | `integrations/search/tavily.py` | 请求和归一化行为不变 |
| `DisabledEmbeddingGateway` | `adapters.py` | `integrations/embedding/disabled.py` | 行为不变 |
| `OpenAICompatibleEmbeddingGateway` | `adapters_remote.py` | `integrations/embedding/openai_compatible.py` | 兼容 SiliconFlow 等既有配置 |
| `MockPublisher` | `adapters.py` | `integrations/publishing/mock.py` | 保持默认/测试行为 |
| `FanqiePublisherAdapter` | `adapters_remote.py` | `integrations/publishing/fanqie.py` | 只迁移，不补全真实发布 |
| `build_gateway` | `adapters.py` | `integrations/factories.py` | 新工厂 + 旧签名 wrapper |
| `build_search_adapter` | `adapters.py` | `integrations/factories.py` | 新工厂 + 旧签名 wrapper |
| `build_embedding_gateway` | `adapters.py` | `integrations/factories.py` | 新工厂 + 旧签名 wrapper |
| Publisher 构建逻辑 | `bootstrap.py` 或现有位置 | `integrations/factories.py` | 统一为 `build_publisher` |

迁移时必须“移动定义并 re-export”，不能复制类定义。否则旧路径与新路径导入的异常/类型不是同一个 Python class，会导致 `except`、`isinstance` 和 monkeypatch 失效。

---

## 7. Ports 设计

### 7.1 Ports 的职责

Ports 只描述 NovelAI 需要什么能力，不描述某家 Provider 如何提供能力。Ports 中允许出现：

- 抽象方法或 Protocol；
- 稳定的输入/输出类型；
- 与能力调用有关的最小公共类型；
- telemetry sink 的抽象类型。

Ports 中禁止出现：

- DeepSeek、Tavily、SiliconFlow、Fanqie 等品牌名；
- API key、base URL 默认值；
- urllib 请求代码；
- Provider 状态码；
- `Settings` 的读取逻辑；
- Analytics repository 或具体 recorder。

### 7.2 `ports/__init__.py`

只 re-export 稳定公共类型，示例：

```python
from .embedding import EmbeddingGateway
from .llm import LLMGateway
from .publishing import PublisherAdapter
from .search import SearchAdapter
from .telemetry import LLMCallSink, LLMUsageSink

__all__ = [
    "EmbeddingGateway",
    "LLMGateway",
    "PublisherAdapter",
    "SearchAdapter",
    "LLMCallSink",
    "LLMUsageSink",
]
```

最终名称应以现有 callback 签名为准；若一个结构化事件 sink 足以表达当前两个 callback，也应先做兼容适配，不要在本次强制重塑 Analytics 数据模型。

---

## 8. Telemetry 公开注入设计

### 8.1 当前问题

`bootstrap.py` 当前通过检查 `_on_call`、`_on_usage` 是否存在，再直接修改私有字段完成 telemetry 装配。这会导致：

- bootstrap 了解具体 Gateway 内部实现；
- 类型检查无法验证 callback 签名；
- 新 Gateway 很容易遗漏 telemetry；
- 测试只能依赖私有属性；
- 重构字段名会产生静默失效。

### 8.2 目标方案

优先使用构造参数注入，并保留当前 callback 的调用时机与 payload：

```python
gateway = DeepSeekLLMGateway(
    ...,
    on_call=telemetry.record_call,
    on_usage=telemetry.record_usage,
)
```

要求：

- 构造参数默认为 `None`，不提供时行为与当前一致；
- Provider 内部保存形式可以是私有字段，但 bootstrap 不再写私有字段；
- 工厂显式接收 telemetry sink/callback，并传给支持 telemetry 的 Gateway；
- 离线/禁用实现不需要伪造 usage；
- callback 自身失败时沿用当前处理策略，不能让拆分改变主业务成功/失败语义；
- 测试验证 callback 次数、时机和数据，不直接断言私有字段。

若现有 `DeepSeekLLMGateway` 的 dataclass 初始化兼容性要求不能立即增加公开参数，可先增加公开方法：

```python
gateway.set_telemetry_handlers(on_call=..., on_usage=...)
```

但构造注入仍是最终优先方案。不要同时长期保留三套注入方式。

### 8.3 与 Analytics 模块的边界

- `ports/telemetry.py` 定义回调/Protocol；
- Analytics 模块提供符合该 Protocol 的 recorder；
- `bootstrap.py` 将两者连接；
- Provider 不得导入 Analytics repository、数据库或 Dashboard service。

---

## 9. Factory 与 bootstrap 设计

### 9.1 新工厂

建议由 `integrations/factories.py` 提供统一的 Settings 驱动入口：

```python
def build_llm_gateway(settings, telemetry_sink=None) -> LLMGateway: ...
def build_search_adapter(settings) -> SearchAdapter: ...
def build_embedding_gateway(settings) -> EmbeddingGateway: ...
def build_publisher(settings) -> PublisherAdapter: ...
```

具体类型注解应使用项目当前 `Settings` 类型及 telemetry 实际类型。工厂负责：

- 读取已经构造好的 Settings；
- 规范化 Provider 名称；
- 校验必需配置；
- 应用当前默认 URL/model；
- 选择并实例化具体实现；
- 注入 transport/telemetry 等依赖。

工厂不负责：

- 读取 HTTP request；
- 写数据库；
- 创建 Analytics schema；
- 执行业务 Workflow；
- 修改已创建对象的私有字段。

### 9.2 旧工厂兼容

`novel_agent.adapters` 中保留现有：

- `build_gateway(...)`
- `build_search_adapter(...)`
- `build_embedding_gateway(...)`

它们应保持原签名，内部仅把参数转换为新工厂所需形式，或调用兼容的低层 builder。不要为了追求统一而一次性修改所有外部调用方。

### 9.3 bootstrap 最终职责

`bootstrap.py` 最终只执行以下动作：

1. 获取 Settings；
2. 创建 telemetry recorder；
3. 调用各新工厂；
4. 将 Ports 注入 service/workflow/API context；
5. 返回应用依赖容器。

bootstrap 中不得出现：

- Provider URL 拼接；
- Provider 名称分支；
- 私有字段探测/赋值；
- HTTP transport 细节；
- DeepSeek/Tavily 响应解析。

---

## 10. 兼容 Facade 设计

### 10.1 `novel_agent/adapters.py`

最终仅保留：

- 从 `ports` re-export 的抽象；
- 从 `integrations` re-export 的离线/禁用/Mock 实现；
- `APIConfigurationRequired` re-export；
- 保持旧签名的工厂 wrapper；
- 明确的 `__all__`。

### 10.2 `novel_agent/adapters_remote.py`

最终仅保留：

- Provider errors re-export；
- DeepSeek、Tavily、OpenAI-compatible Embedding、Fanqie 实现 re-export；
- 若测试确实导入 HTTP helper，则暂时 re-export；否则 helper 保持私有；
- 明确的 `__all__`。

### 10.3 类身份测试

至少增加以下断言，防止兼容层重新定义类型：

```python
assert OldDeepSeekLLMGateway is NewDeepSeekLLMGateway
assert OldLLMProviderError is NewLLMProviderError
assert OldLLMGateway is NewLLMGateway
```

---

## 11. 分阶段实施计划

每一阶段必须遵循：先运行基线测试，实施，只运行相关测试，再运行全量测试；若失败，修复当前阶段，禁止带错进入下一阶段。

### 阶段 0：建立基线与兼容性测试

目标：在移动代码前记录真实行为。

任务：

1. 记录 `git status --short`，不得覆盖现有 staged/unstaged 修改；
2. 运行现有适配器相关测试；
3. 为旧导入路径补充 import smoke tests；
4. 为工厂默认值与缺失 key 行为补 characterization tests；
5. 为异常映射与 telemetry callback 补缺失的回归测试；
6. 记录当前 DeepSeek/Tavily/Embedding 构造签名。

验收：未修改生产行为；测试基线明确；工作区原有修改不丢失。

### 阶段 1：建立 Ports 包与兼容 re-export

目标：只移动抽象，不移动 DeepSeek。

任务：

1. 新建 `novel_agent/ports/`；
2. 将四个 Port 的唯一类定义移入对应文件；
3. 增加 telemetry 公共类型；
4. `adapters.py` 从新路径 re-export；
5. 逐步把 `service.py`、`workflow.py`、`story_skills.py` 的类型导入切到 `novel_agent.ports`；
6. 添加新旧路径类身份测试。

验收：业务层不再从 `adapters.py` 导入 Port；旧导入仍可用；不改变实现。

### 阶段 2：迁移本地、禁用与 Mock 实现

目标：先迁低风险实现，验证目录和兼容策略。

任务：

1. 迁移 `OfflineLLMGateway`、`DisabledRemoteGateway`；
2. 迁移 `DisabledSearchAdapter`；
3. 迁移 `DisabledEmbeddingGateway`；
4. 迁移 `MockPublisher`；
5. 在 `adapters.py` re-export；
6. 保证测试中的继承、monkeypatch 和类型检查仍有效。

验收：离线完整 Workflow 测试通过；旧类与新类身份一致。

### 阶段 3：迁移错误与 HTTP transport

目标：为远程 Provider 建立无循环依赖的公共底座。

任务：

1. 将 Provider errors 移到 `integrations/llm/errors.py`；
2. 将 `APIConfigurationRequired` 移到唯一公共定义位置；
3. 将 urllib transport 与必要 helper 移到 `http_transport.py`；
4. 保持 transport 可注入，以便单元测试不访问真实网络；
5. 更新 `api.py` 到新错误路径；
6. 在两个旧模块 re-export；
7. 检查并消除新的循环 import。

验收：异常分类、timeout、认证、限流与坏响应测试通过；类身份不变。

### 阶段 4：迁移 Search、Embedding 与 Publishing

目标：先迁体量较小的远程 Provider。

任务：

1. 迁移 Tavily/RemoteSearch 实现；
2. 迁移 OpenAI-compatible Embedding 实现；
3. 迁移 Fanqie Publisher；
4. 分别建立对应 `__init__.py` 的最小公开面；
5. 保持 transport 注入点和 monkeypatch 路径可测试；
6. 旧 `adapters_remote.py` re-export。

验收：Research、Embedding、Publisher 相关测试通过；无真实外网请求。

### 阶段 5：迁移 DeepSeek Gateway

目标：在底座稳定后再迁最高风险实现。

任务：

1. 原样迁移 Prompt 构造、structured/text chat；
2. 原样迁移 JSON 提取、修复、schema example；
3. 原样迁移重试、错误分类和 usage 采集；
4. 引入公开 telemetry 构造参数或配置方法；
5. 将 helper 保持私有，避免扩大公共 API；
6. 旧路径 re-export 类本身，不创建代理子类。

验收：`tests/test_deepseek_gateway.py` 全部通过；固定 transport 输入下的请求 body 与迁移前一致。

### 阶段 6：集中工厂并简化 bootstrap

目标：完成 Provider 选择与应用装配边界。

任务：

1. 建立 `integrations/factories.py`；
2. 实现四类 Settings 驱动工厂；
3. 保留旧工厂签名 wrapper；
4. 将 bootstrap 改为显式传入 telemetry；
5. 删除 bootstrap 对 `_on_call`、`_on_usage` 的私有字段操作；
6. 检查配置默认值和 provider name 兼容；
7. 增加工厂矩阵测试。

验收：bootstrap 不包含具体 Provider 分支或私有字段操作；API/Workflow 集成测试通过。

### 阶段 7：内部导入收口与全量回归

目标：新目录成为唯一真实实现位置。

任务：

1. 使用 `rg` 检查仓库内旧路径导入；
2. 生产代码迁到新路径，测试保留部分旧路径用于兼容验证；
3. 确认两个旧模块只剩兼容代码；
4. 运行静态检查、全量测试和 import smoke tests；
5. 检查 `git diff`，不得夹带格式化或无关修改；
6. 更新本实施文档的完成记录。

验收：所有 Definition of Done 条件满足。

### 阶段 8（可选，后续单独提交）：弃用提示与最终清理

只有确认不存在仓库外调用方后才可执行：

- 为旧路径增加适度的弃用说明；
- 在未来主版本删除兼容 Facade；
- 清理为兼容保留的 wrapper。

本次拆分默认不执行阶段 8。

---

## 12. 测试矩阵

### 12.1 必跑现有测试

优先运行：

```powershell
pytest tests/test_deepseek_gateway.py -q
pytest tests/test_research_embedding.py -q
pytest tests/test_workflow.py -q
pytest tests/test_revision_workspace.py -q
```

再运行项目全量测试（使用仓库当前约定命令；若项目配置为 `python -m pytest`，保持该方式）。

### 12.2 必增测试

| 测试类别 | 必测内容 |
|---|---|
| Import compatibility | 新旧路径均可导入，类身份一致 |
| Ports | 业务层只依赖 Ports；禁用/离线实现满足接口 |
| Factory matrix | 每个 provider 名称、disabled/offline、缺失 key、默认 URL/model |
| HTTP transport | method、headers、JSON body、timeout、非 2xx、无效 JSON |
| DeepSeek | structured/text、JSON 修复、schema example、retry、错误映射 |
| Telemetry | 调用次数、usage payload、缺失 usage、callback 失败策略 |
| Tavily | 请求参数、结果归一化、空结果、认证/网络错误 |
| Embedding | 请求格式、向量解析、空/畸形响应、配置缺失 |
| Publishing | Mock 行为、Fanqie 当前安全边界、不发生意外真实发布 |
| Bootstrap | 公开注入生效、不访问 `_on_call`/`_on_usage` |
| Workflow integration | Offline 与 mock transport 下完整流程通过 |

### 12.3 网络隔离要求

- 所有测试必须通过注入 transport、fake 或 monkeypatch 隔离外网；
- 不允许测试读取开发者真实 API key；
- 不允许测试向 DeepSeek、Tavily、SiliconFlow 或 Fanqie 发真实请求；
- fixture 中不得写入看似真实的密钥；
- 失败输出不得包含 Authorization header。

### 12.4 结构检查

建议增加或人工执行：

```powershell
rg -n "from novel_agent\.adapters import .*Gateway|from novel_agent\.adapters import .*Adapter" novel_agent
rg -n "adapters_remote" novel_agent
rg -n "_on_call|_on_usage" novel_agent/bootstrap.py
python -c "import novel_agent.adapters; import novel_agent.adapters_remote; import novel_agent.integrations.factories"
git diff --check
```

第一、第二个搜索结果需要逐条判断：兼容 Facade 与兼容测试中允许出现，生产业务模块中不应继续出现。第三个命令最终应无结果。

---

## 13. 风险与控制措施

### 风险 1：类被复制而非移动

后果：新旧路径异常捕获失败、`isinstance` 失效。  
控制：唯一类定义 + re-export + identity test。

### 风险 2：monkeypatch 路径变化

后果：测试表面打桩成功，实际请求仍访问真实 transport。  
控制：将 transport 作为构造依赖注入；测试断言 fake transport 被调用。

### 风险 3：默认配置发生漂移

后果：用户未改 `.env` 但 Provider 无法启动。  
控制：拆分前冻结默认 URL/model/provider name 测试。

### 风险 4：DeepSeek 大类一次性移动造成行为变化

后果：Prompt、解析、重试、usage 任一处回归。  
控制：DeepSeek 放在阶段 5，先完成 Ports、errors、transport 和小 Provider。

### 风险 5：telemetry 改造影响主调用

后果：统计失败导致生成失败，或重复记账。  
控制：冻结 callback 时机/次数；保持现有异常吞吐策略；集成测试核对次数。

### 风险 6：循环依赖被转移而非消除

后果：只能继续依靠函数内 import，启动时随机失败。  
控制：强制依赖方向；使用独立 import smoke test；工厂成为唯一选择实现的位置。

### 风险 7：误实现真实发布

后果：产生不可逆外部副作用。  
控制：Fanqie 本次只迁移；测试中禁止真实请求；不得扩展发布能力。

### 风险 8：覆盖当前工作区修改

后果：Analytics、Reader 工作台或用户其他改动丢失。  
控制：每阶段检查 `git status --short`；禁止 `git reset --hard`、`git checkout --` 和整文件覆盖式回退。

---

## 14. 回滚策略

每个阶段应独立提交或至少形成独立 diff。回滚只撤销当前阶段新增/迁移内容，不触碰用户已有修改。

- 阶段 1 失败：恢复业务层旧导入，删除新 Ports re-export，不修改 Provider；
- 阶段 2 失败：让 `adapters.py` 暂时继续承载本地实现；
- 阶段 3 失败：恢复旧错误/transport 定义，保留已稳定 Ports；
- 阶段 4 失败：按 Provider 单独回滚，不影响其他 Provider；
- 阶段 5 失败：`adapters_remote.py` 继续承载 DeepSeek，其他迁移保留；
- 阶段 6 失败：恢复旧工厂/bootstrap 装配，新实现模块仍可保留；
- 阶段 7 失败：仅恢复内部 import，不删除兼容层。

禁止使用会清除整个工作区修改的回滚命令。

---

## 15. 用户指南与 README 规则

本计划默认是纯结构重构，不改变用户可见行为，因此正常情况下 **不需要修改** `docs/USER_GUIDE.md`。

但是，只要实施过程中出现以下任一变化，必须在同一变更中同步更新 `docs/USER_GUIDE.md`：

- 配置变量、默认 Provider、默认 URL 或默认 model 发生变化；
- API Provider 支持范围发生变化；
- HTTP endpoint、CLI 命令或用户工作流发生变化；
- 成本、安全边界、发布能力或故障排查方式发生变化；
- 存储路径、备份或迁移步骤发生变化。

同时检查 README 指向用户指南的链接仍然有效。不得把内部 Python 导入路径写进面向非开发者的用户指南。

---

## 16. Definition of Done

只有同时满足以下条件，模块拆分才算完成：

- [x] `novel_agent/ports` 是四类外部能力抽象的唯一真实定义位置；
- [x] 各 Provider 已进入独立模块；
- [x] `adapters.py`、`adapters_remote.py` 仅作为兼容 Facade/薄 wrapper；
- [x] 业务层不再依赖具体 Provider 或旧聚合模块中的 Ports；
- [x] Provider errors 只有一份类定义，新旧路径类身份一致；
- [x] bootstrap 不再读写 `_on_call`、`_on_usage`；
- [x] 新工厂由 Settings 驱动并保持所有既有默认配置；
- [x] DeepSeek Prompt、解析、重试与 usage 行为未改变；
- [x] Tavily、Embedding、Publisher 行为未改变；
- [x] 旧导入路径全部通过兼容测试；
- [x] 所有网络测试使用 fake/注入 transport；
- [x] 相关测试与全量测试通过；
- [x] `git diff --check` 通过；
- [x] diff 不包含无关格式化和用户已有代码的覆盖；
- [x] 若发生任何用户可见变化，已同步更新 `docs/USER_GUIDE.md`（本拆分无用户可见变化，未改 USER_GUIDE）；
- [x] README 的用户指南链接仍有效。

---

## 17. 可直接交给 Cursor 的执行指令

以下内容可复制给 Cursor：

```text
请严格按照 docs/EXTERNAL_INTEGRATIONS_ADAPTERS_SPLIT_PLAN.md 拆分 External Integrations / Provider Adapters。

总原则：
1. 这是结构重构，不改变任何用户可见行为。
2. 先读取当前代码与测试，以当前实现为行为真源。
3. 保留 novel_agent.adapters 和 novel_agent.adapters_remote 两条旧导入路径。
4. 类只能移动并 re-export，不能在兼容层重新定义。
5. 不改变 Prompt、默认 URL/model、重试、错误映射、返回结构和 telemetry 语义。
6. 不新增网络库，不发真实外网请求，不实现真实 Fanqie 发布。
7. 不覆盖工作区已有修改，不使用 git reset --hard 或 git checkout --。
8. 每个阶段完成后先报告改动文件、测试结果和遗留问题，测试未通过不得进入下一阶段。

按以下顺序执行：

阶段 0：建立测试基线，补旧路径、类身份、默认配置、异常和 telemetry characterization tests。
阶段 1：新增 novel_agent/ports，只迁四个 Ports 与 telemetry 类型；更新业务层类型导入；旧路径 re-export。不要迁 DeepSeek。
阶段 2：迁移 Offline/Disabled/Mock 实现，并验证继承与旧路径兼容。
阶段 3：迁移 Provider errors 和 urllib transport，更新 api.py 错误导入，消除循环依赖。
阶段 4：分别迁移 Tavily、OpenAI-compatible Embedding、Fanqie，逐个运行测试。
阶段 5：最后迁移 DeepSeek，逐项冻结 Prompt、structured/text、JSON 修复、重试、错误和 usage 行为；加入公开 telemetry 注入。
阶段 6：建立 integrations/factories.py，提供 Settings 驱动的新工厂；保留旧工厂签名 wrapper；简化 bootstrap，删除对 _on_call/_on_usage 的私有字段操作。
阶段 7：生产代码导入收口，两个旧模块变为纯兼容 Facade，运行相关与全量测试、import smoke test、rg 结构检查和 git diff --check。

第一轮只执行阶段 0 和阶段 1。完成后停止并给出：
- 实际修改文件列表；
- 新旧 import identity 测试结果；
- 相关测试命令和结果；
- 当前 git diff 摘要；
- 是否发现当前代码行为与文档假设不一致。

未经确认不要继续移动 DeepSeekLLMGateway。
```

---

## 18. 推荐的实际启动点

第一轮只做 **阶段 0 + 阶段 1：Ports 与兼容性测试**。

不要把 `DeepSeekLLMGateway` 作为第一个移动对象。先让以下三件事稳定：

1. 新旧路径导入到同一个类；
2. 业务模块只依赖 Ports；
3. 全量测试在“实现尚未移动”的状态下通过。

这样可以把“抽象边界是否正确”和“远程 Provider 搬迁是否正确”拆成两个独立问题，后续每次迁移一个 Provider，失败时也能准确定位和回滚。

---

## 19. 实施完成记录

**状态：** 阶段 0—7 已完成；**阶段 8 未执行**（兼容 Facade 保留，无弃用警告）。

**完成日期：** 2026-09-30

### 最终目录结构

```text
novel_agent/
├── ports/                      # 唯一 Ports + telemetry sink 定义
├── integrations/
│   ├── errors.py               # APIConfigurationRequired
│   ├── http_transport.py       # 共享 Transport / _urllib_transport
│   ├── factories.py            # 唯一 Provider 选择逻辑
│   ├── llm/                    # offline / disabled / deepseek / errors / json_util
│   ├── search/                 # disabled / tavily(+RemoteSearchAdapter)
│   ├── embedding/              # disabled / openai_compatible
│   └── publishing/             # mock / fanqie
├── adapters.py                 # 兼容 Facade：Ports/实现 re-export + 旧工厂薄 wrapper
├── adapters_remote.py          # 兼容 Facade：远程 Provider / errors / helper re-export
└── bootstrap.py                # Settings + factories + 公开 on_call 注入
```

### 已确认的真实兼容行为（行为真源）

1. LLM `provider="disabled"` → `OfflineLLMGateway`（不是 DisabledRemoteGateway）
2. 未知 LLM provider → `DisabledRemoteGateway`
3. 未知 search/embedding provider → `APIConfigurationRequired`
4. DeepSeek 默认 model = `deepseek-v4-pro`
5. `openai-compatible` Embedding 无默认 base_url；`siliconflow` 默认 `https://api.siliconflow.cn/v1`
6. `FanqiePublisherAdapter` 初始化即抛 `APIConfigurationRequired`（安全闸门）
7. telemetry：`on_call` 优先于 `on_usage`；callback 异常吞掉，不影响主调用
8. 正式 Port 名称是 `EmbeddingGateway`（不是 EmbeddingPort）

### 测试与门禁

- 兼容测试：`tests/test_adapters_compat.py` 继续覆盖旧路径 identity / 工厂签名
- 工厂测试：`tests/test_factories.py`
- 阶段相关测试：`Ran 89 tests` → OK（compat + factories + deepseek + research_embedding + workflow + revision_workspace）
- 全量 unittest：`Ran 137 tests` → OK
- import smoke（同进程导入 ports / factories / 全部 Provider / adapters / adapters_remote / bootstrap / api / service / workflow）→ OK
- `git diff --check` → 通过（仅既有 CRLF warning，无 whitespace error）
- `adapters.py` / `adapters_remote.py` 继续作为兼容层保留；不删除、不加 DeprecationWarning
- 阶段 8 未执行
