window.getCsrfToken = function (fallback) {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  if (match) return decodeURIComponent(match[1]);
  return fallback || '';
};
