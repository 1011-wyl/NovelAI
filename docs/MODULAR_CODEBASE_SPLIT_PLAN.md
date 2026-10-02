# NovelAI 功能模块化拆分实施文档

> 文档用途：指导 Cursor 在不改变现有功能的前提下，将当前代码按业务功能拆分到不同目录  
> 审计基线：2026-09-30 当前工作区  
> 本文只规划重构，不要求一次性完成全部迁移

## 1. 审计结论

NovelAI 的功能闭环已经比较完整，但代码结构仍处于“单文件实现逐渐拆出少量 Mixin/独立脚本”的中间阶段。当前问题并非功能不足，而是功能增长后，入口层、业务层、存储层和前端页面都出现了职责堆积。

最需要拆分的文件如下：

| 文件 | 约行数 | 当前承担的职责 | 主要问题 |
|---|---:|---|---|
| `novel_agent/repository.py` | 2444 | 数据库连接、迁移、项目、方案、章节、记忆、运行记录、研究、向量索引、设置、统计 | 存储职责过多，修改任何功能都需要进入同一文件 |
| `novel_agent/revision_store.py` | 1209 | 修订草稿、AI 会话、消息、修改集、回滚、正式提交 | 单个 Mixin 仍是一个完整子系统；通过方法内导入规避循环依赖 |
| `novel_agent/adapters_remote.py` | 1403 | DeepSeek、Tavily、Embedding、发布适配器、HTTP 重试、错误分类 | 多个外部供应商和传输细节相互混在一起 |
| `novel_agent/workflow.py` | 969 | 单章工作流从初始化到正式提交的全部阶段 | `_run_scoped` 过长，规划、研究、写作、审核、记忆提交难以独立测试 |
| `novel_agent/adapters.py` | 883 | Port 协议、禁用实现、离线 LLM、工厂 | 抽象接口和具体实现没有分层 |
| `novel_agent/models.py` | 549 | 全项目所有 Pydantic 模型和枚举 | 项目、方案、章节、审核、记忆、修订模型集中在一个命名空间 |
| `novel_agent/api.py` | 639 | 路由、请求解析、序列化、错误映射、静态文件、Dashboard 查询 | HTTP Handler 直接访问 Repository，应用层边界不完整 |
| `novel_agent/service.py` | 509 | 项目、方案、章节生成、记忆、统计和恢复 | `NovelAgentService` 职责过多，并通过继承 Mixin 获得修订功能 |
| `apps/web/app.js` | 1100 | 全局状态、导航、项目、方案、章节、人物、设置、用量 | 页面状态、API、渲染和事件全部耦合 |
| `apps/web/dashboard.js` | 1153 | API、筛选、图表原语、图表渲染、记录表格 | 可复用图表和 Dashboard 业务混合 |
| `apps/web/reader-workspace.js` | 1021 | 目录、编辑器、自动保存、选区、AI、版本、对话框 | 已从主文件拆出，但内部仍是一个大型 IIFE |
| `apps/web/styles.css` | 1844 | token、基础样式、Shell、表单、方案、阅读、记忆、设置、响应式 | 全局选择器和功能样式混合，且包含旧 Reader 样式 |
| `apps/web/index.html` | 376 | App Shell 和所有页面静态结构、启动兜底脚本 | 页面模板仍集中，存在内联导航脚本和手工缓存版本号 |

### 1.1 已经存在的良好边界

以下边界应该保留并继续强化：

- `ChapterWorkflow` 统一控制逐章生成状态机；
- `LLMGateway`、`SearchAdapter`、`EmbeddingGateway`、`PublisherAdapter` 已形成外部能力抽象；
- `StorySkillsRuntime` 与 `OhStoryWritingRuntime` 已隔离第三方写作规则；
- `chapter_workspace.py` 已将阅读修订编排从 `service.py` 部分拆出；
- `revision_store.py` 已将修订存储从 `repository.py` 部分拆出；
- `dashboard.js` 与 `reader-workspace.js` 已从 `app.js` 分离；
- SQLite 正式正文与记忆的原子事务边界清晰；
- tests 已覆盖方案、工作流、修订、Dashboard、外部适配和技能运行时。

这些已有拆分不应推倒重来，而应作为迁移起点。

### 1.2 当前依赖问题

1. `NovelAgentService` 继承 `ChapterWorkspaceMixin`，Mixin 隐式依赖 `repository`、`gateway`、`embedding`、`story_skills` 等字段，类型边界不清楚。
2. `SQLiteRepository` 继承 `RevisionStoreMixin`；`RevisionStoreMixin` 又在方法内部导入 `RepositoryError`，说明当前已经出现循环依赖压力。
3. `api.py` 一部分路由调用 Service，另一部分直接调用 Repository，业务入口不统一。
4. `scheduler.py` 通过 `service.repository.list_projects()` 越过 Service 边界。
5. `bootstrap.py` 通过检测 `_on_call`、`_on_usage` 私有属性连接统计回调，供应商实现细节泄漏到装配层。
6. 前端 `app.js`、`dashboard.js`、`reader-workspace.js` 各自维护 API、状态和 DOM helper，缺少共享核心。
7. 前端通过 `window.switchView`、`window.placeBookPicker`、`window.ReaderWorkspace` 等全局变量通信，模块加载顺序成为隐含依赖。
8. `styles.css` 中仍保留 Reader 样式，同时另有 `reader-workspace.css`，容易发生覆盖顺序问题。
9. 静态文件不存在时 `_serve_static` 会回退到 `index.html`，缺失的 JS/CSS 也可能得到 200 HTML，导致难定位的前端语法错误。

## 2. 当前功能模块盘点

拆分后必须完整保留以下能力。

### 2.1 项目与创作方案

- 从频道、题材、标签、约束和核心想法创建作品；
- 离线或 DeepSeek 生成创作方案；
- 用户指定书名；
- 方案手工编辑；
- 按反馈整体/局部重生成；
- 方案版本对比与恢复；
- 确认、暂停、继续、归档和删除作品。

### 2.2 章节生成

- 精简章节规划；
- 现实知识调研；
- 上一章衔接写作；
- oh-story 题材卡和去 AI 味；
- 八维可读性审核；
- Story Skills 连续性审核；
- FAILED 重试与已保存计划复用；
- 正式正文、时间线和人物记忆原子提交；
- 储备补充和本地调度。

### 2.3 阅读与修订

- 三栏工作台；
- READY 章节标题与正文编辑；
- 工作草稿自动保存；
- 版本历史恢复为草稿；
- 选区交给 AI；
- 顾问、共创、编辑模式；
- diff、批准、拒绝和回滚；
- 正式修订提交；
- 后续章节 RESET_ARCHIVE 与安全重置。

### 2.4 长期记忆与检索

- 重要人物档案；
- 世界硬规则；
- 时间线与伏笔；
- 研究资料与可信度；
- 语义索引与召回；
- 旧作品人物档案重建。

### 2.5 Dashboard 与系统能力

- 写作活动、热力日历和字数趋势；
- LLM 调用次数、Token、延迟、模型分布；
- 调用记录筛选、排序和分页；
- 本地设置和外部能力 readiness；
- CLI、HTTP 服务、agent worker、scheduler worker；
- 离线模式、DeepSeek、Tavily、OpenAI-compatible Embedding、Mock Publisher。

## 3. 拆分原则

### 3.1 重构目标

- 以业务能力为第一层目录，不以“所有 service 放一起”作为唯一分类；
- 业务模块不能直接依赖具体 DeepSeek、Tavily 或 SQLite 细节；
- HTTP、CLI、worker 只是接口层，不承载业务规则；
- 跨表原子事务继续留在同一个 SQLite transaction 中，不能为追求文件拆分破坏一致性；
- 保留现有公共 import 路径作为过渡兼容层；
- 每次迁移一个垂直模块，测试通过后再继续；
- 本次重构默认不修改 API 路径、JSON 字段、数据库结构和页面行为。

### 3.2 禁止事项

- 禁止一次性移动所有文件后再集中修复 import；
- 禁止同时进行 FastAPI、SQLAlchemy、React/Vue 等技术栈迁移；
- 禁止在结构重构中顺手改变工作流、提示词或质量门槛；
- 禁止删除现有兼容入口，直到所有调用和测试都已迁移；
- 禁止把一个超大文件机械切成多个仍然互相随意访问内部变量的文件；
- 禁止通过 `git reset --hard`、覆盖文件或清空工作区处理当前未提交改动。

## 4. 目标目录结构

目标采用“业务功能优先 + 基础设施隔离”的混合结构。

```text
novel_agent/
  core/
    ids.py
    time.py
    errors.py
    text.py
    result.py

  features/
    story_design/
      models.py
      requirements.py
      tags.py
      service.py
    projects/
      models.py
      service.py
    chapters/
      models.py
      service.py
      workflow/
        context.py
        orchestrator.py
        planning.py
        research.py
        drafting.py
        review.py
        memory_commit.py
        semantic_index.py
    revisions/
      models.py
      errors.py
      diff.py
      service.py
    memory/
      models.py
      service.py
      context_builder.py
    analytics/
      models.py
      service.py
    settings/
      service.py

  ports/
    llm.py
    search.py
    embedding.py
    publishing.py
    telemetry.py

  integrations/
    llm/
      disabled.py
      offline.py
      deepseek.py
      http_transport.py
      errors.py
    search/
      disabled.py
      tavily.py
    embedding/
      disabled.py
      openai_compatible.py
    publishing/
      mock.py
      fanqie.py
    skills/
      story_skills.py
      writing_skills.py
    factories.py

  infrastructure/
    config/
      env.py
      settings.py
    persistence/
      sqlite/
        database.py
        migrations.py
        projects_store.py
        briefs_store.py
        chapters_store.py
        revisions/
          drafts_store.py
          sessions_store.py
          changes_store.py
          commit_store.py
        memory_store.py
        runs_store.py
        research_store.py
        semantic_store.py
        settings_store.py
        analytics_store.py
        facade.py
    telemetry/
      context.py
      recorder.py

  interfaces/
    http/
      context.py
      request.py
      response.py
      errors.py
      static_files.py
      server.py
      routes/
        system.py
        projects.py
        story_design.py
        chapters.py
        revisions.py
        memory.py
        analytics.py
        settings.py
    cli/
      parser.py
      commands.py
    workers/
      scheduler.py

  bootstrap.py

  # 过渡兼容 Facade；迁移期保留原 import 路径
  models.py
  adapters.py
  adapters_remote.py
  repository.py
  service.py
  api.py
  workflow.py
```

前端目标结构：

```text
apps/web/
  index.html
  main.js

  core/
    api-client.js
    app-store.js
    events.js
    dom.js
    format.js
    errors.js

  shell/
    app-shell.js
    navigation.js
    book-picker.js
    notifications.js
    busy-state.js

  ui/
    dialog.js
    icons.js
    status.js
    charts/
      line-chart.js
      bar-chart.js
      donut-chart.js
      heatmap.js
      tooltip.js

  features/
    project-dashboard/
      view.js
      api.js
      template.js
    novel-create/
      view.js
      api.js
      tags.js
      template.js
    story-brief/
      view.js
      editor.js
      versions.js
      api.js
      template.js
    chapter-production/
      actions.js
      chapter-list.js
      pipeline.js
      api.js
    reader/
      workspace.js
      state.js
      api.js
      chapter-toc.js
      editor.js
      autosave.js
      selection.js
      versions.js
      assistant.js
      changes.js
      template.js
    memory/
      view.js
      characters.js
      world.js
      timeline.js
      research.js
      api.js
      template.js
    analytics/
      view.js
      data.js
      writing.js
      llm.js
      records.js
      template.js
    settings/
      view.js
      runtime.js
      usage-period.js
      api.js
      template.js

  styles/
    tokens.css
    reset.css
    base.css
    shell.css
    forms.css
    components.css
    responsive.css
    features/
      project-dashboard.css
      novel-create.css
      story-brief.css
      chapter-production.css
      reader.css
      memory.css
      analytics.css
      settings.css
```

测试目标结构：

```text
tests/
  helpers/
    factories.py
    fakes.py
    database.py
  unit/
    story_design/
    chapters/
    revisions/
    memory/
    integrations/
  integration/
    persistence/
    workflows/
    http/
  regression/
    test_existing_public_api.py
```

## 5. 后端模块职责与公开接口

### 5.1 `core`

只存放不属于任何业务功能的稳定基础：

- ID 与 UTC 时间生成；
- 文本换行规范化和字数统计；
- 通用领域错误基类；
- 通用 Result/分页结构。

`core` 不允许导入 `features`、`integrations`、`infrastructure` 或 `interfaces`。

### 5.2 `features/story_design`

从当前文件迁移：

- `NovelCreateRequest`、`CharacterProfile`、`CreativeBrief`、`BriefRegenerateRequest`；
- `tags.py`；
- `requirements.py`；
- `create_novel` 中与方案生成有关的部分；
- `update_draft_brief`、`regenerate_draft_brief`、`restore_draft_brief`。

公开服务：

```python
class StoryDesignService:
    def create_story(self, request: NovelCreateRequest) -> ProjectRecord: ...
    def update_brief(self, project_id: str, brief: CreativeBrief) -> ProjectRecord: ...
    def regenerate_brief(self, project_id: str, change: BriefRegenerateRequest) -> ProjectRecord: ...
    def restore_brief(self, project_id: str, version: int) -> ProjectRecord: ...
```

### 5.3 `features/projects`

负责项目生命周期，不负责生成具体正文：

- `ProjectStatus`、`ProjectRecord`；
- 项目列表和详情聚合；
- 确认、暂停、继续、归档和删除；
- 项目 readiness 与下一步状态。

公开服务：

```python
class ProjectService:
    def list_projects(self) -> list[ProjectRecord]: ...
    def get_detail(self, project_id: str) -> ProjectDetail: ...
    def confirm(self, project_id: str) -> ProjectRecord: ...
    def pause(self, project_id: str) -> ProjectRecord: ...
    def resume(self, project_id: str) -> ProjectRecord: ...
    def delete(self, project_id: str, confirmation_title: str | None) -> None: ...
```

### 5.4 `features/chapters`

负责章节计划、生成、审核、重做和储备：

- `ChapterPlan`、`ChapterRecord`、`ChapterStatus`；
- Review/Readability/Continuity 模型；
- `generate_next_chapter`、`fill_reserve`、`rework_chapter`、异常恢复；
- `ChapterWorkflow`。

对外只暴露应用服务和 orchestrator，不暴露 workflow stage 内部状态。

```python
class ChapterService:
    def list_chapters(self, project_id: str) -> list[ChapterRecord]: ...
    def generate_next(self, project_id: str) -> WorkflowResult: ...
    def fill_reserve(self, project_id: str, limit: int | None) -> list[WorkflowResult]: ...
    def rework(self, project_id: str, number: int, feedback: str) -> ProjectRecord: ...
    def recover(self, project_id: str) -> ProjectRecord: ...
```

### 5.5 `features/revisions`

替代当前 `ChapterWorkspaceMixin`，使用显式组合：

- 工作台聚合数据；
- 工作草稿；
- AI 会话、消息和修改集；
- diff、批准、拒绝、回滚；
- 正式修订编排；
- 版本恢复。

```python
class RevisionService:
    def get_workspace(...): ...
    def save_draft(...): ...
    def discard_draft(...): ...
    def commit(...): ...
    def restore_version(...): ...
    def create_session(...): ...
    def send_message(...): ...
    def approve_change(...): ...
    def reject_change(...): ...
    def rollback_session(...): ...
```

`NovelAgentService` 在过渡期委托给 `RevisionService`，不再继承 Mixin。

### 5.6 `features/memory`

负责：

- `CharacterRecord`、`CharacterMemoryUpdate`、`WorldFactRecord`；
- MemoryManager 上下文预算；
- 人物档案重建；
- 世界、时间线、伏笔、研究资料查询；
- 语义检索应用服务。

Embedding 的具体实现仍放在 integrations；Memory 服务只依赖 `EmbeddingPort`。

### 5.7 `features/analytics`

负责：

- 写作活动聚合；
- LLM 调用统计；
- 调用记录筛选、排序和分页；
- Token 日统计。

这是推荐首先执行的试点模块，因为它主要是只读查询，现有测试覆盖较完整，不涉及章节正式提交事务。

## 6. Persistence 拆分

### 6.1 数据库基础设施

`database.py` 只提供：

```python
class SQLiteDatabase:
    path: Path
    def connect(self) -> sqlite3.Connection: ...
    @contextmanager
    def connection(self): ...
    @contextmanager
    def transaction(self): ...
```

`migrations.py` 负责：

- `SCHEMA_VERSION`、`DASHBOARD_MIGRATION_VERSION`；
- v1–v5 现有 SQL；
- idempotent 列检查与回填；
- writing activity backfill。

拆分迁移代码时不得改变任何表、列、索引、默认值或回填结果。

### 6.2 Store 划分

| Store | 从当前 `repository.py` 迁移的内容 |
|---|---|
| `ProjectsStore` | project CRUD、状态、删除 |
| `BriefsStore` | brief versions、保存和恢复 |
| `ChaptersStore` | chapter CRUD、生成草稿版本、READY 提交、重做 |
| `MemoryStore` | characters、world facts、timeline、foreshadows |
| `RunsStore` | runs、diagnostics、events、review reports |
| `ResearchStore` | research sources |
| `SemanticStore` | pending inputs、upsert、search、count、delete |
| `SettingsStore` | setting CRUD/list |
| `AnalyticsStore` | token usage、writing activity、Dashboard queries |
| `RevisionDraftsStore` | edit draft CRUD、working copy |
| `AssistantStore` | sessions、messages、changes、approve/reject/rollback |
| `RevisionCommitStore` | version restore、正式修订跨表事务 |

### 6.3 跨模块原子事务

以下操作不能被机械拆成多个独立 Store 调用后分别提交：

- `create_project` 同时建立项目、人物和世界规则；
- `commit_ready_chapter` 同时提交正文、版本、时间线、人物和审核；
- `rework_chapter` 同时回滚章节及派生数据；
- `commit_chapter_revision` 同时提交修订、记忆并重置后续章节；
- AI change approve 同时更新 change 状态和工作草稿。

这些事务放入专用 transaction service/store，并由同一个 `sqlite3.Connection` 完成。文件拆分不能改变事务边界。

### 6.4 兼容 Facade

迁移期间保留：

```python
from novel_agent.repository import SQLiteRepository, SCHEMA_VERSION
```

`SQLiteRepository` 改为组合各 Store，并显式委托旧方法。不要继续增加新的 Mixin。所有新业务代码直接依赖对应 Store Protocol；旧测试和入口逐步迁移后再精简 Facade。

## 7. Workflow 拆分

当前 `_run_scoped` 包含约 580 行连续流程。拆分采用“一个 orchestrator + 多个 stage”，而不是让 stage 互相直接调用。

### 7.1 `ChapterWorkflowContext`

集中保存一次运行的可变状态：

- project、chapter、run_id、chapter_number；
- previous chapters 与 memory context；
- plan、research sources、draft content；
- review reports、character updates；
- workflow events。

Context 不能包含数据库连接，也不能作为长期持久化对象。

### 7.2 Stage 顺序

```text
Prepare
→ BuildContext
→ Plan
→ Research
→ Draft
→ ProsePolish
→ ReadabilityReview
→ ContinuityReview
→ ExtractMemory
→ CommitReady
→ SemanticIndex
```

每个 stage：

- 接收 context 和明确依赖；
- 返回更新后的 context 或抛出已有领域错误；
- 不擅自调用下一个 stage；
- 不吞掉外部 API 错误；
- 继续通过统一 event emitter 写运行事件。

`ChapterWorkflow.run(project_id)` 的公开行为和 `WorkflowResult` 保持不变。

## 8. 外部适配器拆分

### 8.1 Ports

从 `adapters.py` 迁出协议：

- `LLMGateway` → `ports/llm.py`
- `SearchAdapter` → `ports/search.py`
- `EmbeddingGateway` → `ports/embedding.py`
- `PublisherAdapter` → `ports/publishing.py`

业务 feature 只能导入 Port，不得导入 DeepSeek/Tavily 类。

### 8.2 具体实现

- `OfflineLLMGateway` → `integrations/llm/offline.py`
- `DisabledRemoteGateway` → `integrations/llm/disabled.py`
- `DeepSeekLLMGateway` → `integrations/llm/deepseek.py`
- HTTP retry、JSON 提取和 provider errors → `integrations/llm/http_transport.py`、`errors.py`
- `TavilySearchAdapter` → `integrations/search/tavily.py`
- `OpenAICompatibleEmbeddingGateway` → `integrations/embedding/openai_compatible.py`
- `MockPublisher`、`FanqiePublisherAdapter` → publishing 子目录。

### 8.3 工厂

`integrations/factories.py` 公开：

```python
build_llm_gateway(settings, telemetry_sink)
build_search_adapter(settings)
build_embedding_gateway(settings)
build_publisher(settings)
```

回调通过公开构造参数注入，不再由 `bootstrap.py` 检测 `_on_call` 或 `_on_usage` 私有属性。

## 9. Application Service 拆分

用组合替代继承：

```python
@dataclass(slots=True)
class ApplicationServices:
    projects: ProjectService
    story_design: StoryDesignService
    chapters: ChapterService
    revisions: RevisionService
    memory: MemoryService
    analytics: AnalyticsService
    settings: SettingsService
```

迁移期的 `NovelAgentService` 作为兼容 Facade：

```python
class NovelAgentService:
    def create_novel(self, request):
        return self.services.story_design.create_story(request)

    def generate_next_chapter(self, project_id):
        return self.services.chapters.generate_next(project_id)
```

禁止 Feature Service 通过 `service.repository` 访问整个仓库。每个 Service 只注入它需要的 Store Protocol 和外部 Port。

`LocalScheduler` 改为依赖：

- `ProjectQueryService.list_runnable_projects()`；
- `ChapterService.fill_reserve()`。

不再访问 `service.repository`。

## 10. HTTP 层拆分

继续使用标准库 `BaseHTTPRequestHandler`，本次不迁移 FastAPI。

### 10.1 Router

实现轻量路由注册，不把新的框架写进项目：

```python
@dataclass(frozen=True)
class Route:
    method: str
    pattern: Pattern[str]
    handler: Callable[[HttpContext, Match[str], HttpRequest], HttpResponse]
```

`NovelAgentHandler` 只负责：

- OPTIONS/GET/POST/PUT/DELETE 转换为统一 request；
- 调用 router；
- 序列化 response；
- 未命中 API 时交给 static server；
- 使用统一 error mapper。

### 10.2 路由分组

| 路由文件 | 当前接口范围 |
|---|---|
| `system.py` | health、tags、publishing readiness |
| `projects.py` | `/api/novels`、confirm/pause/resume/recover/delete |
| `story_design.py` | brief update/regenerate/restore/versions |
| `chapters.py` | chapters、runs、rework、run events |
| `revisions.py` | workspace、edit-draft、versions restore、assistant sessions/changes |
| `memory.py` | characters、world、research、semantic search/rebuild |
| `analytics.py` | writing、LLM stats、records、usage |
| `settings.py` | runtime readiness 和本地 preferences |

路由 handler 只调用 Application Service，不直接执行 SQL 或调用 Repository。

### 10.3 静态文件

`static_files.py` 保留路径越界保护，并修复资源回退规则：

- `/` 和前端页面路由可以回退 `index.html`；
- 缺失的 `.js`、`.css`、图片和字体返回 404，不能返回 HTML 200；
- 嵌套目录和 ES modules 必须正常返回正确 MIME。

## 11. 前端拆分

### 11.1 使用原生 ES modules

不引入 npm 构建工具。将入口改为：

```html
<script type="module" src="/main.js"></script>
```

静态服务器已经支持嵌套文件和 JavaScript MIME。迁移完成后移除：

- `window.switchView`
- `window.placeBookPicker`
- `window.ReaderWorkspace`
- Dashboard 的全局对象
- `index.html` 中的内联导航兜底脚本
- 手工 `?v=rrN` 缓存版本号；当前服务已对 JS/CSS 设置 `no-store`。

### 11.2 共享核心

`core/api-client.js` 统一：

- JSON headers；
- 非 2xx 错误解析；
- AbortSignal；
- 409/422 等结构化错误；
- 不负责 toast 或页面跳转。

`core/app-store.js` 只保存跨页面状态：

- health；
- projects；
- selectedProjectId；
- selectedView。

章节编辑器、Dashboard 筛选、方案表单等状态留在各 Feature 内。

`core/events.js` 只定义有限事件：

- `project:selected`
- `project:updated`
- `chapters:changed`
- `view:activated`
- `settings:changed`

禁止使用任意字符串作为隐式事件协议。

### 11.3 `app.js` 拆分映射

| 当前行段/函数 | 目标模块 |
|---|---|
| `api`、`escapeHtml`、日期/数字 helper | `core` |
| `notify`、`busy` | `shell/notifications.js`、`busy-state.js` |
| `switchView`、sidebar | `shell/navigation.js`、`app-shell.js` |
| Book picker | `shell/book-picker.js` |
| `refresh/loadSelected/renderProjectSelect` | `features/projects` |
| `renderBrief`、编辑、版本比较 | `features/story-brief` |
| `renderChapters`、generate、pipeline | `features/chapter-production` |
| character functions | `features/memory/characters.js` |
| world/timeline/research | `features/memory` 对应文件 |
| tags/create form | `features/novel-create` |
| runtime/settings/usage period | `features/settings` |

迁移完成后 `main.js` 只负责初始化、注册 Feature、加载首屏和销毁。

### 11.4 Reader 工作台拆分映射

| 当前职责 | 目标文件 |
|---|---|
| mount/init/destroy | `reader/workspace.js` |
| 工作台本地状态 | `reader/state.js` |
| workspace HTTP | `reader/api.js` |
| 章节筛选和列表 | `reader/chapter-toc.js` |
| 标题/正文/字数 | `reader/editor.js` |
| debounce、flush、conflict | `reader/autosave.js` |
| 选区和快捷菜单 | `reader/selection.js` |
| 版本列表和恢复 | `reader/versions.js` |
| AI session/message/composer | `reader/assistant.js` |
| diff 卡片、approve/reject/rollback | `reader/changes.js` |
| DOM 静态结构 | `reader/template.js` |

各模块只通过显式 controller 和回调通信，不能直接修改其他模块私有变量。

### 11.5 Dashboard 拆分映射

- 图表基础设施迁入 `ui/charts`；
- API 和 AbortController 迁入 `analytics/data.js`；
- writing、LLM、records 各自管理渲染和筛选；
- `analytics/view.js` 只管理 tab 激活、初始化和刷新。

图表模块输入纯 model，不能直接请求 API。

### 11.6 HTML 与 CSS

`index.html` 最终只保留 App Shell、页面挂载点、全局 flash/busy/dialog host 和 module 入口。各 Feature 的静态 DOM 由 `template.js` 创建，动态用户内容必须使用 `textContent` 或显式转义。

CSS 拆分时：

1. 先移动 token、reset、base、shell、forms；
2. 再按 Feature 移动选择器；
3. 迁移 Reader 后删除 `styles.css` 中 943–1001 附近的旧 Reader 规则；
4. 每次只移动一组选择器，并在 320/375/414/768/1024/1440px 验证；
5. 保持现有选择器优先级，不使用大量 `!important` 修复迁移问题。

## 12. 兼容层与导入规则

迁移期间以下导入必须继续工作：

```python
from novel_agent.models import NovelCreateRequest, ChapterRecord
from novel_agent.adapters import OfflineLLMGateway, build_gateway
from novel_agent.repository import SQLiteRepository, SCHEMA_VERSION
from novel_agent.service import NovelAgentService
from novel_agent.api import AppContext, NovelAgentHandler, serve
from novel_agent.workflow import ChapterWorkflow, WorkflowBlocked
```

原文件逐步变成 re-export/Facade，不允许同时保留两套业务实现。

目标依赖方向：

```text
core
  ↑
features + ports
  ↑
application orchestration
  ↑
interfaces

infrastructure/integrations ──实现──> ports
bootstrap ──组装所有依赖──> application + interfaces
```

禁止方向：

- feature 导入 HTTP Handler；
- feature 导入具体 SQLite Store；
- feature 导入 DeepSeek/Tavily；
- persistence 导入 Service；
- route 直接执行 SQL；
- scheduler 访问 service 内部 repository。

## 13. 分阶段迁移计划

### 阶段 0：冻结基线

1. 执行 `git status --short`，确认当前已有修改归属。
2. 当前审计发现阅读工作台、样式、用户指南和实施文档存在已暂存改动；先由用户保存为 commit 或可恢复快照。
3. 不 reset、不覆盖、不将这些改动当作待清理文件。
4. 记录测试基线：当前 `python -m unittest discover -s tests -v` 为 64/64 通过。
5. `ruff` 当前未安装，不能把 lint 写为基线通过。

验收：工作区成果可恢复，64 个测试保持通过。

### 阶段 1：基础骨架与兼容测试

1. 创建 `core`、`features`、`ports`、`integrations`、`infrastructure`、`interfaces` 包。
2. 增加 regression test，验证旧 import 路径。
3. 只迁移 `text_metrics.py`、`text_normalize.py`、ID/时间 helper 等低风险纯函数。
4. 原文件保留 re-export。

验收：功能、API 和数据库完全不变。

### 阶段 2：Dashboard 试点

1. 将 Dashboard SQLite 查询迁入 `AnalyticsStore`。
2. 建立 `AnalyticsService`，API 不再直接访问 repository。
3. 将 dashboard routes 移入独立路由模块。
4. 前端拆出 charts、data、writing、llm、records。
5. 保持现有 `test_dashboard.py` 全部通过，并补 route/service 测试。

选择它作为试点的原因：只读为主、事务风险低、前后端边界完整、现有测试较强。

### 阶段 3：外部适配器

1. 先迁 Port 协议并由 `adapters.py` re-export。
2. 分离 Offline、Disabled、DeepSeek、Tavily、Embedding、Publisher。
3. 把公共 HTTP 重试和错误分类从 provider 类中提取。
4. 更新 bootstrap 使用公开构造参数注入 telemetry sink。

验收：DeepSeek、Research/Embedding 和 Workflow 测试全部通过。

### 阶段 4：项目与故事方案

**状态：已完成**（详见 `docs/PROJECT_STORY_DESIGN_SPLIT_PLAN.md` 实施完成记录）

1. 拆分 story design 和 project models/service/store。
2. API 路由迁入 projects/story_design。
3. 前端拆出 novel-create、story-brief、project-dashboard。
4. `NovelAgentService` 继续委托以保持旧接口。

验收：创建、方案编辑、重生成、版本恢复、确认和删除行为不变。

### 阶段 5：Memory、Research 与 Semantic

**状态：未开始**（Projects / Story Design 完成后的推荐下一模块）

1. 拆分 memory models/context builder/service/store。
2. 拆分 research 和 semantic stores。
3. 前端拆出人物、世界、时间线、研究页面。
4. 保留章节正式提交时同一事务更新 memory 的能力。

验收：Memory、Story Skills、Research/Embedding 相关测试通过。

### 阶段 6：阅读与修订

1. 将 `ChapterWorkspaceMixin` 改为显式 `RevisionService`。
2. 将 `RevisionStoreMixin` 拆为 drafts、sessions、changes、commit stores。
3. 消除方法内 `from novel_agent.repository import RepositoryError`。
4. 拆 reader-workspace.js 为 controller、editor、autosave、selection、assistant、changes、versions。
5. 合并/删除重复 Reader CSS。

验收：修订闭环测试全部通过，页面手工验收无回归。

### 阶段 7：章节工作流

这是最后拆分的核心模块。

1. 先建立 characterization tests，固定每个节点、事件顺序和失败状态。
2. 抽出 `ChapterWorkflowContext`。
3. 每次只提取一个 stage，`ChapterWorkflow.run` 保持入口不变。
4. 最后拆 ChapterService 和章节 stores。
5. scheduler/worker 改用明确服务接口。

验收：所有 workflow、writing skills、story skills 和 DeepSeek workflow 测试通过。

### 阶段 8：HTTP、Shell 与收尾

1. 完成 route registry 和错误映射拆分。
2. API/CLI/worker 移入 interfaces，同时保留原入口 re-export。
3. 前端切换原生 ES modules，移除 window globals 和内联脚本。
4. 拆分剩余 CSS 和 HTML 模板。
5. 修复静态资源 404 行为。
6. 更新 README 目录、`docs/ARCHITECTURE.md` 和相关开发文档。

## 14. 测试拆分与新增覆盖

### 14.1 共享测试工具

当前多个测试重复创建 TemporaryDirectory、SQLiteRepository 和 NovelAgentService。新增：

- `tests/helpers/database.py`：临时数据库 context；
- `tests/helpers/factories.py`：project、READY chapter、service；
- `tests/helpers/fakes.py`：Fake LLM/Search/Embedding。

继续兼容 `unittest`，本次不要求迁移 pytest fixture。

### 14.2 每阶段必须运行

```powershell
python -m unittest discover -s tests -v
```

若安装开发依赖，再运行：

```powershell
python -m ruff check novel_agent tests
python -m pyright novel_agent
```

未安装时必须报告“未安装/未执行”，不能声称通过。

### 14.3 新增测试

- 兼容 import 测试；
- 每个 Feature Service 的单元测试；
- Store 集成测试；
- 路由到 Service 的 handler 测试；
- Workflow 节点和事件顺序 characterization；
- 静态 JS/CSS 缺失返回 404；
- 前端模块初始化/销毁的最小浏览器手工清单。

### 14.4 前端回归清单

- 所有导航页可以进入和返回；
- 项目切换同步刷新当前页面；
- 创建、方案编辑和生成操作正常；
- Reader 自动保存、AI、diff、提交和历史恢复正常；
- Memory 人物列表/详情和移动端返回正常；
- Dashboard 图表、筛选、排序、分页正常；
- Settings 保存和 readiness 正常；
- 320、375、414、768、1024、1440px 无新增布局问题。

## 15. Git 与回滚策略

每阶段采用小提交，建议顺序：

1. 添加新模块和兼容 re-export；
2. 迁移一组调用方；
3. 删除旧实现；
4. 更新测试和架构文档。

一次提交只处理一个明确模块，禁止将“目录移动、功能修改、UI 重做”混在同一提交中。

推荐提交粒度示例：

```text
refactor(analytics): extract sqlite analytics store
refactor(api): route dashboard requests through analytics service
refactor(web): split dashboard charts from page controller
docs(architecture): document analytics module boundary
```

如果阶段测试失败，只回退当前小阶段；不得清空用户已有的未提交改动。

## 16. 文档同步

纯目录和代码组织变化不需要修改用户操作说明，但必须更新：

- `README.md` 的目录树；
- `docs/ARCHITECTURE.md` 的依赖图和运行链路；
- 开发/实施文档中的旧文件路径。

只有拆分过程中同时改变用户可见页面、接口、配置、命令或工作流时，才必须按项目约定同步更新 `docs/USER_GUIDE.md`。

## 17. 代码卫生单独处理

审计发现以下内容已被 Git 跟踪，但不属于业务模块拆分：

- `.idea/*`
- `_tmp_schema5_check.py`

不要在功能移动提交中顺手删除。单独确认文件归属后，再用独立 cleanup 提交处理，并视需要把 `.idea/`、`_tmp_*` 加入 `.gitignore`。

`__pycache__`、`.pytest_cache`、`*.egg-info` 和数据库文件已经属于生成物/忽略项，不进入目标目录设计。

## 18. Definition of Done

模块化拆分完成必须满足：

- 所有业务能力都能在目标功能目录中找到唯一实现；
- 顶层兼容文件只做 re-export 或 Facade，不再包含重复业务逻辑；
- `repository.py` 不再包含迁移、全部 Store 和 Dashboard SQL；
- `api.py` 不再包含全部路由，也不直接访问 Repository；
- `service.py` 不再继承功能 Mixin；
- `adapters.py` 只保留兼容导出/工厂，具体供应商位于 integrations；
- `workflow.py` 只保留兼容入口，章节阶段位于 workflow 子目录；
- `app.js`、`dashboard.js`、`reader-workspace.js` 被 ES modules 取代；
- `styles.css` 不再包含所有功能页面样式；
- 数据库 schema、API 路径、JSON 结构和用户操作行为保持兼容；
- 64 个现有测试继续通过，并增加模块/路由/兼容测试；
- README 与 ARCHITECTURE 反映真实目录；
- 无循环导入、无通过私有字段装配依赖、无 route 直接 SQL；
- 当前阅读工作台成果和用户数据没有因重构丢失。

## 19. 推荐起点

Analytics / Dashboard 与 External Integrations、Projects / Story Design 已完成主体拆分。

下一实施模块应为：

> **Memory / Research / Semantic（总路线阶段 5）**

不要跳过它直接拆 `ChapterWorkflow`。执行顺序见上文阶段 5，并继续遵守：不覆盖工作区无关成果、保留兼容 Facade、事务边界不变。

