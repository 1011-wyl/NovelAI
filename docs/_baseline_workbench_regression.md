# 阶段 A 工作台回归表（基线冻结）

> 记录于 2026-10-02。原始基线为 `Ran 180 tests ... OK`（见 `_baseline_test_results.txt`）；Vue SPA 迁移删除旧静态资源断言并改用新的 SPA 构建测试后，当前完整 Python 套件为 177 项。
> 离线模式 + 临时数据库验证；不调用在线模型。

## 导航基线（旧）

| 顺序 | view | 文案 |
|---|---|---|
| 1 | dashboard | 创作控制台 |
| 2 | create | 创建小说 |
| 3 | reader | 作品阅读 |
| 4 | memory | 长期记忆 |
| 5 | analytics | 仪表盘 |
| 6 | settings | 系统设置 |

默认入口：`dashboard`。最近项目键：`localStorage.novelAgentProject`。

## 工作台动作

| # | UI | 前置 | API | 期望 |
|---|-----|------|-----|------|
| 1 | 创建小说提交 | 表单合法 | POST `/api/novels` | 切 dashboard，选中新项目 |
| 2 | 确认创作方案 | 未 confirmed | POST `.../confirm` | generate 可点 |
| 3 | 修改方案→保存 | 可编辑草稿 | PUT `.../brief` | 新版本，刷新 |
| 4 | 重新生成 | 可编辑草稿 | POST `.../brief-regenerate` 空 sections | 新版本 |
| 5 | 按意见生成 | feedback 或勾选 sections | POST `.../brief-regenerate` | 新版本 |
| 6 | 恢复左侧版本 | 有版本列表 | POST `.../brief-restore` | 新当前版本 |
| 7 | 生成下一章 | ACTIVE+confirmed | POST `.../runs` `{count:1}` | pipeline + refresh |
| 8 | 暂停 / 继续 | confirmed | POST pause/resume | 状态切换 |
| 9 | 修复并恢复 | HUMAN_REQUIRED | POST recover | 可再生成 |
| 10 | 删除草稿/作品 | 有项目 | DELETE + title 确认 | 清空选择 |
| 11 | 章节打回重做 | 非 PLANNED | POST `.../chapters/{n}/rework` | 后续章重置 |
| 12 | 章节行打开阅读 | 有章节 | — | reader + openChapter |
| 13 | 重建人物档案 | 已选项目 | POST `.../characters/rebuild` | memory 刷新 |
| 14 | 刷新 | — | health + novels + detail | 全壳更新 |
| 15 | 设置保存 | settings 页 | PUT `/api/settings` | 偏好持久化 |

## 创建字段（NovelCreateRequest）

`audience_channel`, `genre`, `preferred_title`, `experiences`, `elements`, `protagonist_tags`, `romance`, `idea`, `must_have`, `nice_to_have`, `exclude`, `chapter_target_chars`, `daily_chapters`, `reserve_target`, `require_plan_confirmation`

## 状态文案

| 状态 | 文案 |
|---|---|
| DRAFT | 草稿 |
| ACTIVE | 创作中 |
| PAUSED | 已暂停 |
| HUMAN_REQUIRED | 需要处理 |
| ARCHIVED | 已归档 |

## 截图说明

多视口验收截图（2026-10-03）见：

`D:\实习日报\NovelAI\NovelAI\artifacts\frontend-regression\e2e-run\`

功能回归以本表 + Vitest / Playwright / Python 自动化测试为准。侧栏文案已更新为「我的小说 / 创作工作台 / 作品阅读 / 长期记忆 / 仪表盘 / 系统设置」。
