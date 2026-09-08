"use client";

import { useCallback, useEffect, useRef, useState, type MouseEvent } from "react";
import NextLink from "next/link";
import { useRouter } from "next/navigation";
import { EditorContent, useEditor, useEditorState } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Link } from "@tiptap/extension-link";
import { Image } from "@tiptap/extension-image";
import { Table } from "@tiptap/extension-table";
import { TableCell } from "@tiptap/extension-table-cell";
import { TableHeader } from "@tiptap/extension-table-header";
import { TableRow } from "@tiptap/extension-table-row";
import {
  Bold,
  BookOpen,
  Code,
  ExternalLink,
  Eye,
  Heading1,
  Heading2,
  Heading3,
  ImagePlus,
  Italic,
  Link2,
  List,
  ListOrdered,
  Minus,
  Quote,
  SquareCode,
  Table as TableIcon,
  X,
} from "lucide-react";

import {
  saveArticleAction,
  setArticleStatusAction,
  uploadArticleImageAction,
} from "@/app/(console)/knowledge-base/actions";
import { useArticleGuard } from "@/components/knowledge-base/article-guard";
import { STATUS_CONTROL } from "@/components/knowledge-base/article-status";
import { DocRenderer } from "@/components/knowledge-base/doc-renderer";
import { plainDoc } from "@/components/knowledge-base/plain-doc";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { ArticleStatus, KbArticle, KbCategory } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Where the browser reads an article image from.
 *
 * A stored `image` node carries the API's image id and nothing else, so
 * this is the single place that turns one into a URL. It points at the
 * console's own proxy route rather than the API, because the API only
 * serves these behind a bearer token an `<img>` cannot send. The editor and
 * the preview below both go through it, which is what makes what you type
 * and what you preview the same picture.
 */
function articleImageSrc(id: string): string {
  return `/api/kb/images/${id}`;
}

/**
 * The image node, keyed by id rather than by URL.
 *
 * TipTap's stock Image node stores a `src`, which would bake an absolute
 * URL into a document that is also rendered by the public help site under a
 * different origin. Storing the id instead keeps the document portable and
 * keeps `DocRenderer` -- which reads `attrs.id` and resolves it through its
 * own `imageSrc` -- the one thing deciding where the bytes come from.
 */
const ArticleImage = Image.extend({
  addAttributes() {
    return {
      id: {
        default: null,
        parseHTML: (element: HTMLElement) => element.getAttribute("data-image-id"),
        renderHTML: (attributes: Record<string, unknown>) =>
          attributes.id ? { "data-image-id": String(attributes.id) } : {},
      },
      alt: { default: "" },
    };
  },
  parseHTML() {
    return [{ tag: "img[data-image-id]" }];
  },
  renderHTML({ node }) {
    const id = String(node.attrs.id ?? "");
    return [
      "img",
      {
        src: articleImageSrc(id),
        alt: String(node.attrs.alt ?? ""),
        "data-image-id": id,
      },
    ];
  },
});

const STATUS_TONE: Record<ArticleStatus, "neutral" | "accent" | "positive"> = {
  draft: "neutral",
  ready: "accent",
  published: "positive",
};

/**
 * Shared by the editable surface and the preview, so switching between them
 * does not change how the article looks. Written out rather than pulled
 * from a typography plugin because the console does not carry one.
 */
const docStyles = cn(
  "text-[14px] leading-relaxed text-ink-800",
  "[&_h1]:mb-2 [&_h1]:mt-6 [&_h1]:text-[20px] [&_h1]:font-semibold [&_h1]:tracking-tight [&_h1]:text-ink-900",
  "[&_h2]:mb-2 [&_h2]:mt-5 [&_h2]:text-[17px] [&_h2]:font-semibold [&_h2]:tracking-tight [&_h2]:text-ink-900",
  "[&_h3]:mb-1.5 [&_h3]:mt-4 [&_h3]:text-[15px] [&_h3]:font-semibold [&_h3]:text-ink-900",
  "[&_p]:my-2.5",
  "[&_ul]:my-2.5 [&_ul]:list-disc [&_ul]:pl-5",
  "[&_ol]:my-2.5 [&_ol]:list-decimal [&_ol]:pl-5",
  "[&_li]:my-1 [&_li>p]:my-0",
  "[&_blockquote]:my-3 [&_blockquote]:border-l-2 [&_blockquote]:border-accent-500 [&_blockquote]:pl-3 [&_blockquote]:text-ink-600",
  "[&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-ink-900 [&_pre]:p-3 [&_pre]:font-mono [&_pre]:text-[12px] [&_pre]:text-ink-50",
  "[&_:not(pre)>code]:rounded [&_:not(pre)>code]:bg-ink-100 [&_:not(pre)>code]:px-1 [&_:not(pre)>code]:py-0.5 [&_:not(pre)>code]:font-mono [&_:not(pre)>code]:text-[12px]",
  "[&_a]:text-accent-950 [&_a]:underline [&_a]:underline-offset-2",
  "[&_hr]:my-5 [&_hr]:border-ink-200",
  "[&_img]:my-3 [&_img]:max-w-full [&_img]:rounded-md [&_img]:border [&_img]:border-ink-200",
  "[&_table]:my-3 [&_table]:w-full [&_table]:table-fixed [&_table]:border-collapse",
  "[&_td]:border [&_td]:border-ink-200 [&_td]:px-2 [&_td]:py-1.5 [&_td]:align-top",
  "[&_th]:border [&_th]:border-ink-200 [&_th]:bg-ink-50 [&_th]:px-2 [&_th]:py-1.5 [&_th]:text-left [&_th]:font-semibold",
);

type TiptapEditor = NonNullable<ReturnType<typeof useEditor>>;
type EditorInitialContent = NonNullable<Parameters<typeof useEditor>[0]>["content"];

function imageFilesFrom(list: FileList | null | undefined): File[] {
  return Array.from(list ?? []).filter((file) => file.type.startsWith("image/"));
}

/**
 * A new article is stored as `{ type: "doc", content: [] }`, which
 * ProseMirror's schema does not accept -- `doc` requires at least one block,
 * and an editor opened on one has nowhere to put the cursor. Give it the
 * empty paragraph it wants; every other document goes through untouched.
 */
function editableDoc(doc: unknown): EditorInitialContent {
  const content = (doc as { content?: unknown } | null)?.content;
  if (Array.isArray(content) && content.length === 0) {
    return { type: "doc", content: [{ type: "paragraph" }] };
  }
  return doc as EditorInitialContent;
}

export function ArticleEditor({
  article,
  category,
  portalOrigin,
}: {
  article: KbArticle;
  category: KbCategory | null;
  /** The origin of this workspace's public help site. See `lib/api/portal.ts`. */
  portalOrigin: string;
}) {
  const [title, setTitle] = useState(article.title);
  const [excerpt, setExcerpt] = useState(article.excerpt);
  const [status, setStatus] = useState<ArticleStatus>(article.status);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [changingStatus, setChangingStatus] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [linkDraft, setLinkDraft] = useState<string | null>(null);
  /**
   * What a confirmed "discard and leave" does; null while nothing is asked.
   * Held as an object so `useState` stores the callback rather than calling
   * it as a state updater.
   */
  const [leaving, setLeaving] = useState<{ proceed: () => void } | null>(null);

  const router = useRouter();
  const guard = useArticleGuard();

  const fileInput = useRef<HTMLInputElement>(null);
  // ProseMirror's paste and drop handlers are registered once, when the
  // editor is created, so they cannot close over an uploader that needs the
  // editor itself. They call through this ref, which every render points at
  // the current one.
  const uploadRef = useRef<((files: File[]) => void) | null>(null);

  const editor = useEditor({
    immediatelyRender: false,
    content: editableDoc(article.doc),
    extensions: [
      StarterKit.configure({
        // `DocRenderer` renders exactly four marks: bold, italic, code, and
        // link. Strike and underline would still be reachable by keyboard
        // shortcut if they were registered, and would then vanish the
        // moment the article was rendered on the help site -- so the editor
        // does not offer what the renderer would drop.
        strike: false,
        underline: false,
        // Configured explicitly below so its protocol handling is visible
        // at this call site rather than buried in a kit default.
        link: false,
      }),
      Link.configure({ openOnClick: false, autolink: true }),
      ArticleImage,
      Table.configure({ resizable: false }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    editorProps: {
      attributes: {
        class: cn(docStyles, "min-h-[24rem] px-4 py-3 focus:outline-none"),
      },
      handlePaste: (_view, event) => {
        const files = imageFilesFrom(event.clipboardData?.files);
        if (files.length === 0) return false;
        event.preventDefault();
        uploadRef.current?.(files);
        return true;
      },
      handleDrop: (_view, event, _slice, moved) => {
        // `moved` means the user dragged a node from one place in this same
        // document to another. That is ProseMirror's job, not an upload.
        if (moved) return false;
        const files = imageFilesFrom(event.dataTransfer?.files);
        if (files.length === 0) return false;
        event.preventDefault();
        uploadRef.current?.(files);
        return true;
      },
    },
    onUpdate: () => setDirty(true),
  });

  const uploadImages = useCallback(
    async (files: File[]) => {
      if (!editor) return;
      setError(null);
      setUploading(true);
      try {
        for (const file of files) {
          const form = new FormData();
          form.set("file", file);
          const result = await uploadArticleImageAction(article.id, form);
          if (!result.ok) {
            // Over the size cap, or a type that cannot be rendered inline.
            // Stop here rather than pressing on through the rest of a
            // multi-file paste with an error already on screen.
            setError(result.message);
            return;
          }
          editor
            .chain()
            .focus()
            .insertContent({
              type: "image",
              attrs: { id: result.id, alt: file.name },
            })
            .run();
        }
      } finally {
        setUploading(false);
      }
    },
    [editor, article.id],
  );

  useEffect(() => {
    uploadRef.current = (files) => void uploadImages(files);
  }, [uploadImages]);

  // Saving is explicit, so leaving with unsaved work has to be something
  // the browser asks about -- otherwise a stray reload silently discards
  // however long someone spent writing.
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  // In the master-detail console the likeliest way out of an unsaved article
  // is a click on a different one in the sidebar -- which lives in the
  // layout and cannot see any of this. It asks; this answers, with the same
  // dialog the breadcrumb puts up. See `ArticleGuardProvider`.
  useEffect(
    () =>
      guard.register((proceed) => {
        if (!dirty) return false;
        setLeaving({ proceed });
        return true;
      }),
    [guard, dirty],
  );

  async function save() {
    if (!editor) return;
    setError(null);
    setSaving(true);
    try {
      const result = await saveArticleAction(article.id, {
        title: title.trim(),
        excerpt: excerpt.trim(),
        // Not `getJSON()` directly: its `attrs` are the null-prototype
        // objects prosemirror-model builds, and a Server Action's encoder
        // drops those in transit -- the save succeeds and the document
        // arrives with every node's attributes gone. See `plainDoc`.
        doc: plainDoc(editor.getJSON()),
      });
      if (result.ok) {
        setDirty(false);
      } else {
        // The document stays exactly as it is: nothing here throws away
        // what failed to save.
        setError(result.message);
      }
    } finally {
      setSaving(false);
    }
  }

  async function transition(to: ArticleStatus) {
    setError(null);
    setChangingStatus(true);
    try {
      const result = await setArticleStatusAction(article.id, to);
      if (result.ok) {
        setStatus(result.status);
      } else {
        setError(result.message);
      }
    } finally {
      setChangingStatus(false);
    }
  }

  function applyLink() {
    if (!editor || linkDraft === null) return;
    const href = linkDraft.trim();
    const chain = editor.chain().focus().extendMarkRange("link");
    if (href.length === 0) {
      chain.unsetLink().run();
    } else {
      chain.setLink({ href }).run();
    }
    setLinkDraft(null);
  }

  const canSave = editor !== null && title.trim().length > 0 && !saving;
  const backHref = `/knowledge-base?tab=${category?.scope ?? "internal"}`;
  const control = STATUS_CONTROL[status];
  // Pulled out as a const so its `null` check narrows inside the click
  // handler below, which runs long after the JSX guard.
  const publish = control.publish;

  /**
   * The article's public page, or null when it has none.
   *
   * The help site serves exactly one kind of article -- published, in an
   * external category -- and 404s on everything else, so anything short of
   * that leaves Preview disabled rather than offering a link into a dead
   * end. `status` is the live one, so publishing lights this up without a
   * reload. The slugs are the stored ones: neither a renamed category nor a
   * retitled article gets a new slug, because that is the published address.
   */
  const previewHref =
    category?.scope === "external" && status === "published"
      ? `${portalOrigin}/help/${category.slug}/${article.slug}`
      : null;

  const previewReason =
    category?.scope !== "external"
      ? "Only external articles have a public page."
      : "Publish this article to give it a public page.";

  /**
   * `beforeunload` covers a reload or a closed tab, but a click on the
   * breadcrumb is a client-side route change the browser never hears about.
   * Ask first when there is unsaved work. A modified click (new tab, new
   * window) is left alone: it leaves this tab, and its edits, exactly where
   * they are.
   */
  function handleBack(event: MouseEvent<HTMLAnchorElement>) {
    if (!dirty) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    setLeaving({ proceed: () => router.push(backHref) });
  }

  return (
    <div className="space-y-4">
      <nav
        aria-label="Breadcrumb"
        className="flex min-w-0 items-center gap-1.5 text-[13px] text-ink-500"
      >
        <NextLink
          href={backHref}
          onClick={handleBack}
          className="shrink-0 transition-colors hover:text-ink-900"
        >
          Knowledge base
        </NextLink>
        {category && (
          <>
            <span aria-hidden>/</span>
            <span className="shrink-0">{category.name}</span>
          </>
        )}
        <span aria-hidden>/</span>
        <span className="truncate font-medium text-ink-900">{title}</span>
      </nav>

      <Dialog
        open={leaving !== null}
        onOpenChange={(open) => {
          if (!open) setLeaving(null);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Leave without saving?</DialogTitle>
            <DialogDescription>
              This article has changes you have not saved. Leaving now discards
              them.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setLeaving(null)}>
              Keep editing
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                const go = leaving?.proceed;
                setLeaving(null);
                go?.();
              }}
            >
              Discard and leave
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-ink-200 bg-white px-3 py-2.5">
        <Badge variant={STATUS_TONE[status]}>{status}</Badge>
        {dirty && (
          // A transition moves the article as it was last saved. Worth
          // saying out loud, since nothing here saves on your behalf.
          <span className="text-[12px] text-ink-500">
            Uses the last saved version — save first.
          </span>
        )}

        <div className="flex-1" />

        <span
          className={cn(
            "text-[12px]",
            dirty ? "text-ink-600" : "text-ink-400",
          )}
        >
          {dirty ? "Unsaved changes" : "All changes saved"}
        </span>

        {/* The status control. Both halves are driven by STATUS_CONTROL,
            whose every target is an edge in the API's own transition table
            -- so there is no state in which this offers a move the API
            would refuse, and no published -> ready anywhere. */}
        <span className="flex select-none items-center gap-2 text-[12px] text-ink-600">
          <Switch
            aria-label={control.toggleLabel}
            checked={control.toggleOn}
            disabled={changingStatus}
            onCheckedChange={() => void transition(control.toggleTo)}
          />
          {control.toggleLabel}
        </span>
        {publish && (
          <Button
            variant="primary"
            size="sm"
            disabled={changingStatus || !publish.enabled}
            onClick={() => {
              if (publish.enabled) void transition(publish.to);
            }}
          >
            Publish
          </Button>
        )}

        {previewHref ? (
          <Button asChild variant="secondary" size="sm">
            <a href={previewHref} target="_blank" rel="noreferrer">
              <ExternalLink />
              Preview live page
            </a>
          </Button>
        ) : (
          <Button variant="secondary" size="sm" disabled title={previewReason}>
            <ExternalLink />
            Preview live page
          </Button>
        )}

        {/* The complement to the button above, for the case it cannot cover:
            an external article that is not live yet has no public URL to
            open, and this reads the same article through the console's own
            authenticated API instead. Offered on external articles only --
            an internal one has no help-centre page to preview. A new tab,
            like its neighbour, so it never walks out of unsaved edits; the
            "Preview" toggle beside it is what shows those. */}
        {category?.scope === "external" && (
          <Button asChild variant="secondary" size="sm">
            <a
              href={`/knowledge-base/${article.id}/preview`}
              target="_blank"
              rel="noreferrer"
            >
              <BookOpen />
              Preview help page
            </a>
          </Button>
        )}

        <Button
          variant="secondary"
          size="sm"
          aria-pressed={previewing}
          onClick={() => setPreviewing((on) => !on)}
        >
          <Eye />
          {previewing ? "Back to editing" : "Preview"}
        </Button>
        <Button variant="primary" size="sm" disabled={!canSave} onClick={() => void save()}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-[13px] text-danger-700"
        >
          {error}
        </p>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="article-title">Title</Label>
        <Input
          id="article-title"
          value={title}
          maxLength={200}
          onChange={(event) => {
            setTitle(event.target.value);
            setDirty(true);
          }}
        />
        {title.trim().length === 0 && (
          <p className="text-[12px] text-danger-700">An article needs a title.</p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="article-excerpt">Excerpt</Label>
        <Textarea
          id="article-excerpt"
          value={excerpt}
          maxLength={400}
          placeholder="One or two sentences, shown in search results and category listings."
          onChange={(event) => {
            setExcerpt(event.target.value);
            setDirty(true);
          }}
        />
      </div>

      <div className="overflow-hidden rounded-lg border border-ink-200 bg-white">
        {previewing ? (
          // The links in a preview are the article's own, and following one
          // would walk out of an unsaved document -- the same loss the back
          // link now asks about, but with a destination this editor has no
          // business confirming. A preview shows you the link; it does not
          // take you there.
          <div
            className={cn(docStyles, "px-4 py-3")}
            onClick={(event) => {
              if ((event.target as HTMLElement).closest("a")) {
                event.preventDefault();
              }
            }}
          >
            <DocRenderer doc={editor?.getJSON()} imageSrc={articleImageSrc} />
          </div>
        ) : (
          <>
            {editor && (
              <Toolbar
                editor={editor}
                uploading={uploading}
                onPickImage={() => fileInput.current?.click()}
                onEditLink={() =>
                  setLinkDraft(String(editor.getAttributes("link").href ?? ""))
                }
              />
            )}
            {linkDraft !== null && (
              <div className="border-b border-ink-200 bg-ink-50 px-2 py-2">
                <div className="flex items-center gap-2">
                  <Input
                    autoFocus
                    aria-label="Link address"
                    className="h-8 text-[13px]"
                    placeholder="https://example.com/page"
                    value={linkDraft}
                    onChange={(event) => setLinkDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        applyLink();
                      }
                      if (event.key === "Escape") setLinkDraft(null);
                    }}
                  />
                  <Button variant="primary" size="sm" onClick={applyLink}>
                    Apply
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Cancel link"
                    onClick={() => setLinkDraft(null)}
                  >
                    <X />
                  </Button>
                </div>
                <p className="mt-1.5 text-[12px] text-ink-500">
                  Leave it empty to remove the link.
                </p>
              </div>
            )}
            <EditorContent editor={editor} />
          </>
        )}
      </div>

      <input
        ref={fileInput}
        type="file"
        accept="image/png,image/jpeg,image/gif,image/webp"
        multiple
        hidden
        onChange={(event) => {
          const files = imageFilesFrom(event.target.files);
          // Reset first, so picking the same file twice in a row still
          // fires a change event.
          event.target.value = "";
          if (files.length > 0) void uploadImages(files);
        }}
      />
    </div>
  );
}

function Toolbar({
  editor,
  uploading,
  onPickImage,
  onEditLink,
}: {
  editor: TiptapEditor;
  uploading: boolean;
  onPickImage: () => void;
  onEditLink: () => void;
}) {
  const active = useEditorState({
    editor,
    selector: ({ editor: current }) => ({
      h1: current.isActive("heading", { level: 1 }),
      h2: current.isActive("heading", { level: 2 }),
      h3: current.isActive("heading", { level: 3 }),
      bold: current.isActive("bold"),
      italic: current.isActive("italic"),
      code: current.isActive("code"),
      bulletList: current.isActive("bulletList"),
      orderedList: current.isActive("orderedList"),
      blockquote: current.isActive("blockquote"),
      codeBlock: current.isActive("codeBlock"),
      link: current.isActive("link"),
      inTable: current.isActive("table"),
    }),
  });

  return (
    <div className="flex flex-wrap items-center gap-0.5 border-b border-ink-200 bg-ink-50 px-2 py-1.5">
      <ToolbarButton
        label="Heading 1"
        icon={Heading1}
        active={active.h1}
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
      />
      <ToolbarButton
        label="Heading 2"
        icon={Heading2}
        active={active.h2}
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
      />
      <ToolbarButton
        label="Heading 3"
        icon={Heading3}
        active={active.h3}
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
      />

      <ToolbarDivider />

      <ToolbarButton
        label="Bold"
        icon={Bold}
        active={active.bold}
        onClick={() => editor.chain().focus().toggleBold().run()}
      />
      <ToolbarButton
        label="Italic"
        icon={Italic}
        active={active.italic}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      />
      <ToolbarButton
        label="Inline code"
        icon={Code}
        active={active.code}
        onClick={() => editor.chain().focus().toggleCode().run()}
      />

      <ToolbarDivider />

      <ToolbarButton
        label="Bullet list"
        icon={List}
        active={active.bulletList}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      />
      <ToolbarButton
        label="Numbered list"
        icon={ListOrdered}
        active={active.orderedList}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      />
      <ToolbarButton
        label="Quote"
        icon={Quote}
        active={active.blockquote}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
      />
      <ToolbarButton
        label="Code block"
        icon={SquareCode}
        active={active.codeBlock}
        onClick={() => editor.chain().focus().toggleCodeBlock().run()}
      />

      <ToolbarDivider />

      <ToolbarButton label="Link" icon={Link2} active={active.link} onClick={onEditLink} />
      <ToolbarButton
        label="Table"
        icon={TableIcon}
        active={active.inTable}
        onClick={() =>
          editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
        }
      />
      <ToolbarButton
        label="Horizontal rule"
        icon={Minus}
        onClick={() => editor.chain().focus().setHorizontalRule().run()}
      />
      <ToolbarButton
        label={uploading ? "Uploading image…" : "Image"}
        icon={ImagePlus}
        disabled={uploading}
        onClick={onPickImage}
      />

      {/* A table you cannot add a row to is not much of a table. These only
          appear with the cursor inside one, so the main toolbar stays the
          list the brief describes. */}
      {active.inTable && (
        <>
          <ToolbarDivider />
          <ToolbarTextButton
            label="+ Row"
            onClick={() => editor.chain().focus().addRowAfter().run()}
          />
          <ToolbarTextButton
            label="+ Column"
            onClick={() => editor.chain().focus().addColumnAfter().run()}
          />
          <ToolbarTextButton
            label="− Row"
            onClick={() => editor.chain().focus().deleteRow().run()}
          />
          <ToolbarTextButton
            label="− Column"
            onClick={() => editor.chain().focus().deleteColumn().run()}
          />
          <ToolbarTextButton
            label="Delete table"
            onClick={() => editor.chain().focus().deleteTable().run()}
          />
        </>
      )}
    </div>
  );
}

function ToolbarDivider() {
  return <span aria-hidden className="mx-1 h-4 w-px bg-ink-200" />;
}

function ToolbarTextButton({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-7 items-center rounded px-1.5 text-[12px] text-ink-600 transition-colors hover:bg-ink-200 hover:text-ink-900"
    >
      {label}
    </button>
  );
}

function ToolbarButton({
  label,
  icon: Icon,
  active = false,
  disabled = false,
  onClick,
}: {
  label: string;
  icon: typeof Bold;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "inline-flex size-7 items-center justify-center rounded transition-colors",
        "disabled:pointer-events-none disabled:opacity-40",
        active
          ? "bg-ink-900 text-white"
          : "text-ink-600 hover:bg-ink-200 hover:text-ink-900",
      )}
    >
      <Icon className="size-3.5" />
    </button>
  );
}
