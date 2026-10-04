declare module "*.js" {
  // Chart adapters remain imperative JS and are typed loosely at the boundary.
  const value: unknown;
  export = value;
}

declare module "./runtime.js" {
  export function createChartRuntime(helpers: Record<string, unknown>): Record<string, unknown>;
}

declare module "./bar-chart.js" {
  export function renderBarChart(
    container: HTMLElement,
    model: unknown,
    runtime: Record<string, unknown>
  ): void;
}

declare module "./line-chart.js" {
  export function renderLineChart(
    container: HTMLElement,
    model: unknown,
    runtime: Record<string, unknown>
  ): void;
}

declare module "./donut-chart.js" {
  export function renderDonutChart(
    container: HTMLElement,
    model: unknown,
    runtime: Record<string, unknown>
  ): void;
}

declare module "./year-heatmap.js" {
  export function renderYearHeatmap(
    container: HTMLElement,
    model: unknown,
    runtime: Record<string, unknown>
  ): void;
}
