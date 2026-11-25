const $ = (id) => document.getElementById(id);

// Empty = backend is served from the same origin.
// On Vercel, set window.RDS_API_BASE = "https://backend.example.com" in index.html.
const API_BASE = (window.RDS_API_BASE || "").replace(/\/$/, "");
const apiUrl = (path) => `${API_BASE}${path}`;

function websocketUrl() {
  if (!API_BASE) {
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    return `${scheme}://${location.host}/ws`;
  }
  const u = new URL(API_BASE, location.href);
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
  u.pathname = '/ws';
  u.search = '';
  u.hash = '';
  return u.toString();
}

function duration(sec) {
  sec = Number(sec) || 0;
  const m = Math.floor(sec / 60), s = sec % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function render(state) {
  if (!state || !state.totals) return;
  $('tot-people').textContent = state.totals.people;
  $('tot-tables').textContent = state.totals.tables;
  $('tot-chairs').textContent = state.totals.chairs || 0;
  $('tot-occupied').textContent = state.totals.occupied;
  $('tot-free').textContent = state.totals.free;
  $('tot-served').textContent = state.totals.served;

  const grid = $('tables');
  grid.innerHTML = state.tables.map(t => {
    const badge = t.free ? 'free' : (t.served ? 'served' : 'occupied');
    const badgeText = t.free ? 'FREE' : (t.served ? 'SERVED' : 'OCCUPIED');
    const people = t.people.map(p => `P${p.track_id} (in ${p.entry_hhmmss}, ${duration(p.duration_sec)})`).join(', ') || '—';
    return `<div class="table-card ${t.free ? '' : 'occupied'} ${t.served ? 'served' : ''}">
      <div class="title"><span>${t.label}</span><span class="badge ${badge}">${badgeText}</span></div>
      <div class="meta">People: <b>${t.count}</b><br>${people}<br>
      Served at: ${t.served_at ? new Date(t.served_at).toLocaleTimeString() : '—'}</div>
      <div class="buttons">
        <button class="serve" data-serve="${t.id}" ${t.free ? 'disabled' : ''}>Mark served</button>
        <button class="clear" data-clear="${t.id}">Clear</button>
      </div>
    </div>`;
  }).join('');

  const tbody = document.querySelector('#people-table tbody');
  tbody.innerHTML = state.people.map(p => `<tr>
    <td>P${p.track_id}</td><td>${p.entry_hhmmss}</td>
    <td>${duration(p.duration_sec)}</td><td>${p.table_id || '—'}</td>
  </tr>`).join('') || '<tr><td colspan="4">No people detected</td></tr>';

  $('clock').textContent = new Date(state.timestamp).toLocaleTimeString();
}

async function post(url) {
  await fetch(url, { method: 'POST' });
}

document.addEventListener('click', (e) => {
  const serve = e.target.closest('[data-serve]');
  const clear = e.target.closest('[data-clear]');
  if (serve) post(apiUrl(`/api/tables/${encodeURIComponent(serve.dataset.serve)}/serve`));
  if (clear) post(apiUrl(`/api/tables/${encodeURIComponent(clear.dataset.clear)}/clear`));
});

async function loadEvents() {
  try {
    const res = await fetch(apiUrl('/api/events?limit=40'));
    const data = await res.json();
    $('events').innerHTML = data.events.map(ev => `<div class="ev">
      <time>${new Date(ev.ts).toLocaleTimeString()}</time>
      <b>${ev.type}</b> ${ev.table_id || ''} ${ev.message || ''}
    </div>`).join('') || '<div class="ev">No events yet</div>';
  } catch (_) {}
}

function connect() {
  const ws = new WebSocket(websocketUrl());
  ws.onmessage = (e) => {
    try { render(JSON.parse(e.data)); } catch (_) {}
  };
  ws.onclose = () => setTimeout(connect, 1500);
}

$('feed').src = apiUrl('/video_feed');
connect();
loadEvents();
setInterval(loadEvents, 3000);
