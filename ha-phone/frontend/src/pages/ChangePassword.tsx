import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** First-login mandatory password change (SEC-04, must_change_password gate). */
export default function ChangePassword() {
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (pw.length < 12) {
      setError("Password must be at least 12 characters");
      return;
    }
    if (pw !== confirm) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      const resp = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_password: pw }),
      });
      if (resp.status === 401) {
        setError("Session expired — please sign in again");
        navigate("/login");
        return;
      }
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        setError(data?.detail ?? "Could not change password");
        return;
      }
      // Flag cleared — go to dashboard
      navigate("/");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center">
          <img src="/haphone-logo.svg" alt="HA-Phone" className="size-16 mb-2" />
          <CardTitle>Set a New Password</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            First login — choose a new admin password (at least 12 characters).
          </p>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="new-password">New password</Label>
              <Input
                id="new-password"
                type="password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                autoFocus
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm password</Label>
              <Input
                id="confirm-password"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Saving…" : "Save & Continue"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
