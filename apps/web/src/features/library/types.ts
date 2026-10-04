import type { ProjectSummary } from "@/api/contracts";
import { mapShelfStatus } from "@/stores/projects.store";

export type { ProjectSummary };

export function formatChars(count: number): string {
  if (count >= 10000) {
    return `${(count / 10000).toFixed(count >= 100000 ? 0 : 1)} 万字`;
  }
  return `${count} 字`;
}

export function formatRelativeTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return date.toLocaleDateString("zh-CN");
}

export function coverSeed(project: ProjectSummary): number {
  let hash = 0;
  const source = `${project.id}:${project.genre}`;
  for (let i = 0; i < source.length; i += 1) {
    hash = (hash * 31 + source.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export function shelfStatusOf(project: ProjectSummary) {
  return mapShelfStatus(project);
}
