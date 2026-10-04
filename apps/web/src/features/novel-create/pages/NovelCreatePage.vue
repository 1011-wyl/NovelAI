<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { ArrowLeft } from "lucide-vue-next";
import AppShell from "@/layouts/AppShell.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import ErrorSummary from "@/components/base/ErrorSummary.vue";
import LoadingBlock from "@/components/base/LoadingBlock.vue";
import CreateProgress from "@/features/novel-create/components/CreateProgress.vue";
import CreateSummary from "@/features/novel-create/components/CreateSummary.vue";
import StoryStartStep from "@/features/novel-create/components/steps/StoryStartStep.vue";
import CreativePreferenceStep from "@/features/novel-create/components/steps/CreativePreferenceStep.vue";
import SerializationStep from "@/features/novel-create/components/steps/SerializationStep.vue";
import { useNovelCreateStore } from "@/features/novel-create/store/novel-create.store";
import { RouteNames } from "@/router/route-names";

const store = useNovelCreateStore();
const router = useRouter();

onMounted(() => {
  void store.loadCatalog();
});

function onBackToLibrary() {
  if (!store.abandonIfNeeded()) return;
  void router.push({ name: RouteNames.Library });
}

async function onSubmit() {
  const project = await store.submit();
  if (!project) return;
  await router.replace({
    name: RouteNames.Workbench,
    params: { projectId: project.id },
    query: { created: "1" },
  });
}
</script>

<template>
  <AppShell>
    <div class="create-page">
      <header class="create-header">
        <button type="button" class="back" @click="onBackToLibrary">
          <ArrowLeft :size="16" aria-hidden="true" />
          返回书架
        </button>
        <CreateProgress :step="store.step" />
        <p class="muted">按步骤完善方向后，再生成创作方案。</p>
      </header>

      <div v-if="store.catalogLoading && !store.catalog" class="catalog-loading">
        <LoadingBlock label="正在加载标签目录" />
      </div>

      <div v-else-if="store.catalogError" class="catalog-error" role="alert">
        <p>{{ store.catalogError }}</p>
        <BaseButton @click="store.loadCatalog()">重新加载标签</BaseButton>
      </div>

      <div v-else class="create-layout">
        <div class="create-main">
          <ErrorSummary
            v-if="store.formErrorMessages.length"
            :messages="store.formErrorMessages"
          />

          <StoryStartStep v-if="store.step === 1" />
          <CreativePreferenceStep v-else-if="store.step === 2" />
          <SerializationStep v-else />

          <div class="progress-slot" aria-live="polite">
            <div v-if="store.submitting" class="progress-panel">
              <p>正在生成创作方案……</p>
              <p class="muted">请勿关闭或刷新页面。生成可能需要一些时间。</p>
            </div>
            <div v-else class="progress-panel is-idle" aria-hidden="true" />
          </div>

          <div class="actions">
            <BaseButton v-if="store.step > 1" :disabled="store.submitting" @click="store.prevStep()">
              上一步
            </BaseButton>
            <BaseButton
              v-if="store.step < 3"
              variant="primary"
              :disabled="store.submitting"
              @click="store.nextStep()"
            >
              下一步
            </BaseButton>
            <BaseButton
              v-else
              variant="primary"
              :loading="store.submitting"
              :disabled="store.submitting"
              @click="onSubmit"
            >
              {{ store.submitting ? "正在生成创作方案……" : "生成创作方案" }}
            </BaseButton>
          </div>
        </div>

        <div class="summary-wrap">
          <CreateSummary :form="store.form" />
        </div>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
.create-header {
  margin-bottom: var(--space-4);
}

.back {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: var(--touch-min);
  border: 0;
  background: transparent;
  padding: 0;
  margin-bottom: var(--space-2);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.create-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(240px, 0.8fr);
  gap: var(--space-6);
  align-items: start;
}

.create-main {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  background: var(--color-surface);
}

.progress-slot {
  min-height: 72px;
}

.progress-panel {
  min-height: 72px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-surface-muted);
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: var(--space-1);
}

.progress-panel.is-idle {
  visibility: hidden;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  justify-content: flex-end;
}

@media (max-width: 767px) {
  .create-layout {
    grid-template-columns: 1fr;
  }
}
</style>
