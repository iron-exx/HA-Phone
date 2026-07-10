import { describe, expect, it } from "vitest";

import {
  buildLinphoneConfigUri,
  buildLinphoneQrPayload,
  buildProvisioningUrl,
} from "./linphoneProvisioning";

describe("Linphone provisioning helpers", () => {
  const path = "/api/linphone/provision/test-token";

  it("builds the direct port-80 provisioning URL from the browser hostname", () => {
    expect(buildProvisioningUrl(path, "pbx.example.local")).toBe(
      "http://pbx.example.local/api/linphone/provision/test-token"
    );
  });

  it("never routes the phone through HA ingress or the browser port", () => {
    // Regression for the 0.7.84 bug: the phone has no HA session, so an
    // ingress URL (https://ha:8123/api/hassio_ingress/...) is a guaranteed
    // 401 for it. Only the hostname may be taken from the browser location -
    // scheme is plain http and the port is the add-on's own port 80.
    const url = buildProvisioningUrl(path, "pbx.example.local");
    expect(url).not.toContain(":8123");
    expect(url).not.toContain("hassio_ingress");
    expect(url.startsWith("http://pbx.example.local/")).toBe(true);
  });

  it("builds the OS launch URI with a single linphone-config colon", () => {
    expect(buildLinphoneConfigUri(path, "pbx.example.local")).toBe(
      "linphone-config:http://pbx.example.local/api/linphone/provision/test-token"
    );
  });

  it("keeps the QR payload as the raw provisioning URL", () => {
    expect(buildLinphoneQrPayload(path, "pbx.example.local")).toBe(
      "http://pbx.example.local/api/linphone/provision/test-token"
    );
    expect(buildLinphoneQrPayload(path, "pbx.example.local")).not.toContain("linphone-config:");
  });
});
