# HTTP API

`GET /api/novels/{id}/chapters/{number}/versions` returns immutable chapter snapshots (draft and final), newest first. Failed retries keep these snapshots so earlier drafts can be reviewed.

服务默认监听 `http://127.0.0.1:8000`。

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/health` | 运行模式、数据库、外部 API 与写作技能就绪状态 |
| GET | `/api/novels/{id}/research` | 已保存的网页研究来源与核验状态 |
| GET | `/api/novels/{id}/brief-versions` | 查看并对比创作方案历史版本 |
| POST | `/api/novels/{id}/semantic-search` | 在章节摘要和研究资料中执行语义检索；请求体包含 `query` 与可选 `limit` |
| PUT | `/api/novels/{id}/brief` | 在确认前手工修改完整创作方案并保存新版本 |
| POST | `/api/novels/{id}/brief-regenerate` | 根据 `feedback` 和 `sections` 整体或局部重做方案 |
| POST | `/api/novels/{id}/brief-restore` | 恢复指定历史版本，并把恢复结果保存为新版本 |
| DELETE | `/api/novels/{id}` | 删除项目；未确认空草稿可使用空请求体，其他作品必须传入 `confirmation_title`，且必须与当前书名完全一致 |
| GET | `/api/tags` | 男频/女频频道目录，以及各频道独立的题材、体验、元素、主角与感情线标签 |
| POST | `/api/novels` | 创建项目与创作方案 |
| GET | `/api/novels` | 书架轻量列表（`ProjectSummary`）；临时兼容可用 `?detail=full` 返回完整 `ProjectRecord`（已废弃，请勿新用） |
| PUT | `/api/novels/{id}/metadata` | 修改书名：同步 `projects.title` 与 `brief.selected_title`，追加 `metadata_edit` 方案版本；不改变状态、确认标记与章节 |
| GET | `/api/novels/{id}` | 项目、章节、人物、世界、时间线与已加载 Skill 聚合详情 |
| POST | `/api/novels/{id}/confirm` | 确认创作方案 |
| POST | `/api/novels/{id}/pause` | 暂停自动写作 |
| POST | `/api/novels/{id}/resume` | 恢复自动写作 |
| POST | `/api/novels/{id}/runs` | 运行 1 到 10 个连续章节工作流 |
| POST | `/api/novels/{id}/chapters/{number}/rework` | 打回指定章节及其后续章节；请求体可包含最多 2000 字的 `feedback`，以及 `mode`：`auto` / `reuse_plan` / `replan`。服务端按最近审校报告分类；若分类为必须重新规划，请求 `reuse_plan` 会返回 409/`REWORK_MODE_NOT_ALLOWED` |
| GET | `/api/novels/{id}/chapters/{number}/workspace` | 阅读修订工作台聚合：正式章、工作草稿、版本、会话、下游重置范围与 `capabilities`（后端真源；含 `accept_with_warnings`；缺省时客户端必须全部禁用写操作）。`FAILED` 详情中的 `chapter_failures` 另含 `score_trace`、`lowest_component`、`review_attempt`、`revision_count` 等扩展字段；字数或生成预检未通过时 `preflight_only=true`且 `score=null`，表示尚未执行质量审核 |
| PUT | `/api/novels/{id}/chapters/{number}/edit-draft` | 保存工作草稿（不改正式章节）；支持乐观锁 `expected_draft_hash`；`FAILED` 章节也可保存 |
| DELETE | `/api/novels/{id}/chapters/{number}/edit-draft` | 放弃工作草稿 |
| POST | `/api/novels/{id}/chapters/{number}/revisions` | 将 `READY` 章节的工作草稿提交为正式修订；`FAILED` 章节调用此接口会返回 409/`FAILED_DRAFT_REVIEW_REQUIRED` |
| POST | `/api/novels/{id}/chapters/{number}/review-submit` | 将 `FAILED` 草稿送入与生产工作流相同的完整质量门；只审核当前用户草稿，不会静默自动改写正文。唯一通过条件是加权综合 `quality_score` **严格大于 60**（`60.0` 本身不通过）。单项分、平均分和 `MAJOR`/`BLOCKER` 只用于解释与修订优先级，不再单独否决。审校执行成功一律 HTTP 200：`passed=true` 时章节变为 `READY`，`passed=false` 时保持 `FAILED` 并保留草稿与 `review`。请求冲突、缺少草稿或当前状态不允许送审才返回 4xx |
| POST | `/api/novels/{id}/chapters/{number}/accept-with-warnings` | 不能用该接口绕过 `quality_score > 60`。仅当服务端已判定分数通过且无空稿/截断/排除项等技术失败时才可能允许显式确认。不满足时返回 409/`QUALITY_OVERRIDE_NOT_ALLOWED`。 |
| GET | `/api/novels/{id}/opening-repair-preview` | 预览开篇数据修复资格、影响范围与开篇锚点；不修改数据库 |
| POST | `/api/novels/{id}/opening-repair` | 确认后创建 schema v6 快照、清理错误第一章研究资料并修复开篇人物初态；需要 `confirm=true` 与 `expected_project_updated_at` |
| GET | `/api/novels/{id}/opening-repair-snapshots/latest` | 查询当前项目最新可回退的 opening repair 快照（不含 payload）。无快照时 `{ "snapshot": null }`。`rollback_allowed` 由服务端根据是否已有正式章节计算 |
| POST | `/api/novels/{id}/opening-repair/{snapshot_id}/rollback` | 用 `UPDATE` 恢复项目行并回退本次开篇修复。成功：`rolled_back=true` 且快照仍在、状态为 `rolled_back`。已回退过或已有正式章节：409/`OPENING_REPAIR_ROLLBACK_UNSAFE` |
| POST | `/api/novels/{id}/chapters/{number}/versions/{version}/restore` | 将历史版本恢复为工作草稿 |
| GET/POST | `/api/novels/{id}/chapters/{number}/assistant/sessions` | 列出 / 创建 AI 修订会话 |
| GET/POST | `/api/assistant/sessions/{session_id}/messages` | 列出 / 发送助手消息（编辑模式可产生待批准修改） |
| GET | `/api/assistant/sessions/{session_id}/changes` | 会话修改集列表 |
| POST | `/api/assistant/sessions/{session_id}/rollback` | 回滚到指定用户消息 |
| DELETE | `/api/assistant/sessions/{session_id}` | 软删除会话 |
| POST | `/api/assistant/changes/{change_id}/approve` | 批准修改写入工作草稿 |
| POST | `/api/assistant/changes/{change_id}/reject` | 拒绝修改 |
| GET | `/api/novels/{id}/chapters` | 章节列表与正文 |
| GET | `/api/novels/{id}/characters` | 人物权威状态 |
| POST | `/api/novels/{id}/characters/rebuild` | 扫描全部 READY 章节，重建重要人物档案并清理非重要人物；在线模式会调用大模型 |
| GET | `/api/novels/{id}/world` | 世界硬规则与时间线 |
| GET | `/api/runs/{id}/events` | SSE 格式的工作流节点事件 |
| GET/PUT | `/api/settings` | API、写作技能就绪状态与非敏感本地偏好 |
| GET/PUT/DELETE | `/api/settings/llm` | 大模型配置安全视图；PUT 可保存并启用；DELETE 清除页面配置（环境变量仍可用） |
| POST | `/api/settings/llm/test` | 使用表单或已保存密钥做低成本连通性测试 |
| GET | `/api/usage` | 当前进程的模型累计用量与最近调用 |
| GET | `/api/token/statistics?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | 兼容接口：查询本地持久化的每日 Token 统计 |
| GET | `/api/dashboard/writing` | 写作仪表盘：按项目/来源/时间范围与时区聚合字数时序 |
| GET | `/api/dashboard/llm-api/stats` | LLM 统计：调用次数、Token、延迟与模型/项目分布 |
| GET | `/api/dashboard/llm-api/records` | LLM 调用记录：筛选、搜索、排序与分页 |
| GET | `/api/publishing` | Mock 发布状态与安全提示 |

### 仪表盘接口说明

- `GET /api/dashboard/writing` 查询参数：`project_id`、`source`（`user|agent|import`）、`start_at`、`end_at`、`timezone`（IANA 名称，如 `Asia/Shanghai`）。响应含 `summary.active_days`、`summary.creative_chapters` 与按日的 `time_series`。
- `GET /api/dashboard/llm-api/stats` 可选筛选：`project_id`、`model_provider`、`model_id`、`category`、`operation`、`status`、`start_at`、`end_at`。响应含 `summary`、`model_time_series`、`by_model`、`by_project`、`options`。无首 Token 样本时 `avg_first_token_ms` 为 `null`。
- `GET /api/dashboard/llm-api/records` 在 stats 相同筛选之外支持 `search`、`page`（默认 1）、`page_size`（5–100，默认 20）、`sort_by`、`sort_order`。排序白名单：`created_at`、`tokens_input`、`tokens_output`、`tokens_total`、`latency_ms`、`first_token_ms`、`retry_count`。非法参数返回 400。
- 上述接口不返回 API Key、完整提示词或完整模型输出。旧的 `/api/token/statistics` 与 `/api/usage` 继续可用。
- `GET /api/settings/llm` 只返回供应商、地址、模型、是否已有密钥和可选尾号掩码，**永不返回完整 API Key**。`PUT` 仅在新增或替换时提交 `api_key`；`keep_existing_api_key=true` 且密钥框为空时保留旧密钥。`PUT` 且 `enabled=false` 可在没有新密钥时写入停用状态，并覆盖环境变量。页面配置优先于环境变量；清除后若环境变量仍有效则 `source=environment`。已停用的页面配置不会回退到环境变量。

## 创建示例

```json
{
  "genre": "末世",
  "experiences": ["爽文", "热血"],
  "elements": ["囤货", "经营建设"],
  "protagonist_tags": ["重生", "普通人成长"],
  "idea": "仓储管理员依靠有限经验建立社区，没有无限空间。",
  "must_have": ["资源可追踪"],
  "nice_to_have": ["群像"],
  "exclude": ["过度血腥"],
  "chapter_target_chars": 2200,
  "daily_chapters": 2,
  "reserve_target": 5,
  "require_plan_confirmation": true
}
```

冲突标签返回 HTTP 409；非法结构返回 HTTP 422；尚未确认、已暂停或需人工处理的项目运行工作流时返回 HTTP 409。

删除正式作品的请求示例：

```json
{
  "confirmation_title": "当前完整书名"
}
```

浏览器跨域响应只允许与服务地址相同的来源。服务默认没有公网身份认证，不应直接监听公网地址。

`/api/health` 的 `apis.story_skills`、`apis.oh_story`，以及 `/api/settings` 的 `runtime.story_skills`、`runtime.oh_story` 会返回对应技能的固定来源、提交版本、已加载 Skill 名称、题材卡数量与启用状态。项目详情的 `skills` 会返回 `story_skills` 和 `oh_story`，当前项目匹配到的题材卡位于 `skills.oh_story.active_genre_card`。这些信息不包含 API Key 或完整正文。

章节规划数据除原有的目标、阻力、转折和钩子外，还包含全书阶段、剧情单元、读者目标情绪、本章爽点、新期待、主角目标和关键选择、多条剧情线推进、人物关系变化、信息差与场景情绪节拍。旧项目缺少这些字段时，运行时会根据现有方案补齐默认值。
