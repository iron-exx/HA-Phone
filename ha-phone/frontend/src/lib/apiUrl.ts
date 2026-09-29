/**
 * Backend URL for places that do not go through fetch (img src, audio src, links).
 * Under the Home Assistant ingress the SPA is served from /api/hassio_ingress/<token>/,
 * so a root-relative "/api/..." would reach HA Core instead of this add-on. The fetch
 * wrapper in main.tsx uses the same function.
 */
export function apiUrl(path: string): string {
  const ingressPath: string = (window as { __INGRESS_PATH__?: string }).__INGRESS_PATH__ ?? "";
  return ingressPath && path.startsWith("/api/") ? ingressPath + path : path;
}
