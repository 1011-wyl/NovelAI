import { test, expect } from "@playwright/test";
import {
  confirmPlan,
  createNovelDraft,
  gotoLibrary,
  openFailedChapterMenu,
  resetE2EData,
} from "./helpers/app";

test.beforeEach(async ({ request }) => resetE2EData(request));
test.afterEach(async ({ request }) => resetE2EData(request));

test.describe("开篇生成与 FAILED 恢复", () => {
  test("确认后生成第 1 章绑定第一条锚点且无承接上一章", async ({ page }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "E2E 开篇锚点：仓储管理员抢到第一项先机。", "E2E开篇书");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.getByRole("link", { name: /异常征兆/ }).first()).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByText("承接上一章")).toHaveCount(0);
  });

  test("FAILED 章节可在工作台查看原因并重新规划", async ({ page }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "__E2E_FAIL_REVIEW__ 构造失败章节。", "E2E失败书");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.locator(".status-failed").first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("button", { name: "重新生成第 1 章" })).toBeVisible();
    await openFailedChapterMenu(page);
    await expect(page.getByRole("button", { name: "重新规划并重写" })).toBeVisible();
  });

  test("FAILED 阅读页可改草稿并重新送审", async ({ page }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "__E2E_FAIL_REVIEW__ 阅读送审。", "E2E送审书");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.locator(".status-failed").first()).toBeVisible({ timeout: 60_000 });
    await page.getByRole("link", { name: "作品阅读" }).click();
    await expect(page).toHaveURL(/\/reader/);
    await expect(page.getByRole("alert")).toContainText(/质量待修改|未通过审核/);
    const resubmit = page.getByRole("button", { name: "重新送审", exact: true });
    await expect(page.getByRole("button", { name: "应用修订" })).toHaveCount(0);
    const editor = page.locator("#wsContentInput");
    await expect(editor).toBeEnabled();
    const current = await editor.inputValue();
    await editor.fill(`${current}\n【送审修正】`);
    await expect(resubmit).toBeEnabled({ timeout: 10_000 });
    await resubmit.click();
    await page.getByRole("button", { name: "确认送审" }).click();
    await expect(page.getByRole("button", { name: "应用修订" })).toBeVisible({ timeout: 60_000 });
  });

  test("FAILED 草稿质量门未通过时仍可继续编辑", async ({ page }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "__E2E_FAIL_REVIEW__ 送审仍失败。", "E2E再失败书");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.locator(".status-failed").first()).toBeVisible({ timeout: 60_000 });
    await page.getByRole("link", { name: "作品阅读" }).click();
    const banner = page.getByRole("alert");
    await expect(banner).toContainText(/质量待修改|未通过审核/);
    const editor = page.locator("#wsContentInput");
    const current = await editor.inputValue();
    await editor.fill(`${current}\n补一句但仍未过审`);
    await page.getByRole("button", { name: "重新送审", exact: true }).click();
    await page.getByRole("button", { name: "确认送审" }).click();
    const recoveryAlert = page.locator(".recovery-banner");
    await expect(recoveryAlert).toBeVisible({ timeout: 60_000 });
    await expect
      .poll(async () => recoveryAlert.evaluate((el) => document.activeElement === el), {
        timeout: 10_000,
      })
      .toBe(true);
    await expect(page.getByRole("button", { name: "重新送审", exact: true })).toBeVisible();
    await expect(page.locator("#wsContentInput")).toHaveValue(/补一句但仍未过审/);
  });

  test("工作区缺少 capabilities 时禁用 AI", async ({ page }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "E2E 能力降级。", "E2E能力书");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.getByRole("link", { name: /异常征兆/ }).first()).toBeVisible({
      timeout: 60_000,
    });
    let assistantSessionRequests = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().includes("/assistant/sessions")) {
        assistantSessionRequests += 1;
      }
    });
    await page.route("**/chapters/**/workspace", async (route) => {
      const response = await route.fetch();
      const body = (await response.json()) as Record<string, unknown>;
      delete body.capabilities;
      await route.fulfill({
        status: response.status(),
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
    });
    await page.getByRole("link", { name: "作品阅读" }).click();
    await expect(page.getByText("服务器未返回工作区能力")).toBeVisible();
    await expect(page.getByRole("button", { name: "新建会话" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "发送" })).toBeDisabled();
    expect(assistantSessionRequests).toBe(0);
  });

  test("符合条件的失败项目可预览修复，有正式章节则不可确认", { timeout: 360_000 }, async ({ page, request }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "正式章节后不可自动修复。", "E2E正式书");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.getByRole("link", { name: /异常征兆/ }).first()).toBeVisible({
      timeout: 60_000,
    });
    const list = await request.get("/api/novels");
    const payload = (await list.json()) as { items: Array<{ id: string; title: string }> };
    const ready = payload.items.find((item) => item.title === "E2E正式书");
    expect(ready).toBeTruthy();
    const preview = await request.get(
      `/api/novels/${encodeURIComponent(ready!.id)}/opening-repair-preview`
    );
    expect(preview.ok()).toBeTruthy();
    const body = (await preview.json()) as { eligible: boolean };
    expect(body.eligible).toBe(false);

    await gotoLibrary(page);
    await createNovelDraft(page, "__E2E_FAIL_REVIEW__ 开篇修复。", "E2E修复书");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.locator(".status-failed").first()).toBeVisible({ timeout: 60_000 });
    await openFailedChapterMenu(page);
    await page.getByRole("button", { name: "检查并修复开篇数据" }).click();
    await expect(page.getByRole("dialog", { name: "检查并修复开篇数据" })).toBeVisible();
    await page.getByLabel("我已阅读影响范围，确认修复开篇数据").check();
    await page.getByRole("button", { name: "确认修复" }).click();
    await expect(page.getByRole("button", { name: "回退开篇修复" })).toBeVisible({ timeout: 30_000 });
    await page.reload();
    await expect(page.getByRole("button", { name: "回退开篇修复" })).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "回退开篇修复" }).click();
    await expect(page.getByRole("button", { name: "回退开篇修复" })).toHaveCount(0);
    await expect(page.locator(".status-failed").first()).toBeVisible();

    await gotoLibrary(page);
    await createNovelDraft(page, "__E2E_FAIL_REVIEW__ 对话框重置。", "E2E对话框书");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.locator(".status-failed").first()).toBeVisible({ timeout: 60_000 });
    await openFailedChapterMenu(page);
    await page.getByRole("button", { name: "检查并修复开篇数据" }).click();
    const dialog = page.getByRole("dialog", { name: "检查并修复开篇数据" });
    await expect(dialog).toBeVisible();
    await page.getByLabel("我已阅读影响范围，确认修复开篇数据").check();
    await page.getByRole("button", { name: "取消" }).click();
    await openFailedChapterMenu(page);
    await page.getByRole("button", { name: "检查并修复开篇数据" }).click();
    await expect(page.getByRole("button", { name: "确认修复" })).toBeDisabled();
  });
});

test.describe("桌面助手折叠", () => {
  test("宽屏关闭助手后收起右栏，再打开可恢复", async ({ page }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "E2E 助手折叠。", "E2E折叠书");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.getByRole("link", { name: /异常征兆/ }).first()).toBeVisible({
      timeout: 60_000,
    });
    await page.getByRole("link", { name: "作品阅读" }).click();
    await expect(page.locator("#readerView")).toBeVisible();
    await page.setViewportSize({ width: 1440, height: 900 });
    const reader = page.locator("#readerView");
    await expect(reader).not.toHaveClass(/assistant-closed/);
    await page.getByRole("button", { name: "关闭助手" }).click();
    await expect(reader).toHaveClass(/assistant-closed/);
    await page.getByRole("button", { name: "打开 AI 助手" }).click();
    await expect(reader).not.toHaveClass(/assistant-closed/);
  });
});
