(function () {
  if (!document.querySelector('link[rel="icon"]')) {
    var icon = document.querySelector('meta[name="crm-favicon"]');
    var href = icon ? icon.getAttribute('content') : '/static/img/favicon.svg';
    var link = document.createElement('link');
    link.rel = 'icon';
    link.type = 'image/svg+xml';
    link.href = href;
    document.head.appendChild(link);

    var apple = document.createElement('link');
    apple.rel = 'apple-touch-icon';
    apple.href = href;
    document.head.appendChild(apple);
  }

  document.body.classList.add("has-unified-nav", "req-page");

  const nav = document.getElementById("appNav");
  const toggle = document.getElementById("appNavToggle");
  const closeBtn = document.getElementById("appNavClose");
  const backdrop = document.getElementById("appNavBackdrop");

  if (!nav || !toggle || !backdrop) return;

  function openNav() {
    nav.classList.add("is-open");
    backdrop.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
    document.body.style.overflow = "hidden";
  }

  function closeNav() {
    nav.classList.remove("is-open");
    backdrop.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
    document.body.style.overflow = "";
  }

  toggle.addEventListener("click", function () {
    if (nav.classList.contains("is-open")) closeNav();
    else openNav();
  });

  if (closeBtn) closeBtn.addEventListener("click", closeNav);
  backdrop.addEventListener("click", closeNav);

  window.addEventListener("resize", function () {
    if (window.innerWidth > 900) closeNav();
  });

  // Highlight current page in the sidebar
  const currentPath = window.location.pathname;
  const links = nav.querySelectorAll('.app-nav__item[href], .app-nav__group > a');

  links.forEach(function (link) {
    let linkPath;
    try {
      linkPath = new URL(link.href, window.location.origin).pathname;
    } catch (e) {
      return;
    }

    const isMatch = linkPath === currentPath
      || (linkPath.length > 1 && currentPath.startsWith(linkPath));

    if (isMatch) {
      link.classList.add('is-active');
      const group = link.closest('.app-nav__group');
      if (group) group.open = true;
    }
  });
})();
