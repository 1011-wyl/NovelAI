# 给 Cursor 的前端剩余问题修复提示词

下面内容可以完整复制到 Cursor：

```text
请继续修复当前 NovelAI 项目的前端问题。不要重新从零实现，也不要覆盖或回滚当前工作区中已经存在的修改。

项目目录：
D:\实习日报\NovelAI\NovelAI

开始工作前，请完整阅读并严格执行：

1. 根目录的 AGENTS.md
2. docs/FRONTEND_REMAINING_FIXES_CURSOR_EXECUTION.md
3. docs/USER_GUIDE.md
4. 当前 README.md

其中，docs/FRONTEND_REMAINING_FIXES_CURSOR_EXECUTION.md 是本次任务的详细执行标准和验收依据。请按文档中的阶段顺序执行全部任务，不要只阅读后给建议，也不要只生成新的计划文档。你需要直接检查、修改、测试当前代码，直到满足文档定义的完成条件。

一、开工要求

1. 先运行并检查：
   - git status --short
   - git diff --stat
   - git diff -- apps/web docs README.md
2. 当前工作区包含用户和上一轮修复留下的未提交改动。必须在这些改动上继续工作，禁止使用 git reset --hard、git checkout -- .、git clean -fd，禁止回滚、覆盖、删除任何无关修改。
3. 修改文件前先阅读当前文件内容，不得根据旧版本或缓存覆盖现有实现。
4. 先确认任务书第 3 节列出的“已完成基线”仍然存在。后续重构必须保留这些行为，并将它们补入自动化回归测试。
5. 如果发现任务书与当前代码存在差异，以当前代码和用户已经完成的行为为事实基础；需要调整实现路径时可以调整，但不能降低任务书的验收标准，并要在最终报告中说明差异和原因。

二、本次必须完成的核心任务

请完整完成，不要任选一部分：

1. 将仪表盘彻底迁移为 Vue 3 原生实现：
   - Vue 管理页签、筛选、加载、错误、空态、分页、排序和所有用户交互。
   - API、类型、store/composable、组件和图表渲染职责分离。
   - 图表渲染器只能作为受控适配器，不能继续负责整个页面 DOM、筛选器、表格或事件。
   - 禁止用 v-html、整页 innerHTML 或在 Vue 中继续 mount 旧页面来冒充迁移完成。
   - 功能与当前仪表盘保持对等。
   - 迁移和测试完成后，删除所有未引用的旧 analytics controller/template/view 文件和死入口。

2. 补齐 ESLint：
   - 安装与现有 Vue 3、TypeScript 和 Vite 版本兼容的依赖。
   - 建立可执行的 flat config。
   - 正确忽略构建、覆盖率和 Playwright 生成目录。
   - 修复真实 lint 问题，禁止通过全局关闭规则、大量 eslint-disable、@ts-ignore 或 any 让 lint 假通过。
   - npm run lint 必须真实成功。

3. 建立 Playwright E2E：
   - 安装并配置 @playwright/test。
   - 使用独立测试数据库或临时数据目录，绝对禁止读取、修改或清理用户真实数据库。
   - 覆盖任务书中列出的书架、三步创建、方案确认门控、URL 守卫、正式工作台、侧栏持久化、卡片菜单、重命名、删除、无效 projectId、阅读页固定布局、textarea resize、弹窗焦点以及多视口无横向滚动等用例。
   - 不要用大量固定 waitForTimeout 掩盖竞态，要等待真实可观察状态。
   - 所有测试必须可独立、可重复运行；E2E 最终连续运行两次。

4. 补齐 Vue 组件测试：
   - BaseDialog
   - AppSidebar
   - useActionMenu 或真实宿主组件
   - WorkbenchPage
   - ReaderPage
   - 仪表盘的 store/composable 和关键组件
   - 必须覆盖方案门控、加载、错误、空态、请求失败后保留输入、键盘菜单、焦点陷阱、焦点恢复、侧栏状态持久化以及 reader 无拖拽分隔线。

5. 修复 Python 测试依赖被忽略的 dist 的问题：
   - 新克隆或无旧构建产物的环境必须有稳定、明确的验证顺序。
   - 优先保证先 npm ci 和 npm run build，再运行依赖 SPA 资源的 Python 测试。
   - 不得依赖开发者机器碰巧残留的 apps/web/dist。
   - README 和用户指南中的命令、路径必须与实际实现一致。

6. 完成真实浏览器验收：
   - 1440×900
   - 1024×768
   - 768×1024
   - 390×844
   - 检查书架展开/收起、创建步骤 1/2/3、未确认方案、已确认工作台、阅读页、长期记忆、仪表盘、设置、弹窗和菜单状态。
   - 每个适用页面验证 scrollWidth <= innerWidth、固定侧栏不随正文移动、无遮挡、无双滚动、textarea 不可缩放、无布局拖拽柄、键盘焦点可见、弹窗和菜单焦点行为正确、关键触控目标至少 44×44px。
   - 保存有意义名称的验收截图，并在最终报告中给出绝对路径。

7. 完成旧代码和文档收尾：
   - 清理 analytics 迁移后的旧 DOM 页面代码和未引用文件。
   - 处理 docs/_baseline_workbench_regression.md 的空占位问题：填写真实回归记录或删除并移除引用。
   - 更新 docs/_vue3_migration_stage12_report.md，内容必须与真实完成情况一致。
   - 检查并处理 /favicon.ico 404，不能通过吞掉所有静态资源 404 来掩盖。
   - 按 AGENTS.md 规定：凡用户可见功能、UI 操作、流程状态、配置、接口、存储路径、备份迁移、命令或排错步骤发生变化，都必须在同一修改中同步 docs/USER_GUIDE.md；README 中的用户指南链接必须保持有效。

三、必须保留的上一轮成果

以下行为禁止回退：

1. 桌面侧栏固定，正文滚动时不移动。
2. 侧栏展开 240px、收起 76px，主内容正确让位。
3. 桌面收起状态持久化，移动端仍是独立抽屉。
4. 所有 textarea 的计算样式为 resize: none。
5. 阅读页是固定响应式三栏，没有 workspace-resizer 或其他拖拽分隔线。
6. 创建小说固定要求确认方案。
7. 未确认时只显示方案审阅相关内容，隐藏正式生产指标和生产流程。
8. 未确认项目不能进入 reader 和 memory，直接 URL 也必须被守卫拦截。
9. 确认后立即解锁正式工作台、阅读和长期记忆，无需刷新。
10. 无效 projectId 必须进入 ProjectMissing，包括空书架情况。
11. 工作台章节入口保持真实 RouterLink。
12. BaseDialog 保持 Escape、焦点陷阱、初始焦点和关闭后焦点恢复。
13. 小说卡片菜单保持点击外部、Escape、方向键、Home、End 和焦点恢复。
14. 移动端创建页顺序正确，手机书架工具栏不产生横向滚动。

四、代码组织要求

1. 前端继续使用 Vue 3 和 TypeScript。
2. 按功能模块组织文件，页面、组件、API、类型、store/composable、测试各自职责清晰。
3. 不要把所有逻辑重新堆入一个超大 .vue 文件。
4. 也不要为了形式机械拆分大量只有几行的文件。
5. 网络请求集中在 API 边界，页面组件不要散落拼接 URL。
6. 不允许新增旧式全局变量、内联 onclick 或手动控制整页 DOM。
7. 修改应聚焦本任务，不要进行全仓库无关格式化。

五、执行和验证方式

不要一次性修改完所有内容后才运行测试。每个阶段完成后先运行相关 lint、类型检查和测试，发现回归立即修复。

最终必须真实执行：

cd apps/web
npm ci
npm run lint
npm run type-check
npm run test
npm run build
npm run test:e2e
npm run test:e2e

cd ../..
python -m unittest discover -s tests -v
git diff --check

然后执行任务书中规定的 rg 静态清理检查，逐条检查仍存在的 innerHTML、document.querySelector、addEventListener、createAnalyticsView、workspace-resizer 和旧 analytics 文件引用。每一处保留的底层 DOM API 都必须在最终报告中给出文件位置和必要性说明。

如果命令失败：

1. 阅读完整错误输出并修复根因。
2. 不得删除失败测试或降低断言来换取通过。
3. 不得隐藏错误、跳过核心测试或伪造结果。
4. 如果确实受外部环境阻塞，先完成所有不受阻塞的工作，再在最终报告中提供具体命令、完整原因、已尝试方案和剩余动作，不能只写“环境问题”。

六、最终回复要求

完成后严格使用 docs/FRONTEND_REMAINING_FIXES_CURSOR_EXECUTION.md 第 15 节的模板回报，并至少包含：

1. 实际完成和未完成内容。
2. 所有实际修改、新增、删除的文件。
3. analytics Vue 迁移后的模块结构和旧代码删除结果。
4. 每一条验证命令的真实退出结果。
5. Vitest 测试文件数、用例数和通过/失败数。
6. Playwright 测试文件数、用例数、浏览器项目数，以及连续两次运行结果。
7. Python 测试用例数和结果。
8. E2E 独立数据库或数据目录及隔离方式。
9. 四类视口的验收结论。
10. 截图和 Playwright 报告的绝对路径。
11. docs/USER_GUIDE.md、README、回归记录和迁移报告的同步情况。
12. 所有尚存风险或未完成项。

不允许用“功能上应该没问题”“理论上已经完成”“页面可以打开”代替测试结果。

现在请直接开始：先检查当前工作区和相关文件，再按任务书逐阶段实施、测试、修复，直到达到最终完成定义。不要只给我计划。
```

