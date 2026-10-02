export function mountDashboardHero(host) {
  if (!host) return null;
  const existing = host.querySelector(".hero-card") || document.querySelector("#dashboardView .hero-card");
  if (existing) return existing;
  return null;
}
