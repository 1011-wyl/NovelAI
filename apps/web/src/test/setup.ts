import { config } from "@vue/test-utils";

config.global.stubs = {
  teleport: true,
};

class LocalStorageMock {
  private store = new Map<string, string>();

  clear() {
    this.store.clear();
  }

  getItem(key: string) {
    return this.store.has(key) ? this.store.get(key)! : null;
  }

  setItem(key: string, value: string) {
    this.store.set(key, String(value));
  }

  removeItem(key: string) {
    this.store.delete(key);
  }
}

Object.defineProperty(window, "localStorage", {
  value: new LocalStorageMock(),
  configurable: true,
});
