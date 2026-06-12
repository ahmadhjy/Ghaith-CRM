function resolveUrl(url) {
  if (!url) return self.location.origin + '/';
  try {
    return new URL(url, self.location.origin).href;
  } catch (e) {
    return self.location.origin + '/';
  }
}

self.addEventListener('push', function (event) {
  let data = { title: 'Ghaith CRM', body: '', url: '/' };
  try {
    if (event.data) {
      data = Object.assign(data, event.data.json());
    }
  } catch (e) {}

  const options = {
    body: data.body || '',
    icon: resolveUrl(data.icon || '/static/css/favicon.ico'),
    badge: resolveUrl(data.icon || '/static/css/favicon.ico'),
    tag: data.tag || 'crm-notification',
    renotify: true,
    data: { url: resolveUrl(data.url || '/') },
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'Ghaith CRM', options)
  );
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
      for (let i = 0; i < list.length; i++) {
        const client = list[i];
        if ('focus' in client) {
          if (targetUrl && 'navigate' in client) {
            return client.navigate(targetUrl).then(function () {
              return client.focus();
            });
          }
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
