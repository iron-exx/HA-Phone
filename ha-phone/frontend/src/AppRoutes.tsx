import { Navigate, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Extensions from "./pages/Extensions";
import Provisioning from "./pages/Provisioning";
import Phonebook from "./pages/Phonebook";
import Routing from "./pages/Routing";
import IVR from "./pages/IVR";
import Voicemail from "./pages/Voicemail";
import Doorbell from "./pages/Doorbell";
import Trunk from "./pages/Trunk";
import Tailscale from "./pages/Tailscale";
import PublicIP from "./pages/PublicIP";
import Backup from "./pages/Backup";
import Diagnostics from "./pages/Diagnostics";
import Account from "./pages/system/Account";
import { LEGACY_REDIRECTS } from "./nav";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/extensions" element={<Extensions />} />
      <Route path="/devices" element={<Provisioning />} />
      <Route path="/phonebook" element={<Phonebook />} />
      <Route path="/calls/inbound" element={<Routing />} />
      <Route path="/calls/outbound" element={<Routing />} />
      <Route path="/calls/groups" element={<Routing />} />
      <Route path="/calls/ivr" element={<IVR />} />
      <Route path="/calls/schedules" element={<Routing />} />
      <Route path="/calls/voicemail" element={<Voicemail />} />
      <Route path="/doorbell" element={<Doorbell />} />
      <Route path="/doorbell/cameras" element={<Doorbell />} />
      <Route path="/connection/provider" element={<Trunk />} />
      <Route path="/connection/remote" element={<Tailscale />} />
      <Route path="/connection/network" element={<PublicIP />} />
      <Route path="/system/email" element={<PublicIP />} />
      <Route path="/system/backup" element={<Backup />} />
      <Route path="/system/diagnostics" element={<Diagnostics />} />
      <Route path="/system/account" element={<Account />} />
      {Object.entries(LEGACY_REDIRECTS).map(([from, to]) => (
        <Route key={from} path={from} element={<Navigate to={to} replace />} />
      ))}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
