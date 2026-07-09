function currentIngressPath() {
  const raw = (window as Window & { __INGRESS_PATH__?: string }).__INGRESS_PATH__ ?? "";
  return raw.replace(/\/+$/, "");
}

function normalizePath(path: string) {
  return path.startsWith("/") ? path : `/${path}`;
}

export function buildProvisioningUrl(
  path: string,
  origin = window.location.origin,
  ingressPath = currentIngressPath()
) {
  if (/^https?:\/\//i.test(path)) return path;

  const normalizedPath = normalizePath(path);
  const normalizedIngress = ingressPath ? normalizePath(ingressPath).replace(/\/+$/, "") : "";
  const prefix =
    normalizedIngress && !normalizedPath.startsWith(`${normalizedIngress}/`)
      ? normalizedIngress
      : "";

  return `${origin.replace(/\/+$/, "")}${prefix}${normalizedPath}`;
}

export function buildLinphoneConfigUri(
  path: string,
  origin = window.location.origin,
  ingressPath = currentIngressPath()
) {
  return `linphone-config:${buildProvisioningUrl(path, origin, ingressPath)}`;
}

export function buildLinphoneQrPayload(
  path: string,
  origin = window.location.origin,
  ingressPath = currentIngressPath()
) {
  return buildProvisioningUrl(path, origin, ingressPath);
}
