export function buildProvisioningUrl(path: string, hostname = window.location.hostname) {
  return `http://${hostname}${path}`;
}

export function buildLinphoneConfigUri(path: string, hostname = window.location.hostname) {
  return `linphone-config:${buildProvisioningUrl(path, hostname)}`;
}

export function buildLinphoneQrPayload(path: string, hostname = window.location.hostname) {
  return buildProvisioningUrl(path, hostname);
}
