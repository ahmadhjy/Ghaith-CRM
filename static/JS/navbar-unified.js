(function () {
  document.body.classList.add("has-unified-nav");

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
})();
