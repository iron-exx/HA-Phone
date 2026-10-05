import { Navigate, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Extensions from "./pages/extensions/Extensions";
import Devices from "./pages/devices/Devices";
import Phonebook from "./pages/Phonebook";
import Inbound from "./pages/calls/Inbound";
import Outbound from "./pages/calls/Outbound";
import Groups from "./pages/calls/Groups";
import Ivr from "./pages/calls/Ivr";
import Schedules from "./pages/calls/Schedules";
import Voicemail from "./pages/calls/Voicemail";
import Doorbell from "./pages/doorbell/Doorbell";
import Cameras from "./pages/doorbell/Cameras";
import Provider from "./pages/connection/Provider";
import Remote from "./pages/connection/Remote";
import Network from "./pages/connection/Network";
import Email from "./pages/system/Email";
import Backup from "./pages/system/Backup";
import Diagnostics from "./pages/system/Diagnostics";
import Account from "./pages/system/Account";
import { LEGACY_REDIRECTS } from "./nav";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/extensions" element={<Extensions />} />
      <Route path="/devices" element={<Devices />} />
      <Route path="/phonebook" element={<Phonebook />} />
      <Route path="/calls/inbound" element={<Inbound />} />
      <Route path="/calls/outbound" element={<Outbound />} />
      <Route path="/calls/groups" element={<Groups />} />
      <Route path="/calls/ivr" element={<Ivr />} />
      <Route path="/calls/schedules" element={<Schedules />} />
      <Route path="/calls/voicemail" element={<Voicemail />} />
      <Route path="/doorbell" element={<Doorbell />} />
      <Route path="/doorbell/cameras" element={<Cameras />} />
      <Route path="/connection/provider" element={<Provider />} />
      <Route path="/connection/remote" element={<Remote />} />
      <Route path="/connection/network" element={<Network />} />
      <Route path="/system/email" element={<Email />} />
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
