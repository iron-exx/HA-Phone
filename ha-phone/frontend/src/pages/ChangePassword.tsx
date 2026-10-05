import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ShieldCheck } from "lucide-react";
import Logo from "@/components/Logo";

export default function ChangePassword() {
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (pw.length < 12) { setError("Mindestens 12 Zeichen erforderlich"); return; }
    if (pw !== confirm) { setError("Passwörter stimmen nicht überein"); return; }
    setLoading(true);
    try {
      const resp = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_password: pw }),
      });
      if (resp.status === 401) { navigate("/login"); return; }
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        setError(data?.detail ?? "Passwort konnte nicht gesetzt werden");
        return;
      }
      navigate("/");
    } finally {
      setLoading(false);
    }
  }

  const strength =
    pw.length < 12
      ? { bar: "bg-end", text: "text-end", label: "Zu kurz" }
      : pw.length < 16
        ? { bar: "bg-door", text: "text-door", label: "Gut" }
        : { bar: "bg-answer", text: "text-answer", label: "Stark" };

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-background p-4">
      {/* Card */}
      <div className="relative z-10 w-full max-w-sm rounded-card border border-hair bg-card p-8 shadow-2xl">
        {/* Logo + header */}
        <div className="mb-8 flex flex-col items-center gap-4">
          <div className="relative">
            <Logo
              className="h-16 w-16"
            />
            <span className="absolute -bottom-1 -right-1 grid h-6 w-6 place-items-center rounded-full bg-brand text-brand-ink">
              <ShieldCheck className="h-3.5 w-3.5" />
            </span>
          </div>
          <div className="text-center">
            <h1 className="font-display text-brand-title text-xl font-semibold tracking-tight">Passwort ändern erforderlich</h1>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Das aktuelle Passwort ist ein Standard- oder Erstpasswort — wähle ein sicheres Admin-Passwort.
            </p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="new-password"
              className="block text-xs font-medium uppercase tracking-widest text-muted-foreground">
              Neues Passwort
              <span className="ml-1 normal-case font-normal">(min. 12 Zeichen)</span>
            </label>
            <Input id="new-password" type="password" value={pw}
              onChange={(e) => setPw(e.target.value)}
              autoFocus required autoComplete="new-password" className="h-11 font-mono text-base" />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="confirm-password"
              className="block text-xs font-medium uppercase tracking-widest text-muted-foreground">
              Passwort bestätigen
            </label>
            <Input id="confirm-password" type="password" value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required autoComplete="new-password" className="h-11 font-mono text-base" />
          </div>

          {/* Password strength hint */}
          {pw.length > 0 && (
            <div className="flex items-center gap-2">
              <div className="h-1 flex-1 overflow-hidden rounded-full bg-raised">
                <div className={`h-full rounded-full transition-all duration-300 ${strength.bar}`}
                  style={{ width: `${Math.min(100, (pw.length / 20) * 100)}%` }} />
              </div>
              <span className={`text-xs ${strength.text}`}>{strength.label}</span>
            </div>
          )}

          {error && (
            <div className="rounded-ctl bg-end-soft px-3 py-2 text-sm font-semibold text-end">
              {error}
            </div>
          )}

          <Button type="submit" disabled={loading}
            className="mt-2 h-11 w-full cursor-pointer text-sm font-semibold">
            {loading ? "Speichert…" : "Speichern & Weiter"}
          </Button>
        </form>
      </div>
    </div>
  );
}
