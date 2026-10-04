<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import ProjectShell from "@/layouts/ProjectShell.vue";
import LoadingBlock from "@/components/base/LoadingBlock.vue";
import ErrorSummary from "@/components/base/ErrorSummary.vue";
import { useWorkbenchStore } from "@/features/workbench/store/workbench.store";
import { rebuildCharacters } from "@/features/workbench/api/workbench.api";
import { useAppStore } from "@/stores/app.store";
import { toUserError } from "@/stores/projects.store";
import type { CharacterRecord, ResearchSource, WorldFact } from "@/api/contracts";
import {
  CHARACTER_ROLE_LABELS,
  appearedChapter,
  characterFacts,
  characterStateLabel,
  formatCharacterValue,
  stateRows,
} from "../character-format";
import "../styles/memory.css";

const route = useRoute();
const workbench = useWorkbenchStore();
const app = useAppStore();

const selectedId = ref<string | null>(null);
const showDetail = ref(false);
const timelineExpanded = ref(false);
const researchExpanded = ref(false);
const rebuilding = ref(false);

const projectId = computed(() => String(route.params.projectId || ""));
const characters = computed(() => workbench.detail?.characters ?? []);
const worldFacts = computed(() => workbench.detail?.world_facts ?? []);
const timeline = computed(() => workbench.detail?.timeline ?? []);
const research = computed(() => workbench.detail?.research_sources ?? []);
const semanticCount = computed(() => workbench.detail?.semantic_document_count ?? 0);

const selected = computed(
  () =>
    characters.value.find((item) => item.id === selectedId.value) ||
    characters.value.find((item) => item.role === "protagonist") ||
    characters.value[0] ||
    null
);

const factGroups = computed(() => {
  const groups: Record<string, WorldFact[]> = {};
  for (const fact of worldFacts.value) {
    (groups[fact.category] ||= []).push(fact);
  }
  return Object.entries(groups);
});

const visibleTimeline = computed(() => {
  if (timelineExpanded.value || timeline.value.length <= 15) return timeline.value;
  return timeline.value.slice(-15);
});

const hiddenTimelineCount = computed(() => Math.max(0, timeline.value.length - 15));

const visibleResearch = computed(() => {
  if (researchExpanded.value || research.value.length <= 5) return research.value;
  return research.value.slice(0, 5);
});

const hiddenResearchCount = computed(() => Math.max(0, research.value.length - 5));

async function load() {
  if (!projectId.value) return;
  if (workbench.detail?.project?.id !== projectId.value) {
    await workbench.loadDetail(projectId.value);
  }
  const first =
    characters.value.find((item) => item.role === "protagonist") || characters.value[0];
  selectedId.value = first?.id ?? null;
  showDetail.value = false;
}

watch(projectId, () => {
  void load().catch(() => undefined);
});

onMounted(() => {
  void load().catch(() => undefined);
});

function selectCharacter(character: CharacterRecord, openMobileDetail = false) {
  selectedId.value = character.id;
  if (openMobileDetail) showDetail.value = true;
}

function roleLabel(role: string) {
  return CHARACTER_ROLE_LABELS[role] || "人物";
}

function progressText(item: CharacterRecord) {
  const chapter = appearedChapter(item);
  return chapter > 0 ? `最近第 ${chapter} 章` : "尚未正式出场";
}

function importanceText(item: CharacterRecord) {
  const state = item.current_state || {};
  return state.importance === "core" || item.role === "protagonist" ? "核心" : "重要";
}

function initialOf(name: string) {
  return Array.from(String(name || "人"))[0] || "人";
}

async function onRebuild() {
  if (!projectId.value) {
    app.flash("请先选择小说项目", true);
    return;
  }
  if (
    !window.confirm(
      "将扫描这本书的全部 READY 章节，只保留核心人物和重要人物；在线模式下会调用大模型。是否继续？"
    )
  ) {
    return;
  }
  rebuilding.value = true;
  app.setBusy(true);
  try {
    const result = await rebuildCharacters(projectId.value);
    await workbench.loadDetail(projectId.value);
    const failed = result.failures?.length ? `，${result.failures.length} 章提取失败` : "";
    const removed = result.removed_nonimportant
      ? `，清理 ${result.removed_nonimportant} 个非重要人物档案`
      : "";
    app.flash(
      `重要人物档案重建完成：扫描 ${result.processed_chapters} 章，共 ${result.character_count} 人${removed}${failed}`
    );
  } catch (error) {
    app.flash(toUserError(error, "重建人物档案失败"), true);
  } finally {
    rebuilding.value = false;
    app.setBusy(false);
  }
}

function researchMeta(item: ResearchSource) {
  const verified = item.verified ? "已获得交叉来源" : "单一来源";
  const reliability = Number(item.reliability || 0).toFixed(2);
  return `${verified} · 可信度 ${reliability}`;
}
</script>

<template>
  <ProjectShell>
    <LoadingBlock v-if="workbench.loading && !workbench.detail" />
    <ErrorSummary v-else-if="workbench.error && !workbench.detail" :messages="[workbench.error]" />
    <div v-else class="memory-page">
      <article class="legacy-panel character-library">
        <div class="panel-head">
          <div>
            <h3>重要人物档案库</h3>
            <p class="panel-subtitle">选择人物查看背景、目标、知识与关系</p>
          </div>
          <div class="panel-actions">
            <span class="badge">{{ characters.length }} 人</span>
            <button class="text-button" type="button" :disabled="rebuilding" @click="onRebuild">
              重建重要人物档案
            </button>
          </div>
        </div>
        <div class="character-browser" :class="{ 'show-detail': showDetail }">
          <aside class="character-list-pane">
            <div class="character-list">
              <div v-if="!characters.length" class="empty">暂无重要人物</div>
              <button
                v-for="item in characters"
                :key="item.id"
                type="button"
                class="character-list-item"
                :class="{ selected: selected?.id === item.id }"
                :aria-pressed="selected?.id === item.id"
                @click="selectCharacter(item, true)"
              >
                <span class="character-avatar">{{ initialOf(item.name) }}</span>
                <span class="character-list-copy">
                  <b>{{ item.name }}</b>
                  <small>{{ roleLabel(item.role) }} · {{ importanceText(item) }}人物</small>
                  <em>{{ progressText(item) }}</em>
                </span>
                <span class="character-chevron" aria-hidden="true">›</span>
              </button>
            </div>
          </aside>
          <section class="character-detail-pane">
            <button class="text-button character-back-button" type="button" @click="showDetail = false">
              ← 返回人物列表
            </button>
            <div v-if="!selected" class="empty">请选择人物</div>
            <article v-else class="character-card">
              <div class="character-head">
                <div>
                  <h4>{{ selected.name }}</h4>
                  <span>{{ roleLabel(selected.role) }}</span>
                  <span class="importance-badge">{{ importanceText(selected) }}人物</span>
                </div>
                <div class="character-progress">
                  {{
                    appearedChapter(selected) > 0
                      ? `更新至第 ${appearedChapter(selected)} 章`
                      : "尚未正式出场"
                  }}
                  <small>记忆版本 v{{ Number(selected.version || 1) }}</small>
                </div>
              </div>
              <details v-if="characterFacts(selected).length" class="character-section" open>
                <summary><h5>人物档案</h5></summary>
                <dl>
                  <div
                    v-for="([label, value], index) in characterFacts(selected)"
                    :key="`${label}-${index}`"
                    class="character-field"
                  >
                    <dt>{{ label }}</dt>
                    <dd>{{ value }}</dd>
                  </div>
                </dl>
              </details>
              <details v-if="stateRows(selected).length" class="character-section">
                <summary>
                  <h5>当前进展（{{ stateRows(selected).length }} 项）</h5>
                </summary>
                <dl>
                  <div
                    v-for="([key, value]) in stateRows(selected)"
                    :key="key"
                    class="character-field"
                  >
                    <dt>{{ characterStateLabel(key) }}</dt>
                    <dd>{{ formatCharacterValue(value) }}</dd>
                  </div>
                </dl>
              </details>
              <p v-if="appearedChapter(selected) <= 0" class="character-empty">
                尚未在正文中正式出场，档案数据来自创作方案。
              </p>
            </article>
          </section>
        </div>
      </article>

      <div class="memory-supporting">
        <article class="legacy-panel">
          <div class="panel-head">
            <h3>世界硬规则</h3>
            <span class="badge">锁定</span>
          </div>
          <div v-if="!factGroups.length" class="empty">暂无规则</div>
          <details v-for="([category, items]) in factGroups" :key="category" class="fact-group" open>
            <summary>{{ category }} ({{ items.length }})</summary>
            <div class="fact-group-body">
              <p v-for="(fact, index) in items" :key="index">
                {{ fact.statement }}
                <span v-if="fact.locked" class="lock-tag">锁定</span>
              </p>
            </div>
          </details>
        </article>
        <article class="legacy-panel">
          <div class="panel-head">
            <h3>时间线</h3>
            <span class="badge">章节证据</span>
          </div>
          <div v-if="!timeline.length" class="empty">暂无正式事件</div>
          <template v-else>
            <div
              v-for="(item, index) in visibleTimeline"
              :key="`${item.chapter_number}-${index}`"
              class="timeline-item"
            >
              <b>第 {{ item.chapter_number }} 章</b>
              <p>{{ item.event }}</p>
            </div>
            <button
              v-if="hiddenTimelineCount > 0"
              class="text-button"
              type="button"
              @click="timelineExpanded = !timelineExpanded"
            >
              {{ timelineExpanded ? "收起" : `展开全部 ${timeline.length} 条` }}
            </button>
          </template>
        </article>
      </div>

      <article class="legacy-panel">
        <div class="panel-head">
          <h3>研究资料</h3>
          <span class="badge">{{ semanticCount }} 条语义索引</span>
        </div>
        <div v-if="!research.length" class="empty">尚未触发现实知识调研</div>
        <template v-else>
          <div
            v-for="(item, index) in visibleResearch"
            :key="index"
            class="research-card"
          >
            <div>
              <b>{{ item.title || item.domain || "网页来源" }}</b>
              <span>{{ researchMeta(item) }}</span>
            </div>
            <p>{{ item.excerpt || "" }}</p>
            <a
              v-if="item.url"
              :href="item.url"
              target="_blank"
              rel="noopener noreferrer"
            >
              打开来源 ↗
            </a>
          </div>
          <button
            v-if="hiddenResearchCount > 0"
            class="text-button"
            type="button"
            @click="researchExpanded = !researchExpanded"
          >
            {{ researchExpanded ? "收起" : `展开全部 ${research.length} 条` }}
          </button>
        </template>
      </article>
    </div>
  </ProjectShell>
</template>
