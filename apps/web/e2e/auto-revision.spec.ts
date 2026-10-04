import { test, expect } from "@playwright/test";
import {
  confirmPlan,
  createNovelDraft,
  gotoLibrary,
  resetE2EData,
} from "./helpers/app";

test.beforeEach(async ({ request }) => resetE2EData(request));
test.afterEach(async ({ request }) => resetE2EData(request));

test.describe("自动修订闭环", () => {
  test("首稿失败后自动修订一次并通过", async ({ page, request }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "__E2E_AUTO_REVISE_ONCE__ 自动修订一次。", "E2E修订一次");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.getByRole("link", { name: /异常征兆|第1章/ }).first()).toBeVisible({
      timeout: 90_000,
    });
    await expect(page.locator(".status-failed")).toHaveCount(0);
    const list = await request.get("/api/novels");
    const payload = (await list.json()) as { items: Array<{ id: string; title: string }> };
    const project = payload.items.find((item) => item.title === "E2E修订一次");
    expect(project).toBeTruthy();
    const detail = await request.get(`/api/novels/${encodeURIComponent(project!.id)}`);
    const body = (await detail.json()) as {
      chapters: Array<{ status: string; number: number }>;
      latest_events: Array<{ node: string; message: string }>;
    };
    expect(body.chapters[0]?.status).toBe("READY");
    expect(body.latest_events.some((event) => /质量检查|自动修订|ParallelReview/.test(event.node + event.message))).toBe(
      true
    );
  });

  test("第二次修订才通过", async ({ page, request }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "__E2E_AUTO_REVISE_TWICE__ 自动修订两次。", "E2E修订两次");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.getByRole("link", { name: /异常征兆|第1章/ }).first()).toBeVisible({
      timeout: 120_000,
    });
    const list = await request.get("/api/novels");
    const payload = (await list.json()) as { items: Array<{ id: string; title: string }> };
    const project = payload.items.find((item) => item.title === "E2E修订两次");
    const detail = await request.get(`/api/novels/${encodeURIComponent(project!.id)}`);
    const body = (await detail.json()) as { chapters: Array<{ status: string }> };
    expect(body.chapters[0]?.status).toBe("READY");
  });

  test("自动修订耗尽后才出现 FAILED，并显示尝试信息", async ({ page, request }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "__E2E_AUTO_REVISE_EXHAUST__ 耗尽修订。", "E2E修订耗尽");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.locator(".status-failed").first()).toBeVisible({ timeout: 120_000 });
    await expect(page.getByText(/质量分|质量待修改|已自动修订/).first()).toBeVisible();
    const list = await request.get("/api/novels");
    const payload = (await list.json()) as { items: Array<{ id: string; title: string }> };
    const project = payload.items.find((item) => item.title === "E2E修订耗尽");
    const detail = await request.get(`/api/novels/${encodeURIComponent(project!.id)}`);
    const body = (await detail.json()) as {
      chapters: Array<{ status: string }>;
      chapter_failures: Array<{ revision_count?: number; score_trace?: number[] }>;
    };
    expect(body.chapters[0]?.status).toBe("FAILED");
    expect((body.chapter_failures[0]?.revision_count || 0) >= 1).toBe(true);
  });

  test("结构性失败走 replan", async ({ page, request }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "__E2E_AUTO_REPLAN__ 结构重规划。", "E2E结构重规划");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.getByRole("link", { name: /异常征兆|第1章/ }).first()).toBeVisible({
      timeout: 120_000,
    });
    const list = await request.get("/api/novels");
    const payload = (await list.json()) as { items: Array<{ id: string; title: string }> };
    const project = payload.items.find((item) => item.title === "E2E结构重规划");
    const detail = await request.get(`/api/novels/${encodeURIComponent(project!.id)}`);
    const body = (await detail.json()) as {
      chapters: Array<{ status: string; content?: string }>;
      latest_events: Array<{ node: string; message: string }>;
    };
    expect(body.chapters[0]?.status).toBe("READY");
    const eventBlob = body.latest_events
      .map((event) => `${event.node} ${event.message}`)
      .join("\n");
    expect(/PlanRegenerate|重新规划|结构/.test(eventBlob)).toBe(true);
  });

  test("分数未过线时不可接受，硬阻断返回 409", async ({ page, request }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "__E2E_SOFT_FAIL__ 软问题不可绕过。", "E2E软不可接受");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.locator(".status-failed").first()).toBeVisible({ timeout: 120_000 });
    // 综合分 ≤60 时不得用“接受当前版本”绕过唯一通过线。
    await expect(page.getByRole("button", { name: "接受当前版本并继续" })).toHaveCount(0);

    await gotoLibrary(page);
    await createNovelDraft(page, "__E2E_HARD_FAIL__ 硬阻断。", "E2E硬阻断");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.locator(".status-failed").first()).toBeVisible({ timeout: 120_000 });
    await expect(page.getByRole("button", { name: "接受当前版本并继续" })).toHaveCount(0);
    const list = await request.get("/api/novels");
    const payload = (await list.json()) as { items: Array<{ id: string; title: string }> };
    const project = payload.items.find((item) => item.title === "E2E硬阻断");
    const workspace = await request.get(
      `/api/novels/${encodeURIComponent(project!.id)}/chapters/1/workspace`
    );
    const ws = (await workspace.json()) as {
      chapter: { version: number; title: string; content?: string };
      draft: { content_hash: string } | null;
      capabilities: { accept_with_warnings: boolean };
    };
    expect(ws.capabilities.accept_with_warnings).toBe(false);
    const accept = await request.post(
      `/api/novels/${encodeURIComponent(project!.id)}/chapters/1/accept-with-warnings`,
      {
        data: {
          confirm: true,
          base_version: ws.chapter.version,
          expected_draft_hash: ws.draft?.content_hash || "x".repeat(64),
        },
      }
    );
    expect(accept.status()).toBe(409);
    const errorBody = (await accept.json()) as { error?: string };
    expect(errorBody.error).toBe("QUALITY_OVERRIDE_NOT_ALLOWED");
  });

  test("刷新后失败报告与 capability 保持一致", async ({ page, request }) => {
    await gotoLibrary(page);
    await createNovelDraft(page, "__E2E_SOFT_FAIL__ 刷新保持。", "E2E刷新软失败");
    await confirmPlan(page);
    await page.getByRole("button", { name: "生成下一章" }).click();
    await expect(page.locator(".status-failed").first()).toBeVisible({ timeout: 120_000 });
    await expect(page.getByRole("button", { name: "接受当前版本并继续" })).toHaveCount(0);
    await page.reload();
    await expect(page.locator(".status-failed").first()).toBeVisible({ timeout: 30_000 });
    const list = await request.get("/api/novels");
    const payload = (await list.json()) as { items: Array<{ id: string; title: string }> };
    const project = payload.items.find((item) => item.title === "E2E刷新软失败");
    const detail = await request.get(`/api/novels/${encodeURIComponent(project!.id)}`);
    const body = (await detail.json()) as {
      chapter_failures: Array<{
        can_accept_with_warnings?: boolean;
        score?: number;
        quality_status?: string;
        selected_score?: number;
      }>;
    };
    expect(body.chapter_failures[0]?.can_accept_with_warnings).toBe(false);
    expect((body.chapter_failures[0]?.score || 0) <= 60).toBe(true);
  });
});
