/**
 * Snippet placeholders, and the one pass that fills them in.
 *
 * A snippet is stored verbatim — the API neither knows nor validates this
 * vocabulary (see the `0019_snippets` migration). Substitution happens here,
 * in the console, at the moment an agent inserts one into a reply, so what
 * they see in the composer is exactly what the customer will read.
 */

/** Everything a placeholder can be filled in from. */
export interface SnippetContext {
  customerName: string;
  customerEmail: string;
  /** The sequential ticket number shown in the details panel, not the UUID. */
  ticketNumber: number;
  ticketSubject: string;
  /** The signed-in agent, not the conversation's assignee. */
  agentName: string;
  workspaceName: string;
}

/**
 * A contact with no display name is stored under its own address (see the
 * API's `services/contacts.py`), so "Hi {{customer.first_name}}" would
 * otherwise open with a full email address. Take the mailbox in that case.
 */
function firstName(name: string): string {
  const first = name.trim().split(/\s+/)[0] ?? "";
  const at = first.indexOf("@");
  return at > 0 ? first.slice(0, at) : first;
}

const RESOLVERS: Record<string, (context: SnippetContext) => string> = {
  "customer.first_name": (context) => firstName(context.customerName),
  "customer.email": (context) => context.customerEmail,
  "ticket.id": (context) => String(context.ticketNumber),
  "ticket.subject": (context) => context.ticketSubject,
  "agent.name": (context) => context.agentName,
  "workspace.name": (context) => context.workspaceName,
};

/**
 * The placeholders offered by the snippet dialog's Variables menu.
 *
 * Derived from the resolvers rather than listed separately, so the menu
 * cannot offer something `renderSnippet` would leave in a customer's reply
 * as literal `{{...}}`.
 */
export const SNIPPET_VARIABLES: readonly string[] = Object.keys(RESOLVERS).map(
  (name) => `{{${name}}}`,
);

/**
 * Fill in the placeholders in `content`.
 *
 * One pass over the source string. A value is written to the output and
 * never re-scanned, which matters because `customerName` is the display
 * name off an inbound email header — attacker-controlled text that must not
 * be able to introduce a placeholder of its own. An unrecognised
 * placeholder is left exactly as written.
 */
export function renderSnippet(content: string, context: SnippetContext): string {
  return content.replace(/\{\{\s*([\w.]+)\s*\}\}/g, (match, name: string) => {
    const resolve = RESOLVERS[name];
    return resolve ? resolve(context) : match;
  });
}
