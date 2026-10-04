<script setup lang="ts">
import { computed, reactive, watch } from "vue";
import type { BriefVersion, CreativeBrief } from "@/api/contracts";
import BaseButton from "@/components/base/BaseButton.vue";
import { useAppStore } from "@/stores/app.store";

const VERSION_SOURCE_MAP: Record<string, string> = {
  initial: "初始方案",
  migration: "历史方案",
  manual_edit: "手工修改",
  regenerate: "整体重做",
  partial_regenerate: "局部重做",
  feedback_regenerate: "按意见重做",
  restore: "恢复旧版",
  metadata_edit: "修改书名",
};

const SECTIONS = [
  { value: "title", label: "书名" },
  { value: "story", label: "故事核心" },
  { value: "protagonist", label: "主角" },
  { value: "world", label: "世界规则" },
  { value: "opening", label: "开篇三章" },
  { value: "style", label: "文风" },
  { value: "serialization", label: "连载计划" },
];

const props = defineProps<{
  brief: CreativeBrief;
  versions: BriefVersion[];
  acting?: boolean;
}>();

const emit = defineEmits<{
  save: [brief: CreativeBrief];
  regenerate: [payload: { feedback: string; sections: string[] }];
  restore: [version: number];
}>();

const app = useAppStore();
const editing = defineModel<boolean>("editing", { default: false });
const feedback = defineModel<string>("feedback", { default: "" });
const selectedSections = reactive<Record<string, boolean>>({});

const form = reactive({
  selected_title: "",
  synopsis: "",
  target_readers: "",
  protagonist_name: "",
  protagonist_profile: "",
  main_conflict: "",
  reader_contract: "",
  core_expectation: "",
  selling_points: "",
  world_rules: "",
  opening_three_chapters: "",
  style_guide: "",
  total_chapters: 1,
  volume_count: 1,
  update_plan: "",
});

const leftVersion = defineModel<number>("leftVersion", { default: 0 });
const rightVersion = defineModel<number>("rightVersion", { default: 0 });

watch(
  () => props.brief,
  (brief) => {
    form.selected_title = brief.selected_title || "";
    form.synopsis = brief.synopsis || "";
    form.target_readers = brief.target_readers || "";
    form.protagonist_name = brief.protagonist_name || brief.protagonist || "";
    form.protagonist_profile = brief.protagonist_profile || "";
    form.main_conflict = brief.main_conflict || "";
    form.reader_contract = brief.reader_contract || "";
    form.core_expectation = brief.core_expectation || "";
    form.selling_points = (brief.selling_points || []).join("\n");
    form.world_rules = (brief.world_rules || []).join("\n");
    form.opening_three_chapters = (
      brief.opening_chapter_anchors?.length
        ? brief.opening_chapter_anchors.map(
            (item) => `${item.title || ""}｜${item.core_event || ""}`.replace(/^｜/, "")
          )
        : brief.opening_three_chapters || []
    ).join("\n");
    form.style_guide = (brief.style_guide || []).join("\n");
    form.total_chapters = brief.total_chapters;
    form.volume_count = brief.volume_count;
    form.update_plan = brief.update_plan || "";
  },
  { immediate: true }
);

watch(
  () => props.versions,
  (items) => {
    if (!items.length) return;
    rightVersion.value = items[0].version;
    leftVersion.value = items.length > 1 ? items[1].version : items[0].version;
  },
  { immediate: true }
);

function splitLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function versionSource(source: string) {
  return VERSION_SOURCE_MAP[source] || source;
}

function snapshot(version: number) {
  return props.versions.find((item) => item.version === Number(version)) ?? null;
}

const leftSnapshot = computed(() => snapshot(leftVersion.value));
const rightSnapshot = computed(() => snapshot(rightVersion.value));

function onSave(event: Event) {
  event.preventDefault();
  const title = form.selected_title.trim();
  emit("save", {
    ...props.brief,
    selected_title: title,
    title_candidates: [...new Set([title, ...(props.brief.title_candidates || [])])].slice(0, 6),
    synopsis: form.synopsis.trim(),
    target_readers: form.target_readers.trim(),
    selling_points: splitLines(form.selling_points),
    protagonist: form.protagonist_name.trim(),
    protagonist_name: form.protagonist_name.trim(),
    protagonist_profile: form.protagonist_profile.trim(),
    main_conflict: form.main_conflict.trim(),
    reader_contract: form.reader_contract.trim(),
    core_expectation: form.core_expectation.trim(),
    world_rules: splitLines(form.world_rules),
    total_chapters: Number(form.total_chapters),
    volume_count: Number(form.volume_count),
    opening_three_chapters: splitLines(form.opening_three_chapters),
    opening_chapter_anchors: splitLines(form.opening_three_chapters)
      .slice(0, 3)
      .map((line, index) => {
        const [title, ...rest] = line.split(/[｜|]/);
        const core = rest.join("｜").trim() || title.trim();
        return {
          number: (index + 1) as 1 | 2 | 3,
          title: rest.length ? title.trim() : "",
          core_event: core,
        };
      }),
    update_plan: form.update_plan.trim(),
    style_guide: splitLines(form.style_guide),
  });
  editing.value = false;
}

function onFeedbackRegenerate() {
  const sections = Object.entries(selectedSections)
    .filter(([, checked]) => checked)
    .map(([value]) => value);
  const text = feedback.value.trim();
  if (!text && !sections.length) {
    app.flash("请填写修改意见或选择需要重做的模块。", true);
    return;
  }
  emit("regenerate", { feedback: text, sections });
  feedback.value = "";
  Object.keys(selectedSections).forEach((key) => {
    selectedSections[key] = false;
  });
}
</script>

<template>
  <article class="legacy-panel">
    <div class="panel-head">
      <div>
        <p class="eyebrow">方案工作台</p>
        <h3>方案修改与版本对比</h3>
      </div>
      <span class="badge">确认前可修改</span>
    </div>
    <div class="workbench-grid" :class="{ 'is-feedback-only': !editing }">
      <form v-if="editing" class="brief-edit-form" @submit="onSave">
        <label>正式书名<input v-model="form.selected_title" maxlength="80" required /></label>
        <label>故事简介<textarea v-model="form.synopsis" rows="4" required /></label>
        <div class="field-row">
          <label>目标读者<input v-model="form.target_readers" required /></label>
          <label>主角姓名<input v-model="form.protagonist_name" maxlength="20" required /></label>
        </div>
        <label>主角介绍<textarea v-model="form.protagonist_profile" rows="3" /></label>
        <label>主要冲突<textarea v-model="form.main_conflict" rows="2" required /></label>
        <label>
          读者契约
          <textarea v-model="form.reader_contract" rows="2" placeholder="这本书持续向读者交付什么核心情绪回报" />
        </label>
        <label>
          核心期待
          <textarea v-model="form.core_expectation" rows="2" placeholder="开篇建立并需要持续推进的主要期待" />
        </label>
        <label>核心卖点（每行一项）<textarea v-model="form.selling_points" rows="3" /></label>
        <label>世界规则（每行一项）<textarea v-model="form.world_rules" rows="4" /></label>
        <label>
          开篇三章锚点（每行一章，可用 标题｜核心事件）
          <textarea v-model="form.opening_three_chapters" rows="3" />
        </label>
        <label>文风规则（每行一项）<textarea v-model="form.style_guide" rows="3" /></label>
        <div class="field-row">
          <label>预计章节数<input v-model.number="form.total_chapters" type="number" min="1" required /></label>
          <label>分卷数<input v-model.number="form.volume_count" type="number" min="1" required /></label>
        </div>
        <label>更新计划<input v-model="form.update_plan" required /></label>
        <div class="form-actions">
          <BaseButton type="submit" variant="primary" :disabled="acting">保存为新版本</BaseButton>
          <BaseButton type="button" variant="ghost" @click="editing = false">取消</BaseButton>
        </div>
      </form>
      <div class="brief-regenerate-box">
        <label>
          告诉智能体哪里不满意
          <textarea v-model="feedback" rows="4" placeholder="例如：书名更简洁；主角不要重生；开篇冲突更快。" />
        </label>
        <fieldset>
          <legend>只重做选中的模块；不选则整体优化</legend>
          <div class="chips">
            <label v-for="section in SECTIONS" :key="section.value" class="chip">
              <input v-model="selectedSections[section.value]" type="checkbox" :value="section.value" />
              <span>{{ section.label }}</span>
            </label>
          </div>
        </fieldset>
        <BaseButton :disabled="acting" @click="onFeedbackRegenerate">按意见生成新版本</BaseButton>
        <p class="muted">每次修改都会保留旧版本。只有点击“确认创作方案”后才会锁定设定并开始写作。</p>
      </div>
    </div>
    <div class="version-compare">
      <div class="compare-controls">
        <label>
          左侧版本
          <select v-model.number="leftVersion">
            <option v-for="item in versions" :key="`l-${item.version}`" :value="item.version">
              v{{ item.version }} · {{ versionSource(item.source) }}
            </option>
          </select>
        </label>
        <label>
          右侧版本
          <select v-model.number="rightVersion">
            <option v-for="item in versions" :key="`r-${item.version}`" :value="item.version">
              v{{ item.version }} · {{ versionSource(item.source) }}
            </option>
          </select>
        </label>
        <BaseButton variant="ghost" :disabled="acting || !leftVersion" @click="emit('restore', leftVersion)">
          恢复左侧版本
        </BaseButton>
      </div>
      <div class="compare-grid">
        <div class="brief-snapshot">
          <template v-if="leftSnapshot">
            <h4>v{{ leftSnapshot.version }} · {{ versionSource(leftSnapshot.source) }}</h4>
            <p><strong>书名：</strong>{{ leftSnapshot.brief.selected_title }}</p>
            <p><strong>主角：</strong>{{ leftSnapshot.brief.protagonist_name || leftSnapshot.brief.protagonist }}</p>
            <p><strong>简介：</strong>{{ leftSnapshot.brief.synopsis }}</p>
            <p><strong>主要冲突：</strong>{{ leftSnapshot.brief.main_conflict }}</p>
            <p><strong>世界规则：</strong>{{ (leftSnapshot.brief.world_rules || []).join("；") }}</p>
            <p v-if="leftSnapshot.feedback"><strong>修改意见：</strong>{{ leftSnapshot.feedback }}</p>
          </template>
          <p v-else>暂无版本</p>
        </div>
        <div class="brief-snapshot">
          <template v-if="rightSnapshot">
            <h4>v{{ rightSnapshot.version }} · {{ versionSource(rightSnapshot.source) }}</h4>
            <p><strong>书名：</strong>{{ rightSnapshot.brief.selected_title }}</p>
            <p><strong>主角：</strong>{{ rightSnapshot.brief.protagonist_name || rightSnapshot.brief.protagonist }}</p>
            <p><strong>简介：</strong>{{ rightSnapshot.brief.synopsis }}</p>
            <p><strong>主要冲突：</strong>{{ rightSnapshot.brief.main_conflict }}</p>
            <p><strong>世界规则：</strong>{{ (rightSnapshot.brief.world_rules || []).join("；") }}</p>
            <p v-if="rightSnapshot.feedback"><strong>修改意见：</strong>{{ rightSnapshot.feedback }}</p>
          </template>
          <p v-else>暂无版本</p>
        </div>
      </div>
    </div>
  </article>
</template>
