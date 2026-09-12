/**
 * A message body, with a widget transcript pulled out of it.
 *
 * A ticket escalated from the support widget arrives as the visitor's own
 * message followed by the conversation they had with the bot first, under a
 * separator the API writes (`api/widget.py`'s `submit`). Rendered as one
 * flat block those run together, and the thing an agent needs to read --
 * what the person actually wants -- is the part that looks like everything
 * else.
 *
 * So the transcript gets a box. Everything else renders exactly as it did.
 */

const SEPARATOR = "--- Before contacting support ---";

/** `Visitor: …`, `Assistant: …`, or the indented `(articles shown: …)`
 *  note the widget appends under an answer that cited something. */
const SPEAKER = /^(Visitor|Assistant):\s?(.*)$/;
const ARTICLES = /^\s*\((articles shown: .*)\)\s*$/;

export function MessageBody({ body }: { body: string }) {
  const at = body.indexOf(SEPARATOR);
  if (at === -1) {
    return <p className="whitespace-pre-wrap">{body}</p>;
  }

  const message = body.slice(0, at).trimEnd();
  const transcript = body.slice(at + SEPARATOR.length).trim();

  return (
    <>
      {message && <p className="whitespace-pre-wrap">{message}</p>}

      <div className="mt-3 rounded-lg border border-ink-200 bg-white/70 px-3.5 py-3">
        <p className="mb-2.5 text-[11px] font-medium tracking-wide text-ink-500 uppercase">
          Before contacting support
        </p>

        <div className="space-y-2.5">
          {transcript.split("\n").map((line, index) => {
            const articles = ARTICLES.exec(line);
            if (articles) {
              return (
                <p key={index} className="-mt-1.5 pl-0 text-[11px] text-ink-500 italic">
                  {articles[1]}
                </p>
              );
            }

            const speaker = SPEAKER.exec(line);
            if (!speaker) {
              // A line this parser does not recognise is still the
              // visitor's content -- show it rather than dropping it.
              return (
                <p key={index} className="text-[13px] whitespace-pre-wrap text-ink-800">
                  {line}
                </p>
              );
            }

            const visitor = speaker[1] === "Visitor";
            return (
              <div key={index} className="flex gap-2">
                <span
                  className={[
                    "shrink-0 text-[11px] font-semibold",
                    visitor ? "text-ink-900" : "text-accent-700",
                  ].join(" ")}
                >
                  {visitor ? "Visitor" : "Bot"}
                </span>
                <span className="min-w-0 text-[13px] whitespace-pre-wrap text-ink-800">
                  {speaker[2]}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
