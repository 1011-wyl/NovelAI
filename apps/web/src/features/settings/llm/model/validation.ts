import type { LlmProvider } from "./contracts";

const MODEL_RE = /^[A-Za-z0-9._:/-]{1,128}$/;

export function validateLlmForm(input: {
  provider: LlmProvider;
  baseUrl: string;
  model: string;
  timeoutSeconds: number;
  maxRetries: number;
}): string | null {
  if (!input.provider) return "请选择供应商";
  try {
    const parsed = new URL(input.baseUrl);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return "API 地址必须是 http 或 https";
    }
  } catch {
    return "API 地址格式不正确";
  }
  if (!MODEL_RE.test(input.model.trim())) return "请填写有效的模型 ID";
  if (input.timeoutSeconds < 10 || input.timeoutSeconds > 300) return "超时需在 10～300 秒";
  if (input.maxRetries < 0 || input.maxRetries > 5) return "重试次数需在 0～5";
  return null;
}
