export function createProjectsApi(request) {
  const controllers = {
    list: null,
    detail: null,
  };
  const requestIds = {
    list: 0,
    detail: 0,
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

  async function fetchJson(path, key, options = {}) {
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

  async function listProjects({ signal } = {}) {
    return fetchJson("/api/novels", "list", signal ? { signal } : {});
  }

  async function getDetail(id, { signal } = {}) {
    return fetchJson(`/api/novels/${id}`, "detail", signal ? { signal } : {});
  }

  async function confirm(id) {
    return request(`/api/novels/${id}/confirm`, { method: "POST", body: "{}" });
  }

  async function pause(id) {
    return request(`/api/novels/${id}/pause`, { method: "POST", body: "{}" });
  }

  async function resume(id) {
    return request(`/api/novels/${id}/resume`, { method: "POST", body: "{}" });
  }

  async function recover(id) {
    return request(`/api/novels/${id}/recover`, { method: "POST", body: "{}" });
  }

  async function deleteProject(id, confirmationTitle) {
    return request(`/api/novels/${id}`, {
      method: "DELETE",
      body: JSON.stringify({ confirmation_title: confirmationTitle }),
    });
  }

  return {
    abort,
    abortAll,
    listProjects,
    getDetail,
    confirm,
    pause,
    resume,
    recover,
    deleteProject,
  };
}
