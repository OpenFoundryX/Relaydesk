import { getWidgetBootstrap } from "@/lib/api/widget";

/**
 * Just enough of a key's branding for the loader to draw its launcher:
 * the accent colour and which corner it sits in.
 *
 * The loader draws from the `data-*` attributes on its own script tag
 * first, so a launcher appears with no network at all. This is what lets a
 * colour or corner changed in the console take effect without every
 * customer re-pasting their snippet -- the loader corrects itself once
 * this answers.
 *
 * Deliberately narrower than `/widget/frame`'s bootstrap. That one carries
 * the workspace name, the article count and whether AI is configured,
 * none of which the launcher needs; a response that stops at two fields
 * cannot grow a third by accident.
 */
export async function GET(request: Request) {
  const key = new URL(request.url).searchParams.get("key");
  if (!key) return new Response(null, { status: 404 });

  const bootstrap = await getWidgetBootstrap(key);
  if (!bootstrap) return new Response(null, { status: 404 });

  const settings = bootstrap.settings as {
    accentColour?: unknown;
    position?: unknown;
  };

  return Response.json(
    {
      accent: typeof settings.accentColour === "string" ? settings.accentColour : null,
      position: settings.position === "left" ? "left" : "right",
    },
    {
      headers: {
        // A minute is long enough that a visitor clicking through several
        // pages asks once, and short enough that someone who has just
        // changed a colour in the console sees it on the site rather than
        // wondering whether it saved.
        "Cache-Control": "public, max-age=60",
      },
    },
  );
}
