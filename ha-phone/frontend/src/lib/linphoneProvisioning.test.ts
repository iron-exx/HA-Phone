import { describe, expect, it } from "vitest";

import {
  buildLinphoneConfigUri,
  buildLinphoneQrPayload,
  buildProvisioningUrl,
} from "./linphoneProvisioning";

describe("Linphone provisioning helpers", () => {
  const path = "/api/linphone/provision/test-token";
  const host = "pbx.example.local";

  it("builds the direct provisioning URL without an explicit port", () => {
    expect(buildProvisioningUrl(path, host)).toBe(
      "http://pbx.example.local/api/linphone/provision/test-token"
    );
  });

  it("builds the OS launch URI with a single linphone-config colon", () => {
    expect(buildLinphoneConfigUri(path, host)).toBe(
      "linphone-config:http://pbx.example.local/api/linphone/provision/test-token"
    );
  });

  it("keeps the QR payload as the raw provisioning URL", () => {
    expect(buildLinphoneQrPayload(path, host)).toBe(
      "http://pbx.example.local/api/linphone/provision/test-token"
    );
    expect(buildLinphoneQrPayload(path, host)).not.toContain("linphone-config:");
  });
});
