import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";
import { test, expect } from "@playwright/test";
import { gotoLibrary, resetE2EData } from "./helpers/app";

type MockHit = { model?: string; body: string };

function startMockLlm() {
  const hits: MockHit[] = [];
  const server = createServer((req: IncomingMessage, res: ServerResponse) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk) => chunks.push(chunk as Buffer));
    req.on("end", () => {
      const body = Buffer.concat(chunks).toString("utf8");
      let model: string | undefined;
      try {
        model = JSON.parse(body).model;
      } catch {
        model = undefined;
      }
      hits.push({ model, body });
      res.writeHead(200, { "content-type": "application/json" });
      res.end(
        JSON.stringify({
          choices: [
            {
              finish_reason: "stop",
              message: { role: "assistant", content: "ok" },
            },
          ],
          usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
        })
      );
    });
  });
  return new Promise<{ url: string; hits: MockHit[]; close: () => Promise<void> }>((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address() as AddressInfo;
      resolve({
        url: `http://127.0.0.1:${port}/v1`,
        hits,
        close: () => new Promise((done) => server.close(() => done())),
      });
    });
  });
}

const FAKE_KEY = "test-llm-key-e2e";

test.beforeEach(async ({ request }) => {
  await resetE2EData(request);
  await request.delete("/api/settings/llm", { data: {} });
});

test.afterEach(async ({ request }) => {
  await request.delete("/api/settings/llm", { data: {} });
});

test.describe("大模型配置", () => {
  test("卡片可打开配置并保存启用", async ({ page }) => {
    await page.route("**/api/settings/llm/test", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          code: "CONNECTION_OK",
          message: "连接成功",
          latency_ms: 11,
          tested_at: new Date().toISOString(),
        }),
      });
    });
    await page.goto("/settings");
    const card = page.getByRole("button", { name: /配置大模型/ });
    await expect(card).toBeVisible();
    await card.press("Enter");
    const dialog = page.getByRole("dialog", { name: "大模型配置" });
    await expect(dialog).toBeVisible();
    await dialog.locator("select").selectOption("dashscope");
    await dialog.getByText("API Key", { exact: true }).locator("..").locator("input").fill(FAKE_KEY);
    await dialog.getByRole("button", { name: "测试连接" }).click();
    await expect(dialog.getByText("连接成功")).toBeVisible();
    await dialog.getByRole("button", { name: "保存并启用" }).click();
    await expect(card).toContainText("已启用");
    await expect(card).toContainText("qwen-plus");
    const html = await page.content();
    expect(html).not.toContain(FAKE_KEY);
  });

  test("编辑不填 Key 会保留旧密钥，错误 Key 不会覆盖", async ({ page, request }) => {
    await page.route("**/api/settings/llm/test", async (route) => {
      const raw = route.request().postDataJSON() as { api_key?: string };
      if (raw.api_key && raw.api_key !== FAKE_KEY) {
        await route.fulfill({
          status: 502,
          contentType: "application/json",
          body: JSON.stringify({ error: "INVALID_API_KEY", message: "API Key 无效或已失效" }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          code: "CONNECTION_OK",
          message: "连接成功",
          latency_ms: 9,
          tested_at: new Date().toISOString(),
        }),
      });
    });
    await request.put("/api/settings/llm", {
      data: {
        provider: "dashscope",
        base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
        model: "qwen-plus",
        api_key: FAKE_KEY,
        enabled: true,
        timeout_seconds: 120,
        max_retries: 2,
      },
    });
    await page.goto("/settings");
    await page.getByRole("button", { name: /配置大模型/ }).click();
    const dialog = page.getByRole("dialog", { name: "大模型配置" });
    await expect(dialog.getByText(/已保存密钥/)).toBeVisible();
    await dialog.getByRole("button", { name: "保存并启用" }).click();
    const kept = await request.get("/api/settings/llm");
    const keptJson = await kept.json();
    expect(keptJson.has_api_key).toBe(true);
    expect(JSON.stringify(keptJson)).not.toContain(FAKE_KEY);

    await page.getByRole("button", { name: /配置大模型/ }).click();
    await dialog.getByText("API Key", { exact: true }).locator("..").locator("input").fill("wrong-key");
    await dialog.getByRole("button", { name: "测试连接" }).click();
    await expect(dialog.getByText("API Key 无效或已失效")).toBeVisible();
    const after = await (await request.get("/api/settings/llm")).json();
    expect(after.api_key_mask).toBe(keptJson.api_key_mask);
  });

  test("停用后不再回退到环境或离线模型", async ({ page, request }) => {
    await request.put("/api/settings/llm", {
      data: {
        provider: "deepseek",
        base_url: "https://api.deepseek.com",
        model: "deepseek-chat",
        api_key: FAKE_KEY,
        enabled: true,
      },
    });
    await page.goto("/settings");
    const dialog = page.getByRole("dialog", { name: "大模型配置" });
    page.once("dialog", (nativeDialog) => nativeDialog.accept());
    await page.getByRole("button", { name: /配置大模型/ }).click();
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "停用" }).click();
    await expect(page.getByRole("button", { name: /配置大模型/ })).toContainText("已停用");
    const view = await (await request.get("/api/settings/llm")).json();
    expect(view.card_status).toBe("disabled");
    expect(view.enabled).toBe(false);
    expect(view.source).toBe("saved");
  });

  test("清除配置后回退", async ({ page, request }) => {
    await request.put("/api/settings/llm", {
      data: {
        provider: "deepseek",
        base_url: "https://api.deepseek.com",
        model: "deepseek-chat",
        api_key: FAKE_KEY,
        enabled: true,
      },
    });
    await page.goto("/settings");
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: /配置大模型/ }).click();
    await page.getByRole("dialog", { name: "大模型配置" }).getByRole("button", { name: "清除配置" }).click();
    await expect(page.getByRole("button", { name: /配置大模型/ })).toContainText(/离线演示|未配置/);
  });

  test("保存后生成入口会使用新的 provider/model", async ({ page, request }) => {
    const mock = await startMockLlm();
    try {
      await request.put("/api/settings/llm", {
        data: {
          provider: "openai_compatible",
          base_url: mock.url,
          model: "e2e-mock-model",
          api_key: FAKE_KEY,
          enabled: true,
          timeout_seconds: 10,
          max_retries: 0,
        },
      });
      await gotoLibrary(page);
      const create = request.post("/api/novels", {
        data: {
          idea: "E2E 验证大模型配置会进入生成入口。",
          genre: "末世",
          audience_channel: "男频",
          preferred_title: "E2E模型配置生成",
        },
      });
      await expect
        .poll(() => mock.hits.some((hit) => hit.model === "e2e-mock-model"), { timeout: 30_000 })
        .toBe(true);
      await create.catch(() => undefined);
      expect(await page.content()).not.toContain(FAKE_KEY);
      expect(mock.hits.some((hit) => hit.body.includes(FAKE_KEY))).toBe(false);
    } finally {
      await mock.close();
    }
  });
});
