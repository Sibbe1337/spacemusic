(() => {
  const root = document.documentElement;
  const pageKind = () => location.pathname === "/" ? "home" : location.pathname.startsWith("/apply") ? "apply" : "content";
  root.dataset.spacePage = pageKind();
  let queued = false;
  function enhance() {
    queued = false;
    root.dataset.spacePage = pageKind();
    const heading = document.querySelector("h1");
    if (heading) {
      if (!heading.id) heading.id = "space-page-heading";
      if (!heading.hasAttribute("tabindex")) heading.tabIndex = -1;
      let skip = document.querySelector(".space-skip");
      if (!skip) {
        skip = document.createElement("a");
        skip.className = "space-skip";
        skip.dataset.spaceAux = "true";
        skip.textContent = "Skip to content";
        document.body.prepend(skip);
      }
      skip.setAttribute("href", `#${heading.id}`);
    }
    document.querySelectorAll("nav.fixed a[href]").forEach(link => {
      const url = new URL(link.href, location.href);
      if (url.origin === location.origin && url.pathname.replace(/\/$/, "") === location.pathname.replace(/\/$/, "")) {
        link.setAttribute("aria-current", "page");
      } else link.removeAttribute("aria-current");
    });
    const menu = document.querySelector('nav.fixed button[aria-label$="menu"]');
    if (menu) {
      const expanded = menu.getAttribute("aria-label") === "Close menu";
      menu.setAttribute("aria-expanded", String(expanded));
      const panel = document.querySelector("nav.fixed .md\\:hidden.overflow-hidden");
      if (panel) {
        if (!panel.id) panel.id = "space-mobile-navigation";
        menu.setAttribute("aria-controls", panel.id);
        panel.inert = !expanded;
      }
    }
    document.querySelectorAll(".overflow-x-auto,.space-blog-table").forEach(region => {
      if (!region.querySelector("table")) return;
      if (!region.hasAttribute("tabindex")) region.tabIndex = 0;
      if (!region.hasAttribute("role")) region.setAttribute("role", "region");
      if (!region.hasAttribute("aria-label") && !region.hasAttribute("aria-labelledby")) region.setAttribute("aria-label", "Data table, scroll horizontally if needed");
    });
    // The existing newsletter placeholder is not an accessible field label.
    document.querySelectorAll('footer input[type="email"]').forEach(input => {
      if (!input.labels.length && !input.hasAttribute("aria-label")) input.setAttribute("aria-label", "Email address for The Catalog Report");
    });
  }
  const schedule = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(enhance);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule, { once: true });
  else schedule();
  // Ignore our own state attributes; observe React's menu label as it changes.
  new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["aria-label"] });
  window.addEventListener("popstate", schedule);
  document.addEventListener("keydown", event => {
    if (event.key !== "Escape") return;
    const menu = document.querySelector('nav.fixed button[aria-label="Close menu"]');
    if (menu) { menu.click(); menu.focus(); }
  });
})();
