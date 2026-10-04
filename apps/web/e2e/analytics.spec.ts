import { test, expect } from "@playwright/test";
import { gotoLibrary, resetE2EData } from "./helpers/app";

test.beforeEach(async ({ request }) => resetE2EData(request));
test.afterEach(async ({ request }) => resetE2EData(request));

test.describe("仪表盘 Vue 交互", () => {
  test("页签切换、筛选保留、空态与排序路径", async ({ page }) => {
    await gotoLibrary(page);
    await page.getByRole("link", { name: "仪表盘" }).click();
    await expect(page).toHaveURL(/\/analytics/);
    await expect(page.getByRole("heading", { name: "仪表盘" })).toBeVisible();

    const writingTab = page.getByRole("tab", { name: "写作" });
    const llmTab = page.getByRole("tab", { name: "LLM 统计" });
    const recordsTab = page.getByRole("tab", { name: "调用记录" });
    await expect(writingTab).toHaveAttribute("aria-selected", "true");

    await llmTab.click();
    await expect(llmTab).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText("LLM 调用次数")).toBeVisible();

    await recordsTab.click();
    await expect(recordsTab).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("records-table-card")).toBeVisible();
    await expect(page.getByText(/第 .+ 条，共 .+ 条/)).toBeVisible();

    await page.getByTestId("records-search").fill("no-such-model-xyz");
    await expect(page.getByTestId("analytics-empty")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("records-search")).toHaveValue("no-such-model-xyz");

    await page.getByRole("button", { name: "按时间排序" }).click();
    await expect(page.getByTestId("records-search")).toHaveValue("no-such-model-xyz");

    await writingTab.click();
    await expect(page.getByTestId("writing-filter-reset")).toBeVisible();
    await page.getByTestId("writing-start-date").fill("2020-01-01");
    await page.getByTestId("writing-end-date").fill("2020-01-31");
    await expect(page.getByTestId("writing-start-date")).toHaveValue("2020-01-01");
  });

  test("错误态可重试且不丢失筛选（拦截 API）", async ({ page }) => {
    await page.route("**/api/dashboard/llm-api/records*", async (route) => {
      if (route.request().url().includes("fail-once")) {
        await route.fulfill({ status: 500, body: JSON.stringify({ message: "模拟失败" }) });
        return;
      }
      await route.continue();
    });

    await page.goto("/analytics");
    await page.getByRole("tab", { name: "调用记录" }).click();
    await page.getByTestId("records-search").fill("fail-once");
    await expect(page.getByTestId("analytics-error")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("records-search")).toHaveValue("fail-once");

    await page.unroute("**/api/dashboard/llm-api/records*");
    await page.getByTestId("analytics-retry").click();
    await expect(page.getByTestId("analytics-error")).toHaveCount(0, { timeout: 10_000 });
  });
});
