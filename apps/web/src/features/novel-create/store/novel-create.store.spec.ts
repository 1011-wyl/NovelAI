import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useNovelCreateStore } from "@/features/novel-create/store/novel-create.store";
import { toCreatePayload, defaultCreateForm } from "@/features/novel-create/schema";

vi.mock("@/features/novel-create/api/novel-create.api", () => ({
  fetchTagCatalog: vi.fn(),
  createNovel: vi.fn(),
  abortTagCatalog: vi.fn(),
}));

import { fetchTagCatalog } from "@/features/novel-create/api/novel-create.api";

describe("novel-create store & payload", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.mocked(fetchTagCatalog).mockResolvedValue({
      default_channel: "男频",
      channels: {
        男频: {
          genres: ["玄幻脑洞", "都市脑洞"],
          experiences: ["爽文", "热血", "轻松"],
          elements: ["系统", "重生"],
          protagonist_tags: ["普通人成长", "天才"],
          romance: ["自动推导", "无感情线"],
        },
        女频: {
          genres: ["现言脑洞"],
          experiences: ["甜宠"],
          elements: ["穿书"],
          protagonist_tags: ["大女主"],
          romance: ["自动推导", "1v1"],
        },
      },
    });
  });

  it("navigates steps without losing form data", async () => {
    const store = useNovelCreateStore();
    await store.loadCatalog();
    store.form.idea = "一个关于仓储管理员的故事";
    store.form.genre = "玄幻脑洞";
    expect(store.nextStep()).toBe(true);
    expect(store.step).toBe(2);
    store.form.experiences = ["爽文"];
    expect(store.nextStep()).toBe(true);
    expect(store.step).toBe(3);
    store.prevStep();
    expect(store.step).toBe(2);
    expect(store.form.idea).toBe("一个关于仓储管理员的故事");
    expect(store.form.experiences).toEqual(["爽文"]);
  });

  it("blocks next step when idea is empty", async () => {
    const store = useNovelCreateStore();
    await store.loadCatalog();
    store.form.idea = "";
    expect(store.nextStep()).toBe(false);
    expect(store.step).toBe(1);
    expect(store.fieldErrors.idea).toBeTruthy();
  });

  it("maps payload fields to NovelCreateRequest shape", () => {
    const form = defaultCreateForm();
    form.audience_channel = "男频";
    form.genre = "玄幻脑洞";
    form.preferred_title = "  长夜  ";
    form.idea = "核心故事想法";
    form.experiences = ["爽文"];
    form.elements = ["系统"];
    form.protagonist_tags = ["普通人成长"];
    form.romance = "自动推导";
    form.must_have = "系统, 成长";
    form.exclude = "悲剧结局";
    form.chapter_target_chars = 2200;
    form.daily_chapters = 2;
    form.reserve_target = 5;
    form.require_plan_confirmation = true;

    expect(toCreatePayload(form)).toEqual({
      preferred_title: "长夜",
      audience_channel: "男频",
      genre: "玄幻脑洞",
      experiences: ["爽文"],
      elements: ["系统"],
      protagonist_tags: ["普通人成长"],
      romance: null,
      idea: "核心故事想法",
      must_have: ["系统", "成长"],
      nice_to_have: [],
      exclude: ["悲剧结局"],
      chapter_target_chars: 2200,
      daily_chapters: 2,
      reserve_target: 5,
      require_plan_confirmation: true,
    });
  });

  it("removes invalid tags when switching channel", async () => {
    const store = useNovelCreateStore();
    await store.loadCatalog();
    store.form.experiences = ["爽文"];
    store.form.elements = ["系统"];
    store.setChannel("女频");
    expect(store.form.experiences).toEqual([]);
    expect(store.form.elements).toEqual([]);
    expect(store.channelWarning).toContain("女频");
  });
});
