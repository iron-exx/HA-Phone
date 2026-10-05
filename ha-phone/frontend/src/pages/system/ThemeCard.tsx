import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { SectionCard } from "@/components/SectionCard";
import type { ThemePreference } from "@/lib/theme";
import { useTheme } from "@/lib/themeContext";
import { cn } from "@/lib/utils";

const OPTIONS: { value: ThemePreference; label: string; icon: LucideIcon }[] = [
  { value: "system", label: "Wie das System", icon: Monitor },
  { value: "light", label: "Hell", icon: Sun },
  { value: "dark", label: "Dunkel", icon: Moon },
];

export function ThemeCard() {
  const { preference, setPreference } = useTheme();
  return (
    <SectionCard
      icon={Sun}
      tone="violet"
      title="Darstellung"
      description="Folgt normalerweise Home Assistant bzw. dem Gerät. Hier lässt sie sich für diesen Browser festlegen."
    >
      <div role="group" aria-label="Darstellung" className="inline-flex w-fit flex-wrap gap-0.5 rounded-full border border-hair bg-raised p-[3px]">
        {OPTIONS.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            type="button"
            aria-pressed={preference === value}
            onClick={() => setPreference(value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border border-transparent px-3 py-1.5 text-[12.5px] font-bold transition-colors",
              preference === value ? "border-hair bg-card text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>
    </SectionCard>
  );
}
