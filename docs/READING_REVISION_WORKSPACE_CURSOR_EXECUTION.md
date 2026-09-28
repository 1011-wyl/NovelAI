# NovelAI“阅读与修订工作台”前后端实施文档（Cursor 执行版）

> 文档用途：直接交给 Cursor 按阶段实现  
> 实施范围：阅读与修订工作台 MVP，不包含作品库、故事种子和故事分支  
> 产品依据：`docs/NOVELAI_CREATION_CLOSED_LOOP_PRODUCT_PLAN.md`  
> 参考实现：OpenFic 三栏写作页、章节编辑、工具审批、差异和 revision 回滚机制

## 0. 执行规则

Cursor 开始修改前必须先阅读：

- `docs/NOVELAI_CREATION_CLOSED_LOOP_PRODUCT_PLAN.md`
- `docs/USER_GUIDE.md`
- `apps/web/index.html`
- `apps/web/app.js`
- `apps/web/styles.css`
- `novel_agent/models.py`
- `novel_agent/repository.py`
- `novel_agent/service.py`
- `novel_agent/api.py`
- `novel_agent/adapters.py`
- `novel_agent/adapters_remote.py`
- `novel_agent/workflow.py`

实现过程中必须遵守：

1. 保持当前原生 HTML、CSS、JavaScript 技术栈，不引入 React、Vue、TipTap、Tailwind 或前端构建工具。
2. 不把 OpenFic 的 React/Python 代码复制到 NovelAI；只复用交互和领域机制。
3. 不改变现有“确认方案—逐章生成—审核后 READY”的主流程。
4. 不允许 AI 未经批准直接写入正文。
5. 自动保存只保存工作草稿，不能触发正式记忆更新或后续章节重置。
6. 正式提交必须在服务端完成版本、正文、记忆和后续章节处理。
7. 每个阶段先完成后端单元测试，再接前端。
8. 所有用户可见变化必须同步更新 `docs/USER_GUIDE.md`。
9. 保留 README 中用户指南链接，不改变仪表盘及调用记录页面行为。

## 1. 本期目标和验收闭环

本期要让一章现有 READY 正文完成以下闭环：

```text
打开 READY 章节
→ 手工编辑并自动保存工作草稿
→ 选择正文并加入 AI 对话
→ AI 给出建议或待执行修改
→ 查看修改差异
→ 批准或拒绝
→ 将批准结果写入工作草稿
→ 正式提交章节新版本
→ 重建本章记忆
→ 保留并重置后续章节
→ 继续生成下一章
```

完成标准不是“页面看起来像 OpenFic”，而是上述链路可以在刷新、失败、冲突和回滚场景下可靠运行。

### 1.1 本期包含

- OpenFic 风格三栏写作工作区；
- READY 章节标题和纯文本正文编辑；
- 800ms 防抖自动保存工作草稿；
- 章节版本历史；
- 选中文字加入 AI 对话；
- 顾问、共创、编辑三种 AI 模式；
- AI 修改预览、批准、拒绝和会话级回滚；
- 工作草稿正式提交；
- 修订后的摘要、人物、时间线、世界事实和伏笔提取；
- 修改早期章节后的后续章节安全重置；
- 桌面、平板、手机响应式；
- 键盘与基础无障碍支持。

### 1.2 本期不包含

- 富文本格式、图片、Markdown 渲染；
- 多人协作和账号权限；
- token 流式输出；
- 同时编辑多章；
- 自动修复全部后续章节；
- 完整故事分支；
- AI 自动执行工具的“始终允许”设置；
- 编辑 SCHEDULED、PUBLISHED、FAILED 或生成中的章节。

## 2. 已确认的领域规则

### 2.1 可编辑范围

- 只有 `ChapterStatus.READY` 可以进入编辑状态。
- `FAILED`、`WRITING`、`REVIEWING`、`REVISING` 等状态只能查看，并引导用户回创作控制台处理。
- `SCHEDULED` 和 `PUBLISHED` 本期只读，避免修改已经排期或发布的正文。
- `ARCHIVED` 项目只读。
- `PAUSED` 项目允许修订，但提交后仍保持 `PAUSED`。

### 2.2 工作草稿与正式正文

系统同时维护两层内容：

- **正式正文**：`chapters` 当前 READY 内容和正式 `chapter_versions`。
- **工作草稿**：`chapter_edit_drafts` 中未正式提交的标题和正文。

打开章节时：

1. 有工作草稿则展示工作草稿；
2. 没有工作草稿则以正式正文初始化编辑器；
3. 编辑器顶部明确显示“正式版本 vN”或“有未提交修订”；
4. 自动保存只更新工作草稿；
5. 点击“应用修订”才创建新的正式版本。

### 2.3 冲突规则

- 工作草稿保存时携带 `base_version`。
- AI 修改额外携带当前工作副本的 SHA-256 `base_draft_hash`。
- 正式章节版本变化或工作副本 hash 不一致时，服务端返回 HTTP 409。
- 发生冲突后不自动覆盖；前端展示“正文已被其他操作更新”，允许重新加载或复制当前编辑内容。

### 2.4 AI 权限规则

- 顾问模式只能回答，不允许返回可执行写入。
- 共创模式只能给候选内容，不允许写入。
- 编辑模式可以生成 `edit_chapter` 或 `rewrite_chapter` 修改集。
- 两个写入工具固定为 `ask`。
- 待批准修改只能写入 `assistant_change_sets`。
- “批准”只把结果写入工作草稿，不直接提交正式版本。
- “拒绝”不改变正文或工作草稿。

### 2.5 后续章节规则

提交第 N 章修订时：

- 第 N 章保存为新的 READY 正式版本；
- 第 N 章之前的内容不变；
- 第 N 章之后的章节重置为 `PLANNED`；
- 后续章节原有版本必须保留，不再像当前 `rework_chapter` 一样物理删除；
- 运行记录、审核结果、研究资料、发布任务和派生记忆按现有重做规则清理；
- 后续章节可以从版本历史中查看旧内容，并可恢复为新的工作草稿；
- 提交前必须显示会被重置的章节数量和编号范围。

本期不改变现有“重做”按钮的行为；只让新的“应用修订”流程采用保留版本的安全重置。

## 3. 数据库迁移

将 `novel_agent/repository.py` 中 `SCHEMA_VERSION` 从 `4` 提升到 `5`。迁移必须可重复运行，不能破坏已有数据库。

### 3.1 扩展 `chapter_versions`

新增列：

```sql
ALTER TABLE chapter_versions ADD COLUMN title TEXT;
ALTER TABLE chapter_versions ADD COLUMN source TEXT NOT NULL DEFAULT 'workflow';
ALTER TABLE chapter_versions ADD COLUMN is_official INTEGER NOT NULL DEFAULT 0;
```

回填规则：

- `title`：用对应 `chapters.title` 回填；历史标题无法恢复时接受使用当前标题。
- `kind='FINAL'` 的记录设置 `is_official=1`、`source='agent'`。
- `kind='DRAFT'` 的记录保持 `is_official=0`、`source='workflow'`。

新增索引：

```sql
CREATE INDEX IF NOT EXISTS idx_chapter_versions_official
ON chapter_versions(chapter_id, is_official, version DESC);
```

正式修订版本的 `kind` 使用：

- `FINAL`：原工作流生成的正式章节；
- `MANUAL_EDIT`：只包含用户手工修改；
- `AI_EDIT`：只包含 AI 批准修改；
- `MIXED_EDIT`：同时存在手工和 AI 修改；
- `ROLLBACK`：由历史版本或会话回滚产生。

以上四种新增 kind 均设置 `is_official=1`。

必须同步修改现有版本写入和记忆重建查询：

- `commit_ready_chapter` 写入 `title`、`source='agent'`、`is_official=1`；
- `save_draft_version` 写入 `title`、`source='workflow'`、`is_official=0`；
- `rework_chapter` 当前用于重建人物的 `kind='FINAL'` 条件改为 `is_official=1`，否则手工或 AI 正式修订会被记忆重建遗漏；
- 任何“最新正式版本”查询都使用 `is_official=1 ORDER BY version DESC`，不要枚举 kind。

### 3.2 `chapter_edit_drafts`

```sql
CREATE TABLE IF NOT EXISTS chapter_edit_drafts (
    chapter_id TEXT PRIMARY KEY REFERENCES chapters(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    base_version INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('manual','ai','mixed','rollback')),
    applied_change_ids_json TEXT NOT NULL DEFAULT '[]',
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chapter_edit_drafts_project
ON chapter_edit_drafts(project_id, updated_at DESC);
```

`content_hash` 计算方式必须固定：

```python
sha256(f"{title}\0{content}".encode("utf-8")).hexdigest()
```

计算前必须把正文的 `\r\n` 和单独 `\r` 统一为 `\n`；标题去除首尾空白，但正文只规范化换行，不擅自 trim，以免改变用户排版。

### 3.3 `assistant_sessions`

```sql
CREATE TABLE IF NOT EXISTS assistant_sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_assistant_sessions_chapter
ON assistant_sessions(chapter_id, updated_at DESC);
```

### 3.4 `assistant_messages`

```sql
CREATE TABLE IF NOT EXISTS assistant_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES assistant_sessions(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
    mode TEXT NOT NULL CHECK(mode IN ('advisor','coauthor','editor')),
    content TEXT NOT NULL,
    selection_json TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(session_id, sequence)
);
```

### 3.5 `assistant_change_sets`

```sql
CREATE TABLE IF NOT EXISTS assistant_change_sets (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES assistant_sessions(id) ON DELETE CASCADE,
    message_id TEXT NOT NULL REFERENCES assistant_messages(id) ON DELETE CASCADE,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    operation TEXT NOT NULL CHECK(operation IN ('edit_chapter','rewrite_chapter')),
    base_version INTEGER NOT NULL,
    base_draft_hash TEXT NOT NULL,
    before_title TEXT NOT NULL,
    before_content TEXT NOT NULL,
    after_title TEXT NOT NULL,
    after_content TEXT NOT NULL,
    diff_json TEXT NOT NULL,
    explanation TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK(status IN ('PENDING','APPROVED','REJECTED','REVERTED')),
    created_at TEXT NOT NULL,
    decided_at TEXT,
    reverted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_assistant_changes_session
ON assistant_change_sets(session_id, created_at);
```

## 4. Python 模型与错误类型

在 `novel_agent/models.py` 增加严格 Pydantic 模型，不使用无约束 `dict` 代替正式接口。

### 4.1 枚举

```python
class AssistantMode(StrEnum):
    ADVISOR = "advisor"
    COAUTHOR = "coauthor"
    EDITOR = "editor"

class AssistantChangeStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVERTED = "REVERTED"
```

### 4.2 工作草稿模型

```python
class ChapterEditDraft(StrictModel):
    chapter_id: str
    project_id: str
    base_version: int
    title: str
    content: str
    source: Literal["manual", "ai", "mixed", "rollback"]
    applied_change_ids: list[str]
    content_hash: str
    created_at: str
    updated_at: str

class ChapterDraftUpdate(StrictModel):
    base_version: int
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=100_000)
    expected_draft_hash: str | None = None
```

### 4.3 选区与消息模型

```python
class ChapterSelection(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=8_000)
    chapter_version: int = Field(ge=1)
    draft_hash: str

class AssistantMessageCreate(StrictModel):
    content: str = Field(min_length=1, max_length=8_000)
    mode: AssistantMode
    selection: ChapterSelection | None = None
    quick_action: Literal[
        "polish", "shorten", "expand", "visualize", "dialogue"
    ] | None = None
```

增加模型级校验，保证 `end > start`。选区 offset 统一使用 Unicode code point 索引，不直接传浏览器的 UTF-16 offset。前端必须通过下式转换后再发送，避免正文中出现 emoji 或增补字符时错位：

```javascript
const toCodePointOffset = (text, utf16Offset) =>
  Array.from(text.slice(0, utf16Offset)).length;
```

服务端除校验 offset 外，还要校验 `content[start:end] === selection.text`。

### 4.4 AI 输出模型

```python
class AssistantEditProposal(StrictModel):
    operation: Literal["edit_chapter", "rewrite_chapter"]
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=100_000)
    explanation: str = Field(max_length=2_000)

class AssistantGatewayResponse(StrictModel):
    message: str
    proposal: AssistantEditProposal | None = None
```

约束：

- `advisor` 和 `coauthor` 返回 `proposal=None`；
- `editor` 可以不修改正文，但如果返回 proposal，必须生成待批准修改集；
- 服务端不信任模型返回的 operation、标题和长度，必须再次验证。

### 4.5 修订分析模型

```python
class ChapterRevisionAnalysis(StrictModel):
    summary: str = Field(min_length=1, max_length=2_000)
    timeline_event: str = Field(min_length=1, max_length=1_000)
    character_updates: list[CharacterMemoryUpdate] = Field(default_factory=list)
    world_facts: list[WorldFactRecord] = Field(default_factory=list)
    introduced_foreshadows: list[str] = Field(default_factory=list)
    resolved_foreshadows: list[str] = Field(default_factory=list)
```

`WorldFactRecord` 若不适合作为无 ID 的模型，新增 `WorldFactUpdate`，不要让 LLM 生成数据库 ID。

### 4.6 领域错误

增加明确错误类型，避免根据中文字符串判断 HTTP 状态：

- `ChapterNotEditableError` → 409 `CHAPTER_NOT_EDITABLE`
- `EditConflictError` → 409 `EDIT_CONFLICT`
- `AssistantChangeStaleError` → 409 `ASSISTANT_CHANGE_STALE`
- `AssistantChangeStateError` → 409 `ASSISTANT_CHANGE_STATE`
- `RevisionAnalysisError` → 422 `REVISION_ANALYSIS_FAILED`

在 `api.py::_handle_error` 中显式映射这些错误，并返回稳定的 `error`、`message` 和 `details`。

## 5. Repository 实施

在 `SQLiteRepository` 增加以下方法。

### 5.1 工作草稿

```python
get_chapter_edit_draft(project_id, chapter_number) -> ChapterEditDraft | None
upsert_chapter_edit_draft(project_id, chapter_number, update) -> ChapterEditDraft
delete_chapter_edit_draft(project_id, chapter_number) -> None
```

`upsert` 事务要求：

1. 查询项目和章节；
2. 校验项目、章节归属及 `READY` 状态；
3. 校验 `chapters.version == base_version`；
4. 如传 `expected_draft_hash`，校验当前工作草稿 hash；
5. 保存标题、内容和新 hash；
6. 如果已有 AI 来源草稿又发生手工编辑，将 source 更新为 `mixed`；
7. 不修改 `chapters`、`chapter_versions` 或正式记忆。

标题、正文和 hash 的规范化必须集中在 Python helper 中；前端也执行相同换行规范化，但服务端结果始终为权威。

### 5.2 AI 会话和消息

```python
create_assistant_session(project_id, chapter_number) -> AssistantSession
list_assistant_sessions(project_id, chapter_number) -> list[AssistantSession]
get_assistant_session(session_id) -> AssistantSession
delete_assistant_session(session_id) -> None
list_assistant_messages(session_id) -> list[AssistantMessage]
append_assistant_message(...) -> AssistantMessage
create_assistant_change_set(...) -> AssistantChangeSet
get_assistant_change_set(change_id) -> AssistantChangeSet
list_assistant_changes(session_id) -> list[AssistantChangeSet]
approve_assistant_change(change_id) -> tuple[AssistantChangeSet, ChapterEditDraft]
reject_assistant_change(change_id) -> AssistantChangeSet
rollback_assistant_session(session_id, to_message_id) -> ChapterEditDraft
```

删除会话使用软删除：只设置 `assistant_sessions.deleted_at`，普通列表不再返回该会话，但消息和 change set 保留用于正式版本审计。只有删除整个项目时才由外键级联物理删除。

批准事务必须：

- 只允许 `PENDING`；
- 校验正式版本与 `base_version`；
- 校验当前工作副本 hash 与 `base_draft_hash`；
- 将 after 标题和正文写入工作草稿；
- 把 change id 加入 `applied_change_ids_json`；
- 更新 change 为 `APPROVED`；
- 不更新正式章节。

会话回滚规则：

- 目标必须是该会话中的用户消息；
- 找出目标消息之后所有 `APPROVED` 修改；
- 按相反顺序恢复最早修改前的 working copy；
- 将被撤销的修改标记为 `REVERTED`；
- 不删除消息，保证历史可审计；
- 如果当前工作副本在会话修改后又有手工编辑，返回 409，禁止覆盖手工内容。

### 5.3 正式修订提交

新增一个仓储事务方法，建议命名：

```python
commit_chapter_revision(
    project_id,
    chapter_number,
    *,
    expected_base_version,
    expected_draft_hash,
    analysis,
    review,
    base_characters,
) -> ChapterRevisionResult
```

事务内必须完成：

1. 再次校验项目、READY 状态、base version 和 draft hash；
2. 计算正式新版本号；
3. 按 draft source 写入 `MANUAL_EDIT`、`AI_EDIT`、`MIXED_EDIT` 或 `ROLLBACK`；
4. 正式版本 metadata 保存：
   - `official=true`
   - `source`
   - `review`
   - `timeline_event`
   - `character_updates`
   - `world_facts`
   - `introduced_foreshadows`
   - `resolved_foreshadows`
   - `assistant_change_ids`
5. 更新当前章节标题、正文、摘要、版本和时间，状态保持 READY；
6. 写入 `writing_activity_events`，source 为 `user` 或 `agent`，mixed 使用 `user` 并在 metadata 记录 AI；
7. 删除当前章及后续章节的旧派生时间线、非锁定世界事实、伏笔状态和语义文档；
8. 插入修订后当前章的新时间线、世界事实和伏笔变更；
9. 对后续章节保存 `RESET_ARCHIVE` 版本快照，再重置为 `PLANNED`；
10. 保留既有 `chapter_versions`，不得删除；
11. 清理后续章节的 runs、review_reports、research_sources、publish_tasks 和 semantic_documents；
12. 从基础人物和保留到当前章的正式版本 metadata 重建人物档案；
13. 将 `projects.current_chapter` 设置为当前章编号；
14. 项目为 PAUSED 时保持 PAUSED；
15. 删除当前工作草稿；
16. 提交事务。

`RESET_ARCHIVE` 快照 metadata 至少包含：

```json
{
  "official": false,
  "reset_by_chapter": 8,
  "previous_status": "READY",
  "previous_version": 4,
  "summary": "旧章节摘要",
  "plan": {}
}
```

### 5.4 版本查询

扩展 `list_chapter_versions` 返回：

- title；
- source；
- is_official；
- reset archive 元数据；
- 版本创建时间。

版本历史默认只显示正式版本和 `RESET_ARCHIVE`；原工作流的中间 DRAFT 放入“生成草稿”折叠区。

增加“恢复为工作草稿”，而不是直接覆盖正式版本：

```python
restore_chapter_version_to_draft(project_id, chapter_number, version) -> ChapterEditDraft
```

## 6. LLM Gateway 实施

### 6.1 协议扩展

在 `LLMGateway` 增加：

```python
def respond_to_chapter_assistant(
    self,
    *,
    mode: AssistantMode,
    user_message: str,
    selection: ChapterSelection | None,
    project: ProjectRecord,
    chapter: ChapterRecord,
    working_title: str,
    working_content: str,
    recent_summaries: list[str],
    characters: list[CharacterRecord],
    world_facts: list[WorldFactRecord],
    timeline: list[dict[str, object]],
) -> AssistantGatewayResponse: ...

def analyze_chapter_revision(
    self,
    *,
    project: ProjectRecord,
    chapter: ChapterRecord,
    title: str,
    content: str,
    characters: list[CharacterRecord],
) -> ChapterRevisionAnalysis: ...
```

同步补齐：

- `DeepSeekLLMGateway`
- `OfflineLLMGateway`
- `DisabledRemoteGateway`
- 测试中的 fake gateway

### 6.2 编辑提示词硬约束

编辑模式的系统提示必须说明：

- 保留用户未要求修改的剧情事实；
- 不擅自新增关键人物、世界规则或重大转折；
- 有选区时优先只改选区；
- 返回完整的修改后章节正文，便于服务端验证和生成 diff；
- 不允许在正文中加入解释、Markdown 代码块或“修改如下”等说明；
- explanation 单独返回；
- 输出必须通过结构化 JSON 校验。

### 6.3 离线模式

离线模式必须可测试：

- 顾问模式返回固定但与章节标题相关的分析；
- 共创模式返回三个候选建议；
- 编辑模式对选区执行确定性替换；
- 无选区时执行简单全文修订；
- 修订分析生成确定性摘要、时间线和人物更新。

## 7. Service 实施

继续由 `NovelAgentService` 作为 API 入口，不在本期引入新的依赖注入框架。

新增方法：

```python
get_chapter_workspace(project_id, chapter_number)
save_chapter_edit_draft(project_id, chapter_number, request)
discard_chapter_edit_draft(project_id, chapter_number)
commit_chapter_edit_draft(project_id, chapter_number, request)
restore_chapter_version(project_id, chapter_number, version)

create_assistant_session(project_id, chapter_number)
list_assistant_sessions(project_id, chapter_number)
get_assistant_messages(session_id)
send_assistant_message(session_id, request)
approve_assistant_change(change_id)
reject_assistant_change(change_id)
rollback_assistant_session(session_id, to_message_id)
delete_assistant_session(session_id)
```

### 7.1 Workspace 聚合响应

`get_chapter_workspace` 一次返回页面首屏所需数据：

```json
{
  "project": {
    "id": "project_x",
    "title": "书名",
    "status": "ACTIVE"
  },
  "chapter": {
    "id": "chapter_x",
    "number": 8,
    "title": "旧港来信",
    "content": "...",
    "status": "READY",
    "version": 3,
    "updated_at": "..."
  },
  "draft": null,
  "editable": true,
  "read_only_reason": null,
  "downstream": {
    "count": 4,
    "first_number": 9,
    "last_number": 12
  },
  "versions": [],
  "sessions": []
}
```

### 7.2 AI 消息处理

`send_assistant_message` 顺序：

1. 校验 session、project 和 chapter 归属；
2. 取得工作草稿，没有则用正式正文作为 working copy；
3. 验证选区 offset、text、version 和 draft hash；
4. 保存用户消息；
5. 构造受预算约束的上下文；
6. 调用 gateway；
7. 保存 assistant 消息；
8. 如有 proposal，生成服务端 diff 并创建 PENDING change set；
9. 返回新消息和 change set。

本期使用同步请求，不实现 token 流式传输。前端显示“AI 正在分析”，请求期间将当前编辑器设为只读；服务端 hash 校验仍必须保留。

### 7.3 正式提交编排

`commit_chapter_edit_draft` 顺序：

1. 读取并验证 draft；
2. 获取项目、章节、人物、世界和最近章节上下文；
3. 在数据库事务之外调用 `analyze_chapter_revision`；
4. 执行 Story Skills 连续性审校；
5. 审校结果为 REVISE 或 HUMAN_REQUIRED 时仍允许用户提交，但作为 warnings 返回；用户正文拥有最终决定权；
6. 调用仓储正式修订事务，并在事务内再次校验版本/hash；
7. Embedding 启用时删除旧索引并重新索引当前章；索引失败不能恢复旧的错误索引，响应中返回 warning；
8. 返回正式章节、重置章节、记忆变化和审校 warning。

响应示例：

```json
{
  "chapter": {"number": 8, "version": 4, "status": "READY"},
  "reset_chapters": [9, 10, 11, 12],
  "memory_changes": {
    "characters": [{"name": "林夏", "change": "更新了当前目标"}],
    "timeline": [{"event": "调查组进入旧港区"}],
    "world_facts": [],
    "foreshadows": []
  },
  "warnings": [],
  "semantic_index_status": "updated"
}
```

## 8. HTTP API

沿用当前 `BaseHTTPRequestHandler`，不迁移到 FastAPI。

### 8.1 Workspace 与草稿

```text
GET    /api/novels/{project_id}/chapters/{number}/workspace
PUT    /api/novels/{project_id}/chapters/{number}/edit-draft
DELETE /api/novels/{project_id}/chapters/{number}/edit-draft
POST   /api/novels/{project_id}/chapters/{number}/revisions
POST   /api/novels/{project_id}/chapters/{number}/versions/{version}/restore
```

保存草稿请求：

```json
{
  "base_version": 3,
  "title": "第八章 旧港来信",
  "content": "正文",
  "expected_draft_hash": "可选，首次保存为空"
}
```

正式提交请求：

```json
{
  "base_version": 3,
  "expected_draft_hash": "当前工作草稿 hash"
}
```

### 8.2 AI 会话

```text
GET    /api/novels/{project_id}/chapters/{number}/assistant/sessions
POST   /api/novels/{project_id}/chapters/{number}/assistant/sessions
GET    /api/assistant/sessions/{session_id}/messages
POST   /api/assistant/sessions/{session_id}/messages
DELETE /api/assistant/sessions/{session_id}
GET    /api/assistant/sessions/{session_id}/changes
POST   /api/assistant/sessions/{session_id}/rollback
POST   /api/assistant/changes/{change_id}/approve
POST   /api/assistant/changes/{change_id}/reject
```

发送消息请求：

```json
{
  "content": "让这段对话更自然，但保留两个人互相试探的感觉",
  "mode": "editor",
  "quick_action": null,
  "selection": {
    "start": 1250,
    "end": 1428,
    "text": "选择的正文",
    "chapter_version": 3,
    "draft_hash": "..."
  }
}
```

回滚请求：

```json
{
  "to_message_id": "message_x",
  "expected_draft_hash": "..."
}
```

### 8.3 API 安全与限制

- 继续使用 `_read_json` 的 1MB 请求上限；
- 服务端验证所有 project/chapter/session 归属；
- 不接受客户端传入任意工具名；
- 快捷操作使用固定枚举；
- 返回内容统一经过 `_jsonable`；
- 错误响应不能包含提示词、API key 或完整远程模型响应；
- DELETE session 必须删除会话消息和修改集，但不能影响已经写入草稿的内容。

## 9. Diff 实施

使用 Python 标准库 `difflib.SequenceMatcher`，不增加第三方依赖。

### 9.1 两层 diff

1. 先按段落（一个或多个换行）比较；
2. 对 replace 段落再按中文单字、英文单词和标点 token 比较。

token 正则建议：

```python
r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]"
```

`added` 和 `removed` 统计上述 token 数量，不统计行数；前端只显示 `+18 / -9`，不要写成“18 行”。

存储格式：

```json
{
  "added": 18,
  "removed": 9,
  "sections": [
    {
      "type": "content",
      "lines": [
        {"type": "context", "text": "未变化段落"},
        {"type": "removed", "text": "旧文本"},
        {"type": "added", "text": "新文本"}
      ]
    }
  ]
}
```

标题变化作为独立 section。前端默认显示统一 diff，新增绿色、删除红色，但必须同时显示 `+`、`-` 标记，不能只依赖颜色。

## 10. 前端文件组织

避免继续把所有逻辑堆入 `apps/web/app.js`。新增：

```text
apps/web/reader-workspace.js
apps/web/reader-workspace.css
```

`reader-workspace.js` 使用 IIFE 暴露：

```javascript
window.ReaderWorkspace = {
  init({ api, notify, busy }),
  setProject(detail),
  openChapter(chapter),
  destroy()
};
```

`index.html` 按以下顺序加载：

```html
<script src="/dashboard.js"></script>
<script src="/reader-workspace.js"></script>
<script src="/app.js"></script>
```

在 `app.js` 中：

- 保留全局项目加载和章节列表来源；
- 把 `showChapterWithHistory` 的职责交给 `ReaderWorkspace.openChapter`；
- 项目切换时调用 `setProject`；
- 切出 reader 页面时不销毁未提交草稿；
- 切换项目时清理旧 session、timer 和 selection 状态。

## 11. 三栏页面结构

替换当前 `readerView` 内容，结构要求：

```html
<section id="readerView" class="view writing-workspace">
  <aside class="workspace-chapters">...</aside>
  <div class="workspace-resizer" role="separator">...</div>
  <main class="workspace-editor">...</main>
  <div class="workspace-resizer" role="separator">...</div>
  <aside class="workspace-assistant">...</aside>
</section>
```

### 11.1 左栏

- 标题“章节”；
- READY/其他状态筛选；
- 章节列表；
- 当前章节高亮并设置 `aria-current="page"`；
- 显示状态、版本和“未提交”圆点；
- 点击章节前先 flush 当前防抖保存；
- 如果保存失败，阻止切换并提示用户。

### 11.2 中栏

头部：

- 返回目录按钮（移动端）；
- 章节编号；
- 保存状态；
- 版本历史；
- 放弃草稿；
- 应用修订。

编辑区：

- 标题使用 `<input>`；
- 正文使用纯文本 `<textarea>`；
- `spellcheck="false"`，保留换行；
- 文本区拥有独立滚动，不让整个页面随长正文无限增长；
- 显示字数和选中字数；
- READY 以外状态将 input/textarea 设为 readonly。

保存状态使用单个 `role="status" aria-atomic="true"` 区域，依次显示：

- 已保存；
- 保存中；
- 有未保存修改；
- 保存失败，点击重试；
- 正文已发生冲突。

### 11.3 选区工具条

正文存在非空选择且编辑器可编辑时，在编辑器工具栏下方显示固定选区操作条：

```text
已选择 128 字 | 润色 | 精简 | 扩写 | 增强画面 | 调整对白 | 加入对话
```

不要在本期实现复杂的光标位置浮层。固定工具条在 textarea、移动端和键盘操作中更稳定。

快捷动作自动：

1. 打开 AI 面板；
2. 切换到编辑模式；
3. 创建/复用当前 session；
4. 附加 selection；
5. 发送对应 quick_action。

执行快捷动作或“加入对话”前必须先 flush 当前自动保存；只有保存成功并取得最新 `draft_hash` 后才构造 selection。保存失败时不得发送基于未持久化内容的 AI 请求。

“加入对话”只添加引用卡片，不自动发送。

### 11.4 右栏

头部：

- 当前模式切换：顾问、共创、编辑；
- 新建会话；
- 会话历史；
- 本次会话变更汇总。

消息区：

- 用户消息；
- AI 消息；
- 引用正文卡片；
- 待批准修改卡；
- 已批准、已拒绝、已回滚状态；
- “回滚到这里”只出现在用户消息菜单。

输入区：

- 多行 textarea；
- 选区引用 chip；
- Enter 发送、Shift+Enter 换行；
- 请求期间禁用重复发送；
- AI 请求失败时保留输入内容并提供重试。

会话删除在前端表现为“移出会话列表”，不承诺清除审计数据；已有批准修改仍可在章节版本 metadata 中追踪到原 change id。

## 12. 自动保存状态机

前端状态：

```text
clean → dirty → saving → saved
                 ├→ error
                 └→ conflict
```

实现要求：

- title/input 和 content/textarea 的 input 事件都标记 dirty；
- 800ms 防抖；
- 新输入到来时取消旧 timer；
- 同一时间只允许一个保存请求；
- 保存中再次输入则在请求完成后立即进行下一次保存；
- 页面 `visibilitychange`、章节切换、项目切换和 `beforeunload` 时 flush；
- 不依赖 CSS animationend/transitionend 更新真实状态；
- `Ctrl/Cmd+S` 立即保存草稿并阻止浏览器默认行为；
- 保存失败不丢弃本地编辑内容。

不要把正文写入 `localStorage`，SQLite 工作草稿是权威来源；`localStorage` 只保存面板宽度、AI 面板开关和最近章节编号。

## 13. 正式提交交互

点击“应用修订”前先 flush 草稿。

无后续章节时：

- 弹出轻量确认，显示来源、字数变化和新版本号；
- 确认后开始分析和提交。

有后续章节时：

- 使用阻断式对话框；
- 明确显示“将重置第 9–12 章，共 4 章”；
- 说明旧内容会保留在版本历史；
- 主按钮文案为“提交并重置后续章节”；
- 取消按钮为默认焦点；
- Esc 关闭，不执行提交。

提交中：

- 编辑器和按钮只读；
- 显示“分析记忆并提交修订”；
- 不使用全屏 busy 遮挡整个应用；
- 允许用户看到当前章节内容。

提交成功后：

- 更新章节正式版本；
- 清除未提交标记；
- 刷新左侧章节状态；
- 打开“本章记忆变更”摘要；
- toast 显示“第 8 章已更新为 v4，4 个后续章节已安全重置”。

## 14. 响应式与无障碍

### 14.1 桌面 `≥1200px`

- 左栏默认 240px，范围 200–340px；
- 右栏默认 360px，范围 320–480px；
- 中栏最小 480px；
- 拖动 separator 调整宽度；
- separator 支持键盘左右箭头每次调整 16px；
- 宽度保存到 `localStorage`。

### 14.2 平板 `768–1199px`

- 左栏 220px；
- 中栏占剩余空间；
- AI 改为右侧 overlay；
- overlay 打开后 focus 移入，关闭后返回触发按钮。

### 14.3 手机 `<768px`

- 默认只显示中间编辑器；
- 章节目录为左侧抽屉；
- AI 为全屏覆盖层；
- 选择章节后关闭目录；
- 正文选择工具条允许横向内部滚动，但页面主体不能横向滚动；
- 适配 320、375、414px。

### 14.4 基础规范

- 正文基础字号桌面 17–18px、移动端 16px；
- 正文行高 1.8；
- UI 正文不得小于 12px；
- 文字对比度至少 4.5:1；
- 所有图标按钮有 `aria-label` 和 tooltip；
- 点击目标至少 44×44px；
- visible focus 不得移除；
- 不使用 Emoji 作为功能图标；
- `prefers-reduced-motion` 下关闭非必要位移动画；
- Tab 顺序为章节栏 → 编辑器 → AI；
- 抽屉和对话框需要 focus trap；
- Esc 只关闭当前最上层 overlay/dialog。

## 15. 视觉规范

采用 OpenFic 式中性编辑器风格，不使用紫色 AI 渐变。

建议 CSS token：

```css
:root {
  --workspace-bg: #f7f7f5;
  --workspace-panel: #ffffff;
  --workspace-text: #1f1f1d;
  --workspace-muted: #6f706b;
  --workspace-border: #deded9;
  --workspace-hover: #f0f0ed;
  --workspace-active: #e8e8e3;
  --workspace-primary: #242421;
  --workspace-success: #237a49;
  --workspace-danger: #b42318;
  --workspace-focus: #2563eb;
}
```

- 页面以白色正文编辑面和浅灰应用背景区分层级；
- 边框为主，阴影仅用于 overlay、dialog 和浮层；
- hover 150–200ms；
- 保存、批准和提交不能只用颜色表达；
- diff 添加/删除使用低饱和背景，正文保持高对比度。

## 16. 测试计划

### 16.1 Repository 测试

在 `tests/test_repository.py` 或新建 `tests/test_revision_workspace.py` 覆盖：

1. v4 数据库升级到 v5，原项目、章节和版本可读取。
2. migrate 重复执行不报错、不重复数据。
3. READY 章节可创建和更新工作草稿。
4. 非 READY 章节拒绝创建工作草稿。
5. base version 不匹配返回冲突。
6. 草稿 hash 计算稳定。
7. 批准 PENDING change 能原子更新草稿和状态。
8. 重复批准、批准 REJECTED change 被拒绝。
9. change 基于过期 hash 时不覆盖草稿。
10. 回滚会话恢复正确内容并保留消息。
11. 正式修订生成新的 official version。
12. 当前章保持 READY，后续章变为 PLANNED。
13. 后续章节旧版本仍可查询。
14. 当前章之前的章节、版本和记忆不变。
15. 人物记忆从保留正式版本 metadata 重建。
16. 项目删除级联删除工作草稿和 AI 会话。

### 16.2 Service 测试

1. workspace 响应在有/无草稿时正确。
2. advisor/coauthor 不产生 change set。
3. editor 产生 PENDING change set，不直接修改草稿。
4. selection 与正文不匹配时拒绝请求。
5. revision analysis 失败时正式章节和后续章节不变。
6. Story Skills warning 返回前端但不阻断用户提交。
7. PAUSED 项目提交后保持 PAUSED。
8. ARCHIVED、PUBLISHED 和 SCHEDULED 拒绝编辑。
9. Embedding 失败时删除旧索引并返回 warning，不保留错误旧索引。

### 16.3 API 测试

新增轻量 handler/service 测试，至少覆盖：

- 正常 GET/PUT/POST/DELETE；
- 422 Pydantic 校验错误；
- 409 edit conflict；
- 409 stale AI change；
- 404 session/change 不存在；
- 错误响应不泄露提示词和密钥。

### 16.4 前端手工验收

1. 打开 READY 章节后展示正式正文。
2. 编辑后 800ms 自动显示“保存中→已保存”。
3. 刷新页面仍显示未提交工作草稿。
4. `Ctrl/Cmd+S` 立即保存。
5. 选中文字后出现操作条。
6. 加入对话后引用文字和字符数正确。
7. 顾问和共创模式不会出现批准按钮。
8. 编辑模式出现 diff，批准前正文不变。
9. 批准后工作草稿更新，拒绝后不变。
10. 回滚能够恢复相应内容。
11. 正式提交后产生新版本和记忆变更。
12. 修改早期章节时确认框显示准确影响范围。
13. 后续章节重置后旧内容仍能从版本历史查看。
14. 保存失败、AI 失败和提交失败都不会丢失编辑内容。
15. 使用键盘可以选章、编辑、发送、批准、拒绝和关闭对话框。
16. 在 320、375、414、768、1024、1440px 下完成主要流程。

### 16.5 回归命令

```powershell
python -m pytest
python -m ruff check novel_agent tests
python -m pyright novel_agent
```

如项目当前环境未安装某个开发依赖，记录未执行原因，不得伪造通过结果。

## 17. Cursor 分阶段执行顺序

Cursor 必须按以下顺序推进，每阶段完成后先运行相关测试，再进入下一阶段。

### 阶段 A：数据与版本内核

- 数据库 v5 迁移；
- Pydantic 模型和领域错误；
- 工作草稿 CRUD；
- chapter_versions 扩展；
- 安全正式修订事务；
- Repository 测试。

验收：不接前端也能通过 service/repository 完成“保存草稿—提交新版本—重置后续—保留历史”。

### 阶段 B：AI 会话与审批

- AI session/message/change 表和 repository；
- Gateway 协议和离线实现；
- 顾问、共创和编辑模式；
- 服务端 diff；
- 批准、拒绝和回滚；
- Service 测试。

验收：批准前正式正文和草稿均不变化，批准后只改变工作草稿。

### 阶段 C：HTTP API

- workspace、draft、revision、version restore；
- session、message、change、rollback；
- 领域错误映射；
- API 测试。

验收：接口请求响应与本文档完全一致，冲突使用 409。

### 阶段 D：三栏前端

- readerView 重构；
- reader-workspace.js/css；
- 章节切换；
- 编辑器和自动保存；
- 选区工具条；
- AI 面板和会话；
- diff、批准、拒绝、回滚；
- 提交确认和记忆变更。

验收：完整闭环可在离线 LLM 模式下演示。

### 阶段 E：响应式、无障碍和文档

- 桌面 resizer；
- 平板 overlay；
- 手机抽屉与全屏 AI；
- 键盘、focus、ARIA、reduced-motion；
- 更新 `docs/USER_GUIDE.md`；
- 全量测试和手工验收。

## 18. 允许修改的主要文件

主要修改：

- `novel_agent/models.py`
- `novel_agent/repository.py`
- `novel_agent/service.py`
- `novel_agent/api.py`
- `novel_agent/adapters.py`
- `novel_agent/adapters_remote.py`
- `apps/web/index.html`
- `apps/web/app.js`
- `apps/web/styles.css`
- `docs/USER_GUIDE.md`

建议新增：

- `novel_agent/diffing.py`
- `apps/web/reader-workspace.js`
- `apps/web/reader-workspace.css`
- `tests/test_revision_workspace.py`
- `tests/test_assistant_workspace.py`

如果单个文件变得明显过大，可以新增 `novel_agent/revision_service.py` 或 `novel_agent/assistant_service.py`，但不要同时重构与本功能无关的工作流和仪表盘。

## 19. Definition of Done

只有满足以下条件才算本模块完成：

- 数据库旧数据无损升级；
- 原有章节生成和阅读功能通过回归；
- READY 章节可编辑并可靠自动保存；
- 刷新、切章和失败不会丢失草稿；
- AI 写入始终经过差异和用户批准；
- AI 修改可以拒绝和回滚；
- 正式提交创建不可变版本；
- 修改早期章节不会永久丢失后续正文；
- 记忆和时间线与新正式正文一致；
- 桌面、平板和手机主要流程可用；
- 键盘可以完成核心操作；
- 全量测试通过或对无法运行项目给出真实说明；
- `docs/USER_GUIDE.md` 已同步更新；
- 没有把 API key、提示词原文或模型敏感错误暴露到前端。
