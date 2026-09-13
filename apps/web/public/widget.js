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
  var skel = null;
  var loaded = false;
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
    "#rdw,#rds{position:fixed;" + side + ":24px;bottom:96px;width:380px;height:600px;" +
    "transition:width .22s ease,height .22s ease;" +
    "border:0;border-radius:16px;z-index:2147480000;box-shadow:0 10px 38px" +
    " -10px rgba(9,9,11,.2)}" +
    // Above the iframe, not behind it: a document that has not arrived
    // yet still paints its own opaque white, so a skeleton underneath
    // would never be seen. Hidden the moment the frame loads.
    "#rds{background:#fff;overflow:hidden;z-index:2147480001}" +
    "#rds i{position:absolute;background:#e4e4e7;border-radius:8px;" +
    "animation:rdp 1.1s ease-in-out infinite}@keyframes rdp{50%{opacity:.4}}" +
    "@media(prefers-color-scheme:dark){#rds{background:#18181b}" +
    "#rds i{background:#27272a}}" +
    "@media(prefers-reduced-motion:reduce){" +
    "#rdw{transition:none}#rds i{animation:none}}" +
    "@media(min-width:1024px){#rdw,#rds{width:440px;" +
    "height:min(700px,calc(100vh - 140px))}}@media(max-width:480px){#rdw,#rds{" +
    "inset:0;width:100%;height:100%;border-radius:0}}";
  document.head.appendChild(style);

  // Appended after `style`, so its rule wins at equal specificity when it
  // has one. Empty until the panel asks to grow.
  var grow = document.createElement("style");
  document.head.appendChild(grow);

  // Drawn in the host page while the frame's document is still in
  // flight. Until it arrives the iframe is a blank white rectangle, and
  // on a slow connection that is the first thing a visitor sees of the
  // product. Shapes only -- a header line, two messages, a composer --
  // and aria-hidden, because there is nothing here to read.
  function skeleton() {
    skel = document.createElement("div");
    skel.id = "rds";
    skel.setAttribute("aria-hidden", "true");
    skel.innerHTML =
      "<i style='top:22px;left:20px;width:42%;height:16px'></i>" +
      "<i style='top:50px;left:20px;width:64%;height:12px'></i>" +
      "<i style='top:104px;left:20px;width:70%;height:52px'></i>" +
      "<i style='top:172px;right:20px;width:52%;height:38px'></i>" +
      "<i style='bottom:20px;left:20px;right:20px;height:44px'></i>";
    mount(skel);
    return skel;
  }

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
    frame.addEventListener("load", function () {
      loaded = true;
      skel.style.display = "none";
    });
    skeleton();
    mount(frame);
    return frame;
  }

  // Where focus returns to the launcher, for all three close paths.
  function hide() {
    open = false;
    if (frame) frame.style.display = "none";
    if (skel) skel.style.display = "none";
    launcher.focus();
  }

  launcher.addEventListener("click", function () {
    if (open) return hide();
    open = true;
    panel().style.display = "block";
    // A visitor who closes the panel before it has loaded and opens it
    // again still has nothing to look at, so the skeleton comes back.
    if (!loaded) skel.style.display = "block";
  });

  window.addEventListener("message", function (event) {
    if (event.origin !== origin) return;
    if (event.data === "relaydesk:close") {
      if (open) hide();
      return;
    }
    // The panel asks to grow when a visitor is reading or in a
    // conversation, and to shrink coming back.
    //
    // Through a stylesheet rather than inline styles. Inline width and
    // height outrank the max-width:480px takeover below, and nothing
    // cleared them -- so expanding on a laptop and then narrowing the
    // window (or rotating a tablet) left the panel pinned to all four
    // edges at a fixed size. Wrapping the rule in the same min-width
    // query the large size already uses means it does not exist at all on
    // a small screen, so no innerWidth guard is needed -- and a collapse
    // arriving after the window shrank is no longer dropped.
    if (event.data === "relaydesk:expand" || event.data === "relaydesk:collapse") {
      grow.textContent =
        event.data === "relaydesk:expand"
          ? "@media(min-width:1024px){#rdw,#rds{width:min(720px,calc(100vw - 48px));" +
            "height:min(820px,calc(100vh - 120px))}}"
          : "";
    }
  });

  mount(launcher);

  // Console settings win once they arrive. Silent on failure: the
  // launcher is already drawn, and nobody is owed a note about a colour.
  fetch(origin + "/widget/launcher?key=" + encodeURIComponent(key))
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (s) {
      if (!s) return;
      // `null` means this key has no colour of its own and the launcher
      // should go back to the default -- distinct from the field being
      // absent. Testing truthiness treated the two the same, so clearing
      // a colour in the console did nothing on a live site and the
      // launcher kept whatever the pasted snippet carried.
      if (s.accent !== undefined) {
        var next = s.accent || "#18181B";
        if (next !== accent) {
          launcher.style.background = next;
          accent = next;
        }
      }
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
