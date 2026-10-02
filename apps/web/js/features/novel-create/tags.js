export function channelTags(catalog, channel) {
  if (!catalog?.channels) return null;
  return catalog.channels[channel] || null;
}

export function buildGenreOptions(tags, escapeHtml) {
  if (!tags?.genres?.length) return "";
  return tags.genres
    .map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`)
    .join("");
}

export function buildChipGroupHtml(groupName, values, escapeHtml) {
  if (!Array.isArray(values)) return "";
  return values
    .map(
      (value, index) =>
        `<label class="chip"><input type="checkbox" name="${groupName}" value="${escapeHtml(value)}" ${index === 0 ? "checked" : ""}><span>${escapeHtml(value)}</span></label>`
    )
    .join("");
}

export function buildRomanceOptions(tags, escapeHtml) {
  if (!tags?.romance?.length) return "";
  return tags.romance
    .map(
      (value, index) =>
        `<option value="${index === 0 ? "" : escapeHtml(value)}">${escapeHtml(value)}</option>`
    )
    .join("");
}
