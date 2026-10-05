import { NavLink } from "react-router-dom";
import { NAV_GROUPS, type NavItem } from "@/nav";
import { cn } from "@/lib/utils";
import { BrandMark } from "./BrandMark";

function SidebarLink({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "relative flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-[13.5px] font-bold transition-colors motion-reduce:transition-none",
          isActive
            ? "bg-blue-soft text-foreground before:absolute before:-left-3 before:top-[7px] before:bottom-[7px] before:w-1 before:rounded-r before:bg-brand before:content-['']"
            : "text-muted-foreground hover:bg-raised hover:text-foreground",
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon aria-hidden="true" className={cn("size-[18px] shrink-0", isActive && "text-blue")} />
          {item.label}
        </>
      )}
    </NavLink>
  );
}

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Hauptmenü" className="flex h-full flex-col gap-3.5 px-3 py-[18px]">
      <div className="flex items-center gap-2.5 px-2 pb-2 pt-0.5">
        <BrandMark />
        <div>
          <span className="block font-display text-[17px] font-extrabold leading-tight">HA-Phone</span>
          <span className="text-[11.5px] font-semibold text-faint">Telefonanlage</span>
        </div>
      </div>
      <div className="flex-1 space-y-3.5 overflow-y-auto">
        {NAV_GROUPS.map((group) =>
          group.label ? (
            <div key={group.label} role="group" aria-label={group.label} className="grid gap-0.5">
              <span aria-hidden="true" className="px-2.5 pb-1 pt-1.5 text-[11px] font-extrabold uppercase tracking-[0.08em] text-faint">
                {group.label}
              </span>
              {group.items.map((item) => <SidebarLink key={item.to} item={item} onNavigate={onNavigate} />)}
            </div>
          ) : (
            <div key="start" className="grid gap-0.5">
              {group.items.map((item) => <SidebarLink key={item.to} item={item} onNavigate={onNavigate} />)}
            </div>
          ),
        )}
      </div>
    </nav>
  );
}
