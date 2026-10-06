# Novel Agent 小说书架、创建流程与 Vue 3 迁移执行书

> 面向 Cursor 的前后端实施文档。本文只定义改造方案与验收边界，不代表功能已经实现。  
> 本文基于 2026-10-02 仓库现状编写，目标仓库为当前仓库根目录，视觉参考仓库为 OpenFic 参考仓库根目录。

## 0. Cursor 必须先读

开始修改前，依次阅读：

1. `AGENTS.md`
2. 本文全文
3. `docs/USER_GUIDE.md`
4. `docs/API.md`
5. `apps/web/index.html`、`apps/web/app.js`、`apps/web/reader-workspace.js`
6. `apps/web/js/features/projects/`
7. `apps/web/js/features/novel-create/`
8. `apps/web/js/features/project-dashboard/`、`story-brief/`、`analytics/`
9. `novel_agent/interfaces/http/routes/projects.py`
10. `novel_agent/interfaces/http/routes/story_design.py`
11. `novel_agent/features/projects/`、`novel_agent/features/story_design/`
12. `novel_agent/infrastructure/persistence/projects_store.py`
13. OpenFic 的 `frontend/src/features/projects/`，只提取书架、工具栏、卡片和空状态的交互规律，不复制 React 代码和品牌资源。

### 0.1 文档优先级

用户已经明确要求本次前端使用 Vue 3，因此本文在以下范围内优先于旧策划：

- `docs/OPENFIC_FRONTEND_DESIGN_EXECUTION.md` 中“保留原生 HTML/CSS/JavaScript、不引入 Vite”的旧约束；
- `docs/NOVELAI_CREATION_CLOSED_LOOP_PRODUCT_PLAN.md` 中“不引入新的大型前端框架”的旧阶段性非目标。

其他关于业务状态、数据安全、方案确认、章节生成、修订、长期记忆和成本边界的约束继续有效。

### 0.2 不可违反的规则

1. 默认入口必须从“创作控制台”改成小说书架。
2. 左侧导航第一项为“我的小说”，第二项为“创作工作台”。全站统一使用“创作工作台”，不再混用“创作控制台”。
3. 新建小说成功后必须进入该小说的创作工作台，并展示刚生成的创作方案。
4. 本次不重新设计创作工作台、作品阅读、长期记忆、仪表盘和系统设置的内容；迁移到 Vue 时必须保持现有字段、动作、状态和信息层级。
5. 不允许在页面组件里直接散落 `fetch`、业务判断或 localStorage 操作。API、状态、路由、组件和页面必须分层。
6. 不允许通过在 Vue 页面中加载旧页面 iframe、复制整段旧 HTML、长期保留两套事件系统等方式伪造迁移完成。
7. 旧代码只能在 Vue 功能对等、测试通过后删除；删除后不能保留未引用的兼容脚本和样式。
8. 所有用户可见页面、流程、状态、命令和接口变化，必须在同一改动中更新 `docs/USER_GUIDE.md`；接口变化同步更新 `docs/API.md`；README 中的用户指南链接必须保持有效。
9. 不删除或重建用户的 SQLite 数据库。数据库结构如需变化，必须使用可重复执行的迁移并先增加回归测试。
10. 不调用在线模型做测试。创建流程使用现有离线网关和临时数据库验证。

---

## 1. 改造目标

当前系统把“创作控制台”放在第一位，用户还没有小说时也会先进入工作台；“创建小说”是独立表单页面，项目列表只存在于页头选择器中。这使入口顺序与真实创作过程相反。

目标流程：

```text
打开 Novel Agent
  → 我的小说（书架，默认首页）
  → 点击“新建小说”
  → 三步创作引导表单
  → 点击“生成创作方案”
  → 后端生成并保存项目与方案
  → 自动进入 /novels/:projectId/workbench
  → 用户检查、修改或确认方案
  → 继续现有章节生产流程
```

已有小说的返回流程：

```text
我的小说
  → 点击书籍卡片或“继续创作”
  → 选择该项目
  → 进入该项目创作工作台
```

### 1.1 成功标准

- 新用户不再先看到一个没有项目上下文的工作台。
- 用户始终知道自己正在创建哪一本书、当前处于书架、创建还是工作台阶段。
- 书架可以搜索、排序并切换卡片/列表视图。
- 创建表单不再把所有字段同时压在一屏，而是按任务顺序渐进展示。
- 表单字段和后端 `NovelCreateRequest` 完整对应，不丢失现有生成能力。
- Vue 3 成为唯一前端运行时，旧原生 JS/CSS 在迁移结束时彻底移除。
- Python 继续作为唯一后端，SQLite 继续作为唯一权威存储。

### 1.2 本次不做

- 不照搬 OpenFic 的 React、Radix、Zustand、TanStack Query 或品牌资产。
- 不实现 OpenFic 的项目导入、封面上传、云同步或账号系统。
- 不重做创作工作台内部布局和文案。
- 不修改章节生成算法、Prompt、LLM 提供商、长期记忆算法或审核门禁。
- 不引入异步任务队列。`POST /api/novels` 本阶段仍为同步创建；前端必须正确处理长时间生成状态，且不得自动重复提交。
- 不实现深色主题。先完成浅色主题和功能迁移。

---

## 2. 现状与保留边界

### 2.1 当前前端

当前前端是无构建步骤的原生单页应用：

- `apps/web/index.html`：全站骨架和大量业务 DOM；
- `apps/web/app.js`：导航、项目选择、工作台、记忆、设置等总装逻辑；
- `apps/web/reader-workspace.js`：阅读与修订工作台；
- `apps/web/js/features/*`：项目、创建小说、方案、仪表盘等分拆模块；
- `apps/web/styles.css`、`reader-workspace.css`、`styles/features/*`：全站与页面样式。

这套代码已经有部分模块化，但仍依赖固定 ID、手工拼 HTML、全局函数和 DOM 查询。Vue 迁移后不能继续维护这套绑定。

### 2.2 当前后端

现有后端分层应保留：

- HTTP 路由：`novel_agent/interfaces/http/routes/`
- 项目生命周期：`novel_agent/features/projects/`
- 创作方案：`novel_agent/features/story_design/`
- 持久化：`novel_agent/infrastructure/persistence/`
- 组装：`novel_agent/bootstrap.py`
- 静态站点与通用 HTTP：`novel_agent/api.py`

已有接口可以继续承担主流程：

- `GET /api/tags`
- `POST /api/novels`
- `GET /api/novels`
- `GET /api/novels/{id}`
- `POST /api/novels/{id}/confirm`
- `DELETE /api/novels/{id}`
- 创作方案编辑、重做和版本接口

本次只补充书架需要的轻量列表结构与书名修改能力，不把工作台逻辑塞回路由文件。

### 2.3 必须冻结的业务行为

以下行为在 Vue 迁移中只换实现方式，不改语义：

- DRAFT、ACTIVE、PAUSED、HUMAN_REQUIRED、ARCHIVED 状态；
- 方案确认、手工编辑、反馈重做、局部重做、版本比较和恢复；
- 生成下一章、暂停、继续、修复与恢复；
- 草稿项目和正式项目不同的删除确认规则；
- 作品阅读与修订、人物档案、世界规则、时间线、研究资料；
- 仪表盘、设置和服务健康状态；
- `novelAgentProject` 代表最近选择项目的兼容含义。Vue 版可改为 Pinia 持久化，但首次加载必须读取旧键，避免升级后丢失最近选择。

---

## 3. 目标信息架构与路由

使用 Vue Router 的 history 模式。Python 静态服务器已有未知非资源路径回退 `index.html` 的逻辑，需要增加深链测试。

| 路由 | 页面 | 项目上下文 |
|---|---|---|
| `/` | 重定向到 `/novels` | 否 |
| `/novels` | 我的小说 / 书架 | 否 |
| `/novels/new` | 新建小说三步表单 | 否 |
| `/novels/:projectId/workbench` | 创作工作台 | 是 |
| `/novels/:projectId/reader` | 作品阅读 | 是 |
| `/novels/:projectId/memory` | 长期记忆 | 是 |
| `/analytics` | 仪表盘 | 可选项目筛选 |
| `/settings` | 系统设置 | 否 |
| `/:pathMatch(.*)*` | 404 页面，提供返回书架按钮 | 否 |

### 3.1 导航顺序

```text
我的小说
创作工作台
作品阅读
长期记忆
仪表盘
----------------
系统设置
```

规则：

1. “我的小说”永远可进入，并是默认首页。
2. 用户点击“创作工作台”“作品阅读”或“长期记忆”时：
   - 当前 URL 已有 `projectId`：使用当前项目；
   - 否则读取最近选择项目；
   - 最近项目仍存在：进入对应项目路由；
   - 没有有效项目：返回 `/novels`，显示“请先创建或选择一本小说”，不能进入空工作台。
3. 项目选择器只在项目作用域页面显示；书架和新建页不显示“尚无项目”的选择器。
4. 删除当前项目后清除选择并返回书架。
5. 直接刷新项目深链时，先验证项目存在；404 则显示项目不存在页面并允许返回书架。

---

## 4. 页面与交互规格

## 4.1 我的小说 / 书架

桌面结构：

```text
┌───────────────────────────────────────────────────────────┐
│ 我的小说                                                  │
│ [＋ 新建小说]     [搜索小说……] [最近编辑⌄] [网格] [列表] │
├───────────────────────────────────────────────────────────┤
│ ┌──────┐  ┌──────┐  ┌──────┐                             │
│ │ 封面 │  │ 封面 │  │ 封面 │                             │
│ │      │  │      │  │      │                             │
│ └──────┘  └──────┘  └──────┘                             │
│ 书名      书名      书名                                  │
│ 字数·章节 状态·时间  字数·章节                             │
└───────────────────────────────────────────────────────────┘
```

工具栏：

- 主按钮：“新建小说”，跳转 `/novels/new`；
- 搜索：按书名、题材匹配，输入 200ms 防抖；
- 排序：最近编辑、最近创建、书名；默认最近编辑降序；
- 网格/列表切换；偏好写入 localStorage；
- 第一阶段不显示“导入”，不要留下不可用按钮。

书籍卡片：

- 默认封面比例 `2:3`；没有真实封面时使用本地 SVG 书本图标、书名首字和题材生成稳定的占位封面；
- 标题最多两行；完整标题可由 `title` 或可访问名称获得；
- 展示题材、状态、有效正文字数、章节数和最近编辑时间；
- 主操作为整卡进入工作台，同时保留清楚的“继续创作”文本操作；
- 次操作放在菜单中：修改书名、删除；不能只依赖 hover 才能出现；
- 卡片使用 `<article>`，进入操作使用真实 `<a>`/`RouterLink`，不要给普通 `<div>` 模拟按钮；
- 操作按钮最小点击区域 44×44px，有 `aria-label` 和可见焦点。

状态文案：

| 后端状态 | 书架文案 | 颜色只作辅助 |
|---|---|---|
| `DRAFT` 且未确认 | 待确认方案 | 中性警示 |
| `ACTIVE` | 创作中 | 成功色 |
| `PAUSED` | 已暂停 | 中性灰 |
| `HUMAN_REQUIRED` | 需要处理 | 危险/警示色 |
| `ARCHIVED` | 已归档 | 中性灰 |

必须实现五种页面状态：

1. 首次加载骨架屏；
2. 加载失败，原位错误和“重新加载”；
3. 无任何小说，显示“从一个想法开始你的第一本小说”和“创建第一本小说”；
4. 搜索无结果，保留搜索词并提供清空；
5. 正常网格/列表。

### 4.1.1 修改书名

- 弹窗只包含书名字段；最大 80 字，与后端一致；
- 保存期间禁用重复提交；
- 成功后更新卡片、最近编辑时间和当前工作台标题；
- 修改必须同步 `projects.title` 与当前 `brief.selected_title`，不能出现书架和方案标题不一致；
- 不改变项目状态、确认状态、章节和长期记忆。

### 4.1.2 删除

- 未确认且没有章节的 DRAFT 项目：普通二次确认；
- 其他项目：要求完整输入当前书名；
- 前端只负责展示和收集确认信息，最终规则仍由后端校验；
- 删除成功后刷新书架；如果删除的是当前项目，清除最近项目；
- 删除失败不得乐观地从列表永久移除。

## 4.2 新建小说三步表单

复杂创建表单使用独立路由页面，不使用狭窄弹窗。桌面为“左侧步骤内容 + 右侧需求摘要”，移动端为单列，摘要折叠在步骤标题下方。

顶部显示：返回书架、标题“创建小说”、`第 1 步，共 3 步` 进度和简短说明。

### 第一步：故事起点

字段：

- `audience_channel`：男频 / 女频；
- `genre`：随频道更新；
- `preferred_title`：可选，最多 80 字；
- `idea`：必填，1–2000 字，显示字数计数；

说明文本面向作者，不使用“请求体、规则转换、智能体参数”等开发术语。

### 第二步：创作偏好

字段：

- `experiences`：最多 8 个；
- `elements`：最多 12 个；
- `protagonist_tags`：最多 8 个；
- `romance`：可选；

要求：

- 标签目录来自 `GET /api/tags`；
- 切换频道后，如果旧选择不属于新频道，明确提示并移除无效选择；
- 标签必须是可键盘操作的 checkbox/radio，不用只有点击事件的 span；
- 达到上限时给出就地提示，不静默失败。

### 第三步：连载计划与边界

默认展示：

- `must_have`：必须包含；
- `exclude`：明确不要；
- `require_plan_confirmation`：默认开启；

“更多设置”展开后展示：

- `nice_to_have`；
- `chapter_target_chars`：800–8000，默认 2200；
- `daily_chapters`：1–20，默认 2；
- `reserve_target`：1–50，默认 5。

右侧需求摘要实时显示频道、题材、标题/待生成标题、核心想法摘要、已选标签和连载设置。摘要不是第二份表单，不允许在摘要中产生另一套状态。

### 4.2.1 步骤与校验

- 下一步只校验当前步骤；返回上一步不清空内容；
- 普通字段在 blur 后校验，标签上限即时校验；
- 最终提交失败时在表单顶部显示可聚焦的错误摘要，并同时保留字段旁错误；
- 422 错误按 `details[].loc` 映射到字段和步骤；
- `REQUIREMENT_CONFLICT`/409 的冲突详情显示在相关标签组和错误摘要；
- 不用 toast 代替字段错误；
- 浏览器刷新和意外返回时，用 localStorage 保存未提交草稿；创建成功后清除；用户主动放弃非空表单时二次确认。

### 4.2.2 提交与跳转

点击“生成创作方案”后：

1. 锁定提交按钮，按钮显示“正在生成创作方案……”；
2. 页面显示稳定尺寸的进度区，不让布局跳动；
3. 禁止同一次点击发起多个 POST；
4. 不设置短于后端 LLM 超时的前端超时，不自动重试 POST；
5. 成功后将项目设为当前项目，清空表单草稿；
6. 使用 `router.replace('/novels/{id}/workbench?created=1')`；
7. 工作台读取项目详情并展示方案；
8. 显示一次性成功提示“创作方案已生成，请检查后确认”；
9. 失败后留在当前步骤，保留所有输入，恢复按钮可用并显示可操作错误。

如果用户在请求过程中关闭或刷新页面，重新打开后先刷新书架，不能直接建议再次提交；服务端可能已经完成创建，避免重复项目。

## 4.3 创作工作台

本阶段只改变入口和路由，不改变工作台内容。

Vue 组件必须完整迁移当前：

- 项目状态和简介；
- 确认方案、修改方案、重新生成、修复恢复、生成下一章、暂停/继续、删除；
- 今日完成、储备、当前进度、运行健康度；
- 章节生产流程、章节储备；
- 创作方案展示、编辑、反馈重做、局部重做、版本对比和恢复。

不得以“暂时占位”交付工作台。若任何旧操作尚未迁移，不能删除对应旧代码，也不能宣布 Vue 迁移完成。

---

## 5. 视觉与可访问性规范

采用 OpenFic 书架的内容优先结构，但不复制其代码。视觉保持现有改造后的中性、克制、轻边界方向，不采用常见的紫色渐变“AI 风”。

### 5.1 基础令牌

在 `apps/web/src/styles/tokens.css` 定义语义变量，组件中禁止散落重复色值：

```css
:root {
  --color-bg: #ffffff;
  --color-sidebar: #fafafa;
  --color-surface: #ffffff;
  --color-surface-muted: #f5f5f5;
  --color-border: #e5e5e5;
  --color-text: #202020;
  --color-text-muted: #666666;
  --color-primary: #202020;
  --color-on-primary: #ffffff;
  --color-success: #237a57;
  --color-warning: #9a6700;
  --color-danger: #b42318;
  --color-focus: #2563eb;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
}
```

具体色值可在视觉验证时微调，但必须保持：

- 正文对背景对比度至少 4.5:1；
- 状态不只靠颜色表达；
- 主操作区域只有一个高对比按钮；
- 普通卡片不用大阴影，浮层才使用阴影；
- 不使用 emoji 充当界面图标；使用本地 SVG 或 `lucide-vue-next`；
- 不加载外部 CDN 字体，使用系统中文字体栈。

### 5.2 响应式

- `>= 1200px`：展开侧栏，书架 4–5 列，创建页双栏；
- `768–1199px`：可收起侧栏，书架 3 列，创建摘要收窄；
- `< 768px`：抽屉导航，书架 2 列或列表，创建页单列；
- 最小验证宽度 375px；任何页面不得出现全局横向滚动；
- 长书名、200% 浏览器缩放和系统大字体下操作按钮仍可用。

### 5.3 动效

- hover/focus/展开过渡 150–240ms；
- 卡片不要持续浮动，不为每条列表做大幅入场动画；
- `prefers-reduced-motion: reduce` 时移除非必要位移和渐变动画；
- 加载反馈立即出现，不能出现点击后静默等待。

---

## 6. Vue 3 技术方案

### 6.1 技术栈

- Vue 3 + Composition API + `<script setup lang="ts">`
- TypeScript 严格模式
- Vite
- Vue Router
- Pinia（setup store 写法）
- Zod（前端表单结构和字段校验）
- `lucide-vue-next`（图标）
- Vitest + Vue Test Utils + jsdom
- Playwright（关键流程端到端测试）
- 原生 `fetch`，不额外引入 Axios

不引入 Tailwind、Element Plus、Ant Design Vue 或新的大型 UI 库。基础组件在项目内维护，以免视觉和行为被第三方主题绑死。

### 6.2 最终目录

```text
apps/web/
  index.html
  package.json
  package-lock.json
  tsconfig.json
  vite.config.ts
  vitest.config.ts
  src/
    main.ts
    App.vue
    env.d.ts
    router/
      index.ts
      guards.ts
      route-names.ts
    api/
      http-client.ts
      api-error.ts
      contracts.ts
    layouts/
      AppShell.vue
      ProjectShell.vue
    components/
      base/
        BaseButton.vue
        BaseDialog.vue
        BaseField.vue
        BaseIconButton.vue
        BaseStatusBadge.vue
        ErrorSummary.vue
        LoadingBlock.vue
      navigation/
        AppSidebar.vue
        ProjectPicker.vue
        StatusBar.vue
    stores/
      app.store.ts
      projects.store.ts
    features/
      library/
        api/library.api.ts
        components/LibraryToolbar.vue
        components/NovelCard.vue
        components/NovelListItem.vue
        components/RenameNovelDialog.vue
        components/DeleteNovelDialog.vue
        pages/NovelLibraryPage.vue
        types.ts
      novel-create/
        api/novel-create.api.ts
        components/CreateProgress.vue
        components/CreateSummary.vue
        components/steps/StoryStartStep.vue
        components/steps/CreativePreferenceStep.vue
        components/steps/SerializationStep.vue
        pages/NovelCreatePage.vue
        schema.ts
        store/novel-create.store.ts
        types.ts
      workbench/
        api/workbench.api.ts
        components/...
        pages/WorkbenchPage.vue
      story-brief/
        api/...
        components/...
      reader/
        api/...
        components/...
        pages/ReaderPage.vue
      memory/
        api/...
        components/...
        pages/MemoryPage.vue
      analytics/
        api/...
        components/...
        pages/AnalyticsPage.vue
      settings/
        api/...
        components/...
        pages/SettingsPage.vue
    styles/
      tokens.css
      base.css
      utilities.css
      transitions.css
    test/
      setup.ts
  e2e/
    library-create.spec.ts
    project-navigation.spec.ts
  dist/                 # 构建产物，不提交 Git
```

### 6.3 模块职责

- `pages/`：组织页面和调用 store，不写底层请求细节；
- `components/`：接收 props、发出事件，避免跨功能读取全局 DOM；
- `api/`：唯一 HTTP 入口，解析统一错误；
- `store/`：跨页面业务/UI 状态和并发状态；
- `schema.ts`：表单默认值、Zod 校验和 payload 映射；
- `router/guards.ts`：统一处理项目上下文，不在每个页面重复判断；
- `styles/`：只放令牌、基础规则和真正全局的工具类；页面样式优先使用 SFC scoped style。

### 6.4 Store 边界

`projects.store.ts` 至少包含：

- `items`、`loading`、`error`；
- `selectedProjectId`；
- `searchQuery`、`sortBy`、`viewMode`；
- `loadProjects()`、`selectProject()`、`clearSelection()`；
- `renameProject()`、`deleteProject()`；
- 从旧 `novelAgentProject` 键迁移最近项目；
- 通过 computed 完成客户端搜索和排序，不改写服务端原数组。

`novel-create.store.ts` 只管理未提交表单和步骤，不保存后端返回的完整工作台详情。创建成功后交给 projects store 和路由。

### 6.5 HTTP 客户端

统一封装：

```ts
type ApiErrorPayload = {
  error: string;
  message: string;
  details?: unknown;
};
```

要求：

- 非 2xx 解析为 `ApiError`；
- 区分网络失败、AbortError、422 字段错误、409 冲突和 5xx；
- GET 可以取消陈旧请求；POST 创建不得因路由重新渲染而自动重复；
- 组件不直接拼 URL；
- 不记录 API Key、完整正文、完整 Prompt 或完整模型输出到 console。

---

## 7. 后端改造

## 7.1 轻量书架模型

当前 `GET /api/novels` 直接返回完整 `ProjectRecord`，包含 request 和完整 brief，不适合作为书架列表。增加 `ProjectSummary`，HTTP 列表只返回书架需要的数据：

```json
{
  "items": [
    {
      "id": "novel_xxx",
      "title": "书名",
      "status": "ACTIVE",
      "confirmed": true,
      "audience_channel": "男频",
      "genre": "玄幻脑洞",
      "chapter_count": 3,
      "content_chars": 6812,
      "current_chapter": 3,
      "created_at": "2026-10-02T08:00:00Z",
      "updated_at": "2026-10-02T09:30:00Z"
    }
  ]
}
```

约束：

- `content_chars` 使用现有 `count_content_chars` 的“非空白字符数”口径，UI 必须写“字”，不要冒充分词后的词数；
- 章节数按项目所有章节记录统计，内容字符只统计非空正文；
- 列表默认按 `updated_at DESC`；
- 单次查询读取项目和章节数据后聚合，不能每个项目再发一次查询；
- 列表不返回 `request`、`brief`、人物、正文和事件；
- 详情继续由 `GET /api/novels/{id}` 返回。

建议文件改动：

- `novel_agent/features/projects/models.py`：增加 `ProjectSummary`；
- `novel_agent/features/projects/ports.py`：增加 summary 查询协议；
- `novel_agent/infrastructure/persistence/projects_store.py`：单次查询并聚合；
- `novel_agent/features/projects/service.py`：增加 `list_project_summaries()`；
- `novel_agent/interfaces/http/routes/projects.py`：`GET /api/novels` 调用 summary 方法。

如果必须保留旧 HTTP 列表兼容，先增加 `/api/novels?detail=full` 作为临时兼容，并在 `docs/API.md` 标明废弃时间；Vue 端只使用轻量默认响应。不要长期保留两个未说明的列表契约。

## 7.2 修改书名接口

新增：

```http
PUT /api/novels/{id}/metadata
Content-Type: application/json

{
  "title": "新的书名"
}
```

响应返回最新 `ProjectSummary` 或最新 `ProjectRecord`，前后端选择一种并在测试中固定；推荐返回 summary，减少载荷。

实现要求：

- 新增严格模型 `ProjectMetadataUpdate`，`title` 去首尾空白，长度 1–80，拒绝额外字段；
- service 负责业务语义，route 不直接写数据库；
- 同一事务更新 `projects.title`、`brief.selected_title`、`brief.title_candidates` 和 `updated_at`；
- 新标题放在候选列表第一位并去重，候选最多保留 6 个；
- 追加方案版本，`source="metadata_edit"`，便于审计；
- 不改变 status、confirmed、current_chapter；
- 不允许空标题；项目不存在返回 404；
- 同步更新 `docs/API.md`。

建议文件改动：

- `novel_agent/features/projects/models.py`
- `novel_agent/features/projects/service.py`
- `novel_agent/features/projects/ports.py`
- `novel_agent/infrastructure/persistence/project_setup_store.py` 或专门的原子更新方法
- `novel_agent/interfaces/http/routes/projects.py`
- `novel_agent/api.py` 的 `do_PUT` 只负责把请求分派到 projects route；不要把业务实现写入 `do_PUT`。

## 7.3 创建接口

保留 `POST /api/novels` 和现有 `NovelCreateRequest` 字段，不为新界面另造重复 DTO。前端步骤最终映射为：

```json
{
  "preferred_title": null,
  "audience_channel": "男频",
  "genre": "玄幻脑洞",
  "experiences": ["爽文"],
  "elements": ["系统"],
  "protagonist_tags": ["普通人成长"],
  "romance": null,
  "idea": "核心故事想法",
  "must_have": [],
  "nice_to_have": [],
  "exclude": [],
  "chapter_target_chars": 2200,
  "daily_chapters": 2,
  "reserve_target": 5,
  "require_plan_confirmation": true
}
```

不要让前端发送逗号拼接字符串；Vue store 在提交前把标签输入转换为去空、去重后的数组。后端校验继续作为最终权威。

## 7.4 静态站点与构建产物

Vue 构建输出为 `apps/web/dist`。修改：

- `novel_agent/bootstrap.py`：生产静态根目录指向 `apps/web/dist`；
- `novel_agent/api.py`：继续支持 Vue history 路由回退；真实缺失的 `.js/.css/.svg` 仍返回 404，不能回退 HTML；
- 若 `dist/index.html` 不存在，启动时给出明确错误和构建命令，不能用模糊 404；
- 哈希资源可使用长期缓存，`index.html` 保持 `no-store`；
- `vite.config.ts` 开发代理 `/api` 到 `http://127.0.0.1:8000`。

开发：

```powershell
# 终端 1
python -m novel_agent serve

# 终端 2
cd apps/web
npm install
npm run dev
```

生产式本地运行：

```powershell
cd apps/web
npm ci
npm run build
cd ../..
python -m novel_agent serve
```

同步修改 `run.ps1` 和 `run.cmd`：检查 `apps/web/dist/index.html`。缺失时显示上述构建方法并退出，不要在用户不知情时自动联网安装依赖。

Dockerfile 改为 Node 构建阶段 + Python 运行阶段；最终镜像只复制 `dist`，不包含 node_modules。

---

## 8. 旧代码迁移与清理

### 8.1 迁移原则

采用“先建 Vue 对等实现 → 测试 → 切换静态根 → 删除旧代码”的顺序。不能先删除旧工作台再用 TODO 占位。

迁移对照：

| 旧模块 | Vue 目标模块 |
|---|---|
| `apps/web/js/features/projects/*` | `src/stores/projects.store.ts`、`features/library/*` |
| `apps/web/js/features/novel-create/*` | `features/novel-create/*` |
| `apps/web/js/features/project-dashboard/*` | `features/workbench/*` |
| `apps/web/js/features/story-brief/*` | `features/story-brief/*` |
| `apps/web/reader-workspace.js` | `features/reader/*` |
| `app.js` 中人物/世界/时间线 | `features/memory/*` |
| `apps/web/js/features/analytics/*` | `features/analytics/*` |
| `app.js` 中设置和健康状态 | `features/settings/*`、`stores/app.store.ts` |

### 8.2 最终删除清单

Vue 版达到功能对等并切换成功后，删除：

```text
apps/web/app.js
apps/web/reader-workspace.js
apps/web/reader-workspace.css
apps/web/styles.css
apps/web/styles/features/analytics.css
apps/web/styles/features/project-dashboard.css
apps/web/styles/features/story-brief.css
apps/web/styles/features/novel-create.css
apps/web/js/core/
apps/web/js/features/
```

`apps/web/index.html` 不删除，但必须替换为 Vite 的最小入口，只保留 `#app` 和 `/src/main.ts`。

删除或重写旧 DOM 资产测试：

- 删除 `tests/test_web_project_assets.py` 中对固定 ID、旧 script 和旧 CSS 的断言；
- 后端测试只检查构建目录、history fallback、资源 404 和 content type；
- Vue 组件、payload 和交互测试迁移到 Vitest；
- 不允许为了让旧测试通过而保留无用 ID 或空脚本。

### 8.3 清理验收

执行：

```powershell
rg -n "__novelBasicSwitchView|window\.switchView|document\.querySelector|innerHTML\s*=|reader-workspace\.js|/js/features/" apps/web --glob '!dist/**'
```

预期：Vue 源码中不存在旧全局切换器、整页 innerHTML 模板和旧脚本引用。局部、已审计的 `v-html` 只有在内容经过安全处理时允许；默认不使用。

---

## 9. 实施阶段

## 阶段 A：基线与契约冻结

1. 运行现有 Python 测试并记录结果。
2. 用离线临时数据库走通：创建 → 方案确认 → 工作台 → 阅读 → 删除。
3. 保存桌面 1440×900、平板 768×1024、手机 390×844 的旧界面截图。
4. 把当前工作台所有按钮、接口、状态和错误文案列成回归表。
5. 不修改数据库内容，不调用在线模型。

完成条件：有可比较基线；现有失败测试有明确记录。

## 阶段 B：后端书架契约

1. 增加 `ProjectSummary` 与列表聚合。
2. 增加修改书名接口和原子更新。
3. 增加 route/service/store 测试。
4. 更新 `docs/API.md` 草稿，但不要提前宣称 Vue 页面已上线。

完成条件：旧项目可直接读取；不需要数据库破坏性迁移；Python 测试通过。

## 阶段 C：Vue 基础设施与外壳

1. 建立 Vite/Vue/TypeScript/Router/Pinia。
2. 建立 tokens、基础组件、HTTP 客户端和统一错误。
3. 实现 AppShell、导航、状态条和路由守卫。
4. 保持旧静态根可运行，直到 Vue build 可独立访问。

完成条件：`npm run type-check`、`npm run test`、`npm run build` 通过；`/` 重定向到 `/novels`。

## 阶段 D：书架与创建流程

1. 完成书架工具栏、卡片/列表、五种状态。
2. 完成修改书名和删除流程。
3. 完成三步表单、草稿保存、校验、错误映射和摘要。
4. 完成生成状态和成功跳转工作台。

完成条件：离线端到端创建流程通过；重复点击只产生一个项目；失败后字段保留。

## 阶段 E：现有页面 Vue 对等迁移

按以下顺序迁移，每迁移一页立即回归：

1. 创作工作台与创作方案；
2. 作品阅读与修订；
3. 长期记忆；
4. 仪表盘；
5. 系统设置。

不做视觉重设计，只将旧逻辑转换成 Vue 的 props/emits/store/API 结构。发现旧 bug 时单独记录；除非阻断本次迁移，不顺手扩大范围。

完成条件：阶段 A 的回归表全部通过。

## 阶段 F：切换、删除旧代码和文档同步

1. Python 静态根切换到 `apps/web/dist`。
2. 更新 Dockerfile、run 脚本和开发命令。
3. 删除第 8.2 节旧文件。
4. 替换旧前端资产测试。
5. 更新 `docs/USER_GUIDE.md`：导航、书架、新建三步、进入工作台、修改书名、删除、启动构建和常见问题。
6. 更新 `docs/API.md`。
7. 更新 README 的技术栈、目录和启动步骤，保持用户指南链接有效。
8. 对旧执行文档加“已被本文取代”的醒目标记，避免以后按原生 JS 继续开发。

完成条件：仓库只有一套前端；文档描述与实际运行一致。

---

## 10. 测试清单

### 10.1 Python 单元/集成测试

至少新增：

- 空项目列表返回 `{"items": []}`；
- summary 不包含完整 request/brief；
- summary 正确统计多章、空正文和非空白字符；
- summary 按更新时间降序；
- 修改书名去首尾空白；
- 修改书名同步 project 和 brief，并追加 `metadata_edit` 版本；
- 空标题、超长标题、额外字段返回 422；
- 不存在项目返回 404；
- 修改书名不改变项目状态、确认状态和章节；
- Vue history 深链返回 index.html；
- 缺失的哈希 JS/CSS 返回 404 而不是 HTML。

运行：

```powershell
python -m unittest discover -s tests -v
```

### 10.2 Vue 单元测试

至少覆盖：

- 项目 store 从旧 localStorage 键恢复并校验项目；
- 搜索、排序和网格/列表偏好；
- 卡片状态映射和计数显示；
- 无项目、无搜索结果、失败和重试；
- 三步前进/后退不会丢数据；
- 切换频道清理无效标签；
- 字段上限和数值范围；
- payload 与 `NovelCreateRequest` 字段完全一致；
- 422/409 错误映射到正确步骤；
- 提交中重复点击不产生第二个请求；
- 创建成功选择项目并跳转工作台；
- 删除当前项目后清除选择；
- 路由守卫在无项目时返回书架。

建议脚本：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "type-check": "vue-tsc -b",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test",
    "lint": "eslint ."
  }
}
```

### 10.3 端到端测试

使用离线模式和临时数据库：

1. 空书架 → 新建小说 → 三步填写 → 生成 → 工作台出现方案；
2. 创建页返回上一步和刷新后草稿仍在；
3. 书架搜索、排序、网格/列表切换；
4. 点击卡片进入正确项目；
5. 修改书名后书架和工作台一致；
6. 删除未确认草稿；
7. 删除正式项目时错误书名被拒绝、正确书名成功；
8. 刷新 `/novels/{id}/workbench` 深链仍可打开；
9. 手机宽度可打开导航、创建、返回书架和进入工作台；
10. 键盘完成书架选择和三步表单，焦点始终可见。

---

## 11. 最终验收标准

### 产品流程

- `/` 默认进入“我的小说”。
- 侧栏顺序正确，“创作工作台”位于“我的小说”之后。
- 没有项目时不能进入无上下文工作台。
- 新建流程只有一个权威表单状态，三步完整映射后端字段。
- 成功生成后自动进入对应工作台，方案已显示。
- 从书架打开任意项目时不会串书。

### 视觉与交互

- 书架具备 OpenFic 式清晰工具栏、封面卡片和宽松内容区，但没有复制其品牌。
- 375、768、1024、1440px 均无横向滚动。
- 文字对比度、标签、焦点、触控尺寸和 reduced motion 满足第 5 节要求。
- 所有异步操作都有 loading、success/error 和重复提交保护。
- 空状态告诉用户下一步做什么。

### 技术

- 前端唯一入口为 Vue 3；不存在第二套运行中的原生页面。
- 页面组件无散落请求和全局 DOM 操作。
- API、store、页面、组件、类型和样式按第 6 节分层。
- 旧代码按第 8.2 节删除，`rg` 清理检查无残留。
- Python 测试、Vue 单测、类型检查、构建和关键 E2E 全部通过。
- Docker 构建和本地 production build 均能访问 Vue 深链。
- `docs/USER_GUIDE.md`、`docs/API.md`、README 与实际一致。

### 数据与安全

- 旧 SQLite 数据直接可用；没有清库、重建或静默丢失。
- 删除规则仍由后端强制执行。
- 测试不调用在线模型，不写真实用户数据库。
- 前端日志不泄露密钥、Prompt 或完整正文。

---

## 12. Cursor 最终交付格式

Cursor 完成后必须给出：

1. 改动摘要，按前端、后端、构建、测试、文档分类；
2. 新增、修改、删除文件清单；
3. 数据库是否迁移及兼容结论；
4. 所有运行过的命令和结果；
5. 桌面、平板、手机的书架、创建三步和工作台截图；
6. 未通过的测试、未完成的验收项和具体原因；
7. 明确说明旧原生前端是否已经完全删除；如果没有，列出阻断项，不得宣称完成。

## 13. 可直接复制给 Cursor 的启动提示词

```text
请完整阅读 docs/NOVEL_LIBRARY_VUE3_CURSOR_EXECUTION.md，并严格按阶段 A→F 执行。

目标是把 Novel Agent 默认入口改成“我的小说”书架，新增三步创建小说流程，生成成功后进入对应创作工作台；前端整体迁移为 Vue 3 + TypeScript + Vite + Vue Router + Pinia。创作工作台及其他已有页面只做 Vue 功能对等迁移，不重做内容。

先建立基线和后端契约，再实现 Vue 书架与创建流程，然后迁移已有页面。只有在功能对等和测试通过后，才能删除旧 app.js、reader-workspace.js、apps/web/js 与旧 CSS。不得用 iframe、长期兼容层或 TODO 页面代替迁移。

遵守 AGENTS.md：所有用户可见流程、接口、命令和路径变化必须同步更新 docs/USER_GUIDE.md；接口同步更新 docs/API.md；README 链接保持有效。使用离线模式和临时数据库测试，不调用在线模型，不修改真实用户数据。

最后按执行书第 12 节报告文件、测试、截图、数据兼容和旧代码清理结果。
```
