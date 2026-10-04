import { expect, type APIRequestContext, type Page } from "@playwright/test";

type ProjectListPayload = {
  items?: Array<{ id: string; title: string }>;
};

export async function resetE2EData(request: APIRequestContext) {
  const response = await request.get("/api/novels");
  expect(response.ok(), `读取 E2E 书架失败：${response.status()}`).toBe(true);
  const payload = (await response.json()) as ProjectListPayload;
  for (const project of payload.items || []) {
    const deletion = await request.delete(`/api/novels/${encodeURIComponent(project.id)}`, {
      data: { confirmation_title: project.title },
    });
    expect(deletion.ok(), `清理 E2E 小说 ${project.id} 失败：${deletion.status()}`).toBe(true);
  }
}

export async function gotoLibrary(page: Page) {
  await page.goto("/novels");
  await expect(page.getByRole("heading", { name: "我的小说" })).toBeVisible();
  await expect(page.getByRole("button", { name: "新建小说" })).toBeVisible();
}

export async function createNovelDraft(page: Page, idea: string, title?: string) {
  await page.getByRole("button", { name: "新建小说" }).click();
  await expect(page).toHaveURL(/\/novels\/new/);
  await page.locator("#idea").fill(idea);
  if (title) await page.locator("#preferred_title").fill(title);
  // genre may auto-select after catalog load
  const genre = page.locator("#genre");
  await expect(genre).toBeVisible();
  await page.waitForFunction(() => {
    const el = document.querySelector<HTMLSelectElement>("#genre");
    return Boolean(el && (el.value || el.options.length > 1));
  });
  if (!(await genre.inputValue())) {
    await genre.selectOption({ index: 1 });
  }
  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "生成创作方案" }).click();
  await expect(page).toHaveURL(/\/novels\/[^/]+\/workbench/);
  await expect(page.getByRole("button", { name: "确认创作方案" })).toBeVisible({ timeout: 30_000 });
}

export async function confirmPlan(page: Page) {
  await page.getByRole("button", { name: "确认创作方案" }).click();
  await expect(page.getByRole("button", { name: "生成下一章" })).toBeVisible({ timeout: 30_000 });
}

export async function openFailedChapterMenu(page: Page) {
  const details = page.locator("details.chapter-action-menu").first();
  await expect(details).toBeVisible();
  const opened = await details.evaluate((element) => (element as HTMLDetailsElement).open);
  if (!opened) {
    await details.locator("summary").click();
  }
  await expect
    .poll(async () => details.evaluate((element) => (element as HTMLDetailsElement).open))
    .toBe(true);
}

export async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  expect(overflow).toBe(true);
}

export async function assertNoNestedHorizontalOverflow(page: Page, selectors: string[]) {
  const offenders = await page.evaluate((targets) => {
    return targets.flatMap((selector) =>
      Array.from(document.querySelectorAll<HTMLElement>(selector))
        .filter((element) => element.getClientRects().length > 0)
        .filter((element) => element.scrollWidth > element.clientWidth + 1)
        .map((element) => ({
          selector,
          className: element.className,
          clientWidth: element.clientWidth,
          scrollWidth: element.scrollWidth,
        }))
    );
  }, selectors);
  expect(offenders).toEqual([]);
}

export async function assertMinimumTouchTargets(page: Page, selector: string, minimum = 44) {
  const targets = await page.locator(selector).evaluateAll((elements) =>
    elements
      .filter((element) => element.getClientRects().length > 0)
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          label:
            element.getAttribute("aria-label") ||
            element.textContent?.trim() ||
            element.tagName.toLowerCase(),
          width: rect.width,
          height: rect.height,
        };
      })
  );
  expect(targets.length).toBeGreaterThan(0);
  for (const target of targets) {
    expect(target.width, `${target.label} 的触控宽度不足 ${minimum}px`).toBeGreaterThanOrEqual(minimum);
    expect(target.height, `${target.label} 的触控高度不足 ${minimum}px`).toBeGreaterThanOrEqual(minimum);
  }
}

export async function assertTextareasNonResizable(page: Page) {
  const ok = await page.evaluate(() =>
    Array.from(document.querySelectorAll("textarea")).every(
      (el) => getComputedStyle(el).resize === "none"
    )
  );
  expect(ok).toBe(true);
}
