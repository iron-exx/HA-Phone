import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Logo from "@/components/Logo";

export default function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (resp.status === 401) { setError("Falsches Passwort"); return; }
      if (resp.status === 429) {
        const data = await resp.json().catch(() => ({}));
        setError(data?.detail ?? "Zu viele Fehlversuche — bitte später erneut versuchen");
        return;
      }
      if (!resp.ok) { setError("Anmeldung fehlgeschlagen — bitte erneut versuchen"); return; }
      const data = await resp.json();
      const mustChange = data.password_change_required || data.must_change_password;
      navigate(mustChange ? "/change-password" : "/");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-background p-4">
      {/* Card */}
      <div className="relative z-10 w-full max-w-sm rounded-card border border-hair bg-card p-8 shadow-2xl">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-4">
          <Logo
            className="h-20 w-20"
          />
          <div className="text-center">
            <h1 className="font-display text-brand-title text-2xl font-semibold tracking-tight">HA-Phone</h1>
            <p className="mt-1 text-xs text-muted-foreground">PBX Admin</p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="password"
              className="block text-xs font-medium uppercase tracking-widest text-muted-foreground">
              Passwort
            </label>
            <Input id="password" type="password" value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus required autoComplete="new-password" className="h-11 font-mono text-base" placeholder="••••••••" />
          </div>

          {error && (
            <div className="rounded-ctl bg-end-soft px-3 py-2 text-sm font-semibold text-end">
              {error}
            </div>
          )}

          <Button type="submit" disabled={loading}
            className="mt-2 h-11 w-full cursor-pointer text-sm font-semibold">
            {loading ? "Anmelden…" : "Anmelden"}
          </Button>
        </form>
      </div>
    </div>
  );
}
