// URLs here are consumed by the Linphone APP ON THE PHONE, not by this
// browser session. The phone has no Home Assistant login, so it can NEVER
// fetch anything behind HA ingress (`:8123/api/hassio_ingress/...` returns
// 401 without an authenticated HA session). The only address a phone can
// reach is the add-on's own FastAPI, served directly on port 80 of the host
// (host_network) - which is why the port AND any ingress prefix from the
// browser's location must be dropped, not preserved.
export function buildProvisioningUrl(path: string, hostname = window.location.hostname) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `http://${hostname}${normalizedPath}`;
}

export function buildLinphoneConfigUri(path: string, hostname = window.location.hostname) {
  return `linphone-config:${buildProvisioningUrl(path, hostname)}`;
}

export function buildLinphoneQrPayload(path: string, hostname = window.location.hostname) {
  return buildProvisioningUrl(path, hostname);
}
