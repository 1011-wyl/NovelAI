import { nextTick, onMounted, onUnmounted, ref } from "vue";

export function useActionMenu() {
  const menuOpen = ref(false);
  const menuRootRef = ref<HTMLElement | null>(null);

  function trigger(): HTMLElement | null {
    return menuRootRef.value?.querySelector<HTMLElement>("button[aria-haspopup='menu']") ?? null;
  }

  function items(): HTMLElement[] {
    return Array.from(
      menuRootRef.value?.querySelectorAll<HTMLElement>("[role='menuitem']:not([disabled])") ?? []
    );
  }

  async function toggleMenu() {
    menuOpen.value = !menuOpen.value;
    if (menuOpen.value) {
      await nextTick();
      items()[0]?.focus();
    }
  }

  function closeMenu(restoreFocus = false) {
    if (!menuOpen.value) return;
    if (restoreFocus) trigger()?.focus();
    menuOpen.value = false;
  }

  function onMenuKeydown(event: KeyboardEvent) {
    if (!menuOpen.value) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeMenu(true);
      return;
    }
    const menuItems = items();
    if (!menuItems.length) return;
    const current = Math.max(0, menuItems.indexOf(document.activeElement as HTMLElement));
    let next = current;
    if (event.key === "ArrowDown") next = (current + 1) % menuItems.length;
    else if (event.key === "ArrowUp") next = (current - 1 + menuItems.length) % menuItems.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = menuItems.length - 1;
    else return;
    event.preventDefault();
    menuItems[next]?.focus();
  }

  function onDocumentPointerDown(event: PointerEvent) {
    const target = event.target as Node | null;
    if (menuOpen.value && target && !menuRootRef.value?.contains(target)) closeMenu();
  }

  onMounted(() => document.addEventListener("pointerdown", onDocumentPointerDown, true));
  onUnmounted(() => document.removeEventListener("pointerdown", onDocumentPointerDown, true));

  return { menuOpen, menuRootRef, toggleMenu, closeMenu, onMenuKeydown };
}
