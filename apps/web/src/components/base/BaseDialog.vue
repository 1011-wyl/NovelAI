<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { X } from "lucide-vue-next";
import BaseIconButton from "./BaseIconButton.vue";

const props = withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    description?: string;
  }>(),
  { description: "" }
);

const emit = defineEmits<{
  close: [];
}>();

const panelRef = ref<HTMLElement | null>(null);
let previouslyFocused: HTMLElement | null = null;
let previousBodyOverflow = "";

function focusableElements(): HTMLElement[] {
  if (!panelRef.value) return [];
  return Array.from(
    panelRef.value.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )
  ).filter((element) => !element.hasAttribute("hidden"));
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape" && props.open) {
    event.preventDefault();
    emit("close");
    return;
  }
  if (event.key !== "Tab" || !props.open) return;
  const focusable = focusableElements();
  if (!focusable.length) {
    event.preventDefault();
    panelRef.value?.focus();
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      previouslyFocused = document.activeElement as HTMLElement | null;
      previousBodyOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      await nextTick();
      const target =
        panelRef.value?.querySelector<HTMLElement>("[autofocus]") ??
        focusableElements()[0] ??
        panelRef.value;
      target?.focus();
    } else {
      document.body.style.overflow = previousBodyOverflow;
      await nextTick();
      previouslyFocused?.focus();
      previouslyFocused = null;
    }
  }
);

onMounted(() => window.addEventListener("keydown", onKeydown));
onUnmounted(() => {
  window.removeEventListener("keydown", onKeydown);
  document.body.style.overflow = previousBodyOverflow;
  previouslyFocused?.focus();
});
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="dialog-root" role="presentation">
      <div class="dialog-backdrop" @click="emit('close')" />
      <div
        ref="panelRef"
        class="dialog-panel"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        tabindex="-1"
      >
        <header class="dialog-header">
          <div>
            <h2 class="dialog-title">{{ title }}</h2>
            <p v-if="description" class="muted dialog-desc">{{ description }}</p>
          </div>
          <BaseIconButton label="关闭" @click="emit('close')">
            <X :size="18" />
          </BaseIconButton>
        </header>
        <div class="dialog-body">
          <slot />
        </div>
        <footer v-if="$slots.footer" class="dialog-footer">
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-root {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: var(--space-4);
}

.dialog-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
}

.dialog-panel {
  position: relative;
  width: min(480px, 100%);
  max-height: min(90vh, 720px);
  overflow: auto;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-float);
  padding: var(--space-4);
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.dialog-title {
  font-size: 1.125rem;
}

.dialog-desc {
  margin-top: var(--space-1);
  font-size: 0.9rem;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-4);
}
</style>
