import { spawn } from "node:child_process";
import { once } from "node:events";
import { existsSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "../..");
const repoRoot = path.resolve(webRoot, "../..");
const distIndex = path.join(webRoot, "dist", "index.html");

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function removeTestDirectory(dataDir) {
  const resolvedTemp = `${path.resolve(tmpdir())}${path.sep}`;
  const resolvedData = path.resolve(dataDir);
  if (!resolvedData.startsWith(resolvedTemp)) {
    throw new Error(`拒绝清理非临时 E2E 目录: ${resolvedData}`);
  }
  rmSync(resolvedData, { recursive: true, force: true });
}

async function waitForServer(child, healthUrl) {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(`E2E 服务提前退出，退出码 ${child.exitCode}`);
    }
    try {
      const response = await fetch(healthUrl);
      if (response.ok) return;
    } catch {
      // Server is still starting.
    }
    await delay(200);
  }
  throw new Error(`等待 E2E 服务超时: ${healthUrl}`);
}

async function stopServer(child) {
  if (child.exitCode !== null) return;
  child.kill("SIGTERM");
  const stopped = await Promise.race([
    once(child, "exit").then(() => true),
    delay(5_000).then(() => false),
  ]);
  if (stopped || child.exitCode !== null) return;
  child.kill("SIGKILL");
  await once(child, "exit");
}

export default async function globalSetup() {
  if (!existsSync(distIndex)) {
    throw new Error("apps/web/dist/index.html missing; run npm run build before e2e");
  }

  const runId = `novel-agent-e2e-${Date.now()}-${process.pid}`;
  const dataDir = mkdtempSync(path.join(tmpdir(), `${runId}-`));
  const database = path.join(dataDir, "e2e.db");
  const port = process.env.NOVEL_AGENT_E2E_PORT || "18000";
  const host = "127.0.0.1";
  const healthUrl = `http://${host}:${port}/api/health`;

  mkdirSync(dataDir, { recursive: true });
  writeFileSync(path.join(dataDir, "README.txt"), `E2E isolated data for ${runId}\n`, "utf8");

  console.log(`正在使用测试数据目录: ${dataDir}`);
  console.log(`E2E database: ${database}`);
  console.log(`E2E server: http://${host}:${port}`);

  const child = spawn(process.env.PYTHON || "python", ["-m", "novel_agent", "serve"], {
    cwd: repoRoot,
    env: {
      ...process.env,
      NOVEL_AGENT_SECRET_STORE: "memory",
      NOVEL_AGENT_HOST: host,
      NOVEL_AGENT_PORT: String(port),
      NOVEL_AGENT_DATABASE: database,
      NOVEL_AGENT_MODE: "offline",
      LLM_PROVIDER: "disabled",
      LLM_API_KEY: "",
      DEEPSEEK_API_KEY: "",
      DASHSCOPE_API_KEY: "",
      MAX_REVISION_ATTEMPTS: process.env.MAX_REVISION_ATTEMPTS || "2",
    },
    stdio: "inherit",
    shell: false,
    windowsHide: true,
  });

  try {
    await waitForServer(child, healthUrl);
  } catch (error) {
    await stopServer(child);
    removeTestDirectory(dataDir);
    throw error;
  }

  return async () => {
    await stopServer(child);
    removeTestDirectory(dataDir);
  };
}
