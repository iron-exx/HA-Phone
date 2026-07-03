import { NavLink, useNavigate } from "react-router-dom";
import Logo from "@/components/Logo";
import {
  LayoutDashboard,
  Phone,
  Network,
  GitBranch,
  Voicemail,
  Settings,
  Activity,
  Router,
  LogOut,
  PhoneIncoming,
} from "lucide-react";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/extensions", label: "Nebenstellen", icon: Phone, end: false },
  { to: "/ivr", label: "IVR-Menüs", icon: PhoneIncoming, end: false },
  { to: "/provisioning", label: "Provisioning", icon: Router, end: false },
  { to: "/trunk", label: "Trunk", icon: Network, end: false },
  { to: "/routing", label: "Routing", icon: GitBranch, end: false },
  { to: "/voicemail", label: "Voicemail", icon: Voicemail, end: false },
  { to: "/settings/public-ip", label: "Settings", icon: Settings, end: false },
  { to: "/diagnostics", label: "Diagnose", icon: Activity, end: false },
];

export default function Sidebar() {
  const navigate = useNavigate();

  async function handleLogout() {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {
      // Ignore — clear client state regardless.
    }
    navigate("/login");
  }

  return (
    <div className="flex h-full flex-col">

      {/* Logo */}
      <div className="px-5 py-5">
        <div className="flex items-center gap-3">
          <Logo
            className="h-10 w-10 shrink-0 drop-shadow-lg"
            style={{ filter: "drop-shadow(0 0 8px rgba(56,189,248,0.5))" }}
          />
          <div className="flex flex-col gap-0">
            <span className="text-gradient text-[15px] font-semibold leading-tight tracking-wide">
              HA-Phone
            </span>
            <span className="text-[10px] leading-tight" style={{ color: "rgba(148,163,184,0.6)" }}>
              PBX Admin
            </span>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="mx-4 h-px" style={{ background: "rgba(255,255,255,0.05)" }} />

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 px-3 py-4">
        {navItems.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              [
                "group relative flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150",
                isActive
                  ? "text-violet-300"
                  : "text-muted-foreground hover:text-slate-200",
              ].join(" ")
            }
            style={({ isActive }) =>
              isActive
                ? {
                    background: "rgba(139, 92, 246, 0.1)",
                    boxShadow: "inset 0 0 0 1px rgba(139, 92, 246, 0.18)",
                  }
                : {}
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <div
                    className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full"
                    style={{ background: "linear-gradient(to bottom, #A78BFA, #7C3AED)" }}
                  />
                )}
                <Icon
                  className="h-4 w-4 shrink-0 transition-colors duration-150"
                  style={isActive ? { color: "#A78BFA" } : {}}
                />
                <span>{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Divider */}
      <div className="mx-4 h-px" style={{ background: "rgba(255,255,255,0.05)" }} />

      {/* Logout */}
      <div className="px-3 py-4">
        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-all duration-150 hover:text-red-400"
          style={{}}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "rgba(239,68,68,0.07)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "";
          }}
        >
          <LogOut className="h-4 w-4 shrink-0" />
          Abmelden
        </button>
      </div>
    </div>
  );
}
