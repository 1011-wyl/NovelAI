<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import AppShell from "@/layouts/AppShell.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseField from "@/components/base/BaseField.vue";
import LoadingBlock from "@/components/base/LoadingBlock.vue";
import ErrorSummary from "@/components/base/ErrorSummary.vue";
import { getSettings, saveSettings } from "../api/settings.api";
import { useAppStore } from "@/stores/app.store";
import { toUserError } from "@/stores/projects.store";
import LlmSettingsDrawer from "../llm/components/LlmSettingsDrawer.vue";

type RuntimeItem = {
  enabled?: boolean;
  configured?: boolean;
  provider?: string;
  provider_label?: string;
  model?: string;
  card_status?: string;
  source?: string;
};

const app = useAppStore();
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const runtime = ref<Record<string, RuntimeItem> | null>(null);
const llmOpen = ref(false);
const llmCardBusy = ref(false);

const form = reactive({
  daily_chapters: 2,
  reserve_target: 5,
  budget_limit: 0,
  debug_mode: false,
});

const RUNTIME_ROWS: Array<[string, string]> = [
  ["大模型 (LLM)", "llm"],
  ["联网搜索", "search"],
  ["向量嵌入", "embedding"],
  ["发布适配", "publisher"],
  ["Story Skills", "story_skills"],
  ["OH Story 写作技能", "oh_story"],
];

function runtimeStatus(key: string, item?: RuntimeItem) {
  if (key === "llm") {
    switch (item?.card_status) {
      case "enabled":
        return { text: "已启用", tone: "ok" };
      case "unverified":
        return { text: "待验证", tone: "warn" };
      case "needs_attention":
        return { text: "需要处理", tone: "warn" };
      case "disabled":
        return { text: "已停用", tone: "off" };
      default:
        return { text: "未配置", tone: "off" };
    }
  }
  if (!item) return { text: "未配置", tone: "off" };
  if (item.enabled) return { text: "已启用", tone: "ok" };
  if (item.configured) return { text: "已配置未启用", tone: "warn" };
  return { text: "未配置", tone: "off" };
}

function llmSubtitle(item?: RuntimeItem) {
  if (!item) return "点击配置模型服务";
  if (item.card_status === "unconfigured" || (!item.provider && !item.model)) return "点击配置模型服务";
  const label = item.provider_label || item.provider;
  return [label, item.model].filter(Boolean).join(" · ");
}

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const payload = await getSettings();
    runtime.value = (payload.runtime as Record<string, RuntimeItem>) || null;
    const prefs = payload.preferences || {};
    form.daily_chapters = Number(prefs.daily_chapters ?? 2);
    form.reserve_target = Number(prefs.reserve_target ?? 5);
    form.budget_limit = Number(prefs.budget_limit ?? 0);
    form.debug_mode = Boolean(prefs.debug_mode);
  } catch (err) {
    error.value = toUserError(err, "加载设置失败");
  } finally {
    loading.value = false;
  }
}

async function onSubmit(event: Event) {
  event.preventDefault();
  saving.value = true;
  try {
    const payload = await saveSettings({
      daily_chapters: Number(form.daily_chapters),
      reserve_target: Number(form.reserve_target),
      budget_limit: Number(form.budget_limit),
      debug_mode: Boolean(form.debug_mode),
    });
    runtime.value = (payload.runtime as Record<string, RuntimeItem>) || runtime.value;
    app.flash("本地偏好已保存。");
  } catch (err) {
    app.flash(toUserError(err, "保存失败"), true);
  } finally {
    saving.value = false;
  }
}

async function onLlmSaved(action?: string) {
  llmCardBusy.value = true;
  try {
    await load();
    await app.refreshHealth();
    llmOpen.value = false;
    if (action === "disable") {
      app.flash("已停用大模型。新任务不会调用，直到再次保存并启用。");
    } else if (action === "clear") {
      if (runtime.value?.llm?.source === "environment") {
        app.flash("已清除页面配置。环境变量里的模型仍会使用，要完全停止请点停用。");
      } else {
        app.flash("已清除大模型配置。");
      }
    }
  } finally {
    llmCardBusy.value = false;
  }
}

onMounted(() => {
  void load();
  void app.refreshHealth();
});
</script>

<template>
  <AppShell>
    <LoadingBlock v-if="loading" />
    <ErrorSummary v-else-if="error" :messages="[error]" />
    <div v-else class="settings-layout">
      <article class="settings-panel">
        <p class="eyebrow">本地偏好</p>
        <h2>本地偏好</h2>
        <form class="settings-form" @submit="onSubmit">
          <BaseField label="默认每日章节数" for-id="daily_chapters" required>
            <input
              id="daily_chapters"
              v-model.number="form.daily_chapters"
              type="number"
              min="1"
              max="20"
            />
          </BaseField>
          <BaseField label="默认储备安全线" for-id="reserve_target" required>
            <input
              id="reserve_target"
              v-model.number="form.reserve_target"
              type="number"
              min="1"
              max="50"
            />
          </BaseField>
          <BaseField label="预算提醒额度" for-id="budget_limit">
            <input
              id="budget_limit"
              v-model.number="form.budget_limit"
              type="number"
              min="0"
              step="1"
            />
          </BaseField>
          <label class="toggle">
            <input v-model="form.debug_mode" type="checkbox" />
            <span>显示调试信息</span>
          </label>
          <BaseButton type="submit" variant="primary" :loading="saving">保存偏好</BaseButton>
        </form>
      </article>

      <article class="settings-panel">
        <p class="eyebrow">运行能力</p>
        <h2>运行能力状态</h2>
        <div v-if="!runtime" class="muted">暂时无法读取运行能力状态。</div>
        <div v-else class="runtime-grid">
          <template v-for="([title, key]) in RUNTIME_ROWS" :key="key">
            <button
              v-if="key === 'llm'"
              type="button"
              class="runtime-item is-action"
              :aria-label="`配置大模型，当前${runtimeStatus(key, runtime.llm).text}`"
              :disabled="llmCardBusy"
              @click="llmOpen = true"
              @keydown.enter.prevent="llmOpen = true"
              @keydown.space.prevent="llmOpen = true"
            >
              <div>
                <b>大模型 (LLM)</b>
                <div class="muted">{{ llmSubtitle(runtime.llm) }}</div>
              </div>
              <span class="status-side">
                <span :class="runtimeStatus(key, runtime.llm).tone">
                  {{ runtimeStatus(key, runtime.llm).text }}
                </span>
                <span class="chevron" aria-hidden="true">配置</span>
              </span>
            </button>
            <div v-else class="runtime-item">
              <div>
                <b>{{ title }}</b>
                <div
                  v-if="runtime[key]?.provider || runtime[key]?.model"
                  class="muted"
                >
                  {{ [runtime[key]?.provider, runtime[key]?.model].filter(Boolean).join(" · ") }}
                </div>
              </div>
              <span :class="runtimeStatus(key, runtime[key]).tone">
                {{ runtimeStatus(key, runtime[key]).text }}
              </span>
            </div>
          </template>
        </div>
        <LlmSettingsDrawer :open="llmOpen" @close="llmOpen = false" @saved="onLlmSaved" />
      </article>
    </div>
  </AppShell>
</template>

<style scoped>
.settings-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.settings-panel {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-6);
}

.eyebrow {
  margin: 0 0 var(--space-1);
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

h2 {
  margin: 0 0 var(--space-4);
  font-size: 20px;
}

.settings-form {
  display: grid;
  gap: var(--space-3);
}

.toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: var(--touch-min);
}

.toggle input {
  width: 16px;
  height: 16px;
}

.runtime-grid {
  display: grid;
  gap: var(--space-2);
}

.runtime-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--space-3);
}

.runtime-item.is-action {
  width: 100%;
  text-align: left;
  background: var(--color-surface);
  color: inherit;
  cursor: pointer;
  min-height: var(--touch-min);
}

.runtime-item.is-action:hover:not(:disabled),
.runtime-item.is-action:focus-visible {
  border-color: var(--color-focus);
  outline: 2px solid color-mix(in srgb, var(--color-focus) 35%, transparent);
  outline-offset: 1px;
}

.status-side {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.chevron {
  color: var(--color-text-muted);
  font-size: 12px;
}

.ok {
  color: var(--color-success);
  font-weight: 650;
}

.warn {
  color: var(--color-warning);
  font-weight: 650;
}

.off {
  color: var(--color-text-muted);
  font-weight: 650;
}

@media (max-width: 900px) {
  .settings-layout {
    grid-template-columns: 1fr;
  }
}
</style>
