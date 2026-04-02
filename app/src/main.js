/**
 * ◑ MiMi Nox – Frontend Application
 * app/src/main.js
 *
 * NoxApp: alle Interaktionen, API-Calls, Streaming, UI-State.
 * Kein Framework. Pures JavaScript.
 *
 * API Base: http://127.0.0.1:8765/api
 */

const API  = 'http://127.0.0.1:8765/api';
const STORE_KEY_HISTORY = 'mimi_nox_history';
const STORE_KEY_MODEL   = 'mimi_nox_model';

/* ── ◑ NoxApp ────────────────────────────────────────────── */
class NoxApp {
  constructor() {
    this.model         = localStorage.getItem(STORE_KEY_MODEL) || 'phi4-mini';
    this.history       = [];   // aktuelle Session-Messages [{role,content}]
    this.cmdHistory    = [];   // Tastatur-Verlauf ↑ Taste
    this.cmdIndex      = -1;
    this.isStreaming   = false;
    this.activityLog   = [];
    this.currentMsgId  = 0;
    this.panelCollapsed = false;
  }

  // ── Initialisierung ─────────────────────────────────────
  init() {
    this._queryElements();
    this._bindEvents();
    this._restoreModel();
    this.checkHealth();
    this.loadSkillChips();
    this.loadMemoryPanel();
    setInterval(() => this.checkHealth(), 30_000); // alle 30s prüfen
  }

  _queryElements() {
    this.el = {
      chatInput:    document.getElementById('chat-input'),
      sendBtn:      document.getElementById('send-btn'),
      messages:     document.getElementById('messages'),
      welcome:      document.getElementById('welcome-screen'),
      statusDot:    document.getElementById('status-dot'),
      statusText:   document.getElementById('status-text'),
      offlineBanner:document.getElementById('offline-banner'),
      offlineRetry: document.getElementById('offline-retry'),
      modelSelect:  document.getElementById('model-select'),
      apToggle:     document.getElementById('ap-toggle'),
      activityPanel:document.getElementById('activity-panel'),
      apTerminal:   document.getElementById('ap-terminal'),
      memoryCards:  document.getElementById('memory-cards'),
      skillChips:   document.getElementById('skill-chips'),
      // Tabs
      tabBtns:      document.querySelectorAll('.tab'),
      tabViews:     document.querySelectorAll('.tab-content'),
      viewHistory:  document.getElementById('view-history'),
      viewMemory:   document.getElementById('view-memory'),
      viewProfile:  document.getElementById('view-profile'),
      // Profile form
      profileForm:  document.getElementById('profile-form'),
      pfName:       document.getElementById('pf-name'),
      pfExpertise:  document.getElementById('pf-expertise'),
      pfLanguage:   document.getElementById('pf-language'),
      pfStyle:      document.getElementById('pf-style'),
      saveConfirm:  document.getElementById('save-confirm'),
      // Memory tab
      memSearchInput: document.getElementById('memory-search-input'),
      memSearchBtn:   document.getElementById('memory-search-btn'),
      memFullList:    document.getElementById('memory-full-list'),
      // History tab
      historyList:  document.getElementById('history-list'),
      clearHistory: document.getElementById('clear-history'),
    };
  }

  _bindEvents() {
    // Send
    this.el.sendBtn.addEventListener('click', () => this.submitMessage());

    // Textarea: Enter senden, Shift+Enter Zeilenumbruch, ↑ letzter Befehl, Esc abbruch
    this.el.chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.submitMessage();
      } else if (e.key === 'Escape') {
        this.el.chatInput.value = '';
        this._autoResize();
      } else if (e.key === 'ArrowUp' && this.el.chatInput.value === '') {
        e.preventDefault();
        this._navigateHistory(-1);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        this._navigateHistory(1);
      }
    });

    // Auto-resize textarea
    this.el.chatInput.addEventListener('input', () => this._autoResize());

    // Model select
    this.el.modelSelect.addEventListener('change', (e) => {
      this.model = e.target.value;
      localStorage.setItem(STORE_KEY_MODEL, this.model);
      this._addActivity('info', `Modell gewechselt: ${this.model}`);
    });

    // Activity panel toggle (◀)
    this.el.apToggle.addEventListener('click', () => this.toggleActivityPanel());

    // Skill Chips → Input befüllen
    this.el.skillChips.addEventListener('click', (e) => {
      const chip = e.target.closest('.skill-chip');
      if (!chip) return;
      const trigger = chip.dataset.trigger;
      this.el.chatInput.value = trigger + ' ';
      this.el.chatInput.focus();
      this._highlightChip(chip);
    });

    // Willkommens-Karten
    document.getElementById('chat-area').addEventListener('click', (e) => {
      const card = e.target.closest('.welcome-card');
      if (!card) return;
      this.el.chatInput.value = card.dataset.prompt;
      this.submitMessage();
    });

    // Tabs
    this.el.tabBtns.forEach(btn => {
      btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
    });

    // Offline Retry
    this.el.offlineRetry.addEventListener('click', () => this.checkHealth());

    // Profil-Formular
    this.el.profileForm.addEventListener('submit', (e) => {
      e.preventDefault();
      this.saveProfile();
    });

    // Memory Suche (Tab)
    this.el.memSearchBtn.addEventListener('click', () => this.searchMemoryFull());
    this.el.memSearchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.searchMemoryFull();
    });

    // Verlauf löschen
    this.el.clearHistory.addEventListener('click', () => {
      if (confirm('Verlauf wirklich löschen?')) {
        localStorage.removeItem(STORE_KEY_HISTORY);
        this._renderHistoryList();
      }
    });
  }

  _restoreModel() {
    this.el.modelSelect.value = this.model;
  }

  _autoResize() {
    const ta = this.el.chatInput;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  }

  // ── Health Check ────────────────────────────────────────
  async checkHealth() {
    try {
      const res = await fetch(`${API}/health`, { signal: AbortSignal.timeout(5000) });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();

      if (data.ollama) {
        this._setStatus('connected');
        this.el.offlineBanner.classList.add('hidden');
      } else {
        this._setStatus('offline');
        this.el.offlineBanner.classList.remove('hidden');
      }

      // Modell-Optionen aktualisieren wenn Modelle verfügbar
      if (data.models && data.models.length > 0) {
        this._updateModelOptions(data.models);
      }
    } catch {
      this._setStatus('offline');
      this.el.offlineBanner.classList.remove('hidden');
    }
  }

  _setStatus(state) {
    const dot  = this.el.statusDot;
    const text = this.el.statusText;
    if (state === 'connected') {
      dot.className  = 'status-dot';
      text.className = 'status-text';
      text.textContent = 'Verbunden';
    } else {
      dot.className  = 'status-dot offline';
      text.className = 'status-text offline';
      text.textContent = 'Offline';
    }
  }

  _updateModelOptions(models) {
    const select  = this.el.modelSelect;
    const current = this.model;
    select.innerHTML = '';
    models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m;
      if (m === current) opt.selected = true;
      select.appendChild(opt);
    });
    if (!models.includes(current) && models.length > 0) {
      this.model = models[0];
      select.value = this.model;
    }
  }

  // ── Skills ──────────────────────────────────────────────
  async loadSkillChips() {
    try {
      const res  = await fetch(`${API}/skills`);
      const data = await res.json();
      const chips = this.el.skillChips;
      chips.innerHTML = '';

      const icons = {
        '/research': '🔍',
        '/files':    '📁',
        '/write':    '✏️',
        '/review':   '💻',
        '/shell':    '>_',
      };

      (data.skills || []).forEach(skill => {
        const btn = document.createElement('button');
        btn.className = 'skill-chip';
        btn.dataset.trigger = skill.trigger;
        btn.title = skill.description;
        btn.textContent = (icons[skill.trigger] || '⚡') + ' ' + skill.trigger;
        btn.setAttribute('role', 'listitem');
        chips.appendChild(btn);
      });
    } catch {
      // Behalte die statischen HTML-Chips als Fallback
    }
  }

  _highlightChip(activeChip) {
    this.el.skillChips.querySelectorAll('.skill-chip')
      .forEach(c => c.classList.remove('active'));
    activeChip.classList.add('active');
    setTimeout(() => activeChip.classList.remove('active'), 1500);
  }

  // ── Nachricht senden ────────────────────────────────────
  submitMessage() {
    const text = this.el.chatInput.value.trim();
    if (!text || this.isStreaming) return;

    // Verlauf für ↑ Taste
    this.cmdHistory.unshift(text);
    if (this.cmdHistory.length > 50) this.cmdHistory.pop();
    this.cmdIndex = -1;

    this.el.chatInput.value = '';
    this._autoResize();
    this._hideWelcome();

    this.renderUserBubble(text);
    this._startStreaming(text);
  }

  async _startStreaming(text) {
    this.isStreaming = true;
    this.el.sendBtn.disabled = true;
    this.el.chatInput.disabled = true;

    this.currentMsgId++;
    const msgId = this.currentMsgId;
    const bubble = this.renderAIBubble(msgId);
    let   full   = '';

    // Activity: Anfrage gestartet
    this._addActivity('cmd', `react_loop("${text.slice(0,40)}${text.length>40?'…':''}")`);

    try {
      const res = await fetch(`${API}/chat/stream`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          message: text,
          model:   this.model,
          history: this.history,
        }),
        signal: AbortSignal.timeout(120_000), // 2 Minuten max
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({detail: 'Unbekannter Fehler'}));
        throw new Error(err.detail || 'HTTP ' + res.status);
      }

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let   buffer  = '';

      this._addActivity('progress', 'Antwort generieren…', 0);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // unvollständige Zeile zurückbehalten

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') break;

          try {
            const parsed = JSON.parse(raw);
            if (parsed.chunk !== undefined) {
              full += parsed.chunk;
              this._appendChunk(bubble, parsed.chunk);
            } else if (parsed.error) {
              this._appendChunk(bubble, `\n\n⚠ Fehler: ${parsed.error}`);
            }
          } catch {
            // Ungültige JSON-Zeile überspringen
          }
        }
      }

      // Cursor entfernen, Aktionen anzeigen
      bubble.classList.remove('streaming-cursor');
      this._showBubbleActions(msgId, text, full);
      this._addActivity('done', `✓ Fertig`);

      // Memory nach Antwort kurz aktualisieren
      setTimeout(() => this.loadMemoryPanel(), 1000);

    } catch (err) {
      bubble.classList.remove('streaming-cursor');
      if (!full) {
        bubble.textContent = `⚠ ${err.message}`;
      }
      this._addActivity('error', `Fehler: ${err.message}`);
      this._setStatus('offline');
    } finally {
      // Session-History aktualisieren
      this.history.push({ role: 'user',      content: text });
      this.history.push({ role: 'assistant', content: full });

      // In Verlauf speichern (localStorage)
      this._saveToHistory(text, full);

      this.isStreaming = false;
      this.el.sendBtn.disabled = false;
      this.el.chatInput.disabled = false;
      this.el.chatInput.focus();
      this._scrollToBottom();
    }
  }

  // ── Render Funktionen ───────────────────────────────────
  _hideWelcome() {
    if (this.el.welcome) {
      this.el.welcome.style.display = 'none';
    }
  }

  renderUserBubble(text) {
    const el = document.createElement('div');
    el.className = 'bubble-user';
    el.textContent = text;
    this.el.messages.appendChild(el);
    this._scrollToBottom();
    return el;
  }

  renderAIBubble(id) {
    const wrap = document.createElement('div');
    wrap.className = 'bubble-ai-wrap';
    wrap.dataset.msgId = id;

    const bubble = document.createElement('div');
    bubble.className = 'bubble-ai streaming-cursor';
    bubble.id = `msg-${id}`;

    wrap.appendChild(bubble);
    this.el.messages.appendChild(wrap);
    this._scrollToBottom();
    return bubble;
  }

  _appendChunk(bubble, chunk) {
    bubble.textContent += chunk;
    this._scrollToBottom();
  }

  _showBubbleActions(id, prompt, response) {
    const wrap = document.querySelector(`.bubble-ai-wrap[data-msg-id="${id}"]`);
    if (!wrap) return;

    const actions = document.createElement('div');
    actions.className = 'bubble-actions';
    actions.innerHTML = `
      <button class="bubble-action-btn" id="copy-${id}" aria-label="Antwort kopieren">📋 Kopieren</button>
      <span class="action-sep">·</span>
      <button class="bubble-action-btn" id="up-${id}"   aria-label="Hilfreiche Antwort">👍</button>
      <span class="action-sep">·</span>
      <button class="bubble-action-btn" id="down-${id}" aria-label="Nicht hilfreiche Antwort">👎</button>
      <span class="action-sep">·</span>
      <button class="bubble-action-btn" id="deep-${id}" aria-label="Vertiefen">↩ Vertiefen</button>
    `;

    wrap.appendChild(actions);

    document.getElementById(`copy-${id}`)
      .addEventListener('click', () => this.handleCopy(response, `copy-${id}`));
    document.getElementById(`up-${id}`)
      .addEventListener('click', () => this.handleFeedback('thumbs_up', prompt, response, `up-${id}`));
    document.getElementById(`down-${id}`)
      .addEventListener('click', () => this.handleFeedback('thumbs_down', prompt, response, `down-${id}`));
    document.getElementById(`deep-${id}`)
      .addEventListener('click', () => {
        this.el.chatInput.value = 'Erkläre das genauer: ';
        this.el.chatInput.focus();
      });
  }

  _scrollToBottom() {
    const area = document.getElementById('chat-area');
    area.scrollTop = area.scrollHeight;
  }

  // ── Feedback ────────────────────────────────────────────
  async handleFeedback(type, prompt, response, btnId) {
    try {
      await fetch(`${API}/feedback/${type}`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ prompt, response }),
      });
      const btn = document.getElementById(btnId);
      if (btn) {
        btn.style.color = 'var(--green)';
        btn.textContent = type === 'thumbs_up' ? '👍 ✓' : '👎 ✓';
        btn.disabled = true;
      }
    } catch {
      // Still show some feedback to user
    }
  }

  // ── Copy ────────────────────────────────────────────────
  async handleCopy(text, btnId) {
    try {
      await navigator.clipboard.writeText(text);
      const btn = document.getElementById(btnId);
      if (btn) {
        const orig = btn.textContent;
        btn.textContent = '✅ Kopiert!';
        setTimeout(() => { btn.textContent = orig; }, 2000);
      }
    } catch {
      // Fallback: select the text
    }
  }

  // ── Aktivitäts-Panel Terminal ────────────────────────────
  _addActivity(type, text, progress) {
    const terminal = this.el.apTerminal;

    // Placeholder entfernen
    const placeholder = terminal.querySelector('.terminal-placeholder');
    if (placeholder) placeholder.remove();

    const line = document.createElement('div');
    line.className = 'terminal-line';

    if (type === 'cmd') {
      line.innerHTML = `<span class="terminal-cmd">&gt; <span class="t-keyword">${this._escHtml(text)}</span></span>`;
    } else if (type === 'progress') {
      line.innerHTML = `
        <span class="terminal-status">${this._escHtml(text)}</span>
        <div class="terminal-progress"><div class="terminal-progress-bar" style="width:0%"></div></div>`;
      // Animiere die Leiste
      setTimeout(() => {
        const bar = line.querySelector('.terminal-progress-bar');
        if (bar) {
          let pct = 0;
          const timer = setInterval(() => {
            pct = Math.min(pct + Math.random() * 15, 90);
            bar.style.width = pct + '%';
            if (pct >= 90) clearInterval(timer);
          }, 300);
        }
      }, 50);
    } else if (type === 'done') {
      // Leiste auf 100%
      const lastBar = terminal.querySelector('.terminal-progress-bar');
      if (lastBar) lastBar.style.width = '100%';
      line.innerHTML = `<span class="terminal-status done">${this._escHtml(text)}</span>`;
    } else if (type === 'error') {
      line.innerHTML = `<span class="terminal-status" style="color:#ef4444">${this._escHtml(text)}</span>`;
    } else {
      line.innerHTML = `<span class="terminal-status">${this._escHtml(text)}</span>`;
    }

    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;

    // Max 20 Einträge
    while (terminal.children.length > 20) {
      terminal.removeChild(terminal.firstChild);
    }
  }

  toggleActivityPanel() {
    this.panelCollapsed = !this.panelCollapsed;
    this.el.activityPanel.classList.toggle('collapsed', this.panelCollapsed);
  }

  // ── Memory Panel ─────────────────────────────────────────
  async loadMemoryPanel() {
    try {
      const res  = await fetch(`${API}/memory/search?q=&top_k=5`);
      const data = await res.json();
      const cards = this.el.memoryCards;

      if (!data.results || data.results.length === 0) {
        cards.innerHTML = '<div class="memory-placeholder">Noch nichts gespeichert.</div>';
        return;
      }

      cards.innerHTML = '';
      data.results.forEach(r => {
        const card = document.createElement('div');
        card.className = 'memory-card';
        card.textContent = r.text.slice(0, 120) + (r.text.length > 120 ? '…' : '');
        cards.appendChild(card);
      });
    } catch {
      // Ignorieren wenn Memory nicht erreichbar
    }
  }

  // ── Tab Navigation ──────────────────────────────────────
  switchTab(tabName) {
    this.el.tabBtns.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabName);
      btn.setAttribute('aria-selected', btn.dataset.tab === tabName);
    });

    this.el.tabViews.forEach(view => {
      const isActive = view.id === `view-${tabName}`;
      view.classList.toggle('active', isActive);
      view.hidden = !isActive;
    });

    // Tab-spezifische Aktion
    if (tabName === 'history')  this._renderHistoryList();
    if (tabName === 'memory')   this.searchMemoryFull();
    if (tabName === 'profile')  this.loadProfile();
  }

  // ── Verlauf (localStorage) ──────────────────────────────
  _saveToHistory(prompt, response) {
    const all = JSON.parse(localStorage.getItem(STORE_KEY_HISTORY) || '[]');
    all.unshift({
      id:       Date.now(),
      date:     new Date().toLocaleDateString('de-DE', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit' }),
      title:    prompt.slice(0, 80),
      response: response.slice(0, 200),
    });
    if (all.length > 100) all.splice(100);
    localStorage.setItem(STORE_KEY_HISTORY, JSON.stringify(all));
  }

  _renderHistoryList() {
    const all  = JSON.parse(localStorage.getItem(STORE_KEY_HISTORY) || '[]');
    const list = this.el.historyList;
    list.innerHTML = '';

    if (all.length === 0) {
      list.innerHTML = '<div class="history-empty">Noch keine Unterhaltungen gespeichert.</div>';
      return;
    }

    all.forEach(item => {
      const div = document.createElement('div');
      div.className = 'history-item';
      div.innerHTML = `
        <div class="history-title">${this._escHtml(item.title)}</div>
        <div class="history-date">${item.date}</div>
      `;
      div.addEventListener('click', () => {
        this.switchTab('chat');
        this.el.chatInput.value = item.title;
        this.el.chatInput.focus();
      });
      list.appendChild(div);
    });
  }

  // ── Memory Tab Suche ────────────────────────────────────
  async searchMemoryFull() {
    const q = this.el.memSearchInput.value.trim();
    try {
      const res  = await fetch(`${API}/memory/search?q=${encodeURIComponent(q)}&top_k=20`);
      const data = await res.json();
      const list = this.el.memFullList;
      list.innerHTML = '';

      if (!data.results || data.results.length === 0) {
        list.innerHTML = '<div class="history-empty">Keine Einträge gefunden.</div>';
        return;
      }

      data.results.forEach(r => {
        const card = document.createElement('div');
        card.className = 'memory-full-card';
        card.textContent = r.text;
        list.appendChild(card);
      });
    } catch {
      this.el.memFullList.innerHTML = '<div class="history-empty">Memory nicht erreichbar.</div>';
    }
  }

  // ── Profil ──────────────────────────────────────────────
  async loadProfile() {
    try {
      const res  = await fetch(`${API}/profile`);
      const data = await res.json();
      if (data.name)               this.el.pfName.value       = data.name;
      if (data.expertise)          this.el.pfExpertise.value   = data.expertise;
      if (data.preferred_language) this.el.pfLanguage.value    = data.preferred_language;
      if (data.response_style)     this.el.pfStyle.value       = data.response_style;
    } catch {
      // Formular bleibt leer wenn API nicht erreichbar
    }
  }

  async saveProfile() {
    const payload = {
      name:               this.el.pfName.value.trim()     || null,
      expertise:          this.el.pfExpertise.value.trim() || null,
      preferred_language: this.el.pfLanguage.value,
      response_style:     this.el.pfStyle.value,
    };
    try {
      const res = await fetch(`${API}/profile`, {
        method:  'PUT',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });
      if (res.ok) {
        this.el.saveConfirm.classList.remove('hidden');
        setTimeout(() => this.el.saveConfirm.classList.add('hidden'), 3000);
      }
    } catch {
      alert('Profil konnte nicht gespeichert werden. Ist der Server erreichbar?');
    }
  }

  // ── Tastatur Verlauf (↑/↓) ──────────────────────────────
  _navigateHistory(direction) {
    this.cmdIndex = Math.max(-1, Math.min(this.cmdIndex + direction, this.cmdHistory.length - 1));
    this.el.chatInput.value = this.cmdIndex >= 0 ? this.cmdHistory[this.cmdIndex] : '';
    this._autoResize();
  }

  // ── Hilfsfunktionen ─────────────────────────────────────
  _escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
}

// ── Start ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const app = new NoxApp();
  app.init();
  window._nox = app; // Debug-Zugriff in DevTools
});
