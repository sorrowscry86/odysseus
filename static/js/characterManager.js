// static/js/characterManager.js
// Character management page — load, create, edit, delete, activate characters.

const API_BASE = '';
let _templates = [];
let _editingId = null;
let _pendingAvatarFile = null;

async function loadTemplates() {
  try {
    const res = await fetch(`${API_BASE}/api/presets/templates`);
    _templates = res.ok ? await res.json() : [];
  } catch (e) {
    _templates = [];
  }
  renderGrid();
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderGrid() {
  const grid = document.getElementById('char-grid');
  const addBtn = document.getElementById('char-add-btn');

  // Remove all cards except the add button
  grid.querySelectorAll('.char-card').forEach(el => el.remove());

  _templates
    .filter(t => (t.category || 'character') === 'character')
    .forEach(t => {
      const card = document.createElement('div');
      card.className = 'char-card';
      const avatarHtml = t.avatar_url
        ? `<img class="char-avatar" src="${esc(t.avatar_url)}" alt="${esc(t.name)}">`
        : `<div class="char-avatar-placeholder">👤</div>`;
      card.innerHTML = `
        <div class="char-card-header">
          ${avatarHtml}
          <div>
            <div class="char-card-name">${esc(t.name)}</div>
            <div class="char-card-temp">temp ${(t.temperature ?? 1.0).toFixed(1)}</div>
          </div>
        </div>
        <div class="char-card-prompt">${esc((t.system_prompt || '').substring(0, 150))}</div>
        <div class="char-card-actions">
          <button class="btn-edit" data-id="${esc(t.id)}">Edit</button>
          <button class="btn-activate" data-id="${esc(t.id)}">Start Chat</button>
          <button class="btn-danger btn-delete" data-id="${esc(t.id)}">Delete</button>
        </div>
      `;
      card.querySelector('.btn-edit').addEventListener('click', () => openModal(t));
      card.querySelector('.btn-activate').addEventListener('click', () => activateAndChat(t));
      card.querySelector('.btn-delete').addEventListener('click', () => deleteTemplate(t));
      grid.insertBefore(card, addBtn);
    });
}

function openModal(template = null) {
  _editingId = template ? template.id : null;
  _pendingAvatarFile = null;

  document.getElementById('char-modal-title').textContent = template ? 'Edit Character' : 'New Character';
  document.getElementById('char-modal-id').value = template ? template.id : '';
  document.getElementById('char-modal-name').value = template ? template.name : '';
  document.getElementById('char-modal-prompt').value = template ? (template.system_prompt || '') : '';
  const tempInput = document.getElementById('char-modal-temp');
  const tempVal = document.getElementById('char-modal-temp-val');
  tempInput.value = template ? (template.temperature ?? 1.0) : 1.0;
  tempVal.textContent = parseFloat(tempInput.value).toFixed(1);
  document.getElementById('char-modal-tokens').value = template ? (template.max_tokens || 0) : 0;

  const preview = document.getElementById('char-modal-avatar-preview');
  if (template && template.avatar_url) {
    preview.innerHTML = `<img src="${esc(template.avatar_url)}" style="width:48px;height:48px;border-radius:50%;object-fit:cover;">`;
  } else {
    preview.innerHTML = '👤';
  }

  document.getElementById('char-modal-backdrop').classList.add('open');
  document.getElementById('char-modal-name').focus();
}

async function saveModal() {
  const id = document.getElementById('char-modal-id').value;
  const name = document.getElementById('char-modal-name').value.trim();
  if (!name) { alert('Name is required.'); return; }

  const rawTokens = parseInt(document.getElementById('char-modal-tokens').value) || 0;
  const template = {
    id: id || '',
    name,
    system_prompt: document.getElementById('char-modal-prompt').value,
    temperature: parseFloat(document.getElementById('char-modal-temp').value),
    max_tokens: rawTokens > 65536 ? 0 : rawTokens,
    avatar_url: _editingId
      ? (_templates.find(t => t.id === _editingId)?.avatar_url || '')
      : '',
    category: 'character',
  };

  const res = await fetch(`${API_BASE}/api/presets/templates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(template),
  });
  if (!res.ok) { alert('Failed to save character.'); return; }
  const data = await res.json();

  // Upload avatar if one was selected
  if (_pendingAvatarFile && data.template) {
    const savedId = data.template.id;
    const fd = new FormData();
    fd.append('file', _pendingAvatarFile);
    await fetch(`${API_BASE}/api/presets/templates/${savedId}/avatar`, {
      method: 'POST', body: fd,
    });
  }

  document.getElementById('char-modal-backdrop').classList.remove('open');
  await loadTemplates();
}

async function deleteTemplate(t) {
  if (!confirm(`Delete "${t.name}"? This cannot be undone.`)) return;
  await fetch(`${API_BASE}/api/presets/templates/${t.id}`, { method: 'DELETE' });
  await loadTemplates();
}

async function activateAndChat(t) {
  const maxTok = t.max_tokens || 0;
  await fetch(`${API_BASE}/api/presets/custom`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: t.name,
      enabled: true,
      temperature: t.temperature ?? 1.0,
      max_tokens: maxTok,
      system_prompt: t.system_prompt || '',
      inject_prefix: '',
      inject_suffix: '',
    }),
  });
  window.location.href = '/';
}

// ── Wiring ──
document.getElementById('char-add-btn').addEventListener('click', () => openModal());
document.getElementById('char-modal-cancel').addEventListener('click', () => {
  document.getElementById('char-modal-backdrop').classList.remove('open');
});
document.getElementById('char-modal-save').addEventListener('click', saveModal);
document.getElementById('char-modal-temp').addEventListener('input', e => {
  document.getElementById('char-modal-temp-val').textContent = parseFloat(e.target.value).toFixed(1);
});
document.getElementById('char-modal-backdrop').addEventListener('click', e => {
  if (e.target === document.getElementById('char-modal-backdrop')) {
    document.getElementById('char-modal-backdrop').classList.remove('open');
  }
});

// Avatar upload
document.getElementById('char-modal-avatar-preview').addEventListener('click', () => {
  document.getElementById('char-avatar-upload').click();
});
document.getElementById('char-avatar-upload').addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  _pendingAvatarFile = file;
  const url = URL.createObjectURL(file);
  const preview = document.getElementById('char-modal-avatar-preview');
  preview.innerHTML = `<img src="${url}" style="width:48px;height:48px;border-radius:50%;object-fit:cover;">`;
});

// Initial load
loadTemplates();
