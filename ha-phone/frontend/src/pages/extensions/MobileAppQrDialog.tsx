import { useEffect, useState } from "react";
import { toast } from "sonner";
import QRCode from "qrcode";
import { Copy } from "lucide-react";
import type { Extension, ProvisioningTokenOut } from "@/types/api";
import { apiErrorMessage, toErrorMessage } from "@/lib/apiError";
import { copyToClipboard } from "@/lib/clipboard";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

// Kopplungs-QR bewusst schwarz auf weiß – nur so liest ihn jeder Scanner, in hellem wie dunklem Design.
const QR_DARK = "#000000";
const QR_LIGHT = "#FFFFFF";

// QR pairing dialog for the native HA-Phone companion app (Android for now -
// the iOS app doesn't exist yet, see the note in the dialog body). Replaces
// the old LinphoneQrDialog, which provisioned the generic third-party
// Linphone app; that path is unreliable for background calls, which is
// exactly why the native app exists. This dialog starts a fresh, short-lived
// (5 min) pairing token per open via POST /api/mobile/provision/start rather
// than reusing a long-lived per-extension token like Linphone's did.
export function MobileAppQrDialog({
  extension,
  onClose,
}: {
  extension: Extension;
  onClose: () => void;
}) {
  const [loading, setLoading] = useState(true);
  const [qrCodeDataUrl, setQrCodeDataUrl] = useState("");
  const [provisioning, setProvisioning] = useState<ProvisioningTokenOut | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const resp = await fetch("/api/mobile/provision/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            extension_number: extension.number,
            platform: "android",
            device_name: "",
          }),
        });
        if (!resp.ok) throw new Error(await apiErrorMessage(resp, "QR-Code konnte nicht erstellt werden."));
        const data: ProvisioningTokenOut = await resp.json();
        if (cancelled) return;
        setProvisioning(data);
        const dataUrl = await QRCode.toDataURL(data.qr_code_url, {
          width: 320,
          margin: 2,
          color: {
            dark: QR_DARK,
            light: QR_LIGHT,
          },
        });
        if (!cancelled) setQrCodeDataUrl(dataUrl);
      } catch (err) {
        if (!cancelled) toast.error(toErrorMessage(err, "QR-Code konnte nicht erstellt werden."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [extension.id, extension.number]);

  async function copyProvisioningLink() {
    if (!provisioning) return;
    await copyToClipboard(provisioning.qr_code_url, "Provisioning-Link kopiert.");
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>HA-Phone App für Nebenstelle {extension.number}</DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="space-y-3">
            <Skeleton className="mx-auto h-72 w-72" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : provisioning ? (
          <div className="space-y-4">
            <div
              className="mx-auto flex w-full max-w-[320px] items-center justify-center rounded-card border border-hair bg-raised p-4"
            >
              {qrCodeDataUrl ? (
                <img
                  src={qrCodeDataUrl}
                  alt={`HA-Phone Kopplungs-QR für Nebenstelle ${extension.number}`}
                  className="h-72 w-72 rounded-ctl"
                />
              ) : (
                <Skeleton className="h-72 w-72" />
              )}
            </div>

            <div className="space-y-2">
              <p className="text-sm text-foreground">
                {extension.display_name} ({extension.number})
              </p>
              <p className="text-xs text-muted-foreground">
                In der HA-Phone App auf „QR-Code scannen“ tippen. Der Code ist 5 Minuten gültig.
                Aktuell nur für Android, die iOS-App folgt.
              </p>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">Provisioning-Link</p>
              <div className="flex gap-2">
                <Input
                  readOnly
                  value={provisioning.qr_code_url}
                  className="font-mono text-xs"
                />
                <Button type="button" variant="outline" onClick={copyProvisioningLink} className="shrink-0">
                  <Copy className="mr-2 h-4 w-4" />
                  Kopieren
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Schließen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
