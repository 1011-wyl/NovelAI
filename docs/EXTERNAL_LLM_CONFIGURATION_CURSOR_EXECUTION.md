# 外部大模型 API 配置功能——Cursor 可执行开发文档

> 目标：在“运行能力状态”区域点击“大模型（LLM）”卡片后，进入可视化配置界面。用户可以在应用外部申请 API Key，再在本项目中配置供应商、接口地址和模型；保存并测试成功后，小说生成、章节重写、质量审核、AI 对话等所有生产调用统一使用该配置。
>
> 本文是实施任务书，不代表功能已经上线。完成代码修改后，必须同步更新 `docs/USER_GUIDE.md`。

## 1. Cursor 执行原则

1. 先审计，后修改。不要根据本文凭空新建一套与现有架构重复的配置系统。
2. 参考项目位于 `D:\实习日报\githubClone\OpenFic`。只参考它的交互流程、字段组织和状态表达，不要整段复制实现，也不要破坏 OpenFic 工作区。
3. 当前项目位于 `D:\实习日报\NovelAI\NovelAI`。修改前先阅读根目录及子目录中的 `AGENTS.md`。
4. 保留工作区中用户已有的未提交修改；不得回滚、覆盖或清理无关文件。
5. API Key 属于机密：不得输出到终端、日志、异常、测试快照、前端响应、浏览器存储或 Git。
6. 前端必须使用 Vue 3，并按照现有项目的 Composition API、TypeScript、样式和测试约定实现。
7. 所有运行中的 LLM 功能必须通过统一配置解析器和客户端工厂获取模型，禁止各功能继续单独读取环境变量或自行实例化供应商客户端。
8. 不允许为了“看起来成功”而静默切换到离线模型。远程模型调用失败时必须返回真实、可操作的错误；离线模式只能由测试或明确的开发配置启用。

## 2. 修改范围

### 2.1 本次必须完成

- “运行能力状态”中的“大模型（LLM）”卡片可点击、可键盘操作，并有明确的悬停/聚焦状态。
- 点击后打开“大模型配置”界面。优先沿用项目已有的路由、抽屉或模态框模式；若没有统一模式，使用右侧抽屉，在窄屏切换成整页。
- 支持新增、编辑、测试、保存、启用、停用和清除 LLM 配置。
- 首期支持以下配置类型：
  - DeepSeek；
  - 阿里云百炼 DashScope / Qwen（OpenAI 兼容接口）；
  - OpenAI；
  - 自定义 OpenAI-compatible 接口。
- 非机密配置持久化；API Key 安全存储。
- 所有生产 LLM 调用统一切换到当前生效配置，包括但不限于：小说方案生成、章节生成、续写/重写、质量审核、自动修订、右侧 AI 对话。
- 保存后更新运行能力卡片，显示生效的供应商和模型，例如 `dashscope · qwen-plus`。
- 增加配置测试接口和清晰的错误分类。
- 兼容现有环境变量配置，不要求用户立刻迁移。
- 添加后端单元/集成测试、前端组件测试以及至少一条端到端流程测试。
- 更新 `docs/USER_GUIDE.md`；保持 README 中用户指南链接有效。

### 2.2 本次不做

- 联网搜索、向量嵌入、发布适配和 Story Skills 的配置。
- 在线拉取所有供应商的实时模型列表。首期允许“推荐模型下拉框 + 自定义模型 ID”。
- 多用户账号、云端密钥同步、计费充值、API Key 代购。
- 在一个写作任务中动态切换模型。任务开始时固定配置快照。

## 3. 先执行的代码审计

Cursor 必须先完成以下审计，并把结论写入最终交付报告：

### 3.1 当前项目

使用 `rg` 定位，不要读取或打印任何 `.env` 中的值：

- “运行能力状态”“大模型（LLM）”“联网搜索”“向量嵌入”等文案所在的 Vue 页面和组件；
- 前端路由、API 请求封装、状态管理及通用 Modal/Drawer/Form 组件；
- 后端 HTTP 路由注册方式、设置/配置仓库、数据库初始化和迁移方式；
- `novel_agent/integrations/llm/` 下的 DeepSeek、DashScope、OpenAI-compatible、离线实现；
- 所有直接读取 API Key、Base URL、模型名或直接构造 LLM 客户端的位置；
- 小说方案、工作流、章节审核、自动修订、AI 对话的完整调用链；
- 配置类、环境变量样例、README、`docs/USER_GUIDE.md`、`docs/API.md`；
- 日志中可能记录请求头、请求体、完整异常或 API Key 的位置。

安全检查环境变量时只能确认“是否存在”，禁止用 `Get-Content .env`、`cat .env`、`rg API_KEY .env` 等方式打印值。

### 3.2 OpenFic 参考项目

定位并记录：

- LLM 状态卡点击后的入口形式；
- 供应商选择、模型输入、Base URL、API Key、测试连接、保存与状态回显的交互；
- 配置存储位置、后端接口和运行时客户端解析方式；
- 哪些设计可以复用，哪些不适合本项目。

只吸收适合当前项目的交互，不照搬 OpenFic 的业务命名、目录或无关能力。

## 4. 用户流程

### 4.1 首次配置

1. 用户进入运行能力页面。
2. “大模型（LLM）”卡片显示“未配置”，整张卡片可点击。
3. 用户点击卡片，打开配置界面。
4. 用户选择供应商。
5. 系统自动填入该供应商推荐的 Base URL 和推荐模型；用户可以更改模型 ID。
6. 用户输入 API Key。输入框默认遮挡，支持临时显示/隐藏，禁止复制到任何回显区域。
7. 用户点击“测试连接”。
8. 后端使用当前表单数据执行低成本连通性测试，返回成功或分类错误。
9. 测试成功后用户点击“保存并启用”。保存成功，关闭界面并刷新状态卡。
10. 后续新启动的生成任务使用该配置；已经运行的任务继续使用启动时的配置快照。

### 4.2 编辑已有配置

- 页面仅显示“已保存密钥（尾号 4 位可选）”，绝不把完整 Key 返回给前端。
- API Key 输入框为空时表示“保留现有密钥”，不是清空。
- 用户输入新 Key 才执行替换。
- 更改供应商或 Base URL 后必须重新测试；配置状态变为“待验证”。
- 提供独立的“清除密钥/删除配置”操作，并二次确认。

### 4.3 失败和恢复

- 连接测试失败时保留表单内容，但不得记录 Key。
- 已有生效配置编辑失败时，不覆盖最后一份可用配置。
- 保存采用原子更新：非机密配置和密钥都写入成功后再切换生效版本。
- 生产调用发生鉴权错误时，状态卡显示“需要处理”，点击后直接进入配置界面并显示安全的错误摘要。
- 不因一次超时永久标记配置无效；区分“配置错误”和“临时网络故障”。

## 5. 界面设计

### 5.1 运行能力卡片

卡片保留截图中的简洁样式，但增加交互提示：

- 标题：`大模型（LLM）`；
- 副标题：已配置时为 `{providerLabel} · {model}`，未配置时为“点击配置模型服务”；
- 右侧状态：`已启用`、`未配置`、`待验证`、`需要处理`、`已停用`；
- 右侧增加轻量箭头或“配置”文本，不使用拖拽框；
- 整卡使用 `button` 或语义等价的可聚焦元素；
- 支持 Enter/Space；有 `aria-label`、可见焦点和足够对比度；
- 加载时仅禁用该卡片，不冻结整个页面。

状态颜色只作为辅助信息，不能只靠颜色表达状态。

### 5.2 配置界面信息架构

界面分为四段，避免把高级参数一次性铺满：

1. **模型服务**
   - 供应商；
   - API 地址；
   - 模型 ID。
2. **访问凭证**
   - API Key；
   - 已保存密钥提示；
   - 显示/隐藏按钮；
   - 安全说明：“密钥只发送给本机后端，不会从接口回显”。
3. **连接状态**
   - 上次测试结果和时间；
   - “测试连接”按钮；
   - 简洁错误说明和解决建议。
4. **高级设置**（默认折叠）
   - 请求超时；
   - 最大重试次数；
   - 可选的组织/项目请求头，仅在供应商确有需要时展示。

底部固定操作区：`取消`、`测试连接`、`保存并启用`。删除/清除配置放在危险操作区，不与主按钮并排抢占视觉焦点。

### 5.3 字段规则

| 字段 | 必填 | 规则 |
| --- | --- | --- |
| `provider` | 是 | 枚举值，不直接把展示文案作为存储值 |
| `base_url` | 是 | 必须是合法 `http/https` URL；生产部署默认要求 HTTPS；去除末尾多余 `/` |
| `model` | 是 | 1～128 字符，允许供应商常见模型 ID 字符 |
| `api_key` | 新配置必填 | 不设置最大值过小；编辑时空值代表保留旧 Key |
| `timeout_seconds` | 是 | 建议 10～300 秒，默认沿用当前项目合理值 |
| `max_retries` | 是 | 建议 0～5，默认沿用当前项目合理值 |

Base URL 是否需要自动追加 `/v1` 由供应商适配器处理，不在多个调用点重复拼接。

### 5.4 推荐预设

供应商默认值集中存放在一处，不要散落在 Vue 组件、路由和客户端中：

| 供应商 | 默认 Base URL | 推荐模型示例 |
| --- | --- | --- |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 由项目当前支持的 Qwen 模型作为默认值 |
| OpenAI | `https://api.openai.com/v1` | 不硬编码可能过期的唯一模型；提供可编辑推荐值 |
| 自定义兼容接口 | 空 | 用户填写 |

不要从截图中的 `qwen3.7-plus` 推断它一定是可用模型。模型名必须允许用户编辑，实际有效性由“测试连接”确认。

## 6. 后端设计

### 6.1 分层结构

按当前项目实际目录命名落位，但职责必须拆开：

```text
LLM settings HTTP routes
        ↓
LLM settings service
        ├── validation / redaction
        ├── settings repository（非机密）
        └── secret store（API Key）
        ↓
EffectiveLLMConfigResolver
        ↓
LLMClientFactory / provider adapters
        ↓
writing / review / revision / chat workflows
```

禁止：Vue 直接调用第三方接口；业务工作流读取数据库字段或环境变量；每个功能单独维护一份 provider 判断。

### 6.2 领域模型

建议根据现有命名风格建立以下模型：

```python
class LLMProvider(str, Enum):
    DEEPSEEK = "deepseek"
    DASHSCOPE = "dashscope"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"

class LLMConfiguration:
    id: str
    provider: LLMProvider
    base_url: str
    model: str
    enabled: bool
    timeout_seconds: int
    max_retries: int
    secret_ref: str | None
    verification_status: str  # unverified / valid / invalid
    last_tested_at: datetime | None
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime
    version: int
```

API Key 不属于 `LLMConfiguration` 的可序列化字段。运行时使用单独的不可回显对象，例如 `ResolvedLLMCredentials`。

### 6.3 配置来源优先级

统一解析器使用确定性的优先级：

1. 已保存且启用的 UI 配置；
2. 现有环境变量配置（兼容旧部署）；
3. 仅在明确的测试/开发开关开启时使用离线实现；
4. 否则返回 `LLM_NOT_CONFIGURED`，不得伪装成成功。

状态接口同时返回 `source: saved | environment | offline | none`，但不要暴露环境变量内容。

### 6.4 密钥存储

实现 `SecretStore` 抽象，不把 Key 明文写入普通 SQLite 表、JSON、YAML、localStorage 或 sessionStorage：

```python
class SecretStore(Protocol):
    def put(self, secret_ref: str, value: str) -> None: ...
    def get(self, secret_ref: str) -> str: ...
    def delete(self, secret_ref: str) -> None: ...
    def exists(self, secret_ref: str) -> bool: ...
```

优先使用当前项目已有的安全存储机制。若没有：

- 本地桌面/单机运行优先接入系统凭据存储（Windows Credential Manager、macOS Keychain、Linux Secret Service，可通过成熟的 keyring 适配）；
- 必须提供测试用内存实现；
- 若系统凭据存储不可用，不得静默降级为明文文件。返回 `SECRET_STORE_UNAVAILABLE`，并在用户指南说明配置要求；
- 数据库只保存不可逆推导不出 Key 的 `secret_ref` 和可选的掩码元信息；
- 更新密钥时先写入新引用，配置提交成功后再删除旧引用，确保失败可回滚。

### 6.5 HTTP API

路径应服从项目已有前缀。若项目以 `/api` 开头，建议：

#### `GET /api/settings/llm`

返回安全视图：

```json
{
  "provider": "dashscope",
  "provider_label": "阿里云百炼 DashScope",
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "model": "qwen-plus",
  "enabled": true,
  "has_api_key": true,
  "api_key_mask": "••••1234",
  "verification_status": "valid",
  "last_tested_at": "2026-10-04T10:00:00+08:00",
  "source": "saved",
  "version": 3
}
```

完整 API Key 永不返回；如果供应商 Key 不适合展示尾号，则只返回 `has_api_key`。

#### `PUT /api/settings/llm`

请求：

```json
{
  "provider": "dashscope",
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "model": "qwen-plus",
  "api_key": "<只在新增或替换时提交>",
  "keep_existing_api_key": true,
  "enabled": true,
  "timeout_seconds": 120,
  "max_retries": 2,
  "expected_version": 3
}
```

规则：

- `api_key` 缺失且 `keep_existing_api_key=true` 时保留旧密钥；
- 新配置没有 Key 时返回 422；
- 使用 `expected_version` 做乐观锁，避免两个页面互相覆盖；
- 响应仍是安全视图；
- API Key 不得出现在验证错误详情中。

#### `POST /api/settings/llm/test`

- 可以测试“已保存配置”，也可以测试“当前尚未保存的表单”。
- 未提交新 Key 且已有 Key 时由后端读取；前端不需要获取旧 Key。
- 使用极短、确定、低 token 的请求验证鉴权、地址、模型和基本响应解析。
- 返回标准化结果，不返回供应商原始响应正文。

```json
{
  "ok": true,
  "code": "CONNECTION_OK",
  "message": "连接成功",
  "latency_ms": 842,
  "tested_at": "2026-10-04T10:00:00+08:00"
}
```

#### `DELETE /api/settings/llm`

- 二次确认由前端完成，后端仍需鉴权/本地权限校验；
- 删除非机密配置和对应密钥；
- 若环境变量仍提供有效配置，状态应回退为 `source=environment`，而不是错误地显示未配置。

如项目现有 HTTP 规范不使用 PUT/DELETE，可调整方法，但语义、幂等性和测试必须保持。

### 6.6 错误代码

至少标准化以下错误，前端不得直接展示第三方完整异常：

| 代码 | 用户提示 |
| --- | --- |
| `LLM_NOT_CONFIGURED` | 尚未配置大模型服务 |
| `INVALID_API_KEY` | API Key 无效或已失效 |
| `MODEL_NOT_FOUND` | 当前账号无法使用该模型，请检查模型 ID |
| `INVALID_BASE_URL` | API 地址格式或接口路径不正确 |
| `NETWORK_UNREACHABLE` | 无法连接服务，请检查网络和 API 地址 |
| `REQUEST_TIMEOUT` | 连接超时，可稍后重试或调整超时时间 |
| `RATE_LIMITED` | 请求过于频繁或额度受限 |
| `INSUFFICIENT_QUOTA` | 账户额度不足 |
| `PROVIDER_ERROR` | 模型服务暂时异常 |
| `SECRET_STORE_UNAVAILABLE` | 本机安全凭据存储不可用 |
| `CONFIG_VERSION_CONFLICT` | 配置已在其他页面更新，请刷新后重试 |

服务器日志可以记录错误代码、供应商、模型、耗时和请求 ID，但不能记录 Authorization 头、Key、完整提示词、小说正文或第三方原始响应正文。

### 6.7 统一运行时调用

建立或整理为统一工厂：

```python
config = effective_llm_config_resolver.resolve()
client = llm_client_factory.create(config)
```

要求：

- 供应商适配器只处理各自协议差异；OpenAI-compatible 共用一个基础适配器；
- 在每次“运行任务”开始时生成不可变配置快照，记录 provider、model、base_url、配置版本，不记录 Key；
- 同一任务的写作与审核默认使用同一配置契约；若未来支持不同模型，另开功能，不在本次暗中拆分；
- 保存配置后使客户端缓存失效，新任务立刻使用新配置；
- 正在执行的任务不受配置切换影响；
- 删除所有生产调用点对旧全局客户端、硬编码模型名和分散环境变量的直接依赖；
- 保留兼容层只能有一个入口，并标注迁移意图，不能让新旧两条链路随机并存。

## 7. 前端模块划分（Vue 3）

按照实际目录微调文件名，建议组织为：

```text
apps/web/src/features/settings/llm/
├── api/
│   └── llm-settings-api.ts
├── components/
│   ├── LlmSettingsDrawer.vue
│   ├── LlmProviderFields.vue
│   ├── LlmSecretField.vue
│   ├── LlmConnectionStatus.vue
│   └── LlmAdvancedSettings.vue
├── composables/
│   └── useLlmSettings.ts
├── model/
│   ├── contracts.ts
│   ├── providers.ts
│   └── validation.ts
└── tests/
```

运行能力页面只负责：

- 获取安全状态；
- 展示卡片；
- 打开配置界面；
- 保存后刷新状态。

它不应包含供应商字段规则、请求拼装、密钥状态判断或第三方 API 逻辑。

前端状态至少包括：`idle`、`loading`、`testing`、`saving`、`deleting`、`success`、`error`。测试连接和保存分别禁用自己的按钮，防止重复提交；关闭有未保存修改的界面时给出确认。

## 8. 旧代码清理与兼容

### 8.1 必须删除或收口

- 各工作流中直接使用 `os.getenv(...)` 读取模型配置的代码；
- 分散的默认 Base URL、模型名和供应商判断；
- 前端硬编码“已启用”但后端实际无配置的假状态；
- 任意把 API Key 放进普通配置 DTO、日志或 API 响应的代码；
- 新旧 LLM 客户端并存、随机被不同功能调用的分叉；
- 失败后无提示切换到离线生成的生产逻辑。

不要删除历史数据或用户 `.env`。环境变量兼容必须通过统一解析器保留。

### 8.2 兼容变量

审计当前代码后列出实际变量名。若现有项目使用例如 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`，继续支持并写入用户指南。不要未经检查擅自重命名变量。

如需新增示例文件，只更新不含真实密钥的 `.env.example`，示例值必须是占位符。

### 8.3 数据迁移

- 新表/字段采用项目现有迁移方式；
- 迁移不得读取并复制环境变量中的 Key 到数据库；
- 老数据库升级后默认无 UI 配置，继续从环境变量解析；
- 回滚时不能删除系统凭据中的旧 Key，除非明确确认该凭据由本次迁移创建且安全删除；
- 不修改用户正式数据库来跑测试，使用临时数据库和内存 SecretStore。

## 9. 测试要求

### 9.1 后端单元测试

- 配置校验：provider、URL、model、timeout、retry；
- API Key 永不参与响应序列化；
- 新增、保留旧 Key、替换 Key、删除 Key；
- 密钥写入失败时配置不切换；配置写入失败时新密钥可回滚；
- 配置来源优先级：saved > environment > explicit offline > none；
- 配置版本冲突；
- 四种 provider 到适配器的映射；
- 连接测试错误映射；
- 日志脱敏；
- 客户端缓存失效；
- 运行任务持有不可变配置快照。

### 9.2 后端集成测试

- GET 不返回 Key；
- PUT 新建、编辑和保留密钥；
- POST test 使用未保存 Key 和已保存 Key；
- DELETE 后正确回退到环境变量或未配置状态；
- 保存新配置后章节生成、质量审核和 AI 对话都通过统一工厂获取同一 provider/model；
- 第三方模拟 401、404、429、超时、额度不足、5xx 时返回约定错误码；
- 测试全部使用 mock server，不调用真实计费 API。

### 9.3 前端测试

- 卡片鼠标和键盘都可打开配置界面；
- 未配置/已启用/待验证/需要处理/停用状态正确；
- 选择 provider 后更新推荐字段，但不强制覆盖用户已编辑的值；
- 已保存配置不回填完整 Key；
- 空 Key + 保留选项不会清空旧 Key；
- API Key 显示/隐藏正常，DOM 快照与错误文本不包含真实测试 Key；
- 更改关键字段后状态变为待验证；
- 测试失败不会错误显示保存成功；
- 有未保存修改时关闭确认；
- 窄屏布局无横向滚动。

### 9.4 E2E

至少覆盖：

1. 未配置 → 点击 LLM 卡片 → 填写 → 测试成功 → 保存启用 → 卡片展示 provider/model；
2. 编辑现有配置且不输入新 Key → 保存 → 原 Key 仍可用；
3. 输入错误 Key → 测试返回鉴权错误 → 原生效配置未被覆盖；
4. 清除配置 → 回退到环境变量或未配置；
5. 配置成功后触发一个生成入口，mock 断言请求使用新 provider/model，且前后端日志不含 Key。

## 10. 文档更新

实现完成后必须更新 `docs/USER_GUIDE.md`，用非开发者能理解的中文说明：

- 从哪里点击“大模型（LLM）”；
- 如何选择供应商、填写 Base URL、模型名和 API Key；
- “测试连接”和“保存并启用”的区别；
- 已保存密钥为什么不会再次显示；
- 配置何时对新任务生效；
- 环境变量与页面配置的优先级；
- 如何停用、替换和清除密钥；
- 401、模型不存在、限流、额度不足、网络超时的排查方式；
- API 请求可能产生供应商费用，应用本身不代购额度；
- Key 的安全边界与备份/迁移限制。

同时检查 README 到用户指南的链接仍然有效；如接口发生变化，更新 `docs/API.md`。

## 11. 完成标准

以下条件全部满足才能报告完成：

- [ ] LLM 状态卡可点击且无障碍键盘操作正常；
- [ ] 配置界面完成供应商、Base URL、模型、Key、测试、保存、启用、停用、清除；
- [ ] 完整 API Key 从未由 GET 接口返回；
- [ ] Key 不存在于浏览器存储、普通数据库明文字段、日志、异常和测试快照；
- [ ] 四类 provider 均由统一客户端工厂创建；
- [ ] 所有生产 LLM 调用均通过统一配置解析器；
- [ ] 页面配置优先于环境变量，环境变量兼容仍有效；
- [ ] 保存失败不破坏上一份可用配置；
- [ ] 新任务使用新配置，运行中的任务保持配置快照；
- [ ] 远程失败不会静默伪装成离线成功；
- [ ] 后端、前端、类型检查、lint、构建和 E2E 均通过；
- [ ] `git diff --check` 通过；
- [ ] `docs/USER_GUIDE.md` 与 `docs/API.md`（如适用）已同步；
- [ ] 未修改正式数据库，未泄露或提交任何真实 Key；
- [ ] 最终报告列出修改文件、删除的旧路径、配置优先级、测试命令与结果、未完成项。

## 12. 建议实施顺序

1. 审计当前项目和 OpenFic，并画出当前 LLM 调用链。
2. 确定现有数据库迁移、配置仓库、前端路由和 UI 容器约定。
3. 先写后端契约、SecretStore、配置仓库和测试。
4. 实现 EffectiveLLMConfigResolver 与 LLMClientFactory。
5. 将所有写作、审核、修订、对话调用迁移到统一工厂。
6. 实现设置 API 和错误映射。
7. 实现 Vue 3 配置模块与运行能力卡片入口。
8. 清理旧的分散配置/客户端路径。
9. 补齐单元、集成、前端和 E2E 测试。
10. 更新用户指南和 API 文档，运行完整验证。

---

## 13. 可直接发给 Cursor 的提示词

```text
请严格执行 docs/EXTERNAL_LLM_CONFIGURATION_CURSOR_EXECUTION.md，在当前 NovelAI 项目中完成“从运行能力状态的大模型（LLM）卡片进入并配置外部大模型 API”的前后端功能。

执行要求：
1. 开始前阅读所有适用的 AGENTS.md，并审计当前项目与 D:\实习日报\githubClone\OpenFic 中相关实现。OpenFic 只作为交互和架构参考，不要直接照搬，也不要修改它。
2. 保留工作区已有未提交修改，不得回滚或覆盖无关代码。
3. 前端使用 Vue 3、TypeScript 和当前项目已有组件/样式规范；大模型卡片需要支持鼠标与键盘打开配置界面。
4. 后端实现统一的 LLM 配置服务、SecretStore、有效配置解析器和客户端工厂。页面配置优先于现有环境变量；离线模型只能显式启用，远程失败不得静默降级。
5. API Key 只能提交给后端安全存储，完整值不得从接口回传，不得写入 localStorage/sessionStorage、普通数据库明文字段、日志、异常、测试快照或 Git。不要打印任何现有 .env 的内容。
6. 首期支持 DeepSeek、DashScope/Qwen、OpenAI、自定义 OpenAI-compatible；实现连接测试、保存启用、编辑保留旧 Key、替换 Key、停用和清除。
7. 小说方案、章节生成、重写、质量审核、自动修订、右侧 AI 对话等所有生产调用必须统一使用新配置入口；删除或收口旧的分散读取和客户端构造逻辑，不能保留随机走新旧链路的代码。
8. 保存配置必须是原子的；失败不能破坏上一份可用配置。新配置只影响新启动的任务，运行中的任务继续使用启动时的无密钥配置快照。
9. 使用临时数据库、内存 SecretStore 和 mock provider 完成测试，禁止调用真实计费 API，禁止修改正式数据库。
10. 按项目规则同步更新 docs/USER_GUIDE.md；如接口有变更，更新 docs/API.md，并确认 README 用户指南链接有效。
11. 完成后运行后端完整测试、前端测试、type-check、lint、生产构建、E2E、git diff --check，并用 rg 检查旧生产路径和潜在密钥泄露。不要只跑新增测试。

请先输出审计结果和计划，再直接实施，不需要等待我逐项确认。最终报告必须包含：
- 当前调用链与改造后的调用链；
- 修改/新增/删除的文件；
- API 和配置来源优先级；
- 密钥存储方式及安全边界；
- 清理掉的旧逻辑；
- 每条验证命令和真实结果；
- 尚未完成或刻意收窄的内容。

只有满足文档第 11 节全部完成标准后，才可以声明任务完成。
```

<!-- 本文档为 Cursor 实施任务书；功能上线状态以代码与测试结果为准。 -->
