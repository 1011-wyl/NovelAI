export function createProjectsState() {
  const listeners = new Set();
  const data = {
    projects: [],
    selectedId: null,
    detail: null,
    briefVersions: [],
    status: "idle",
    error: null,
  };

  function notify() {
    const snapshot = getSnapshot();
    listeners.forEach((listener) => {
      try {
        listener(snapshot);
      } catch (error) {
        console.error(error);
      }
    });
  }

  function getSnapshot() {
    return {
      projects: data.projects,
      selectedId: data.selectedId,
      detail: data.detail,
      briefVersions: data.briefVersions,
      status: data.status,
      error: data.error,
    };
  }

  function subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  function setProjects(items) {
    data.projects = Array.isArray(items) ? items : [];
    notify();
  }

  function select(projectId) {
    data.selectedId = projectId || null;
    notify();
  }

  function setDetail(detail) {
    data.detail = detail ?? null;
    notify();
  }

  function setBriefVersions(items) {
    data.briefVersions = Array.isArray(items) ? items : [];
    notify();
  }

  function setStatus(status) {
    data.status = status || "idle";
    notify();
  }

  function setError(error) {
    data.error = error ?? null;
    notify();
  }

  function reset() {
    data.projects = [];
    data.selectedId = null;
    data.detail = null;
    data.briefVersions = [];
    data.status = "idle";
    data.error = null;
    notify();
  }

  return {
    get projects() {
      return data.projects;
    },
    get selectedId() {
      return data.selectedId;
    },
    get detail() {
      return data.detail;
    },
    get briefVersions() {
      return data.briefVersions;
    },
    get status() {
      return data.status;
    },
    get error() {
      return data.error;
    },
    subscribe,
    getSnapshot,
    setProjects,
    select,
    setDetail,
    setBriefVersions,
    setStatus,
    setError,
    reset,
  };
}
