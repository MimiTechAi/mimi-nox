/**
 * ◑ MiMi Nox – i18n Module
 *
 * Lightweight internationalization.
 * - Auto-detects browser language (de/en)
 * - Translates data-i18n attributes + JS strings
 * - Falls back to English if locale is not German
 *
 * Usage (HTML):   <span data-i18n="welcome.heading">Fallback</span>
 * Usage (JS):     import { t, currentLang } from './i18n.js';
 *                 element.textContent = t('welcome.heading');
 */

const translations = {
  de: {
    // ── Meta ──
    'meta.description': '◑ MiMi Nox – Lokale KI. Privat. Lokal. Deins.',
    'meta.tagline': 'Privat · Lokal · Deins.',

    // ── Topbar ──
    'nav.newChat': '📝 Neuer Chat',
    'nav.chat': '💬 Chat',
    'nav.skills': '⚡ Skills',
    'nav.history': '📚 Verlauf',
    'nav.memory': '🧠 Memory',
    'nav.profile': '👤 Profil',
    'nav.mobilePairing': '📱 Smartphone verbinden',
    'nav.autonom': '🤖 Autonom',
    'status.connecting': 'Verbinden…',
    'status.connected': 'Verbunden',
    'status.offline': 'Offline',

    // ── Offline Banner ──
    'offline.message': '⚠ Ollama nicht erreichbar — starte Ollama mit:',
    'offline.retry': '↻ Erneut versuchen',

    // ── Welcome Screen ──
    'welcome.heading': 'Womit kann ich helfen?',
    'welcome.sub': 'Tippe eine Frage oder wähle einen Skill',
    'welcome.searchNews': 'Aktuelle News suchen',
    'welcome.analyzeFile': 'Datei analysieren',
    'welcome.writeText': 'Text schreiben',

    // ── Activity Panel ──
    'activity.title': '⬡ KI-Aktivität',
    'activity.waiting': '💡 Tippe "/research" für Web-Suche\n💡 "/files" zum Dateien durchsuchen\n💡 Hänge ein Bild mit 📎 an für KI-Vision',
    'activity.about': '🧠 Was ich über dich weiß',
    'activity.nothingSaved': 'Noch nichts gespeichert.',

    // ── Chat ──
    'chat.thinking': '🧠 Nox denkt nach…',
    'chat.generating': 'Antwort generieren…',
    'chat.analyzing': 'Anfrage analysieren…',
    'chat.readAloud': 'Vorlesen',
    'chat.copy': 'Kopieren',
    'chat.deepen': 'Vertiefen',
    'chat.placeholder': 'Nachricht eingeben… oder / für Skills',
    'chat.send': 'Senden',
    'chat.attachImage': 'Bild anfügen',
    'chat.removeImage': 'Bild entfernen',
    'chat.copied': 'Kopiert!',
    'chat.stop': 'Stopp',

    // ── Input Hint ──
    'hint.full': '↑ Letzter Befehl · / Skills · Enter Senden · Esc Abbruch',

    // ── Skills Tab ──
    'skills.title': '⚡ Skills verwalten',
    'skills.sub': 'Aktiviere Built-in Skills oder erstelle deine eigenen Befehle.',
    'skills.newSkill': '+ Neuer Skill',
    'skills.createTitle': 'Neuen Skill erstellen',
    'skills.editTitle': 'Skill bearbeiten',
    'skills.name': 'Skill-Name',
    'skills.nameHint': 'Nur Kleinbuchstaben, Zahlen und Bindestriche',
    'skills.trigger': 'Trigger',
    'skills.description': 'Beschreibung',
    'skills.descPlaceholder': 'Was macht dieser Skill?',
    'skills.tools': 'Tools (kommagetrennt)',
    'skills.prompt': 'Verhalten der KI (System Prompt)',
    'skills.promptPlaceholder': 'Du bist ein spezialisierter Assistent für…',
    'skills.save': '💾 Speichern',
    'skills.cancel': 'Abbrechen',
    'skills.saved': '✅ Gespeichert!',
    'skills.delete': 'Löschen',
    'skills.builtIn': 'Built-in',

    // ── History Tab ──
    'history.title': '📚 Gespeicherte Unterhaltungen',
    'history.sub': 'Deine Unterhaltungen bleiben nur lokal auf deinem Gerät.',
    'history.clear': '🗑 Verlauf löschen',
    'history.confirmClear': 'Verlauf wirklich löschen?',
    'history.empty': 'Noch keine Unterhaltungen gespeichert.',

    // ── Memory Tab ──
    'memory.title': '🧠 Langzeit-Memory',
    'memory.sub': 'Die KI erinnert sich über mehrere Sessions an wichtige Informationen.',
    'memory.searchPlaceholder': 'Memory durchsuchen…',
    'memory.delete': 'Löschen',

    // ── Profile Tab ──
    'profile.title': '👤 Dein Profil',
    'profile.sub': 'Hilft der KI, bessere und persönlichere Antworten zu geben.',
    'profile.name': 'Name',
    'profile.nameOptional': '(optional)',
    'profile.namePlaceholder': 'Wie heißt du?',
    'profile.expertise': 'Expertise',
    'profile.expertisePlaceholder': 'z.B. Python-Entwickler, Marketing, Arzt…',
    'profile.language': 'Bevorzugte Sprache',
    'profile.style': 'Antwort-Stil',
    'profile.voice': '🗣️ Bevorzugte Stimme (Text-to-Speech)',
    'profile.voiceDefault': 'System-Standard Stimme',
    'profile.save': '💾 Speichern',
    'profile.saved': '✅ Gespeichert!',
    'profile.styleDetailed': 'Ausführlich',
    'profile.styleShort': 'Kurz & knapp',
    'profile.styleTechnical': 'Technisch',
    'profile.styleSimple': 'Einfach erklärt',

    // ── Onboarding ──
    'onboarding.title': 'Willkommen bei MiMi Nox',
    'onboarding.sub': 'Wähle, wofür du mich hauptsächlich nutzen möchtest.',
    'onboarding.subLine2': 'Ich aktiviere die passenden Skills automatisch.',
    'onboarding.dev': 'Entwickler',
    'onboarding.devDesc': 'Code reviewen, Shell-Befehle, Debugging',
    'onboarding.research': 'Forscher',
    'onboarding.researchDesc': 'Web-Recherche, Faktencheck, Quellen',
    'onboarding.writer': 'Schreiber',
    'onboarding.writerDesc': 'Texte, E-Mails, Briefe, Zusammenfassungen',
    'onboarding.analyst': 'Analyst',
    'onboarding.analystDesc': 'Daten auswerten, Berichte, CSV lesen',
    'onboarding.medic': 'Medizin / Pflege',
    'onboarding.medicDesc': 'Informationen recherchieren, Dokumentation',
    'onboarding.allround': 'Allgemein',
    'onboarding.allroundDesc': 'Alle Skills aktivieren',
    'onboarding.hint': 'Du kannst Skills jederzeit unter ⚡ Skills anpassen.',
    'onboarding.start': 'Starten →',

    // ── Mobile Pairing Modal ──
    'mobile.title': '📱 Mobile Pairing',
    'mobile.sub': 'Scanne mich, um MiMi auf dein Handy zu holen (weltweit erreichbar).',
    'mobile.loading': 'Globaler Tunnel wird aufgebaut...',
    'mobile.loadingHint': 'Dies kann bis zu 3 Sekunden dauern.',
    'mobile.close': 'Schließen',

    // ── Skill Chips ──
    'chip.research': 'Web-Suche starten',
    'chip.files': 'Dateien lesen/suchen',
    'chip.write': 'Texte schreiben',
    'chip.review': 'Code reviewen',
    'chip.shell': 'Shell-Befehl',
    'chip.scan': 'Screenshots analysieren',

    // ── Errors ──
    'error.ollamaOffline': 'Ollama nicht erreichbar — starte: ollama serve',
    'error.modelBusy': 'Modell beschäftigt – bitte nochmal versuchen',
    'error.modelNotFound': 'Modell nicht installiert',

    // ── Artifact Panel ──
    'artifact.copy': 'Kopieren',
    'artifact.download': 'Download',
    'artifact.preview': 'Vorschau',
    'artifact.code': 'Code',
    'artifact.copied': '✓ Kopiert',

    // ── Misc ──
    'confirm.shell': 'Shell-Befehl ausführen?',
    'confirm.run': 'Ausführen',
    'confirm.cancel': 'Abbrechen',
  },

  en: {
    // ── Meta ──
    'meta.description': '◑ MiMi Nox – Local AI. Private. Local. Yours.',
    'meta.tagline': 'Private · Local · Yours.',

    // ── Topbar ──
    'nav.newChat': '📝 New Chat',
    'nav.chat': '💬 Chat',
    'nav.skills': '⚡ Skills',
    'nav.history': '📚 History',
    'nav.memory': '🧠 Memory',
    'nav.profile': '👤 Profile',
    'nav.mobilePairing': '📱 Connect Phone',
    'nav.autonom': '🤖 Autonomous',
    'status.connecting': 'Connecting…',
    'status.connected': 'Connected',
    'status.offline': 'Offline',

    // ── Offline Banner ──
    'offline.message': '⚠ Ollama not reachable — start with:',
    'offline.retry': '↻ Retry',

    // ── Welcome Screen ──
    'welcome.heading': 'How can I help?',
    'welcome.sub': 'Type a question or choose a skill',
    'welcome.searchNews': 'Search latest news',
    'welcome.analyzeFile': 'Analyze a file',
    'welcome.writeText': 'Write a text',

    // ── Activity Panel ──
    'activity.title': '⬡ AI Activity',
    'activity.waiting': '💡 Try "/research" to search the web\n💡 Type "/files" to browse documents\n💡 Attach an image with 📎 for AI vision',
    'activity.about': '🧠 What I know about you',
    'activity.nothingSaved': 'Nothing saved yet.',

    // ── Chat ──
    'chat.thinking': '🧠 Nox is thinking…',
    'chat.generating': 'Generating response…',
    'chat.analyzing': 'Analyzing request…',
    'chat.readAloud': 'Read aloud',
    'chat.copy': 'Copy',
    'chat.deepen': 'Dig deeper',
    'chat.placeholder': 'Type a message… or / for skills',
    'chat.send': 'Send',
    'chat.attachImage': 'Attach image',
    'chat.removeImage': 'Remove image',
    'chat.copied': 'Copied!',
    'chat.stop': 'Stop',

    // ── Input Hint ──
    'hint.full': '↑ Last command · / Skills · Enter Send · Esc Cancel',

    // ── Skills Tab ──
    'skills.title': '⚡ Manage Skills',
    'skills.sub': 'Activate built-in skills or create your own commands.',
    'skills.newSkill': '+ New Skill',
    'skills.createTitle': 'Create new skill',
    'skills.editTitle': 'Edit skill',
    'skills.name': 'Skill Name',
    'skills.nameHint': 'Lowercase letters, numbers and hyphens only',
    'skills.trigger': 'Trigger',
    'skills.description': 'Description',
    'skills.descPlaceholder': 'What does this skill do?',
    'skills.tools': 'Tools (comma-separated)',
    'skills.prompt': 'AI behavior (System Prompt)',
    'skills.promptPlaceholder': 'You are a specialized assistant for…',
    'skills.save': '💾 Save',
    'skills.cancel': 'Cancel',
    'skills.saved': '✅ Saved!',
    'skills.delete': 'Delete',
    'skills.builtIn': 'Built-in',

    // ── History Tab ──
    'history.title': '📚 Saved Conversations',
    'history.sub': 'Your conversations stay local on your device only.',
    'history.clear': '🗑 Clear History',
    'history.confirmClear': 'Really clear history?',
    'history.empty': 'No conversations saved yet.',

    // ── Memory Tab ──
    'memory.title': '🧠 Long-Term Memory',
    'memory.sub': 'The AI remembers important information across multiple sessions.',
    'memory.searchPlaceholder': 'Search memory…',
    'memory.delete': 'Delete',

    // ── Profile Tab ──
    'profile.title': '👤 Your Profile',
    'profile.sub': 'Helps the AI give better, more personalized answers.',
    'profile.name': 'Name',
    'profile.nameOptional': '(optional)',
    'profile.namePlaceholder': 'What's your name?',
    'profile.expertise': 'Expertise',
    'profile.expertisePlaceholder': 'e.g. Python developer, Marketing, Doctor…',
    'profile.language': 'Preferred Language',
    'profile.style': 'Response Style',
    'profile.voice': '🗣️ Preferred Voice (Text-to-Speech)',
    'profile.voiceDefault': 'System Default Voice',
    'profile.save': '💾 Save',
    'profile.saved': '✅ Saved!',
    'profile.styleDetailed': 'Detailed',
    'profile.styleShort': 'Short & concise',
    'profile.styleTechnical': 'Technical',
    'profile.styleSimple': 'Simply explained',

    // ── Onboarding ──
    'onboarding.title': 'Welcome to MiMi Nox',
    'onboarding.sub': 'Choose what you\'ll mainly use me for.',
    'onboarding.subLine2': 'I\'ll activate the right skills automatically.',
    'onboarding.dev': 'Developer',
    'onboarding.devDesc': 'Code review, shell commands, debugging',
    'onboarding.research': 'Researcher',
    'onboarding.researchDesc': 'Web research, fact-checking, sources',
    'onboarding.writer': 'Writer',
    'onboarding.writerDesc': 'Texts, emails, letters, summaries',
    'onboarding.analyst': 'Analyst',
    'onboarding.analystDesc': 'Analyze data, reports, read CSVs',
    'onboarding.medic': 'Medical / Care',
    'onboarding.medicDesc': 'Research information, documentation',
    'onboarding.allround': 'General',
    'onboarding.allroundDesc': 'Activate all skills',
    'onboarding.hint': 'You can adjust skills anytime under ⚡ Skills.',
    'onboarding.start': 'Start →',

    // ── Mobile Pairing Modal ──
    'mobile.title': '📱 Mobile Pairing',
    'mobile.sub': 'Scan to get MiMi on your phone (reachable worldwide).',
    'mobile.loading': 'Setting up global tunnel...',
    'mobile.loadingHint': 'This may take up to 3 seconds.',
    'mobile.close': 'Close',

    // ── Skill Chips ──
    'chip.research': 'Start web search',
    'chip.files': 'Read/search files',
    'chip.write': 'Write texts',
    'chip.review': 'Code review',
    'chip.shell': 'Shell command',
    'chip.scan': 'Analyze screenshots',

    // ── Errors ──
    'error.ollamaOffline': 'Ollama not reachable — start: ollama serve',
    'error.modelBusy': 'Model busy — please try again',
    'error.modelNotFound': 'Model not installed',

    // ── Artifact Panel ──
    'artifact.copy': 'Copy',
    'artifact.download': 'Download',
    'artifact.preview': 'Preview',
    'artifact.code': 'Code',
    'artifact.copied': '✓ Copied',

    // ── Misc ──
    'confirm.shell': 'Run shell command?',
    'confirm.run': 'Run',
    'confirm.cancel': 'Cancel',
  },
};

// ── Detect language ──────────────────────────────────────────────────────────
function detectLanguage() {
  // 1. Check localStorage override
  const stored = localStorage.getItem('mimi-nox-lang');
  if (stored && translations[stored]) return stored;

  // 2. Check browser language
  const browserLang = (navigator.language || navigator.userLanguage || 'en').substring(0, 2);
  return translations[browserLang] ? browserLang : 'en';
}

let _currentLang = detectLanguage();

/**
 * Get translation for a key.
 * @param {string} key - Dot-notation key (e.g. 'welcome.heading')
 * @param {Record<string, string>} [vars] - Optional interpolation variables
 * @returns {string} Translated string or key as fallback
 */
export function t(key, vars) {
  const str = translations[_currentLang]?.[key] || translations.en?.[key] || key;
  if (!vars) return str;
  return str.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? `{${k}}`);
}

/**
 * Current active language code.
 */
export function currentLang() {
  return _currentLang;
}

/**
 * Switch language and re-apply all translations.
 * @param {'de'|'en'} lang
 */
export function setLanguage(lang) {
  if (!translations[lang]) return;
  _currentLang = lang;
  localStorage.setItem('mimi-nox-lang', lang);
  document.documentElement.lang = lang;
  applyTranslations();
}

/**
 * Apply translations to all elements with data-i18n attributes.
 * Supports:
 *   data-i18n="key"                → textContent
 *   data-i18n-placeholder="key"    → placeholder
 *   data-i18n-title="key"          → title
 *   data-i18n-aria="key"           → aria-label
 *   data-i18n-html="key"           → innerHTML (use sparingly)
 */
export function applyTranslations() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    el.title = t(el.dataset.i18nTitle);
  });
  document.querySelectorAll('[data-i18n-aria]').forEach(el => {
    el.setAttribute('aria-label', t(el.dataset.i18nAria));
  });
  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    el.innerHTML = t(el.dataset.i18nHtml);
  });
}

export default { t, currentLang, setLanguage, applyTranslations, translations };
