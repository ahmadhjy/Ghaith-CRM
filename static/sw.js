const DEFAULT_ICON = '/static/img/favicon.svg';

self.addEventListener('install', function (event) {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
});

function resolveIcon(path) {
  if (!path) return new URL(DEFAULT_ICON, self.location.origin).href;
  try {
    return new URL(path, self.location.origin).href;
  } catch (e) {
    return new URL(DEFAULT_ICON, self.location.origin).href;
  }
}

function notifyAllClients(payload) {
  return self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
    list.forEach(function (client) {
      client.postMessage({ type: 'crm-push', payload: payload });
    });
  });
}

self.addEventListener('push', function (event) {
  let data = { title: 'Ghaith CRM', body: '', url: '/' };
  try {
    if (event.data) {
      data = Object.assign(data, event.data.json());
    }
  } catch (e) {}

  const icon = resolveIcon(data.icon);
  const targetUrl = data.url || '/';
  const options = {
    body: data.body || '',
    icon: icon,
    badge: resolveIcon(data.badge || data.icon),
    tag: data.tag || targetUrl,
    renotify: true,
    requireInteraction: false,
    silent: false,
    data: { url: targetUrl },
  };

  event.waitUntil(
    Promise.all([
      self.registration.showNotification(data.title || 'Ghaith CRM', options),
      notifyAllClients({
        title: data.title || 'Ghaith CRM',
        body: data.body || '',
        url: targetUrl,
        icon: icon,
      }),
    ])
  );
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/';
  const absoluteUrl = new URL(targetUrl, self.location.origin).href;

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
      for (let i = 0; i < list.length; i++) {
        const client = list[i];
        if ('focus' in client) {
          if ('navigate' in client) {
            return client.navigate(absoluteUrl).then(function () {
              return client.focus();
            });
          }
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(absoluteUrl);
      }
    })
  );
});
