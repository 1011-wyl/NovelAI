import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import ChapterRecoveryBanner from "./ChapterRecoveryBanner.vue";
import ErrorSummary from "@/components/base/ErrorSummary.vue";

describe("阅读页 FAILED 恢复", () => {
  it("shows a compact recovery banner and reveals details on demand", async () => {
    const wrapper = mount(ChapterRecoveryBanner, {
      props: {
        chapter: { id: "c1", number: 1, title: "异常征兆", status: "FAILED", version: 1 } as never,
        failure: {
          chapter_number: 1,
          score: 40,
          issues: [{ message: "字数偏短" }],
          score_trace: [40, 55, 62],
          review_attempt: 3,
          max_review_attempts: 3,
          lowest_component: "readability.opening_hook",
        },
        canAccept: true,
        acceptDisabled: false,
      },
    });
    expect(wrapper.text()).toContain("质量待修改");
    expect(wrapper.text()).toContain("40.0 分 · 通过条件 > 60.0");
    expect(wrapper.text()).not.toContain("编辑草稿");
    expect(wrapper.get(".banner-toggle").attributes("aria-expanded")).toBe("false");
    await wrapper.get(".banner-toggle").trigger("click");
    expect(wrapper.text()).toContain("编辑草稿");
    expect(wrapper.text()).toContain("返回工作台");
    expect(wrapper.text()).toContain("接受当前版本");
    expect(wrapper.text()).toContain("第 3/3 次质量检查");
    expect(wrapper.text()).toContain("40.0 → 55.0 → 62.0");
    expect(wrapper.get(".banner-toggle").attributes("aria-expanded")).toBe("true");
    expect(wrapper.get(".recovery-banner").attributes("role")).toBe("alert");
    expect(wrapper.get(".recovery-banner").attributes("tabindex")).toBe("-1");
  });

  it("hides accept action when capability is false", async () => {
    const wrapper = mount(ChapterRecoveryBanner, {
      props: {
        chapter: { id: "c1", number: 1, title: "异常征兆", status: "FAILED", version: 1 } as never,
        failure: { chapter_number: 1, issues: [{ message: "硬阻断" }] },
        canAccept: false,
      },
    });
    await wrapper.get(".banner-toggle").trigger("click");
    expect(wrapper.text()).not.toContain("接受当前版本并继续");
  });

  it("does not present a length preflight failure as a zero-point review", () => {
    const wrapper = mount(ChapterRecoveryBanner, {
      props: {
        chapter: { id: "c1", number: 1, title: "异常征兆", status: "FAILED", version: 1 } as never,
        failure: {
          chapter_number: 1,
          score: 0,
          selected_score: 0,
          quality_status: "LENGTH_NEEDS_ATTENTION",
          preflight_only: true,
          actual_length: 1781,
          accepted_length_min: 1980,
          accepted_length_max: 2420,
        },
      },
    });
    expect(wrapper.text()).toContain("字数不足");
    expect(wrapper.text()).toContain("当前 1781 / 至少 1980 字 · 尚未审核");
    expect(wrapper.text()).not.toContain("综合质量分 0.0");
    expect(wrapper.text()).not.toContain("最终采用：0.0 分");
  });

  it("uses the live draft count instead of a stale failure snapshot", () => {
    const wrapper = mount(ChapterRecoveryBanner, {
      props: {
        chapter: { id: "c1", number: 1, title: "异常征兆", status: "FAILED", version: 1 } as never,
        currentLength: 1900,
        failure: {
          chapter_number: 1,
          quality_status: "LENGTH_NEEDS_ATTENTION",
          preflight_only: true,
          actual_length: 1781,
          accepted_length_min: 2000,
          accepted_length_max: 2400,
        },
      },
    });
    expect(wrapper.text()).toContain("当前 1900 / 至少 2000 字");
    expect(wrapper.text()).not.toContain("1781");
  });

  it("error summary uses role=alert", () => {
    const wrapper = mount(ErrorSummary, { props: { messages: ["工作区加载失败"] } });
    expect(wrapper.attributes("role")).toBe("alert");
    expect(wrapper.text()).toContain("工作区加载失败");
  });
});
