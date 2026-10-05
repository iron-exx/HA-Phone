import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { KeyRound } from "lucide-react";
import { SectionCard } from "@/components/SectionCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiErrorMessage } from "@/lib/apiError";
import { zodFormResolver } from "@/lib/zodFormResolver";

const MIN_LENGTH = 12; // wie backend/routers/auth.py

const passwordSchema = z
  .object({
    current: z.string().min(1, "Gib dein aktuelles Passwort ein."),
    password: z.string().min(MIN_LENGTH, `Mindestens ${MIN_LENGTH} Zeichen.`),
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, {
    message: "Die beiden Eingaben stimmen nicht überein.",
    path: ["confirm"],
  });

type PasswordFormValues = z.infer<typeof passwordSchema>;

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p role="alert" className="rounded-ctl bg-end-soft px-3 py-2 text-sm font-semibold text-end">{message}</p>;
}

export function PasswordChangeCard() {
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<PasswordFormValues>({
    resolver: zodFormResolver(passwordSchema),
    defaultValues: { current: "", password: "", confirm: "" },
  });
  const { errors, isSubmitting } = form.formState;

  async function onSubmit(values: PasswordFormValues) {
    setServerError(null);
    try {
      const resp = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: values.current, new_password: values.password }),
      });
      if (resp.status === 401) {
        navigate("/login");
        return;
      }
      if (!resp.ok) {
        setServerError(await apiErrorMessage(resp, "Passwort konnte nicht geändert werden."));
        return;
      }
      form.reset();
      toast.success("Passwort geändert. Es gilt ab der nächsten Anmeldung.");
    } catch {
      setServerError("Keine Verbindung zur Anlage.");
    }
  }

  return (
    <SectionCard icon={KeyRound} title="Admin-Passwort ändern" description="Freiwillig – zum Beispiel, wenn jemand anderes das Passwort kennt. Mindestens 12 Zeichen.">
      <form onSubmit={(e) => void form.handleSubmit(onSubmit)(e)} className="grid max-w-md gap-3" noValidate>
        <div className="grid gap-1.5">
          <Label htmlFor="current-password">Aktuelles Passwort</Label>
          <Input id="current-password" type="password" autoComplete="current-password" aria-invalid={!!errors.current} {...form.register("current")} />
          <FieldError message={errors.current?.message} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="new-password">Neues Passwort</Label>
          <Input id="new-password" type="password" autoComplete="new-password" aria-invalid={!!errors.password} {...form.register("password")} />
          <FieldError message={errors.password?.message} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="confirm-password">Neues Passwort wiederholen</Label>
          <Input id="confirm-password" type="password" autoComplete="new-password" aria-invalid={!!errors.confirm} {...form.register("confirm")} />
          <FieldError message={errors.confirm?.message} />
        </div>
        <FieldError message={serverError ?? undefined} />
        <div>
          <Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Speichert…" : "Passwort ändern"}</Button>
        </div>
      </form>
    </SectionCard>
  );
}
