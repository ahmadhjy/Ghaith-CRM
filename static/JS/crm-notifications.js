(function () {
  const cfg = window.CRM_NOTIFY;
  if (!cfg) return;

  const root = document.getElementById('crmNotify');
  const bell = document.getElementById('crmNotifyBell');
  const panel = document.getElementById('crmNotifyPanel');
  const badge = document.getElementById('crmNotifyBadge');
  const list = document.getElementById('crmNotifyList');
  const markAllBtn = document.getElementById('crmNotifyMarkAll');
  const broadcastForm = document.getElementById('crmNotifyBroadcast');

  const COUNT_INTERVAL_MS = 90000;
  const OPEN_INTERVAL_MS = 45000;
  let countTimer = null;
  let openTimer = null;
  let pushRegistered = false;
  let listLoaded = false;

  function csrfHeaders() {
    return {
      'Content-Type': 'application/json',
      'X-CSRFToken': cfg.csrfToken,
    };
  }

  function formatTime(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleString();
  }

  function setBadge(count) {
    if (!badge) return;
    if (count > 0) {
      badge.hidden = false;
      badge.textContent = count > 99 ? '99+' : String(count);
    } else {
      badge.hidden = true;
    }
  }

  function isOpen() {
    return root.classList.contains('is-open');
  }

  function renderNotifications(items) {
    if (!items.length) {
      list.innerHTML = '<p class="crm-notify__empty">No notifications yet.</p>';
      return;
    }
    list.innerHTML = items.map(function (n) {
      return (
        '<button type="button" class="crm-notify__item' + (n.is_read ? '' : ' is-unread') + '" data-id="' + n.id + '" data-url="' + (n.url || '') + '">' +
        '<div class="crm-notify__item-kind">' + escapeHtml(n.kind_label) + '</div>' +
        '<div class="crm-notify__item-title">' + escapeHtml(n.title) + '</div>' +
        (n.message ? '<div class="crm-notify__item-msg">' + escapeHtml(n.message) + '</div>' : '') +
        '<div class="crm-notify__item-time">' + formatTime(n.created_at) + '</div>' +
        '</button>'
      );
    }).join('');

    list.querySelectorAll('.crm-notify__item').forEach(function (btn) {
      btn.addEventListener('click', function () {
        const id = btn.getAttribute('data-id');
        const url = btn.getAttribute('data-url');
        fetch(cfg.markReadUrl, {
          method: 'POST',
          headers: csrfHeaders(),
          body: JSON.stringify({ id: Number(id) }),
          credentials: 'same-origin',
        }).then(function () {
          if (url) window.location.href = url;
          else fetchNotifications();
        });
      });
    });
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

  function countUrl() {
    const sep = cfg.listUrl.indexOf('?') >= 0 ? '&' : '?';
    return cfg.listUrl + sep + 'count_only=1';
  }

  function fetchCount() {
    return fetch(countUrl(), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        setBadge((data.unread_count || 0) + (data.unread_messages || 0));
      })
      .catch(function () {});
  }

  function fetchNotifications() {
    if (!listLoaded) {
      list.innerHTML = '<p class="crm-notify__empty">Loading…</p>';
    }
    return fetch(cfg.listUrl, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        listLoaded = true;
        setBadge((data.unread_count || 0) + (data.unread_messages || 0));
        renderNotifications(data.notifications || []);
      })
      .catch(function () {
        list.innerHTML = '<p class="crm-notify__empty">Could not load notifications.</p>';
      });
  }

  function startCountPolling() {
    stopCountPolling();
    countTimer = setInterval(fetchCount, COUNT_INTERVAL_MS);
  }

  function stopCountPolling() {
    if (countTimer) {
      clearInterval(countTimer);
      countTimer = null;
    }
  }

  function startOpenPolling() {
    stopOpenPolling();
    openTimer = setInterval(fetchNotifications, OPEN_INTERVAL_MS);
  }

  function stopOpenPolling() {
    if (openTimer) {
      clearInterval(openTimer);
      openTimer = null;
    }
  }

  function openPanel() {
    root.classList.add('is-open');
    panel.hidden = false;
    bell.setAttribute('aria-expanded', 'true');
    stopCountPolling();
    fetchNotifications();
    startOpenPolling();
    if (!pushRegistered) {
      pushRegistered = true;
      registerPush();
    }
  }

  function closePanel() {
    root.classList.remove('is-open');
    bell.setAttribute('aria-expanded', 'false');
    stopOpenPolling();
    startCountPolling();
    window.setTimeout(function () {
      if (!isOpen()) panel.hidden = true;
    }, 200);
  }

  function togglePanel() {
    if (isOpen()) closePanel();
    else openPanel();
  }

  bell.addEventListener('click', function (e) {
    e.stopPropagation();
    togglePanel();
  });

  document.addEventListener('click', function (e) {
    if (isOpen() && !root.contains(e.target)) closePanel();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && isOpen()) closePanel();
  });

  if (markAllBtn) {
    markAllBtn.addEventListener('click', function () {
      fetch(cfg.markReadUrl, {
        method: 'POST',
        headers: csrfHeaders(),
        body: JSON.stringify({ all: true }),
        credentials: 'same-origin',
      }).then(fetchNotifications);
    });
  }

  if (broadcastForm) {
    broadcastForm.addEventListener('submit', function (e) {
      e.preventDefault();
      const body = document.getElementById('crmNotifyBroadcastBody').value.trim();
      if (!body) return;
      fetch(cfg.broadcastUrl, {
        method: 'POST',
        headers: csrfHeaders(),
        body: JSON.stringify({ body: body }),
        credentials: 'same-origin',
      }).then(function () {
        document.getElementById('crmNotifyBroadcastBody').value = '';
        fetchNotifications();
      });
    });
  }

  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = window.atob(base64);
    const arr = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
    return arr;
  }

  function registerPush() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
    fetch(cfg.vapidUrl, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.enabled || !data.public_key) return;
        return navigator.serviceWorker.register(cfg.swUrl).then(function (reg) {
          return reg.pushManager.getSubscription().then(function (sub) {
            if (sub) return sub;
            return Notification.requestPermission().then(function (perm) {
              if (perm !== 'granted') return null;
              return reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(data.public_key),
              });
            });
          }).then(function (sub) {
            if (!sub) return;
            const json = sub.toJSON();
            return fetch(cfg.pushSubscribeUrl, {
              method: 'POST',
              headers: csrfHeaders(),
              body: JSON.stringify({
                endpoint: json.endpoint,
                keys: json.keys,
              }),
              credentials: 'same-origin',
            });
          });
        });
      })
      .catch(function () {});
  }

  // Collapsed by default: lightweight badge poll only.
  fetchCount();
  startCountPolling();
})();
