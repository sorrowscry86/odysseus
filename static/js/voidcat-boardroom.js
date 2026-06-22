/**
 * voidcat-boardroom.js
 * VoidCat RDC Spirit Communicator — Board Room GUI Module
 *
 * Handles:
 * - Spirit avatar injection into chat bubbles
 * - Mode badge rendering in the chat header
 * - Council progress bar updates
 * - Hearth pulse indicator
 * - Resolution panel rendering
 * - Pass-turn indicator display
 */

'use strict';

// ──────────────────────────────────────────────
// Spirit Roster — maps folder names to display data
// ──────────────────────────────────────────────
const SPIRIT_REGISTRY = {
  ryuzu:            { name: 'Ryuzu',            avatar: '/static/spirits/ryuzu.jpg' },
  albedo:           { name: 'Albedo',           avatar: '/static/spirits/albedo.jpg' },
  beatrice:         { name: 'Beatrice',         avatar: '/static/spirits/beatrice.jpg' },
  codey_coderson:   { name: 'Codey Coderson',   avatar: '/static/spirits/codey_coderson.jpg' },
  sonmi_451:        { name: 'Sonmi-451',        avatar: '/static/spirits/sonmi_451.jpg' },
  pandora:          { name: 'Pandora',          avatar: '/static/spirits/pandora.jpg' },
  cadence:          { name: 'Cadence',          avatar: '/static/spirits/cadence.jpg' },
  echo:             { name: 'Echo',             avatar: '/static/spirits/echo.jpg' },
  echidna:          { name: 'Echidna',          avatar: '/static/spirits/echidna.jpg' },
  roland:           { name: 'Roland',           avatar: '/static/spirits/roland.jpg' },
  glados:           { name: 'GLaDOS',           avatar: '/static/spirits/glados.jpg' },
  high_evolutionary:{ name: 'High Evolutionary',avatar: '/static/spirits/high_evolutionary.jpg' },
  rika:             { name: 'Rika',             avatar: '/static/spirits/rika.jpg' },
  vivy:             { name: 'Vivy',             avatar: '/static/spirits/vivy.jpg' },
};

// Mode display metadata
const MODE_REGISTRY = {
  audience:    { label: 'THE AUDIENCE',    css: 'vc-mode-badge--audience' },
  round_table: { label: 'ROUND TABLE',     css: 'vc-mode-badge--round_table' },
  council:     { label: 'THE COUNCIL',     css: 'vc-mode-badge--council' },
  hearth:      { label: 'THE HEARTH',      css: 'vc-mode-badge--hearth' },
};

// ──────────────────────────────────────────────
// Board Room State
// ──────────────────────────────────────────────
let _currentMode      = null;
let _councilRound     = 0;
let _councilMaxRounds = 10;
let _councilExtended  = false;
let _hearthActive     = false;

// ──────────────────────────────────────────────
// Avatar helpers
// ──────────────────────────────────────────────

/**
 * Build a spirit avatar — <img> when the file loads, colored
 * initials circle as fallback when the image is missing or errors.
 */
function buildSpiritAvatar(spiritKey) {
  const data = SPIRIT_REGISTRY[spiritKey];
  const displayName = data ? data.name : spiritKey;

  // "High Evolutionary" → "HE", "Sonmi-451" → "S4", "Ryuzu" → "R"
  const initials = displayName
    .split(/[\s\-_]+/)
    .map(w => w[0])
    .filter(Boolean)
    .join('')
    .slice(0, 2)
    .toUpperCase();

  if (data && data.avatar) {
    const img = document.createElement('img');
    img.className = 'vc-spirit-avatar';
    img.dataset.spirit = spiritKey;
    img.alt = displayName;
    img.src = data.avatar;
    img.onerror = () => { img.replaceWith(_buildAvatarFallback(spiritKey, initials)); };
    return img;
  }
  return _buildAvatarFallback(spiritKey, initials);
}

function _buildAvatarFallback(spiritKey, initials) {
  const fb = document.createElement('div');
  fb.className = 'vc-spirit-avatar vc-spirit-avatar--fallback';
  fb.dataset.spirit = spiritKey;
  fb.setAttribute('aria-label', initials);
  fb.textContent = initials;
  return fb;
}

/**
 * Build the spirit name label element.
 */
function buildSpiritNameLabel(spiritKey, displayName) {
  const span = document.createElement('span');
  span.className = 'vc-spirit-name';
  span.dataset.spirit = spiritKey;
  span.textContent = displayName || (SPIRIT_REGISTRY[spiritKey]?.name ?? spiritKey);
  return span;
}

// ──────────────────────────────────────────────
// Chat Bubble Decoration
// ──────────────────────────────────────────────

/**
 * Inject spirit identity (avatar + color border) into an existing
 * chat bubble element. Called whenever a new assistant bubble is rendered.
 *
 * @param {HTMLElement} bubbleEl  - The .chat-bubble or equivalent element
 * @param {string}      spiritKey - Pantheon folder name
 * @param {string}      mode      - Board Room mode string
 * @param {string|null} passedTo  - Spirit tagged in via pass_turn, or null
 */
function decorateSpiritBubble(bubbleEl, spiritKey, mode, passedTo = null) {
  if (!bubbleEl || !spiritKey) return;

  // Tag the bubble for CSS targeting
  bubbleEl.dataset.spirit = spiritKey;
  bubbleEl.classList.add('vc-spirit-enter');

  // Inject avatar into the role/header row if present
  const roleEl = bubbleEl.querySelector('.role, [data-role]');
  if (roleEl && !roleEl.querySelector('.vc-spirit-avatar')) {
    const avatar = buildSpiritAvatar(spiritKey);
    roleEl.insertBefore(avatar, roleEl.firstChild);
  }

  // Apply spirit color to the existing role text element
  const roleText = bubbleEl.querySelector('r, .role-text, [data-role-text]');
  if (roleText) {
    roleText.dataset.spirit = spiritKey;
    roleText.classList.add('vc-spirit-name');
  }

  // Pass-turn indicator
  if (passedTo) {
    const passData = SPIRIT_REGISTRY[passedTo];
    const indicator = document.createElement('div');
    indicator.className = 'vc-pass-turn-indicator';
    indicator.textContent = `Passing to ${passData?.name ?? passedTo}`;
    const body = bubbleEl.querySelector('.body');
    if (body) body.appendChild(indicator);
  }
}

// ──────────────────────────────────────────────
// Mode Badge
// ──────────────────────────────────────────────

/**
 * Inject or update the Board Room mode badge in the chat header.
 * @param {string} mode - One of: audience | round_table | council | hearth
 */
function setModeBadge(mode) {
  _currentMode = mode;
  const modeData = MODE_REGISTRY[mode];
  if (!modeData) return;

  let badge = document.getElementById('vc-mode-badge');
  if (!badge) {
    badge = document.createElement('span');
    badge.id = 'vc-mode-badge';
    badge.className = 'vc-mode-badge';
    // Try to inject near the chat header title
    const header = document.querySelector('.chat-top-bar, .chat-header, #chat-header, .chat-title');
    if (header) header.appendChild(badge);
    else document.body.appendChild(badge); // fallback
  }

  // Remove all mode classes then apply the active one
  Object.values(MODE_REGISTRY).forEach(m => badge.classList.remove(m.css));
  badge.classList.add(modeData.css);
  badge.textContent = modeData.label;
}

/**
 * Clear the mode badge (when returning to a standard chat).
 */
function clearModeBadge() {
  const badge = document.getElementById('vc-mode-badge');
  if (badge) badge.remove();
  _currentMode = null;
}

// ──────────────────────────────────────────────
// Council Progress Bar
// ──────────────────────────────────────────────

/**
 * Show/update the Council progress bar.
 * @param {number} round    - Current round number (1-indexed)
 * @param {number} maxRounds - Total rounds allowed in this session
 * @param {boolean} extended - Whether an extension was just granted
 */
function updateCouncilProgress(round, maxRounds, extended = false) {
  _councilRound     = round;
  _councilMaxRounds = maxRounds;
  _councilExtended  = extended;

  let bar = document.getElementById('vc-council-progress');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'vc-council-progress';
    bar.className = 'vc-council-progress';
    bar.innerHTML = `
      <span class="vc-council-progress__label">COUNCIL</span>
      <div class="vc-council-progress__track">
        <div class="vc-council-progress__fill" id="vc-council-fill"></div>
      </div>
      <span class="vc-council-progress__text" id="vc-council-text"></span>
    `;
    const chatArea = document.querySelector('.chat-history, #chat-history, .chat-area, #chat, .messages-container');
    if (chatArea) chatArea.insertBefore(bar, chatArea.firstChild);
  }

  const pct = Math.min((round / maxRounds) * 100, 100);
  const fill = document.getElementById('vc-council-fill');
  const text = document.getElementById('vc-council-text');

  if (fill) fill.style.width = `${pct}%`;
  if (text) text.textContent = `Round ${round} / ${maxRounds}`;

  if (extended) {
    bar.classList.add('vc-council-progress--extended');
    setTimeout(() => bar.classList.remove('vc-council-progress--extended'), 2000);
  }
}

/**
 * Remove the Council progress bar.
 */
function clearCouncilProgress() {
  const bar = document.getElementById('vc-council-progress');
  if (bar) bar.remove();
}

// ──────────────────────────────────────────────
// Hearth Pulse Indicator
// ──────────────────────────────────────────────

/**
 * Show the "Hearth is thinking" pulse indicator.
 */
function showHearthPulse() {
  _hearthActive = true;
  let indicator = document.getElementById('vc-hearth-indicator');
  if (!indicator) {
    indicator = document.createElement('div');
    indicator.id = 'vc-hearth-indicator';
    indicator.className = 'vc-hearth-indicator';
    indicator.innerHTML = `
      <div class="vc-hearth-indicator__dots">
        <div class="vc-hearth-indicator__dot"></div>
        <div class="vc-hearth-indicator__dot"></div>
        <div class="vc-hearth-indicator__dot"></div>
      </div>
      <span>The Hearth stirs…</span>
    `;
    const footer = document.querySelector('.chat-input-bar, .chat-footer, #chat-footer, .input-area');
    if (footer) footer.insertBefore(indicator, footer.firstChild);
  }
  requestAnimationFrame(() => indicator.classList.add('vc-hearth-indicator--active'));
}

/**
 * Hide the Hearth pulse indicator.
 */
function hideHearthPulse() {
  _hearthActive = false;
  const indicator = document.getElementById('vc-hearth-indicator');
  if (indicator) {
    indicator.classList.remove('vc-hearth-indicator--active');
    setTimeout(() => indicator.remove(), 400);
  }
}

// ──────────────────────────────────────────────
// Council Resolution Panel
// ──────────────────────────────────────────────

/**
 * Render the Council resolution panel when the Chair proposes consensus.
 *
 * @param {string}      summary         - The unified proposal text
 * @param {string|null} dissentingViews - Minority positions
 * @param {Function}    onApprove       - Callback for "Approve" button
 * @param {Function}    onReject        - Callback for "Reject" button
 */
function renderResolutionPanel(summary, dissentingViews, onApprove, onReject) {
  // Remove any existing panel
  const existing = document.getElementById('vc-resolution-panel');
  if (existing) existing.remove();

  const panel = document.createElement('div');
  panel.id = 'vc-resolution-panel';
  panel.className = 'vc-resolution-panel vc-spirit-enter';

  const dissentHTML = dissentingViews
    ? `<div class="vc-resolution-panel__dissent">Minority views: ${dissentingViews}</div>`
    : '';

  panel.innerHTML = `
    <div class="vc-resolution-panel__header">Council Resolution</div>
    <div class="vc-resolution-panel__summary">${summary}</div>
    ${dissentHTML}
    <div class="vc-resolution-panel__actions">
      <button class="vc-resolution-panel__btn vc-resolution-panel__btn--approve" id="vc-res-approve">
        Approve Plan
      </button>
      <button class="vc-resolution-panel__btn vc-resolution-panel__btn--reject" id="vc-res-reject">
        Send Back
      </button>
    </div>
  `;

  const chatArea = document.querySelector('.chat-history, #chat-history, .chat-area, #chat, .messages-container');
  if (chatArea) chatArea.appendChild(panel);
  panel.scrollIntoView({ behavior: 'smooth', block: 'center' });

  document.getElementById('vc-res-approve')?.addEventListener('click', () => {
    panel.remove();
    clearCouncilProgress();
    clearModeBadge();
    if (typeof onApprove === 'function') onApprove(summary);
  });

  document.getElementById('vc-res-reject')?.addEventListener('click', () => {
    panel.remove();
    if (typeof onReject === 'function') onReject(summary);
  });
}

// ──────────────────────────────────────────────
// Step-In Button (Council mode)
// ──────────────────────────────────────────────

/**
 * Show the "Step In" button during autonomous Council deliberation.
 * @param {Function} onStepIn - Called when the user clicks the button
 */
function showStepInButton(onStepIn) {
  if (document.getElementById('vc-stepin-btn')) return;

  const btn = document.createElement('button');
  btn.id = 'vc-stepin-btn';
  btn.className = 'vc-stepin-btn';
  btn.textContent = '⚡ Step In';
  btn.title = 'Interject into the Council deliberation';

  btn.addEventListener('click', () => {
    if (typeof onStepIn === 'function') onStepIn();
  });

  const footer = document.querySelector('.chat-input-bar, .chat-footer, #chat-footer, .input-area');
  if (footer) footer.insertBefore(btn, footer.firstChild);
}

/**
 * Remove the Step-In button.
 */
function hideStepInButton() {
  document.getElementById('vc-stepin-btn')?.remove();
}

// ──────────────────────────────────────────────
// CSS Injection (self-bootstrapping)
// ──────────────────────────────────────────────

function injectBoardroomCSS() {
  if (document.getElementById('vc-boardroom-styles')) return;
  const link = document.createElement('link');
  link.id = 'vc-boardroom-styles';
  link.rel = 'stylesheet';
  link.href = '/static/voidcat-boardroom.css';
  document.head.appendChild(link);
}

// ──────────────────────────────────────────────
// Public API
// ──────────────────────────────────────────────

const VoidCatBoardroom = {
  init: injectBoardroomCSS,
  decorateSpiritBubble,
  setModeBadge,
  clearModeBadge,
  updateCouncilProgress,
  clearCouncilProgress,
  showHearthPulse,
  hideHearthPulse,
  renderResolutionPanel,
  showStepInButton,
  hideStepInButton,
  buildSpiritAvatar,
  buildSpiritNameLabel,
  SPIRIT_REGISTRY,
  MODE_REGISTRY,
};

// Auto-init CSS on load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', injectBoardroomCSS);
} else {
  injectBoardroomCSS();
}

// Expose globally for integration with chat.js / chatRenderer.js
window.VoidCatBoardroom = VoidCatBoardroom;

export default VoidCatBoardroom;
