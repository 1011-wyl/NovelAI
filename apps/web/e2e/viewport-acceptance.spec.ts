import { test, expect } from "@playwright/test";
import {
  assertMinimumTouchTargets,
  assertNoNestedHorizontalOverflow,
  assertNoHorizontalOverflow,
  assertTextareasNonResizable,
  confirmPlan,
  createNovelDraft,
  gotoLibrary,
  resetE2EData,
} from "./helpers/app";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { mkdirSync } from "node:fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const artifactRoot = path.resolve(__dirname, "../../../artifacts/frontend-regression/e2e-run");

const viewports = [
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "desktop-1024", width: 1024, height: 768 },
  { name: "tablet-768", width: 768, height: 1024 },
  { name: "mobile-390", width: 390, height: 844 },
] as const;

test.beforeEach(async ({ request }) => resetE2EData(request));
test.afterEach(async ({ request }) => resetE2EData(request));

test.describe("多视口验收截图", () => {
  test.beforeAll(() => {
    for (const vp of viewports) {
      mkdirSync(path.join(artifactRoot, vp.name), { recursive: true });
    }
  });

  for (const vp of viewports) {
    test(`${vp.name} 关键页面验收`, async ({ page }) => {
      test.setTimeout(180_000);
      await page.setViewportSize({ width: vp.width, height: vp.height });
      const dir = path.join(artifactRoot, vp.name);
      const isMobile = vp.width <= 767;

      await gotoLibrary(page);
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: path.join(dir, "library-empty.png"), fullPage: true });
      if (isMobile) {
        await page.getByRole("button", { name: "打开导航" }).click();
        const sidebar = page.locator("aside.sidebar");
        await expect(sidebar).toHaveClass(/is-open/);
        await expect
          .poll(async () => {
            const box = await sidebar.boundingBox();
            return box ? { x: Math.round(box.x), width: Math.round(box.width) } : null;
          })
          .toEqual({ x: 0, width: 240 });
        expect(
          await page.evaluate(
            () => document.elementFromPoint(24, 120)?.closest("aside.sidebar") !== null
          )
        ).toBe(true);
        await page.screenshot({ path: path.join(dir, "library-mobile-drawer.png") });
        await page.getByRole("button", { name: "关闭导航" }).click();
      } else {
        await page.getByRole("button", { name: "收起导航" }).click();
        await page.screenshot({ path: path.join(dir, "library-sidebar-collapsed.png"), fullPage: true });
        await page.getByRole("button", { name: "展开导航" }).click();
      }

      await createNovelDraft(page, `视口验收 ${vp.name}`, `视口书-${vp.name}`);
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: path.join(dir, "workbench-unconfirmed.png"), fullPage: true });

      await confirmPlan(page);
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: path.join(dir, "workbench-confirmed.png"), fullPage: true });

      const projectId = page.url().match(/\/novels\/([^/]+)\/workbench/)?.[1];
      expect(projectId).toBeTruthy();

      await page.goto("/novels");
      await expect(page.getByText(`视口书-${vp.name}`)).toBeVisible();
      await page.getByRole("button", { name: "更多操作" }).first().click();
      await expect(page.getByRole("menu")).toBeVisible();
      await page.screenshot({ path: path.join(dir, "library-action-menu.png") });
      await page.getByRole("menuitem", { name: "修改书名" }).click();
      await expect(page.getByRole("dialog", { name: "修改书名" })).toBeVisible();
      await page.screenshot({ path: path.join(dir, "rename-dialog.png") });
      await page.keyboard.press("Escape");

      if (isMobile) {
        await page.goto(`/novels/${projectId}/reader`);
      } else {
        await page.getByRole("link", { name: "作品阅读" }).click();
      }
      await expect(page).toHaveURL(/\/reader/);
      await expect(page.locator(".workspace-resizer")).toHaveCount(0);
      await expect(page.locator(".writing-workspace")).toBeVisible();
      await assertTextareasNonResizable(page);
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: path.join(dir, "reader.png"), fullPage: true });

      if (isMobile) {
        await page.goto(`/novels/${projectId}/memory`);
      } else {
        await page.getByRole("link", { name: "长期记忆" }).click();
      }
      await expect(page).toHaveURL(/\/memory/);
      await expect(page.locator(".memory-page")).toBeVisible();
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: path.join(dir, "memory.png"), fullPage: true });

      await page.goto("/analytics");
      await expect(page.locator("#writingPanel")).toBeVisible();
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: path.join(dir, "analytics-writing.png"), fullPage: true });
      await page.getByRole("tab", { name: "调用记录" }).click();
      await expect(page.getByTestId("records-table-card")).toBeVisible();
      await assertNoHorizontalOverflow(page);
      await assertNoNestedHorizontalOverflow(page, [
        ".records-filter-row",
        ".records-table-wrap",
        ".records-pagination",
      ]);
      await assertMinimumTouchTargets(
        page,
        ".analytics-tab, .records-filter-row select, .records-filter-row input, .records-filter-row button"
      );
      await page.screenshot({ path: path.join(dir, "analytics-records.png"), fullPage: true });

      await page.goto("/settings");
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: path.join(dir, "settings.png"), fullPage: true });

      await page.goto("/novels/new");
      await expect(page.getByText("第 1 步，共 3 步")).toBeVisible();
      await page.screenshot({ path: path.join(dir, "create-step1.png"), fullPage: true });
      await page.locator("#idea").fill("步骤截图");
      const genre = page.locator("#genre");
      await page.waitForFunction(() => {
        const el = document.querySelector<HTMLSelectElement>("#genre");
        return Boolean(el && el.options.length > 1);
      });
      if (!(await genre.inputValue())) await genre.selectOption({ index: 1 });
      await page.getByRole("button", { name: "下一步" }).click();
      await page.screenshot({ path: path.join(dir, "create-step2.png"), fullPage: true });
      await page.getByRole("button", { name: "下一步" }).click();
      await page.screenshot({ path: path.join(dir, "create-step3.png"), fullPage: true });
    });
  }
});
