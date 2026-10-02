export function createNovelCreateApi(request) {
  const controllers = {
    tags: null,
    create: null,
  };
  const requestIds = {
    tags: 0,
    create: 0,
  };

  function abort(key) {
    if (controllers[key]) {
      controllers[key].abort();
      controllers[key] = null;
    }
    requestIds[key] += 1;
  }

  function abortAll() {
    Object.keys(controllers).forEach(abort);
  }

  async function fetchWithGeneration(path, key, options = {}) {
    abort(key);
    const controller = new AbortController();
    controllers[key] = controller;
    const id = ++requestIds[key];
    try {
      const payload = await request(path, {
        ...options,
        signal: options.signal || controller.signal,
      });
      if (id !== requestIds[key]) {
        const err = new Error("stale");
        err.stale = true;
        throw err;
      }
      return payload;
    } catch (error) {
      if (error.name === "AbortError" || error.stale) {
        const err = new Error("stale");
        err.stale = true;
        throw err;
      }
      throw error;
    }
  }

  async function loadTagCatalog({ signal } = {}) {
    return fetchWithGeneration("/api/tags", "tags", signal ? { signal } : {});
  }

  async function createNovel(payload, { signal } = {}) {
    return fetchWithGeneration("/api/novels", "create", {
      method: "POST",
      body: JSON.stringify(payload),
      ...(signal ? { signal } : {}),
    });
  }

  return {
    abort,
    abortAll,
    loadTagCatalog,
    createNovel,
  };
}
