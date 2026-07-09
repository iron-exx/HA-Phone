import { describe, expect, it } from "vitest";

import {
  buildLinphoneConfigUri,
  buildLinphoneQrPayload,
  buildProvisioningUrl,
} from "./linphoneProvisioning";

describe("Linphone provisioning helpers", () => {
  const path = "/api/linphone/provision/test-token";
  const origin = "http://pbx.example.local";

  it("builds the direct provisioning URL from the visible browser origin", () => {
    expect(buildProvisioningUrl(path, origin)).toBe(
      "http://pbx.example.local/api/linphone/provision/test-token"
    );
  });

  it("keeps ports, https and Home Assistant ingress paths", () => {
    expect(
      buildProvisioningUrl(
        path,
        "https://pbx.example.local:8123",
        "/api/hassio_ingress/abc123"
      )
    ).toBe(
      "https://pbx.example.local:8123/api/hassio_ingress/abc123/api/linphone/provision/test-token"
    );
  });

  it("builds the OS launch URI with a single linphone-config colon", () => {
    expect(buildLinphoneConfigUri(path, origin)).toBe(
      "linphone-config:http://pbx.example.local/api/linphone/provision/test-token"
    );
  });

  it("keeps the QR payload as the raw provisioning URL", () => {
    expect(buildLinphoneQrPayload(path, origin)).toBe(
      "http://pbx.example.local/api/linphone/provision/test-token"
    );
    expect(buildLinphoneQrPayload(path, origin)).not.toContain("linphone-config:");
  });
});
