import { PageHeader } from "@/components/PageHeader";
import { SharedCamerasCard } from "@/components/SharedCamerasCard";

export default function Cameras() {
  return (
    <div className="grid gap-4">
      <PageHeader />
      <SharedCamerasCard />
    </div>
  );
}
