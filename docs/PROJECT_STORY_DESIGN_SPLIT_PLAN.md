# NovelAI 项目与故事方案模块前后端详细拆分实施文档

> 文档用途：交给 Cursor 分阶段执行“项目生命周期 + 故事方案”模块化拆分
>
> 审计基线：2026-10-01 当前工作区
>
> 上游路线：`docs/MODULAR_CODEBASE_SPLIT_PLAN.md` 阶段 4
>
> 前置状态：Analytics / Dashboard 和 External Integrations / Provider Adapters 已完成主体拆分
>
> 本文只规划结构重构；默认不改变数据库、HTTP、页面文案、用户操作和模型提示词

## 1. 结论：下一个应拆分的模块

接下来应拆分：

> **Projects / Story Design（项目生命周期 / 故事方案）垂直模块**

这是总拆分路线中的阶段 4，位于已经实施的 Analytics 和外部适配器之后，位于 Memory、阅读修订和章节工作流之前。

选择它作为下一模块的原因：

1. 创建小说、修改方案、确认方案、暂停、继续和删除已经形成完整的前后端闭环。
2. 当前相关代码集中在 `models.py`、`service.py`、`repository.py`、`api.py` 和 `app.js`，职责边界清楚，适合复用 Analytics 已验证的 Store → Service → Route → Frontend Feature 模式。
3. 它能继续缩小四个主单体文件，但不需要先拆高风险的 `ChapterWorkflow`。
4. 现有 `test_brief_iteration.py`、`test_requirements.py`、`test_workflow.py` 和 DeepSeek 测试已经固定了大量行为。
5. 该模块包含两条重要跨表事务，适合在进入更复杂的 Memory 和 Revision 拆分前，先建立可靠的事务组织方式。

本阶段完成后，推荐继续执行总路线阶段 5：Memory / Research / Semantic；不要跳过它直接拆 `workflow.py`。

## 2. 本次目标与非目标

### 2.1 必须完成的目标

后端：

- 把项目、方案相关模型从总 `models.py` 迁入独立 Feature；
- 把标签目录与需求冲突检查迁入 `features/story_design`；
- 建立 `ProjectService` 和 `StoryDesignService`；
- 把项目和方案数据库操作从 `repository.py` 迁入独立 Store；
- 明确保留创建项目、保存方案时的跨表原子事务；
- 把项目/方案 HTTP 路由从 `api.py` 迁入独立 route 模块；
- 让 `NovelAgentService` 和 `SQLiteRepository` 只保留兼容委托；
- 保留 `novel_agent.models`、`novel_agent.requirements`、`novel_agent.tags` 的旧导入路径。

前端：

- 把创建小说表单拆为 `novel-create` Feature；
- 把方案展示、编辑、重新生成、版本对比和恢复拆为 `story-brief` Feature；
- 把项目标题、状态和生命周期操作拆为 `project-dashboard` Feature；
- 新模块使用 ES Modules，不再把新增逻辑写回 `app.js`；
- 保持现有 DOM ID、class、中文文案、确认弹窗和项目选择行为；
- 将对应 CSS 从全局 `styles.css` 迁入 Feature CSS，但不做视觉重设计。

### 2.2 本次明确不做

- 不修改 SQLite schema、表名、列名、索引、外键或 schema version；
- 不修改任何现有 HTTP 路径、方法、状态码或 JSON 字段；
- 不修改 DeepSeek / Offline 的方案生成提示词和返回模型；
- 不改变方案确认前后可编辑规则；
- 不改变删除正式作品时必须输入完整书名的安全规则；
- 不把方案确认后的修改扩展为新功能；
- 不拆章节生成、Reader、Memory、Research、Semantic 或 Settings；
- 不把 `NovelAgentHandler` 改成 FastAPI；
- 不引入 React、Vue、npm bundler、ORM 或依赖注入框架；
- 不顺手删除兼容 Facade；
- 不改页面视觉、文案、按钮顺序或响应式断点；
- 不清理当前工作区中与本模块无关的 Reader、Analytics 或文档修改。

### 2.3 本阶段的代码卫生边界

允许删除的旧代码仅限：

- 已由新模块接管、全仓无调用且有测试证明的项目/方案实现；
- `repository.py`、`service.py`、`api.py`、`app.js` 中已被兼容委托替代的同一份业务逻辑；
- `styles.css` 中已经原样迁入 Feature CSS 的重复选择器。

以下内容即使看起来旧，也不能在本阶段删除：

- `novel_agent.models` 中供其他模块使用的 re-export；
- `NovelAgentService` 和 `SQLiteRepository` 的公开兼容方法；
- 旧 API 路径和 JSON 字段；
- `CreativeBrief.protagonist` 兼容字段与旧方案归一化；
- 旧数据库中 `request_json`、`brief_json` 的读取能力；
- 与章节、人物记忆恢复、Reader 或 Workflow 有关的 legacy 逻辑。

## 3. 当前实现审计

### 3.1 当前后端职责分布

| 当前文件 | 当前职责 | 本阶段处理方式 |
|---|---|---|
| `novel_agent/models.py` | `ProjectStatus`、`NovelCreateRequest`、`BriefRegenerateRequest`、`CharacterProfile`、`CreativeBrief`、`ProjectRecord` | 迁入 Feature，旧路径 re-export |
| `novel_agent/requirements.py` | 标签冲突和频道校验 | 迁入 `features/story_design/requirements.py`，旧路径 re-export |
| `novel_agent/tags.py` | 男女频标签目录和公开 catalog | 迁入 `features/story_design/tags.py`，旧路径 re-export |
| `novel_agent/service.py` | 创建、确认、编辑、重生成、恢复、删除、暂停、继续、项目详情 | 拆为两个 Service，旧类委托 |
| `novel_agent/repository.py` | projects、brief_versions SQL 与跨表初始化/同步 | 拆为 ProjectsStore、BriefsStore 和事务协调 Store |
| `novel_agent/api.py` | 项目/方案 GET、POST、PUT、DELETE 路由 | 迁入 projects/story_design routes |
| `novel_agent/ports/llm.py` | `create_brief`、`revise_brief` 协议 | 保持签名，不在本阶段拆 LLM Port |
| `novel_agent/bootstrap.py` | 构建 Repository、Gateway、Service、AppContext | 显式装配新增 Service |

### 3.2 当前前端职责分布

`apps/web/app.js` 当前同时承担：

- 全局项目列表、当前项目、项目详情和方案版本状态；
- `/api/novels` 列表请求和当前项目加载；
- 项目选择器和 localStorage 记忆；
- 项目空状态和详情渲染；
- 方案展示；
- 方案表单填充与手工保存；
- 反馈重生成、部分重生成；
- 方案版本加载、比较和恢复；
- 项目确认、暂停、继续、恢复和删除；
- 标签目录加载与创建小说表单提交；
- 章节、Memory、Settings 等其他模块。

本阶段不要求一次性替换整个 `app.js`。只把项目与方案职责迁出，并留下薄的应用协调代码。

### 3.3 当前数据库事务

必须冻结以下两条事务。

#### 创建项目事务

当前 `SQLiteRepository.create_project` 在同一事务中写入：

1. `projects`；
2. `brief_versions` 初始 v1；
3. `characters` 初始人物档案；
4. `world_facts` 锁定世界规则。

任一写入失败，全部回滚。不能拆成四次独立提交。

#### 保存草稿方案事务

当前 `SQLiteRepository.save_draft_brief` 在同一事务中完成：

1. 校验项目存在；
2. 校验项目仍是未确认 DRAFT；
3. 校验项目没有章节；
4. 更新 `projects.title` 和 `projects.brief_json`；
5. 追加 `brief_versions`；
6. 同步主角姓名、背景、目标、关系和版本；
7. 重建方案中的其他主要人物；
8. 重建锁定世界规则。

该事务是本阶段最高风险边界。不能为了“一个表一个 Store”让这些步骤分别提交。

### 3.4 当前业务规则

必须保持：

- 创建前先执行 `validate_requirements`；
- 用户指定书名时，必须成为 `selected_title`，并进入候选书名首位；
- `require_plan_confirmation=false` 时项目创建后直接为 ACTIVE 且 confirmed；
- 方案只允许在 DRAFT、未 confirmed、没有章节时编辑；
- 部分重生成只覆盖所选字段组；
- 不选字段时整体重生成；
- 有 feedback 时版本 source 为 `feedback_regenerate`；
- 无 feedback、选了 sections 时 source 为 `partial_regenerate`；
- 普通整体重生成为 `regenerate`；
- 恢复旧版本不是覆盖历史，而是追加 source=`restore` 的新版本；
- 确认项目后状态为 ACTIVE、confirmed=true；
- 暂停只改为 PAUSED；
- 继续前必须已确认；
- 未确认且无章节的草稿可直接删除；
- 已确认或已有章节的作品必须输入完整当前书名才能强制删除；
- 删除依赖数据库外键级联，并显式清理 `publish_tasks`；
- `CreativeBrief` 必须继续归一化 `protagonist` / `protagonist_name` / `protagonist_profile`；
- 旧方案 JSON 必须继续可以被当前模型加载。

### 3.5 当前测试基线

当前全量基线：

```text
Ran 137 tests
OK
```

已有直接相关测试：

- `tests/test_brief_iteration.py`：标题优先级、手工编辑、版本、人物/世界同步、局部重生成、恢复、删除限制；
- `tests/test_requirements.py`：频道、标签冲突、must/exclude 冲突；
- `tests/test_deepseek_gateway.py`：结构化方案生成、方案修订字段；
- `tests/test_workflow.py`：未确认阻断、暂停继续、旧主角字段兼容；
- `tests/test_repository.py`：Repository 基础事务行为；
- `tests/test_dashboard.py`：项目筛选与项目数据间接兼容；
- `tests/test_factories.py`、`tests/test_adapters_compat.py`：Gateway/Port 导入边界。

## 4. 必须冻结的兼容契约

### 4.1 Python 导入契约

拆分后以下旧导入必须继续工作，并且对象身份应与新模块一致：

```python
from novel_agent.models import (
    ProjectStatus,
    NovelCreateRequest,
    BriefRegenerateRequest,
    CharacterProfile,
    CreativeBrief,
    ProjectRecord,
)

from novel_agent.requirements import RequirementConflict, validate_requirements
from novel_agent.tags import TAG_CATALOG, public_tag_catalog
from novel_agent.service import NovelAgentService
from novel_agent.repository import SQLiteRepository, RepositoryError
```

禁止在旧文件中复制第二份类或常量定义。必须使用 import/re-export 保持同一个对象。

### 4.2 LLM Port 契约

本阶段不改变：

```python
class LLMGateway(Protocol):
    def create_brief(self, request: NovelCreateRequest) -> CreativeBrief: ...

    def revise_brief(
        self,
        request: NovelCreateRequest,
        current: CreativeBrief,
        feedback: str,
        fields: list[str],
    ) -> CreativeBrief: ...
```

`OfflineLLMGateway`、`DeepSeekLLMGateway` 和 `DisabledRemoteGateway` 不应因本次拆分改变行为。

### 4.3 数据库契约

以下内容全部保持不变：

- `SCHEMA_VERSION = 5`；
- `projects` 和 `brief_versions` 表结构；
- `projects.request_json`、`projects.brief_json` 的 JSON 结构；
- `brief_versions` 的 version 从 1 连续递增；
- `source`、`feedback`、`created_at` 的语义；
- `characters` 和 `world_facts` 的初始化与同步结果；
- 所有外键和级联删除行为；
- SQLite 仍是唯一权威存储。

不得建立“新表作为临时过渡”。本次是代码结构迁移，不是数据迁移。

### 4.4 HTTP 路径与方法

必须原样保留：

| 方法 | 路径 | 语义 |
|---|---|---|
| GET | `/api/tags` | 获取标签目录 |
| GET | `/api/novels` | 项目列表 |
| POST | `/api/novels` | 创建项目并生成方案 |
| GET | `/api/novels/{project_id}` | 项目聚合详情 |
| POST | `/api/novels/{project_id}/confirm` | 确认方案 |
| POST | `/api/novels/{project_id}/pause` | 暂停 |
| POST | `/api/novels/{project_id}/resume` | 继续 |
| GET | `/api/novels/{project_id}/brief-versions` | 方案版本列表 |
| PUT | `/api/novels/{project_id}/brief` | 手工保存方案 |
| POST | `/api/novels/{project_id}/brief-regenerate` | 整体/局部重生成 |
| POST | `/api/novels/{project_id}/brief-restore` | 恢复方案版本为新版本 |
| DELETE | `/api/novels/{project_id}` | 删除草稿或正式作品 |

`POST /recover` 属于项目恢复入口，但内部涉及章节和运行状态。本阶段只允许迁入 Project route 做委托，不迁移其业务实现；也可以暂时留在 `api.py`，但必须在文档记录该过渡点。

### 4.5 HTTP 返回与错误契约

必须保持：

- 创建成功继续返回 ProjectRecord，状态码 201；
- 项目列表继续返回 `{ "items": [...] }`；
- 项目详情继续返回现有聚合字段：
  - `project`
  - `chapters`
  - `latest_events`
  - `characters`
  - `world_facts`
  - `timeline`
  - `research_sources`
  - `semantic_document_count`
  - `reserve_count`
  - `skills`
- 版本列表继续返回 `{ "items": [...] }`；
- 删除成功继续返回 `{ "deleted": true }`；
- Pydantic ValidationError、RequirementConflict、RepositoryError、ValueError 的 HTTP 映射保持现状；
- APIConfigurationRequired 和 LLM provider 错误映射保持现状；
- 未知路径继续返回既有 404；
- 不把内部类名、SQL 或堆栈暴露给前端。

### 4.6 前端 DOM 与行为契约

以下 ID、data 属性和交互必须保持：

- `projectSelect`、`bookPickerTrigger`、`bookPickerMenu`、`bookPickerGrid`；
- `dashboardView`、`createView`；
- `projectStatus`、`projectTitle`、`projectSynopsis`；
- `confirmButton`、`editBriefButton`、`regenerateBriefButton`；
- `pauseButton`、`recoverButton`、`deleteDraftButton`；
- `briefWorkbench`、`briefEditForm`、`briefFeedback`、`briefSections`；
- `briefVersionLeft`、`briefVersionRight`、`restoreBriefVersion`；
- `briefCompareLeft`、`briefCompareRight`、`briefContent`；
- `createForm`、`genreSelect`、`romanceSelect`、`tagCatalogNote`；
- `[data-check-group]`、`[data-usage-range]` 等其他页面属性不受影响。

必须保持：

- 当前项目继续保存在 localStorage 的 `novelAgentProject`；
- 无项目时仍显示当前空状态；
- 创建成功后选中新项目、刷新并切回控制台；
- DRAFT 且无章节时显示方案编辑工作台；
- 确认后隐藏编辑/重生成能力；
- 删除草稿使用 confirm；
- 删除正式作品使用 prompt 并校验完整书名；
- 暂停按钮在 PAUSED 时显示“继续”；
- 方案版本左右比较和恢复行为不变；
- 任何错误继续通过现有 notify 展示；
- 请求过程中继续使用 busy 状态；
- 320–1440px 现有布局不回归。

## 5. 目标目录结构

本阶段建议形成：

```text
novel_agent/
  features/
    projects/
      __init__.py
      models.py
      errors.py
      ports.py
      service.py
    story_design/
      __init__.py
      models.py
      errors.py
      ports.py
      requirements.py
      tags.py
      service.py

  infrastructure/
    persistence/
      projects_store.py
      briefs_store.py
      project_setup_store.py

  interfaces/
    http/
      routes/
        projects.py
        story_design.py

  models.py          # 兼容 re-export；其他领域模型暂时保留
  requirements.py    # 兼容 re-export
  tags.py            # 兼容 re-export
  repository.py      # 兼容 Facade
  service.py         # 兼容 Facade / 尚未迁移的服务
  api.py             # Handler 与未迁移 routes
  bootstrap.py

apps/web/
  js/
    core/
      api-client.js
      dom.js
      format.js
    features/
      projects/
        state.js
        api.js
        controller.js
      project-dashboard/
        view.js
        template.js
      novel-create/
        api.js
        tags.js
        view.js
        template.js
      story-brief/
        api.js
        editor.js
        versions.js
        view.js
        template.js

  styles/
    features/
      project-dashboard.css
      novel-create.css
      story-brief.css
```

说明：

- `projects/state.js` 只保存项目列表、selectedId、detail 和订阅者；
- `project-dashboard` 不接管章节生产和 Memory 渲染；
- `novel-create` 不直接修改全局项目状态，只通过成功回调通知 coordinator；
- `story-brief` 只处理方案，不处理章节或人物浏览页面；
- `shell/book-picker.js` 属于阶段 8，本阶段可以保留在 `app.js`，但要改为订阅 projects state；
- `project_setup_store.py` 名称可以调整，但必须有一个明确对象拥有跨表创建/方案同步事务。

## 6. 依赖方向

目标依赖：

```text
HTTP Routes
  → ProjectService / StoryDesignService
    → Feature Ports
      → SQLite Stores
        → DatabaseSessionProvider

StoryDesignService
  → LLMGateway Port

Compatibility Facades
  → New Services / Stores
```

禁止：

- Feature Service 导入 `sqlite3`；
- Feature Service 导入 `api.py`；
- Route 直接执行 SQL；
- Store 导入 Service；
- 新模块导入 `novel_agent.service.NovelAgentService`；
- 新模块反向导入 `novel_agent.repository.SQLiteRepository` 作为具体类型；
- Projects Feature 导入 DeepSeek 或 Offline 实现；
- 前端 Feature 直接读写其他 Feature 的内部变量；
- 前端 Feature 重新创建一套独立的当前项目状态。

## 7. 后端模型拆分设计

### 7.1 `features/projects/models.py`

迁移：

- `ProjectStatus`；
- `ProjectRecord`。

`ProjectRecord` 字段、Pydantic 配置和 JSON 输出必须保持完全一致。

### 7.2 `features/story_design/models.py`

迁移：

- `NovelCreateRequest`；
- `BriefRegenerateRequest`；
- `CharacterProfile`；
- `CreativeBrief`。

必须完整保留 validator：

- genre、idea、preferred_title strip；
- audience_channel 白名单；
- feedback strip；
- sections 白名单和去重；
- protagonist 兼容归一化；
- 主角 profile 注入与角色纠正；
- character_profiles 去重。

迁移顺序：

1. 新文件定义模型；
2. `novel_agent.models` 改为 import/re-export；
3. 增加对象 identity 测试；
4. 逐步迁移内部 import；
5. 未迁移领域模型继续留在 `models.py`。

禁止把整个 `models.py` 一次性搬空。

### 7.3 `errors.py`

建议定义：

```python
class ProjectError(RuntimeError): ...
class ProjectNotFoundError(ProjectError): ...
class ProjectStateError(ProjectError): ...
class ProjectDeletionConfirmationError(ProjectError): ...

class StoryDesignError(RuntimeError): ...
class StoryDesignNotEditableError(StoryDesignError): ...
class BriefVersionNotFoundError(StoryDesignError): ...
class RequirementConflict(StoryDesignError, ValueError): ...
```

但本阶段不能擅自改变外部错误类型和 HTTP 状态。若新异常会改变现有 `isinstance` 行为，应先让旧 `RepositoryError` / `ValueError` 做兼容包装，或暂缓异常细分。

最安全做法：先迁移现有 `RequirementConflict`，其他异常在 Store/Service 层保留当前外部映射，待 route 测试固定后再细分。

### 7.4 `requirements.py` 与 `tags.py`

迁移现有逻辑，不修改 catalog 内容和冲突规则。

必须验证：

- 男频/女频类型目录不串线；
- romance 默认项语义不变；
- `public_tag_catalog()` 的 `default_channel`、`channels`、`references`、`note` 不变；
- must_have 与 exclude 交集继续报错；
- 已有四组 incompatible 规则不变。

## 8. Persistence 设计

### 8.1 `ProjectsStore`

负责：

- `list_projects`；
- `get_project`；
- `update_project_status`；
- `confirm_project`；
- `delete_project`；
- row → ProjectRecord 映射。

不负责：

- 调用 LLM；
- 判断删除确认书名；
- 生成初始人物；
- 方案字段合并；
- 项目详情跨域聚合。

### 8.2 `BriefsStore`

负责只读/窄写职责：

- `list_brief_versions`；
- `get_brief_version`；
- 获取下一个 version；
- 插入 brief version；
- 更新 project 当前 title/brief 的底层语句。

`BriefsStore` 不应单独提交需要同步人物和世界规则的正式方案保存事务。

### 8.3 `ProjectSetupStore` / 事务协调对象

该对象负责两条跨表事务：

```python
class ProjectSetupStore(Protocol):
    def create_project_with_seed(
        self,
        project: ProjectRecord,
        characters: list[CharacterRecord],
        world_facts: list[WorldFactRecord],
    ) -> ProjectRecord: ...

    def save_draft_brief_with_seed_sync(
        self,
        project_id: str,
        brief: CreativeBrief,
        *,
        source: str,
        feedback: str = "",
    ) -> ProjectRecord: ...
```

实现可以组合 ProjectsStore、BriefsStore 和暂时仍在 Repository Facade 后面的 Memory SQL helper，但必须共享同一个 `sqlite3.Connection`。

推荐实现方式：

- Stores 的内部方法接受显式 `conn`；
- 最外层 transaction coordinator 只开启一次 transaction；
- 被调用的内部方法在收到 `conn` 时不得再次 BEGIN/COMMIT；
- 所有失败统一冒泡，由最外层 rollback；
- 暂时不要让通用 Store 互相持有具体实现。

### 8.4 DatabaseSessionProvider

复用 Analytics 已建立的 `DatabaseSessionProvider`，不要重新定义第二份协议。

Store 构造依赖应类似：

```python
class SQLiteProjectsStore:
    def __init__(self, database: DatabaseSessionProvider):
        self._database = database
```

`SQLiteRepository` 可以在 `migrate()` 后装配：

```python
self.projects = SQLiteProjectsStore(self)
self.briefs = SQLiteBriefsStore(self)
self.project_setup = SQLiteProjectSetupStore(self, self.projects, self.briefs)
```

### 8.5 Repository 兼容 Facade

保留旧方法和签名：

```python
repository.create_project(...)
repository.list_projects()
repository.get_project(...)
repository.update_project_status(...)
repository.confirm_project(...)
repository.save_draft_brief(...)
repository.list_brief_versions(...)
repository.get_brief_version(...)
repository.delete_project(...)
```

Facade 只允许：

- 参数适配；
- 调用新 Store；
- 把新领域异常翻译为旧 `RepositoryError`；
- 保持旧返回结构。

Facade 不再保留 SQL、版本计算或人物/世界同步逻辑。

## 9. Application Service 设计

### 9.1 `StoryDesignService`

建议接口：

```python
@dataclass(slots=True)
class StoryDesignService:
    store: StoryDesignStore
    gateway: LLMGateway
    id_factory: Callable[[str], str] = new_id
    clock: Callable[[], str] = utc_now

    def create_story(self, request: NovelCreateRequest) -> ProjectRecord: ...
    def update_brief(self, project_id: str, brief: CreativeBrief) -> ProjectRecord: ...
    def regenerate_brief(
        self,
        project_id: str,
        change: BriefRegenerateRequest,
    ) -> ProjectRecord: ...
    def restore_brief(self, project_id: str, version: int) -> ProjectRecord: ...
    def list_versions(self, project_id: str) -> list[BriefVersionRecord]: ...
```

职责：

- 校验创建需求；
- 设置 project_id 和 LLM telemetry scope；
- 调用 `create_brief` / `revise_brief`；
- 应用 preferred title；
- 映射部分重生成字段；
- 决定 version source；
- 构造初始人物和世界规则；
- 调用事务 Store；
- 校验草稿可编辑状态。

禁止：

- 执行 SQL；
- 知道 HTTP；
- 直接依赖 DeepSeek 类；
- 吞掉 LLM 错误；
- 在 Service 中分多次提交同一个业务事务。

### 9.2 `_brief_fields` 字段组

以下映射必须原样迁移并加单元测试：

| section | 影响字段 |
|---|---|
| `title` | `title_candidates`, `selected_title` |
| `story` | `synopsis`, `target_readers`, `selling_points`, `main_conflict`, `reader_contract`, `core_expectation` |
| `protagonist` | `protagonist`, `protagonist_name`, `protagonist_profile`, `character_profiles` |
| `world` | `world_rules` |
| `opening` | `opening_three_chapters` |
| `style` | `style_guide` |
| `serialization` | `total_chapters`, `volume_count`, `update_plan` |

### 9.3 `ProjectService`

建议接口：

```python
@dataclass(slots=True)
class ProjectService:
    projects: ProjectStore
    detail_reader: ProjectDetailReader

    def list_projects(self) -> list[ProjectRecord]: ...
    def get_detail(self, project_id: str) -> dict[str, object]: ...
    def confirm(self, project_id: str) -> ProjectRecord: ...
    def pause(self, project_id: str) -> ProjectRecord: ...
    def resume(self, project_id: str) -> ProjectRecord: ...
    def delete(self, project_id: str, confirmation_title: str | None) -> None: ...
```

`get_detail` 当前跨越 Chapter、Runs、Memory、Research、Semantic 和 Skills。阶段 4 不应强行拆完这些模块。

过渡方案：

- 定义只读 `ProjectDetailReader` Protocol；
- 当前由 `SQLiteRepository` 兼容 Facade 和 skills provider 实现；
- `ProjectService` 只负责聚合输出；
- 后续阶段再把 detail_reader 替换为多个明确 Query Service。

禁止把 `ProjectService` 设计成持有整个 `NovelAgentService`。

### 9.4 生命周期规则

`ProjectService` 必须显式验证：

- confirm 只执行当前既有语义，不自动生成章节；
- pause 不删除数据；
- resume 要求 confirmed；
- delete 草稿时检查 DRAFT、未 confirmed、无章节；
- delete 正式作品时校验确认书名；
- 不把 HUMAN_REQUIRED 恢复混入普通 resume。

### 9.5 NovelAgentService 兼容委托

保留：

```python
NovelAgentService.create_novel
NovelAgentService.confirm_novel
NovelAgentService.update_draft_brief
NovelAgentService.regenerate_draft_brief
NovelAgentService.restore_draft_brief
NovelAgentService.delete_novel
NovelAgentService.pause_novel
NovelAgentService.resume_novel
NovelAgentService.project_detail
```

方法体只委托：

```python
def create_novel(self, request):
    return self.story_design.create_story(request)
```

为避免立刻破坏大量测试，`NovelAgentService` 的现有三位置参数构造方式必须继续工作。可以在 `__post_init__` 中从现有 repository/gateway 装配默认子服务，但 bootstrap 应显式注入。

## 10. HTTP Routes 设计

### 10.1 Route 形式

沿用 Analytics 已验证的 dispatch 风格，不引入新框架：

```python
def dispatch_projects_get(path, params, service) -> RouteResult | None: ...
def dispatch_projects_post(path, payload, service) -> RouteResult | None: ...
def dispatch_projects_delete(path, payload, service) -> RouteResult | None: ...

def dispatch_story_design_get(path, params, service) -> RouteResult | None: ...
def dispatch_story_design_post(path, payload, service) -> RouteResult | None: ...
def dispatch_story_design_put(path, payload, service) -> RouteResult | None: ...
```

可以先共用 Analytics 的 `RouteResult`，也可以将其提升到 `interfaces/http/routes/result.py`。如果提升，必须保持旧 import 兼容。

### 10.2 `projects.py`

负责：

- `GET /api/novels`；
- `GET /api/novels/{id}`；
- `POST /api/novels/{id}/confirm`；
- `POST /api/novels/{id}/pause`；
- `POST /api/novels/{id}/resume`；
- `DELETE /api/novels/{id}`。

`recover` 暂时只做代理，不迁移业务实现，避免把章节恢复混入本阶段。

### 10.3 `story_design.py`

负责：

- `POST /api/novels`；
- `GET /api/novels/{id}/brief-versions`；
- `PUT /api/novels/{id}/brief`；
- `POST /api/novels/{id}/brief-regenerate`；
- `POST /api/novels/{id}/brief-restore`。

`GET /api/tags` 可以暂时保留在 `api.py`，或迁入 `story_design.py`；若迁移，不能改变返回结构。总路线最终把 tags 放入 system route，阶段 8 可再移动一次。

### 10.4 api.py 接线顺序

必须先让新 route 尝试匹配，未匹配返回 `None`，再进入旧 Handler 分支。

每迁移一条路由后立即删除 `api.py` 中对应旧分支，不能让新旧两条路径同时可执行。

### 10.5 AppContext 与 bootstrap

建议扩展：

```python
@dataclass(slots=True)
class AppContext:
    settings: Settings
    service: NovelAgentService
    repository: SQLiteRepository
    web_root: Path
    analytics: AnalyticsService | None = None
    projects: ProjectService | None = None
    story_design: StoryDesignService | None = None
```

要求：

- 原四位置参数构造继续工作；
- `__post_init__` 只做兼容兜底；
- `bootstrap.create_context` 显式创建和注入新 Service；
- Route 只调用 `context.projects` / `context.story_design`；
- 新 route 不访问 `context.repository`。

## 11. 前端共享状态与装配

### 11.1 唯一项目状态源

建议 `features/projects/state.js`：

```javascript
export function createProjectsState() {
  return {
    projects: [],
    selectedId: null,
    detail: null,
    briefVersions: [],
    status: "idle",
    error: null,
    subscribe(listener),
    getSnapshot(),
    setProjects(items),
    select(projectId),
    setDetail(detail),
    setBriefVersions(items),
    reset(),
  };
}
```

不要求引入复杂状态库。目标只是避免 novel-create、story-brief、project-dashboard 各自保存一份 selectedId/detail。

### 11.2 API client

当前 `app.js` 的 `api()` 应迁入 `js/core/api-client.js`，并继续通过依赖注入传给 Analytics 和新 Feature。

必须保持：

- JSON headers；
- 非 2xx 时的错误消息提取；
- 204/null 响应处理；
- fetch AbortSignal 支持；
- 不在 client 中写 DOM 或调用 notify。

### 11.3 Coordinator

`app.js` 在本阶段结束时仍可负责：

- 启动 Feature；
- shell 导航；
- 当前项目变化广播；
- Chapter/Memory/Reader/Settings 尚未迁移的协调；
- 刷新 health 和项目集合。

但不再包含：

- 创建小说 payload 拼装；
- 标签 DOM 渲染；
- 方案表单读写；
- 方案版本比较；
- 项目确认/暂停/继续/删除业务交互；
- 项目与方案模板字符串。

## 12. `novel-create` 前端设计

### 12.1 文件职责

`api.js`：

- `loadTagCatalog()`；
- `createNovel(payload, { signal })`。

`tags.js`：

- 根据 channel 选择 catalog；
- 生成 genre/experience/element/protagonist/romance view model；
- 不直接 fetch；
- 不读取全局 state。

`view.js`：

- mount/create form；
- 绑定频道切换；
- 构造 payload；
- submit busy/error；
- 成功后调用 `onCreated(project)`；
- destroy 时解绑事件和中止请求。

`template.js`：

- 保存当前 `createView` 内部静态结构；
- 保持所有 name、ID、min/max/default、placeholder 和中文文案。

### 12.2 Payload 冻结

必须继续提交：

```javascript
{
  preferred_title,
  audience_channel,
  genre,
  experiences,
  elements,
  protagonist_tags,
  romance,
  idea,
  must_have,
  nice_to_have,
  exclude,
  chapter_target_chars,
  daily_chapters,
  reserve_target,
  require_plan_confirmation,
}
```

`must_have`、`nice_to_have`、`exclude` 继续支持中文逗号和英文逗号。

### 12.3 生命周期

```javascript
createNovelCreateView({ api, notify, busy, onCreated })
```

返回：

```javascript
{
  mount(host),
  activate(),
  deactivate(),
  reset(),
  destroy(),
}
```

要求：

- mount 幂等；
- 标签只在需要时加载一次；
- 快速切频道不发网络请求；
- deactivate 不丢失用户尚未提交的表单；
- destroy 后不得残留监听器；
- 重复点击提交时只保留一次有效请求。

## 13. `story-brief` 前端设计

### 13.1 `view.js`

负责：

- 渲染当前方案摘要；
- 控制工作台显示/隐藏；
- 协调 editor 和 versions；
- 根据 editableDraft 控制按钮；
- 对外暴露 `setProjectDetail(detail)`。

不负责：

- 项目列表；
- 章节列表；
- Memory；
- 项目暂停/删除；
- shell 导航。

### 13.2 `editor.js`

负责：

- `populateBriefEditor`；
- 从表单构造完整 CreativeBrief payload；
- 手工保存；
- feedback 和 sections 读取；
- 整体/局部重生成；
- 编辑表单打开、取消和 busy 状态。

必须继续保留未显示字段。手工编辑时不能因表单没有 character_profiles/title_candidates 等控件而丢弃这些字段；应以当前 brief 为基底，只覆盖表单展示字段。

### 13.3 `versions.js`

负责：

- 加载版本列表；
- 默认左右版本选择；
- version source 中文映射；
- 渲染左右快照；
- 恢复左侧版本；
- 恢复成功后刷新 detail 和 versions。

必须处理：

- 0 个版本；
- 1 个版本；
- 版本刷新后原选择不存在；
- 快速切项目导致旧响应返回；
- 恢复版本时项目已被确认的冲突。

### 13.4 请求取消和过期响应

每个 projectId 相关请求必须带 request generation 或 AbortController。

切换项目后，旧项目的 versions/detail 响应不得覆盖新项目状态。

推荐：

```javascript
let requestId = 0;

async function load(projectId) {
  const current = ++requestId;
  const result = await api(...);
  if (current !== requestId) return;
  // apply result
}
```

## 14. `project-dashboard` 前端设计

### 14.1 本阶段边界

负责：

- 空项目状态；
- 项目 title、synopsis、status；
- confirm、pause、resume、delete；
- 是否显示 recover 按钮；
- 将项目详情传给 story-brief；
- 将未归属职责通过回调交给 app coordinator。

暂不负责：

- generate chapter；
- chapterQueue；
- pipeline；
- metrics 中来自章节的数据计算；
- Memory 渲染；
- ReaderWorkspace。

这些暂由 `app.js` 保留，后续阶段迁出。

### 14.2 删除交互

必须保持两种路径：

1. 未确认且无章节草稿：普通 confirm；
2. 已确认或已有章节：prompt 输入完整书名。

前端校验只是减少误操作，后端必须再次校验。

删除成功后：

- 清空 selectedId；
- 删除 `novelAgentProject`；
- 刷新项目列表；
- 选择新的首个项目或进入空状态；
- 通知 Reader/Memory 当前项目变化。

### 14.3 状态显示

保持映射：

```javascript
{
  DRAFT: "等待方案确认",
  ACTIVE: "自动连载可用",
  PAUSED: "已暂停",
  HUMAN_REQUIRED: "需要人工处理",
  ARCHIVED: "已归档",
}
```

不得在结构重构中修改状态文案或增加新状态。

## 15. 模板与 CSS 迁移

### 15.1 模板迁移顺序

1. 先让新 View 挂载现有 DOM，只迁逻辑；
2. 行为回归通过后，把 `createView` 静态结构迁入 `novel-create/template.js`；
3. 再迁 brief workbench 到 `story-brief/template.js`；
4. 最后视情况迁项目 hero；
5. 每次迁移都保持 ID、class、ARIA 和 DOM 顺序；
6. `index.html` 最终只保留挂载点，但阶段中间不能出现同 ID 两份节点。

### 15.2 CSS 拆分

当前相关选择器大致分布：

- Book picker：`styles.css` 336–439，属于 shell，暂不迁或最后迁入 shell；
- Project hero/actions：约 509–532；
- Metrics：约 642–667，暂有章节职责，不全部迁；
- Brief workbench/compare：约 677–727；
- Brief display：约 822–843；
- Create form/chips/catalog：约 845–936；
- Responsive 对应规则：约 1671、1778–1782。

本阶段只迁：

- `project-dashboard` 独占选择器；
- `story-brief` 独占选择器；
- `novel-create` 独占选择器。

共享 `.button`、`.panel`、`.field-row`、`.hidden`、`.muted`、`.empty` 等继续留在全局组件样式。

迁移要求：

- 保持原 cascade 顺序；
- 不改 specificity；
- 不用大量 `!important` 修复；
- 迁入后从 `styles.css` 删除原规则，不能保留两份；
- 更新 `index.html` 的 CSS link；
- 静态资源测试覆盖每个新 CSS；
- 320、375、414、768、1024、1440px 手工验证。

## 16. 分阶段实施计划

每一阶段独立完成、测试、检查 diff。不要一次性执行全部阶段。

### 阶段 0：冻结基线

1. 记录 `git status --short`；
2. 不覆盖 Analytics、Reader、外部适配器和现有文档改动；
3. 保存项目/方案 HTTP 典型 JSON fixture；
4. 保存创建、编辑、版本、确认、暂停、删除页面截图；
5. 运行现有相关测试和全量测试；
6. 记录当前工作区有未跟踪新模块，提交时必须显式核对。

验收：基线可恢复，137 项测试通过。

### 阶段 1：补 Characterization 与兼容测试

新增：

```text
tests/projects/test_models_compat.py
tests/projects/test_store.py
tests/projects/test_service.py
tests/projects/test_routes.py
tests/story_design/test_models_compat.py
tests/story_design/test_requirements.py
tests/story_design/test_service.py
tests/story_design/test_routes.py
tests/test_web_project_assets.py
```

先固定：

- 旧/新模型对象 identity；
- Repository 方法签名；
- NovelAgentService 方法签名；
- API 路径、状态码和 JSON；
- 两条事务 rollback；
- 项目详情完整字段；
- 前端关键 ID 和现有静态资源。

本阶段不迁实现。

### 阶段 2：迁移模型、标签和需求校验

1. 建立 projects/story_design 包；
2. 迁移模型；
3. 旧 `models.py` re-export；
4. 迁移 tags 和 requirements；
5. 旧模块 re-export；
6. 更新内部 import，但不要触碰 Persistence/Service 行为。

验收：对象 identity、Pydantic schema、旧 JSON、DeepSeek 和 requirements 测试全部通过。

### 阶段 3：抽取 ProjectsStore 与 BriefsStore

1. 先抽 list/get/status/confirm/delete；
2. 再抽 brief version 只读；
3. 建立 project setup transaction coordinator；
4. 迁移 create_project；
5. 最后迁移 save_draft_brief；
6. Repository 同名方法改为兼容委托；
7. 用失败注入验证 rollback。

验收：`repository.py` 不再包含 projects/brief_versions SQL；创建和方案同步仍为单事务。

建议分两个提交，不要把 `save_draft_brief` 与简单 CRUD 放在一个大提交里。

### 阶段 4：建立 StoryDesignService

1. 迁移 create/update/regenerate/restore；
2. 迁移 `_character_records`；
3. 迁移 `_assert_editable_draft`；
4. 迁移 `_brief_fields`；
5. 通过 fake store 和 fake gateway 单测；
6. NovelAgentService 方法改为委托。

验收：Service 不导入 SQLiteRepository、sqlite3、api 或具体 LLM provider。

### 阶段 5：建立 ProjectService

1. 迁移 list/confirm/pause/resume/delete；
2. 用 `ProjectDetailReader` 迁移 detail 聚合；
3. recover 仅保留兼容委托；
4. NovelAgentService 方法改为委托；
5. bootstrap 显式装配两个 Service。

验收：生命周期规则单元测试通过；旧 NovelAgentService 调用结果等于新 Service。

### 阶段 6：提取 HTTP Routes

1. 新增 projects route；
2. 新增 story_design route；
3. AppContext 增加兼容字段；
4. api.py 接线；
5. 每迁一条路由，删除一个旧分支；
6. Route 测试验证 service 调用次数、参数和错误映射。

验收：新 route 不访问 Repository；HTTP fixture 深比较一致。

### 阶段 7：前端共享状态与 novel-create

1. 抽 `core/api-client.js`；
2. 建立 projects state/controller；
3. 拆 novel-create api/tags/view；
4. 先挂现有 DOM；
5. 再迁 template；
6. app.js 只接收 onCreated 并刷新项目。

验收：男女频切换、表单默认值、创建成功/失败、重复点击和项目选中行为不变。

### 阶段 8：拆 story-brief

1. 提取展示；
2. 提取 editor；
3. 提取 versions；
4. 加 request generation/Abort；
5. 迁 template；
6. 删除 app.js 对应实现。

验收：手工编辑、整体重生成、部分重生成、左右比较和恢复全部回归通过。

### 阶段 9：拆 project-dashboard 与 CSS

1. 提取项目 hero、状态、确认/暂停/继续/删除；
2. 章节和 Memory 仍通过 callback 保留在 app.js；
3. 迁三个 Feature 的独占 CSS；
4. 删除全局重复规则；
5. 更新静态资源测试；
6. 完成全尺寸手工回归。

验收：`app.js` 不再包含项目/方案业务实现；styles.css 无对应重复规则。

### 阶段 10：兼容收尾与文档

1. 全仓搜索旧实现与 route；
2. 保留公开 Facade，标明迁移期用途；
3. 更新 `docs/ARCHITECTURE.md` 的真实依赖；
4. 更新总拆分文档的阶段完成状态；
5. 检查 README 到 USER_GUIDE 的链接；
6. 只有用户可见行为实际变化时才更新 `docs/USER_GUIDE.md`；
7. 运行全量测试、JS 语法检查和 diff check。

## 17. 后端测试计划

### 17.1 模型兼容

- 旧路径与新路径对象 identity；
- `model_json_schema()` 一致；
- 旧 brief JSON 可读取；
- protagonist 兼容归一化；
- character_profiles 去重；
- sections 去重和非法值；
- 字段长度、数字范围、extra=forbid。

### 17.2 Store

- create 写入 projects + v1 + characters + world facts；
- create 任一步失败时全部 rollback；
- list created_at DESC；
- get 不存在项目；
- confirm/status 更新时间；
- save brief version 递增；
- save brief 同步 title、主角、配角和 world facts；
- save brief 任一步失败时全部 rollback；
- 并发/重复保存不产生相同 version；
- get/list version 顺序和 DTO；
- 删除草稿；
- force 删除正式作品；
- 删除级联不残留关联数据；
- publish_tasks 显式清理。

### 17.3 StoryDesignService

- requirements 在 LLM 前执行；
- preferred title 覆盖；
- require confirmation true/false；
- telemetry scope 使用新 project_id；
- create 只调用 gateway 一次；
- update 重新验证 CreativeBrief；
- 不可编辑项目在 LLM 调用前失败；
- partial regenerate 只合并所选字段；
- feedback/source 组合；
- restore 追加新版本；
- gateway 异常不保存版本；
- store 异常不被吞掉。

### 17.4 ProjectService

- list/get detail 委托；
- detail 字段完整；
- confirm/pause/resume；
- 未确认项目不能 resume；
- 草稿删除无需书名；
- 正式作品删除必须书名完全一致；
- 书名前后空格行为与当前 API 一致；
- recover 不被普通 resume 取代。

### 17.5 Routes

- 每条路径成功；
- 未匹配返回 None；
- URL 编码 project_id 行为保持；
- payload 验证；
- create 201；
- delete payload 空/书名；
- service 每次只调用一次；
- route 不访问 Repository；
- ValidationError / RequirementConflict / RepositoryError / ValueError / LLM errors 映射不变；
- 未知异常最终 500。

### 17.6 兼容 Facade

旧 Repository 与新 Store 返回深度相等；旧 NovelAgentService 与新 Service 返回深度相等；不能只测试方法存在。

## 18. 前端测试与手工回归

### 18.1 静态自动检查

- index 中所有本地 JS/CSS 存在；
- ES module import 不越出 web root；
- create/dashboard/brief 挂载点只出现一次；
- 旧 app.js 项目/方案函数已删除；
- 缺失 JS/CSS 返回 404；
- template 含关键 ID、name、min/max 和 ARIA；
- 新 CSS link 存在；
- styles.css 不再保留已迁选择器；
- 全部 JS 通过 `node --check`。

### 18.2 可选纯 JS 测试

如果现有 Node 可用，不引入 npm：

- tags view model；
- split list；
- status label；
- editableDraft selector；
- delete confirmation selector；
- brief section merge/view model；
- version source label；
- stale request generation。

### 18.3 手工回归矩阵

宽度：320、375、414、768、1024、1440px。

逐项检查：

1. 无项目启动；
2. 男频/女频切换；
3. 标签和感情线更新；
4. 创建表单字段和默认值；
5. 冲突要求错误提示；
6. 离线创建；
7. 在线创建 loading/error；
8. 创建后自动选中新项目并回控制台；
9. 多项目切换与 localStorage 恢复；
10. 空项目/详情切换不闪旧数据；
11. 修改方案和取消；
12. 保存为新版本；
13. 整体重生成；
14. 带 feedback 的部分重生成；
15. 版本左右选择；
16. 恢复旧版本生成新版本；
17. 确认后编辑工作台消失；
18. 暂停和继续；
19. 草稿删除确认；
20. 正式作品书名不匹配时取消；
21. 正式作品书名匹配时删除；
22. 快速切项目时旧请求不覆盖新项目；
23. Reader/Memory/Analytics/Settings 不受影响；
24. 控制台无 404、MIME、重复监听或未处理 Promise 错误。

## 19. 每阶段验证命令

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m unittest tests.test_requirements -v
python -m unittest tests.test_brief_iteration -v
python -m unittest tests.test_workflow -v
python -m unittest tests.test_deepseek_gateway -v
python -m unittest discover -s tests -v
git diff --check
```

JavaScript：

```powershell
Get-ChildItem -File -Recurse apps/web -Filter *.js | ForEach-Object {
  node --check $_.FullName
  if ($LASTEXITCODE -ne 0) { throw "JS syntax failed: $($_.FullName)" }
}
```

如果 Ruff 已安装，再执行：

```powershell
python -m ruff check novel_agent tests
```

未安装 Ruff 时记录“未执行”，不能写成通过。

## 20. Cursor 分阶段执行模板

### 20.1 阶段 0–2 指令

```text
请严格按照 docs/PROJECT_STORY_DESIGN_SPLIT_PLAN.md 执行阶段 0–2。

本次只建立 Characterization 测试，并迁移 Projects/Story Design 模型、标签目录和需求校验。
不要迁移 Repository SQL、Service、HTTP 或前端。

要求：
1. 先记录 git status，不覆盖当前工作区已有修改。
2. novel_agent.models、novel_agent.requirements、novel_agent.tags 必须保留兼容 re-export。
3. 旧路径和新路径必须是同一个类/函数/常量对象，不得复制定义。
4. 保持 Pydantic schema、validator、CreativeBrief legacy protagonist 兼容和 JSON 完全不变。
5. 运行相关测试和完整 unittest，报告未执行项。
```

### 20.2 阶段 3 指令

```text
请严格按照 docs/PROJECT_STORY_DESIGN_SPLIT_PLAN.md 执行阶段 3。

只提取 ProjectsStore、BriefsStore 和项目初始化/方案同步事务协调对象，不修改 Service、HTTP 或前端行为。

要求：
1. 复用现有 DatabaseSessionProvider。
2. 创建项目的 projects + brief v1 + characters + world_facts 必须保持同一事务。
3. 保存方案的 project + version + characters + world_facts 必须保持同一事务。
4. 对两条事务增加失败注入 rollback 测试。
5. SQLiteRepository 保留所有旧方法和签名，方法体只委托新 Store。
6. repository.py 最终不得保留 projects/brief_versions SQL 或重复业务逻辑。
7. 不改 schema/version/JSON。
```

### 20.3 阶段 4–6 指令

```text
请严格按照 docs/PROJECT_STORY_DESIGN_SPLIT_PLAN.md 执行阶段 4–6。

建立 StoryDesignService、ProjectService，并提取 projects/story_design HTTP routes。

要求：
1. Service 只依赖 Feature Ports 和 LLMGateway Port，不导入 sqlite3、SQLiteRepository、api.py 或具体 Provider。
2. NovelAgentService 保留旧方法并委托新 Service，原构造方式继续工作。
3. AppContext 四位置参数兼容，bootstrap 显式装配新 Service。
4. Route 只调用 context.projects/context.story_design，不直接访问 Repository。
5. 保持所有 HTTP 路径、方法、状态码、JSON 和错误映射。
6. recover 只做代理，不把章节恢复逻辑混入 ProjectService。
7. 每迁移一条 route 就删除 api.py 对应旧分支，禁止双实现。
```

### 20.4 阶段 7–9 指令

```text
请严格按照 docs/PROJECT_STORY_DESIGN_SPLIT_PLAN.md 执行阶段 7–9。

使用原生 ES Modules 拆分 projects state、novel-create、story-brief 和 project-dashboard，不引入 npm、框架或构建工具。

要求：
1. 先让新模块接管现有 DOM，再迁 template，最后迁 CSS。
2. 保持所有 DOM ID、class、ARIA、中文文案、表单 name/default/min/max、localStorage key 和交互。
3. selected project/detail 只有一个状态源。
4. 切项目时取消旧请求或使用 generation，旧响应不得覆盖新状态。
5. app.js 只保留协调和未迁 Feature，不再保留项目/方案业务实现。
6. 章节、Memory、Reader、Analytics 和 Settings 不在本阶段迁移。
7. CSS 原样移动，保持 cascade；迁入后删除 styles.css 重复规则。
8. 运行静态资源测试、node --check、完整 unittest，并完成文档中的手工回归矩阵。
```

### 20.5 阶段 10 指令

```text
请严格按照 docs/PROJECT_STORY_DESIGN_SPLIT_PLAN.md 执行阶段 10 收尾。

全仓搜索旧 Projects/Story Design 实现、旧路由、重复 SQL、重复 CSS 和无调用前端函数。
保留公开兼容 Facade，不删除旧 import 路径。
更新 docs/ARCHITECTURE.md 和总拆分路线的完成状态。

纯结构重构不修改 docs/USER_GUIDE.md；若实现过程中确实改变任何用户可见按钮、操作、状态、API、存储、成本、安全或排障方式，必须在同一改动中同步更新 docs/USER_GUIDE.md，并检查 README 链接。
```

## 21. 风险与保护措施

### 风险 1：拆断创建事务

表现：项目已创建，但初始版本、人物或世界规则缺失。

保护：唯一 transaction coordinator；失败注入；提交后计数断言；不允许 Service 连续调用四个自动提交 Store。

### 风险 2：拆断方案同步事务

表现：项目 brief 已更新，但人物或世界规则仍是旧值。

保护：`save_draft_brief_with_seed_sync` 单事务；每个内部 Store 接收同一 conn；任一写入失败全部 rollback。

### 风险 3：旧模型类身份改变

表现：Pydantic、isinstance、mock patch 或外部导入异常。

保护：新模块唯一真实定义；旧模块只 re-export；identity 测试。

### 风险 4：ProjectDetail 过早拆散

表现：章节、Memory、Skills 字段丢失，前端整页异常。

保护：阶段 4 使用 `ProjectDetailReader` 过渡，深比较完整 fixture；不要求提前拆所有下游 Store。

### 风险 5：部分重生成覆盖未选字段

表现：只重做书名却修改简介、人物或世界。

保护：字段组单测；以当前 brief 为基底；只覆盖明确字段。

### 风险 6：快速切项目出现旧数据

表现：A 项目版本请求晚于 B 返回，覆盖 B 页面。

保护：AbortController/request generation；所有响应应用前验证 projectId 和 generation。

### 风险 7：模板迁移产生重复 ID

表现：事件绑到旧节点，按钮点击两次或无效。

保护：逻辑迁移和 template 迁移分阶段；静态测试检查关键 ID 只出现一次；mount 幂等。

### 风险 8：CSS 移动改变 cascade

表现：方案工作台、表单或移动端布局变化。

保护：原样移动；保持 link 顺序；逐组删除旧规则；全尺寸截图比较。

### 风险 9：兼容 Facade 变成第二套实现

表现：新旧入口逐渐产生不同行为。

保护：Facade 只做委托和异常翻译；测试旧入口返回等于新 Service/Store。

### 风险 10：工作区已有改动被覆盖

表现：Analytics、Reader 或用户文档的现有成果丢失。

保护：每阶段先看 status/diff；只 patch 本阶段文件；不 reset/checkout；不批量格式化无关文件。

## 22. 回滚策略

推荐提交粒度：

```text
test(projects): characterize project and brief contracts
refactor(models): extract project and story design models
refactor(persistence): extract project stores
refactor(persistence): preserve atomic brief synchronization
refactor(story-design): add application service
refactor(projects): add lifecycle service
refactor(api): extract project and story design routes
refactor(web): extract novel create feature
refactor(web): extract story brief feature
refactor(web): extract project dashboard lifecycle
refactor(web): move project feature styles
docs(architecture): document project and story design boundaries
```

每个提交必须可单独回滚。失败时只回滚当前阶段，不清空整个工作区。

## 23. Definition of Done

只有同时满足以下条件，本模块才算完成：

- Projects/Story Design 模型只有一份真实定义；
- 旧 model/requirements/tags imports 继续工作且对象 identity 一致；
- `repository.py` 不含 projects/brief_versions SQL；
- 创建项目仍是一个跨表事务；
- 保存方案仍是一个跨表事务；
- rollback 测试覆盖两条事务；
- `StoryDesignService` 是方案生成、编辑、重生成和恢复的唯一业务实现；
- `ProjectService` 是列表、详情、确认、暂停、继续和删除的唯一业务实现；
- `NovelAgentService` 对相关方法只做兼容委托；
- 项目/方案 routes 不直接访问 Repository；
- `api.py` 不再含已迁路由分支；
- HTTP 方法、路径、状态码、JSON 和错误映射完全兼容；
- `app.js` 不再含创建小说、方案编辑/版本和项目生命周期实现；
- novel-create、story-brief、project-dashboard 使用 ES Modules；
- 当前项目只有一个状态源；
- 快速切项目不会发生旧响应覆盖；
- Feature 模板无重复 ID；
- 对应 CSS 已迁出且全局无重复规则；
- 320–1440px 手工回归通过；
- 现有 137 项测试继续通过，并新增模型、Store、Service、Route、兼容和静态资源测试；
- 所有 JS 通过 `node --check`；
- `git diff --check` 无新增问题；
- `docs/ARCHITECTURE.md` 与真实目录一致；
- 若无用户可见变化，USER_GUIDE 保持不动；若发生变化，已同步更新；
- README 到 USER_GUIDE 的链接有效；
- 当前工作区其他成果未被覆盖。

## 24. 推荐的实际启动点

第一轮只做：

```text
阶段 0 冻结基线
→ 阶段 1 Characterization
→ 阶段 2 模型/标签/需求校验迁移
```

第二轮再做简单 Persistence：

```text
ProjectsStore CRUD
→ BriefsStore 只读版本
→ Repository 兼容委托
```

跨表事务应单独一轮：

```text
create_project transaction
→ save_draft_brief transaction
→ rollback tests
```

不要第一轮就同时修改模型、SQL、Service、Route、前端和 CSS。该模块真正的风险不在移动文件，而在保持项目初始化和方案同步的事务原子性。
