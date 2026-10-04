# 第一章开篇恢复与 FAILED 闭环修复执行文档（Cursor）

> 适用项目：`D:\实习日报\NovelAI\NovelAI`  
> 前置任务：`docs/FIRST_CHAPTER_BOOTSTRAP_AND_FAILED_RECOVERY_CURSOR_EXECUTION.md`  
> 文档性质：在前置任务已大体完成的基础上，修复验收发现的数据安全、质量门、上下文污染和前端恢复问题。  
> 执行原则：先修复数据安全，再修复审核闭环，最后处理 UI、测试和文档；不得用跳过测试、隐藏错误或修改用户数据库的方式“通过验收”。

## 1. 当前结论

前置任务已经完成了 Schema v6、结构化开篇锚点、第一章空历史、FAILED 工作区、AI 修订、开篇修复接口、桌面助手折叠和大部分测试。但当前版本仍不能验收通过，原因如下：

1. opening repair rollback 使用 `INSERT OR REPLACE` 恢复 `projects`，会触发 SQLite `ON DELETE CASCADE`。
2. 已实测 rollback 会删除自己的 snapshot，并丢失未包含在快照中的后续 `PLANNED` 章节。
3. FAILED 重新送审没有复用生产工作流的完整质量门。
4. opening repair apply 没有清理错误第一章的旧研究资料，旧上下文可能再次污染新第一章。
5. 显式 `reuse_plan` 可以覆盖服务端结构性失败分类。
6. 修复快照 ID 只存在于 Vue 页面内存中，刷新后无法回退。
7. 部分前端影响范围展示、错误可访问性、能力降级和 CSS 仍不符合任务书。

本轮不是重新设计整套系统。应保留已经正确工作的模块和测试，只对下述缺口做最小、可验证的模块化修复。

## 2. 强制安全规则

1. 不得读取、复制覆盖、迁移或修改用户正在使用的数据库。
2. 所有数据库测试必须使用 `tempfile.TemporaryDirectory()`、测试 fixture 或 Playwright 独立临时目录。
3. 不得执行：

   ```text
   git reset --hard
   git checkout -- .
   git clean -fd
   ```

4. 工作区已有大量未提交修改。不得回滚、格式化或清理与本任务无关的文件。
5. 不得把所有新逻辑继续塞进 `workflow.py`、`chapter_workspace.py` 或单个 Vue 页面。
6. 不得通过降低 `QUALITY_PASS_SCORE`、把失败改成 warning、直接改成 `READY` 或让前端假装成功来绕过质量门。
7. 不得让前端成为 capability、rework mode 或 rollback safety 的最终真源。
8. 用户可见流程、HTTP 接口、故障处理和回退方式发生变化时，必须同步更新：

   - `docs/API.md`
   - `docs/USER_GUIDE.md`

9. README 指向 `docs/USER_GUIDE.md` 的链接必须继续有效。
10. 删除旧代码前必须用 `rg` 证明没有生产引用；不允许为了“清理”进行大范围删除。

## 3. 必须保留的已完成能力

以下能力已经基本正确，本轮不得回退：

- `SCHEMA_VERSION = 6`；
- `CharacterProfile` 的 initial/future 字段分离；
- `character_seed.py` 作为人物 chapter 0 种子唯一规则；
- `OpeningChapterAnchor` 及旧字符串兼容转换；
- 第一章 recent summaries、timeline、open threads、previous excerpt 为空；
- 第一章 plan 最多一次受限修复，失败报 `CHAPTER_PLAN_ANCHOR_MISMATCH`；
- FAILED 工作区允许编辑和 AI，普通“应用修订”不可用；
- 工作台展示失败诊断与重新规划入口；
- 桌面关闭 AI 助手后右栏真实收起；
- 目标项目 fixture：`基建：从解析神纹开始`，顾铁山未来效忠不进入 chapter 0；
- 现有正常 READY 阅读、编辑和 AI 流程。

## 4. 实施顺序

必须按以下顺序实施和提交验证：

1. rollback 数据安全；
2. opening repair 研究资料清理；
3. 共享完整质量门；
4. rework 策略和反馈消费时机；
5. 持久化回退入口和前端恢复体验；
6. 锚点校验稳健性；
7. CSS、测试、API 文档和用户指南；
8. 全量回归。

若第 1 项未通过，不得继续宣称任务完成。

## 5. P0：修复 rollback 级联删除

### 5.1 根因

当前代码：

- `novel_agent/infrastructure/persistence/opening_repair_store.py::restore_payload()`
- `_restore_table(..., "projects", ..., replace=True)`
- `_restore_table()` 将 `replace=True` 转成 `INSERT OR REPLACE`

SQLite 的 `REPLACE` 不是普通更新。它会先删除原 `projects` 行，再插入新行。数据库已启用 `PRAGMA foreign_keys = ON`，项目子表使用 `ON DELETE CASCADE`，因此会删除：

- `project_repair_snapshots`；
- 所有 chapters；
- brief versions、人物、世界事实；
- runs、reports、研究资料；
- 其他与项目关联但未包含在 opening snapshot 中的数据。

现有测试仅断言 rollback 函数返回 `rolled_back=True`，没有检查实际数据库状态。

### 5.2 修复要求

1. 禁止对 `projects` 使用 `INSERT OR REPLACE`。
2. 新增专用方法，例如：

   ```python
   def update_project_from_snapshot(
       conn: sqlite3.Connection,
       project_id: str,
       project_row: dict[str, Any],
   ) -> None:
       ...
   ```

3. 该方法必须执行普通 `UPDATE projects SET ... WHERE id=?`。
4. 不更新主键，不删除项目行，不触发任何项目级级联。
5. `cursor.rowcount != 1` 时抛出明确异常并让事务整体回滚。
6. 只清理和恢复 opening repair 明确触及的数据，不能先删除整个项目树。
7. rollback 完成后再把 snapshot 更新为：

   ```text
   status = rolled_back
   rolled_back_at = 当前时间
   ```

8. `mark_rolled_back()` 必须验证确实更新了 1 行；更新 0 行不能返回成功。
9. 同一 snapshot 第二次 rollback 必须返回明确的业务错误。
10. rollback 中任一步失败，项目数据和 snapshot 状态必须全部保持 rollback 前状态。

### 5.3 数据保留边界

rollback 只能恢复本次 opening repair 修改的内容。以下数据即使存在，也不能因为 rollback 被删除：

- 第 2 章及以后未受修复影响的 `PLANNED` 章节；
- 这些章节的 versions、runs、reports 或工作草稿；
- 项目级无关审计数据；
- 其他项目的任何记录。

### 5.4 必须新增的 Python 测试

至少增加：

1. `rollback` 后 snapshot 仍存在，状态为 `rolled_back`，`rolled_back_at` 非空。
2. rollback 前后第 2 章 `PLANNED` 记录完全一致。
3. 第 2 章的 version、run、report、draft 不丢失。
4. 原 brief、人物、第一章、run、report、research 和 semantic 数据能恢复。
5. rollback 中途注入异常时事务整体回滚。
6. 第二次 rollback 被拒绝。
7. 修复一个项目不影响另一个项目。

测试不能只检查 service 返回值，必须直接查询数据库或通过 repository 读取记录并逐项比较。

## 6. P1：清理错误第一章研究资料

### 6.1 当前问题

`OpeningRepairService._apply_transaction()` 当前只删除：

- 第 1 章 timeline；
- `chapter_id` 等于第一章的 semantic documents。

它没有删除旧 `research_sources`。工作流会调用 `list_research_sources(project_id)`，高可靠性旧资料会重新进入 `compact_research`，从而继续污染重新生成的第一章。

### 6.2 修复要求

1. 在创建完整 snapshot 后，确定错误第一章对应的 research source IDs。
2. eligibility 已保证 `current_chapter = 0`、没有正式章节；在此范围内清理：

   - `chapter_id = 第一章 ID` 的 research sources；
   - 明确属于本项目错误开篇生成过程的 legacy `chapter_id IS NULL` research sources；
   - `source_type = 'research_source'` 且 `source_id` 对应上述来源的 semantic documents；
   - 直接以第一章 ID 建立的其他 semantic documents。

3. 删除顺序必须避免孤儿索引：先删除关联 semantic documents，再删除 research sources。
4. 被删除内容必须已在 snapshot 中完整记录，rollback 能恢复。
5. 不要清理其他项目或后续正式章节的资料。
6. 对 legacy `chapter_id IS NULL` 的归属判断必须写成独立、可测试的 store 方法，不允许散落字符串 SQL。

### 6.3 必须新增的测试

- apply 后错误第一章研究资料不再出现在 `list_research_sources()`；
- 对应语义索引被删除；
- 重新生成第一章时 `compact_research` 不含旧错误资料；
- rollback 后研究资料与索引完整恢复；
- 其他项目资料不受影响。

## 7. P1：抽取共享完整质量门

### 7.1 当前问题

生产工作流审核包括：

- plan/anchor 结构校验；
- 基础确定性检查：篇幅、排除项、主角、重复度等；
- prose audit；
- readability；
- Story Skills；
- 人物关系 guard。

`ChapterWorkspaceService.submit_failed_chapter_review()` 目前只执行 readability、可选 Story Skills 和人物关系 guard，没有执行基础检查与 prose audit，却在前端显示“完整质量门”。

### 7.2 模块结构

新增共享模块，建议：

```text
novel_agent/features/chapter_review/
  __init__.py
  models.py
  quality_gate.py
```

`quality_gate.py` 提供公开服务，例如：

```python
@dataclass(slots=True)
class ChapterQualityGate:
    gateway: LLMGateway
    story_skills: StorySkillsRuntime
    writing_skills: OhStoryWritingRuntime

    def review(
        self,
        *,
        repository: SQLiteRepository,
        project: ProjectRecord,
        plan: ChapterPlan,
        content: str,
        protagonist_name: str,
        previous_chapter_excerpt: str,
        has_research: bool,
        characters: list[CharacterRecord],
    ) -> ReviewReport:
        ...
```

具体命名可调整，但必须满足：

1. 生产工作流和 FAILED 重新送审调用同一个公开质量门。
2. 不允许在 `chapter_workspace.py` 中调用 `ChapterWorkflow._review()` 私有方法。
3. 不允许复制两套相似检查逻辑。
4. 合并报告时保留最低分、所有去重后的 issue 和全部 checks。
5. `HUMAN_REQUIRED` 优先级最高。
6. 只有最终 `decision = PASS` 且分数严格高于现有阈值时才能转 `READY`。
7. 未通过时：

   - chapter 继续保持 `FAILED`；
   - edit draft 保留；
   - 新 review report 保存；
   - 返回结构化 review；
   - 不提交正式记忆。

8. 通过时才调用 `commit_failed_chapter_review()`。

### 7.3 HTTP 语义

“审校执行成功但结果未通过”是正常业务结果，不是请求格式错误。统一改为：

```text
HTTP 200
{
  "passed": false,
  "message": "重新送审未通过质量门，草稿已保留",
  "review": { ... },
  "chapter": { ... },
  "draft": { ... }
}
```

以下情况才返回 4xx：

- 请求字段错误；
- base version/hash 冲突；
- 当前状态不允许重新送审；
- 缺少草稿或细纲。

同步更新 `docs/API.md`。

### 7.4 必须新增的测试

- 低于目标篇幅的 FAILED 草稿不能通过；
- 命中 `exclude` 的草稿不能通过；
- 主角缺失或重复度超标不能通过；
- prose audit blocker 不能通过；
- readability、Story Skills、关系 guard 都参与最终报告；
- 未通过仍为 FAILED，草稿和报告存在；
- 完整质量门通过后才转 READY；
- 生产工作流和重新送审对同一内容给出一致的基础检查结果。

## 8. P1：服务端约束 rework mode

### 8.1 禁止结构性失败强制 reuse

当前 `resolve_requested_mode()` 对显式 `reuse_plan` 直接接受。改为：

1. 先根据最新 review report 计算服务端分类。
2. 如果分类是 `REPLAN`，客户端请求 `reuse_plan` 必须拒绝，返回：

   ```text
   code = REWORK_MODE_NOT_ALLOWED
   message = 当前失败涉及开篇、人物状态、连续性或世界规则，必须重新规划
   ```

3. 客户端可以在服务端允许 `REUSE_PLAN` 时主动选择 `replan`，但不能反向降级。
4. `auto` 继续采用服务端分类。
5. 前端只能展示后端返回的 allowed modes/recommended mode，不能自行判断结构性安全。

### 8.2 reuse 时重新校验锚点

即使复用旧计划，也必须在写作前执行：

- `validate_plan_against_anchor()`；
- 完整 `assert_write_gate()`；
- 第一章空历史校验。

验证失败时不得进入 Writer。

### 8.3 反馈消费时机

当前 workflow 在 `update_chapter(... plan=plan)` 之前删除 `rework_feedback` 和 `rework_mode`。必须改为：

1. 先生成并验证 plan；
2. 成功持久化 plan；
3. 再删除 feedback/mode；
4. 最好把保存 plan 与消费 setting 放进同一事务。

新增“计划保存失败时 feedback 仍存在”的测试。

## 9. P1：持久化回退入口

### 9.1 后端接口

新增明确的查询接口：

```text
GET /api/novels/{project_id}/opening-repair-snapshots/latest
```

返回：

```json
{
  "snapshot": {
    "id": "repair_xxx",
    "status": "applied",
    "created_at": "...",
    "applied_at": "...",
    "rollback_allowed": true,
    "blocked_reason": null
  }
}
```

没有可回退快照时返回：

```json
{ "snapshot": null }
```

要求：

- 只返回当前项目的 opening repair 快照；
- 不返回 `payload_json`；
- 后端实时计算 `rollback_allowed`；
- 产生正式章节后返回 `rollback_allowed=false` 和原因；
- 项目不存在时保持现有 404 语义。

### 9.2 Vue 状态

删除 `WorkbenchPage.vue` 中把 `lastSnapshotId` 作为唯一来源的做法。

建议新增：

```text
features/workbench/api/opening-repair.api.ts
features/workbench/store/opening-repair.store.ts
```

或在现有 workbench store 中建立独立状态，但页面不得自己维护业务真源。

工作台加载项目后查询 latest snapshot。必须满足：

- 应用修复后立即显示回退按钮；
- 刷新页面后仍显示；
- 切换项目不会串用 snapshot ID；
- rollback 成功后按钮消失并重新加载项目；
- rollback 不安全时按钮禁用并显示后端原因；
- API 加载失败时不显示假可用按钮。

## 10. 前端恢复体验与可访问性

### 10.1 OpeningRepairDialog

修改 `OpeningRepairDialog.vue`：

1. 每次 `open` 从 false 变为 true 时，把 `confirmed` 重置为 false。
2. preview 或 `project_updated_at` 变化时也重置。
3. 关闭后再次打开必须重新勾选。
4. 完整展示：

   - `detected_problems`；
   - opening anchor；
   - `character_changes.from_relationships`；
   - `character_changes.to_relationships`；
   - `moved_to_future`；
   - `chapter_changes`；
   - `preserved_artifacts`；
   - 回退说明。

5. 不得只显示“当前关系移出 chapter 0”这种无法审计的通用句子。
6. loading 时按钮真实禁用并有状态文本。

### 10.2 FAILED 恢复横幅

`ChapterRecoveryBanner.vue` 必须：

- 使用 `role="alert"` 或适当的 `aria-live="assertive"`；
- 保留 `tabindex="-1"`；
- 当当前章节首次进入 FAILED 或送审再次失败时，把焦点移到横幅容器；
- 不要在每次普通响应式更新时抢夺焦点；
- 恢复动作使用语义化 `<button>`；
- 不依赖颜色表达 FAILED。

`ui-ux-pro-max` 验收依据：失败摘要需要被读屏宣布，提交失败后键盘焦点应落在摘要或其标题；不能只有 toast 或红色边框。

### 10.3 送审未通过的前端行为

HTTP 200、`passed=false` 时：

1. 显示“仍未通过审核，草稿已保留”；
2. 将结构化 review issues 更新到页面；
3. 重新加载 project detail 和 chapter workspace；
4. 焦点移动到 FAILED 恢复横幅；
5. 编辑器内容和草稿不得丢失。

### 10.4 capability 降级

`useReaderWorkspace.ts` 中 API 未返回 capabilities 时，不得根据 `status === FAILED` 自行开放 AI 和编辑。

兼容降级必须保守：

```ts
{
  edit_draft: false,
  use_assistant: false,
  commit_revision: false,
  submit_for_review: false,
  replan: false
}
```

同时显示“服务器未返回工作区能力，请刷新或升级后端”，不能表现成可点击后再失败。

### 10.5 CSS 修复

修复 `apps/web/src/features/workbench/styles/workbench.css` 开头缺少选择器的声明：

```css
border: ...;
border-radius: ...;
padding: ...;
```

确认这些声明属于哪个组件后放回正确选择器。不得仅删除构建警告而丢失应有布局。`npm run build` 必须没有 CSS 语法警告。

## 11. 锚点校验稳健性

### 11.1 当前问题

`validation.py::_overlap_score()` 主要按中文标点切分。长中文短语会成为整句 token，模型只要换一种表达就可能得到 0 分。

### 11.2 修复要求

使用确定性、可解释且不依赖外部模型的组合校验：

1. 保留章节号和 sibling anchor 排除逻辑。
2. 标题可以是直接绑定证据，但不能成为唯一证据。
3. 优先检查结构化 `must_establish` 和 `forbidden_assumptions`。
4. 对 `core_event` 与 plan blob 做中文字符级 2-gram/3-gram 相似度，而不是整句 token 精确相等。
5. 归一化空白、标点、章节前缀和常见停用表达。
6. 输出可解释的 issue，说明缺少哪个 establish 项或命中了哪个 forbidden assumption。
7. 阈值必须通过正负 fixture 校准并写入常量，不能散落 magic number。
8. 不能用 embedding 或真实 LLM 作为写作前硬门，避免非确定性和额外费用。

### 11.3 测试样本

至少覆盖：

- 原文一致：通过；
- 同一事件的中文合理改写：通过；
- 只改标题但正文是第二章事件：失败；
- 命中 sibling anchor：失败；
- 缺失关键 `must_establish`：失败；
- 命中 `forbidden_assumptions`：失败；
- 第一章出现“承接上一章”：失败。

## 12. 测试要求

### 12.1 Python

先运行相关测试：

```powershell
python -m unittest tests.opening_repair.test_service tests.chapter_planning.test_bootstrap tests.test_revision_workspace tests.test_workflow -v
```

再运行全量：

```powershell
python -m unittest discover -s tests -v
```

不得删除或放宽现有断言。

### 12.2 Vue

补充 Vitest：

1. repair dialog 每次打开和 preview 变化都重置确认框；
2. from/to relationships 和 chapter changes 可见；
3. FAILED 横幅有 alert/live region；
4. FAILED 出现和送审失败时焦点落到横幅；
5. capability 缺失时所有写能力关闭且不发请求；
6. `passed=false` 时页面刷新 review、保留草稿；
7. refresh 后 latest snapshot 恢复回退按钮；
8. rollback 后状态清空。

运行：

```powershell
cd apps/web
npm run lint
npm run type-check
npm run test
npm run build
```

### 12.3 Playwright

扩充 `apps/web/e2e/opening-recovery.spec.ts`，必须覆盖：

1. FAILED 草稿重新送审未通过：仍为 FAILED、草稿存在、新 issues 可见；
2. FAILED 草稿完整质量门通过：才进入 READY；
3. opening repair apply 后刷新页面：回退按钮仍存在；
4. rollback 后 snapshot 状态为 rolled_back；
5. rollback 后原第一章、run、report、research 恢复；
6. 第 2 章 PLANNED fixture 不丢失；
7. repair dialog 关闭重开后必须重新勾选；
8. 错误横幅可聚焦且有 alert 语义；
9. 后端 capability=false 时 AI 模式、新建会话、输入和发送都禁用且不发请求。

连续运行两次排除偶发问题：

```powershell
cd apps/web
npm run test:e2e
npm run test:e2e
```

Playwright 必须继续使用独立临时数据库。

## 13. 文档同步

代码完成后同步：

### `docs/API.md`

- latest repair snapshot 查询接口；
- rollback 成功和不安全响应；
- review-submit 的 HTTP 200 + `passed=false` 业务语义；
- `REWORK_MODE_NOT_ALLOWED`；
- capability 字段为后端真源。

### `docs/USER_GUIDE.md`

用非开发者语言说明：

- 为什么重新送审后可能仍然显示“未通过审核”；
- 草稿不会因为未通过而消失；
- 哪些问题必须重新规划；
- 为什么有时不能沿用旧细纲；
- 如何在刷新或重启后回退开篇修复；
- 什么情况下回退会被安全阻止；
- 修复会清理哪些错误第一章派生资料；
- capability 缺失时为什么操作会暂时禁用。

不要在用户指南中暴露内部表名或实现术语。

## 14. 完成定义

只有同时满足以下条件才能报告完成：

- [ ] rollback 不删除项目行，不触发项目级 cascade；
- [ ] rollback 后 snapshot 仍存在且为 rolled_back；
- [ ] 第 2 章及以后未受影响数据不丢失；
- [ ] 错误第一章 research/semantic 上下文被清理且可回退；
- [ ] 生产生成和 FAILED 送审共用完整质量门；
- [ ] 未通过送审仍为 FAILED，草稿和报告保留；
- [ ] 结构性失败不能强制 reuse_plan；
- [ ] rework feedback 只在 plan 保存成功后消费；
- [ ] 刷新后仍可发现并执行安全 rollback；
- [ ] repair dialog 完整展示影响范围并每次重新确认；
- [ ] FAILED 错误摘要可被键盘和读屏发现；
- [ ] capability 缺失时前端保守禁用；
- [ ] anchor 合理中文改写不会被误杀；
- [ ] build 无 CSS 语法警告；
- [ ] Python、Vitest、Playwright 全部通过；
- [ ] Playwright 连续两轮通过；
- [ ] `docs/API.md`、`docs/USER_GUIDE.md` 已同步；
- [ ] 未修改用户数据库；
- [ ] 未破坏工作区既有未提交修改。

## 15. Cursor 最终回报格式

Cursor 完成后必须按以下结构回复，不能只说“已完成”：

```text
1. 数据安全
- rollback 根因：
- 修复方式：
- 如何证明未触发 cascade：
- snapshot 与第 2 章数据完整性测试：

2. 质量门
- 新共享模块：
- 生产 workflow 接入点：
- FAILED review-submit 接入点：
- 未通过/通过行为：

3. 开篇上下文
- research/semantic 清理范围：
- rollback 恢复方式：
- anchor validator 改进：

4. 前端
- 持久化 rollback 入口：
- repair dialog：
- FAILED 横幅和焦点：
- capability fallback：
- CSS：

5. 测试
- Python 最小测试：
- Python 全量：
- lint：
- type-check：
- Vitest：
- build：
- Playwright 第一次：
- Playwright 第二次：

6. 文档
- docs/API.md：
- docs/USER_GUIDE.md：
- README 链接：

7. 文件
- 新增：
- 修改：
- 删除及无引用证据：

8. 安全声明
- 使用的测试数据库路径/生成方式：
- 是否触碰用户数据库：否
- 是否保留既有未提交修改：是
```

## 16. 可直接发送给 Cursor 的提示词

```text
请在当前 NovelAI 仓库中严格执行：

docs/FIRST_CHAPTER_RECOVERY_REMEDIATION_CURSOR_EXECUTION.md

这是上一轮“第一章开篇初始化、FAILED 恢复和旧项目修复”任务的阻断缺陷修复，不是重新设计项目。请先完整阅读该文档、仓库根目录 AGENTS.md，以及前置文档 docs/FIRST_CHAPTER_BOOTSTRAP_AND_FAILED_RECOVERY_CURSOR_EXECUTION.md，再开始修改。

执行优先级不可调整：
1. 先修复 opening repair rollback 的 INSERT OR REPLACE 级联删除。必须改为 UPDATE 项目行，并用临时数据库证明 snapshot 不消失、第 2 章 PLANNED 及其子数据不丢失。
2. 清理错误第一章的 research_sources 和对应 semantic_documents，同时保证 snapshot/rollback 可恢复。
3. 抽取公开、共享的完整章节质量门，让生产 workflow 和 FAILED review-submit 共用。不得调用私有 ChapterWorkflow._review，也不得复制两套检查。
4. 服务端禁止结构性失败强制 reuse_plan；任何复用计划都重新做 anchor 校验；feedback 只能在 plan 成功保存后消费。
5. 增加 latest repair snapshot 查询，让刷新或重启后仍能安全回退。
6. 修复 repair dialog 状态重置、完整影响范围、FAILED alert/focus、保守 capability fallback、review-submit 失败刷新和 workbench.css 语法错误。
7. 改进中文 anchor 确定性校验，并补齐文档规定的 Python、Vitest、Playwright 回归。
8. 更新 docs/API.md 和 docs/USER_GUIDE.md，保持 README 用户指南链接有效。

安全要求：
- 不得读取、复制覆盖或修改用户数据库。
- 所有测试使用 tempfile 或 Playwright 独立临时数据库。
- 不得执行 git reset --hard、git checkout -- .、git clean -fd。
- 工作区已有大量未提交修改，不得回滚、覆盖或格式化无关文件。
- 不得降低质量阈值、跳过审核、把失败改成 warning 或直接写 READY。
- 不得用前端状态代替后端安全判断。
- 不得大范围删除旧代码；删除前必须提供 rg 无引用证据。

工作方式：
- 先检查当前代码与测试，列出将修改的具体文件和原因。
- 按文档阶段逐项实施，每完成一个阶段先运行最小相关测试。
- 修复过程中若发现文档假设与当前代码不符，以数据安全和现有公开行为为优先，说明差异后采用最小兼容实现。
- 最后运行 Python 全量、lint、type-check、Vitest、build，并连续运行两次 Playwright。
- build 不得残留 CSS 语法警告。
- 最终严格使用文档第 15 节格式回报，附测试数量和结果。不要只回复“全部完成”。
```
