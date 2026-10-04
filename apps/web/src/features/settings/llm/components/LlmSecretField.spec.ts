import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import LlmSecretField from "./LlmSecretField.vue";

describe("LlmSecretField", () => {
  it("toggles visibility and never snapshots a complete saved key", async () => {
    const wrapper = mount(LlmSecretField, {
      props: {
        modelValue: "",
        mask: "••••1234",
        show: false,
      },
    });
    expect(wrapper.text()).toContain("已保存密钥：••••1234");
    expect(wrapper.html()).not.toContain("sk-live-should-never-appear");
    const input = wrapper.get("input");
    expect(input.attributes("type")).toBe("password");
    await wrapper.get("button.toggle").trigger("click");
    expect(wrapper.emitted("update:show")?.[0]).toEqual([true]);
    await wrapper.setProps({ show: true, modelValue: "typed-secret" });
    expect(wrapper.get("input").attributes("type")).toBe("text");
    expect(wrapper.html()).not.toContain("sk-live-should-never-appear");
  });
});
