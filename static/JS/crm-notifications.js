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
  const pushBanner = document.getElementById('crmNotifyPushBanner');
  const pushEnableBtn = document.getElementById('crmNotifyPushEnable');
  const pushDismissBtn = document.getElementById('crmNotifyPushDismiss');

  const COUNT_INTERVAL_MS = 90000;
  const OPEN_INTERVAL_MS = 45000;
  const PUSH_DISMISS_KEY = 'crm_push_banner_dismissed';
  let countTimer = null;
  let openTimer = null;
  let listLoaded = false;
  let swRegistration = null;

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

  function hidePushBanner() {
    if (pushBanner) pushBanner.hidden = true;
  }

  function showPushBanner() {
    if (!pushBanner) return;
    if (Notification.permission !== 'default') return;
    try {
      const dismissed = localStorage.getItem(PUSH_DISMISS_KEY);
      if (dismissed && Date.now() - Number(dismissed) < 7 * 24 * 60 * 60 * 1000) return;
    } catch (e) {}
    pushBanner.hidden = false;
  }

  function saveSubscription(sub) {
    if (!sub) return Promise.resolve();
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
  }

  function subscribeToPush(reg, publicKey) {
    return reg.pushManager.getSubscription().then(function (existing) {
      if (existing) return existing;
      return reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      });
    });
  }

  function requestPushPermission() {
    if (!('Notification' in window)) return Promise.resolve(null);
    if (Notification.permission === 'granted') return Promise.resolve('granted');
    if (Notification.permission === 'denied') return Promise.resolve('denied');
    return Notification.requestPermission();
  }

  function initPush(promptUser) {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return Promise.resolve();

    return fetch(cfg.vapidUrl, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.enabled || !data.public_key) return null;

        const regOpts = { scope: cfg.swScope || '/' };
        return navigator.serviceWorker.register(cfg.swUrl, regOpts).then(function (reg) {
          swRegistration = reg;

          if (Notification.permission === 'granted') {
            return subscribeToPush(reg, data.public_key).then(saveSubscription).then(hidePushBanner);
          }

          if (!promptUser) {
            showPushBanner();
            return null;
          }

          return requestPushPermission().then(function (perm) {
            if (perm !== 'granted') {
              if (perm === 'denied') hidePushBanner();
              return null;
            }
            return subscribeToPush(reg, data.public_key)
              .then(saveSubscription)
              .then(hidePushBanner);
          });
        });
      })
      .catch(function () {});
  }

  if (pushEnableBtn) {
    pushEnableBtn.addEventListener('click', function () {
      initPush(true);
    });
  }

  if (pushDismissBtn) {
    pushDismissBtn.addEventListener('click', function () {
      hidePushBanner();
      try { localStorage.setItem(PUSH_DISMISS_KEY, String(Date.now())); } catch (e) {}
    });
  }

  // Collapsed by default: lightweight badge poll only.
  fetchCount();
  startCountPolling();

  // Register service worker + subscribe if already granted; otherwise show enable banner.
  window.setTimeout(function () { initPush(false); }, 1500);
})();
