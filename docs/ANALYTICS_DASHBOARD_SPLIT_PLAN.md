# NovelAI Analytics / Dashboard 模块详细拆分实施文档

> 文档用途：交给 Cursor 按阶段执行 Analytics / Dashboard 的垂直模块化拆分  
> 审计基线：2026-09-30 当前工作区  
> 本文只规划结构重构，不要求在编写本文时修改业务代码  
> 总体方案：[MODULAR_CODEBASE_SPLIT_PLAN.md](./MODULAR_CODEBASE_SPLIT_PLAN.md)

## 1. 本次拆分要解决什么

当前 Analytics / Dashboard 已经具备完整功能，但实现分散在多个“大入口”中：

- `novel_agent/repository.py` 同时负责 Analytics 表迁移、事件写入、查询过滤、SQL 聚合、分页和返回结构拼装；
- `novel_agent/service.py` 只包装了旧 Token 统计，Dashboard 三个接口却绕过 Service 直接访问 Repository；
- `novel_agent/api.py` 同时完成路由匹配、查询参数解析、类型转换和 Repository 调用；
- `apps/web/dashboard.js` 同时管理 API 请求、AbortController、页面状态、图表原语、业务数据转换、DOM 渲染、筛选、排序、分页和生命周期；
- `apps/web/app.js` 通过 `window.NovelDashboard` 与 Dashboard 通信；
- Dashboard 静态 DOM 仍占据 `apps/web/index.html` 的大段内容。

本次目标不是重做仪表盘样式，也不是新增统计指标，而是建立一条清晰、可复用的垂直边界：

```text
LLM / 章节 / 修订模块
        │ 只上报观测事件
        ▼
Analytics Recorder / Store
        │
        ▼
Analytics Service
        │
        ▼
Analytics HTTP Routes
        │
        ▼
Analytics Frontend Feature
```

拆分完成后，应当能回答以下问题：

1. 想修改写作统计 SQL，应只进入 `infrastructure/persistence/analytics_store.py`；
2. 想修改统计业务规则，应只进入 `features/analytics/service.py`；
3. 想修改 Dashboard 查询参数，应只进入 `interfaces/http/routes/analytics.py` 和查询模型；
4. 想修改某个图表，应只进入对应 chart 或 feature 文件；
5. 章节、修订和 LLM 适配器只负责“产生事件”，不依赖 Dashboard 页面或统计查询。

## 2. 范围和非目标

### 2.1 本次必须纳入的能力

后端：

- LLM 调用记录写入；
- 写作活动事件写入；
- 历史章节写作活动回填；
- 旧 Token 日统计与周期汇总；
- 写作仪表盘聚合；
- LLM 汇总、模型趋势、模型分布和项目分布；
- 调用记录筛选、搜索、排序和分页；
- Dashboard 筛选选项；
- Dashboard HTTP 路由和错误映射；
- bootstrap 中 Analytics 依赖装配。

前端：

- 写作、LLM 统计、调用记录三个 Tab；
- 年度写作热力图与年度指标；
- 写作趋势、累计字数、来源占比、星期分布；
- LLM 指标卡和六张图表；
- 调用记录筛选、搜索防抖、排序和分页；
- 请求取消、过期响应保护、loading/empty/error 状态；
- Dashboard 激活、停用和刷新生命周期；
- Analytics HTML 模板和专属 CSS 的归属。

### 2.2 本次明确不做

- 不改变现有 UI 视觉、文案或交互逻辑；
- 不增加费用估算、预算告警、导出、实时推送等新功能；
- 不迁移到 FastAPI、SQLAlchemy、React、Vue 或 npm 构建系统；
- 不修改 SQLite 表名、字段、索引或已有迁移版本；
- 不统一重构所有 HTTP 路由，只提取 Analytics 路由；
- 不顺手重构 Reader、Settings、章节工作流或 LLM Provider；
- 不在结构迁移时优化 SQL 次数或改变聚合算法；
- 不删除旧公共方法，直到兼容测试证明所有调用者已经迁移。

## 3. 当前实现审计

### 3.1 数据库和存储职责

`novel_agent/repository.py` 中与本模块相关的当前职责：

| 当前内容 | 当前大致位置 | 说明 |
|---|---:|---|
| `SCHEMA_VERSION`、`DASHBOARD_MIGRATION_VERSION` | 33–34 | 当前分别为 5 和 4 |
| `token_usage` 建表和补列 | 276–371 | LLM 调用记录及索引 |
| `writing_activity_events` 建表和索引 | 302–320 | 写作活动事件 |
| `_backfill_writing_activity` | 1742–1773 | 从已有章节回填一次写作事件 |
| `save_token_usage` | 1775–1807 | 兼容旧 callback 参数并创建 `LLMCallRecord` |
| `record_llm_call` | 1809–1840 | 写入 `token_usage` |
| `record_writing_activity` | 1842–1878 | 写入写作事件；支持复用外部事务连接 |
| `get_token_statistics` | 1880–1911 | 按 `date` 聚合 Token 数组 |
| `get_token_daily_summary` | 1913–1938 | 周期 Token 汇总 |
| `_parse_timezone` 等时间 helper | 1940–1979 | 日期解析和本地日期计算 |
| `get_writing_dashboard` | 1981–2045 | 写作统计聚合 |
| `get_dashboard_filter_options` | 2047–2121 | 项目、模型、Provider 等筛选选项 |
| `_token_usage_filters` | 2123–2182 | LLM 查询条件与 LIKE 转义 |
| `get_llm_dashboard_stats` | 2184–2301 | LLM 汇总和分组统计 |
| `list_llm_call_records` | 2303–2406 | 调用记录分页、排序和映射 |

当前最重要的隐式契约是：`record_writing_activity(..., conn=existing_connection)` 可以加入章节或修订的既有事务。拆分后必须继续支持这一点，不能为了“独立 Store”而把一次原子提交拆成两个数据库事务。

### 3.2 数据生产者

Analytics 不只是读取 Dashboard，它还有两个写入来源：

1. `novel_agent/bootstrap.py` 把 `repository.save_token_usage` 填入 Gateway 的 `_on_call` 或 `_on_usage` 私有回调；
2. `novel_agent/repository.py` 的章节正式提交和 `novel_agent/revision_store.py` 的修订提交会调用 `record_writing_activity`。

因此拆分时必须把“记录事件”和“读取统计”分开建模：

- 写入侧是稳定、轻量、不能依赖页面的观测接口；
- 读取侧是面向 Dashboard 的查询接口；
- 章节和修订模块只能看到写入接口，不应看到 `get_llm_dashboard_stats` 等查询能力。

### 3.3 Service 和 HTTP

当前 `NovelAgentService`：

- `get_usage()` 返回 Gateway 内存态用量摘要；
- `get_token_statistics()` 调用 Repository 两个方法，再计算今日用量、峰值和日均。

当前 `NovelAgentHandler`：

- `/api/token/statistics` 调用 `NovelAgentService`；
- `/api/dashboard/writing` 直接调用 Repository；
- `/api/dashboard/llm-api/stats` 直接调用 Repository；
- `/api/dashboard/llm-api/records` 直接调用 Repository，并在 Handler 内转换 `page`、`page_size`；
- RepositoryError 和 ValueError 最终映射为 HTTP 400。

这使得同一模块同时存在两种入口，无法在 Service 层统一验证和测试。

### 3.4 前端

当前 `apps/web/dashboard.js` 约 1153 行，主要职责可分为：

| 当前函数/状态 | 目标职责 |
|---|---|
| 常量、`format*`、日期 helper | `shared/labels.js`、`core/format.js`、`core/date.js` |
| `state` | `features/analytics/state.js` |
| `controllers`、`requestIds`、`fetchJson` | `features/analytics/api.js` |
| tooltip、cleanup、resize、chart state | `ui/charts/runtime.js` |
| `renderLineChart` | `ui/charts/line-chart.js` |
| `renderBarChart` | `ui/charts/bar-chart.js` |
| `renderDonutChart` | `ui/charts/donut-chart.js` |
| `renderYearHeatmap` | `ui/charts/year-heatmap.js` |
| `computeYearMetrics` 到 `buildTokenTrend` | `features/analytics/selectors.js` |
| 写作渲染和加载 | `features/analytics/writing.js` |
| LLM 渲染和加载 | `features/analytics/llm.js` |
| 记录筛选、表格、分页和加载 | `features/analytics/records.js` |
| Tab、事件、init/activate/deactivate/refresh | `features/analytics/view.js` |

当前页面通过 `window.NovelDashboard` 暴露生命周期，`app.js` 在导航时调用 `activate()` / `deactivate()`，启动时调用 `init()`。目标是改成显式模块实例，同时在迁移提交中保留一个短期兼容入口。

### 3.5 现有测试

`tests/test_dashboard.py` 已覆盖：

- Dashboard migration 幂等且只回填一次；
- 写作事件按 `Asia/Shanghai` 分组；
- LLM 汇总、筛选、排序、搜索特殊字符；
- 非法排序字段抛错；
- LLM 上下文在线程之间隔离；
- 三个 Dashboard endpoint 空数据返回 200；
- 非法排序字段通过 HTTP 返回 400。

`tests/test_repository.py` 还覆盖 Token 日汇总。现有覆盖是拆分基线，但不足以保护 Service、分页边界、错误参数和前端资源。

## 4. 必须冻结的兼容契约

### 4.1 数据库契约

本次不得修改：

- 表：`token_usage`、`writing_activity_events`；
- 已有字段含义与 nullability；
- 已有索引名；
- `DASHBOARD_MIGRATION_VERSION = 4`；
- schema migration 的幂等行为；
- 历史章节只生成一次 `operation='backfill'` 事件；
- `word_delta = new_word_count - old_word_count`；
- 写作来源仅允许 `user`、`agent`、`import`。

### 4.2 HTTP 路径

必须保持：

```text
GET /api/dashboard/writing
GET /api/dashboard/llm-api/stats
GET /api/dashboard/llm-api/records
GET /api/token/statistics
GET /api/usage
```

`/api/usage` 暂时仍属于运行时 Gateway 状态，不强行归入数据库 AnalyticsService；只在未来 Settings/Runtime 模块拆分时迁移。

### 4.3 查询参数

写作统计：

```text
project_id, source, start_at, end_at, timezone
```

LLM 统计：

```text
project_id, model_provider, model_id, category, operation,
status, start_at, end_at
```

调用记录在上述参数外还包括：

```text
search, page, page_size, sort_by, sort_order
```

约束必须保持：

- `page >= 1`；
- `5 <= page_size <= 100`；
- `sort_order` 仅为 `asc` 或 `desc`；
- `sort_by` 白名单为 `created_at`、`tokens_input`、`tokens_output`、`tokens_total`、`latency_ms`、`first_token_ms`、`retry_count`；
- 搜索中的反斜线、`%` 和 `_` 必须正确转义；
- 结束时间不能早于开始时间；
- 非法时区、来源、日期、页码和排序字段继续返回 400。

### 4.4 JSON 返回结构

以下顶层键必须冻结：

```text
writing: summary, time_series
llm stats: summary, model_time_series, by_model, by_project, options
records: options, records
records.records: items, total, page, page_size
```

不要在结构迁移中把 snake_case 改为 camelCase，也不要把数值改成已格式化字符串。格式化属于前端职责。

### 4.5 前端 DOM 和行为

第一轮迁移应保留现有：

- `analyticsView`、三个 Tab/Panel 和所有 chart host 的 ID；
- CSS class 名称；
- 默认 Tab 为 `writing`；
- 默认写作时间范围；
- 浏览器本地时区；
- 搜索 300ms 防抖；
- 进入页面时懒加载当前 Tab；
- 离开页面时取消请求；
- 键盘左右方向键切换 Tab；
- loading、empty、error、retry 状态；
- 记录默认按 `created_at desc`、每页 20 条。

## 5. 目标目录结构

本模块完成后的目录建议如下：

```text
novel_agent/
├── features/
│   └── analytics/
│       ├── __init__.py
│       ├── errors.py
│       ├── models.py
│       ├── ports.py
│       └── service.py
├── infrastructure/
│   └── persistence/
│       ├── database.py
│       ├── analytics_store.py
│       └── migrations/
│           ├── __init__.py
│           └── analytics_v4.py
├── interfaces/
│   └── http/
│       └── routes/
│           ├── __init__.py
│           └── analytics.py
├── telemetry.py                       # 本阶段保留兼容导入
├── repository.py                      # 保留薄 Facade
├── service.py                         # 保留旧 Service 委托
└── api.py                             # 只保留 Analytics 分发接线

apps/web/
├── index.html
├── app.js
├── js/
│   ├── core/
│   │   ├── date.js
│   │   ├── dom.js
│   │   └── format.js
│   ├── ui/
│   │   └── charts/
│   │       ├── runtime.js
│   │       ├── line-chart.js
│   │       ├── bar-chart.js
│   │       ├── donut-chart.js
│   │       └── year-heatmap.js
│   └── features/
│       └── analytics/
│           ├── api.js
│           ├── labels.js
│           ├── selectors.js
│           ├── state.js
│           ├── template.js
│           ├── writing.js
│           ├── llm.js
│           ├── records.js
│           ├── view.js
│           └── index.js
└── styles/
    └── features/
        └── analytics.css

tests/
├── analytics/
│   ├── __init__.py
│   ├── test_migration.py
│   ├── test_store.py
│   ├── test_service.py
│   ├── test_routes.py
│   └── test_compatibility.py
└── test_web_analytics_assets.py
```

说明：本项目暂不引入打包器。所有前端 import 使用浏览器原生 ES Modules 和从 `/js/...` 开始的绝对路径。

## 6. 后端职责设计

### 6.1 `features/analytics/models.py`

只保存与 Analytics 业务有关的查询和值对象，不导入 SQLite、HTTP Handler 或 Web 类型。

建议模型：

```python
@dataclass(frozen=True, slots=True)
class DateRange:
    start_at: str | None = None
    end_at: str | None = None

@dataclass(frozen=True, slots=True)
class WritingDashboardQuery:
    project_id: str | None = None
    source: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    timezone_name: str = "UTC"

@dataclass(frozen=True, slots=True)
class LLMStatsQuery:
    project_id: str | None = None
    model_provider: str | None = None
    model_id: str | None = None
    category: str | None = None
    operation: str | None = None
    status: str | None = None
    start_at: str | None = None
    end_at: str | None = None

@dataclass(frozen=True, slots=True)
class LLMRecordsQuery(LLMStatsQuery):
    search: str | None = None
    page: int = 1
    page_size: int = 20
    sort_by: str = "created_at"
    sort_order: str = "desc"
```

Query 模型负责跨入口一致的值约束；HTTP 字符串到类型的转换仍由 route 层完成。返回结构第一阶段可继续使用 `dict[str, Any]`，避免一次性把所有响应改成 Pydantic 后引入序列化差异。待兼容测试稳定后，再单独引入响应 DTO。

### 6.2 `features/analytics/errors.py`

定义：

```python
class AnalyticsError(RuntimeError): ...
class AnalyticsValidationError(AnalyticsError, ValueError): ...
```

规则：

- 非法筛选、日期、时区、分页、排序抛 `AnalyticsValidationError`；
- API 映射为现有 `BAD_REQUEST` / 400；
- 数据库 I/O 错误不要包装成 400，应继续作为服务器错误；
- 兼容 Facade 可按需把 `AnalyticsValidationError` 映射为 `RepositoryError`，但新 Service 和 Route 只依赖 Analytics error。

### 6.3 `features/analytics/ports.py`

定义最小能力，不暴露 SQLite：

```python
class AnalyticsRecorder(Protocol):
    def save_token_usage(..., **extra: Any) -> None: ...
    def record_llm_call(self, record: LLMCallRecord) -> None: ...
    def record_writing_activity(..., conn: Any | None = None) -> None: ...

class AnalyticsQueryStore(Protocol):
    def get_token_statistics(self, start_date: str, end_date: str) -> dict[str, Any]: ...
    def get_token_daily_summary(self, start_date: str, end_date: str) -> dict[str, Any]: ...
    def get_writing_dashboard(self, query: WritingDashboardQuery) -> dict[str, Any]: ...
    def get_llm_dashboard_stats(self, query: LLMStatsQuery) -> dict[str, Any]: ...
    def list_llm_call_records(self, query: LLMRecordsQuery) -> dict[str, Any]: ...
```

推荐让 `SQLiteAnalyticsStore` 同时实现这两个 Protocol，但消费方只注入自己需要的窄接口。

### 6.4 `infrastructure/persistence/database.py`

Pilot 阶段不要强制迁移所有 Repository 连接代码。先定义结构化 Protocol：

```python
class DatabaseSessionProvider(Protocol):
    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]: ...

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]: ...
```

现有 `SQLiteRepository` 已经结构上符合此接口，因此 `SQLiteAnalyticsStore` 可以接收它作为 session provider，而不需要导入 `SQLiteRepository`。未来抽取完整 `SQLiteDatabase` 时可无缝替换。

禁止 `analytics_store.py` 写出：

```python
from novel_agent.repository import SQLiteRepository
```

否则只是把 SQL 搬了文件，依赖方向没有改善。

### 6.5 `infrastructure/persistence/analytics_store.py`

负责：

- 保存 LLM 调用与写作活动事件；
- 查询 Token 日统计；
- 创建安全 SQL filter；
- 执行写作和 LLM 聚合查询；
- 将 sqlite row 转为当前 JSON 所需的基本字典。

不负责：

- HTTP 查询字符串；
- 页面中文标签；
- “今日”“日均”“峰值日”等应用层组合；
- 全局 Repository 其他表的 CRUD；
- 调用 LLM 或章节 Service。

构造方式：

```python
class SQLiteAnalyticsStore:
    def __init__(self, database: DatabaseSessionProvider):
        self._database = database
```

现有方法迁移映射：

| 原方法 | 目标方法 | 备注 |
|---|---|---|
| `save_token_usage` | 同名 | 保留 Gateway callback 签名 |
| `record_llm_call` | 同名 | 保留 `LLMCallRecord` |
| `record_writing_activity` | 同名 | 必须保留可选 `conn` |
| `get_token_statistics` | 同名 | 保持使用 `date` 字段 |
| `get_token_daily_summary` | 同名 | 保持 distinct date 语义 |
| `_parse_timezone` | `_parse_timezone` | 私有 helper |
| `_parse_iso_datetime` | `_parse_iso_datetime` | 私有 helper |
| `_local_date` | `_local_date` | 私有 helper |
| `get_writing_dashboard` | 同名 | 参数改为 query object |
| `get_dashboard_filter_options` | 同名私有/公开均可 | 第一阶段保持返回结构 |
| `_token_usage_filters` | `_build_token_usage_filter` | 返回 SQL fragment + bind params |
| `get_llm_dashboard_stats` | 同名 | 参数改为 query object |
| `list_llm_call_records` | 同名 | 参数改为 query object |

SQL 安全要求：

- 所有用户值必须继续使用 `?` bind parameter；
- 只有排序字段可以从白名单映射成 SQL identifier；
- 禁止直接拼接 `sort_by`、`sort_order`、alias 或搜索值；
- alias 由代码内部常量传入，不接受 HTTP 输入；
- `LIKE ... ESCAPE '\\'` 行为必须有回归测试；
- 所有 int/float/null 映射保持现状。

### 6.6 `infrastructure/persistence/migrations/analytics_v4.py`

迁移模块公开一个窄函数：

```python
def apply_analytics_v4(conn: sqlite3.Connection) -> None:
    ...
```

该函数负责：

- Analytics 表、列和索引的 v4 变更；
- 只在 migration 4 未应用时执行历史写作事件回填；
- 写入 `schema_migrations(version=4)`。

主 `SQLiteRepository.migrate()` 暂时仍是 migration orchestrator，只调用该函数。不要在 Pilot 中设计一个全新迁移框架。

必须验证：

- 新数据库首次启动正常；
- 已有 v3 数据库升级正常；
- 已有 v4/v5 数据库重复启动不重复回填；
- v5 Reader 表不受影响。

### 6.7 `features/analytics/service.py`

`AnalyticsService` 是新模块的唯一应用层入口：

```python
class AnalyticsService:
    def __init__(self, store: AnalyticsQueryStore, *, today: Callable[[], date] = date.today): ...

    def get_token_statistics(self, start_date: str, end_date: str) -> dict[str, Any]: ...
    def get_writing_dashboard(self, query: WritingDashboardQuery) -> dict[str, Any]: ...
    def get_llm_dashboard_stats(self, query: LLMStatsQuery) -> dict[str, Any]: ...
    def list_llm_call_records(self, query: LLMRecordsQuery) -> dict[str, Any]: ...
```

职责分配：

- `get_token_statistics` 接管当前 `NovelAgentService.get_token_statistics` 的今日、周期、日均和峰值组合逻辑；
- 其他三个方法统一验证 query 后委托 Store；
- `today` 使用可注入 clock，避免测试依赖系统日期；
- Service 不知道 `BaseHTTPRequestHandler`、`sqlite3.Connection` 或 DOM。

注意：`get_usage()` 仍留在 `NovelAgentService`，因为它读取 Gateway 的即时内存状态，不是 SQLite 统计。

### 6.8 兼容 Facade

为了让现有测试和内部调用能够逐步迁移，`SQLiteRepository` 暂时保留原方法名，但方法体只能委托：

```python
class SQLiteRepository(...):
    def __init__(self, path: Path):
        ...
        self.analytics = SQLiteAnalyticsStore(self)

    def record_writing_activity(self, **kwargs: Any) -> None:
        self.analytics.record_writing_activity(**kwargs)

    def get_llm_dashboard_stats(self, **kwargs: Any) -> dict[str, Any]:
        return self.analytics.get_llm_dashboard_stats(LLMStatsQuery(**kwargs))
```

要求：

- Facade 中不得复制 SQL；
- Facade 中不得重新实现参数校验；
- `revision_store.py` 现有 `self.record_writing_activity(...)` 在 Revision 模块拆分前继续可用；
- 新代码一律注入 `AnalyticsService` 或 `AnalyticsRecorder`，不得调用 Repository 的 Dashboard Facade；
- 等所有调用点迁移后，再在单独 breaking cleanup 中讨论移除旧方法。

## 7. HTTP 拆分设计

### 7.1 路由模块

`interfaces/http/routes/analytics.py` 不引入新 Web 框架。建议公开：

```python
@dataclass(frozen=True, slots=True)
class RouteResult:
    payload: Any
    status: HTTPStatus = HTTPStatus.OK

def dispatch_analytics_get(
    path: str,
    params: Mapping[str, str],
    service: AnalyticsService,
) -> RouteResult | None:
    ...
```

行为：

- 匹配到 Analytics 路径就返回 `RouteResult`；
- 不属于本模块返回 `None`，交还主 Handler；
- route 层只进行字符串解析和 query model 构造；
- route 不接触 Repository；
- `page`、`page_size` 的空值使用默认值；非法整数抛 `AnalyticsValidationError` 或 ValueError；
- Query 参数解析使用 `urllib.parse.urlsplit` + `parse_qs`，不要继续手工按 `&` 和 `=` 切分，避免编码问题；
- 重复参数第一阶段沿用“取一个值”的行为，文档化后再决定是否拒绝。

### 7.2 `api.py` 接线

`NovelAgentHandler.do_GET()` 中只保留：

```python
params = self._query_params()
result = dispatch_analytics_get(path, params, self.context.analytics)
if result is not None:
    self._send_json(result.payload, result.status)
    return
```

随后删除 Handler 内的：

- `_dashboard_writing`；
- `_dashboard_llm_stats`；
- `_dashboard_llm_records`；
- `/api/token/statistics` 的内联分支。

主错误映射增加 `AnalyticsValidationError -> 400 BAD_REQUEST`。不要捕获所有 `AnalyticsError` 并一律返回 400，因为数据库故障应为 500。

### 7.3 `AppContext` 与 bootstrap

为兼容现有 `AppContext(settings, service, repository, web_root)` 的四位置参数构造，新增字段放在最后：

```python
@dataclass(slots=True)
class AppContext:
    settings: Settings
    service: NovelAgentService
    repository: SQLiteRepository
    web_root: Path
    analytics: AnalyticsService | None = None

    def __post_init__(self) -> None:
        if self.analytics is None:
            self.analytics = AnalyticsService(self.repository.analytics)
```

bootstrap 显式装配：

```python
repository = SQLiteRepository(settings.database_path)
analytics_store = repository.analytics
analytics_service = AnalyticsService(analytics_store)

# 暂时保留 Provider 的现有 callback 接口，但不再绑定 Repository facade。
gateway._on_call = analytics_store.save_token_usage

return AppContext(
    settings,
    service,
    repository,
    web_root,
    analytics=analytics_service,
)
```

本阶段不要同时重构 `_on_call/_on_usage` 私有字段。后续 Adapter 阶段再引入正式 `set_usage_recorder()` 或构造参数。

## 8. 前端模块详细设计

### 8.1 启动和兼容策略

不把整个应用一次性改成 ES Module。由现有 `app.js` 动态加载 Analytics：

```javascript
let analyticsView = null;

async function startApp() {
  try {
    const { createAnalyticsView } = await import("/js/features/analytics/index.js");
    analyticsView = createAnalyticsView({ api, notify });
    analyticsView.mount(document.querySelector("#analyticsView"));
  } catch (error) {
    console.error("仪表盘初始化失败", error);
  }
  // Reader 与主应用继续原流程
}
```

`switchView()` 改为调用局部 `analyticsView?.activate()` / `deactivate()`，不再依赖 `window.NovelDashboard`。

拆分提交期间如需要兼容旧调用，可在 `index.js` 临时赋值：

```javascript
window.NovelDashboard = analyticsView;
```

但最终提交必须移除该全局。不要永久保留“两套入口”。

### 8.2 `template.js`

`index.html` 最终只保留：

```html
<section id="analyticsView" class="view analytics-view" aria-labelledby="analyticsTitle"></section>
```

`template.js` 提供 `mountAnalyticsTemplate(host)`，迁移当前 `index.html` 第 194–309 行附近的静态内容。模板中没有用户输入，可使用固定模板字符串；所有运行时数据仍必须通过 `textContent` 或显式 `escapeHtml` 写入。

挂载要求：

- 重复调用 mount 不应重复插入 DOM；
- mount 后再 bind events；
- `destroy()` 时仅清理监听器和图表资源，不应误删整个应用 DOM；
- 所有现有 ID、ARIA role、`aria-selected`、`aria-controls` 和 `tabindex` 保持不变。

### 8.3 `state.js`

导出工厂，不导出可变全局单例：

```javascript
export function createAnalyticsState(now = new Date()) {
  return {
    activeTab: "writing",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    selectedYear: now.getFullYear(),
    availableYears: [],
    writingHero: null,
    writingDetail: null,
    llmStats: null,
    records: null,
    filterOptions: null,
    filters: { ... },
  };
}
```

页面状态只能由本 Feature 的 controller 修改。Chart module 接收 model，不得读取 state。

### 8.4 `api.js`

把当前 `controllers`、`requestIds`、`abortKey`、`abortAll`、`fetchJson` 和 `ensureFilterOptions` 收口到一个实例：

```javascript
export function createAnalyticsApi(request) {
  return {
    loadWriting(query),
    loadLlmStats(query),
    loadRecords(query),
    abort(scope),
    abortAll(),
  };
}
```

要求：

- URL 一律用 `URLSearchParams`；
- 空字符串参数不发送；
- 每个 scope 只有一个活动请求；发起新请求先 abort 旧请求；
- 即使底层 request 不支持 abort，也用递增 request id 丢弃过期响应；
- AbortError 不显示为用户错误；
- 真实错误交给 controller 渲染 error state；
- 筛选 options 可以缓存，但 `refresh()` 应允许失效；
- 不在该文件操作 DOM。

### 8.5 `selectors.js`

迁移纯数据函数：

- `computeYearMetrics`；
- `deriveYears`；
- `getRecentDates`；
- `getTopModels`；
- `buildModelTrend`；
- `buildTokenTrend`；
- 写作累计值、来源占比、星期分布的 model 构造。

所有函数满足：

- 输入相同则输出相同；
- 不读 DOM、window、state；
- 不修改输入数组；
- 对空数组和 null 返回稳定空模型；
- 不做中文数字格式化。

纯 selector 是未来最容易增加 JS 单元测试的部分。

### 8.6 图表层

`ui/charts/runtime.js`：

- tooltip 创建、显示、隐藏；
- ResizeObserver；
- 每个 container 的 cleanup；
- loading/error/empty/retry 状态；
- `destroyChart(container)` 和 `destroyAll()`。

四类图表各自只导出一个 render：

```javascript
renderLineChart(container, model, runtime)
renderBarChart(container, model, runtime)
renderDonutChart(container, model, runtime)
renderYearHeatmap(container, model, runtime)
```

图表约束：

- 不发 API；
- 不知道 Analytics Tab；
- 不直接访问全局 state；
- 每次 render 前清理旧 observer 和事件；
- container 不可见或宽度为 0 时可以延迟重绘；
- SVG 中用户可控 label 必须转义或用 DOM API；
- 保留现有 CSS class，确保视觉不变；
- `deactivate()` 必须清理 ResizeObserver 和 tooltip，防止重复进入页面后累积监听器。

### 8.7 `writing.js`

负责：

- 写作 Hero 年份和热力图；
- 年度指标；
- 写作项目、开始日期和结束日期；
- 四张写作图表；
- 写作筛选重置；
- Hero 全量年份请求与 Detail 时间段请求的独立 loading/error 状态。

建议接口：

```javascript
createWritingController({ state, api, charts, root, notify })
// 返回 loadHero, loadDetail, bind, refresh, destroy
```

注意当前页面存在 `writingHero` 和 `writingDetail` 两个并行请求，不能合并成一个 AbortController，否则筛选详情时可能误取消年度热力图请求。

### 8.8 `llm.js`

负责：

- LLM 四个指标卡；
- 调用趋势；
- 模型调用次数分布；
- 模型 Token 分布；
- Token 消耗趋势；
- 响应时间趋势；
- 项目 Token 分布；
- 空数据和部分 `avg_first_token_ms = null` 的显示。

当前 LLM Tab 没有独立筛选 UI，但 API 已支持筛选。拆分时不要擅自添加筛选控件；新增 UI 应另开功能任务。

### 8.9 `records.js`

负责：

- 筛选 options 渲染；
- 搜索 300ms debounce；
- query 构造；
- 表格安全渲染；
- 排序状态和指示器；
- 页码计算和按钮事件；
- 重置筛选；
- 销毁 timer 和监听器。

特别要求：

- 切换任何筛选和排序时页码重置为 1；
- 总数减少导致当前页越界时，回到最后有效页并只重试一次；
- 错误信息只作纯文本展示，禁止直接拼入未转义 HTML；
- `project_title` 为空时保留现有兜底文案；
- 表格排序字段必须与后端白名单一致；
- pagination 按钮禁用和当前页语义保持不变。

### 8.10 `view.js` 与 `index.js`

`view.js` 只负责页面编排：

```javascript
export function createAnalyticsView(deps) {
  return {
    mount(host),
    activate(),
    deactivate(),
    refresh(),
    destroy(),
  };
}
```

生命周期定义：

- `mount`：挂模板、创建 state/api/controllers、绑定一次事件；
- `activate`：标记 active，只加载当前 Tab；
- `deactivate`：取消请求、隐藏 tooltip、停止 resize 资源，但保留筛选和已加载数据；
- `refresh`：仅页面 active 时刷新当前 Tab；
- `destroy`：取消请求、timer、observer 和所有事件，实例不可继续使用。

Tab 编排保留 WAI-ARIA 键盘行为。`index.js` 只 re-export `createAnalyticsView`，不要放业务代码。

### 8.11 CSS

当前已有独立 `apps/web/dashboard.css`，说明样式边界已经基本形成。本阶段只做机械移动：

```text
apps/web/dashboard.css
→ apps/web/styles/features/analytics.css
```

然后更新 `index.html` link。不要在同一提交中改颜色、间距、断点或 class 名。

同时审计 `styles.css` 中是否仍有 `.analytics-*`、`.chart-*`、`.records-*` 重叠规则；如有，按原 cascade 顺序搬入 Analytics CSS，并用视觉回归确认。Settings 页的 `.usage-*` 仍属于 Settings，不要因为都展示 Token 就一起迁移。

## 9. 分阶段执行顺序

每一阶段都应形成独立、可回滚的提交。不得先删除旧实现再补新实现。

### 阶段 0：冻结基线

1. `git status --short`，记录用户已有修改；
2. 不 reset、不覆盖当前阅读工作台相关改动；
3. 运行全量测试并保存结果；
4. 记录三个 Dashboard API 和 `/api/token/statistics` 的典型 JSON fixture；
5. 使用当前页面截图记录三个 Tab 的桌面和窄屏状态；
6. 建立 `tests/analytics/`，先复制/移动测试，不改实现。

验收：移动测试后仍全部通过；fixture 可用于拆分前后对比。

### 阶段 1：抽取 Analytics Store 和 migration

1. 添加 `features/analytics/models.py`、`ports.py`、`errors.py`；
2. 添加 `DatabaseSessionProvider`；
3. 把 Analytics SQL 迁入 `SQLiteAnalyticsStore`；
4. 把 v4 migration/backfill 迁入 `analytics_v4.py`；
5. `SQLiteRepository` 在 migrate 后创建 `self.analytics`；
6. 原 Repository 方法改为一行委托；
7. 保证 `record_writing_activity(conn=...)` 原子事务测试通过；
8. bootstrap 的 Gateway callback 改绑 `repository.analytics.save_token_usage`。

此阶段不改 HTTP 和前端。

验收：现有 `test_repository.py`、`test_dashboard.py` 和全量测试通过；Repository Analytics Facade 无 SQL。

建议提交：

```text
refactor(analytics): extract sqlite analytics store
```

### 阶段 2：建立 AnalyticsService

1. 新建 `AnalyticsService`；
2. 迁移 `NovelAgentService.get_token_statistics` 逻辑；
3. 新增 fake store 单元测试；
4. `NovelAgentService.get_token_statistics` 暂时委托新 Service，保持旧调用；
5. 验证可注入 today clock；
6. 验证 Service 不导入 Repository、sqlite3、api。

验收：业务组合逻辑只存在一份。

建议提交：

```text
refactor(analytics): add analytics application service
```

### 阶段 3：提取 HTTP Routes

1. 新建 `interfaces/http/routes/analytics.py`；
2. 迁移四个数据库统计 GET 路由；
3. 扩展 `AppContext.analytics`，保留四参数兼容构造；
4. bootstrap 显式装配 Service；
5. 删除 Handler 三个 `_dashboard_*` 私有方法；
6. 增加查询参数和错误矩阵测试；
7. 确认 route 不直接访问 `context.repository`。

验收：所有路径和 JSON fixture 与基线相同，非法参数仍为 400。

建议提交：

```text
refactor(api): route dashboard requests through analytics service
```

### 阶段 4：抽取无状态前端基础

1. 创建 `core/date.js`、`core/format.js`；
2. 创建 chart runtime 和四类 chart；
3. 创建 selectors；
4. 暂时由旧 `dashboard.js` import 新模块，页面 controller 尚不拆；
5. 对比三个 Tab 的截图和响应式布局；
6. 确认重复切换 Tab 后 observer、tooltip 和 listener 数量不增长。

验收：视觉和交互不变，`dashboard.js` 已不包含通用 chart 实现。

建议提交：

```text
refactor(web): extract dashboard chart primitives
```

### 阶段 5：拆分 Feature controllers

1. 添加 state、api、writing、llm、records、view；
2. 把旧 IIFE 状态变为实例状态；
3. 将 `window.NovelDashboard` 替换为 `analyticsView` 模块实例；
4. `app.js` 用动态 import 加载模块；
5. 删除旧 `dashboard.js` 或把它缩成一次性兼容入口；
6. 确认任一子 controller 的失败不会阻断主应用启动。

验收：三 Tab、筛选、搜索、排序、分页、Abort 和刷新全部正常。

建议提交：

```text
refactor(web): split analytics feature controllers
```

### 阶段 6：迁移模板与 CSS

1. 把 Analytics DOM 迁入 `template.js`；
2. `index.html` 只保留挂载点；
3. 移动 `dashboard.css`；
4. 清理 `styles.css` 中 Analytics 重复规则；
5. 删除 `index.html` 中旧 `dashboard.js` script；
6. 更新静态资源路径测试。

验收：DOM ID、ARIA、样式 cascade 和所有断点无回归。

建议提交：

```text
refactor(web): move analytics template and styles into feature
```

### 阶段 7：兼容收尾与文档

1. 全仓 `rg` 搜索旧 Analytics Repository 调用；
2. 确认新业务代码只依赖 Service/Ports；
3. 保留被现有代码和测试使用的 Facade，并标注迁移期用途；
4. 更新 `docs/ARCHITECTURE.md` 与 README 目录；
5. 只有用户操作发生变化时才更新 `docs/USER_GUIDE.md`；纯结构重构无需修改用户指南；
6. 运行全量测试和手工前端回归。

建议提交：

```text
docs(architecture): document analytics module boundary
```

## 10. 测试计划

### 10.1 Store 测试

至少覆盖：

- 新库建表、索引和 migration version；
- v4 回填只执行一次；
- 空正文不回填；
- 写作 source 白名单；
- 正、负、零 word delta；
- 外部 `conn` 中写作事件与正文变更共同 commit；
- 外部事务 rollback 时事件也 rollback；
- UTC 到 Asia/Shanghai 跨日；
- 非法时区和非法日期；
- start/end 反转；
- LLM 成功、失败、null latency、null first token；
- filter 的每个字段；
- 搜索 `%`、`_`、反斜线；
- sort 白名单、asc/desc、稳定的 id tie-break；
- page 1、最后一页、空页、非法 page/page_size；
- 无项目记录显示“未归属项目”；
- filter options 不丢 writing-only 项目。

### 10.2 Service 测试

用 fake store，不创建 SQLite：

- query 原样委托；
- 旧 Token 统计组合结构；
- 今日 Token；
- 峰值日期和峰值数；
- 无数据时 max/avg；
- distinct days 对日均的影响；
- today clock 可控；
- Store 异常不被错误吞掉或误映射。

### 10.3 Route 测试

至少覆盖：

- 四个路径成功；
- 未匹配路径返回 `None`；
- URL 编码搜索字符串；
- page/page_size 缺省；
- page/page_size 非整数；
- 非法日期、时区、source、sort；
- Service 被调用一次且获得正确 query object；
- route 不访问 Repository；
- AnalyticsValidationError 最终 HTTP 400；
- 未知异常最终 HTTP 500。

### 10.4 兼容测试

保留以下旧调用：

```python
repository.save_token_usage(...)
repository.record_llm_call(...)
repository.record_writing_activity(...)
repository.get_token_statistics(...)
repository.get_token_daily_summary(...)
repository.get_writing_dashboard(...)
repository.get_llm_dashboard_stats(...)
repository.list_llm_call_records(...)
service.get_token_statistics(...)
AppContext(settings, service, repository, web_root)
```

兼容测试不仅验证方法存在，还要验证返回等于新实现结果，避免 Facade 漂移。

### 10.5 前端自动检查

在不引入 npm 的前提下，至少增加 Python 静态资源测试：

- `index.html` 引用的本地 JS/CSS 都存在；
- Analytics 挂载点只出现一次；
- 已删除的 `/dashboard.js` 不再被引用；
- ES module 路径都位于 web root 内；
- 服务请求缺失 JS/CSS 时不应回退成 `index.html`；
- Analytics 模板包含关键 ID 和 ARIA 属性。

如果项目已有可用 Node，再补纯 selector 的 `node:test`；不要为了本次拆分引入完整 npm toolchain。

### 10.6 手工回归矩阵

桌面宽度：1440、1024。移动/窄屏：768、414、375、320。

逐项检查：

1. 从其他页面进入仪表盘，默认打开“写作”；
2. 年份选择、热力图 tooltip、年度指标正确；
3. 写作项目与日期筛选、重置正确；
4. 四张写作图表 empty/loading/error/retry 正确；
5. LLM 指标卡及六张图正确；
6. 无首字时间时显示当前兜底文案；
7. 调用记录五个下拉、日期、搜索、重置正确；
8. 搜索快速输入只应用最后一次结果；
9. 排序重复点击在升序/降序切换；
10. 前后分页和范围文字正确；
11. 快速切 Tab、离开页面、再返回不会闪回旧请求；
12. 浏览器缩放和窗口 resize 后图表不重叠；
13. 键盘左右键、Tab、Enter 可操作；
14. 控制台无重复监听、AbortError 或 404/MIME 错误；
15. Settings 的 Token 用量图仍正常。

### 10.7 每阶段命令

```powershell
python -m unittest tests.analytics.test_migration -v
python -m unittest tests.analytics.test_store -v
python -m unittest tests.analytics.test_service -v
python -m unittest tests.analytics.test_routes -v
python -m unittest tests.analytics.test_compatibility -v
python -m unittest discover -s tests -v
git diff --check
```

如果 Ruff 已安装再执行：

```powershell
python -m ruff check novel_agent tests
```

当前环境未安装 Ruff 时应明确记录“未执行”，不能写成“静态检查通过”。

## 11. Cursor 逐阶段执行模板

每个阶段给 Cursor 的任务都应包含以下固定要求：

```text
1. 先阅读本阶段涉及的当前文件和测试，不覆盖工作区其他改动。
2. 本次只完成一个阶段，不提前进行后续清理。
3. 新实现先加入，兼容测试通过后再删除旧实现。
4. 不改变 API 路径、JSON、数据库 schema、文案、DOM ID 和视觉。
5. 不引入新框架或构建工具。
6. 运行本阶段测试和完整 unittest；报告未运行的检查。
7. 输出：改动文件、依赖变化、测试结果、遗留 Facade、风险和回滚点。
8. 用户可见功能没有变化时，不修改 docs/USER_GUIDE.md；若实际行为变化，必须同步更新。
```

### 阶段 1 可直接复制的 Cursor 指令

```text
请根据 docs/ANALYTICS_DASHBOARD_SPLIT_PLAN.md 的阶段 1 执行 Analytics Store 拆分。
只提取数据库 Analytics 代码和 v4 migration，不修改 HTTP、前端、API 返回或数据库结构。
使用 DatabaseSessionProvider 隔离具体 SQLiteRepository，禁止 analytics_store.py 导入 repository.py。
保留 SQLiteRepository 的同名兼容方法，方法体只做委托。
特别保护 record_writing_activity(conn=...) 的同事务能力，并增加 commit/rollback 测试。
先运行现有 Dashboard/Repository 测试，再运行完整 unittest。
```

### 阶段 2–3 可直接复制的 Cursor 指令

```text
请根据 docs/ANALYTICS_DASHBOARD_SPLIT_PLAN.md 的阶段 2 和阶段 3，建立 AnalyticsService 并提取 Analytics GET routes。
所有 Dashboard 路由必须只调用 AnalyticsService，不得访问 context.repository。
保持 AppContext 四位置参数兼容、现有 HTTP 路径、查询参数、错误码和 JSON 字段完全不变。
使用 urlsplit/parse_qs 解析查询参数，为非法整数、日期、时区、来源和排序增加 route 测试。
不修改前端。
```

### 阶段 4–6 可直接复制的 Cursor 指令

```text
请根据 docs/ANALYTICS_DASHBOARD_SPLIT_PLAN.md 的阶段 4–6 拆分前端 Analytics。
使用原生 ES Modules，不引入 npm 或 UI 框架。
先提取纯 selector 和 chart primitives，再拆 writing/llm/records controllers，最后迁移 template/CSS。
保持现有 DOM ID、class、ARIA、中文文案、图表样式、筛选、排序、分页、300ms 搜索防抖和请求取消行为。
用 app.js 动态 import 创建 analyticsView 实例，最终移除 window.NovelDashboard。
完成后执行静态资源检查和文档中的全部手工回归矩阵。
```

## 12. 风险与保护措施

### 12.1 事务被拆断

风险：章节正文已提交，但写作事件写入失败或反之。

保护：`record_writing_activity` 必须接受调用者传入的 connection；增加 commit/rollback 集成测试；不得在传入 conn 时自行开启 transaction。

### 12.2 API 返回轻微漂移导致图表失效

风险：字段从 null 变 0、key 改名、排序顺序变化，前端无明显错误但图表含义变化。

保护：保存拆分前 JSON fixture，逐字段深比较；响应 DTO 后置。

### 12.3 时区语义变化

风险：写作统计按本地日聚合，而 LLM 趋势目前按 UTC `created_at` 日期截断；统一它们会改变既有数据。

保护：本次保持现状并在代码注释标明差异；“统一统计时区”另开产品任务。

### 12.4 Windows ZoneInfo fallback

风险：缺少系统 tzdata 时，当前部分时区使用固定 offset，对夏令时不准确。

保护：结构重构不顺手修复；保留测试基线。未来单独引入 tzdata 或限制支持时区。

### 12.5 前端模块加载竞态

风险：classic `app.js` 在 module 挂载前激活 Analytics，导致空 DOM 或重复事件。

保护：由 `startApp()` await 动态 import 和 mount，再启动导航；mount 必须幂等；加载失败时主应用仍能启动并显示明确错误。

### 12.6 Observer 与监听器泄漏

风险：多次切 Tab/页面后图表重复渲染和性能下降。

保护：所有 listener 返回 disposer；chart runtime 使用 WeakMap；deactivate 清临时资源，destroy 清全部资源。

### 12.7 静态资源错误被 SPA fallback 掩盖

风险：模块路径拼错时服务器返回 200 的 `index.html`，浏览器报难理解的 MIME/语法错误。

保护：静态服务器对 `.js`、`.css`、图片等缺失资源必须返回 404，只有页面导航回退 `index.html`；增加 API/静态资源测试。

### 12.8 工作区已有改动被覆盖

风险：当前 Reader、样式、用户指南存在其他任务改动。

保护：每阶段先看 `git status --short`；只 patch 本阶段文件；发生重叠时先检查 diff；禁止 reset、checkout 覆盖或批量格式化无关文件。

## 13. 性能改进的后续清单

以下问题已观察到，但不应混入结构拆分：

- LLM stats 和 records 每次都重新查询完整 filter options；
- `get_writing_dashboard` 在 Python 中按日聚合全部命中事件；
- 长期数据下调用记录 count + page 查询可能需要组合索引；
- 模型趋势没有服务端粒度降采样；
- 前端 SVG 在超长日期范围下节点数可能过多；
- filter options 暂无 TTL/版本失效策略。

完成模块拆分并建立基准后，再单独做性能任务。任何缓存都必须定义失效时机，不能让新调用记录长期不可见。

## 14. Definition of Done

只有同时满足以下条件，Analytics / Dashboard 才算完成拆分：

- Analytics SQL 只存在于 `analytics_store.py` 和 migration 文件；
- `repository.py` 的 Analytics 方法只做兼容委托，不包含 SQL 或重复业务逻辑；
- 写入侧存在窄 `AnalyticsRecorder`，章节/修订不依赖 Dashboard 查询；
- `AnalyticsService` 是数据库统计的唯一应用层入口；
- Dashboard routes 不直接访问 Repository；
- `api.py` 不再包含 `_dashboard_writing`、`_dashboard_llm_stats`、`_dashboard_llm_records`；
- 原有 HTTP 路径、参数、状态码和 JSON fixture 保持一致；
- Gateway callback 已绑定 Analytics recorder/store，而不是 Repository 查询 Facade；
- `record_writing_activity(conn=...)` 的 commit/rollback 原子性有测试；
- `dashboard.js` 的 API、状态、业务 controller 和图表实现已拆开；
- Dashboard 不再通过 `window.NovelDashboard` 与主应用通信；
- Analytics 模板和样式位于自己的 feature 目录；
- 所有请求可以取消，过期响应不会覆盖新状态；
- 图表 observer、tooltip、timer 和事件可正确清理；
- 现有 64 个基线测试继续通过，并新增 Store、Service、Route、兼容和资源测试；
- 三个 Tab 在 320–1440px 回归通过；
- README/ARCHITECTURE 已反映真实目录；
- 没有用户可见变化时不改用户指南；如果实施中出现用户可见变化，已同步更新 `docs/USER_GUIDE.md`；
- 当前工作区其他功能改动未被覆盖或混入提交。

## 15. 建议从哪里开始

实际执行时先只做“阶段 0 + 阶段 1”：

```text
冻结接口 fixture
→ 抽取 SQLiteAnalyticsStore
→ 保留 Repository Facade
→ 保护跨表事务
→ 跑完整回归
```

不要一开始同时拆后端和前端。Store 是整个模块的稳定底座；它通过测试后，再进入 Service/Route，最后才处理前端。这样每一步失败都可以在本层回滚，不会出现 SQL、HTTP 和页面同时处于半迁移状态。
