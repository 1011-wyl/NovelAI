import { test, expect } from "@playwright/test";
import { createNovelDraft, gotoLibrary, resetE2EData } from "./helpers/app";

test.beforeEach(async ({ request }) => resetE2EData(request));
test.afterEach(async ({ request }) => resetE2EData(request));

test.describe("侧栏、菜单与弹窗", () => {
  test("桌面侧栏收起状态可持久化", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoLibrary(page);
    await page.getByRole("button", { name: "收起导航" }).click();
    await expect(page.locator("aside.sidebar")).toHaveClass(/is-collapsed/);
    await expect
      .poll(async () => page.evaluate(() => localStorage.getItem("novelAgentSidebarCollapsed")))
      .toBe("1");
    await page.reload();
    await expect(page.locator("aside.sidebar")).toHaveClass(/is-collapsed/);
    await page.getByRole("button", { name: "展开导航" }).click();
    await expect(page.locator("aside.sidebar")).not.toHaveClass(/is-collapsed/);
  });

  test("移动端使用抽屉且不错误继承桌面收起宽度状态", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoLibrary(page);
    await page.getByRole("button", { name: "收起导航" }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    const openNavigation = page.getByRole("button", { name: "打开导航" });
    await expect(openNavigation).toBeVisible();
    await openNavigation.click();
    const sidebar = page.locator("aside.sidebar");
    await expect(sidebar).toHaveClass(/is-open/);
    await expect(sidebar.getByRole("link", { name: "我的小说" })).toBeVisible();
    await expect
      .poll(async () => {
        const box = await sidebar.boundingBox();
        return box ? { x: Math.round(box.x), width: Math.round(box.width) } : null;
      })
      .toEqual({ x: 0, width: 240 });
    expect(
      await page.evaluate(() => document.elementFromPoint(24, 120)?.closest("aside.sidebar") !== null)
    ).toBe(true);
    await page.getByRole("button", { name: "关闭导航" }).click();
    await expect(sidebar).not.toHaveClass(/is-open/);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth
    );
    expect(overflow).toBe(true);
  });

  test("卡片菜单键盘操作、重命名及删除流程", async ({ page }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "E2E 菜单测试。", "E2E菜单原名");
    await page.goto("/novels");
    await expect(page.getByText("E2E菜单原名")).toBeVisible();

    const more = page.getByRole("button", { name: "更多操作" }).first();
    await more.click();
    const menu = page.getByRole("menu");
    await expect(menu).toBeVisible();
    const renameItem = page.getByRole("menuitem", { name: "修改书名" });
    const deleteItem = page.getByRole("menuitem", { name: "删除" });
    await expect(renameItem).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(deleteItem).toBeFocused();
    await page.keyboard.press("ArrowUp");
    await expect(renameItem).toBeFocused();
    await page.keyboard.press("End");
    await expect(deleteItem).toBeFocused();
    await page.keyboard.press("Home");
    await expect(renameItem).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(menu).toHaveCount(0);
    await expect(more).toBeFocused();

    await more.click();
    await page.getByRole("menuitem", { name: "修改书名" }).click();
    const renameDialog = page.getByRole("dialog", { name: "修改书名" });
    await expect(renameDialog).toBeVisible();
    await renameDialog.locator("#rename-title").fill("E2E菜单新名");
    await renameDialog.getByRole("button", { name: "保存" }).click();
    await expect(renameDialog).toHaveCount(0);
    await expect(page.getByText("E2E菜单新名")).toBeVisible();

    await page.getByRole("button", { name: "更多操作" }).first().click();
    await page.getByRole("menuitem", { name: "删除" }).click();
    const deleteDialog = page.getByRole("dialog", { name: "删除小说" });
    await expect(deleteDialog).toBeVisible();
    await deleteDialog.getByRole("button", { name: "取消" }).click();
    await expect(deleteDialog).toHaveCount(0);
    await expect(page.getByText("E2E菜单新名")).toBeVisible();

    await page.getByRole("button", { name: "更多操作" }).first().click();
    await page.getByRole("menuitem", { name: "删除" }).click();
    await expect(deleteDialog).toBeVisible();
    await deleteDialog.getByRole("button", { name: "确认删除" }).click();
    await expect(deleteDialog).toHaveCount(0);
    await expect(page.getByText("E2E菜单新名")).toHaveCount(0);
  });

  test("BaseDialog Escape 与焦点恢复", async ({ page }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "E2E 弹窗焦点。", "E2E弹窗书");
    await page.goto("/novels");
    const more = page.getByRole("button", { name: "更多操作" }).first();
    await more.click();
    await page.getByRole("menuitem", { name: "修改书名" }).click();
    const dialog = page.getByRole("dialog", { name: "修改书名" });
    await expect(dialog).toBeVisible();
    const focusable = dialog.locator(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    const focusableCount = await focusable.count();
    expect(focusableCount).toBeGreaterThan(1);
    await focusable.nth(focusableCount - 1).focus();
    await page.keyboard.press("Tab");
    await expect(focusable.first()).toBeFocused();
    await focusable.first().focus();
    await page.keyboard.press("Shift+Tab");
    await expect(focusable.nth(focusableCount - 1)).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(more).toBeFocused();
  });

  test("桌面侧栏在正文滚动后保持固定", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoLibrary(page);
    await createNovelDraft(page, "E2E 固定侧栏测试。", "E2E固定侧栏书");
    const sidebar = page.locator("aside.sidebar");
    const before = await sidebar.boundingBox();
    expect(before).not.toBeNull();
    await page.evaluate(() => window.scrollTo(0, 700));
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
    const after = await sidebar.boundingBox();
    expect(after).not.toBeNull();
    expect(Math.abs((after?.y || 0) - (before?.y || 0))).toBeLessThan(1);
  });
});

test.describe("视口无横向滚动", () => {
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 1024, height: 768 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
  ]) {
    test(`${viewport.width}x${viewport.height} 书架与创建无横向滚动`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await gotoLibrary(page);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
      ).toBe(true);
      await page.getByRole("button", { name: "新建小说" }).click();
      await expect(page).toHaveURL(/\/novels\/new/);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
      ).toBe(true);
    });
  }
});
