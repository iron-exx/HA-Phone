import { LogOut } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { SectionCard } from "@/components/SectionCard";
import { Button } from "@/components/ui/button";
import { useLogout } from "@/lib/useLogout";

export default function Account() {
  const logout = useLogout();
  return (
    <div className="grid gap-4">
      <PageHeader />
      <SectionCard icon={LogOut} tone="end" title="Abmelden" description="Beendet die Sitzung in diesem Browser.">
        <div>
          <Button variant="outline" onClick={() => void logout()}>Abmelden</Button>
        </div>
      </SectionCard>
    </div>
  );
}
