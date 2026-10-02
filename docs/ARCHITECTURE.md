# 架构与状态边界

## 运行链路

```mermaid
flowchart TD
  UI[自主作者控制台] --> API[HTTP API / SSE]
  API --> CTX[AppContext]
  CTX --> PSD[ProjectService / StoryDesignService]
  CTX --> APP[NovelAgentService]
  PSD --> STORE[ProjectsStore / BriefsStore / ProjectSetupStore]
  APP --> REQ[需求冲突检查]
  APP --> WF[单章工作流]
  WF --> LLM[LLMGateway]
  WF --> SEARCH[SearchAdapter]
  WF --> REVIEW[确定性审核套件]
  WF --> SKILL[StorySkillsRuntime]
  SKILL --> VENDOR[固定 revision-continuity 规则]
  SKILL --> LLM
  SKILL --> REVIEW
  WF --> WRITING[OhStoryWritingRuntime]
  WRITING --> OHVENDOR[固定 story-long-write / story-deslop / 题材卡]
  WRITING --> LLM
  WRITING --> REVIEW
  WF --> TX[MemoryCommit 原子事务]
  TX --> DB[(SQLite 权威数据)]
  STORE --> DB
  APP --> SCHED[LocalScheduler]
  APP --> PUB[PublisherAdapter]
  LLM --> OFFLINE[OfflineLLMGateway]
  PUB --> MOCK[MockPublisher]
```

真实模型、搜索、Temporal、PostgreSQL/pgvector、Redis、MinIO 和发布平台都位于可替换边界之后。业务服务不直接引用供应商 SDK。

项目生命周期与创作方案已拆为独立 Feature：HTTP 路由只调用 `ProjectService` / `StoryDesignService`，不再在 Handler 内直接访问 Repository。`NovelAgentService` 与 `SQLiteRepository` 对相关方法仅作迁移期 Facade 委托。

## 当前模块边界（Projects / Story Design）

```text
novel_agent/
  features/
    projects/           # 列表、详情聚合、确认/暂停/继续/删除
    story_design/       # 创建方案、编辑、重生成、版本恢复、标签与需求校验
  infrastructure/persistence/
    projects_store.py
    briefs_store.py
    project_setup_store.py   # 跨表创建 / save_draft_brief 事务
  interfaces/http/routes/
    projects.py
    story_design.py
  models.py / requirements.py / tags.py   # 兼容 re-export
  repository.py / service.py              # 兼容 Facade + 未迁领域

apps/web/
  js/core/api-client.js
  js/features/projects/          # 唯一 selectedId/detail 状态源
  js/features/novel-create/
  js/features/story-brief/
  js/features/project-dashboard/
  styles/features/{novel-create,story-brief,project-dashboard}.css
```

依赖方向：Routes → Feature Services → Ports → Stores → DatabaseSessionProvider。前端 Feature 通过注入的 `api` 客户端访问 HTTP，不直连 SQLite。

尚未迁出、仍由 `NovelAgentService` / `app.js` 协调的能力：章节生成与工作流、Memory、Reader/Revision、Settings；Analytics 已独立。

## 单章状态机

```mermaid
stateDiagram-v2
  [*] --> PLANNED
  PLANNED --> RESEARCHING: 需要现实知识
  PLANNED --> WRITING: 无需调研
  RESEARCHING --> WRITING
  WRITING --> REVIEWING
  REVIEWING --> READY: PASS
  REVIEWING --> REVISING: REVISE
  REVISING --> REVIEWING
  REVIEWING --> FAILED: 重试超限 / 人工处理
  READY --> SCHEDULED: 未来发布队列
  SCHEDULED --> PUBLISHED: 发布闸门通过
```

当前版本实现到 `READY`。`SCHEDULED` 与 `PUBLISHED` 只保留状态和适配器边界，绝不会把刚生成的章节当作已发布内容。

## 不变量

1. 一个章节对应一个稳定 `chapter_id` 和独立 `run_id`。
2. 草稿版本可以追加，不能覆盖历史版本。
3. 只有审核通过后才执行 `commit_ready_chapter`。
4. 正文正式版本、项目进度、人物状态、时间线和审核报告在同一 SQLite 事务内提交。
5. 失败工作流保存最后节点与错误分类，不更新正式记忆。
6. `READY`、`SCHEDULED`、`PUBLISHED` 严格分离。
7. 外部 API 默认关闭；真实发布适配器默认不可实例化。
8. Story Skills 只提供固定审校规则与确定性契约；oh-story 只提供情绪规划、题材正文提示和去 AI 味规则。
9. 两套技能均固定到已审查的上游提交；oh-story 的 Hooks、自定义 Agent 和脚本不会被执行。
10. SQLite 仍是唯一权威故事存储，第三方 Node CLI 不自动操作正式数据。
11. 创建项目与保存创作方案各自保持单事务跨表写入（projects + brief_versions + characters + world_facts）。
12. 项目/方案公开模型在 `features/*` 只有一份定义；`novel_agent.models` / `requirements` / `tags` 仅 re-export。

## 演进路径

- 下一模块：Memory / Research / Semantic（总拆分路线阶段 5）。
- 将 `NovelAgentHandler` 替换为 FastAPI 路由，保留 `NovelAgentService`。
- 将 `ChapterWorkflow` 节点映射到 LangGraph，保留节点输入输出模型和事务提交点。
- 将 `SQLiteRepository` 替换为 SQLAlchemy/PostgreSQL 仓库，数据库变更交给 Alembic。
- 将 `LocalScheduler` 替换为 Temporal Workflow/Worker，保留 `fill_reserve` 的业务语义。
- 最近摘要和研究资料可增加 pgvector 派生索引；人物当前状态与世界硬规则仍以关系库为权威。
