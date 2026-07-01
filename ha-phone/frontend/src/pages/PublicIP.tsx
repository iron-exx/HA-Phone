import { useEffect, useState } from "react";
import { toast } from "sonner";

import { type PublicIPSettings } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

export default function PublicIP() {
  const [detectedIP, setDetectedIP] = useState<string | null>(null);
  const [inputIP, setInputIP] = useState<string>("");
  const [detecting, setDetecting] = useState(true);
  const [saving, setSaving] = useState(false);

  async function detectIP() {
    setDetecting(true);
    try {
      const resp = await fetch("/api/settings/public-ip");
      if (!resp.ok) throw new Error();
      const data: PublicIPSettings = await resp.json();
      setDetectedIP(data.ip);
      if (data.ip) setInputIP(data.ip);
    } catch {
      setDetectedIP(null);
    } finally {
      setDetecting(false);
    }
  }

  // Auto-detect on mount
  useEffect(() => {
    detectIP();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSave() {
    if (!inputIP.trim()) {
      toast.error("Enter a valid IP address.");
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch("/api/settings/public-ip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ip: inputIP.trim() }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      toast.success("Configuration reloaded. Asterisk applied changes without restarting.");
    } catch {
      toast.error("Failed to save changes. Check that the PBX is running and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-8">Settings — Public IP</h1>

      <Card className="max-w-lg">
        <CardHeader>
          <span className="text-base font-semibold">External IP Address</span>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Auto-detect area */}
          <div className="space-y-2">
            <Label className="text-sm font-semibold">Detected IP</Label>
            {detecting ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Skeleton className="h-4 w-4 rounded-full" />
                <span>Detecting...</span>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <span className="text-sm font-mono">
                  {detectedIP ?? "Not detected"}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={detectIP}
                  disabled={detecting}
                >
                  Re-detect
                </Button>
              </div>
            )}
          </div>

          {/* Manual override input */}
          <div className="space-y-2">
            <Label htmlFor="external-ip" className="text-sm font-semibold">
              External IP Address
            </Label>
            <p className="text-xs text-muted-foreground">
              Enter your public IPv4 or IPv6 address. Used for SIP NAT traversal.
            </p>
            <Input
              id="external-ip"
              type="text"
              value={inputIP}
              onChange={(e) => setInputIP(e.target.value)}
              placeholder="e.g. 203.0.113.1"
            />
          </div>

          {/* Save + Reload */}
          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={saving || detecting}>
              {saving ? "Saving..." : "Save + Reload"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
