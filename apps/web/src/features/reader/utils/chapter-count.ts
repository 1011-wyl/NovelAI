const CHAPTER_TITLE_LINE = /^\s*#*\s*第\s*[0-9零〇一二三四五六七八九十百千万两]+\s*章(?:\s|[-—:：·.、]|$)/;

function normalizeNewlines(text: string) {
  return String(text ?? "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

export function countNonWhitespaceChars(text: string) {
  return Array.from(normalizeNewlines(text)).filter((char) => !/\s/u.test(char)).length;
}

export function countChapterChars(text: string) {
  const normalized = normalizeNewlines(text);
  const newline = normalized.indexOf("\n");
  if (newline < 0) return countNonWhitespaceChars(normalized);
  const firstLine = normalized.slice(0, newline);
  const body = CHAPTER_TITLE_LINE.test(firstLine) ? normalized.slice(newline + 1) : normalized;
  return countNonWhitespaceChars(body);
}
