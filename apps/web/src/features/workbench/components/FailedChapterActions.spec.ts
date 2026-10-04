import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import FailedChapterActions from "./FailedChapterActions.vue";
import FailureDetails from "./FailureDetails.vue";
import OpeningRepairDialog from "./OpeningRepairDialog.vue";
import type { ChapterFailure } from "../types/workbench.types";
import type { OpeningRepairPreview } from "../types/workbench.types";

const replanFailure: ChapterFailure = {
  chapter_number: 1,
  score: 42,
  reviewed_at: "2026-10-03T00:00:00",
  recommended_rework_mode: "replan",
  opening_repair_eligible: true,
  issues: [{ category: "character", message: "人物关系写成了未来效忠" }],
};

const reuseFailure: ChapterFailure = {
  ...replanFailure,
  recommended_rework_mode: "reuse_plan",
  opening_repair_eligible: false,
  issues: [{ category: "length", message: "字数偏短" }],
};

describe("FAILED 工作台卡片", () => {
  it("shows Chinese reason, score and recovery actions", () => {
    const details = mount(FailureDetails, { props: { failure: replanFailure } });
    expect(details.text()).toContain("未通过审核");
    expect(details.text()).toContain("42");
    expect(details.text()).toContain("人物关系写成了未来效忠");
    const actions = mount(FailedChapterActions, { props: { failure: replanFailure } });
    expect(actions.text()).toContain("重新规划并重写");
    expect(actions.text()).toContain("检查并修复开篇数据");
    expect(actions.text()).not.toContain("沿用细纲重写");
  });

  it("hides reuse action for structural replan failures", () => {
    const wrapper = mount(FailedChapterActions, { props: { failure: reuseFailure } });
    expect(wrapper.text()).toContain("沿用细纲重写");
    const replan = mount(FailedChapterActions, { props: { failure: replanFailure } });
    expect(replan.text()).not.toContain("沿用细纲重写");
  });

  it("shows accept action only when server capability is true", () => {
    const soft = mount(FailedChapterActions, {
      props: { failure: { ...reuseFailure, can_accept_with_warnings: true } },
    });
    expect(soft.text()).toContain("接受当前版本并继续");
    const hard = mount(FailedChapterActions, {
      props: { failure: { ...replanFailure, can_accept_with_warnings: false } },
    });
    expect(hard.text()).not.toContain("接受当前版本并继续");
  });

  it("shows score trace and lowest component without calling it an average", () => {
    const details = mount(FailureDetails, {
      props: {
        failure: {
          ...reuseFailure,
          score: 71,
          lowest_component: "readability.scene_causality",
          score_trace: [58, 71],
          review_attempt: 2,
          max_review_attempts: 3,
          revision_count: 1,
        },
      },
    });
    expect(details.text()).toContain("第 2/3 次质量检查");
    expect(details.text()).toContain("场景因果");
    expect(details.text()).toContain("58.0 → 71.0");
    expect(details.text()).toContain("综合质量分 71.0");
    expect(details.text()).toContain("通过条件");
    expect(details.text()).not.toContain("当前最低项分数");
    expect(details.text()).not.toContain("平均总分");
  });

  it("shows an exhausted length repair as unreviewed instead of zero score", () => {
    const details = mount(FailureDetails, {
      props: {
        failure: {
          ...reuseFailure,
          score: 0,
          selected_score: 0,
          quality_status: "LENGTH_NEEDS_ATTENTION",
          preflight_only: true,
          actual_length: 1781,
          accepted_length_min: 1980,
          accepted_length_max: 2420,
          length_repair_count: 2,
          revision_count: 0,
        },
      },
    });
    expect(details.text()).toContain("字数尚未达标");
    expect(details.text()).toContain("综合质量分：未审核");
    expect(details.text()).toContain("实际字数 1781 / 目标范围 1980～2420");
    expect(details.text()).not.toContain("综合质量分 0.0");
    expect(details.text()).not.toContain("最终采用：0.0 分");
  });
});

describe("OpeningRepairDialog", () => {
  const preview: OpeningRepairPreview = {
    eligible: true,
    reasons: [],
    project_updated_at: "2026-10-03T00:00:00",
    detected_problems: ["顾铁山当前关系混入未来效忠"],
    opening_anchor: { title: "异常征兆", core_event: "神纹异常出现" },
    character_changes: [
      {
        name: "顾铁山",
        from_relationships: { 顾宁: "被救后效忠主角" },
        to_relationships: {},
        moved_to_future: true,
      },
    ],
    chapter_changes: [
      {
        chapter_number: 1,
        from_status: "FAILED",
        to_status: "PLANNED",
        from_title: "错章",
        to_title: "异常征兆",
      },
    ],
    preserved_artifacts: ["旧失败正文与细纲会写入修复快照"],
  };

  it("shows impact and requires explicit confirmation", async () => {
    const wrapper = mount(OpeningRepairDialog, {
      props: { open: true, preview },
      attachTo: document.body,
    });
    expect(wrapper.text()).toContain("顾铁山当前关系混入未来效忠");
    expect(wrapper.text()).toContain("异常征兆");
    expect(wrapper.text()).toContain("被救后效忠主角");
    expect(wrapper.text()).toContain("FAILED");
    expect(wrapper.text()).toContain("PLANNED");
    expect(wrapper.text()).toContain("旧失败正文与细纲会写入修复快照");
    const confirm = wrapper.findAll("button").find((btn) => btn.text().includes("确认修复"));
    expect(confirm?.attributes("disabled")).toBeDefined();
    await wrapper.get("input[type='checkbox']").setValue(true);
    expect(wrapper.findAll("button").find((btn) => btn.text().includes("确认修复"))?.attributes("disabled")).toBeUndefined();
    wrapper.unmount();
  });

  it("resets confirmation when reopened or preview changes", async () => {
    const wrapper = mount(OpeningRepairDialog, {
      props: { open: true, preview },
      attachTo: document.body,
    });
    await wrapper.get("input[type='checkbox']").setValue(true);
    expect((wrapper.get("input[type='checkbox']").element as HTMLInputElement).checked).toBe(true);
    await wrapper.setProps({ open: false });
    await wrapper.setProps({ open: true });
    expect((wrapper.get("input[type='checkbox']").element as HTMLInputElement).checked).toBe(false);
    await wrapper.get("input[type='checkbox']").setValue(true);
    await wrapper.setProps({
      preview: { ...preview, project_updated_at: "2026-10-03T01:00:00" },
    });
    expect((wrapper.get("input[type='checkbox']").element as HTMLInputElement).checked).toBe(false);
    wrapper.unmount();
  });
});
