<script setup lang="ts">
import { onMounted, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import { useLlmSettings } from "../composables/useLlmSettings";
import LlmAdvancedSettings from "./LlmAdvancedSettings.vue";
import LlmConnectionStatus from "./LlmConnectionStatus.vue";
import LlmProviderFields from "./LlmProviderFields.vue";
import LlmSecretField from "./LlmSecretField.vue";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{
  close: [];
  saved: [action?: string];
}>();

const llm = useLlmSettings();

watch(
  () => props.open,
  (open) => {
    if (open) void llm.load();
  }
);

onMounted(() => {
  if (props.open) void llm.load();
});

function requestClose() {
  if (llm.dirty.value && !window.confirm("有未保存的修改，确定关闭吗？")) return;
  emit("close");
}

async function onSave() {
  if (await llm.saveAndEnable()) emit("saved");
}

async function onDisable() {
  if (!window.confirm("停用后新任务将不会调用大模型（包括环境变量里的配置），直到再次保存并启用。")) return;
  if (await llm.disable()) emit("saved", "disable");
}

async function onClear() {
  if (!window.confirm("确定清除本机页面保存的大模型配置吗？环境变量里的配置仍会保留。")) return;
  if (await llm.clear()) emit("saved", "clear");
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="drawer-root">
      <button type="button" class="backdrop" aria-label="关闭大模型配置" @click="requestClose" />
      <aside
        class="panel"
        role="dialog"
        aria-modal="true"
        aria-label="大模型配置"
        tabindex="-1"
      >
        <header>
          <h2>大模型配置</h2>
          <button type="button" class="text-close" @click="requestClose">关闭</button>
        </header>
        <div class="body">
          <LlmProviderFields
            :provider="llm.form.provider"
            :base-url="llm.form.baseUrl"
            :model="llm.form.model"
            :disabled="llm.busy.value"
            @provider-change="(value) => llm.onProviderChange(value)"
            @update:base-url="(value) => { llm.form.baseUrl = value; llm.userEdited.baseUrl = true; llm.markDirty(); }"
            @update:model="(value) => { llm.form.model = value; llm.userEdited.model = true; llm.markDirty(); }"
          />
          <LlmSecretField
            v-model="llm.form.apiKey"
            :mask="llm.view.value.api_key_mask"
            :show="llm.showKey.value"
            :disabled="llm.busy.value"
            @update:show="(value) => { llm.showKey.value = value; }"
            @update:model-value="() => { llm.markDirty(); }"
          />
          <LlmConnectionStatus
            :result="llm.testResult.value"
            :error="llm.errorMessage.value"
            :last-tested-at="llm.view.value.last_tested_at"
            :pending="llm.dirty.value && llm.view.value.card_status === 'unverified'"
          />
          <LlmAdvancedSettings
            :timeout-seconds="llm.form.timeoutSeconds"
            :max-retries="llm.form.maxRetries"
            :open="llm.advancedOpen.value"
            :disabled="llm.busy.value"
            @update:open="(value) => { llm.advancedOpen.value = value; }"
            @update:timeout-seconds="(value) => { llm.form.timeoutSeconds = value; llm.markDirty(); }"
            @update:max-retries="(value) => { llm.form.maxRetries = value; llm.markDirty(); }"
          />
        </div>
        <footer>
          <div class="danger">
            <BaseButton :disabled="llm.busy.value" @click="onDisable">停用</BaseButton>
            <BaseButton variant="danger" :disabled="llm.busy.value" @click="onClear">清除配置</BaseButton>
          </div>
          <div class="actions">
            <BaseButton :disabled="llm.busy.value" @click="requestClose">取消</BaseButton>
            <BaseButton :disabled="llm.busy.value || llm.formState.value === 'testing'" :loading="llm.formState.value === 'testing'" @click="llm.testConnection">
              测试连接
            </BaseButton>
            <BaseButton variant="primary" :disabled="llm.busy.value || llm.formState.value === 'saving'" :loading="llm.formState.value === 'saving'" @click="onSave">
              保存并启用
            </BaseButton>
          </div>
          <p v-if="llm.formState.value === 'success'" data-testid="llm-save-success">已保存并启用</p>
        </footer>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.drawer-root {
  position: fixed;
  inset: 0;
  z-index: 1100;
}
.backdrop {
  position: absolute;
  inset: 0;
  border: 0;
  background: rgba(0, 0, 0, 0.35);
}
.panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(440px, 100%);
  background: var(--color-surface);
  border-left: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  max-width: 100%;
  overflow-x: hidden;
  overflow-y: auto;
}
header, footer {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-4);
  border-bottom: 1px solid var(--color-border);
}
footer {
  border-bottom: 0;
  border-top: 1px solid var(--color-border);
  flex-wrap: wrap;
}
.body {
  padding: var(--space-4);
  display: grid;
  gap: var(--space-6);
  flex: 1;
}
h2 { margin: 0; font-size: 1.1rem; }
.text-close, .actions, .danger { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.text-close {
  border: 0;
  background: transparent;
  min-height: var(--touch-min);
}
@media (max-width: 767px) {
  .panel { width: 100%; }
}
</style>
