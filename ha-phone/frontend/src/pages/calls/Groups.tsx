import { PageHeader } from "@/components/PageHeader";
import { ExtensionGroupsSection } from "./ExtensionGroupsSection";
import { RingGroupsSection } from "./RingGroupsSection";

export default function Groups() {
  return (
    <div className="grid gap-8">
      <PageHeader />
      <RingGroupsSection />
      <ExtensionGroupsSection />
    </div>
  );
}
