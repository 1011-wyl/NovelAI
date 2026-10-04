import type { LlmPreset, LlmProvider } from "./contracts";

export const PROVIDER_OPTIONS: Array<{ value: LlmProvider; label: string }> = [
  { value: "deepseek", label: "DeepSeek" },
  { value: "dashscope", label: "阿里云百炼 DashScope" },
  { value: "openai", label: "OpenAI" },
  { value: "openai_compatible", label: "自定义 OpenAI 兼容接口" },
];

export function presetFor(presets: LlmPreset[], provider: LlmProvider): LlmPreset | undefined {
  return presets.find((item) => item.provider === provider);
}
