# 第一章开篇错位、人物初态污染与 FAILED 恢复闭环——Cursor 执行任务书

> 文档状态：待执行  
> 适用仓库：`D:\实习日报\NovelAI\NovelAI`  
> 技术栈：Python + SQLite + Vue 3 + TypeScript + Pinia + Vitest + Playwright  
> 本文用途：交给 Cursor 在当前未提交修改之上增量实施，不是产品概念稿。

## 1. 任务结论

当前问题不是简单的“审核器太严格”，也不能通过降低审核分数、忽略人物冲突或强行把章节改成 `READY` 解决。

真实故障链如下：

1. 创作方案把人物在中后期才会形成的身份和关系，混进了人物通用简介与 `relationships`。
2. 项目确认时，后端把这些未来信息直接写成第 0 章的不可变事实和当前关系。
3. 生成第一章时，规划器没有确定性绑定 `opening_three_chapters[0]`，实际采用了第二章“完美的缺陷”的情节。
4. 第一章虽然没有上一章，代码仍注入了伪造的开放线索 `异常来源`，并且没有拒绝“承接上一章”式计划。
5. 正文生成器忠实执行了错误细纲，于是没有穿越、贫民窟、危房、能力起点和人物介绍，直接进入广场阵法事件。
6. 审核器拿正文与被污染的第 0 章人物档案比较，发现“林渊与顾铁山初次见面”和“顾铁山已经效忠林渊”冲突，因此给出 `REVISE`，最终进入 `FAILED`。
7. 再次生成时，工作流可能继续复用原来的错误细纲，所以只改文风和长度也无法解决章节定位错误。
8. 阅读页对 `FAILED` 章节仍展示看似可用的 AI 控件，但后端只允许 `READY`，造成“按钮能点、请求必失败”的假交互。

本任务必须同时修复上游数据语义、第一章规划锚定、重做策略、旧项目安全修复和 `FAILED` 用户恢复路径。只改提示词、只改前端按钮或只改审核器都不算完成。

## 2. 已核对的故障证据

### 2.1 目标项目数据

- 小说：`基建：从解析神纹开始`
- 项目 ID：`novel_81ea60d15d734fb8b2861d8435d6a714`
- 项目状态：`ACTIVE`
- `current_chapter = 0`
- 第 1 章标题：`完美的缺陷`
- 第 1 章状态：`FAILED`
- 当前章节版本：v2

创作方案中的开篇三章实际顺序为：

1. `废墟中的解析眼`：穿越贫民窟、觉醒/引出解析能力、修复危房、获得第一桶金、发现古老灵纹。
2. `完美的缺陷`：修复阵法、震惊灵构师、引起顾铁山注意。
3. `暗流涌动`。

数据库中的第 1 章计划却使用了第 2 条，并包含：

- 标题 `完美的缺陷`；
- `opening_hook` 写有“承接上一章结尾”；
- `previous_chapter_excerpt` 实际为空；
- 直接从黑石城广场阵法故障开始；
- 没有第一章应有的穿越、贫民窟、危房、能力起点和必要人物背景。

### 2.2 人物档案污染

- 林渊在方案简介中被写成“黑石城实际掌控者”；
- 顾铁山被写成“被林渊救下后成为代理人”；
- 顾铁山与林渊的关系被写成“效忠对象/恩人”；
- 上述未来发展被直接保存成 chapter 0 的当前状态；
- 正文中的两人却是初次见面。

审核器指出人物关系冲突是合理的；错误发生在人物档案初始化和章节规划上游，不能删除这条审核规则。

### 2.3 最新审校结果

- `decision = REVISE`
- 综合分：58
- 当前质量门代码要求严格高于 60
- 错误码：`REVIEW_RETRY_EXHAUSTED`
- 节点：`QualityHold`

审校还指出：章节长度只有目标的约 81%、存在模板化表达、开篇直接展示系统 UI、主角公开炫技与“稳健隐藏”设定冲突、工程细节空泛、结尾黑影套路化、无灵力修改阵法却立刻生效且缺少世界规则解释。

不要通过调低分数线或把 `REVISE` 改成 `PASS` 掩盖这些问题。

## 3. 开始实施前的强制约束

Cursor 必须先执行并阅读：

```powershell
git status --short
git diff --stat
Get-Content -Raw AGENTS.md
Get-Content -Raw docs/FIRST_CHAPTER_BOOTSTRAP_AND_FAILED_RECOVERY_CURSOR_EXECUTION.md
Get-Content -Raw docs/USER_GUIDE.md
```

当前工作区包含 Vue 3 迁移和后端拆分的大量未提交修改。必须遵守：

- 禁止 `git reset --hard`；
- 禁止 `git checkout -- .`；
- 禁止 `git clean -fd`；
- 禁止为了“恢复干净状态”删除当前 `apps/web/src`；
- 禁止覆盖、回滚或重排与本任务无关的用户修改；
- 禁止删除或重建用户数据库；
- 禁止在应用启动时静默批量修复旧项目；
- 禁止直接手工修改目标小说数据库来代替实现通用修复流程；
- 删除旧代码前必须用 `rg` 证明已经没有引用，并运行对应测试；
- 仅清理由本次替换而失效的分支、函数和样式，不扩大清理范围。

如果发现本文列出的文件已被当前未提交代码进一步修改，应以当前实现为准调整落点，但不能改变本文的完成定义和安全边界。

## 4. 当前代码根因与修改位置

### 4.1 人物方案没有时间语义

文件：`novel_agent/features/story_design/models.py`

`CharacterProfile` 当前只有：

- `profile`
- `personality`
- `core_goal`
- `relationships`

它无法区分稳定事实、开篇初态、开篇关系、未来人物弧线和未来关系。

### 4.2 未来关系直接写入第 0 章

文件：

- `novel_agent/features/story_design/characters.py`
- `novel_agent/infrastructure/persistence/project_setup_store.py`

`build_character_records()` 和 `_sync_characters_and_world()` 都会把 `profile` 变成不可变事实，并把 `relationships` 直接写入 `current_state.relationships`，章号固定为 0。

### 4.3 创作方案提示词无法约束初态/未来态

文件：`novel_agent/integrations/llm/deepseek.py`

`create_brief()` 只是用自然语言要求“初始关系”，结构化 Schema 却没有对应字段。模型把长期人物发展塞进 `profile` 和 `relationships` 后，Pydantic 仍会认为结果合法。

`revise_brief()` 也需要同步修复，否则用户重新生成方案时会再次污染。

### 4.4 第一章没有绑定开篇第一条

文件：

- `novel_agent/workflow.py`
- `novel_agent/ports/llm.py`
- `novel_agent/integrations/llm/deepseek.py`
- `novel_agent/integrations/llm/offline.py`

`plan_chapter()` 收到完整 `creative_brief`，但没有收到一个明确且锁定的 `opening_anchor`。模型返回后只修正 `plan.number`，没有验证标题、核心事件和章节目标是否属于当前章。

### 4.5 第一章被注入伪造历史线索

文件：`novel_agent/workflow.py`

当前代码：

```python
open_threads = [item["event"][:40] for item in timeline[-3:]] or ["异常来源"]
```

第一章没有时间线时仍得到 `异常来源`。这会诱导模型制造未交代来源的异常或错误承接。空历史必须保持为空，不能用虚构占位符补齐。

### 4.6 结构性失败仍复用旧计划

文件：`novel_agent/workflow.py`

当前逻辑只要存在旧计划和 `rework_feedback` 就复用原计划：

```python
if existing and existing.plan is not None and rework_feedback:
    plan = existing.plan
```

当失败原因是开篇错位、人物初态污染或连续性错误时，旧计划本身就是错误源，不能复用。

此外，当前反馈在规划前就被删除；如果后续调用失败，修改意见可能丢失。反馈应在成功生成并保存新计划后再消费。

### 4.7 通用重做会删除审计数据

文件：`novel_agent/repository.py` 的 `rework_chapter()`。

当前实现会删除受影响章节的：

- `review_reports`
- `runs`
- `chapter_versions`
- 研究资料、语义索引和发布任务等

工作台弹窗也明确写着“不可撤销”。这不适合用于修复受污染的第一章，因为用户需要预览、审计和回退。不要直接把现有 `rework_chapter()` 当作开篇修复接口。

### 4.8 FAILED 阅读页前后端能力不一致

后端：

- `novel_agent/chapter_workspace.py` 只把 `READY` 设为 `editable`；
- `send_assistant_message()` 对非 `READY` 抛出“只有 READY 章节可以使用修订助手”；
- `novel_agent/revision_store.py::_require_editable_chapter()` 同样只允许 `READY`。

前端：

- `apps/web/src/features/reader/pages/ReaderPage.vue` 的模式按钮、新建会话、输入框和发送按钮没有按 `editable` 或独立能力禁用；
- `useReaderWorkspace.ts::sendAssistant()` 也没有在请求前判断后端能力；
- 用户只能在点击后收到冲突错误；
- 宽屏 CSS 始终显示右栏，`assistantOpen` 只在 `max-width: 1199px` 生效，所以桌面“关闭”按钮没有视觉效果。

### 4.9 工作台缺少失败诊断与恢复分流

文件：

- `novel_agent/features/projects/detail_reader.py`
- `apps/web/src/api/contracts.ts`
- `apps/web/src/features/workbench/store/workbench.store.ts`
- `apps/web/src/features/workbench/pages/WorkbenchPage.vue`

项目详情目前只有 `latest_events`，没有按章节返回最新失败报告。章节卡只显示原始 `FAILED` 和通用“重做”，无法告诉用户为什么失败，也无法区分“沿用细纲重写”和“重新规划并重写”。

## 5. 完成后的目标行为

### 5.1 新项目

1. 方案明确区分人物稳定事实、开篇初态、初始关系和未来弧线。
2. chapter 0 只保存开篇已经成立的状态。
3. 前三章分别绑定对应开篇锚点。
4. 第一章没有任何上一章摘要、时间线、开放线索或“承接上一章”表达。
5. 第一章自然建立主角当前处境、最低必要世界背景、能力起点、即时目标与冲突；不要求百科式介绍，但不能无来源跳入第二章事件。

### 5.2 失败章节

1. 工作台显示失败原因、分数、主要问题和可执行的恢复动作。
2. 语言、长度、节奏类问题可以“沿用细纲重写”。
3. 开篇定位、人物状态、世界规则和连续性问题必须“重新规划并重写”。
4. `FAILED` 章节可以在阅读页建立工作草稿并使用 AI 顾问/共创/编辑。
5. `FAILED` 草稿不能点击普通“应用修订”直接成为正式章节；只能“重新送审”。
6. 重新送审通过完整质量门后才转为 `READY`；未通过则继续保持 `FAILED`，保留草稿和新审校报告。
7. 所有不可用控件真实禁用并显示原因，不允许假可用。

### 5.3 已污染的旧项目

1. 系统只提供显式“检查开篇数据”入口，不自动改库。
2. 用户先看到可修复性、问题列表、人物初态变化和章节重置范围。
3. 确认时先在同一事务中创建完整修复快照，再应用修复。
4. 修复后仍可通过快照回退。
5. 有任意 `READY`、`SCHEDULED` 或 `PUBLISHED` 正式章节的项目，不能使用自动开篇修复。

## 6. 目标模块结构

不要继续把所有逻辑堆进 `service.py`、`repository.py`、`workflow.py` 或单个 Vue 页面。建议最少拆成：

```text
novel_agent/
  features/
    chapter_planning/
      __init__.py
      models.py              # OpeningAnchor、PlanningContext、ReworkMode
      context.py             # 第一章/普通章节上下文构造
      validation.py          # 锚点和第一章禁用表达校验
      rework_policy.py       # 审校问题 -> REUSE_PLAN / REPLAN
    opening_repair/
      __init__.py
      models.py              # preview/apply/rollback DTO
      service.py             # 资格判断、预览、事务编排
  infrastructure/
    persistence/
      opening_repair_store.py
      migrations/
        opening_repair_v6.py
  interfaces/
    http/
      routes/
        opening_repair.py

apps/web/src/features/workbench/
  api/workbench.api.ts
  components/FailedChapterActions.vue
  components/FailureDetails.vue
  components/OpeningRepairDialog.vue
  types/workbench.types.ts

apps/web/src/features/reader/
  api/reader.api.ts
  components/ChapterRecoveryBanner.vue
  composables/useReaderWorkspace.ts
  pages/ReaderPage.vue
  styles/reader-workspace.css
```

允许根据现有命名略作调整，但领域逻辑、持久化、HTTP 路由和 Vue 展示必须分层。页面不能直接拼接新 URL，HTTP 请求统一放在对应 feature 的 `api` 文件中。

## 7. 第一阶段：重构人物时间语义

### 7.1 扩展模型且保持旧 JSON 可读取

在 `CharacterProfile` 中保留现有字段用于兼容，并新增：

```python
stable_facts: list[str] = Field(default_factory=list, max_length=20)
initial_state: str = Field(default="", max_length=1000)
initial_goal: str = Field(default="", max_length=500)
initial_relationships: dict[str, str] = Field(default_factory=dict)
future_arc: str = Field(default="", max_length=1500)
future_relationships: dict[str, str] = Field(default_factory=dict)
first_appearance_chapter: int | None = Field(default=None, ge=1)
```

语义规则：

- `stable_facts`：姓名、出身等从开篇起稳定成立的信息；
- `initial_state`：故事开始时的身份、处境、资源和能力状态；
- `initial_goal`：开篇正在追求的目标；
- `initial_relationships`：开篇已经成立的关系；
- `future_arc`、`future_relationships`：只供规划参考，绝不能写入 chapter 0 正式记忆；
- 旧 `profile` 是兼容性人物说明，不再整体当作不可变事实；
- 旧 `relationships` 可以读取和展示为“未区分时间的旧字段”，但不得自动提升成 `initial_relationships`。

不要在读取旧 JSON 时写回数据库。兼容转换只能发生在内存中；真正修改旧项目必须走显式修复流程。

### 7.2 修复人物种子构造

`build_character_records()` 和 `_sync_characters_and_world()` 必须共用一个纯函数，避免再次出现两套规则。

chapter 0 只允许写入：

- 主角姓名；
- `stable_facts`；
- 稳定性格特征；
- `initial_state`；
- `initial_goal`；
- `initial_relationships`；
- 项目已有的资源/全知能力安全边界。

禁止把以下字段写入 chapter 0：

- `future_arc`；
- `future_relationships`；
- 旧 `profile` 中无法确认时间点的长期成就；
- 旧 `relationships`；
- “被救后效忠”“后来成为掌控者”等尚未发生的结果。

### 7.3 修复方案生成与方案修订提示

同时修改 `create_brief()` 和 `revise_brief()`：

- 要求所有人物分别填写开篇初态与未来弧线；
- 明确“任何包含后来、最终、被救后、成为、效忠等未来变化的内容只能进入 future 字段”；
- 第一章需要出场的人必须有 `first_appearance_chapter = 1`；
- 初始关系未知时使用空字典，不允许推测；
- 方案修改时不能把未来字段重新合并回简介。

方案编辑前端也要支持新字段；旧项目显示旧字段时加非阻断提示，不能误称其为“当前关系”。

## 8. 第二阶段：建立结构化开篇锚点

### 8.1 新增结构化模型

推荐新增：

```python
class OpeningChapterAnchor(StrictModel):
    number: Literal[1, 2, 3]
    title: str
    core_event: str
    must_establish: list[str] = Field(default_factory=list)
    forbidden_assumptions: list[str] = Field(default_factory=list)
    ending_direction: str = ""
```

在 `CreativeBrief` 中增加 `opening_chapter_anchors`。保留 `opening_three_chapters` 作为旧数据兼容投影。

兼容规则：

- 新方案必须生成三条结构化锚点；
- 读取只有 `opening_three_chapters: list[str]` 的旧方案时，在内存中按索引转换为 anchor，原字符串放入 `core_event`；
- 旧数据标题无法可靠提取时可留空，不得凭空编造；
- 保存新方案时由结构化锚点派生旧展示字段，禁止维护两份可相互冲突的独立数据；
- Vue 合约和方案展示组件必须同时兼容新结构和旧字符串。

### 8.2 使用唯一 helper 解析当前章锚点

新增纯函数：

```python
resolve_opening_anchor(brief, chapter_number) -> OpeningChapterAnchor | None
```

只有第 1–3 章返回对应索引；其他章节返回 `None`。禁止在 DeepSeek、Offline、Workflow 中各写一套索引逻辑。

### 8.3 把锚点作为独立上下文传给 LLM

同步修改：

- `LLMGateway` protocol；
- DeepSeek 实现；
- Offline 实现；
- 所有测试替身；
- `plan_chapter()`；
- 如果继续保留三候选接口，也要修改 `plan_chapter_candidates()` 和选择上下文。

传入独立字段 `opening_anchor`，不要只依赖完整 `creative_brief`。提示必须写明：

- 第 1–3 章必须完成对应 anchor，不得借用相邻章节；
- 第一章不存在上一章；
- 第一章禁止“上一章、承接前文、承接上一章、此前已经、继续上章”等依赖前情表达；
- 第一章必须建立 `must_establish`；
- `forbidden_assumptions` 中的信息在本章开场不能已经成立；
- 不允许把第二章事件提前替代第一章起点。

## 9. 第三阶段：统一章节上下文与确定性校验

### 9.1 清理假上下文

第一章必须强制得到：

```python
recent_summaries = []
timeline = []
open_threads = []
previous_chapter_excerpt = ""
```

把 `or ["异常来源"]` 删除。普通章节没有开放线索时也应为空列表。

语义检索不能把未来章节、失败章节或当前章自身的摘要召回为第一章历史。查询和结果都必须按章节号及正式状态过滤。

### 9.2 模型返回后校验

新增 `validate_plan_against_anchor()`，至少校验：

1. `plan.number == chapter_number`；
2. 第一章不存在依赖前情的禁用表达；
3. 第一章 `previous_chapter_excerpt`、timeline、open threads 均为空；
4. 第 1–3 章标题（anchor 有明确标题时）、核心目标和主要事件与对应 anchor 一致；
5. 第一章人物关系从 `initial_relationships` 出发；
6. 不把 `future_arc` 当作已经发生的事实。

编号不一致可以确定性修正；情节锚点不一致不能只改编号后接受。

建议行为：首次校验失败时，把具体违规项连同锁定 anchor 交给同一 provider 做一次低温度结构化修复；第二次仍失败则抛出可识别错误，例如 `CHAPTER_PLAN_ANCHOR_MISMATCH`，保存诊断但不进入正文写作。

不要做脆弱的单关键词“命中一个词即通过”。结构化 anchor 字段做确定性比较，必要的语义修复只允许一次并保留诊断。

### 9.3 正文生成前的最后门禁

`write_chapter()` 调用前再次断言：

- `plan.number` 正确；
- 第一章没有上一章 excerpt；
- plan 已通过 anchor 校验；
- `character_archives` 中不包含未来弧线作为当前状态。

正文提示明确要求第一章用场景和行动完成必要铺垫，不要以设定百科、系统说明书或大段自述代替叙事。

## 10. 第四阶段：按失败类型选择重做策略

新增枚举：

```python
class ReworkMode(str, Enum):
    AUTO = "auto"
    REUSE_PLAN = "reuse_plan"
    REPLAN = "replan"
```

新增纯函数 `classify_rework_mode(report, chapter_number, plan) -> ReworkMode`。

以下问题必须 `REPLAN`：

- 开篇 anchor 错位；
- 第一章引用上一章；
- `opening_hook` 结构错误；
- `Character Knowledge & State`；
- 人物初态或关系冲突；
- `Plot Consistency` / 连续性冲突；
- 世界规则或能力起点冲突；
- 当前计划标题/目标属于相邻章节；
- 第一章本身缺少开篇建立项。

以下问题在计划正确时可以 `REUSE_PLAN`：

- 长度不足；
- 表达模板化；
- 对话生硬；
- 句式、节奏、冗余和局部可读性问题；
- 不改变事件链的细节补强。

`AUTO` 根据最新审校报告决定。若第 1 章为 `FAILED` 且无法取得可靠报告，安全默认值必须是 `REPLAN`，不能默认复用。

替换 `existing.plan is not None and rework_feedback` 这一粗糙判断。工作流事件应明确记录 `PlanReuse` 或 `PlanRegenerate` 及分类原因。

扩展现有 `/rework` 请求体：

```json
{
  "feedback": "用户补充意见",
  "mode": "auto"
}
```

旧客户端不传 `mode` 时按 `auto` 处理。前端不能把结构性失败展示为可安全“沿用细纲”。

## 11. 第五阶段：旧项目的显式、安全、可回退修复

### 11.1 资格条件

只有同时满足以下条件才允许自动开篇修复：

- `current_chapter == 0`；
- 项目没有任何 `READY`、`SCHEDULED` 或 `PUBLISHED` 章节；
- 第 1 章为 `FAILED` 或 `PLANNED`；
- 项目已经确认方案；
- 用户在预览后明确确认；
- 提交时项目 `updated_at` 与预览一致，防止过期预览覆盖新数据。

任一条件不满足时返回 409 和稳定错误码 `OPENING_REPAIR_NOT_ELIGIBLE`，`details` 中列出原因。

### 11.2 新建 schema v6 修复快照

不要继续把迁移 SQL 塞进 `repository.py::migrate()`。新增独立 migration 文件并把 `SCHEMA_VERSION` 提升到 6。

建议表：

```sql
CREATE TABLE IF NOT EXISTS project_repair_snapshots (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    applied_at TEXT,
    rolled_back_at TEXT
);
```

快照必须覆盖本次事务将修改或清理的所有记录：

- 项目基础字段和 `brief_json`；
- brief versions；
- 第 1 章计划、正文、状态、版本；
- chapter versions 与 edit draft；
- runs、run events、review reports；
- characters；
- world facts、timeline、foreshadows；
- 与该章关联的 research/semantic 数据；
- assistant sessions/messages/change sets（如果修复会触及）。

不要备份 API key、全局设置或无关项目数据。

### 11.3 两步接口

建议增加：

```text
GET  /api/novels/{project_id}/opening-repair-preview
POST /api/novels/{project_id}/opening-repair
POST /api/novels/{project_id}/opening-repair/{snapshot_id}/rollback
```

预览响应至少包含：

```json
{
  "eligible": true,
  "reasons": [],
  "project_updated_at": "...",
  "detected_problems": [],
  "opening_anchor": {},
  "character_changes": [],
  "chapter_changes": [],
  "preserved_artifacts": []
}
```

应用请求至少包含：

```json
{
  "confirm": true,
  "expected_project_updated_at": "..."
}
```

`confirm` 不为 `true` 时拒绝。应用事务顺序：

1. 重新检查资格与乐观锁；
2. 创建完整快照；
3. 把修正后的 brief 保存为新的 brief version，`source = opening_repair`，不覆盖历史版本；
4. 只用初始字段重建 chapter 0 人物状态；
5. 将错误第 1 章重置为可重新规划状态；
6. 保留旧失败正文、计划和审校证据在快照中，必要时额外创建 `FAILED_PRE_REPAIR` 章节版本；
7. 清理只属于错误草稿的派生记忆和语义索引；
8. 提交事务并返回 `snapshot_id` 和下一步动作。

应用修复与生成新第一章要分成两个可观察步骤。修复成功后前端显示“开篇数据已修复，可重新生成第 1 章”，不要在一个不可分辨的长请求里自动继续生成。

回退必须先检查项目没有在修复后产生新的正式章节；不安全时拒绝并说明原因。

### 11.4 不能复用现有破坏性重做

开篇修复不得直接调用当前会删除 runs、reports 和 versions 的 `repository.rework_chapter()`。应实现专用 store/service，并在事务里先快照再变更。

通用重做本次也要至少停止删除可用于审计的审校报告和运行诊断；如果因架构限制仍需清理活动记录，必须先归档或建立可恢复快照。

## 12. 第六阶段：让 FAILED AI 助手形成安全闭环

本任务采用明确策略：允许 `FAILED` 章节使用 AI 修改工作草稿，但禁止绕过审核成为正式章节。

### 12.1 用能力对象替代单一 editable

工作区响应增加：

```json
{
  "capabilities": {
    "edit_draft": true,
    "use_assistant": true,
    "commit_revision": false,
    "submit_for_review": true,
    "replan": true
  }
}
```

状态矩阵：

| 章节/项目状态 | 编辑草稿 | AI 助手 | 普通应用修订 | 重新送审 |
|---|---:|---:|---:|---:|
| READY | 是 | 是 | 是 | 否 |
| FAILED + 非归档项目 | 是 | 是 | 否 | 是 |
| PLANNED/生成中 | 否 | 否 | 否 | 否 |
| 任意章节 + ARCHIVED 项目 | 否 | 否 | 否 | 否 |

保留旧 `editable` 一段兼容期也可以，但 Vue 新代码必须使用细粒度能力，不能再用一个布尔值推断全部动作。

### 12.2 存储层按用途放宽，不要全局放开

把 `_require_editable_chapter()` 重构为显式用途或允许状态参数，例如：

```python
_require_chapter_for_action(..., action=WorkspaceAction.EDIT_DRAFT)
```

- `EDIT_DRAFT`、`ASSISTANT`：允许 `READY` 和 `FAILED`；
- `COMMIT_REVISION`：只允许 `READY`；
- `SUBMIT_FAILED_REVIEW`：只允许 `FAILED`。

禁止简单删除状态判断，否则 `PLANNED`、生成中和归档章节也会被意外编辑。

### 12.3 新增 FAILED 重新送审接口

建议：

```text
POST /api/novels/{project_id}/chapters/{number}/review-submit
```

请求继续使用 `base_version` 和 `expected_draft_hash` 做并发校验。

重新送审必须复用生产工作流的完整质量门，而不是复用当前“连续性不通过只给 warning 仍可提交”的普通修订流程：

- 结构性 plan/anchor 校验；
- 连续性审核；
- 可读性审核；
- 题材写作规则审核；
- 现有质量分数与 decision 合并规则；
- 人物更新只在最终 PASS 后应用。

结果规则：

- PASS：归档旧失败版本，保存新正式版本，状态改为 `READY`，再更新人物/时间线/语义索引；
- REVISE：保持 `FAILED`，保留工作草稿，保存新 report，返回 422 或有明确状态的 200 响应；前后端必须统一；
- HUMAN_REQUIRED：保持数据和草稿，返回明确人工处理原因；
- 任何异常都不能把半完成记忆提交到正式状态。

### 12.4 阅读页交互

`FAILED` 时在编辑器顶部显示可聚焦的恢复横幅：

- 当前章节未通过审核；
- 展示前 3 条主要问题；
- “返回工作台重新规划”；
- “编辑草稿并重新送审”。

按钮和输入框要求：

- 模式按钮、新建会话、AI 输入框和发送按钮绑定 `capabilities.use_assistant`；
- 发送时同时判断输入非空、非 busy、session 可用和能力允许；
- 禁用时显示原因，不发送请求；
- 普通“应用修订”在 FAILED 隐藏或禁用，改显示“重新送审”；
- 错误容器使用 `role="alert"` 或 `aria-live="assertive"`；
- 状态提示使用 `aria-live="polite"`；
- 键盘焦点在失败后移到错误摘要；
- 不依赖颜色单独表达状态。

### 12.5 桌面助手关闭必须真实生效

当前 1200px 以上右栏恒显。二选一，但必须选定并测试：

1. 推荐：桌面也允许折叠，`assistant-open`/`assistant-closed` 改变 grid 列，关闭后中间编辑区扩展；
2. 如果产品决定桌面恒显，则移除宽屏“关闭”按钮，只在 overlay 断点显示。

本任务推荐方案 1。使用 grid class 切换，避免用可拖拽、可漂浮面板。保留用户偏好时需要按项目或全局说明清楚，并保证刷新后状态一致。

## 13. 第七阶段：工作台失败诊断与恢复操作

### 13.1 项目详情增加按章诊断

在 detail reader 中增加只读字段，例如：

```json
{
  "chapter_failures": [
    {
      "chapter_number": 1,
      "error_code": "REVIEW_RETRY_EXHAUSTED",
      "node": "QualityHold",
      "decision": "REVISE",
      "score": 58,
      "issues": [],
      "recommended_rework_mode": "replan",
      "opening_repair_eligible": true
    }
  ]
}
```

后端返回稳定机器字段，中文标签由前端集中映射。不要让页面解析 pipeline 文本猜错误类型。

### 13.2 FAILED 章节卡

每个失败章节至少显示：

- “未通过审核”，不要只显示英文 `FAILED`；
- 分数和最新审核时间；
- 主要问题摘要；
- “查看审校意见”；
- “重新规划并重写”；
- 仅在 `recommended_rework_mode == reuse_plan` 时显示“沿用细纲重写”；
- 满足资格时显示“检查并修复开篇数据”。

生成主按钮也要感知未解决的下一章失败状态。此时按钮文案改为“重新生成第 1 章”或“继续修复第 1 章”，不能让用户误以为会生成第 2 章。

### 13.3 修复预览对话框

`OpeningRepairDialog.vue` 展示：

- 为什么判断为开篇数据污染；
- 当前第一章与正确 anchor 的对比；
- 哪些人物关系会从“当前状态”移动到“未来弧线”；
- 哪些草稿/报告会被保存；
- 哪些派生数据会被重置；
- 可回退说明；
- 明确确认按钮。

不得使用只有一个“修复”按钮且不显示影响范围的危险交互。

## 14. 审核器修正边界

审核器应比较：

- chapter 0 的正式初始状态；
- 已通过正式章节产生的当前状态；
- 当前章节计划允许发生的关系变化；
- 当前草稿实际写出的变化。

审核器不得把 `future_arc` 或 `future_relationships` 当作已经发生的事实。

第一章额外检查：

- 不存在上一章承接；
- 使用第一个 opening anchor；
- 关系只能从初始关系出发；
- 能力首次出现符合世界规则；
- 当前章不能被方案第二/三章覆盖。

这些修改不能削弱对真正连续性冲突的检测。测试必须证明“未来关系不再误报”，同时“已经成立的初始关系被正文违反”仍会报错。

## 15. API、错误码和文档

若按本文新增接口，至少增加稳定错误码：

- `CHAPTER_PLAN_ANCHOR_MISMATCH`
- `OPENING_REPAIR_NOT_ELIGIBLE`
- `OPENING_REPAIR_PREVIEW_STALE`
- `OPENING_REPAIR_ROLLBACK_UNSAFE`
- `FAILED_DRAFT_REVIEW_REQUIRED`
- `CHAPTER_ACTION_NOT_ALLOWED`

HTTP 约定：

- 资格/状态冲突：409；
- 请求字段错误：422 或项目既有约定的 400，但全项目统一；
- 重新送审未通过：选择 422 或成功响应中的 `passed: false`，前后端和 `docs/API.md` 必须保持一致；
- 不要把业务拒绝返回成 500；
- `details` 提供机器可读原因，`message` 提供可直接展示的中文说明。

实际实施涉及用户可见流程、状态、HTTP endpoint、数据库迁移和排错方式，必须在同一变更更新：

- `docs/API.md`
- `docs/USER_GUIDE.md`

用户指南面向非开发者，至少说明：

- 为什么章节会显示“未通过审核”；
- “沿用细纲重写”和“重新规划并重写”的区别；
- 如何使用 AI 修改 FAILED 草稿并重新送审；
- 如何预览、确认和回退开篇数据修复；
- 哪些项目不能自动修复；
- 修复不会静默删除正式章节。

检查 README 中指向 `docs/USER_GUIDE.md` 的链接仍有效。

## 16. 测试矩阵

### 16.1 Python 单元/集成测试

新增或扩展：

- `tests/story_design/test_models_compat.py`
- `tests/story_design/test_service.py`
- `tests/test_workflow.py`
- `tests/test_deepseek_gateway.py`
- `tests/test_revision_workspace.py`
- `tests/projects/test_routes.py`
- opening repair service/store/route 的独立测试文件

必须覆盖：

1. 旧 CreativeBrief JSON 在无新字段时仍可反序列化。
2. 新项目的 `future_relationships` 不进入 chapter 0 current state。
3. 旧 `relationships` 不会被静默当作初始关系。
4. `stable_facts`、`initial_state` 和 `initial_relationships` 正确进入初始档案。
5. 第一章解析到第一个 opening anchor，第二章解析到第二个。
6. 第一章的 summaries、timeline、open threads、previous excerpt 全为空。
7. 第一章计划出现“承接上一章”会被修复一次或明确拒绝。
8. 第一章错用第二章标题/核心事件时不会进入正文生成。
9. 结构性失败重做时不复用旧计划。
10. 普通语言/长度失败在计划正确时可以复用计划。
11. rework feedback 只有在新计划成功保存后才被消费。
12. 审核器不把未来弧线当作当前事实。
13. 真正违反初始关系时审核仍会失败。
14. FAILED 工作草稿可以保存并使用 AI。
15. FAILED 草稿不能走 READY 普通提交接口。
16. FAILED 重新送审 PASS 后变为 READY。
17. FAILED 重新送审 REVISE 后仍为 FAILED，草稿和报告保留。
18. opening repair 对有正式章节的项目返回不可修复。
19. opening repair 预览不修改任何数据库记录。
20. stale preview 不能应用。
21. apply 前创建快照；apply 失败时事务整体回滚。
22. rollback 能恢复原 brief、人物、章节、run 和 report。
23. 修复一个项目不会影响其他项目。
24. 当前目标项目的数据形态有回归 fixture：第一章 anchor 为第 1 条，顾铁山未来效忠不进入 chapter 0。

所有 LLM 测试使用 Recording/Fake/Offline gateway，不调用真实付费 API。

### 16.2 Vue Vitest

至少覆盖：

1. FAILED 章节卡展示中文原因、分数和恢复操作。
2. `replan` 失败不显示误导性的“沿用细纲重写”。
3. 修复预览完整显示影响范围并要求明确确认。
4. FAILED 阅读页显示恢复横幅。
5. FAILED 的 AI 输入可用，普通“应用修订”不可用，“重新送审”可用。
6. 后端 capability 为 false 时模式、新建、输入和发送都不可用且不发请求。
7. API 失败后错误摘要有 `role=alert`，焦点行为可验证。
8. READY 的编辑、AI 和提交功能不回退。
9. 桌面关闭 AI 后 grid 真正收起右栏，再打开可恢复。
10. 移动端 overlay 行为不回退。

### 16.3 Playwright

使用独立临时数据库，不得连接或复制覆盖用户数据库。覆盖：

1. 创建新小说 -> 确认方案 -> 生成第 1 章。
2. 第 1 章使用第一条 anchor，不是第二章。
3. 第一章上下文不存在“承接上一章”。
4. 构造 FAILED -> 工作台查看原因 -> 重新规划并重写。
5. FAILED -> 阅读页 -> AI 修改草稿 -> 重新送审。
6. 审核未通过时仍 FAILED 且草稿存在。
7. 审核通过时进入 READY。
8. 符合条件的旧项目可以预览修复、确认、查看 snapshot 并回退。
9. 有正式章节的项目看不到危险的自动修复确认动作。

## 17. 验收命令

先运行最小相关测试，修正后再运行全量：

```powershell
python -m unittest tests.story_design.test_models_compat -v
python -m unittest tests.story_design.test_service -v
python -m unittest tests.test_deepseek_gateway -v
python -m unittest tests.test_workflow -v
python -m unittest tests.test_revision_workspace -v
python -m unittest tests.projects.test_routes -v

Set-Location apps/web
npm run lint
npm run type-check
npm run test
npm run build
npm run test:e2e
npm run test:e2e

Set-Location ../..
python -m unittest discover -s tests -v
git diff --check
git status --short
git diff --stat
```

连续执行两次 E2E 是为了发现临时数据库、localStorage、工作草稿或助手会话造成的状态泄漏。

如果存在与本任务无关的基线失败，必须记录“命令、失败测试、失败信息、为何判断为基线”，不能静默跳过，也不能声称全量通过。

## 18. 完成定义

只有同时满足以下条件才能向用户报告完成：

- 人物初态和未来弧线已在 Schema、提示词、持久化和审核中贯通；
- 第一章/前三章有确定性 anchor，不再只靠模型自行理解完整方案；
- 第一章历史上下文严格为空；
- 结构性失败会重新规划；
- 旧项目修复有预览、确认、快照和回退；
- `FAILED` AI 可用但不能绕过质量门；
- 工作台能解释失败并提供正确恢复动作；
- 桌面 AI 关闭行为真实生效；
- 后端、前端、E2E 测试覆盖关键状态；
- `docs/API.md` 与 `docs/USER_GUIDE.md` 已同步；
- 没有破坏现有未提交修改；
- 没有真实调用付费 LLM；
- 没有修改用户数据库来伪造验收结果。

## 19. Cursor 最终回报模板

Cursor 完成后必须按以下格式汇报：

```text
1. 根因修复
- 人物时间语义：
- 开篇 anchor：
- 第一章上下文：
- 重做策略：

2. FAILED 恢复闭环
- 工作台诊断：
- AI 草稿：
- 重新送审：
- 桌面助手折叠：

3. 旧项目安全修复
- 资格判断：
- 快照：
- 应用：
- 回退：

4. 主要文件
- 新增：
- 修改：
- 删除（含无引用证据）：

5. 数据库与 API
- schema 版本：
- 新接口：
- 兼容策略：

6. 测试结果
- Python：
- lint：
- type-check：
- Vitest：
- build：
- Playwright 第一次：
- Playwright 第二次：
- git diff --check：

7. 文档
- docs/API.md：
- docs/USER_GUIDE.md：
- README 链接：

8. 未完成项或已知风险
- 没有则写“无”；不得省略失败命令。
```

## 20. 可直接复制给 Cursor 的提示词

```text
请在仓库 D:\实习日报\NovelAI\NovelAI 中，严格执行：

docs/FIRST_CHAPTER_BOOTSTRAP_AND_FAILED_RECOVERY_CURSOR_EXECUTION.md

这是一次真实的前后端修复，不是让我获得建议或示例代码。请直接检查当前工作区、实现代码、补齐测试、更新文档并完成验证。

开始前必须先运行并阅读：

git status --short
git diff --stat
Get-Content -Raw AGENTS.md
Get-Content -Raw docs/FIRST_CHAPTER_BOOTSTRAP_AND_FAILED_RECOVERY_CURSOR_EXECUTION.md
Get-Content -Raw docs/USER_GUIDE.md

当前工作区已经有大量 Vue 3 迁移和后端拆分的未提交修改。必须在现有修改上增量实现，严禁 git reset --hard、git checkout -- .、git clean -fd，严禁删除或重建用户数据库，严禁覆盖与本任务无关的修改。不要启动时静默批量改旧项目，也不要直接手工修改“基建：从解析神纹开始”的数据库来伪造修复结果。

必须解决完整根因链：

1. CharacterProfile 区分稳定事实、开篇初态、初始关系、未来弧线和未来关系；旧 JSON 仍可读取，但旧 relationships 不得静默变成 chapter 0 当前关系。
2. build_character_records 与项目确认同步必须共用同一套人物种子规则，future 字段永远不能写入 chapter 0。
3. 新增结构化 opening anchor，并为旧 opening_three_chapters 提供只读兼容转换。
4. 第一至第三章确定性绑定各自 anchor；第一章 recent summaries、timeline、open threads、previous excerpt 必须全空；删除“异常来源”假占位。
5. 对 LLM 返回的细纲做 anchor 校验。第一章出现“承接上一章”或错用第二章情节时，最多做一次受限修复，仍失败则明确报 CHAPTER_PLAN_ANCHOR_MISMATCH，不得继续写正文。
6. 按审校问题区分 reuse_plan 与 replan。开篇错位、人物状态、世界规则和连续性问题必须重新规划；长度、语言、局部节奏问题才可复用计划。失败反馈只能在新计划成功保存后消费。
7. 为旧项目实现显式的 opening repair preview/apply/rollback，带资格判断、乐观锁、schema v6 完整快照和事务回退。不得直接复用会删除审计记录的旧 rework_chapter。
8. 工作台按章显示失败分数、问题、建议重做模式和开篇修复入口；未解决第 1 章失败时不能把按钮误写成“生成下一章”。
9. FAILED 章节允许编辑工作草稿并使用 AI，但禁止通过普通应用修订绕过审核；新增重新送审闭环，只有完整质量门 PASS 才转 READY，失败则保留 FAILED、草稿和报告。
10. 用 capability 对象统一前后端状态。不可用控件必须禁用并解释原因，不允许点击后才收到必然失败。错误摘要需要 role=alert/aria-live。
11. 宽屏“关闭助手”必须真正折叠右栏并扩展编辑区；不要引入可拖拽或漂浮面板。
12. 按任务书要求补齐 Python、Vitest、Playwright 测试。所有 LLM 测试使用 fake/offline gateway，不调用真实付费 API，E2E 使用独立临时数据库。
13. 同步更新 docs/API.md 与 docs/USER_GUIDE.md，并确认 README 的用户指南链接有效。

代码必须按领域、持久化、HTTP、前端 api/store/components/pages 分模块组织，不要继续把所有逻辑塞进 service.py、repository.py、workflow.py 或一个 Vue 页面。页面不能直接拼接新接口 URL。

不要通过降低审核阈值、忽略人物冲突、强制 READY 或删除审核器解决问题。审核器应忽略“尚未发生的 future arc”，但仍必须拦截真正违反初始关系和正式记忆的正文。

实现过程中先跑相关小测试，再跑全量。最后严格执行任务书第 17 节的全部命令，包括连续两次 npm run test:e2e 和 git diff --check。遇到与本任务无关的基线失败要如实记录，不得跳过或虚报通过。

完成后按任务书第 19 节模板汇报：根因修复、FAILED 闭环、旧项目修复、主要文件、schema/API、每条测试命令结果、文档更新、未完成项和风险。不要只说“已完成”。
```
