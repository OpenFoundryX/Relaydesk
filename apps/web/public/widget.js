(function () {
  var tag = document.currentScript;
  var key = tag && tag.getAttribute("data-key");
  if (!key) return;

  // Stops a duplicate tag drawing a second launcher; claimed only once
  // the key is valid, so a bad tag never blocks a later good one.
  if (window.__relaydeskWidget) return;
  window.__relaydeskWidget = true;

  var origin = new URL(tag.src).origin;
  // Prefill only -- the widget never reads a conversation (spec D4).
  var email = tag.getAttribute("data-email") || "";
  var person = tag.getAttribute("data-name") || "";
  var frame = null;
  var open = false;

  // <script async> may run before <body> exists; defer to DOMContentLoaded.
  function mount(el) {
    if (document.body) document.body.appendChild(el);
    else document.addEventListener("DOMContentLoaded", function () {
      document.body.appendChild(el);
    });
  }

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

  // Below ~480px: a full-screen takeover (spec 7), via a <style> tag since
  // an inline style can't carry the media query it takes to express one.
  var style = document.createElement("style");
  style.textContent =
    "#rdw{position:fixed;right:24px;bottom:96px;width:380px;height:600px;" +
    "border:0;border-radius:16px;z-index:2147480000;box-shadow:0 10px 38px" +
    " -10px rgba(9,9,11,.2)}@media(max-width:480px){#rdw{inset:0;" +
    "width:100%;height:100%;border-radius:0}}";
  document.head.appendChild(style);

  function panel() {
    if (frame) return frame;
    frame = document.createElement("iframe");
    frame.id = "rdw";
    frame.title = "Help";
    frame.src =
      origin +
      "/widget/frame?key=" +
      encodeURIComponent(key) +
      (email ? "&email=" + encodeURIComponent(email) : "") +
      (person ? "&name=" + encodeURIComponent(person) : "");
    mount(frame);
    return frame;
  }

  // The one place focus returns to the launcher, for all three close paths.
  function hide() {
    open = false;
    if (frame) frame.style.display = "none";
    launcher.focus();
  }

  launcher.addEventListener("click", function () {
    if (open) return hide();
    open = true;
    panel().style.display = "block";
  });

  window.addEventListener("message", function (event) {
    if (event.origin !== origin || event.data !== "relaydesk:close") return;
    if (open) hide();
  });

  mount(launcher);
})();
