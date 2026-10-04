import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import BaseDialog from "./BaseDialog.vue";

describe("BaseDialog", () => {
  it("focuses the first interactive element, traps Tab, closes on Escape, and restores focus", async () => {
    const trigger = document.createElement("button");
    trigger.textContent = "打开";
    document.body.appendChild(trigger);
    trigger.focus();

    const wrapper = mount(BaseDialog, {
      props: { open: false, title: "测试弹窗", description: "说明" },
      slots: {
        default: '<button type="button" data-testid="first">确认</button><button type="button">取消</button>',
      },
      attachTo: document.body,
    });

    await wrapper.setProps({ open: true });
    await nextTick();
    await nextTick();

    const dialog = wrapper.find('[role="dialog"]');
    expect(dialog.exists()).toBe(true);
    expect(dialog.attributes("aria-modal")).toBe("true");
    expect(dialog.attributes("aria-label")).toBe("测试弹窗");
    expect(document.activeElement?.getAttribute("data-testid") || document.activeElement?.getAttribute("aria-label")).toBeTruthy();

    const focusable = Array.from(
      dialog.element.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    ).filter((el) => !el.hasAttribute("hidden"));
    focusable[focusable.length - 1]?.focus();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }));
    expect(document.activeElement).toBe(focusable[0]);

    focusable[0]?.focus();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true }));
    expect(document.activeElement).toBe(focusable[focusable.length - 1]);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(wrapper.emitted("close")).toBeTruthy();

    await wrapper.setProps({ open: false });
    await nextTick();
    expect(document.activeElement).toBe(trigger);

    wrapper.unmount();
    trigger.remove();
  });
});
