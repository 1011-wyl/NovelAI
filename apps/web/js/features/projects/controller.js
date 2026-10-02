export const PROJECT_STORAGE_KEY = "novelAgentProject";

export function createProjectsController({ state, api, notify, onDetailLoaded, onEmpty } = {}) {
  let detailGeneration = 0;

  function setProjectsAndSelect(items) {
    const projects = Array.isArray(items) ? items : [];
    state.setProjects(projects);
    const remembered = localStorage.getItem(PROJECT_STORAGE_KEY);
    const currentId = state.selectedId;
    if (!currentId || !projects.some((p) => p.id === currentId)) {
      const nextId = projects.some((p) => p.id === remembered) ? remembered : projects[0]?.id || null;
      state.select(nextId);
    }
  }

  async function loadSelected() {
    const generation = ++detailGeneration;
    const selectedId = state.selectedId;
    if (!selectedId) {
      state.setDetail(null);
      state.setBriefVersions([]);
      onEmpty?.();
      return null;
    }

    state.setStatus("loading");
    state.setError(null);
    try {
      const detail = await api.getDetail(selectedId);
      if (generation !== detailGeneration || state.selectedId !== selectedId) {
        return null;
      }
      state.setDetail(detail);
      state.setStatus("ready");
      onDetailLoaded?.(detail);
      return detail;
    } catch (error) {
      if (error.stale || generation !== detailGeneration) return null;
      state.setError(error);
      state.setStatus("error");
      notify?.(error.message, true);
      throw error;
    }
  }

  async function selectProject(id) {
    const projectId = id || null;
    state.select(projectId);
    if (projectId) {
      localStorage.setItem(PROJECT_STORAGE_KEY, projectId);
    } else {
      localStorage.removeItem(PROJECT_STORAGE_KEY);
    }
    return loadSelected();
  }

  function clearSelection() {
    detailGeneration += 1;
    api?.abort?.("detail");
    state.select(null);
    localStorage.removeItem(PROJECT_STORAGE_KEY);
    state.setDetail(null);
    state.setBriefVersions([]);
  }

  return {
    setProjectsAndSelect,
    loadSelected,
    selectProject,
    clearSelection,
  };
}
