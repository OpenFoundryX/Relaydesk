(function () {
  var tag = document.currentScript;
  var key = tag && tag.getAttribute("data-key");
  if (!key) return;

  // One launcher per page; claimed only once the key is valid.
  if (window.__relaydeskWidget) return;
  window.__relaydeskWidget = true;

  var origin = new URL(tag.src).origin;
  // Prefill only (spec D4).
  var email = tag.getAttribute("data-email") || "";
  var person = tag.getAttribute("data-name") || "";
  // Attributes draw instantly, so a launcher needs no network at all --
  // that is what D6/D10 bought. `/widget/launcher` then corrects them: a
  // colour only changeable by every customer re-pasting their snippet is
  // not really a setting.
  var accent = tag.getAttribute("data-accent") || "#18181B";
  var side = tag.getAttribute("data-position") === "left" ? "left" : "right";
  var frame = null;
  var open = false;

  // async may run before <body> exists; defer to DOMContentLoaded.
  function mount(el) {
    if (document.body) document.body.appendChild(el);
    else document.addEventListener("DOMContentLoaded", function () {
      document.body.appendChild(el);
    });
  }

  var launcher = document.createElement("button");
  launcher.setAttribute("aria-label", "Help");
  launcher.style.cssText =
    "position:fixed;" + side + ":24px;bottom:24px;width:56px;height:56px;" +
    "border:0;border-radius:9999px;background:" + accent + ";color:#fff;" +
    "cursor:pointer;z-index:2147480000;box-shadow:0 10px 38px -10px rgba(9,9,11,.35)";
  launcher.innerHTML =
    '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" ' +
    'stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.7 8.7 0 ' +
    '0 1-3.8-.9L3 20.5l1.6-4.9A8.4 8.4 0 0 1 12 3.1a8.4 8.4 0 0 1 9 8.4Z"/></svg>';

  // Full-screen under 480px; a <style> tag carries the media query.
  var style = document.createElement("style");
  style.textContent =
    "#rdw{position:fixed;" + side + ":24px;bottom:96px;width:380px;height:600px;" +
    "border:0;border-radius:16px;z-index:2147480000;box-shadow:0 10px 38px" +
    " -10px rgba(9,9,11,.2)}@media(min-width:1024px){#rdw{width:440px;" +
    "height:min(700px,calc(100vh - 140px))}}@media(max-width:480px){#rdw{" +
    "inset:0;width:100%;height:100%;border-radius:0}}";
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
      (person ? "&name=" + encodeURIComponent(person) : "") +
      (window.innerWidth >= 1024 ? "&wide=1" : "");
    mount(frame);
    return frame;
  }

  // Where focus returns to the launcher, for all three close paths.
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

  // Console settings win once they arrive. Silent on failure: the
  // launcher is already drawn, and nobody is owed a note about a colour.
  fetch(origin + "/widget/launcher?key=" + encodeURIComponent(key))
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (s) {
      if (!s) return;
      if (s.accent && s.accent !== accent) launcher.style.background = s.accent;
      if (s.position && s.position !== side) {
        launcher.style[side] = "";
        launcher.style[s.position] = "24px";
        style.textContent = style.textContent.split(side + ":24px")
          .join(s.position + ":24px");
        side = s.position;
      }
    })
    .catch(function () {});
})();
