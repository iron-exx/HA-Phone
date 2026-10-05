import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type { Extension, IVRMenu, RingGroup } from "@/types/api";

export interface RoutingTargets {
  extensions: Extension[];
  ringGroups: RingGroup[];
  ivrMenus: IVRMenu[];
  reload: () => void;
}

/** Ziele für DestinationField (Nebenstellen, Rufgruppen, Sprachmenüs). */
export function useRoutingTargets(): RoutingTargets {
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [ringGroups, setRingGroups] = useState<RingGroup[]>([]);
  const [ivrMenus, setIvrMenus] = useState<IVRMenu[]>([]);

  const reload = useCallback(() => {
    Promise.all([
      fetch("/api/extensions").then((r) => r.json()),
      fetch("/api/ring-groups").then((r) => r.json()),
      fetch("/api/ivrs").then((r) => r.json()),
    ])
      .then(([ext, groups, ivrs]: [Extension[], RingGroup[], IVRMenu[]]) => {
        setExtensions(ext);
        setRingGroups(groups);
        setIvrMenus(ivrs);
      })
      .catch(() => toast.error("Ziele (Nebenstellen, Gruppen, Sprachmenüs) konnten nicht geladen werden."));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return { extensions, ringGroups, ivrMenus, reload };
}
