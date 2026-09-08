/**
 * A ProseMirror document made of ordinary objects, safe to hand to a Server
 * Action.
 *
 * `editor.getJSON()` returns the node attributes exactly as
 * prosemirror-model built them, and it builds them with
 * `Object.create(null)`. Those are the only null-prototype objects in the
 * document, and a Server Action's argument encoder drops them on the way to
 * the server: the article saves, reports success, and arrives with `attrs`
 * missing from every node.
 *
 * The damage is invisible in the editor, because there the attributes are
 * still in memory. It shows up on the published page, where an image node
 * with no `attrs.id` renders nothing at all (`DocRenderer` has no id to
 * resolve) and every heading has quietly collapsed to level one.
 *
 * A JSON round trip is the whole fix: it rebuilds each object with the
 * ordinary prototype while keeping the values. It is done here, where the
 * document leaves ProseMirror, rather than defensively somewhere downstream
 * -- past this point the loss has already happened and nothing can tell an
 * absent `attrs` from a node that never had one.
 */
export function plainDoc(doc: unknown): unknown {
  return JSON.parse(JSON.stringify(doc));
}
