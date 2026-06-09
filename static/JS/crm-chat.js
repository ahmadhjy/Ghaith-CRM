(function () {
  const cfg = window.CRM_CHAT;
  if (!cfg) return;

  const userListEl = document.getElementById('crmChatUserList');
  const placeholder = document.getElementById('crmChatPlaceholder');
  const thread = document.getElementById('crmChatThread');
  const threadHead = document.getElementById('crmChatThreadHead');
  const messagesEl = document.getElementById('crmChatMessages');
  const form = document.getElementById('crmChatForm');
  const input = document.getElementById('crmChatInput');

  let activeUserId = cfg.initialUserId || null;
  let pollTimer = null;

  function csrfHeaders() {
    return {
      'Content-Type': 'application/json',
      'X-CSRFToken': cfg.csrfToken,
    };
  }

  function formatTime(iso) {
    return iso ? new Date(iso).toLocaleString() : '';
  }

  function renderUsers(users) {
    if (!users.length) {
      userListEl.innerHTML = '<p class="crm-notify__empty">No other users.</p>';
      return;
    }
    userListEl.innerHTML = users.map(function (u) {
      const active = u.id === activeUserId ? ' is-active' : '';
      const unread = u.unread > 0
        ? '<span class="crm-chat__user-unread">' + u.unread + '</span>'
        : '';
      return (
        '<button type="button" class="crm-chat__user' + active + '" data-id="' + u.id + '">' +
        '<div class="crm-chat__user-name">' + escapeHtml(u.name) + unread + '</div>' +
        (u.last_message ? '<div class="crm-chat__user-preview">' + escapeHtml(u.last_message) + '</div>' : '') +
        '</button>'
      );
    }).join('');

    userListEl.querySelectorAll('.crm-chat__user').forEach(function (btn) {
      btn.addEventListener('click', function () {
        selectUser(Number(btn.getAttribute('data-id')));
      });
    });
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

  function renderMessages(messages) {
    messagesEl.innerHTML = messages.map(function (m) {
      const cls = m.is_mine ? 'is-mine' : 'is-theirs';
      return (
        '<div class="crm-chat__bubble ' + cls + '">' +
        escapeHtml(m.body) +
        '<div class="crm-chat__bubble-time">' + formatTime(m.created_at) + '</div>' +
        '</div>'
      );
    }).join('');
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function loadThread() {
    if (!activeUserId) return;
    fetch(cfg.threadUrlBase + activeUserId + '/', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        threadHead.textContent = data.user.name;
        renderMessages(data.messages || []);
      });
  }

  function selectUser(userId) {
    activeUserId = userId;
    placeholder.hidden = true;
    thread.hidden = false;
    loadUsers();
    loadThread();
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(loadThread, 8000);
  }

  function loadUsers() {
    fetch(cfg.usersUrl, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderUsers(data.users || []);
      });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    const body = input.value.trim();
    if (!body || !activeUserId) return;
    fetch(cfg.sendUrl, {
      method: 'POST',
      headers: csrfHeaders(),
      body: JSON.stringify({ recipient_id: activeUserId, body: body }),
      credentials: 'same-origin',
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.status === 'ok') {
          input.value = '';
          loadThread();
          loadUsers();
        }
      });
  });

  loadUsers();
  if (activeUserId) selectUser(activeUserId);
})();
