import { test, expect } from "@playwright/test";
import {
  assertNoHorizontalOverflow,
  assertTextareasNonResizable,
  confirmPlan,
  createNovelDraft,
  gotoLibrary,
  resetE2EData,
} from "./helpers/app";

test.beforeEach(async ({ request }) => resetE2EData(request));
test.afterEach(async ({ request }) => resetE2EData(request));

test.describe("书架、创建与方案门控", () => {
  test("空书架空态并可进入创建页", async ({ page }) => {
    await gotoLibrary(page);
    await expect(page.getByRole("heading", { name: "我的小说" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "从一个想法开始你的第一本小说" })).toBeVisible();
    await expect(page.getByRole("button", { name: "新建小说" })).toBeVisible();
    await page.getByRole("button", { name: "新建小说" }).click();
    await expect(page).toHaveURL(/\/novels\/new/);
    await expect(page.getByText("第 1 步，共 3 步")).toBeVisible();
  });

  test("三步创建后进入未确认方案审阅，生产区隐藏", async ({ page }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "E2E 门控测试：主角穿越后改写规则。", "E2E门控书");
    await expect(page.getByText("创作方案已生成，请检查后确认")).toBeVisible();
    await expect(page.getByRole("button", { name: "确认创作方案" })).toBeVisible();
    await expect(page.getByRole("button", { name: "修改方案" })).toBeVisible();
    await expect(page.getByRole("button", { name: "重新生成" })).toBeVisible();
    await expect(page.getByText("今日完成")).toHaveCount(0);
    await expect(page.getByText("章节生产流程")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "生成下一章" })).toHaveCount(0);
  });

  test("未确认时直接访问 reader/memory 被拦截回工作台", async ({ page }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "E2E URL 守卫测试。", "E2E守卫书");
    const url = page.url();
    const projectId = url.match(/\/novels\/([^/]+)\/workbench/)?.[1];
    expect(projectId).toBeTruthy();

    await page.goto(`/novels/${projectId}/reader`);
    await expect(page).toHaveURL(new RegExp(`/novels/${projectId}/workbench`));
    await expect(page.getByRole("button", { name: "确认创作方案" })).toBeVisible();

    await page.goto(`/novels/${projectId}/memory`);
    await expect(page).toHaveURL(new RegExp(`/novels/${projectId}/workbench`));
  });

  test("确认后立即解锁正式工作台与阅读/记忆入口", async ({ page }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "E2E 确认解锁测试。", "E2E确认书");
    await confirmPlan(page);
    await expect(page.getByText("今日完成")).toBeVisible();
    await expect(page.getByText("章节生产流程")).toBeVisible();

    await page.getByRole("link", { name: "作品阅读" }).click();
    await expect(page).toHaveURL(/\/reader/);
    await expect(page.locator(".workspace-resizer")).toHaveCount(0);

    await page.getByRole("link", { name: "长期记忆" }).click();
    await expect(page).toHaveURL(/\/memory/);
  });

  test("显式无效 projectId 进入项目不存在页", async ({ page }) => {
    await page.goto("/novels/does-not-exist-xyz/workbench");
    await expect(page.getByRole("heading", { name: "项目不存在" })).toBeVisible();
    await expect(page.getByText(/找不到小说/)).toBeVisible();
  });
});

test.describe("布局与输入约束", () => {
  test("阅读页无拖拽分隔线，textarea 不可缩放，关键页无横向滚动", async ({ page }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "E2E 布局约束。", "E2E布局书");
    await confirmPlan(page);
    await page.getByRole("link", { name: "作品阅读" }).click();
    await expect(page).toHaveURL(/\/reader/);
    await expect(page.locator(".workspace-resizer")).toHaveCount(0);
    await assertTextareasNonResizable(page);
    await assertNoHorizontalOverflow(page);

    for (const path of ["/novels", "/analytics", "/settings", "/novels/new"]) {
      await page.goto(path);
      await assertNoHorizontalOverflow(page);
    }
  });
});
