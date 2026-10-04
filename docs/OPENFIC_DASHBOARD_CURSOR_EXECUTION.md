# NovelAI 仪表盘改造：Cursor 前后端任务执行书

> **注意（2026-10-02）**：仪表盘业务能力仍有效，但前端已迁移为 Vue 3。页面实现位于 `apps/web/src/features/analytics/`，勿再按原生 `js/features/analytics` 路径开发。总体入口与书架流程以 [`docs/NOVEL_LIBRARY_VUE3_CURSOR_EXECUTION.md`](NOVEL_LIBRARY_VUE3_CURSOR_EXECUTION.md) 为准。

> 目标：在 NovelAI 中实现与 OpenFic 仪表盘主内容区一致的页面结构、信息层级、交互和数据能力。
>
> 本文只是一份实施任务书。编写本文时没有修改 NovelAI 的前端、后端、数据库或用户操作流程。

## 0. 交给 Cursor 的首条指令

```text
请先完整阅读：
1. D:\实习日报\NovelAI\NovelAI\AGENTS.md
2. D:\实习日报\NovelAI\NovelAI\docs\OPENFIC_DASHBOARD_CURSOR_EXECUTION.md
3. 本文“参考源码”表中列出的 NovelAI 与 OpenFic 文件

严格按本文的阶段 0→7 顺序实施，不要跳过数据库迁移、埋点、测试、响应式或用户手册更新。

目标是在 NovelAI 原生 HTML/CSS/JavaScript + Python/SQLite 架构内，实现 OpenFic 仪表盘的三个页签：
“写作”“LLM 统计”“调用记录”。页面主内容区的布局、间距、卡片比例、筛选器、空态、表格和响应式应与 OpenFic 保持一致；不要把 OpenFic 的 React/Radix/Nivo/ECharts 代码或依赖直接复制进 NovelAI。

本任务不得删除现有“本地偏好”、运行能力状态、Token 历史数据或其他 NovelAI 功能。应把“仪表盘”和“系统设置”拆成两个入口：仪表盘复刻 OpenFic，系统设置继续承载现有偏好和运行状态。

每完成一个阶段先运行对应测试并检查 git diff。最终必须交付：变更文件清单、数据库迁移说明、API 契约、测试结果、1440/1024/390 三档截图，以及 docs/USER_GUIDE.md 的同步更新。
```

## 1. 本次需求的准确解释

### 1.1 要实现什么

以用户提供的图二、图三、图四以及 OpenFic 当前源码为准，在 NovelAI 中新增一个“仪表盘”视图：

1. 顶部标题为“仪表盘”。
2. 标题下方有三个页签：`写作`、`LLM 统计`、`调用记录`。
3. “写作”页签包含年度创作日历、四项年度指标、项目/日期筛选和四张统计图。
4. “LLM 统计”页签包含四项调用指标和六张统计图。
5. “调用记录”页签包含完整筛选区、可排序分页表格和空/加载/错误状态。
6. 页面使用 OpenFic 的白底、灰阶、细边线、低阴影、高信息密度风格，并在常见桌面、平板和手机宽度下可用。
7. 所有数字必须来自 NovelAI 本地 SQLite 的真实数据，不能用前端假数据或随机数据填充。

### 1.2 “一模一样”的边界

“一模一样”指仪表盘**主内容区域**的页面层次、模块顺序、比例、视觉节奏、筛选方式和状态反馈一致，不是把 OpenFic 整个应用复制到 NovelAI。

必须一致：

- 标题、三页签及其选中下划线。
- 图二的年度热力日历、右侧 2×2 指标、筛选卡片和 2×2 图表结构。
- 图三的四项 LLM 指标，以及 `4/2、2/4、4/2` 的六列图表排布。
- 图四的两行筛选器、调用记录表头、排序、分页和空态。
- 28px 桌面页边距、18px 主区块间距、14px 卡片间距、细灰边框、无常规投影的视觉语言。
- OpenFic 的 1180px 和 767px 两个关键响应式断点行为。

不在本次复制范围：

- OpenFic 的 React、Radix UI、TanStack Query、Nivo、ECharts、NumberFlow 或国际化依赖。
- OpenFic Logo、版本号、项目文案、桌面壳层和其他业务页面。
- 输入提示词、模型完整输出和工具定义的持久化展示。它们含有敏感内容，第一版调用记录只实现图四中可见的列；未来如增加详情，必须另设默认关闭的审计开关并补充安全评审。
- 深色主题。先完成并验收浅色仪表盘。

### 1.3 信息架构决定：不要覆盖现有设置功能

OpenFic 的“仪表盘”和“设置”本来就是两个入口。NovelAI 当前把 Token 统计和本地偏好混在 `系统设置` 页面。为同时满足视觉复刻与功能不丢失，应执行以下拆分：

- 新增主导航项：`仪表盘`，内部视图键建议使用 `analytics`，DOM 根节点使用 `#analyticsView`，避免与现有“创作控制台”的 `dashboard` 命名冲突。
- 保留现有 `系统设置` 导航和 `#settingsView`，只移走 Token 统计卡；运行能力状态与本地偏好表单继续留在这里。
- `仪表盘` 放在 `长期记忆` 之后；`系统设置` 仍用齿轮图标，并在桌面侧栏底部独立显示。这与 OpenFic 左栏“统计入口 + 底部设置”的结构一致。
- 不删除 `/api/settings`、`/api/usage`、`/api/token/statistics`。旧 Token 接口作为兼容接口保留，内部可复用新的统计查询。

## 2. 参考源码与事实依据

### 2.1 OpenFic：必须阅读的实现

| 用途 | 文件 |
| --- | --- |
| 页面状态、三个页签、默认 30 天范围、查询触发 | `D:\实习日报\githubClone\OpenFic\frontend\src\features\dashboard\pages\dashboard-page.tsx` |
| 页面尺寸、栅格、表格、断点 | `D:\实习日报\githubClone\OpenFic\frontend\src\features\dashboard\pages\dashboard-page.css` |
| 写作日历和四项年度指标 | `...\frontend\src\features\dashboard\components\writing-dashboard-tab.tsx` |
| LLM 四项指标和六张图 | `...\frontend\src\features\dashboard\components\llm-dashboard-tab.tsx` |
| 调用记录表格、排序、分页、空态 | `...\frontend\src\features\dashboard\components\dashboard-records-tab.tsx` |
| 三种页签对应的筛选区 | `...\frontend\src\features\dashboard\components\dashboard-filters.tsx` |
| 图表数据模型和各图表映射 | `...\frontend\src\features\dashboard\lib\dashboard-chart-options.ts` |
| 前端类型 | `...\frontend\src\features\dashboard\lib\dashboard.types.ts` |
| API 请求与 snake_case/camelCase 映射 | `...\frontend\src\features\dashboard\lib\dashboard-api.ts` |
| 后端响应模型 | `...\backend\app\api\schemas\dashboard.py` |
| 后端路由和查询参数 | `...\backend\app\api\routers\dashboard.py` |
| 调用记录数据结构 | `...\backend\app\storage\models\llm_audit_log.py` |
| 写作活动数据结构 | `...\backend\app\storage\models\writing_activity_event.py` |
| 写作聚合语义与时区处理 | `...\backend\app\storage\services\writing_activity_service.py` |
| LLM 聚合与分页查询 | `...\backend\app\storage\repos\dashboard_repo.py` |
| 后端验收用例 | `...\backend\tests\api\test_dashboard_writing.py`、`test_dashboard_llm.py` |

### 2.2 NovelAI：修改前必须阅读的实现

| 用途 | 文件 / 当前事实 |
| --- | --- |
| 静态页面和导航 | `apps/web/index.html`；当前 `#settingsView` 同时含 Token 面板和本地偏好 |
| 页面逻辑 | `apps/web/app.js`；`loadSettings()`、`renderUsage()`、日期选择器和 `saveSettings()` 位于文件后段 |
| 全局和设置页样式 | `apps/web/styles.css`；已有 OpenFic 风格令牌和 Token 柱状图样式 |
| HTTP 服务 | `novel_agent/api.py`；基于 `ThreadingHTTPServer`，不是 FastAPI |
| SQLite 表和查询 | `novel_agent/repository.py` |
| 当前模型调用埋点 | `novel_agent/adapters_remote.py` 的 `_chat()`、`_request_with_retry()`、`_log_operation()` |
| 当前埋点连接 | `novel_agent/bootstrap.py` 将 `_on_usage` 指向 `repository.save_token_usage` |
| 项目与工作流上下文 | `novel_agent/service.py`、`novel_agent/workflow.py` |
| 当前 Token 表 | `token_usage` 只有日期、operation、model、输入/输出/总 Token、重试次数和创建时间 |
| 当前兼容 API | `GET /api/token/statistics`、`GET /api/usage`、`GET/PUT /api/settings` |
| 当前测试风格 | `tests/test_repository.py`、`tests/test_deepseek_gateway.py` |

### 2.3 当前能力差距

| OpenFic 仪表盘需要 | NovelAI 当前是否具备 | 必须补齐 |
| --- | --- | --- |
| 年度逐日创作字数 | 否 | 写作活动事件表、章节提交/重做埋点、年度聚合 |
| 活跃天数、连续天数、创作章节数 | 部分可推导但无统一口径 | 后端按时区聚合；连续天数也可由前端从完整年度序列计算 |
| 用户/Agent/导入来源占比 | 否 | `source` 字段；现阶段主要产生 `agent`，迁移历史数据标记为 `import` |
| LLM 调用次数和 Token | 有简单统计 | 扩展为按日期、模型、项目、状态聚合 |
| 平均响应时间 | 否 | 在远程调用边界用单调时钟记录 `latency_ms` |
| 首 Token 时间 | 当前非流式调用无法获得 | 字段保留为 `NULL`；前端显示 `—`，不得伪造为响应时间 |
| 调用成功/失败 | 只记录成功且无状态 | 成功、失败都写记录，并存安全的错误分类 |
| 项目/章节归属 | 否 | 调用上下文作用域，使用 `contextvars` 避免并发串线 |
| 调用记录筛选、排序、分页 | 否 | 新查询方法和 API |

## 3. 目标页面规格

### 3.1 页面公共骨架

建议新增：

- `apps/web/dashboard.css`：仅放仪表盘样式。
- `apps/web/dashboard.js`：仅放仪表盘状态、请求、格式化、SVG 图表和事件绑定。
- `index.html` 先加载 `dashboard.css`，底部先加载 `dashboard.js`、再加载 `app.js`。
- `dashboard.js` 对外只暴露 `window.NovelDashboard = { init, activate, deactivate, refresh }`，不要把几十个函数挂到全局。

页面 DOM：

```html
<section id="analyticsView" class="view analytics-view" aria-labelledby="analyticsTitle">
  <div class="analytics-shell">
    <header class="analytics-header">
      <h1 id="analyticsTitle">仪表盘</h1>
    </header>
    <div class="analytics-tabs" role="tablist" aria-label="仪表盘分类">...</div>
    <div id="writingPanel" role="tabpanel">...</div>
    <div id="llmPanel" role="tabpanel" hidden>...</div>
    <div id="recordsPanel" role="tabpanel" hidden>...</div>
  </div>
</section>
```

行为要求：

- 页签用 `<button role="tab">`；维护 `aria-selected`、`tabindex`、`aria-controls`。
- 支持左右方向键切换页签，焦点进入对应面板标题或首个控件。
- 只有激活页签发请求；切回页面时保留筛选和滚动位置。
- 默认页签为“写作”，默认明细日期范围为本地今天往前 29 天，共 30 天。
- 进入仪表盘时调用 `NovelDashboard.activate()`；离开时中止未完成请求，不清空已有数据。
- 用每类请求的递增 request id 或 `AbortController` 防止旧响应覆盖新筛选结果。

### 3.2 视觉令牌与尺寸

优先复用 `styles.css` 已有的 `--ui-*` 语义变量，不在组件内散落十几个相近灰色。仪表盘专用值：

```css
.analytics-view {
  --analytics-page-pad: 28px;
  --analytics-shell-gap: 18px;
  --analytics-card-gap: 14px;
  --analytics-card-border: var(--ui-border);
  --analytics-card-radius: 8px;
  --analytics-chart-height: 300px;
  --analytics-chart-wide-height: 320px;
  --analytics-table-min-height: 520px;
}
```

与 OpenFic 对齐的关键值：

- 主容器 `max-width: 1500px; margin: 0 auto`。
- 页标题约 30–32px、700 字重、1.15 行高。
- 页签间距 26px，底部 1px 线；激活项用 2px 深色下划线。
- 普通卡片只使用 1px 边线，不使用悬浮阴影。
- 指标数字使用等宽/制表数字，避免数值变化造成抖动。
- 桌面页边距 28px；手机为 18px 14px。
- 图表卡高度 300px，宽图 320px；调用记录表容器至少 520px。

不要照搬 OpenFic 的 Radix CSS 变量。把其 `gray-*` 映射到 NovelAI 已有的 `--ui-text`、`--ui-muted`、`--ui-border`、`--ui-surface`、`--ui-hover`。

### 3.3 “写作”页签

模块顺序必须与图二一致：

1. 年度总览区。
   - 左侧大卡：年份选择列、`2026 年创作了 N 天`、12 个月创作热力日历、`2026 年共创作 N 字`、少→多图例。
   - 右侧四张指标卡，桌面 2×2：总创作天数、连续创作天数、总创作章节、总创作字数。
   - 可用年份来自所有写作事件；无数据时仍显示当前年份。
   - 热力色阶使用 OpenFic 同等克制的四级绿色：`#d9e5dc`、`#a9c4b3`、`#6f9a7f`、`#315f46`，零值使用浅灰。
   - 每个日格可获得键盘焦点，hover/focus 显示日期与精确字数。用文本和数值补充颜色信息。
2. 筛选卡。
   - 项目下拉框、开始日期、结束日期、重置按钮。
   - 项目默认“全部”，日期默认最近 30 天。
3. 四张图，桌面 2×2：
   - 写作字数变化：堆叠柱图；“创作”=`user + agent`，“导入”=`import`。
   - 累计创作字数：面积折线图；只累加正向创作量。
   - 来源贡献占比：圆环图；用户编辑、Agent 创作、导入。
   - 创作活跃日分布：周一到周日柱图。

NovelAI 当前没有章节正文编辑器和导入入口，因此第一版真实数据通常只有 `agent`；历史回填数据统一标为 `import`。仍保留三种来源的数据契约，不在 UI 隐藏零值语义。

### 3.4 “LLM 统计”页签

顶部四张指标卡：

1. LLM 调用次数；辅助文字“完成 N 次”。
2. Token 消耗；辅助文字“输入 N / 输出 N”。
3. 平均响应时间；单位秒，保留两位小数。
4. 首字响应时间；当前 DeepSeek 非流式调用没有该指标时显示 `—`，辅助文字说明“当前模型调用为非流式”。不得用总响应时间冒充首 Token 时间。

下面六张图的桌面排布和图三一致：

- 调用趋势：宽 4/6；按模型的面积折线图，只显示最近 7 个有数据日期、最多 5 个模型。
- 模型调用次数分布：宽 2/6；圆环图。
- 模型消耗分布：宽 2/6；圆环图。
- 消耗趋势：宽 4/6；按模型的堆叠柱图。
- 响应时间趋势：宽 4/6；按模型的面积折线图。
- 总消耗分布：宽 2/6；按项目圆环图。

筛选逻辑沿用 OpenFic：LLM 统计页第一版不显示筛选卡，展示全量历史；如果后续需要筛选，可复用调用记录的过滤状态，但不要擅自在图三没有的位置增加控件。

### 3.5 “调用记录”页签

筛选卡布局与图四一致：

- 第一行：项目、模型、提供商、类型、状态，均有可见标签，默认“全部”。
- 第二行：开始日期、结束日期、搜索、重置按钮。
- 搜索输入延迟 300ms 后请求；搜索范围为模型 ID、operation、category、错误类型和错误信息。不要搜索或返回 API Key、完整 prompt。
- 任一筛选变化将页码重置为 1。

表格列与图四一致：

| 列 | 数据 | 行为 |
| --- | --- | --- |
| 时间 | `created_at`，按浏览器本地时区格式化 | 可升降序 |
| 项目 | 项目标题；无归属时显示“未归属项目” | 长文本省略并提供 title |
| 模型 | 模型显示名或 model ID | 不自动换行 |
| 操作 | `类型 / 操作` 的中文映射 | 未知值显示原值 |
| 用时 | `latency_ms / 1000` | 可升降序 |
| 首字 | `first_token_ms / 1000` 或 `—` | 可升降序 |
| 输入（缓存） | `tokens_input（token_cache）` | 可升降序 |
| 输出 | `tokens_output` | 可升降序 |
| 状态 | 成功/失败徽标 | 颜色外必须有文字 |

分页：

- 默认每页 20 条，后端允许 5–100。
- 显示“第 X–Y 条，共 N 条”。
- 前一页、页码、后一页；页码多时显示省略号。
- 表格加载时保留上一页数据并降低透明度，覆盖轻量 loading；避免整个页面闪空。
- 手机端允许表格容器横向滚动；页面本身不能产生横向滚动。

### 3.6 图表实现约束

NovelAI 没有前端构建链。不要新增 React、Nivo、ECharts 或 CDN。使用原生 DOM + SVG 实现可复用图表渲染器：

- `renderLineChart(container, model)`
- `renderBarChart(container, model)`
- `renderDonutChart(container, model)`
- `renderYearHeatmap(container, model)`
- `renderChartState(container, {loading, error, empty})`

每个渲染器必须：

- 清理旧 tooltip 和监听器，避免反复筛选后泄漏。
- 使用 `viewBox` 和 `ResizeObserver` 自适应容器；无 `ResizeObserver` 时退化为 `window.resize` 节流。
- 只用 `transform`/`opacity` 做 180ms 以内入场；尊重 `prefers-reduced-motion`。
- 提供可见图例、坐标单位和 focus/hover 共用 tooltip。
- 在图表 DOM 前加入屏幕阅读器摘要；图表后提供可折叠数据表或等价文本列表。
- 空态显示“该指标暂无统计数据”，不能渲染空坐标轴。
- 错误态显示原因和“重试”按钮。
- 千分位使用 `Intl.NumberFormat('zh-CN')`；日期用用户本地时区。

UI/UX Pro Max 对当前原生栈没有命中可直接套用的栈模板，因此本任务使用其通用规则：图表不能只靠颜色、tooltip 必须支持键盘、表格在手机使用自身横向滚动、正文不出现全局横向滚动。

## 4. 后端数据设计

### 4.1 数据库迁移原则

NovelAI 直接在 `SQLiteRepository.migrate()` 中创建表。此次必须做到：

- 对新数据库一次创建完整结构。
- 对旧数据库使用 `PRAGMA table_info(...)` + `ALTER TABLE ... ADD COLUMN` 或创建新表，绝不删除/重建用户表。
- 使用 `schema_migrations` 记录本次版本，例如版本 `2`；迁移和历史回填必须幂等。
- 迁移放在单个事务内。任何异常回滚，不留下半完成索引或半回填数据。
- 迁移前后的旧 `/api/token/statistics` 结果保持兼容。

### 4.2 扩展 `token_usage` 为调用审计数据源

保留现有列并新增以下可空/有默认值列：

```sql
ALTER TABLE token_usage ADD COLUMN project_id TEXT;
ALTER TABLE token_usage ADD COLUMN chapter_id TEXT;
ALTER TABLE token_usage ADD COLUMN run_id TEXT;
ALTER TABLE token_usage ADD COLUMN category TEXT NOT NULL DEFAULT 'agent';
ALTER TABLE token_usage ADD COLUMN provider TEXT;
ALTER TABLE token_usage ADD COLUMN status TEXT NOT NULL DEFAULT 'success';
ALTER TABLE token_usage ADD COLUMN latency_ms INTEGER;
ALTER TABLE token_usage ADD COLUMN first_token_ms INTEGER;
ALTER TABLE token_usage ADD COLUMN cache_tokens INTEGER NOT NULL DEFAULT 0;
ALTER TABLE token_usage ADD COLUMN error_type TEXT;
ALTER TABLE token_usage ADD COLUMN error_message TEXT;
ALTER TABLE token_usage ADD COLUMN error_status_code INTEGER;
```

说明：

- 不存 API Key、Authorization header、完整请求 prompt 或完整模型输出。
- `project_id` 不设强外键：创建小说的首个模型调用可能先于项目记录落库；失败调用也必须保留。
- 旧记录保留原 `date` 和 `created_at`，新增列按默认值兼容；`provider` 可根据模型/运行配置回填为 `deepseek`，无法判断则为空。
- `first_token_ms` 当前保持 `NULL`。

索引：

```sql
CREATE INDEX IF NOT EXISTS idx_token_usage_created_at ON token_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_token_usage_project_created ON token_usage(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_token_usage_model_created ON token_usage(model, created_at);
CREATE INDEX IF NOT EXISTS idx_token_usage_status_created ON token_usage(status, created_at);
CREATE INDEX IF NOT EXISTS idx_token_usage_operation_created ON token_usage(operation, created_at);
```

不要把每一种筛选组合都建索引；先覆盖日期范围和最常用前缀。

### 4.3 新增 `writing_activity_events`

```sql
CREATE TABLE IF NOT EXISTS writing_activity_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    project_id TEXT NOT NULL,
    chapter_id TEXT,
    chapter_title TEXT,
    source TEXT NOT NULL CHECK(source IN ('user','agent','import')),
    operation TEXT NOT NULL,
    old_word_count INTEGER NOT NULL DEFAULT 0,
    new_word_count INTEGER NOT NULL DEFAULT 0,
    word_delta INTEGER NOT NULL DEFAULT 0,
    run_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_writing_activity_created
ON writing_activity_events(created_at);
CREATE INDEX IF NOT EXISTS idx_writing_activity_project_created
ON writing_activity_events(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_writing_activity_source_created
ON writing_activity_events(source, created_at);
```

字数口径：沿用 NovelAI 的“章节目标字符数”语义，统计正文中**非空白字符数**。把算法放在单一函数中并写测试，前端帮助文字说明此口径。

事件写入点：

- 章节首次正式提交：`source='agent'`、`operation='create'`、旧字数 0、新字数为正式正文。
- 同一章节重生成并提交：`source='agent'`、`operation='update'`、记录旧正式正文与新正式正文的差值。
- 打回导致正文被清空：`source='agent'`、`operation='delete'`、新字数 0；必须与正文状态回滚在同一事务。
- 将来如增加用户正文编辑或导入，分别使用 `user`、`import`，不修改现有聚合契约。

历史回填：

- 迁移版本 2 对已有且 `content` 非空的章节写入一条 `source='import'`、`operation='backfill'` 事件。
- 事件时间使用章节 `updated_at`，新字数按当前正文计算。
- 只在迁移版本首次执行时回填，避免重复累计。

### 4.4 LLM 调用上下文与埋点

当前 `_on_usage` 只能收到 Token，且只记录成功调用。改造要求：

1. 新增轻量调用上下文，例如 `novel_agent/telemetry.py`：

```python
@dataclass(frozen=True)
class LLMCallContext:
    project_id: str | None = None
    chapter_id: str | None = None
    run_id: str | None = None
    category: str = "agent"
```

2. 使用 `contextvars.ContextVar` + context manager 建立作用域，不能使用进程全局可变字典；HTTP 服务是多线程的，全局变量会把不同请求的项目归属串在一起。
3. `create_novel()` 在调用模型前先生成 `project_id`，并在该 scope 中调用 `create_brief()`。如果调用失败，记录仍可带 project ID，但项目标题为空。
4. `regenerate_draft_brief()` 使用项目 scope。
5. 章节工作流在已知 `project_id`、`chapter_id`、`run_id` 后建立 scope，内部所有 plan/write/review/revise/summary 调用自动继承。
6. `_chat()` 用 `time.perf_counter()` 计算用户感知的总耗时；成功与最终失败均调用统一 `record_llm_call(...)` 回调。
7. 错误记录只保留安全分类、HTTP 状态和去敏后的短消息。不要落库 headers、Key、完整请求正文。
8. 一次真实供应商 HTTP 请求对应一条记录。JSON 修复重试产生第二次 HTTP 请求时记录第二条；网络层内部 retry_count 记录在最终该条记录上。
9. 离线 `OfflineLLMGateway` 不伪造 LLM 供应商调用；离线操作不写 `token_usage`。

建议将旧 `_on_usage` 改名为 `_on_call`，回调参数使用一个 dataclass 或关键字字典，避免继续扩大十几个位置参数。保留 `save_token_usage(...)` 作为测试和兼容入口，由它调用新的记录方法并填默认值。

### 4.5 Repository 查询方法

在 `SQLiteRepository` 中增加清晰的只读方法，不把几十行 SQL 写进 `api.py`：

- `get_writing_dashboard(project_id, source, start_at, end_at, timezone)`
- `get_llm_dashboard_stats(filters)`
- `list_llm_call_records(filters, page, page_size, sort_by, sort_order)`
- `get_dashboard_filter_options()`

约束：

- 排序字段必须用服务端白名单映射到固定 SQL 列，绝不能直接拼接用户传入的列名。
- 普通筛选值全部使用 `?` 参数绑定。
- 搜索中的 `%`、`_` 必须转义，并使用 `ESCAPE`，避免它们意外变成通配符。
- 日期按 `created_at` 范围过滤；写作分组根据客户端 `timezone` 转换到本地日期。时区无效时返回 400，不要静默使用错误时区。
- 聚合 SQL 要有界：统计页最多 2–3 次查询；记录页使用一条分页查询和一条 options 查询。数据量较小时可在 Python 中完成时区分组，但不能为每条记录发 SQL。
- 项目名称用 `LEFT JOIN projects`，保证创建失败或已删除项目的历史调用仍可显示。

## 5. HTTP API 契约

NovelAI 沿用 `/api` 前缀，接口名称与 OpenFic 对齐。

### 5.1 `GET /api/dashboard/writing`

查询参数：

- `project_id`：可选。
- `source`：可选，仅 `user|agent|import`。
- `start_at`、`end_at`：可选 ISO 8601。
- `timezone`：IANA 名称，例如 `Asia/Shanghai`。

响应：

```json
{
  "summary": {"active_days": 12, "creative_chapters": 18},
  "time_series": [
    {
      "date": "2026-09-28",
      "user_word_delta": 0,
      "agent_word_delta": 2450,
      "import_word_delta": 0
    }
  ]
}
```

年度日历和最近 30 天明细可调用同一接口，但参数不同。前端要缓存当前会话已取过的年度结果，切页签时不重复请求。

### 5.2 `GET /api/dashboard/llm-api/stats`

支持可选参数：`project_id`、`model_provider`、`model_id`、`category`、`operation`、`status`、`start_at`、`end_at`。

响应保持 OpenFic 字段名：

```json
{
  "summary": {
    "calls_total": 10,
    "success_total": 9,
    "tokens_total": 12345,
    "tokens_input_total": 9000,
    "tokens_output_total": 3345,
    "avg_latency_ms": 2850.5,
    "avg_first_token_ms": null
  },
  "model_time_series": [
    {
      "date": "2026-09-28",
      "key": "deepseek-v4-pro",
      "label": "deepseek-v4-pro",
      "calls": 3,
      "tokens_total": 4200,
      "avg_latency_ms": 2400.0
    }
  ],
  "by_model": [],
  "by_project": [],
  "options": {
    "project_ids": [],
    "model_providers": [],
    "model_ids": [],
    "categories": [],
    "operations": [],
    "statuses": [],
    "project_options": [],
    "model_options": []
  }
}
```

`avg_first_token_ms` 在无有效样本时必须为 `null`，前端据此显示 `—`。

### 5.3 `GET /api/dashboard/llm-api/records`

查询参数：

- 与 stats 相同的过滤条件。
- `search`。
- `page`，默认 1，最小 1。
- `page_size`，默认 20，范围 5–100。
- `sort_by`：`created_at|tokens_input|tokens_output|tokens_total|latency_ms|first_token_ms|retry_count`。
- `sort_order`：`asc|desc`。

响应：

```json
{
  "options": {
    "project_ids": [],
    "model_providers": ["deepseek"],
    "model_ids": ["deepseek-v4-pro"],
    "categories": ["agent"],
    "operations": ["write_chapter"],
    "statuses": ["success", "failed"],
    "project_options": [{"value": "novel_x", "label": "小说标题"}],
    "model_options": [{"value": "deepseek-v4-pro", "label": "deepseek-v4-pro"}]
  },
  "records": {
    "items": [
      {
        "id": 123,
        "created_at": "2026-09-28T06:20:11Z",
        "project_id": "novel_x",
        "project_title": "小说标题",
        "chapter_id": "chapter_x",
        "category": "agent",
        "operation": "write_chapter",
        "model_id": "deepseek-v4-pro",
        "model_provider": "deepseek",
        "tokens_input": 3200,
        "tokens_output": 1800,
        "tokens_total": 5000,
        "token_cache": 0,
        "latency_ms": 4600,
        "first_token_ms": null,
        "status": "success",
        "error_type": null,
        "error_message": null,
        "error_status_code": null,
        "retry_count": 0
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

### 5.4 API 错误约定

- 非法日期、结束日期早于开始日期、非法时区、非法分页和排序：400。
- 服务内部错误：500，前端显示可重试错误卡；不能把 traceback 返回浏览器。
- 空结果：200 + 空数组和全 0 summary，不使用 404。
- 所有 JSON 仍通过现有 `_send_json()` 返回 UTF-8。
- 使用 `urllib.parse.urlsplit` + `parse_qs` 统一解析查询参数，替换 dashboard 接口中的手工字符串拆分；兼容接口可逐步迁移。

## 6. 前端状态与函数划分

`dashboard.js` 建议维护以下单一状态：

```js
const dashboardState = {
  activeTab: "writing",
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  selectedYear: new Date().getFullYear(),
  filters: {
    projectId: "",
    modelProvider: "",
    modelId: "",
    category: "",
    status: "",
    startDate: "",
    endDate: "",
    search: "",
    page: 1,
    pageSize: 20,
    sortBy: "created_at",
    sortOrder: "desc"
  },
  writingHero: null,
  writingDetail: null,
  llmStats: null,
  records: null
};
```

建议函数：

- 生命周期：`initDashboard()`、`activateDashboard()`、`deactivateDashboard()`。
- 请求：`fetchWritingHero()`、`fetchWritingDetail()`、`fetchLlmStats()`、`fetchCallRecords()`。
- DOM：`renderWritingTab()`、`renderLlmTab()`、`renderRecordsTab()`、`renderDashboardFilters()`。
- 图表：第 3.6 节四个 renderer。
- 工具：`formatNumber()`、`formatCompactNumber()`、`formatSeconds()`、`formatLocalDateTime()`、`buildDateRange()`、`escapeHtml()`。
- 交互：`switchDashboardTab()`、`updateFilters()`、`resetFilters()`、`toggleRecordSort()`、`goToRecordPage()`。

不要复制 `app.js` 内的 `api()`、`escapeHtml()`。将通用方法明确暴露给 `NovelDashboard`，或把仪表盘脚本放在 `app.js` 之后并由 `app.js` 注入依赖：

```js
window.NovelDashboard.init({ api, escapeHtml, notify });
```

推荐依赖注入，避免隐式全局耦合。

## 7. Cursor 实施阶段

### 阶段 0：基线和保护

1. 运行 `git status --short`，记录并保留用户已有改动，不覆盖无关文件。
2. 运行当前测试：`py -3 -m pytest`。
3. 启动应用，截图当前系统设置页的有数据/无数据状态。
4. 记录现有导航、`loadSettings()`、`renderUsage()`、`saveSettings()` 的行为。
5. 不调用真实付费模型来造测试数据；测试使用临时 SQLite 和 mock transport。

完成条件：基线测试结果和截图已记录，尚未改功能。

### 阶段 1：数据库和 Repository

1. 实现版本 2 幂等迁移。
2. 扩展 `token_usage`，创建 `writing_activity_events` 和索引。
3. 历史章节按 `import/backfill` 回填一次。
4. 添加记录调用、记录写作事件和三类仪表盘查询方法。
5. 保持旧 Token 查询测试通过。

完成条件：新旧数据库都可打开；重复执行 migrate 不新增重复回填；Repository 单测通过。

### 阶段 2：真实埋点

1. 新增线程/异步安全的 LLM 调用 context scope。
2. 把项目、章节、run 上下文接入 service/workflow。
3. 成功、认证失败、限流、超时、服务商错误、格式错误均形成记录。
4. 用单调时钟记录 latency；首 Token 保持空。
5. 在章节提交和打回事务内记录写作事件。

完成条件：mock transport 的成功、一次重试、最终失败均有精确记录；并发 scope 不串项目。

### 阶段 3：Dashboard API

1. 在 `api.py` 中新增三个 GET 路由，优先匹配具体 records 路径再匹配通用路径。
2. 新增查询参数解析、日期/时区/分页/排序验证。
3. JSON 字段严格按第 5 节输出。
4. 让旧 `/api/token/statistics` 继续工作。
5. 更新 `docs/API.md`。

完成条件：API 单测覆盖空数据、有数据、筛选、排序、分页、非法参数和时区边界。

### 阶段 4：页面静态结构和导航拆分

1. 在侧栏新增“仪表盘”项和内联 SVG 图标，不使用 emoji。
2. 保留“系统设置”，把它定位为底部次级入口。
3. 从 `#settingsView` 移除 Token 图表 DOM，但保留运行能力和本地偏好。
4. 新增 `#analyticsView` 三页签和语义化占位容器。
5. 更新 `labels`、`switchView()` 和页面标题逻辑。

完成条件：无接口数据也能正确切换三个页签和两个侧栏入口；键盘可操作。

### 阶段 5：真实数据和交互

1. 接入写作年度、写作明细、LLM 统计、调用记录接口。
2. 实现项目/日期/模型/提供商/类型/状态筛选。
3. 实现 300ms 搜索防抖、排序、分页、重置和状态保留。
4. 实现 loading、empty、error/retry，并防止响应竞态。
5. 调用记录不返回或展示敏感 prompt/output。

完成条件：筛选和分页请求参数可在浏览器 Network 面板核对；快速切换不会显示旧请求结果。

### 阶段 6：图表与视觉复刻

1. 按第 3 节实现热力日历、柱图、折线/面积图、圆环图。
2. 逐项对照图二、图三、图四和 OpenFic CSS 校准尺寸、间距、卡片比例。
3. 完成 1180px、767px 断点；测试 1440、1024、768、390、320 宽度。
4. 增加键盘 tooltip、文本摘要、数据表替代和 reduced-motion。
5. 不改其他四个 NovelAI 业务页面的布局。

完成条件：主内容区截图视觉层级与 OpenFic 对齐，没有全局横向滚动或遮挡。

### 阶段 7：文档和最终回归

依据 `AGENTS.md`，本阶段是强制项：

1. 更新 `docs/USER_GUIDE.md`：
   - 页面导航表新增“仪表盘”。
   - “系统设置”章节删除 Token 图表说明，只保留能力状态与本地偏好。
   - 新增“仪表盘”章节，说明三个页签、筛选、字数口径、调用记录隐私边界。
   - 说明首 Token 在非流式 DeepSeek 下显示 `—`。
   - 说明历史章节以“导入”来源回填，统计启用前无法还原真实逐日创作过程。
2. 更新 `docs/API.md` 的三个新接口和兼容接口说明。
3. 检查 README 到用户指南的链接仍有效；若 README 功能列表提到旧系统设置 Token 图，改成仪表盘。
4. 运行完整测试和手工验收。

完成条件：代码、API 文档和用户指南一致。

## 8. 必须新增或扩展的测试

### 8.1 Repository / migration

- 旧库升级后原 token 数据仍可查询。
- `migrate()` 连续执行两次，schema 和历史回填不重复。
- 已有章节只产生一条 import/backfill 事件。
- 写作事件按项目、来源、日期正确筛选。
- 跨 UTC 日期的数据按 `Asia/Shanghai` 落在正确本地日期。
- LLM summary 的总调用、成功数、输入/输出/总 Token、平均 latency 正确。
- 空的 `first_token_ms` 不参与平均，全部为空时返回 `None/null`。
- 同一模型不同日期、不同项目的趋势和分布正确。
- 记录排序白名单拒绝恶意列名。
- 搜索 `%`、`_` 时按字面值处理。

### 8.2 Gateway / service / workflow

- 成功调用记录 status=success、Token、模型、provider、latency。
- 最终超时/认证/限流/供应商异常记录 status=failed 和安全错误分类。
- retry_count 与实际网络重试一致。
- 创建小说、重做方案、章节工作流的 project/chapter/run 归属正确。
- 两个并发 context scope 不串数据。
- Offline gateway 不产生伪 LLM 记录。
- READY 提交写入 agent/create 或 agent/update 事件。
- 打回正文写入负向 delete 事件且事务回滚时事件也回滚。

### 8.3 HTTP API

- 三接口空库返回 200 和稳定空结构。
- 各筛选字段生效且 options 不受当前筛选裁剪。
- records 默认 20 条，页码和 total 正确。
- 各允许列升降序正确；非法 sort_by 返回 400。
- 非法日期、逆序日期、非法时区、page=0 返回 400。
- 返回内容不含 API Key、request messages、Authorization 或完整模型输出。

### 8.4 前端手工回归

- 用鼠标和纯键盘切换三个页签。
- 筛选标签始终可见；错误显示在相应区域。
- 300ms 搜索防抖有效，清空搜索后回到第一页。
- 表头排序方向可见且设置 `aria-sort`。
- 热力格和图表数据点可通过 Tab/方向键读取。
- 390px 下页签可见、指标卡不挤坏、表格只在自身区域横向滚动。
- 200% 浏览器缩放下仍能操作。
- `prefers-reduced-motion: reduce` 时没有位移动画。
- 其他页面的项目选择、创建小说、章节生成、阅读、长期记忆和设置保存无回归。

## 9. 验收标准

### 9.1 视觉验收

- 1440px 宽度下，仪表盘主内容区与 OpenFic 图二/三/四的模块顺序和栅格比例一致。
- 没有把现有系统设置表单塞进三个仪表盘页签。
- 页面以白/浅灰、细线和排版分层，没有新增渐变、大投影、玻璃效果或高饱和装饰。
- 图表卡在有数据、无数据、加载和失败四种状态下占位尺寸稳定，不发生布局跳动。
- 数字使用制表数字；长项目名和模型名不挤压其他列。

### 9.2 数据验收

- 页面刷新后统计数据保持不变，证明来自 SQLite 而非内存。
- 新生成章节后，写作页对应日期、章节数和字数更新。
- 成功与失败的远程调用都出现在调用记录中。
- LLM 总数、Token 合计与调用记录筛选后的合计可核对。
- 项目筛选、日期范围、模型、提供商、类型、状态、搜索、排序、分页全部由后端执行。
- 无法采集的首 Token 显示 `—`，不显示伪造的 0 或复制 latency。

### 9.3 安全与兼容验收

- 数据库迁移不丢现有项目、章节、设置和 Token 历史。
- API 与表格不暴露密钥、完整 prompt 或完整输出。
- 原 `/api/settings`、`/api/usage`、`/api/token/statistics` 可继续调用。
- 没有新 CDN、npm 包或运行时网络资源。
- `docs/USER_GUIDE.md` 和 `docs/API.md` 已同步。
- `py -3 -m pytest` 全部通过。

## 10. 建议变更文件清单

预期会修改：

- `apps/web/index.html`
- `apps/web/app.js`
- `apps/web/styles.css`（只放共享导航/设置拆分规则）
- `novel_agent/api.py`
- `novel_agent/bootstrap.py`
- `novel_agent/adapters_remote.py`
- `novel_agent/service.py`
- `novel_agent/workflow.py`
- `novel_agent/repository.py`
- `tests/test_repository.py`
- `tests/test_deepseek_gateway.py`
- `docs/API.md`
- `docs/USER_GUIDE.md`
- 可能需要更新 `README.md`

建议新增：

- `apps/web/dashboard.css`
- `apps/web/dashboard.js`
- `novel_agent/telemetry.py`
- `tests/test_dashboard.py`

不要修改：

- `D:\实习日报\githubClone\OpenFic` 中的任何文件。
- 与仪表盘无关的 Story Skills、oh-story 供应文件。
- 当前创建、写作、审核和记忆领域模型的业务语义。

## 11. 最终交付格式

Cursor 完成后必须按以下格式汇报：

1. **完成内容**：三个页签、数据库、埋点、API、响应式分别做了什么。
2. **变更文件**：逐文件说明，不只列文件名。
3. **数据库迁移**：迁移版本、历史回填口径、是否可重复执行。
4. **API 契约**：三个新接口及兼容接口状态。
5. **测试结果**：命令、通过数量、失败或未运行原因。
6. **视觉证据**：1440px、1024px、390px 的写作/LLM/调用记录截图。
7. **已知限制**：尤其是非流式调用无首 Token 时间、历史写作活动只能回填当前正文。

不得用“页面已优化”“基本完成”这类笼统描述代替可验证结果。
