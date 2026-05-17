const WS_URL = 'ws://localhost:8001/ws/assist';
let ws = null;
let callId = null;
let copilotActive = false;
let paused = false;

const statusBadge = document.getElementById('status-badge');
const transcriptDiv = document.getElementById('transcript');
const checklist = document.getElementById('checklist');
const alertBanner = document.getElementById('alert-banner');

function connect(callIdParam) {
  callId = callIdParam;
  if (ws) ws.close();

  ws = new WebSocket(`${WS_URL}?call_id=${callId}&token=`);
  statusBadge.textContent = 'Conectando...';
  statusBadge.className = 'status disconnected';

  ws.onopen = () => {
    statusBadge.textContent = '🟢 Online';
    statusBadge.className = 'status';
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleMessage(msg);
  };

  ws.onclose = () => {
    statusBadge.textContent = '🔴 Desconectado';
    statusBadge.className = 'status disconnected';
    setTimeout(() => connect(callId), 3000);
  };

  ws.onerror = () => {
    statusBadge.textContent = '⚠ Erro';
    statusBadge.className = 'status fallback';
  };
}

function handleMessage(msg) {
  switch (msg.type) {
    case 'transcript':
      transcriptDiv.textContent = `${msg.speaker}: ${msg.text}`;
      break;

    case 'entities':
      const entityText = Object.entries(msg.data)
        .map(([type, items]) => `${type}: ${items.map(i => i.value).join(', ')}`)
        .join(' | ');
      showAlert(entityText, 'info');
      break;

    case 'alert':
      showAlert(msg.message, msg.severity);
      break;

    case 'checklist':
      renderChecklist(msg.items);
      break;

    case 'stt_status':
      const label = msg.fallback ? 'Fallback' : 'Deepgram';
      statusBadge.textContent = `🟢 ${label}`;
      break;
  }
}

function showAlert(message, severity) {
  alertBanner.textContent = message;
  alertBanner.className = `alert-banner ${severity}`;
  setTimeout(() => { alertBanner.className = 'alert-banner'; }, 5000);
}

function renderChecklist(items) {
  checklist.innerHTML = items.map(item => `
    <div class="check-item ${item.done ? 'done' : ''}">
      <span class="icon">${item.done ? '✅' : '⬜'}</span>
      <span class="text">${item.text}</span>
    </div>
  `).join('');
}

function toggleCopilot() {
  copilotActive = !copilotActive;
  document.getElementById('btn-copilot').classList.toggle('active', copilotActive);
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'copilot', active: copilotActive }));
  }
}

function togglePause() {
  paused = !paused;
  document.getElementById('btn-pause').classList.toggle('active', paused);
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'pause', active: paused }));
  }
}

document.addEventListener('DOMContentLoaded', () => {
  connect('initial');
});
