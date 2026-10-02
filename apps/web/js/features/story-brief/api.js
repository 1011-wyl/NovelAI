export function createStoryBriefApi(request) {
  const controllers = {
    update: null,
    regenerate: null,
    versions: null,
    restore: null,
  };
  const requestIds = {
    update: 0,
    regenerate: 0,
    versions: 0,
    restore: 0,
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

  async function updateBrief(id, brief) {
    return fetchWithGeneration(`/api/novels/${id}/brief`, "update", {
      method: "PUT",
      body: JSON.stringify(brief),
    });
  }

  async function regenerateBrief(id, payload) {
    return fetchWithGeneration(`/api/novels/${id}/brief-regenerate`, "regenerate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async function listVersions(id) {
    return fetchWithGeneration(`/api/novels/${id}/brief-versions`, "versions");
  }

  async function restoreBrief(id, version) {
    return fetchWithGeneration(`/api/novels/${id}/brief-restore`, "restore", {
      method: "POST",
      body: JSON.stringify({ version }),
    });
  }

  return {
    abort,
    abortAll,
    updateBrief,
    regenerateBrief,
    listVersions,
    restoreBrief,
  };
}
