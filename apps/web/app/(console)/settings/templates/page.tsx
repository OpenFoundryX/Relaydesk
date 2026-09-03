import { Ellipsis } from "lucide-react";

import { PageHeader } from "@/components/console/page-header";
import { SettingSection } from "@/components/console/setting-section";
import { SnippetDialog } from "@/components/settings/snippet-dialog";
import { getSnippets, getSnippetVariables } from "@/lib/mock/settings";

export const metadata = { title: "Templates" };

export default async function TemplatesPage() {
  const [snippets, variables] = await Promise.all([
    getSnippets(),
    getSnippetVariables(),
  ]);

  return (
    <>
      <PageHeader
        title="Templates"
        description="Reusable replies your team can drop into any conversation."
      />

      <SettingSection
        title="Snippets"
        description="Type / in the message editor to insert one."
        action={<SnippetDialog variables={variables} />}
      >
        <table className="w-full">
          <thead>
            <tr className="border-b border-ink-200 text-left">
              <th className="w-44 pb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                Title
              </th>
              <th className="pb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                Content
              </th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {snippets.map((snippet) => (
              <tr key={snippet.id} className="border-b border-ink-200 last:border-b-0">
                <td className="py-2.5 pr-4 align-top text-[13px] font-medium text-ink-900">
                  {snippet.title}
                </td>
                <td className="py-2.5 pr-4 align-top text-[13px] text-ink-500">
                  <span className="line-clamp-1">{snippet.content}</span>
                </td>
                <td className="py-2.5 align-top">
                  <button
                    type="button"
                    aria-label={`Options for ${snippet.title}`}
                    className="rounded p-1 text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-900"
                  >
                    <Ellipsis className="size-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </SettingSection>
    </>
  );
}
