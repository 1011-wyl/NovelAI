# 章节质量标准对齐与自动修订闭环——Cursor 执行任务书

> 文档状态：待执行  
> 适用仓库：当前仓库根目录
> 技术栈：Python + SQLite + Vue 3 + TypeScript + Pinia + Vitest + Playwright  
> 前置修复：`docs/FIRST_CHAPTER_RECOVERY_REMEDIATION_CURSOR_EXECUTION.md`  
> 本文用途：交给 Cursor 在当前大量未提交修改之上增量实施。本文不是概念建议，所有“必须”均为验收项。

## 1. 任务结论

当前章节经常第一次生成就低分，不是单纯因为模型能力不足，而是生成、审核和失败恢复三段逻辑没有形成同一套闭环：

1. 正文生成提示只给出概括性的写作要求，没有拿到审稿器实际使用的完整八维评分标准和通过阈值。
2. 可读性审稿器实际要求八项全部不低于 75、平均分不低于 82；任一维度低于 75 都会生成 `MAJOR`。
3. 共享质量门又规定任意 `BLOCKER` 或 `MAJOR` 都不能通过，因此页面所说的“60 分通过”并不是完整规则。
4. 多个审核报告合并时取最低分，单个审核器的低分会成为最终显示分，但用户看不到各组件分数和真正阻断项。
5. 正文生成温度为 `0.85`，在规则较多时容易牺牲约束稳定性。
6. `MAX_REVISION_ATTEMPTS` 已从配置注入工作流，但当前质量循环硬编码为 `range(1)`。
7. 第一次审核不通过时，`workflow.py` 在 `attempt == 0` 分支立即返回 `FAILED`；下方 `revise_chapter()` 代码实际不可达。
8. `revise_chapter()` 只收到原正文、简化后的修改指令和目标字数，没有收到章节细纲、人物档案、世界规则、开篇锚点和上一章结尾，修订时可能解决语言问题却破坏连续性。
9. 部分确定性检查过于粗糙，例如低于目标字数 90% 一律 `MAJOR`、正文没有出现主角姓名就一律 `MAJOR`，可能误伤第一人称或代称叙事。

本任务必须同时完成：

- 生成器与审核器使用同一份可执行质量契约；
- 生成后先做低成本确定性预检；
- 审核失败后自动根据报告修订并重新审核；
- 结构性问题自动重新规划，而不是只润色错误细纲；
- 自动循环有上限、能检测无进展，不会无限消耗 Token；
- 真正耗尽尝试后才进入 `FAILED`；
- 对没有硬阻断的问题提供明确、需用户确认的兜底继续方式；
- 前后端、API、用户指南和测试保持一致。

不得通过简单降低总分、忽略 `BLOCKER`、删除连续性检查或直接把失败章节改成 `READY` 来伪造完成。

## 2. 开始前必须执行

Cursor 必须先执行并阅读：

```powershell
git status --short
git diff --stat
Get-Content -Raw AGENTS.md
Get-Content -Raw docs/FIRST_CHAPTER_RECOVERY_REMEDIATION_CURSOR_EXECUTION.md
Get-Content -Raw docs/USER_GUIDE.md
Get-Content -Raw novel_agent/features/chapter_review/quality_gate.py
```

然后定位当前实现：

```powershell
rg -n "range\(1\)|MAX_REVISION_ATTEMPTS|max_revision_attempts|review_readability|write_chapter|revise_chapter|ReviewIssue|ReviewReport" novel_agent tests apps/web
```

必须以当前工作区代码为基线，不得假设仓库是干净状态。

## 3. 强制安全和范围规则

1. 不得修改、覆盖、迁移或复制用户正在使用的正式 SQLite 数据库。
2. 所有后端测试使用 `tempfile.TemporaryDirectory()` 或独立测试 fixture。
3. Playwright 必须继续使用独立临时数据库和独立数据目录。
4. 禁止执行：

   ```text
   git reset --hard
   git checkout -- .
   git clean -fd
   ```

5. 不得回滚、格式化或清理与本任务无关的既有修改。
6. 不得删除当前 Vue 3 前端或恢复旧版原生 JS 页面。
7. 不得把新逻辑全部堆进 `workflow.py`、`deepseek.py` 或单个 Vue 页面。
8. 删除不可达旧分支前必须先用 `rg` 确认引用，并用测试覆盖替代行为。
9. 用户可见流程、配置、HTTP 接口、失败恢复和成本说明发生变化时，必须同步更新：

   - `docs/API.md`
   - `docs/USER_GUIDE.md`

10. README 中指向 `docs/USER_GUIDE.md` 的链接必须继续有效。

## 4. 已核对的代码证据

### 4.1 生成器不知道完整评分门槛

文件：`novel_agent/integrations/llm/deepseek.py::write_chapter()`

当前正文提示包含世界规则、人物知识、场景因果、读者回报和结尾钩子，但没有把以下审稿契约结构化传入：

- 八个可读性维度的名称和解释；
- 单项最低 75；
- 平均最低 82；
- 哪些条件会形成 `MAJOR`；
- 哪些硬规则会直接阻断。

正文生成 `temperature=0.85`，对约束密集型长文本偏高。

### 4.2 审稿器使用了另一套更严格的规则

文件：`novel_agent/integrations/llm/deepseek.py::review_readability()`

当前实际规则：

```text
opening_hook
scene_causality
conflict_escalation
character_agency
dialogue_voice
showing_specificity
reader_payoff
ending_hook
```

- 任一维度低于 75：必须产生 `MAJOR`；
- 任一维度低于 75：`REVISE`；
- 平均分低于 82：`REVISE`；
- 存在任意 `MAJOR/BLOCKER`：`REVISE`。

这些数字硬编码在审稿方法里，没有与生成提示共享唯一来源。

### 4.3 自动修订代码不可达

文件：`novel_agent/workflow.py`

当前结构：

```python
for attempt in range(1):
    ...
    if report.decision == PASS:
        break
    if attempt == 0:
        return FAILED
    content = gateway.revise_chapter(...)
```

由于循环只有 `attempt == 0`，所有非 PASS 都在调用 `revise_chapter()` 前返回。`max_revision_attempts` 虽然已配置并注入，但没有生效。

### 4.4 修订上下文不足

当前 `revise_chapter(content, instructions, target_chars)` 不知道：

- 当前章节细纲和 scene beats；
- 创作方案和文风；
- 主角及人物当前状态；
- 世界规则；
- 开篇锚点；
- 上一章结尾；
- 本轮完整审核报告和各维度分数。

这会使修订模型只能局部改句子，无法可靠解决连续性、人物能动性和读者回报问题。

### 4.5 “最终分数”语义不透明

`merge_review_reports()` 当前使用各报告最低分作为最终 `score`。最低分可以继续作为保守门控依据，但前端和 API 必须同时展示：

- 各审核组件得分；
- 最低分来自哪个组件；
- 真正阻止通过的问题；
- 普通建议。

不能再让用户把一个最低子项分误解成简单平均分。

## 5. 完成后的目标流程

### 5.1 正常章节

```text
规划章节
→ 生成首稿（携带统一质量契约）
→ 去 AI 味处理
→ 确定性预检
→ 完整质量门
→ PASS：提交 READY
→ REVISE：根据问题自动修订或重新规划
→ 再次预检和完整审核
→ 达到尝试上限仍不通过：FAILED，并保留全部版本和报告
```

默认 `MAX_REVISION_ATTEMPTS=2` 的准确语义必须是：

```text
1 次首稿 + 最多 2 次自动修订 = 最多 3 次完整审核
```

`MAX_REVISION_ATTEMPTS=0` 表示首稿审核后不自动修订，主要用于测试、低成本模式和显式配置；不得被解释为无限次。

### 5.2 问题分流

后端必须确定性分类，不能信任模型自行决定如何恢复。

#### A. 正文可修复问题：复用细纲修订

- 篇幅不足；
- 开篇钩子偏弱；
- 场景因果不清；
- 冲突升级不足；
- 主角能动性不足；
- 对话同质；
- 具体描写不足；
- 读者回报不足；
- 结尾钩子偏弱；
- 去 AI 味问题；
- 局部重复。

#### B. 结构问题：重新规划后重写

- 第一章锚点错位；
- 计划建立在不存在的上一章上；
- 人物初态、关系或知识边界错误；
- 世界硬规则冲突；
- 章节核心目标与 opening anchor 不一致；
- 计划本身提前释放未来剧情；
- 同一结构性问题在正文修订后仍然存在。

#### C. 技术错误：重试请求但不计入质量修订次数

- 网络超时；
- 供应商 429/5xx；
- 空响应；
- JSON 修复后仍无法解析；
- 明确的供应商截断。

技术重试必须继续服从现有网关重试上限，不能无限重试，也不能伪装成章节质量低。

#### D. 人工处理

- 审核明确返回 `HUMAN_REQUIRED`；
- 自动修订次数耗尽；
- 连续两次正文完全相同；
- 同一问题指纹连续两轮不变且分数没有提升；
- 重新规划一次后仍然存在同一结构问题。

### 5.3 不允许自动绕过的硬阻断

- 明确违反用户排除项；
- 第一章错误承接不存在的前文；
- 未来人物关系或未来事实被当作当前事实；
- 已死亡人物在没有合理机制时正常行动；
- 世界硬规则直接冲突；
- 正文为空或供应商明确标记截断；
- 章节与锁定开篇锚点不一致；
- 正式记忆或时间线本身需要人工修复。

## 6. 目标模块结构

在现有 `novel_agent/features/chapter_review/` 基础上拆分：

```text
novel_agent/features/chapter_review/
  __init__.py
  quality_spec.py          # 唯一质量契约、阈值、维度和提示片段
  preflight.py             # 低成本确定性预检
  issue_policy.py          # issue 分类、恢复动作、硬阻断判断
  revision_context.py      # 完整修订上下文 DTO 和指令构造
  recovery.py              # 有界自动修订状态机
  quality_gate.py          # 共享完整审核，不负责无限循环
```

允许根据当前代码调整文件名，但职责必须分开。`workflow.py` 只负责编排章节生命周期，不应继续包含大段评分、分类和指令拼接逻辑。

## 7. P0：建立唯一质量契约

### 7.1 `quality_spec.py`

至少定义：

```python
READABILITY_DIMENSIONS = (...)
READABILITY_DIMENSION_MIN_SCORE = 75.0
READABILITY_AVERAGE_MIN_SCORE = 82.0
QUALITY_PASS_SCORE = 60.0
LENGTH_PASS_RATIO = 0.90
LENGTH_MAJOR_RATIO = 0.80
```

并提供结构化模型或函数，例如：

```python
@dataclass(frozen=True, slots=True)
class ChapterQualitySpec:
    ...

def build_writer_quality_contract(...) -> dict[str, Any]:
    ...

def build_reviewer_quality_contract(...) -> dict[str, Any]:
    ...
```

要求：

1. 生成器和审稿器从同一个模块读取维度、阈值和硬规则。
2. `deepseek.py` 不得继续硬编码另一份 75/82/维度列表。
3. 质量契约必须进入生成 JSON，上下文键建议为 `quality_contract`。
4. 首稿提示明确要求在输出前内部核对质量契约，但最终仍只输出标题和正文，不输出自评表。
5. 第一章质量契约额外包含：无上一章、必须建立的 opening anchor、禁止提前成立的事实。
6. 第二章以后额外包含：直接承接上一章未完成动作，不复述上一章。
7. 写作温度从 `0.85` 调整到更稳定的 `0.70`～`0.75`；选择一个固定默认值并用测试锁定，不新增无必要配置。
8. 审稿温度继续保持低温。

### 7.2 阈值不能互相矛盾

保留当前严格规则时，用户文档必须明确：

- 总分严格高于 60 只是基础条件；
- 可读性还要求八项最低分和平均分；
- `BLOCKER/MAJOR` 仍会阻止提交；
- 首稿失败后系统会自动修订，而不是立即停住。

如果实现中调整 75 或 82，必须同时修改生成契约、审稿器、测试、API 文档和用户指南，禁止只改一处。

## 8. P0：修复确定性预检和误判

### 8.1 拆出预检

将当前 `review_structural()` 中适合程序判断的规则拆入 `preflight.py`：

- 正文字数；
- 明确排除项；
- 空正文/截断；
- 重复段落；
- 第一章禁用前情表达；
- opening anchor 的 must/forbidden；
- 可确定的人物关系和世界规则 guard。

预检应在昂贵的 AI 可读性审稿前执行。若已有硬阻断或明显可修复问题，可先自动修订，再进入完整 AI 审核，避免为确定性失败重复付费。

### 8.2 字数规则

统一字符统计：

- 去掉标题行；
- 忽略空白字符；
- 使用一个后端公共函数；
- 测试中文、英文、标点和换行。

严重度建议固定为：

```text
达到目标 90% 及以上：通过长度预检
达到 80% 但不足 90%：MINOR，要求补足但不单独形成硬阻断
低于 80%：MAJOR，进入自动补写
```

不要再让 89.9% 与 90% 之间的微小计数差异成为整章永久失败原因。

### 8.3 主角检查

禁止继续用“正文不包含主角姓名”直接认定主角缺失：

1. 姓名出现可以作为正证据。
2. 姓名未出现只能产生 `MINOR` 提醒，不能单独形成 `MAJOR`。
3. 主角是否实际推动剧情由 `character_agency` 审核判断。
4. 第一人称、代称叙事和标题未写姓名必须有测试。

### 8.4 AI 严重问题证据

1. AI 返回的 `MAJOR/BLOCKER` 必须有证据或明确的“缺失型规则”依据。
2. 引用型证据必须能在当前正文或正式上下文中定位。
3. 没有证据的主观问题不能升级为硬阻断；可以保留为 `MINOR`。
4. 维度分低于阈值属于机器可验证的审稿结果，可以用 `维度名 + 分数 + 阈值` 作为结构化证据。
5. 未知类别的 `MAJOR` 按保守策略处理，但必须在日志和报告中标为 `unknown_category`，便于排查。

## 9. P0：恢复有界自动修订循环

### 9.1 删除一次性提前返回

移除以下设计：

- `for attempt in range(1)`；
- “quality is intentionally a one-shot gate” 注释；
- `if attempt == 0: return FAILED` 的不可达修订结构。

不得简单改成 `range(max_revision_attempts)` 后保留错误的 attempt 语义。必须明确区分：

```text
review_attempt：审核序号，从 1 开始
revision_count：已经执行的自动修订次数，从 0 开始
```

推荐伪代码：

```python
content = initial_content
revision_count = 0
replanned = False

while True:
    preflight = quality_gate.preflight(...)
    if preflight.can_skip_expensive_review:
        report = preflight.as_review_report()
    else:
        report = quality_gate.review_full(...)

    persist_attempt(content, report, revision_count)

    if report.decision == PASS:
        commit_ready_atomically(...)
        break

    if report.decision == HUMAN_REQUIRED:
        stop_human_required(...)

    if revision_count >= max_revision_attempts:
        stop_failed_with_checkpoint(...)
        break

    action = issue_policy.resolve(report, replanned=replanned)

    if action == REPLAN:
        plan = regenerate_and_validate_plan(...)
        replanned = True
        content = write_chapter_with_quality_contract(...)
    else:
        content = revise_chapter_with_full_context(...)

    revision_count += 1
```

### 9.2 每轮必须保存

每次审核都必须保存：

- 当前 draft version；
- 当前 review report；
- `review_attempt`；
- `revision_count`；
- 恢复动作 `initial/revise/replan`；
- 本轮输入问题摘要；
- 分数变化；
- issue fingerprint；
- 是否通过预检；
- 是否调用完整 AI 审核。

不能覆盖或删除上一轮草稿。正式正文、人物记忆和时间线仍然只能在最终 PASS 后同事务提交。

### 9.3 无进展检测

实现稳定的 issue fingerprint：

```text
category + severity + normalized message
```

至少处理：

- 修订后正文 hash 与上一版相同：停止继续同类修订；
- 同一组严重问题连续两轮不变且分数提升小于 1：若尚未 replan，则 replan；否则提前 FAILED；
- 修订后出现新的硬阻断：下一轮必须优先修复，不得提交。

## 10. P1：给修订 AI 完整上下文

### 10.1 修改端口

不要继续扩展位置参数。新增 DTO，例如：

```python
class ChapterRevisionContext(StrictModel):
    project_id: str
    chapter_number: int
    target_chars: int
    creative_request: dict[str, Any]
    creative_brief: dict[str, Any]
    chapter_plan: dict[str, Any]
    quality_contract: dict[str, Any]
    current_draft: str
    previous_chapter_excerpt: str
    opening_anchor: dict[str, Any] | None
    character_archives: list[dict[str, Any] | str]
    world_rules: list[str]
    review: ReviewReport
    revision_number: int
```

将 LLM 端口改为类似：

```python
def revise_chapter(self, context: ChapterRevisionContext) -> str:
    ...
```

同步修改：

- `novel_agent/ports/llm.py`
- `novel_agent/integrations/llm/deepseek.py`
- `novel_agent/integrations/llm/offline.py`
- `novel_agent/integrations/llm/disabled.py`
- 所有测试 fake gateway

### 10.2 修订提示要求

修订模型必须：

1. 按严重问题优先级处理 `BLOCKER → MAJOR → MINOR`。
2. 对每个严重问题读取 message、evidence、suggestion 和相关分项分数。
3. 保留已经通过的事实、情节和文风，不做无关大改。
4. 保持细纲、人物知识边界、世界规则、开篇锚点和上一章衔接。
5. 输出完整章节，不输出解释、自评、Markdown 或占位符。
6. 字数重新落入目标区间。
7. 使用比首稿更低的温度，优先保证约束修复稳定性。

### 10.3 结构性失败不能只修正文

复用现有 `chapter_planning/rework_policy.py` 的分类知识，但不要让 UI 传入的 mode 覆盖后端判断。

同一次运行中最多自动 replan 一次。新 plan 必须重新执行：

- opening anchor 校验；
- 第一章禁用表达校验；
- plan 持久化；
- 必要研究问题更新；
- 正文重新生成。

## 11. P1：评分结果透明化

### 11.1 后端结构

保留 `ReviewReport` 的向后兼容字段，同时让 `checks` 使用稳定命名空间，例如：

```text
structural.length
structural.constraints
structural.repetition
readability.opening_hook
readability.scene_causality
...
continuity.semantic
prose.template_density
```

新增或派生：

- `blocking_issue_count`；
- `major_issue_count`；
- `minor_issue_count`；
- `lowest_component`；
- `review_attempt`；
- `max_review_attempts`；
- `next_action`。

若不修改数据库 schema，可将这些信息存入 review/run payload 并在 detail reader 中稳定映射。禁止只在前端猜测。

### 11.2 前端展示

修改相关 Vue 组件，使生成中和失败后显示：

```text
第 2/3 次质量检查
当前最低项：场景因果 68
正在根据 2 个严重问题自动修订
```

耗尽后显示：

- 已自动尝试次数；
- 分数变化，例如 `58 → 71 → 79`；
- 仍未解决的阻断问题；
- 系统建议“沿用细纲再写”或“重新规划”；
- 不把“最低组件分”描述为简单平均总分。

所有动态错误摘要继续使用 `role="alert"` / `aria-live`，需要用户处理时移动焦点。

## 12. P2：防卡死的用户兜底

自动闭环不能无限循环，但也不能让没有硬冲突的小说永久无法继续。

### 12.1 服务端 capability

在自动尝试耗尽后，由服务端根据最后一份报告计算：

```text
can_accept_with_warnings =
  正文非空且未截断
  AND 没有 BLOCKER
  AND 没有结构性/连续性 MAJOR
  AND 只剩可读性、篇幅、文风或局部重复问题
```

未知类别保守视为不能接受。前端不得自行计算。

### 12.2 显式接受

若 `can_accept_with_warnings=true`，FAILED 页面可以提供“接受当前版本并继续”操作：

1. 必须弹窗展示未解决问题和影响。
2. 必须二次确认，默认按钮不可误触。
3. 后端重新检查最新 draft hash、chapter version 和 capability。
4. 成功后按正式提交事务更新正文和记忆。
5. review report、run/event 和 chapter version metadata 必须记录 `accepted_with_warnings=true`。
6. 之后仍可在阅读页修订。

建议新增：

```text
POST /api/novels/{id}/chapters/{number}/accept-with-warnings
```

请求至少包含：

```json
{
  "confirm": true,
  "base_version": 1,
  "expected_draft_hash": "..."
}
```

有硬阻断时必须返回 409 和明确错误码，例如 `QUALITY_OVERRIDE_NOT_ALLOWED`。不得让该接口绕过排除项、开篇锚点、人物连续性或世界硬规则。

## 13. P2：FAILED 手工送审边界

现有 `review-submit` 是用户明确提交已经编辑过的草稿，不应在用户不知情时自动重写其文本。

规则：

- 初始自动生成流程：允许自动修订和自动 replan；
- 用户点击“重新送审”：只审核当前用户草稿；
- 若未通过：保持 FAILED、保留用户草稿并返回结构化问题；
- 可另外提供“让 AI 按报告自动修订”按钮，用户点击后再调用修订流程；
- 不得在普通 `review-submit` 内静默覆盖用户编辑内容。

## 14. API 与兼容性

### 14.1 保持兼容

- 已有项目和旧 review report 必须可读。
- 旧 `checks` 键可以读取，但新写入使用命名空间。
- 不要为了本任务自动批量重写旧报告。
- `review-submit` 的 `passed=false` 继续返回 HTTP 200。
- capability 继续以后端为真源；缺失时前端保守禁用。

### 14.2 配置

恢复 `MAX_REVISION_ATTEMPTS` 的真实作用：

- 默认 2；
- 合法范围建议限制为 0～5；
- 非法值启动时给出明确错误，不静默变成无限次；
- 用户指南写清调用次数、成本和失败后的行为。

如果新增其他配置，必须说明默认值、范围、成本影响并更新用户指南；优先少加配置。

## 15. 必须删除或替换的旧逻辑

完成新闭环后，使用 `rg` 清理：

- `range(1)` 一次性质量门；
- `attempt == 0` 立即 FAILED 的旧分支；
- “one-shot gate” 注释；
- `revise_chapter(content, instructions, target_chars)` 旧签名；
- DeepSeek 写作和审稿中重复硬编码的八维列表及阈值；
- 用户指南中“MAX_REVISION_ATTEMPTS 仅兼容保留、不生效”的旧说明；
- 与新状态机重复的 issue 指令拼接代码。

删除前确认没有其他生产引用。不要借机清理无关模块。

## 16. Python 测试矩阵

至少新增或修改以下测试。

### 16.1 质量契约

1. 写作提示包含与审稿器完全相同的八维名称。
2. 写作和审稿读取同一份 75/82 阈值。
3. 第一章契约包含 must_establish 和 forbidden_assumptions。
4. 第二章契约包含上一章衔接要求。
5. DeepSeek 首稿温度为新的稳定值。

### 16.2 预检

1. 去标题和空白后的字符计数正确。
2. 90% 及以上不产生长度问题。
3. 80%～90% 产生 MINOR。
4. 低于 80% 产生 MAJOR。
5. 第一人称正文未出现主角姓名时不会被确定性判为 MAJOR。
6. 明确排除项仍然产生 BLOCKER。
7. 第一章承接前文仍然产生结构性阻断。
8. 空正文和截断仍然阻断。

### 16.3 自动修订

1. 首稿 PASS：不调用 `revise_chapter()`。
2. 首稿失败、第一次修订 PASS：调用一次修订、审核两次、最终 READY。
3. 第二次修订才 PASS：默认配置下审核三次、最终 READY。
4. 两次修订仍失败：最终 FAILED，三版正文和三份报告均可追溯。
5. `MAX_REVISION_ATTEMPTS=0`：只审核首稿，不修订。
6. `HUMAN_REQUIRED`：立即停止，不自动修订。
7. 修订正文 hash 不变：停止无效循环。
8. 同一问题指纹无改善：从 revise 升级为 replan。
9. 结构性失败触发一次 replan，语言问题不触发 replan。
10. replan 后重新校验 opening anchor。
11. 修订过程中不得提交正式人物记忆或时间线。
12. 只有最终 PASS 后才提交 READY 和正式记忆。
13. 修订时收到完整 plan、人物、世界规则、上一章结尾和质量契约。

### 16.4 评分和证据

1. 各组件 checks 使用稳定命名空间。
2. 报告能指出 lowest component。
3. 高分但含真实 BLOCKER 仍不能通过。
4. AI 返回无证据主观 MAJOR 时按策略降级或拒绝作为硬阻断。
5. 低维度分能生成带阈值证据的可执行问题。

### 16.5 接受警告

1. 只有软问题时 capability 为 true。
2. BLOCKER、结构性 MAJOR、未知 MAJOR 时 capability 为 false。
3. 缺少确认、版本冲突、draft hash 冲突被拒绝。
4. 成功接受后正文和记忆同事务提交。
5. 审计数据记录 `accepted_with_warnings=true`。
6. 一个项目的操作不影响其他项目。

## 17. 前端测试和 E2E

### 17.1 Vitest

覆盖：

- 自动修订进度和当前尝试次数；
- 分数轨迹展示；
- 最低组件与阻断原因区分；
- “接受当前版本并继续”只在服务端 capability 为 true 时出现；
- 确认弹窗默认安全状态；
- capability 缺失时不发送接受或 AI 请求；
- 错误摘要可聚焦。

### 17.2 Playwright

至少新增以下真实流程：

1. 首稿审核失败，AI 自动修订后通过，用户只点击一次“生成下一章”。
2. 第一次修订失败、第二次通过，最终生成 READY。
3. 自动修订耗尽后才出现 FAILED。
4. 自动修订过程中页面能看到尝试次数或进度事件。
5. 结构性失败走 replan，不复用错误细纲。
6. FAILED 软问题可以显式接受并继续生成下一章。
7. FAILED 硬阻断没有接受入口，直接请求接口也返回 409。
8. 页面刷新后失败报告、分数轨迹和 capability 保持一致。

E2E 必须断言请求次数和最终数据库/API 状态，不能只检查按钮文字。

## 18. 文档更新

### 18.1 `docs/USER_GUIDE.md`

必须用非开发者语言说明：

- 首稿会按同一套质量标准生成和审核；
- 未通过时会自动修订多少次；
- 什么情况会重新规划；
- 什么情况才进入 FAILED；
- `MAX_REVISION_ATTEMPTS` 的真实含义和成本；
- 为什么一次生成可能调用多次模型；
- 如何查看分数轨迹和剩余问题；
- 何时可以“接受当前版本并继续”；
- 哪些硬问题不能绕过；
- 手工重新送审不会静默改写用户正文。

删除当前“质量门只执行一轮、MAX_REVISION_ATTEMPTS 不生效”的说明。

### 18.2 `docs/API.md`

更新：

- 质量报告扩展字段；
- 自动修订次数和状态事件；
- accept-with-warnings endpoint；
- capability 真源；
- 409 错误码；
- `review-submit` 不自动改写用户草稿的边界。

### 18.3 README

确认用户指南链接仍有效即可；除非启动命令或入口变化，不要无关改写 README。

## 19. 验收命令

后端：

```powershell
python -m unittest discover -s tests -v
```

前端：

```powershell
cd apps/web
npm run lint
npm run type-check
npm run test
npm run build
npm run test:e2e
npm run test:e2e
```

格式检查：

```powershell
cd ../..
git diff --check
```

两轮 E2E 都必须通过，以证明测试数据库隔离、端口清理和重试计数没有残留状态。

## 20. 完成定义

只有同时满足以下条件才能宣称完成：

- [ ] 生成器和审稿器读取同一份质量契约。
- [ ] 八维名称、单项阈值和平均阈值不再重复硬编码。
- [ ] 首稿提示明确包含实际评分标准和硬规则。
- [ ] 确定性预检先于昂贵的 AI 审稿。
- [ ] 字数和主角检查不再产生明显误判。
- [ ] `MAX_REVISION_ATTEMPTS` 实际控制自动修订次数。
- [ ] `range(1)` 和第一次失败立即返回的旧逻辑已删除。
- [ ] 审核失败会把完整问题、证据和分数交给修订 AI。
- [ ] 修订 AI 收到完整章节上下文。
- [ ] 每次修订后都会重新执行同一完整质量门。
- [ ] 结构性问题自动 replan，正文问题复用 plan 修订。
- [ ] 自动循环有次数和无进展保护。
- [ ] 所有中间草稿与报告可追溯。
- [ ] 未 PASS 前不提交正式记忆。
- [ ] 耗尽后才进入 FAILED。
- [ ] 软问题可显式接受，硬阻断不可绕过。
- [ ] `review-submit` 不静默改写用户草稿。
- [ ] 前端展示尝试次数、分数轨迹和真实阻断原因。
- [ ] API 文档和中文用户指南同步。
- [ ] Python 全量测试通过。
- [ ] lint、type-check、Vitest、build 通过。
- [ ] Playwright 连续两轮通过。
- [ ] `git diff --check` 无错误。
- [ ] 没有读写用户正式数据库。
- [ ] 没有回滚或清理既有工作区修改。

## 21. 可直接复制给 Cursor 的提示词

```text
请在当前仓库根目录中，严格按照
docs/CHAPTER_QUALITY_ALIGNMENT_AND_AUTO_REVISION_CURSOR_EXECUTION.md
执行“章节质量标准对齐与自动修订闭环”任务。

开始前必须先阅读：
1. AGENTS.md
2. docs/CHAPTER_QUALITY_ALIGNMENT_AND_AUTO_REVISION_CURSOR_EXECUTION.md
3. docs/FIRST_CHAPTER_RECOVERY_REMEDIATION_CURSOR_EXECUTION.md
4. docs/USER_GUIDE.md
5. 当前 git status 和 git diff

本任务的核心不是降低分数或强行 PASS，而是：
- 让正文生成器和审稿器使用同一份唯一质量契约；
- 修复 write_chapter 与 review_readability 的八维标准和阈值不对齐；
- 恢复 MAX_REVISION_ATTEMPTS 的真实作用；
- 删除 workflow.py 中 range(1) 和第一次失败立即返回导致 revise_chapter 不可达的逻辑；
- 首稿失败后，把完整问题、证据、建议和分项分数交给 AI 自动修订；
- 每次修订后重新执行同一完整质量门；
- 结构性问题重新规划，语言/篇幅/可读性问题复用细纲修订；
- 限制尝试次数并检测无进展，禁止无限 Token 循环；
- 只有最终 PASS 才提交 READY 和正式记忆；
- 自动尝试耗尽后才进入 FAILED；
- 仅对无硬阻断的软质量问题提供需用户确认的“接受当前版本并继续”；
- review-submit 不得静默覆盖用户手工编辑的正文。

必须模块化实现，不要继续把所有逻辑堆进 workflow.py、deepseek.py 或单个 Vue 页面。
必须保留已有 opening anchor、FAILED 编辑/重新送审、opening repair、rollback、capabilities 和 Vue 3 功能。

安全要求：
- 不得修改、复制覆盖或迁移用户正式数据库；
- 测试只能使用 tempfile、fixture 和 Playwright 临时数据库；
- 禁止 git reset --hard、git checkout -- .、git clean -fd；
- 不得回滚或清理与本任务无关的既有修改；
- 删除旧代码前先用 rg 证明没有生产引用；
- 不得通过降低 QUALITY_PASS_SCORE、忽略 BLOCKER、把 FAILED 直接改 READY 或前端假成功来通过测试。

实现过程中同步更新 docs/API.md 和 docs/USER_GUIDE.md。用户指南必须说明自动修订次数、模型调用成本、FAILED 条件、软问题显式接受和不可绕过的硬阻断。README 的用户指南链接必须保持有效。

完成后依次运行并报告真实结果：
- python -m unittest discover -s tests -v
- cd apps/web
- npm run lint
- npm run type-check
- npm run test
- npm run build
- npm run test:e2e
- npm run test:e2e
- cd ../..
- git diff --check

不要只报告“已完成”。最终报告必须列出：
1. 实际修改文件；
2. 质量契约唯一来源；
3. 自动修订和 replan 的状态机；
4. MAX_REVISION_ATTEMPTS 的实际语义；
5. 中间草稿和报告如何保存；
6. accept-with-warnings 的服务端限制；
7. API 和用户指南更新；
8. 每组测试的数量和结果；
9. 是否确认未触碰用户正式数据库；
10. 尚未解决的风险（如有）。
```
