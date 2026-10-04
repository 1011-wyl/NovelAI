import { describe, expect, it } from "vitest";
import { defineComponent, nextTick } from "vue";
import { mount } from "@vue/test-utils";
import { useActionMenu } from "./useActionMenu";

const Host = defineComponent({
  setup() {
    const menu = useActionMenu();
    return { ...menu };
  },
  template: `
    <div ref="menuRootRef" @keydown="onMenuKeydown">
      <button type="button" aria-haspopup="menu" @click="toggleMenu">更多操作</button>
      <div v-if="menuOpen" role="menu">
        <button type="button" role="menuitem">修改书名</button>
        <button type="button" role="menuitem">删除</button>
      </div>
    </div>
  `,
});

describe("useActionMenu", () => {
  it("supports Escape/arrows/Home/End and restores focus", async () => {
    const wrapper = mount(Host, { attachTo: document.body });
    const trigger = wrapper.get('button[aria-haspopup="menu"]');
    await trigger.trigger("click");
    await nextTick();
    const items = wrapper.findAll('[role="menuitem"]');
    expect(items).toHaveLength(2);
    expect(document.activeElement).toBe(items[0].element);

    await wrapper.trigger("keydown", { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[1].element);
    await wrapper.trigger("keydown", { key: "Home" });
    expect(document.activeElement).toBe(items[0].element);
    await wrapper.trigger("keydown", { key: "End" });
    expect(document.activeElement).toBe(items[1].element);
    await wrapper.trigger("keydown", { key: "Escape" });
    expect(wrapper.vm.menuOpen).toBe(false);
    expect(document.activeElement).toBe(trigger.element);
    wrapper.unmount();
  });

  it("closes when clicking outside", async () => {
    const wrapper = mount(Host, { attachTo: document.body });
    await wrapper.get('button[aria-haspopup="menu"]').trigger("click");
    await nextTick();
    document.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true }));
    expect(wrapper.vm.menuOpen).toBe(false);
    wrapper.unmount();
  });
});
