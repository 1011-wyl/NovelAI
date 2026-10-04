import { onBeforeUnmount, shallowRef } from "vue";
import { formatLocalDate } from "../lib/date";
import { formatCompact, formatNumber, formatSeconds } from "../lib/format";
import { createChartRuntime } from "../charts/runtime.js";

function escapeHtml(value: string): string {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function useAnalyticsChartRuntime() {
  const runtime = shallowRef(
    createChartRuntime({
      escapeHtml,
      formatCompact,
      formatSeconds,
      formatNumber,
      formatLocalDate,
    }) as {
      cleanupContainer: (container: HTMLElement) => void;
      destroyChart: (container: HTMLElement) => void;
      destroyAll: () => void;
      observeResize: (container: HTMLElement, render: () => void) => void;
      renderChartState: (
        container: HTMLElement,
        options: { loading?: boolean; error?: string; empty?: boolean; onRetry?: (() => void) | null }
      ) => void;
      showTooltip: (text: string, x: number, y: number) => void;
      hideTooltip: () => void;
      escapeHtml: (value: string) => string;
      formatCompact: typeof formatCompact;
      formatSeconds: typeof formatSeconds;
      formatNumber: typeof formatNumber;
      formatLocalDate: typeof formatLocalDate;
    }
  );

  onBeforeUnmount(() => {
    runtime.value.destroyAll();
  });

  return runtime;
}
