"""The one HTML layout every system email uses.

Constraints, all chosen so the mail arrives and so it does not look like a
phishing attempt:

* Inline styles only. Gmail strips ``<style>`` blocks, so a layout that
  depends on one renders unstyled for a large share of recipients.
* Nothing loaded from the network -- no images, no web fonts, no tracking
  pixel. A client that blocks remote content must render this identically,
  and Relaydesk has no business learning whether a password-reset mail was
  opened.
* The action URL is shown as text as well as wrapped in a link, because a
  client that strips links must still leave the reader something usable.

The text part is generated from the same ``paragraphs`` the HTML part uses,
rather than kept as a separate constant, so the two cannot drift into
saying different things.
"""

from collections.abc import Sequence
from html import escape

_WRAPPER = (
    "margin:0;padding:24px;background-color:#f5f5f4;"
    "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,"
    "sans-serif;"
)
_CARD = (
    "max-width:520px;margin:0 auto;padding:32px;background-color:#ffffff;"
    "border:1px solid #e7e5e4;border-radius:12px;"
)
_HEADING = (
    "margin:0 0 16px;font-size:20px;line-height:28px;font-weight:600;color:#1c1917;"
)
_PARAGRAPH = "margin:0 0 16px;font-size:15px;line-height:24px;color:#44403c;"
_BUTTON = (
    "display:inline-block;padding:10px 18px;background-color:#1c1917;color:#ffffff;"
    "font-size:15px;font-weight:500;text-decoration:none;border-radius:8px;"
)
_FALLBACK = "margin:16px 0 0;font-size:13px;line-height:20px;color:#78716c;"
_FOOTER = (
    "max-width:520px;margin:16px auto 0;font-size:12px;line-height:18px;color:#a8a29e;"
)


def render(
    *,
    heading: str,
    paragraphs: Sequence[str],
    action_label: str | None = None,
    action_url: str | None = None,
) -> tuple[str, str]:
    """Return ``(text, html)`` for one system email.

    ``heading`` is rendered in the HTML part only. The text part's heading
    is the message's subject line, so repeating it in the body reads as a
    stutter.
    """
    lines = list(paragraphs)
    if action_label and action_url:
        lines.append(f"{action_label}: {action_url}")
    text = "\n\n".join(lines) + "\n"

    body = "".join(
        f'<p style="{_PARAGRAPH}">{escape(paragraph)}</p>' for paragraph in paragraphs
    )
    action = ""
    if action_label and action_url:
        safe_url = escape(action_url, quote=True)
        action = (
            f'<p style="{_PARAGRAPH}">'
            f'<a href="{safe_url}" style="{_BUTTON}">{escape(action_label)}</a>'
            f"</p>"
            f'<p style="{_FALLBACK}">'
            f"If the button does not work, paste this into your browser:<br />"
            f"{escape(action_url)}"
            f"</p>"
        )

    html = (
        f'<div style="{_WRAPPER}">'
        f'<div style="{_CARD}">'
        f'<h1 style="{_HEADING}">{escape(heading)}</h1>'
        f"{body}{action}"
        f"</div>"
        f'<p style="{_FOOTER}">Relaydesk</p>'
        f"</div>"
    )
    return text, html
