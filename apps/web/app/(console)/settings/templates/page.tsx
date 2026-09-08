import { PageHeader } from "@/components/console/page-header";
import { SectionEmpty, SettingSection } from "@/components/console/setting-section";
import { SnippetActions } from "@/components/settings/snippet-actions";
import { NewSnippetButton } from "@/components/settings/snippet-dialog";
import { getSnippets } from "@/lib/api/snippets";
import { requireAdmin } from "@/lib/api/workspace";

export const metadata = { title: "Templates" };

export default async function TemplatesPage() {
  await requireAdmin();

  const snippets = await getSnippets();

  return (
    <>
      <PageHeader
        title="Templates"
        description="Reusable replies your team can drop into any conversation."
      />

      <SettingSection
        title="Snippets"
        description="Type / in the message editor to insert one."
        action={<NewSnippetButton />}
      >
        {snippets.length > 0 ? (
          <table className="w-full">
            <thead>
              <tr className="border-b border-ink-200 text-left">
                <th className="w-44 pb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                  Title
                </th>
                <th className="pb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                  Content
                </th>
                <th className="w-20" />
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
                  <td className="py-1.5 align-top">
                    <SnippetActions snippet={snippet} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <SectionEmpty>No snippets yet</SectionEmpty>
        )}
      </SettingSection>
    </>
  );
}
