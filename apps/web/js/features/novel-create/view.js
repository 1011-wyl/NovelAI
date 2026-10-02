import { escapeHtml as defaultEscapeHtml } from "../../core/dom.js";
import { createNovelCreateApi } from "./api.js";
import { channelTags, buildGenreOptions, buildChipGroupHtml, buildRomanceOptions } from "./tags.js";
import { mountNovelCreateTemplate } from "./template.js";

function splitList(value) {
  return String(value || "")
    .split(/[，,]/)
    .map((x) => x.trim())
    .filter(Boolean);
}

export function createNovelCreateView({ api: request, notify, busy, escapeHtml, onCreated } = {}) {
  const esc = escapeHtml || defaultEscapeHtml;
  const api = createNovelCreateApi(request);
  let host = null;
  let form = null;
  let catalog = null;
  let tagsLoaded = false;
  let tagsLoading = null;
  let viewActive = false;
  let mounted = false;
  let destroyed = false;
  let listenerAbort = null;
  let inFlight = false;
  let submitController = null;

  function $(selector) {
    return (host || document).querySelector(selector);
  }

  function $$(selector) {
    return [...(host || document).querySelectorAll(selector)];
  }

  function renderTagCatalog(channel) {
    if (!catalog) return;
    const tags = channelTags(catalog, channel);
    if (!tags) return;
    const genreSelect = $("#genreSelect");
    if (genreSelect) genreSelect.innerHTML = buildGenreOptions(tags, esc);
    ["experiences", "elements", "protagonist_tags"].forEach((group) => {
      const values = tags[group];
      const target = (host || document).querySelector(`[data-check-group="${group}"]`);
      if (!target) return;
      target.innerHTML = buildChipGroupHtml(group, values, esc);
    });
    const romanceSelect = $("#romanceSelect");
    if (romanceSelect) romanceSelect.innerHTML = buildRomanceOptions(tags, esc);
    const note = $("#tagCatalogNote");
    if (note) note.textContent = `${channel}标签已切换。${catalog.note}`;
  }

  async function loadTags() {
    if (tagsLoaded && catalog) {
      const selected =
        $('#createForm input[name="audience_channel"]:checked')?.value || catalog.default_channel;
      renderTagCatalog(selected);
      return catalog;
    }
    if (tagsLoading) return tagsLoading;
    tagsLoading = (async () => {
      try {
        catalog = await api.loadTagCatalog();
        tagsLoaded = true;
        const selected =
          $('#createForm input[name="audience_channel"]:checked')?.value || catalog.default_channel;
        renderTagCatalog(selected);
        return catalog;
      } catch (error) {
        if (error.stale) return null;
        notify?.(error.message, true);
        throw error;
      } finally {
        tagsLoading = null;
      }
    })();
    return tagsLoading;
  }

  function buildPayload(event) {
    const formData = new FormData(event.target);
    const checked = (name) =>
      [...event.target.querySelectorAll(`input[name="${name}"]:checked`)].map((input) => input.value);
    return {
      preferred_title: formData.get("preferred_title") || null,
      audience_channel: formData.get("audience_channel"),
      genre: formData.get("genre"),
      experiences: checked("experiences"),
      elements: checked("elements"),
      protagonist_tags: checked("protagonist_tags"),
      romance: formData.get("romance") || null,
      idea: formData.get("idea"),
      must_have: splitList(formData.get("must_have")),
      nice_to_have: splitList(formData.get("nice_to_have")),
      exclude: splitList(formData.get("exclude")),
      chapter_target_chars: Number(formData.get("chapter_target_chars")),
      daily_chapters: Number(formData.get("daily_chapters")),
      reserve_target: Number(formData.get("reserve_target")),
      require_plan_confirmation: formData.has("require_plan_confirmation"),
    };
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (destroyed || inFlight) return;
    inFlight = true;
    if (submitController) submitController.abort();
    submitController = new AbortController();
    const payload = buildPayload(event);
    try {
      busy?.(true);
      const project = await api.createNovel(payload, { signal: submitController.signal });
      notify?.("创作方案已经生成，请检查后确认。");
      onCreated?.(project);
    } catch (error) {
      if (error.stale || error.name === "AbortError") return;
      notify?.(error.message, true);
    } finally {
      inFlight = false;
      submitController = null;
      busy?.(false);
    }
  }

  function bindEvents() {
    if (listenerAbort) listenerAbort.abort();
    listenerAbort = new AbortController();
    const { signal } = listenerAbort;
    form?.addEventListener("submit", handleSubmit, { signal });
    $$('#createForm input[name="audience_channel"]').forEach((input) => {
      input.addEventListener("change", () => renderTagCatalog(input.value), { signal });
    });
  }

  function mount(mountHost) {
    if (destroyed) return;
    host = mountHost;
    if (!host) return;
    form = mountNovelCreateTemplate(host);
    if (mounted) {
      bindEvents();
      return;
    }
    bindEvents();
    mounted = true;
  }

  function activate() {
    if (destroyed || !mounted) return;
    viewActive = true;
    void loadTags();
  }

  function deactivate() {
    viewActive = false;
  }

  function reset() {
    if (!form) return;
    form.reset();
    const male = form.querySelector('input[name="audience_channel"][value="男频"]');
    if (male) male.checked = true;
    if (catalog) {
      renderTagCatalog(catalog.default_channel || "男频");
    }
  }

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    viewActive = false;
    if (submitController) {
      submitController.abort();
      submitController = null;
    }
    api.abortAll();
    if (listenerAbort) {
      listenerAbort.abort();
      listenerAbort = null;
    }
    inFlight = false;
    mounted = false;
    form = null;
    host = null;
  }

  return {
    mount,
    activate,
    deactivate,
    reset,
    destroy,
    loadTags,
  };
}
