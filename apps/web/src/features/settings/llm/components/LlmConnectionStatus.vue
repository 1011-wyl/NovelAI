<script setup lang="ts">
import type { LlmTestResult } from "../model/contracts";

defineProps<{
  result: LlmTestResult | null;
  error: string | null;
  lastTestedAt: string | null;
  pending?: boolean;
}>();
</script>

<template>
  <section class="block">
    <h3>连接状态</h3>
    <p v-if="error" class="err" role="alert">{{ error }}</p>
    <p v-else-if="result?.ok" class="ok">{{ result.message }}（{{ result.latency_ms }} ms）</p>
    <p v-else-if="pending" class="muted">配置已更改，保存前请重新测试连接。</p>
    <p v-else class="muted">{{ lastTestedAt ? `上次测试：${lastTestedAt}` : "尚未测试连接" }}</p>
  </section>
</template>

<style scoped>
.block { display: grid; gap: var(--space-2); }
.ok { color: var(--color-success); margin: 0; }
.err { color: var(--color-danger); margin: 0; }
.muted { color: var(--color-text-muted); margin: 0; }
</style>
