# 前端剩余问题修复：Cursor 可执行任务书

> 适用项目：`NovelAI`
>
> 执行对象：Cursor
>
> 文档目标：在不回退上一轮已完成修复的前提下，完成仪表盘 Vue 3 原生化、代码质量工具链、自动化测试、跨视口验收、旧代码清理和文档收尾。

## 1. 执行原则与最终完成定义

本任务不是重新设计产品，也不是推翻现有实现。Cursor 必须先检查当前工作区和现有改动，在保留用户已有代码、上一轮修复以及未提交修改的基础上继续工作。

本阶段完成的判定条件如下，缺一不可：

1. 仪表盘不再以旧脚本挂载整页 DOM，而是由 Vue 3 组件、store/composable 和 API 模块管理页面状态、交互和生命周期。
2. `npm run lint`、`npm run type-check`、`npm run test`、`npm run build`、`npm run test:e2e` 均真实通过。
3. Python 测试不再依赖开发者机器中碰巧残留的、被 Git 忽略的 `apps/web/dist`。
4. 核心流程拥有可重复执行的 Playwright E2E，并使用独立测试数据，不能修改用户真实数据库。
5. 关键 Vue 组件和交互补齐组件测试，覆盖门控、焦点、键盘、加载、错误和空状态。
6. 桌面、平板、手机四类视口完成真实浏览器验收，无横向滚动、无固定元素遮挡、无可拖拽文本框和可拖拽布局分隔线。
7. 仪表盘迁移后的旧入口、旧控制器和未引用脚本被删除；不能只是移动目录或换名称继续调用。
8. `docs/USER_GUIDE.md`、README、迁移报告和回归记录与最终实现一致。
9. Cursor 最终回报包含实际修改/删除文件、每条验证命令的真实输出摘要、E2E 数量、截图路径和未完成项；不得用“应该没问题”“理论上可用”等表述代替验证。

## 2. 开工前必须执行的检查

在编辑任何文件前先执行：

```powershell
git status --short
git diff --stat
git diff -- apps/web docs README.md
```

要求：

- 当前工作区包含上一轮和用户的未提交修改，禁止重置、回滚或覆盖无关改动。
- 禁止使用 `git reset --hard`、`git checkout -- .`、`git clean -fd` 等破坏性命令。
- 编辑文件前先阅读它的当前版本，不能依据旧缓存或旧文档直接覆盖。
- 如果同一文件已有未提交改动，应在现有内容上做最小增量修改。
- 先记录当前测试基线；发现原本就失败的用例，要区分“已有问题”和“本次引入问题”，但仍应尽量在本任务范围内修复。

## 3. 已完成基线：禁止回退

以下行为已经实现并通过实际浏览器或自动化验证。后续重构必须保留这些行为，并补充自动化回归测试。

### 3.1 导航和整体布局

- 桌面端左侧导航使用真正的固定定位，正文滚动时导航不移动。
- 侧栏展开宽度为 `240px`，收起宽度为 `76px`，主内容自动让位，不被侧栏覆盖。
- 桌面端侧栏支持展开和图标栏两种状态，状态保存在 `localStorage`。
- 移动端保持抽屉导航，不继承桌面端的收起状态。
- 页面滚动到约 `700px` 后，左侧导航仍固定。
- 项目选择器的可点击高度不低于 `44px`。

### 3.2 固定布局和输入框

- 全站 `textarea` 禁止用户拖拽缩放，计算样式必须为 `resize: none`。
- `BaseField`、工作台重做输入框、阅读助手输入框已同步处理。
- 阅读与修订页已删除左右两条可拖拽分隔线，改为固定响应式三栏。
- 已删除未引用的 `apps/web/src/features/reader/lib/reader-workspace.js`，不得恢复。
- 页面不应出现可由用户拖动改变尺寸的容器；容器尺寸由布局断点和内容自然高度控制。

### 3.3 方案确认门控

- 网页端创建小说固定发送 `require_plan_confirmation: true`，用户不能取消此要求。
- 未确认方案时，工作台只显示方案概览、确认、修改、重新生成、删除，以及版本比较/恢复。
- 未确认方案时，隐藏“今日完成”“READY 储备”“当前进度”“运行健康度”“章节生产流程”“章节储备”和正式方案展示区。
- 未确认项目不能进入作品阅读和长期记忆：侧栏点击返回方案审阅，直接输入 URL 也会被路由守卫拦截。
- 确认方案后立即同步书架项目摘要，侧栏访问权限立即解锁，不依赖刷新页面。
- 空书架下显式无效 `projectId` 必须进入 `ProjectMissing`，不能静默选中其他项目。

### 3.4 语义、弹窗和菜单可访问性

- 工作台章节入口是实际 `RouterLink`，不能退回到 `div role="link"`。
- 工作台重做弹窗使用 `BaseDialog`。
- `BaseDialog` 支持 Escape 关闭、Tab/Shift+Tab 焦点陷阱、打开后的初始焦点、关闭后的焦点恢复。
- 小说卡片菜单支持点击外部关闭、Escape 关闭、上下方向键、Home、End 和关闭后的焦点恢复。
- 可点击控件在触屏上应至少有 `44px × 44px` 的有效触控区域。
- 键盘焦点必须可见，不得通过全局 `outline: none` 隐藏。

### 3.5 移动端修复

- 移动端创建页不再把“需求摘要”强制排到表单前面。
- 手机书架工具栏使用两列响应式网格，不产生横向滚动。
- 页面根节点应满足：`document.documentElement.scrollWidth <= window.innerWidth`。

### 3.6 已通过的基线验证

上一轮已通过：

- `npm run type-check`
- `npm run test`：14 tests / 3 files
- `npm run build`
- `python -m unittest discover -s tests -v`：177 tests
- `git diff --check`：没有补丁格式错误，仅存在工作区原有的 LF/CRLF 提示

后续任一阶段完成后，都不能让上述验证回退。

## 4. 本阶段不修改的内容

除非为修复明确的回归或支持测试所必需，本阶段不做以下工作：

- 不重新设计已经确认的创作工作台信息架构。
- 不改变“书架 → 三步创建 → 生成方案 → 审阅确认 → 正式工作台”的业务流程。
- 不改变现有后端业务规则、模型调用策略、计费语义和项目数据格式。
- 不引入新的前端框架；继续使用 Vue 3 和当前项目的状态管理、路由与构建体系。
- 不进行与当前问题无关的全仓库格式化或命名重构。
- 不用大范围 CSS 覆盖来掩盖单个组件的布局问题。

## 5. 阶段一：仪表盘完全迁移为 Vue 3

优先级：P0。

### 5.1 当前问题

`apps/web/src/features/analytics/pages/AnalyticsPage.vue` 目前仍通过类似以下方式挂载旧页面：

```ts
createAnalyticsView(...)
view.mount(hostRef.value)
```

相关旧实现分散在：

- `apps/web/src/features/analytics/lib/template.js`
- `apps/web/src/features/analytics/lib/view.js`
- `apps/web/src/features/analytics/lib/writing.js`
- `apps/web/src/features/analytics/lib/llm.js`
- `apps/web/src/features/analytics/lib/records.js`

这些文件大量使用 `innerHTML`、`document`、`querySelector`、`addEventListener` 和手工 HTML 字符串。它们绕过 Vue 生命周期和响应式状态，使测试、无障碍和后续维护都不稳定。

### 5.2 迁移目标

Vue 必须管理：

- 页签切换；
- 日期范围、项目、模型等筛选状态；
- 首次加载和重新加载；
- 错误提示和重试；
- 空数据状态；
- 表格分页、排序和筛选；
- 展开/折叠或详情交互；
- 请求取消、页面卸载清理；
- 可访问性状态，例如 `aria-selected`、`aria-expanded`、当前排序方向和加载状态。

允许保留图表库的“纯渲染适配器”，但它只能接收明确的 DOM 容器和结构化数据并绘制图表。它不能负责创建整个页面、绑定筛选器事件、渲染表格、保存页面状态或直接请求 API。

### 5.3 建议目标结构

Cursor 应根据当前代码实际命名做适配，但职责必须清晰。建议结构：

```text
apps/web/src/features/analytics/
├─ api/
│  └─ analytics.api.ts
├─ components/
│  ├─ AnalyticsTabs.vue
│  ├─ AnalyticsFilters.vue
│  ├─ AnalyticsMetricCard.vue
│  ├─ WritingAnalyticsPanel.vue
│  ├─ LlmAnalyticsPanel.vue
│  ├─ RecordsAnalyticsPanel.vue
│  ├─ AnalyticsChart.vue
│  ├─ AnalyticsRecordsTable.vue
│  ├─ AnalyticsEmptyState.vue
│  └─ AnalyticsErrorState.vue
├─ composables/
│  ├─ useAnalyticsQuery.ts
│  └─ useAnalyticsChart.ts
├─ stores/
│  └─ analytics.store.ts
├─ types/
│  └─ analytics.types.ts
├─ pages/
│  └─ AnalyticsPage.vue
└─ __tests__/ 或组件同目录 *.spec.ts
```

不要求机械地创建所有文件；文件数量应服从职责边界，避免一个超大 `.vue` 文件，也避免每十行代码拆一个文件。

### 5.4 具体执行步骤

1. 盘点现有仪表盘所有页签、筛选项、接口、指标、图表、表格列、分页和交互。
2. 为接口响应建立 TypeScript 类型，禁止继续使用无约束的全局对象或大面积 `any`。
3. 将请求集中到 `api` 模块；页面组件不得散落拼接 URL。
4. 将跨组件共享的查询条件和数据状态放入 store 或 composable；仅局部状态留在组件中。
5. 用 Vue 模板重建页签、筛选器、状态提示和记录表格。
6. 图表组件在 `onMounted`、`watch` 和 `onBeforeUnmount` 中正确创建、更新和销毁实例；窗口尺寸变化应使用受控的 `ResizeObserver` 或图表库 resize API。
7. 对快速连续筛选进行防抖或请求取消，避免旧响应覆盖新选择。
8. 请求失败时保留用户已选择的筛选条件，并提供可聚焦的错误提示和重试按钮。
9. 空数据必须展示可理解的空状态，不能留下空白画布或无限加载。
10. 表格使用语义化 `table`、`thead`、`tbody`、`th`，排序按钮提供可读标签和 `aria-sort`。
11. 页签使用语义化按钮和正确的 tab 状态；不得只依赖颜色表示选中状态。
12. 完成功能对照后，删除不再被引用的旧 controller、template、view 文件和死入口。

### 5.5 禁止的伪迁移方式

- 禁止把旧 JS 文件移动到新文件夹后继续 `mount(host)`。
- 禁止在 Vue 组件中用一个大段 `v-html` 重新注入旧模板。
- 禁止在组件顶层直接 `document.querySelector` 全局查找页面节点。
- 禁止为通过类型检查给旧模块整片添加 `@ts-ignore` 或 `any`。
- 禁止在每次状态更新时销毁并重建整页 DOM。

### 5.6 阶段验收

- `AnalyticsPage.vue` 不再调用 `createAnalyticsView(...).mount(...)`。
- 页面功能与迁移前对等，加载、错误、空态都有可见结果。
- 离开页面后没有遗留事件监听器、定时器、观察器或图表实例。
- 仪表盘组件测试通过。
- `rg -n "createAnalyticsView|\.mount\(host|template\.js|view\.js" apps/web/src/features/analytics` 不再命中运行时旧入口。
- `innerHTML` 只允许在经过说明的图表渲染适配器中存在；页面、筛选器和表格不得使用。

## 6. 阶段二：补齐并启用 ESLint

优先级：P0。

### 6.1 当前问题

前端 `package.json` 已定义：

```json
"lint": "eslint ."
```

但项目缺少可执行的 ESLint 依赖和配置，当前命令不能作为质量门禁。

### 6.2 实施要求

1. 安装与当前 Vue 3、TypeScript、Vite 和现有测试栈兼容的 ESLint 依赖。
2. 优先使用 ESLint flat config，例如 `eslint.config.js` 或与项目模块格式一致的扩展名。
3. 正确配置 Vue 单文件组件解析、TypeScript 文件、浏览器环境和 Vitest 测试环境。
4. 忽略至少以下生成内容：`dist`、`coverage`、Playwright 报告、测试截图/视频、依赖目录。
5. 根据项目实际代码选择合理规则；先修复真实问题，不允许靠全局关闭核心规则让命令变绿。
6. 对确有必要的单行例外写局部注释并解释原因，不能整文件禁用。
7. 更新 lockfile，确保 `npm ci` 可复现安装。

建议依赖方向应以当前版本兼容性为准，不要盲目复制最新版组合：

- `eslint`
- `eslint-plugin-vue`
- `typescript-eslint` 或对应兼容包
- Vue 解析器所需依赖
- 如项目使用 Prettier，仅处理规则冲突；不要顺带格式化全仓库

### 6.3 阶段验收

```powershell
cd apps/web
npm ci
npm run lint
npm run type-check
```

三条命令必须退出码为 0。最终报告要给出 ESLint 配置文件、依赖版本和修复的问题类型，不能只写“已配置”。

## 7. 阶段三：建立 Playwright E2E 回归体系

优先级：P0。

### 7.1 基础设施

当前存在 `"test:e2e": "playwright test"`，但缺少 `@playwright/test`、配置和可执行用例。需要：

- 添加与项目 Node 环境兼容的 `@playwright/test`。
- 新增 Playwright 配置，明确 `testDir`、超时、重试、报告器、截图、trace、浏览器和 `webServer`。
- 本地开发默认只在失败时保留截图/trace，CI 可按需保留完整报告。
- 为 E2E 提供独立数据库或临时数据目录；绝对禁止连接、清空、重命名或删除用户真实数据库。
- 测试前准备数据、测试后清理数据。清理范围必须由测试运行唯一标识限定。
- 尽量使用面向用户的 role、label、name 定位元素，不要依赖脆弱的 CSS 层级或中文文案之外的随机 class。
- 仅在确有必要时添加稳定的 `data-testid`，不要给所有元素加测试 ID。

### 7.2 必须覆盖的核心用例

至少建立以下独立且可重复运行的测试。可以合理合并流程，但报告中必须能对应每项断言。

1. 空书架展示正确空态，点击“新建小说”进入创建页。
2. 完成三步创建表单，提交后生成方案并进入方案审阅状态。
3. 未确认方案时只显示审阅相关区域，不出现生产指标和章节生产区。
4. 未确认项目直接访问 reader 和 memory URL 时被拦截并回到方案审阅。
5. 确认方案后正式工作台立即出现，阅读和长期记忆入口立即可用。
6. 桌面侧栏可以展开/收起；刷新后状态持久化；移动端仍使用抽屉且不错误继承桌面宽度状态。
7. 书架卡片菜单可用，重命名成功，删除流程正确；涉及确认弹窗时验证取消不会删除。
8. 显式无效 `projectId` 进入 `ProjectMissing`，即使书架为空也一样。
9. 阅读页不存在 `.workspace-resizer`，正文布局不可拖拽。
10. 页面内所有 `textarea` 的计算样式均为 `resize: none`。
11. `BaseDialog` 支持 Escape、Tab/Shift+Tab 焦点循环，并在关闭后恢复到触发按钮。
12. 关键页面在桌面、平板和手机视口都满足 `scrollWidth <= innerWidth`。
13. 小说卡片菜单支持 Escape、ArrowUp、ArrowDown、Home、End，并在关闭后恢复焦点。
14. 仪表盘的页签、筛选、加载、错误、空状态、分页或排序至少覆盖各一条真实交互路径。

### 7.3 测试数据安全

- 使用测试专用环境变量指向临时数据库或临时数据根目录。
- 测试启动时打印“正在使用测试数据目录”的非敏感路径，便于审计。
- 如果后端不支持测试数据隔离，先实现最小的配置入口，再编写 E2E。
- 清理前验证路径位于测试临时目录内，禁止对项目根目录、用户目录或默认生产数据库执行递归删除。
- 不在仓库提交测试生成的数据库、报告、视频或大量截图；只提交必要的基准截图目录说明或验收截图。

### 7.4 稳定性要求

- 禁止使用大量固定 `waitForTimeout` 掩盖竞态。
- 应等待可观察状态：响应、URL、可见文本、按钮启用、加载提示消失等。
- 测试之间不能依赖执行顺序。
- 每个测试拥有独立项目数据，或通过 beforeEach 创建、afterEach 精确清理。
- 失败时应输出足够诊断信息；重复运行至少两次确认无偶发失败。

### 7.5 阶段验收

```powershell
cd apps/web
npm run test:e2e
npm run test:e2e
```

连续两次通过。最终报告必须写明测试文件数、用例数、浏览器项目数、独立测试数据库/目录位置和报告路径。

## 8. 阶段四：补齐 Vue 组件与交互测试

优先级：P1。

现有测试主要覆盖 projects store、创建 store 和 router guard，组件级交互覆盖不足。至少新增：

- `BaseDialog.spec.ts`
- `AppSidebar.spec.ts`
- `useActionMenu.spec.ts`，或覆盖该 composable 的真实宿主组件测试
- `WorkbenchPage.spec.ts`
- `ReaderPage.spec.ts`
- 仪表盘页面/store/composable/关键组件测试

### 8.1 必须断言的行为

#### BaseDialog

- 打开后焦点进入弹窗的指定初始元素或首个可交互元素。
- Tab 和 Shift+Tab 不会逃出弹窗。
- Escape 触发关闭。
- 关闭后焦点回到原触发元素。
- 标题、描述和对话框角色关联正确。

#### AppSidebar

- 展开、收起后 class/ARIA 状态正确。
- 桌面收起状态写入并从 `localStorage` 恢复。
- 移动端抽屉行为不受桌面状态破坏。
- 未确认项目的受限入口返回工作台方案审阅。

#### 卡片操作菜单

- 点击外部和 Escape 关闭。
- ArrowUp/ArrowDown/Home/End 移动焦点。
- 关闭后焦点恢复到菜单触发器。
- 重命名请求失败时保留用户输入并显示错误。

#### WorkbenchPage

- 未确认状态只渲染方案审阅区。
- 确认成功后正式区域立即出现。
- 确认、修改、重新生成请求分别有加载、错误和防重复提交状态。
- 请求失败不清空用户刚输入的修改意见。

#### ReaderPage

- 不渲染 `.workspace-resizer`。
- 固定三栏在不同状态下采用正确 class/结构。
- 阅读助手输入框不可缩放。
- 加载、空内容和请求错误有稳定界面。

#### Analytics

- 页签与筛选状态由 Vue 响应式状态驱动。
- 请求成功、失败、空数据和重试路径。
- 快速切换时过期响应不能覆盖新响应。
- 表格排序、分页与无障碍属性。
- 图表组件卸载时调用清理逻辑。

### 8.2 测试质量要求

- 不要只断言组件“能 mount”。
- 避免把 Vue 内部实现细节作为主要断言，优先观察用户可见结果和发出的业务事件。
- mock 应位于网络/API 边界，不要把整个待测组件逻辑 mock 掉。
- 清理 `localStorage`、事件监听器、fake timers 和挂载容器，测试不可相互污染。

### 8.3 阶段验收

```powershell
cd apps/web
npm run test
npm run type-check
```

报告新增测试文件和新增用例数量，并说明关键覆盖点。

## 9. 阶段五：修复构建产物与 Python 测试的不稳定依赖

优先级：P1。

### 9.1 当前问题

`tests/test_web_spa_assets.py` 要求存在 `apps/web/dist/index.html`，但 `dist/` 被 `.gitignore` 忽略。新克隆仓库直接执行 README 中的 Python 测试可能失败，当前成功可能只是因为本机残留了旧构建产物。

### 9.2 推荐方案

优先建立统一、明确的验证顺序：

1. `npm ci`
2. 前端 lint、类型、组件测试
3. `npm run build`
4. Python 测试
5. E2E（如 E2E 自己负责启动前后端，也可在同一统一脚本中安排）

可以新增一个跨平台验证脚本或在 CI 中固化该顺序，但不得依赖开发者机器已有 `dist`。

如果现有项目不适合统一脚本，则应修改 `test_web_spa_assets.py`：在 `dist` 不存在时提供明确、可行动的构建提示或受控 skip，并确保正式 CI 在执行 Python 测试前强制构建。不能静默通过而导致 SPA 资源从未被验证。

### 9.3 文档同步

- README 中的验证命令顺序必须与实际实现一致。
- `docs/USER_GUIDE.md` 是中文用户指南唯一权威来源；如果用户可见启动、构建、配置、数据路径或排错步骤变化，必须在同一提交中更新。
- README 中指向 `docs/USER_GUIDE.md` 的链接必须继续有效。

### 9.4 阶段验收

在确认不会丢失用户数据的前提下，用一个没有旧 `dist` 的干净环境验证完整顺序。不得仅在已有构建目录的工作区中证明成功。

## 10. 阶段六：真实多视口与键盘验收

优先级：P1。

### 10.1 必测视口

- 桌面：`1440 × 900`
- 小型桌面/平板横向：`1024 × 768`
- 平板纵向：`768 × 1024`
- 手机：`390 × 844`

### 10.2 必测页面和状态

每个适用视口至少检查：

- 书架：侧栏展开；
- 书架：侧栏收起；
- 创建小说步骤 1、2、3；
- 未确认方案的工作台；
- 已确认后的正式工作台；
- 阅读与修订页；
- 长期记忆页；
- 仪表盘各页签；
- 设置页；
- 代表性的弹窗打开状态；
- 书架卡片操作菜单打开状态。

### 10.3 每个页面的验收项

- `document.documentElement.scrollWidth <= window.innerWidth`。
- 桌面固定侧栏在正文滚动后位置不变。
- 主内容不会被展开或收起侧栏遮挡。
- 页面没有多余的横向滚动条和嵌套双纵向滚动条。
- 文本和按钮不被截断，长标题、空数据和错误文案不会撑破布局。
- 所有 `textarea` 的计算样式为 `resize: none`。
- 页面不存在布局拖拽柄；阅读页不存在 `.workspace-resizer`。
- 键盘 Tab 顺序符合视觉顺序，焦点轮廓清楚可见。
- 弹窗打开后背景不可被键盘访问，关闭后焦点恢复。
- 菜单键盘操作完整。
- 触控目标至少 `44 × 44px`，特别检查侧栏按钮、卡片菜单、关闭按钮和分页按钮。
- 固定元素不能遮挡底部操作区、Toast、表单错误或移动端内容。
- 颜色不是传递选中、错误或成功状态的唯一手段。

### 10.4 截图归档

将人工/自动验收截图放入明确的验收目录，例如：

```text
artifacts/frontend-regression/<date-or-run-id>/
├─ desktop-1440/
├─ desktop-1024/
├─ tablet-768/
└─ mobile-390/
```

若该目录不应提交，加入 `.gitignore` 并在最终回报中提供本地绝对路径。文件名应包含页面和状态，禁止 `1.png`、`new.png` 这类不可识别名称。

## 11. 阶段七：旧代码、日志问题和文档收尾

优先级：P2。

### 11.1 旧代码清理

仪表盘 Vue 化后执行：

```powershell
rg -n "innerHTML|document\.querySelector|addEventListener|createAnalyticsView|workspace-resizer" apps/web/src
rg -n "template\.js|view\.js|writing\.js|llm\.js|records\.js" apps/web/src
```

逐条判断：

- 页面模板、筛选器、表格和交互事件中的旧 DOM 操作必须移除。
- 图表适配器中确有必要的 DOM 操作可以保留，但要局部、可清理、有测试，并写清原因。
- 删除未引用的文件、导出、类型、样式和测试 fixture。
- 不允许保留“以后可能会用”的死入口，也不允许把旧文件改名后继续留存。

### 11.2 空文档和迁移报告

- `docs/_baseline_workbench_regression.md` 当前为空：补充真实回归记录；如果项目不再使用它，则删除并移除全部引用。不得保留空占位文件。
- 更新 `docs/_vue3_migration_stage12_report.md`，只陈述真实完成情况。不得继续声称尚未完成的仪表盘原生化、lint 或 E2E 已完成。
- 若新增本任务执行报告，内容应链接到实际测试和截图，而不是复制本任务书。

### 11.3 favicon 404

检查开发/测试服务器日志中的 `/favicon.ico` 404：

- 如果项目已有品牌图标，正确放入 Vite 公共目录并在 HTML 中引用。
- 如果没有正式图标，可提供项目现有视觉体系内的最小图标资源或删除错误引用。
- 不要通过吞掉所有 404 的后端路由来掩盖问题。

### 11.4 用户指南规则

项目规定 `docs/USER_GUIDE.md` 是中文用户指南唯一权威来源。凡本次实现涉及以下用户可见变化，必须同步更新：

- UI 操作和工作流状态；
- 配置变量；
- HTTP 端点；
- 数据存储或备份路径；
- 启动、构建、测试或故障排查命令；
- 成本或安全边界。

只新增开发测试而没有改变普通用户操作时，不要把内部测试细节堆入用户指南；但 README 中面向使用者或贡献者的命令必须准确，并保持用户指南链接有效。

## 12. 目标文件和目录清单

以下是预期影响范围，不是要求机械创建全部文件。Cursor 最终应根据实际改动报告准确清单。

```text
apps/web/
├─ eslint.config.*
├─ playwright.config.ts
├─ package.json
├─ package-lock.json
├─ e2e/
│  ├─ fixtures/
│  ├─ helpers/
│  └─ *.spec.ts
└─ src/
   ├─ components/base/BaseDialog.spec.ts
   ├─ components/navigation/AppSidebar.spec.ts
   ├─ composables/useActionMenu.spec.ts
   └─ features/
      ├─ analytics/
      │  ├─ api/
      │  ├─ components/
      │  ├─ composables/
      │  ├─ stores/
      │  ├─ types/
      │  ├─ pages/AnalyticsPage.vue
      │  └─ **/*.spec.ts
      ├─ reader/pages/ReaderPage.spec.ts
      └─ workbench/pages/WorkbenchPage.spec.ts
docs/
├─ USER_GUIDE.md
├─ _baseline_workbench_regression.md（补充或删除）
└─ _vue3_migration_stage12_report.md
tests/
└─ test_web_spa_assets.py（如采用测试提示/跳过方案）
README.md
```

迁移完成后，预计删除 `apps/web/src/features/analytics/lib/` 中不再引用的旧页面控制文件。删除前必须用 `rg` 验证引用；最终回报逐个列出删除文件。

## 13. 推荐执行顺序与阶段门禁

为降低一次性重构风险，按以下顺序提交或至少分阶段验证：

1. 记录基线并补最关键的回归测试骨架。
2. 仪表盘 API 类型、store/composable 和 Vue 组件迁移。
3. 仪表盘功能对照通过后删除旧实现。
4. 配置 ESLint并修复现存真实问题。
5. 补齐通用组件、工作台、阅读页和仪表盘组件测试。
6. 建立独立数据的 Playwright E2E。
7. 修正构建与 Python 测试顺序。
8. 完成四类视口、键盘和焦点验收并归档截图。
9. 清理旧代码、空文档、迁移报告和 favicon 404。
10. 执行完整命令矩阵并编写最终回报。

每一阶段完成后至少执行与该阶段相关的 lint、类型和测试。不要等到全部重构完成后才第一次运行测试。

## 14. 最终完整验证命令

在项目当前支持的 Node/Python 环境中执行。以下命令必须真实运行并记录结果：

```powershell
cd apps/web
npm ci
npm run lint
npm run type-check
npm run test
npm run build
npm run test:e2e

cd ../..
python -m unittest discover -s tests -v
git diff --check
```

另执行静态清理检查：

```powershell
rg -n "createAnalyticsView|\.mount\(host|workspace-resizer" apps/web/src
rg -n "innerHTML|document\.querySelector|addEventListener" apps/web/src/features/analytics
rg -n "reader-workspace\.js" apps/web/src
git status --short
```

要求：

- 对仍存在的每一处 `innerHTML`、`document.querySelector` 或 `addEventListener` 给出文件位置和保留原因；没有合理原因就继续清理。
- `git diff --check` 如只出现项目原有换行符警告，应在报告中如实说明；真实空白错误必须修复。
- E2E 至少连续运行两次，排除偶发成功。
- 构建后再运行依赖 SPA 资源的 Python 测试。

## 15. Cursor 最终回报模板

Cursor 完成后必须按下面模板返回，所有项目都填写真实结果。

```markdown
# 前端剩余修复执行结果

## 1. 完成摘要
- 已完成：
- 未完成：
- 与任务书不同的实现选择及原因：

## 2. 实际修改文件
- `路径`：修改内容

## 3. 实际新增文件
- `路径`：用途

## 4. 实际删除文件
- `路径`：确认无引用的依据

## 5. 仪表盘 Vue 迁移结果
- Vue 管理的状态和交互：
- 保留的图表适配器：
- 仍存在的 DOM API 及原因：
- 旧入口清理结果：

## 6. 自动化测试结果
- `npm run lint`：退出码、错误/警告数量
- `npm run type-check`：退出码
- `npm run test`：测试文件数、用例数、通过/失败数
- `npm run build`：退出码、构建摘要
- `npm run test:e2e` 第一次：项目数、用例数、通过/失败数
- `npm run test:e2e` 第二次：项目数、用例数、通过/失败数
- `python -m unittest discover -s tests -v`：用例数、通过/失败数
- `git diff --check`：结果

## 7. E2E 数据隔离
- 测试数据库/数据目录：
- 创建与清理方式：
- 证明未使用用户真实数据的配置：

## 8. 多视口与键盘验收
- 1440×900：
- 1024×768：
- 768×1024：
- 390×844：
- 横向滚动检查：
- 固定侧栏检查：
- textarea resize 检查：
- 弹窗焦点检查：
- 菜单键盘检查：

## 9. 截图和测试报告
- 截图绝对路径：
- Playwright HTML 报告路径：
- 失败 trace/video（如有）：

## 10. 文档同步
- `docs/USER_GUIDE.md`：更新内容或无需更新的理由
- `README.md`：
- 回归记录：
- Vue 迁移报告：

## 11. 尚存风险或未完成项
- 无；或逐项列出具体文件、原因和下一步，禁止写“后续优化”。
```

## 16. 明确禁止事项

- 禁止回退第 3 节列出的任何已完成行为。
- 禁止删除、覆盖或格式化用户的无关未提交修改。
- 禁止把旧 DOM 页面包装在 Vue 组件中冒充 Vue 化完成。
- 禁止通过全局关闭 ESLint 规则、批量 `eslint-disable`、`@ts-ignore` 或大面积 `any` 让验证假通过。
- 禁止让 E2E 使用或清理真实用户数据库。
- 禁止用固定等待时间代替可观察状态同步。
- 禁止提交 `node_modules`、`dist`、Playwright 大型报告、视频、trace 或临时数据库。
- 禁止为了修复 favicon 404 而吞掉所有静态资源 404。
- 禁止保留空回归文档、虚假的迁移完成报告或无人引用的旧入口。
- 禁止只报告“页面可打开”“功能应该正常”；必须提供命令结果、用例数量和截图路径。

## 17. 交付前自检清单

- [ ] 工作区原有改动仍保留，未发生无关回滚。
- [ ] 仪表盘由 Vue 3 原生组件和响应式状态管理。
- [ ] 旧仪表盘页面挂载入口及未引用文件已删除。
- [ ] 方案确认门控没有回退。
- [ ] 固定侧栏、收起持久化和移动端抽屉没有回退。
- [ ] 阅读页没有拖拽分隔线。
- [ ] 所有 textarea 不可拖拽缩放。
- [ ] ESLint 可执行且没有靠全局禁用规则通过。
- [ ] 组件测试覆盖关键状态和键盘行为。
- [ ] Playwright 使用独立测试数据并连续两次通过。
- [ ] 新环境不依赖残留 dist 即可按文档顺序完成验证。
- [ ] 四类视口无横向滚动和固定元素遮挡。
- [ ] 键盘焦点可见，弹窗和菜单焦点行为正确。
- [ ] favicon 404 已处理或有明确、真实的结论。
- [ ] README、用户指南、迁移报告和回归记录与代码一致。
- [ ] 完整验证命令均已真实执行并记录。

