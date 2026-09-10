(function () {
  // The <script> tag's shape is frozen once a customer pastes it, but this
  // file is not -- a re-run guard is safe to add here for a duplicate
  // paste, a tag-manager duplicate, or an SPA re-injecting the tag on
  // navigation, all of which would otherwise draw a second launcher.
  if (window.__relaydeskWidget) return;
  window.__relaydeskWidget = true;

  var tag = document.currentScript;
  var key = tag && tag.getAttribute("data-key");
  if (!key) return;

  var origin = new URL(tag.src).origin;
  // Prefill only. Nothing can be read with an address, because the widget
  // never reads a conversation (spec D4) -- so this is not an
  // authentication claim and needs no signature.
  var email = tag.getAttribute("data-email") || "";
  var person = tag.getAttribute("data-name") || "";
  var frame = null;
  var open = false;

  var launcher = document.createElement("button");
  launcher.setAttribute("aria-label", "Help");
  launcher.style.cssText =
    "position:fixed;right:24px;bottom:24px;width:56px;height:56px;border:0;" +
    "border-radius:9999px;background:#18181B;color:#fff;cursor:pointer;" +
    "z-index:2147480000;box-shadow:0 10px 38px -10px rgba(9,9,11,.35)";
  launcher.innerHTML =
    '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" ' +
    'stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.7 8.7 0 ' +
    '0 1-3.8-.9L3 20.5l1.6-4.9A8.4 8.4 0 0 1 12 3.1a8.4 8.4 0 0 1 9 8.4Z"/></svg>';

  function panel() {
    if (frame) return frame;
    frame = document.createElement("iframe");
    frame.title = "Help";
    frame.src =
      origin +
      "/widget/frame?key=" +
      encodeURIComponent(key) +
      (email ? "&email=" + encodeURIComponent(email) : "") +
      (person ? "&name=" + encodeURIComponent(person) : "");
    frame.style.cssText =
      "position:fixed;right:24px;bottom:96px;width:380px;height:600px;border:0;" +
      "border-radius:16px;z-index:2147480000;" +
      "box-shadow:0 10px 38px -10px rgba(9,9,11,.20)";
    document.body.appendChild(frame);
    return frame;
  }

  // Closing by any of the three paths (launcher toggle, Esc inside the
  // frame, or the frame's close button) hides the same element, so a single
  // function is the one place focus returns to the launcher -- the frame is
  // a separate cross-origin document and cannot move focus in this page
  // itself.
  function hide() {
    open = false;
    if (frame) frame.style.display = "none";
    launcher.focus();
  }

  launcher.addEventListener("click", function () {
    if (open) {
      hide();
      return;
    }
    open = true;
    panel().style.display = "block";
  });

  window.addEventListener("message", function (event) {
    if (event.origin !== origin || event.data !== "relaydesk:close") return;
    if (open) hide();
  });

  document.body.appendChild(launcher);
})();
