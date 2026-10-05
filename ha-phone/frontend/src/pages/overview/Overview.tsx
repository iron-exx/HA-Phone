import { useState } from "react";
import { Link } from "react-router-dom";
import { BellRing, Phone, Plug, Smartphone, UserRound } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { KpiTile } from "./KpiTile";
import { RecentDoorCard } from "./RecentDoorCard";
import { AttentionCard, type UpdateState } from "./AttentionCard";
import { buildAttention, countToday, greeting, summaryLine, trunkLabel } from "./overviewLogic";
import { useOverviewData } from "./useOverviewData";

export default function Overview() {
  const data = useOverviewData();
  const [updateState, setUpdateState] = useState<UpdateState>("idle");
  const now = new Date();

  const enabled = data.extensions.filter((e) => e.enabled);
  const onlineCount = enabled.filter((e) => data.online.has(String(e.number))).length;
  const attention = buildAttention({
    trunkStatus: data.trunkStatus,
    extensions: data.extensions,
    online: data.online,
    statusKnown: data.statusKnown,
    regenFailures: (data.regen?.steps ?? []).filter((s) => !s.ok),
    updateLatest: data.update?.update_available ? data.update.version_latest : null,
  });
  const trunkTone = data.trunkStatus === "Registered" ? "answer" : data.trunkStatus === "UNKNOWN" ? "blue" : "end";

  function startUpdate() {
    setUpdateState("running");
    fetch("/api/update/start", { method: "POST" })
      .then((r) => setUpdateState(r.ok ? "done" : "idle"))
      .catch(() => setUpdateState("idle"));
  }

  return (
    <div>
      <PageHeader
        title={greeting(now)}
        description={summaryLine(onlineCount, enabled.length, attention.length)}
        actions={<Button asChild><Link to="/extensions"><Smartphone />Handy koppeln</Link></Button>}
      />
      <div className="grid gap-3.5">
        <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
          <KpiTile icon={Plug} tone={trunkTone} value={trunkLabel(data.trunkStatus)} label="Telefonanbieter" />
          <KpiTile icon={UserRound} tone="blue" value={`${onlineCount} / ${enabled.length}`} label="Nebenstellen angemeldet" />
          <KpiTile icon={Phone} tone="violet" value={String(data.activeCalls)} label="Gespräche gerade" />
          <KpiTile icon={BellRing} tone="door" value={String(countToday(data.doorEvents, now))} label="Klingeln heute" />
        </div>

        <div className="grid gap-3 min-[1100px]:grid-cols-[1.4fr_1fr]">
          <RecentDoorCard events={data.doorEvents.slice(0, 3)} now={now} />
          <AttentionCard items={attention} updateState={updateState} onStartUpdate={startUpdate} />
        </div>
      </div>
    </div>
  );
}
