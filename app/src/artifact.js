/**
 * ◑ MiMi Nox — Artifact Panel
 * 
 * Claude-inspiriertes Artifact-System:
 * - Code/HTML-Blöcke erscheinen nicht im Chat, sondern in einem Seitenpanel
 * - ArtifactStore verwaltet alle erzeugten Artifacts mit Versionierung
 * - ArtifactPanel steuert die animierte Seitenleiste
 * 
 * Events die aus chat.py kommen:
 *   {type: "replace_text", text: "..."}  → Bubble-Text durch bereinigten Text ersetzen
 *   {type: "artifact", artifact: {...}}  → Artifact anzeigen + Panel öffnen
 */

// ── Sprachkonfiguration für Highlight.js ─────────────────────────────────────
const LANG_DISPLAY = {
  code_python:     { label: 'Python',     icon: '🐍' },
  code_bash:       { label: 'Shell',      icon: '⚡' },
  code_js:         { label: 'JavaScript', icon: '🟨' },
  code_typescript: { label: 'TypeScript', icon: '🔷' },
  code_rust:       { label: 'Rust',       icon: '🦀' },
  code_go:         { label: 'Go',         icon: '🐹' },
  code_sql:        { label: 'SQL',        icon: '🗄️' },
  code_other:      { label: 'Code',       icon: '📄' },
  html:            { label: 'HTML',       icon: '🌐' },
  svg:             { label: 'SVG',        icon: '🎨' },
  json:            { label: 'JSON',       icon: '{ }' },
  yaml:            { label: 'YAML',       icon: '⚙️' },
  diff:            { label: 'Diff',       icon: '±' },
  markdown:        { label: 'Markdown',   icon: '📝' },
};


// ═══════════════════════════════════════════════════════════════════════════════
// ArtifactStore — Versionierter In-Memory-Store
// ═══════════════════════════════════════════════════════════════════════════════

export class ArtifactStore {
  constructor() {
    this._artifacts = new Map();  // id → artifact
    this._order     = [];         // Reihenfolge (neueste zuerst)
    this._listeners = [];
  }

  /** Artifact hinzufügen oder aktualisieren (Versioning by update_id). */
  add(artifact) {
    const id = artifact.id;
    const isUpdate = artifact.update_id && this._artifacts.has(artifact.update_id);

    if (isUpdate) {
      // Update: altes Artifact überschreiben
      const oldId = artifact.update_id;
      this._artifacts.delete(oldId);
      this._order = this._order.filter(i => i !== oldId);
    }

    this._artifacts.set(id, { ...artifact, created_at: Date.now() });
    this._order.unshift(id); // neueste vorne

    this._notify('add', artifact);
    return artifact;
  }

  /** Artifact per ID abrufen oder null. */
  get(id) {
    return this._artifacts.get(id) ?? null;
  }

  /** Alle Artifacts in Reihenfolge (neueste zuerst). */
  all() {
    return this._order.map(id => this._artifacts.get(id));
  }

  /** Anzahl der gespeicherten Artifacts. */
  get size() {
    return this._artifacts.size;
  }

  /** Listener registrieren: fn(event, artifact) */
  subscribe(fn) {
    this._listeners.push(fn);
    return () => { this._listeners = this._listeners.filter(l => l !== fn); };
  }

  _notify(event, data) {
    this._listeners.forEach(fn => fn(event, data));
  }
}


// ═══════════════════════════════════════════════════════════════════════════════
// ArtifactPanel — Sliding Side Panel Controller
// ═══════════════════════════════════════════════════════════════════════════════

export class ArtifactPanel {
  constructor(store) {
    this.store        = store;
    this.activeId     = null;
    this.viewMode     = 'code'; // 'code' | 'preview'
    this._hlReady     = false;
    this._panel       = null;
    this._rendered    = false;

    this._init();
  }

  // ── Setup ──────────────────────────────────────────────────────────────────

  _init() {
    this._injectPanel();
    this._injectStyles();
    this._loadHighlightJS();
    this._bindKeys();
  }

  _injectPanel() {
    const panel = document.createElement('div');
    panel.id        = 'artifact-panel';
    panel.className = 'artifact-panel artifact-panel--closed';
    panel.setAttribute('role', 'complementary');
    panel.setAttribute('aria-label', 'Artifact Viewer');
    panel.innerHTML = this._panelTemplate();
    document.body.appendChild(panel);
    this._panel = panel;

    // Bindings
    panel.querySelector('#ap-close').addEventListener('click', () => this.close());
    panel.querySelector('#ap-copy').addEventListener('click',  () => this._copy());
    panel.querySelector('#ap-download').addEventListener('click', () => this._download());
    panel.querySelector('#ap-toggle-view').addEventListener('click', () => this._toggleView());

    // Resize handle (drag to resize)
    this._initResize(panel.querySelector('.artifact-resize-handle'));

    this._rendered = true;
  }

  _panelTemplate() {
    return `
      <div class="artifact-resize-handle" title="Panel-Breite anpassen"></div>
      <div class="artifact-panel__inner">

        <!-- Header -->
        <div class="artifact-header">
          <div class="artifact-header__left">
            <span class="artifact-type-badge" id="ap-type-badge">📄 Code</span>
            <span class="artifact-title" id="ap-title">Artifact</span>
          </div>
          <div class="artifact-header__actions">
            <button id="ap-toggle-view" class="ap-btn" title="Code / Preview wechseln">👁 Preview</button>
            <button id="ap-copy"        class="ap-btn" title="Kopieren">⎘ Copy</button>
            <button id="ap-download"    class="ap-btn" title="Herunterladen">↓</button>
            <button id="ap-close"       class="ap-btn ap-btn--close" title="Panel schließen (Esc)">✕</button>
          </div>
        </div>

        <!-- Filename bar -->
        <div class="artifact-filename" id="ap-filename">script.py</div>

        <!-- Code View -->
        <div class="artifact-code-wrap" id="ap-code-wrap">
          <pre class="artifact-pre" id="ap-pre"><code id="ap-code"></code></pre>
        </div>

        <!-- Preview View (sandboxed iframe for HTML) -->
        <div class="artifact-preview-wrap hidden" id="ap-preview-wrap">
          <iframe id="ap-preview-frame" sandbox="allow-scripts" class="artifact-preview-frame"></iframe>
        </div>

        <!-- Footer: Artifact History Dots -->
        <div class="artifact-footer" id="ap-footer">
          <span class="artifact-footer__label">Artifacts dieser Session:</span>
          <div class="artifact-dots" id="ap-dots"></div>
        </div>
      </div>
    `;
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /** Öffnet das Panel und zeigt ein Artifact an. */
  open(artifact) {
    this.store.add(artifact);
    this.activeId = artifact.id;
    this._render(artifact);
    this._show();
    this._updateDots();
    this._notifyMainLayout(true);
  }

  /** Schließt das Panel. */
  close() {
    this._panel.classList.remove('artifact-panel--open');
    this._panel.classList.add('artifact-panel--closed');
    this.activeId = null;
    this._notifyMainLayout(false);
  }

  /** Wechselt zum Artifact mit der gegebenen ID. */
  switchTo(id) {
    const art = this.store.get(id);
    if (!art) return;
    this.activeId = id;
    this._render(art);
    this._updateDots();
  }

  get isOpen() {
    return this._panel.classList.contains('artifact-panel--open');
  }

  // ── Rendering ──────────────────────────────────────────────────────────────

  _render(artifact) {
    const meta = LANG_DISPLAY[artifact.artifact_type] ?? { label: 'Code', icon: '📄' };

    // Header
    this._panel.querySelector('#ap-type-badge').textContent = `${meta.icon} ${meta.label}`;
    this._panel.querySelector('#ap-title').textContent      = artifact.title || artifact.filename;
    this._panel.querySelector('#ap-filename').textContent   = artifact.filename;

    // Code-View  
    const codeEl = this._panel.querySelector('#ap-code');
    codeEl.textContent = artifact.content;
    codeEl.className   = `language-${artifact.language}`;

    // Syntax Highlighting
    if (this._hlReady && window.hljs) {
      try { window.hljs.highlightElement(codeEl); } catch {}
    }

    // Preview Button: nur bei HTML/SVG anzeigen
    const canPreview = ['html', 'svg'].includes(artifact.artifact_type);
    const previewBtn = this._panel.querySelector('#ap-toggle-view');
    previewBtn.style.display = canPreview ? '' : 'none';

    // Falls schon im Preview-Modus → aktualisieren
    if (this.viewMode === 'preview' && canPreview) {
      this._renderPreview(artifact.content, artifact.artifact_type);
    } else {
      this.viewMode = 'code';
      this._showCodeView();
    }
  }

  _renderPreview(content, type) {
    const frame = this._panel.querySelector('#ap-preview-frame');
    if (type === 'svg') {
      frame.srcdoc = `<html><body style="margin:0;background:#020504;display:flex;align-items:center;justify-content:center;min-height:100vh">${content}</body></html>`;
    } else {
      frame.srcdoc = content;
    }
    this._panel.querySelector('#ap-code-wrap').classList.add('hidden');
    this._panel.querySelector('#ap-preview-wrap').classList.remove('hidden');
  }

  _showCodeView() {
    this._panel.querySelector('#ap-code-wrap').classList.remove('hidden');
    this._panel.querySelector('#ap-preview-wrap').classList.add('hidden');
    this._panel.querySelector('#ap-toggle-view').textContent = '👁 Preview';
  }

  _updateDots() {
    const dotsEl = this._panel.querySelector('#ap-dots');
    const all = this.store.all();
    dotsEl.innerHTML = all.map(a => `
      <button class="artifact-dot ${a.id === this.activeId ? 'artifact-dot--active' : ''}"
              data-id="${a.id}"
              title="${a.title}"
              aria-label="Artifact: ${a.title}">
      </button>
    `).join('');

    dotsEl.querySelectorAll('.artifact-dot').forEach(btn => {
      btn.addEventListener('click', () => this.switchTo(btn.dataset.id));
    });
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  _toggleView() {
    const art = this.store.get(this.activeId);
    if (!art) return;

    if (this.viewMode === 'code') {
      this.viewMode = 'preview';
      this._renderPreview(art.content, art.artifact_type);
      this._panel.querySelector('#ap-toggle-view').textContent = '📄 Code';
    } else {
      this.viewMode = 'code';
      this._showCodeView();
    }
  }

  async _copy() {
    const art = this.store.get(this.activeId);
    if (!art) return;
    try {
      await navigator.clipboard.writeText(art.content);
      this._flashBtn('#ap-copy', '✓ Copied!');
    } catch {
      // Fallback: textarea trick
      const ta = document.createElement('textarea');
      ta.value = art.content;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
      this._flashBtn('#ap-copy', '✓ Copied!');
    }
  }

  _download() {
    const art = this.store.get(this.activeId);
    if (!art) return;
    const blob = new Blob([art.content], { type: 'text/plain;charset=utf-8' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = art.filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  _flashBtn(selector, text) {
    const btn = this._panel.querySelector(selector);
    if (!btn) return;
    const orig = btn.textContent;
    btn.textContent = text;
    btn.style.color = 'var(--green)';
    setTimeout(() => { btn.textContent = orig; btn.style.color = ''; }, 1500);
  }

  // ── Layout ──────────────────────────────────────────────────────────────────

  _show() {
    this._panel.classList.remove('artifact-panel--closed');
    this._panel.classList.add('artifact-panel--open');
  }

  /** Informiert den Chat-Bereich, dass das Panel geöffnet/geschlossen ist */
  _notifyMainLayout(open) {
    const main = document.getElementById('main-area');
    if (main) main.classList.toggle('has-artifact-panel', open);
  }

  // ── Drag-to-Resize ─────────────────────────────────────────────────────────

  _initResize(handle) {
    let startX, startW;
    handle.addEventListener('mousedown', (e) => {
      startX = e.clientX;
      startW = this._panel.offsetWidth;
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', () => {
        document.removeEventListener('mousemove', onMove);
      }, { once: true });
    });

    const onMove = (e) => {
      const delta = startX - e.clientX;
      const newW  = Math.min(800, Math.max(320, startW + delta));
      this._panel.style.setProperty('--artifact-panel-w', newW + 'px');
    };
  }

  // ── Keyboard ───────────────────────────────────────────────────────────────

  _bindKeys() {
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        e.stopPropagation();
        this.close();
      }
    });
  }

  // ── Highlight.js (lazy CDN load) ───────────────────────────────────────────

  _loadHighlightJS() {
    if (window.hljs) { this._hlReady = true; return; }

    const link = document.createElement('link');
    link.rel  = 'stylesheet';
    link.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css';
    document.head.appendChild(link);

    const script = document.createElement('script');
    script.src   = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js';
    script.onload = () => {
      this._hlReady = true;
      // Aktives Artifact nachträglich highlighten
      const codeEl = this._panel?.querySelector('#ap-code');
      if (codeEl && codeEl.textContent) {
        try { window.hljs.highlightElement(codeEl); } catch {}
      }
    };
    document.head.appendChild(script);
  }

  // ── Inline Styles (kein separates CSS-File nötig für Portabilität) ─────────
  _injectStyles() {
    if (document.getElementById('artifact-panel-styles')) return;
    const style = document.createElement('style');
    style.id = 'artifact-panel-styles';
    style.textContent = ARTIFACT_PANEL_CSS;
    document.head.appendChild(style);
  }
}


// ══════════════════════════════════════════════════════════════════════════════
// CSS (injected dynamically to keep artifact.js self-contained)
// ══════════════════════════════════════════════════════════════════════════════

const ARTIFACT_PANEL_CSS = `
/* ── Artifact Panel Variable ─────────────────────────────────── */
:root { --artifact-panel-w: 440px; }

/* ── Main Area mit Panel ─────────────────────────────────────── */
#main-area.has-artifact-panel {
  right: var(--artifact-panel-w);
  transition: right 300ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
#main-area {
  transition: right 300ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

/* ── Panel Container ─────────────────────────────────────────── */
.artifact-panel {
  position: fixed;
  top: 0; right: 0; bottom: 0;
  width: var(--artifact-panel-w);
  background: #040a04;
  border-left: 1px solid rgba(34, 197, 94, 0.12);
  z-index: 200;
  display: flex;
  flex-direction: column;
  transition: transform 320ms cubic-bezier(0.2, 0.8, 0.2, 1),
              opacity  320ms ease;
}
.artifact-panel--closed {
  transform: translateX(100%);
  opacity: 0;
  pointer-events: none;
}
.artifact-panel--open {
  transform: translateX(0);
  opacity: 1;
  pointer-events: all;
}

/* ── Resize Handle ───────────────────────────────────────────── */
.artifact-resize-handle {
  position: absolute;
  left: -4px; top: 0; bottom: 0;
  width: 8px;
  cursor: ew-resize;
  background: transparent;
  transition: background 200ms;
}
.artifact-resize-handle:hover {
  background: rgba(34, 197, 94, 0.2);
}

/* ── Inner ───────────────────────────────────────────────────── */
.artifact-panel__inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* ── Header ──────────────────────────────────────────────────── */
.artifact-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 12px;
  border-bottom: 1px solid rgba(34, 197, 94, 0.08);
  background: rgba(2, 5, 4, 0.6);
  backdrop-filter: blur(16px);
  flex-shrink: 0;
  gap: 12px;
}
.artifact-header__left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  overflow: hidden;
}
.artifact-type-badge {
  font-size: 11px;
  font-weight: 600;
  color: #22c55e;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: 6px;
  padding: 2px 8px;
  white-space: nowrap;
  flex-shrink: 0;
}
.artifact-title {
  font-size: 13px;
  font-weight: 500;
  color: #f0fdf4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.artifact-header__actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

/* ── Buttons ─────────────────────────────────────────────────── */
.ap-btn {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  color: #6b7280;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 11px;
  cursor: pointer;
  transition: all 180ms ease;
  white-space: nowrap;
}
.ap-btn:hover {
  background: rgba(34, 197, 94, 0.1);
  border-color: rgba(34, 197, 94, 0.3);
  color: #22c55e;
}
.ap-btn--close:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  color: #ef4444;
}

/* ── Filename Bar ────────────────────────────────────────────── */
.artifact-filename {
  padding: 6px 16px;
  font-size: 11px;
  color: #374151;
  font-family: 'JetBrains Mono', monospace;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  background: rgba(2, 5, 4, 0.4);
  flex-shrink: 0;
}

/* ── Code View ───────────────────────────────────────────────── */
.artifact-code-wrap {
  flex: 1;
  overflow: auto;
  position: relative;
}
.artifact-pre {
  margin: 0;
  padding: 20px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 12.5px;
  line-height: 1.65;
  tab-size: 2;
  min-height: 100%;
  background: transparent !important;
  color: #d1fae5;
}
.artifact-pre code {
  background: transparent !important;
  font-family: inherit;
  font-size: inherit;
}

/* ── Preview Frame ───────────────────────────────────────────── */
.artifact-preview-wrap {
  flex: 1;
  overflow: hidden;
}
.artifact-preview-frame {
  width: 100%; height: 100%;
  border: none;
  background: #fff;
}

/* ── Footer Dots ─────────────────────────────────────────────── */
.artifact-footer {
  padding: 10px 16px;
  border-top: 1px solid rgba(34, 197, 94, 0.06);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  background: rgba(2, 5, 4, 0.6);
}
.artifact-footer__label {
  font-size: 10px;
  color: #374151;
  white-space: nowrap;
}
.artifact-dots {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.artifact-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.25);
  border: 1px solid rgba(34, 197, 94, 0.2);
  cursor: pointer;
  padding: 0;
  transition: all 200ms;
}
.artifact-dot--active {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.6);
}
.artifact-dot:hover:not(.artifact-dot--active) {
  background: rgba(34, 197, 94, 0.5);
}

/* ── Artifact Link im Chat ───────────────────────────────────── */
.artifact-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(34, 197, 94, 0.06);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: 10px;
  padding: 8px 14px;
  margin: 8px 0;
  cursor: pointer;
  transition: all 200ms ease;
  font-size: 13px;
  color: #4ade80;
  text-decoration: none;
  width: fit-content;
}
.artifact-link:hover {
  background: rgba(34, 197, 94, 0.12);
  border-color: rgba(34, 197, 94, 0.4);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.15);
}
.artifact-link__icon { font-size: 16px; }
.artifact-link__name { font-weight: 600; }
.artifact-link__meta { font-size: 11px; color: #6b7280; }

/* ── Scroll in Code ──────────────────────────────────────────── */
.artifact-code-wrap::-webkit-scrollbar { width: 4px; height: 4px; }
.artifact-code-wrap::-webkit-scrollbar-thumb { background: rgba(34,197,94,0.2); border-radius: 4px; }

/* ── Responsive: auf schmalem Screen Panel als Full-Overlay ──── */
@media (max-width: 900px) {
  .artifact-panel {
    width: 100% !important;
    border-left: none;
  }
  #main-area.has-artifact-panel {
    right: 0;
  }
}

/* ── Hidden Utility ──────────────────────────────────────────── */
.hidden { display: none !important; }
`;
