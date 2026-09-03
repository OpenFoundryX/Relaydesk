import { Ellipsis } from "lucide-react";

import { PageHeader } from "@/components/console/page-header";
import { SettingSection } from "@/components/console/setting-section";
import { InviteDialog } from "@/components/settings/invite-dialog";
import { Badge } from "@/components/ui/badge";
import { getTeam } from "@/lib/mock/settings";
import { workspace } from "@/lib/mock/workspace";

export const metadata = { title: "Team" };

export default async function TeamPage() {
  const team = await getTeam();

  return (
    <>
      <PageHeader
        title="Team"
        description={`${team.length} of your seats are in use on the ${workspace.plan} plan.`}
      />

      <SettingSection
        title="Members"
        description="Admins can change settings and billing. Agents work the queue."
        action={<InviteDialog />}
      >
        <ul className="divide-y divide-ink-200 rounded-md border border-ink-200">
          {team.map((member) => (
            <li key={member.id} className="flex items-center gap-3 px-3 py-2.5">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-ink-900 text-[10px] font-semibold uppercase text-white">
                {member.name
                  .split(" ")
                  .map((part) => part[0])
                  .join("")}
              </span>
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-ink-900">{member.name}</p>
                <p className="truncate text-[12px] text-ink-500">{member.email}</p>
              </div>
              <div className="ml-auto flex shrink-0 items-center gap-2">
                {member.status === "invited" && (
                  <Badge variant="outline">Invite pending</Badge>
                )}
                <Badge variant={member.role === "Admin" ? "accent" : "neutral"}>
                  {member.role}
                </Badge>
                <button
                  type="button"
                  aria-label={`Options for ${member.name}`}
                  className="rounded p-1 text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-900"
                >
                  <Ellipsis className="size-4" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      </SettingSection>
    </>
  );
}
