(function () {
    if (window.__reqHoverTooltipInit) return;
    window.__reqHoverTooltipInit = true;

    var tip = document.createElement('div');
    tip.id = 'reqTooltipFloat';
    tip.className = 'req-tooltip-float';
    tip.setAttribute('hidden', '');
    document.body.appendChild(tip);

    var activeEl = null;

    function hide() {
        tip.setAttribute('hidden', '');
        activeEl = null;
    }

    function show(el) {
        var text = el.getAttribute('data-full-text');
        if (!text) return;

        activeEl = el;
        tip.textContent = text;
        tip.removeAttribute('hidden');

        requestAnimationFrame(function () {
            if (activeEl !== el) return;
            var rect = el.getBoundingClientRect();
            var margin = 10;
            var left = rect.left;
            var top = rect.top - tip.offsetHeight - margin;

            if (top < margin) {
                top = rect.bottom + margin;
            }
            if (left + tip.offsetWidth > window.innerWidth - margin) {
                left = window.innerWidth - tip.offsetWidth - margin;
            }
            if (left < margin) {
                left = margin;
            }

            tip.style.left = left + 'px';
            tip.style.top = top + 'px';
        });
    }

    document.addEventListener('mouseover', function (e) {
        var el = e.target.closest('[data-full-text]');
        if (!el || !el.getAttribute('data-full-text')) return;
        if (el.contains(e.relatedTarget)) return;
        show(el);
    });

    document.addEventListener('mouseout', function (e) {
        var el = e.target.closest('[data-full-text]');
        if (!el || !el.getAttribute('data-full-text')) return;
        if (el.contains(e.relatedTarget)) return;
        hide();
    });

    window.addEventListener('scroll', hide, true);
    window.addEventListener('resize', hide);
})();
