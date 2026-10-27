/**
 * SIGMAP-AQUA · Agente IA flotante del módulo "IA - Análisis predictivo".
 * Archivo: static/js/ia_agente.js
 *
 * - El avatar es un robot SVG generado por código (buildRobotSvg) para poder
 *   animarlo: flota, parpadea, saluda, cambia los ojos según el riesgo,
 *   sigue el mouse con la mirada, "habla" mientras escribe y se duerme si
 *   nadie lo usa.
 * - Es global: base.html lo incluye en todas las páginas. Dentro de /ai/ lee
 *   los atributos data-ia-* de la página (datos en vivo); en el resto usa el
 *   resumen JSON #iaAgenteDatos que entrega apps.ia.context_processors.
 * - Las preguntas escritas y los chips se envían a la IA real (DeepSeek, con
 *   Gemini de respaldo) por POST a GLOBAL.url_preguntar; el backend le pasa
 *   los datos actuales del sistema. La respuesta trae hallazgos, tablas,
 *   recomendaciones y un botón para descargarla en Excel. Si la IA no está
 *   configurada o falla, el agente responde con sus reglas locales.
 * - El chat se conserva en sessionStorage mientras navegas el módulo y se
 *   puede limpiar con el botón de la cabecera.
 */
(() => {
  'use strict';

  /* ======================================================================
     Configuración
     ====================================================================== */
  const CONFIG = Object.freeze({
    typingDelayMs: 520,
    maxTypeMs: 900,
    blinkMinMs: 2600,
    blinkMaxMs: 5200,
    sleepAfterMs: 45000,
    teaserDelayMs: 1600,
    teaserDurationMs: 6500,
    storageKey: 'sigmap_ia_chat_v1',
    maxStoredMessages: 60,
    askTimeoutMs: 100000,     // DeepSeek puede razonar antes de responder
    previewRows: 6,           // filas de cada tabla visibles en el chat
  });

  /** Pregunta que se envía a la IA cuando se usa un chip. */
  const INTENT_PROMPTS = Object.freeze({
    resumen: 'Dame un resumen del estado actual de todas las piscinas activas: estado del agua, últimas lecturas y lo más importante a vigilar.',
    anomalias: 'Muéstrame las anomalías actuales de todas las piscinas activas: parámetro, valor, rango óptimo y gravedad.',
    recomendacion: '¿Qué debo hacer hoy en cada piscina según los datos actuales? Dame acciones concretas de campo.',
    pendientes: 'Muéstrame las predicciones pendientes y vencidas, con su intervalo previsto y qué tan probable es salir de rango.',
    alertas: 'Lista las alertas activas por piscina con su severidad, el valor que las disparó y qué hacer con cada una.',
  });

  /** Expresiones disponibles del robot. */
  const FACE = Object.freeze({
    HAPPY: 'happy',
    OPEN: 'open',
    WARN: 'warn',
    ALERT: 'alert',
    THINK: 'think',
    SLEEP: 'sleep',
  });

  const PARAM_ALIASES = Object.freeze({
    ph: ['ph', 'acidez', 'acido'],
    turbidez: ['turbidez', 'turbio', 'ntu', 'solidos'],
    temperatura: ['temperatura', 'temp', 'calor', 'frio', 'termic'],
    oxigeno: ['oxigeno', 'od', 'disuelto'],
  });

  const PARAM_LABELS = Object.freeze({
    ph: 'pH', turbidez: 'Turbidez', temperatura: 'Temperatura', oxigeno: 'Oxígeno disuelto',
  });

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /** Resumen global entregado por el context processor (todas las páginas). */
  const readGlobalData = () => {
    const node = document.getElementById('iaAgenteDatos');
    if (!node) return {};
    try {
      return JSON.parse(node.textContent) || {};
    } catch (error) {
      console.error('[Agente IA] Resumen global inválido:', error);
      return {};
    }
  };
  const GLOBAL = readGlobalData();

  /** Solo se aceptan enlaces internos del propio sistema. */
  const safeHref = (href) => (typeof href === 'string' && /^\/(?!\/)/.test(href) ? href : null);

  /* ======================================================================
     Utilidades
     ====================================================================== */
  /** @param {string} value */
  const normalize = (value) =>
    (value || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim();

  /** @param {Element|null} el */
  const textOf = (el) => (el ? el.textContent.replace(/\s+/g, ' ').trim() : '');

  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, reducedMotion ? 0 : ms));

  const randomBetween = (min, max) => min + Math.random() * (max - min);

  /** Primeras N oraciones de un texto largo. */
  const firstSentences = (text, count = 2) => {
    const parts = text.match(/[^.!?]+[.!?]+/g);
    return parts ? parts.slice(0, count).join(' ').trim() : text;
  };

  const storage = {
    read() {
      try {
        return JSON.parse(sessionStorage.getItem(CONFIG.storageKey)) || null;
      } catch (error) {
        return null;
      }
    },
    write(state) {
      try {
        sessionStorage.setItem(CONFIG.storageKey, JSON.stringify(state));
      } catch (error) {
        /* almacenamiento bloqueado: el chat sigue funcionando en memoria */
      }
    },
    clear() {
      try { sessionStorage.removeItem(CONFIG.storageKey); } catch (error) { /* sin acción */ }
    },
  };

  /* ======================================================================
     Robot SVG
     ====================================================================== */
  /**
   * Construye el SVG del robot SigmaP Aqua.
   * @param {string} uid - prefijo único para los ids de gradientes.
   * @param {{variant?: 'full'|'bust'|'head'}} [options]
   * @returns {string} markup SVG
   */
  function buildRobotSvg(uid, { variant = 'full' } = {}) {
    const viewBoxes = { full: '-6 -4 132 150', bust: '8 4 104 110', head: '26 8 68 58' };
    const id = (name) => `${uid}-${name}`;

    return `
<svg class="rb rb--${variant}" viewBox="${viewBoxes[variant]}" data-face="${FACE.HAPPY}"
     xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">
  <defs>
    <linearGradient id="${id('shell')}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ffffff"/><stop offset=".6" stop-color="#eef5fb"/><stop offset="1" stop-color="#c9daea"/>
    </linearGradient>
    <linearGradient id="${id('visor')}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#16345c"/><stop offset="1" stop-color="#081a33"/>
    </linearGradient>
    <linearGradient id="${id('accent')}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#2f80ed"/><stop offset="1" stop-color="#0e5a8a"/>
    </linearGradient>
    <linearGradient id="${id('beam')}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#5eead4" stop-opacity=".9"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/>
    </linearGradient>
    <radialGradient id="${id('glow')}" cx=".5" cy=".5" r=".5">
      <stop offset="0" stop-color="#a5f3fc" stop-opacity=".9"/><stop offset="1" stop-color="#a5f3fc" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <!-- ambiente: burbujas y destellos -->
  <g class="rb-fx">
    <circle class="rb-bubble rb-bubble--1" cx="18" cy="40" r="3.4"/>
    <circle class="rb-bubble rb-bubble--2" cx="104" cy="30" r="2.6"/>
    <circle class="rb-bubble rb-bubble--3" cx="12" cy="74" r="2"/>
    <circle class="rb-bubble rb-bubble--4" cx="108" cy="80" r="3"/>
    <path class="rb-spark rb-spark--1" d="M100 52 l1.6 4.4 4.4 1.6 -4.4 1.6 -1.6 4.4 -1.6 -4.4 -4.4 -1.6 4.4 -1.6z"/>
    <path class="rb-spark rb-spark--2" d="M14 56 l1.2 3.2 3.2 1.2 -3.2 1.2 -1.2 3.2 -1.2 -3.2 -3.2 -1.2 3.2 -1.2z"/>
    <path class="rb-spark rb-spark--3" d="M96 104 l1 2.6 2.6 1 -2.6 1 -1 2.6 -1 -2.6 -2.6 -1 2.6 -1z"/>
  </g>

  <g class="rb-float">
    <!-- propulsor -->
    <g class="rb-thruster">
      <path class="rb-beam" d="M53 116 L67 116 L80 146 L40 146 Z" fill="url(#${id('beam')})"/>
      <rect class="rb-particle rb-particle--1" x="55" y="122" width="2.4" height="2.4" rx=".6"/>
      <rect class="rb-particle rb-particle--2" x="62" y="126" width="2" height="2" rx=".5"/>
      <rect class="rb-particle rb-particle--3" x="58" y="132" width="2.6" height="2.6" rx=".6"/>
      <rect class="rb-particle rb-particle--4" x="66" y="120" width="1.8" height="1.8" rx=".4"/>
      <rect class="rb-particle rb-particle--5" x="51" y="128" width="1.8" height="1.8" rx=".4"/>
    </g>

    <!-- brazo izquierdo (en reposo) -->
    <g class="rb-arm rb-arm--left">
      <path d="M37 74 C27 80 22 96 25 108 C27 112 31 110 33 104 C36 94 39 84 41 78 Z"
            fill="url(#${id('shell')})" stroke="#1d3b63" stroke-width="1.6" stroke-linejoin="round"/>
    </g>

    <!-- cuerpo -->
    <g class="rb-body">
      <path d="M60 62 C80 62 87 76 86 92 C85 106 75 116 60 116 C45 116 35 106 34 92 C33 76 40 62 60 62 Z"
            fill="url(#${id('shell')})" stroke="#1d3b63" stroke-width="1.8"/>
      <path d="M41 96 C44 108 52 113 60 113" fill="none" stroke="#9fb6cc" stroke-width="1.2" stroke-linecap="round"/>
      <ellipse cx="60" cy="66" rx="20" ry="5.6" fill="url(#${id('accent')})" stroke="#1d3b63" stroke-width="1.4"/>
      <ellipse cx="60" cy="65.4" rx="14" ry="2.8" fill="#22d3ee" opacity=".55"/>
      <rect class="rb-chest-led" x="45" y="74" width="10" height="3" rx="1.5"/>
      <!-- emblema del pez -->
      <circle cx="60" cy="90" r="9" fill="#ffffff" stroke="#2f80ed" stroke-width="1.6"/>
      <path d="M54.5 90.5 C56.5 86.8 61.5 86.6 64 89.6 L66.6 87.4 L66 90.6 L66.6 93.6 L64 91.6 C61.5 94.4 56.5 94.2 54.5 90.5 Z"
            fill="#2f80ed"/>
      <circle cx="57.6" cy="89.6" r=".8" fill="#ffffff"/>
      <path d="M53.5 95.4 q2 -1.2 4 0 t4 0 t4 0" fill="none" stroke="#22d3ee" stroke-width=".9" stroke-linecap="round"/>
      <!-- tobera -->
      <ellipse cx="60" cy="114.6" rx="11" ry="3.6" fill="#1d3b63"/>
      <ellipse class="rb-nozzle" cx="60" cy="115.4" rx="7" ry="2" fill="#5eead4"/>
    </g>

    <!-- brazo derecho (el que saluda) -->
    <g class="rb-arm rb-arm--right">
      <path d="M83 74 C93 72 99 82 97 94 C96 100 91 100 89 95 C87 89 84 82 80 78 Z"
            fill="url(#${id('shell')})" stroke="#1d3b63" stroke-width="1.6" stroke-linejoin="round"/>
      <ellipse cx="94" cy="92" rx="3.4" ry="4.6" fill="url(#${id('accent')})" transform="rotate(-18 94 92)"/>
      <ellipse cx="94.4" cy="91" rx="1.4" ry="2.4" fill="#22d3ee" opacity=".8" transform="rotate(-18 94 92)"/>
    </g>

    <!-- cabeza -->
    <g class="rb-head">
      <rect x="51" y="54" width="18" height="8" rx="3" fill="#1d3b63"/>
      <path d="M60 12 C76 12 86 24 86 38 C86 50 76 58 60 58 C44 58 34 50 34 38 C34 24 44 12 60 12 Z"
            fill="url(#${id('shell')})" stroke="#1d3b63" stroke-width="1.8"/>
      <path d="M44 20 C52 14 66 13 75 18" fill="none" stroke="#ffffff" stroke-width="2.4" stroke-linecap="round" opacity=".9"/>
      <path d="M38 32 C46 28 52 30 58 30" fill="none" stroke="#b9cde0" stroke-width="1" stroke-linecap="round"/>
      <!-- orejas -->
      <circle cx="34" cy="38" r="6" fill="url(#${id('accent')})" stroke="#1d3b63" stroke-width="1.4"/>
      <circle class="rb-ear" cx="34" cy="38" r="3" fill="#22d3ee"/>
      <circle cx="86" cy="38" r="6" fill="url(#${id('accent')})" stroke="#1d3b63" stroke-width="1.4"/>
      <circle class="rb-ear" cx="86" cy="38" r="3" fill="#22d3ee"/>
      <!-- visor -->
      <rect class="rb-visor" x="38.5" y="26" width="43" height="23" rx="11.5" fill="url(#${id('visor')})" stroke="#1d3b63" stroke-width="1.4"/>
      <ellipse class="rb-visor-glow" cx="60" cy="37.5" rx="18" ry="8" fill="url(#${id('glow')})" opacity=".18"/>
      <path d="M45 30.5 C49 29 53 28.6 57 28.6" fill="none" stroke="#ffffff" stroke-width="1.2" stroke-linecap="round" opacity=".35"/>
      <!-- ojos -->
      <g class="rb-eyes">
        <g class="rb-face rb-face--happy">
          <path d="M47 39.5 Q51.5 32.5 56 39.5"/><path d="M64 39.5 Q68.5 32.5 73 39.5"/>
        </g>
        <g class="rb-face rb-face--open">
          <rect x="48.5" y="32.5" width="6" height="9" rx="3"/><rect x="65.5" y="32.5" width="6" height="9" rx="3"/>
        </g>
        <g class="rb-face rb-face--warn">
          <rect x="48.5" y="34.5" width="6.5" height="6" rx="3"/><rect x="65" y="34.5" width="6.5" height="6" rx="3"/>
          <path class="rb-brow" d="M47 32.5 L56 33.5"/><path class="rb-brow" d="M64 33.5 L73 32.5"/>
        </g>
        <g class="rb-face rb-face--alert">
          <rect x="48.5" y="34" width="6.5" height="7.5" rx="2.4"/><rect x="65" y="34" width="6.5" height="7.5" rx="2.4"/>
          <path class="rb-brow" d="M47 31 L56 33.6"/><path class="rb-brow" d="M64 33.6 L73 31"/>
        </g>
        <g class="rb-face rb-face--think">
          <rect x="50.5" y="31.5" width="5.6" height="7" rx="2.8"/><rect x="66.5" y="31.5" width="5.6" height="7" rx="2.8"/>
        </g>
        <g class="rb-face rb-face--sleep">
          <path d="M47.5 37.5 Q51.5 40.5 55.5 37.5"/><path d="M64.5 37.5 Q68.5 40.5 72.5 37.5"/>
        </g>
      </g>
    </g>

    <!-- zzz -->
    <g class="rb-zzz">
      <text x="84" y="16">z</text><text x="91" y="9">z</text><text x="98" y="2">Z</text>
    </g>
  </g>
</svg>`;
  }

  /**
   * Controlador de un robot ya insertado en el DOM.
   * Expone métodos de gesto y gestiona parpadeo y mirada.
   */
  class Robot {
    /** @param {SVGSVGElement} svg */
    constructor(svg) {
      this.svg = svg;
      this.mood = FACE.HAPPY;
      this.face = FACE.HAPPY;
      this.blinkTimer = null;
      this.gestureTimers = new Set();
      if (!reducedMotion) this.scheduleBlink();
    }

    /** Expresión base según el estado del cultivo. */
    setMood(face) {
      this.mood = face;
      if (![FACE.THINK, FACE.SLEEP].includes(this.face)) this.setFace(face);
    }

    setFace(face) {
      this.face = face;
      this.svg.dataset.face = face;
    }

    restoreMood() {
      this.setFace(this.mood);
    }

    /** Aplica una clase temporal de gesto. */
    gesture(name, durationMs) {
      if (reducedMotion) return;
      const cls = `rb--${name}`;
      this.svg.classList.remove(cls);
      // fuerza reflow para reiniciar la animación
      void this.svg.getBoundingClientRect();
      this.svg.classList.add(cls);
      const timer = setTimeout(() => {
        this.svg.classList.remove(cls);
        this.gestureTimers.delete(timer);
      }, durationMs);
      this.gestureTimers.add(timer);
    }

    wave() { this.gesture('wave', 1700); }
    hop() { this.gesture('hop', 650); }
    shake() { this.gesture('shake', 700); }
    spin() { this.gesture('spin', 900); }

    setTalking(value) { this.svg.classList.toggle('rb--talking', value); }

    blink() {
      if (this.face === FACE.SLEEP) return;
      this.svg.classList.add('rb--blink');
      setTimeout(() => this.svg.classList.remove('rb--blink'), 160);
    }

    scheduleBlink() {
      clearTimeout(this.blinkTimer);
      this.blinkTimer = setTimeout(() => {
        this.blink();
        if (Math.random() < 0.25) setTimeout(() => this.blink(), 260); // doble parpadeo
        this.scheduleBlink();
      }, randomBetween(CONFIG.blinkMinMs, CONFIG.blinkMaxMs));
    }

    /**
     * Orienta mirada y cabeza hacia un punto de la pantalla.
     * @param {number} clientX
     * @param {number} clientY
     */
    lookAt(clientX, clientY) {
      const rect = this.svg.getBoundingClientRect();
      if (!rect.width) return;
      const dx = clientX - (rect.left + rect.width / 2);
      const dy = clientY - (rect.top + rect.height / 3);
      const distance = Math.hypot(dx, dy) || 1;
      const reach = Math.min(1, distance / 260);
      this.svg.style.setProperty('--rb-look-x', `${((dx / distance) * 2.6 * reach).toFixed(2)}px`);
      this.svg.style.setProperty('--rb-look-y', `${((dy / distance) * 1.8 * reach).toFixed(2)}px`);
      this.svg.style.setProperty('--rb-tilt', `${((dx / distance) * 7 * reach).toFixed(2)}deg`);
    }

    resetLook() {
      ['--rb-look-x', '--rb-look-y', '--rb-tilt'].forEach((prop) => this.svg.style.removeProperty(prop));
    }
  }

  /* ======================================================================
     Lectura de datos del módulo (contrato data-ia-*)
     ====================================================================== */
  /**
   * @typedef {Object} ModuleData
   * @property {Object<string,{value:string, sub:string}>} kpis
   * @property {Array<Object>} pending
   * @property {Object|null} analysis
   */

  /**
   * Lee los datos en vivo de la página del módulo de IA.
   * @returns {ModuleData|null} null si la página actual no es /ai/
   */
  function collectFromPage() {
    if (!document.querySelector('[data-ia-analisis], [data-ia-kpi]')) return null;
    const kpis = {};
    document.querySelectorAll('[data-ia-kpi]').forEach((card) => {
      kpis[card.dataset.iaKpi] = {
        value: textOf(card.querySelector('.sg-kpi-valor')),
        sub: textOf(card.querySelector('.sg-kpi-sub')),
      };
    });

    const pending = [...document.querySelectorAll('[data-ia-prediccion]')].map((row) => ({
      param: row.dataset.parametro || '',
      targetDay: row.dataset.fecha || '',
      interval: row.dataset.intervalo || '',
      expected: row.dataset.esperado || '',
      probability: parseFloat(row.dataset.probabilidad) || 0,
      overdue: row.dataset.vencida === '1',
      reason: textOf(row.querySelector('[data-ia-justificacion]')),
    }));

    const hero = document.querySelector('[data-ia-analisis]');
    let analysis = null;
    if (hero) {
      analysis = {
        pool: hero.dataset.iaPiscina || '',
        type: hero.dataset.iaTipo || '',
        confidence: hero.dataset.iaConfianza || '',
        risk: hero.dataset.iaRiesgo || '',
        diagnosis: textOf(document.querySelector('[data-ia-diagnostico]')),
        anomalies: [...document.querySelectorAll('[data-ia-anomalia]')].map((item) => ({
          param: item.dataset.parametro || '',
          severity: item.dataset.gravedad || '',
          description: textOf(item.querySelector('[data-ia-descripcion]')),
        })),
        recommendations: [...document.querySelectorAll('[data-ia-recomendacion]')].map(textOf),
      };
    }

    return { kpis, pending, analysis };
  }

  /**
   * Adapta el resumen JSON global a la misma forma que collectFromPage.
   * @returns {ModuleData}
   */
  function collectFromGlobal() {
    const precision = GLOBAL.precision || {};
    const kpis = {
      precision: {
        value: precision.tasa_acierto != null ? `${precision.tasa_acierto}%` : '—',
        sub: precision.evaluadas ? `sobre ${precision.evaluadas} predicción(es)` : 'sin predicciones evaluadas aún',
      },
      acertadas: {
        value: String(precision.acertadas || 0),
        sub: `${precision.fallidas || 0} fallida(s)`,
      },
    };

    const pending = (GLOBAL.pendientes || []).map((p) => ({
      param: p.parametro || '',
      targetDay: p.fecha || '',
      interval: p.intervalo || '',
      expected: p.esperado || '',
      probability: Number(p.probabilidad) || 0,
      overdue: Boolean(p.vencida),
      reason: p.justificacion || '',
    }));

    const a = GLOBAL.analisis;
    const analysis = a ? {
      pool: a.piscina || '',
      type: a.tipo || '',
      confidence: a.confianza != null ? String(a.confianza) : '',
      risk: a.riesgo || '',
      diagnosis: a.diagnostico || '',
      anomalies: (a.anomalias || []).map((x) => ({
        param: x.parametro || '', severity: x.gravedad || '', description: x.descripcion || '',
      })),
      recommendations: a.recomendaciones || [],
    } : null;

    return { kpis, pending, analysis };
  }

  /**
   * Datos para el agente: la página en vivo si estamos en /ai/, si no el
   * resumen global. Siempre agrega alertas activas y enlaces de navegación.
   * @returns {ModuleData}
   */
  function collectModuleData() {
    const fromPage = collectFromPage();
    const data = fromPage || collectFromGlobal();
    data.inModule = Boolean(fromPage) || Boolean(GLOBAL.en_modulo_ia);
    data.alerts = GLOBAL.alertas || { activas: 0, graves: 0 };
    data.links = {
      module: safeHref(GLOBAL.url_analisis) || safeHref(GLOBAL.url_modulo) || '/ai/',
      alerts: safeHref(GLOBAL.url_alertas) || '/alertas/',
    };
    return data;
  }

  /** @param {string} level - alta|media|baja|alto|medio|bajo */
  const toneFromLevel = (level) => {
    const value = normalize(level);
    if (value.startsWith('alt') || value.startsWith('crit')) return 'alerta';
    if (value.startsWith('med')) return 'aviso';
    if (value.startsWith('baj')) return 'ok';
    return 'info';
  };

  /** Expresión del robot según el riesgo proyectado. */
  const faceFromRisk = (risk) => {
    const tone = toneFromLevel(risk);
    if (tone === 'alerta') return FACE.ALERT;
    if (tone === 'aviso') return FACE.WARN;
    return FACE.HAPPY;
  };

  const matchParam = (paramName, key) =>
    PARAM_ALIASES[key].some((alias) => normalize(paramName).replace(/\s/g, '').includes(alias));

  /** Firma del análisis visible, para detectar cambios entre recargas. */
  const analysisSignature = (analysis) =>
    (analysis ? `${analysis.pool}|${analysis.type}|${analysis.confidence}|${analysis.risk}` : 'none');

  /* ======================================================================
     Respuestas del agente
     ====================================================================== */
  /**
   * @param {string} intent
   * @param {ModuleData} data
   * @param {string} [paramKey]
   * @returns {Array<{tag?: string, text: string, tone: string}>}
   */
  function buildMessages(intent, data, paramKey) {
    const msgs = buildIntentMessages(intent, data, paramKey);
    const linkable = ['resumen', 'anomalias', 'recomendacion', 'pendientes', 'parametro'];
    const last = msgs[msgs.length - 1];
    if (!data.inModule && data.analysis && last && !last.link && linkable.includes(intent)) {
      last.link = { href: data.links.module, label: 'Ver en el módulo de IA →' };
    }
    return msgs;
  }

  /**
   * Mensajes base de cada intención.
   * @param {string} intent
   * @param {ModuleData} data
   * @param {string} [paramKey]
   */
  function buildIntentMessages(intent, data, paramKey) {
    const { kpis, pending, analysis } = data;
    const overdue = pending.filter((p) => p.overdue);
    const highAnomalies = analysis ? analysis.anomalies.filter((a) => toneFromLevel(a.severity) === 'alerta') : [];
    const noAnalysis = {
      tone: 'info',
      text: 'Aún no hay un análisis. Usa **Generar análisis** en el módulo de IA para que pueda leer el estado de una piscina.',
      link: data.inModule ? undefined : { href: data.links.module, label: 'Ir al módulo de IA →' },
    };

    switch (intent) {
      case 'bienvenida': {
        if (!analysis) return [noAnalysis];
        const msgs = [{
          tag: analysis.pool || 'Estado actual',
          tone: toneFromLevel(analysis.risk),
          text: `Riesgo proyectado: **${analysis.risk || 'sin dato'}**. Detecté **${analysis.anomalies.length}** anomalía(s), ${highAnomalies.length} de gravedad alta.`,
        }];
        if (overdue.length) {
          msgs.push({ tone: 'aviso', text: `Tienes **${overdue.length} predicción(es) vencida(s)** listas para contrastar con los sensores.` });
        }
        if (data.alerts.activas) {
          msgs.push({
            tone: data.alerts.graves ? 'alerta' : 'aviso',
            text: `Además hay **${data.alerts.activas}** alerta(s) activa(s) de sensores.`,
            link: { href: data.links.alerts, label: 'Ver alertas →' },
          });
        }
        if (!data.inModule) {
          msgs[0].link = { href: data.links.module, label: 'Abrir análisis completo →' };
        }
        return msgs;
      }

      case 'alertas': {
        const { activas, graves } = data.alerts;
        if (!activas) return [{ tone: 'ok', text: 'No hay alertas activas de sensores en este momento. ✅' }];
        return [{
          tag: 'Alertas de sensores',
          tone: graves ? 'alerta' : 'aviso',
          text: `Hay **${activas}** alerta(s) activa(s)${graves ? `, **${graves}** de severidad alta o crítica` : ''}. Revísalas para confirmar si el problema sigue en el agua.`,
          link: { href: data.links.alerts, label: 'Ir a Alertas →' },
        }];
      }

      case 'cambio': {
        if (!analysis) return [noAnalysis];
        return [{
          tag: 'Nuevo análisis en pantalla',
          tone: toneFromLevel(analysis.risk),
          text: `Ahora veo **${analysis.pool}** · ${analysis.type}. Riesgo **${analysis.risk || 'sin dato'}** con ${analysis.anomalies.length} anomalía(s).`,
        }];
      }

      case 'resumen': {
        const precision = kpis.precision;
        const hits = kpis.acertadas;
        const msgs = [{
          tag: 'Modelo predictivo',
          tone: 'info',
          text: `Precisión: **${precision ? precision.value : '—'}** (${precision ? precision.sub : 'sin dato'}). Acertadas: **${hits ? hits.value : '0'}** · ${hits ? hits.sub : ''}. Pendientes: **${pending.length}**.`,
        }];
        if (analysis) {
          msgs.push({
            tag: `${analysis.type} · confianza ${analysis.confidence || '?'}%`,
            tone: toneFromLevel(analysis.risk),
            text: firstSentences(analysis.diagnosis, 2) || 'El análisis no trae texto de diagnóstico.',
          });
        } else {
          msgs.push(noAnalysis);
        }
        return msgs;
      }

      case 'anomalias': {
        if (!analysis) return [noAnalysis];
        if (!analysis.anomalies.length) {
          return [{ tone: 'ok', text: `Sin anomalías registradas en **${analysis.pool}** para este análisis. 💧` }];
        }
        const msgs = analysis.anomalies.map((a) => ({
          tag: `${a.param} · gravedad ${a.severity}`,
          tone: toneFromLevel(a.severity),
          text: a.description,
        }));
        const risky = pending.filter((p) => p.probability >= 70);
        if (risky.length) {
          msgs.push({
            tag: 'Predicciones en riesgo',
            tone: 'aviso',
            text: risky.map((p) => `• **${p.param}**: ${p.probability}% de salir de rango (${p.targetDay})`).join('\n'),
          });
        }
        return msgs;
      }

      case 'recomendacion': {
        if (!analysis) return [noAnalysis];
        if (!analysis.recommendations.length) {
          return [{ tone: 'info', text: 'Este análisis no incluye recomendaciones. Genera uno de tipo **Recomendación operativa**.' }];
        }
        const [first, ...rest] = analysis.recommendations;
        const msgs = [{ tag: `Prioridad de hoy · ${analysis.pool}`, tone: toneFromLevel(analysis.risk), text: first }];
        if (rest.length) msgs.push({ tag: 'También conviene', tone: 'info', text: rest.map((r) => `• ${r}`).join('\n') });
        return msgs;
      }

      case 'pendientes': {
        if (!pending.length) {
          return [{ tone: 'ok', text: 'No hay predicciones pendientes. Genera una **Predicción de riesgo** para empezar a medir el acierto del modelo.' }];
        }
        const msgs = [{
          tag: `${pending.length} predicción(es) en seguimiento`,
          tone: 'info',
          text: pending.map((p) => `• **${p.param}** → ${p.interval} (${p.overdue ? 'vencida' : 'esperando'}, ${p.targetDay})`).join('\n'),
        }];
        if (overdue.length) {
          msgs.push({ tone: 'aviso', text: `Pulsa **Contrastar ${overdue.length} vencida(s)** en "Seguimiento de predicciones" para calcular el acierto real.` });
        }
        return msgs;
      }

      case 'parametro': {
        const label = PARAM_LABELS[paramKey];
        const anomaly = analysis && analysis.anomalies.find((a) => matchParam(a.param, paramKey));
        const prediction = pending.find((p) => matchParam(p.param, paramKey));
        const msgs = [];
        if (anomaly) msgs.push({ tag: `${label} · gravedad ${anomaly.severity}`, tone: toneFromLevel(anomaly.severity), text: anomaly.description });
        if (prediction) {
          msgs.push({
            tag: `Predicción de ${label}`,
            tone: prediction.probability >= 70 ? 'aviso' : 'info',
            text: `Intervalo previsto **${prediction.interval}** (esperado ${prediction.expected}) para el ${prediction.targetDay}. Probabilidad fuera de rango: **${prediction.probability}%**.${prediction.reason ? `\n${prediction.reason}` : ''}`,
          });
        }
        if (!msgs.length) msgs.push({ tone: 'ok', text: `No tengo alertas ni predicciones activas de **${label}** en este momento.` });
        return msgs;
      }

      case 'piscinas': {
        const pools = Array.isArray(GLOBAL.piscinas) ? GLOBAL.piscinas : [];
        if (!pools.length) return [{ tone: 'info', text: 'No hay piscinas registradas todavía.', link: { href: '/geomembranas/', label: 'Ir a Geomembranas →' } }];
        const active = pools.filter((p) => p.activa);
        const list = active.map((p) => `**${p.nombre}** (${p.codigo})${p.apta ? '' : ' · no apta'}`).join(', ');
        return [{
          tone: 'info',
          text: `Hay **${active.length}** piscina(s) activa(s) de ${pools.length} registradas: ${list || 'ninguna activa'}.`,
          link: { href: '/geomembranas/', label: 'Ver geomembranas →' },
        }];
      }

      case 'saludo':
        return [{ tone: 'info', text: '¡Hola! 👋 Pregúntame por **pH**, **turbidez**, **temperatura** u **oxígeno**, o usa los botones rápidos.' }];

      case 'gracias':
        return [{ tone: 'ok', text: '¡Con gusto! Sigo vigilando el agua de tus piscinas. 🐟' }];

      default:
        return [{
          tone: 'info',
          text: 'Puedo hablarte de **pH**, **turbidez**, **temperatura** u **oxígeno**, darte un **resumen**, las **anomalías**, la **recomendación de hoy**, las **pendientes** o las **alertas activas**.',
        }];
    }
  }

  /** Detecta la intención a partir de una consulta escrita. */
  function resolveQuery(query) {
    const q = normalize(query);
    const words = q.split(/[^a-z0-9]+/).filter(Boolean);
    const paramKey = Object.keys(PARAM_ALIASES)
      .find((key) => PARAM_ALIASES[key].some((alias) => words.some((w) => w.startsWith(alias))));
    if (paramKey) return { intent: 'parametro', paramKey };
    if (/^(hola|buenas|hey|saludos)/.test(q)) return { intent: 'saludo' };
    if (/gracias|genial|perfecto/.test(q)) return { intent: 'gracias' };
    if (/piscina|estanque|geomembrana/.test(q)) return { intent: 'piscinas' };
    if (/resumen|estado|general|como va/.test(q)) return { intent: 'resumen' };
    if (/alertas|sensor|alarma/.test(q)) return { intent: 'alertas' };
    if (/anomal|alerta|riesgo|problema/.test(q)) return { intent: 'anomalias' };
    if (/recomend|hacer|hoy|accion|consejo/.test(q)) return { intent: 'recomendacion' };
    if (/pendient|vencid|contrast/.test(q)) return { intent: 'pendientes' };
    return { intent: 'ayuda' };
  }

  /** Divide "**negrita**" en segmentos seguros (sin innerHTML). */
  const toSegments = (text) => text.split(/\*\*/).map((part, i) => ({ text: part, bold: i % 2 === 1 })).filter((s) => s.text);

  /** Crea un elemento con clase y texto (nunca innerHTML con datos). */
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  };

  /** Tono del mensaje según el hallazgo más grave. */
  const toneFromFindings = (findings) => {
    const levels = (findings || []).map((f) => f.gravedad);
    if (levels.includes('alta')) return 'alerta';
    if (levels.includes('media')) return 'aviso';
    return findings && findings.length ? 'ok' : 'info';
  };

  /**
   * Parte enriquecida de una respuesta de la IA: hallazgos, tablas,
   * recomendaciones, enlaces y descarga en Excel.
   * @param {{findings?:Array, tables?:Array, recommendations?:Array, links?:Array, excel?:string, model?:string}} rich
   * @returns {HTMLElement}
   */
  function buildRich(rich) {
    const box = el('div', 'ia-msg__rich');

    if (rich.findings && rich.findings.length) {
      const list = el('ul', 'ia-msg__findings');
      rich.findings.forEach((f) => {
        const item = el('li', `ia-finding ia-finding--${['alta', 'media', 'baja'].includes(f.gravedad) ? f.gravedad : 'media'}`);
        const where = [f.piscina, f.parametro].filter(Boolean).join(' · ');
        if (where) item.append(el('strong', null, `${where}: `));
        item.append(document.createTextNode(f.descripcion || ''));
        list.append(item);
      });
      box.append(list);
    }

    (rich.tables || []).forEach((table) => {
      const wrap = el('div', 'ia-msg__table-wrap');
      wrap.append(el('p', 'ia-msg__table-title', table.titulo));
      const grid = el('table', 'ia-msg__table');
      const headRow = el('tr');
      (table.columnas || []).forEach((col) => headRow.append(el('th', null, col)));
      const head = el('thead');
      head.append(headRow);
      grid.append(head);
      const body = el('tbody');
      (table.filas || []).slice(0, CONFIG.previewRows).forEach((row) => {
        const tr = el('tr');
        row.forEach((cell) => tr.append(el('td', null, cell)));
        body.append(tr);
      });
      grid.append(body);
      wrap.append(grid);
      const extra = (table.filas || []).length - CONFIG.previewRows;
      if (extra > 0) wrap.append(el('p', 'ia-msg__note', `+${extra} fila(s) más en el Excel`));
      box.append(wrap);
    });

    if (rich.recommendations && rich.recommendations.length) {
      box.append(el('p', 'ia-msg__section', 'Recomendaciones'));
      const list = el('ul', 'ia-msg__recs');
      rich.recommendations.forEach((rec) => list.append(el('li', null, rec)));
      box.append(list);
    }

    const actions = el('div', 'ia-msg__actions');
    const excel = safeHref(rich.excel);
    if (excel) {
      const download = el('a', 'ia-msg__download', '⬇ Descargar Excel');
      download.href = excel;
      download.setAttribute('download', '');
      actions.append(download);
    }
    (rich.links || []).forEach((link) => {
      const href = safeHref(link.url);
      if (!href) return;
      const a = el('a', 'ia-msg__chip-link', link.etiqueta || 'Abrir');
      a.href = href;
      actions.append(a);
    });
    if (actions.children.length) box.append(actions);
    if (rich.notice) box.append(el('p', 'ia-msg__note', rich.notice));
    if (rich.model) box.append(el('p', 'ia-msg__note', `Respondido por ${rich.model} con los datos actuales del sistema.`));
    return box;
  }

  /* ======================================================================
     Agente
     ====================================================================== */
  function initAgent() {
    const agent = document.querySelector('[data-agent]');
    if (!agent) return;

    const ui = {
      trigger: agent.querySelector('[data-agent-toggle]'),
      triggerAvatar: agent.querySelector('[data-agent-robot="trigger"]'),
      headerAvatar: agent.querySelector('[data-agent-robot="header"]'),
      panel: agent.querySelector('.ia-agent__panel'),
      body: agent.querySelector('[data-agent-body]'),
      welcome: agent.querySelector('[data-agent-welcome]'),
      welcomeAvatar: agent.querySelector('[data-agent-robot="welcome"]'),
      welcomeText: agent.querySelector('[data-agent-welcome-text]'),
      log: agent.querySelector('[data-agent-log]'),
      badge: agent.querySelector('[data-agent-badge]'),
      teaser: agent.querySelector('[data-agent-teaser]'),
      teaserText: agent.querySelector('[data-agent-teaser-text]'),
      status: agent.querySelector('[data-agent-status]'),
      clear: agent.querySelector('[data-agent-clear]'),
      close: agent.querySelector('[data-agent-close]'),
      form: agent.querySelector('[data-agent-form]'),
      input: agent.querySelector('[data-agent-form] input[type="text"]'),
      controls: agent.querySelectorAll('[data-agent-intent], .ia-agent__send, [data-agent-clear]'),
    };

    // ---- Robots ---------------------------------------------------------
    const mountRobot = (host, variant) => {
      if (!host) return null;
      host.innerHTML = buildRobotSvg(`rb-${variant}-${Math.random().toString(36).slice(2, 7)}`, { variant });
      return new Robot(host.querySelector('svg'));
    };
    const robots = {
      trigger: mountRobot(ui.triggerAvatar, 'bust'),
      header: mountRobot(ui.headerAvatar, 'head'),
      welcome: mountRobot(ui.welcomeAvatar, 'full'),
    };
    const allRobots = () => Object.values(robots).filter(Boolean);
    const everyRobot = (fn) => allRobots().forEach(fn);

    // ---- Estado ---------------------------------------------------------
    let data;
    try {
      data = collectModuleData();
    } catch (error) {
      console.error('[Agente IA] No se pudieron leer los datos del módulo:', error);
      data = { kpis: {}, pending: [], analysis: null, inModule: false, alerts: { activas: 0, graves: 0 }, links: { module: '/ai/', alerts: '/alertas/' } };
    }
    const mood = data.analysis ? faceFromRisk(data.analysis.risk) : FACE.HAPPY;
    const highCount = data.analysis ? data.analysis.anomalies.filter((a) => toneFromLevel(a.severity) === 'alerta').length : 0;
    agent.dataset.mood = mood;
    everyRobot((r) => r.setMood(mood));

    let busy = false;
    let history = [];

    const persist = () => {
      storage.write({ signature: analysisSignature(data.analysis), messages: history.slice(-CONFIG.maxStoredMessages) });
    };

    const setStatus = (text) => { if (ui.status) ui.status.textContent = text; };

    const setBusy = (value) => {
      busy = value;
      ui.controls.forEach((control) => { control.disabled = value; });
      agent.classList.toggle('is-busy', value);
    };

    const scrollToEnd = () => { ui.body.scrollTop = ui.body.scrollHeight; };

    const showWelcome = (visible) => {
      ui.welcome.hidden = !visible;
      ui.log.hidden = visible;
    };

    // ---- Badge + teaser -------------------------------------------------
    if (ui.badge && highCount > 0) {
      ui.badge.textContent = String(highCount);
      ui.badge.hidden = false;
      ui.trigger.setAttribute('aria-label', `Abrir Asistente IA de SigmaP Aqua (${highCount} anomalías altas)`);
    }

    if (ui.welcomeText) {
      if (!data.analysis) {
        ui.welcomeText.textContent = 'Vigilo pH, temperatura, turbidez y oxígeno de tus piscinas. ¿Qué quieres saber?';
      } else if (data.inModule) {
        ui.welcomeText.textContent = `Estoy viendo ${data.analysis.pool}. Riesgo ${data.analysis.risk || 'sin dato'}. ¿Qué quieres saber?`;
      } else {
        ui.welcomeText.textContent = `Te acompaño en todo SIGMAP-AQUA. Último análisis: ${data.analysis.pool}, riesgo ${data.analysis.risk || 'sin dato'}. ¿Qué quieres saber?`;
      }
    }

    let teaserTimer = null;
    const hideTeaser = () => {
      clearTimeout(teaserTimer);
      if (ui.teaser) ui.teaser.classList.remove('is-visible');
    };
    const showTeaser = () => {
      if (!ui.teaser || agent.classList.contains('is-open')) return;
      let text = '¡Hola! Soy tu asistente de calidad del agua.';
      if (highCount) text = `Detecté ${highCount} anomalía${highCount > 1 ? 's' : ''} grave${highCount > 1 ? 's' : ''} en ${data.analysis.pool}.`;
      else if (data.analysis) text = `${data.analysis.pool}: riesgo ${data.analysis.risk || 'sin dato'}. ¿Te cuento?`;
      ui.teaserText.textContent = text;
      ui.teaser.classList.add('is-visible');
      robots.trigger && robots.trigger.wave();
      teaserTimer = setTimeout(hideTeaser, CONFIG.teaserDurationMs);
    };

    // ---- Mensajes -------------------------------------------------------
    /**
     * Pinta un mensaje del agente.
     * @param {{tag?: string, text: string, tone?: string}} msg
     * @param {boolean} animate - efecto de tecleo
     */
    const renderAgentMessage = (msg, animate) => new Promise((resolve) => {
      const bubble = document.createElement('div');
      bubble.className = `ia-msg ia-msg--${msg.tone || 'info'}`;
      if (msg.tag) {
        const tag = document.createElement('span');
        tag.className = 'ia-msg__tag';
        tag.textContent = msg.tag;
        bubble.append(tag);
      }
      const content = document.createElement('div');
      content.className = 'ia-msg__text';
      bubble.append(content);

      const segments = toSegments(msg.text).map((segment) => {
        const node = segment.bold ? document.createElement('strong') : document.createTextNode('');
        content.appendChild(node);
        return { node, text: segment.text };
      });
      const href = msg.link && safeHref(msg.link.href);
      let linkNode = null;
      if (href) {
        linkNode = document.createElement('a');
        linkNode.className = 'ia-msg__link';
        linkNode.href = href;
        linkNode.textContent = msg.link.label || 'Abrir';
      }
      const finish = () => {
        if (msg.rich) bubble.append(buildRich(msg.rich));
        if (linkNode) bubble.append(linkNode);
        scrollToEnd();
        resolve();
      };
      ui.log.appendChild(bubble);

      const total = segments.reduce((sum, s) => sum + s.text.length, 0);
      if (!animate || reducedMotion || total === 0) {
        segments.forEach((s) => { s.node.textContent = s.text; });
        finish();
        return;
      }

      // setTimeout (no requestAnimationFrame): rAF se pausa con la pestaña en
      // segundo plano y dejaría el chat bloqueado a mitad de mensaje.
      const start = performance.now();
      const duration = Math.min(CONFIG.maxTypeMs, total * 14);
      const step = () => {
        const elapsed = performance.now() - start;
        let budget = Math.ceil(total * Math.min(1, elapsed / duration));
        segments.forEach((s) => {
          const take = Math.max(0, Math.min(s.text.length, budget));
          s.node.textContent = s.text.slice(0, take);
          budget -= take;
        });
        scrollToEnd();
        if (elapsed < duration) setTimeout(step, 16);
        else finish();
      };
      step();
    });

    const renderUserMessage = (text) => {
      const bubble = document.createElement('div');
      bubble.className = 'ia-msg ia-msg--user';
      bubble.textContent = text;
      ui.log.appendChild(bubble);
      scrollToEnd();
    };

    const showTyping = () => {
      const dots = document.createElement('div');
      dots.className = 'ia-typing';
      dots.setAttribute('aria-label', 'El asistente está escribiendo');
      dots.innerHTML = '<span></span><span></span><span></span>';
      ui.log.appendChild(dots);
      scrollToEnd();
      return dots;
    };

    /** Reproduce una secuencia de mensajes del agente con gestos. */
    const speak = async (messages) => {
      setBusy(true);
      showWelcome(false);
      try {
        for (const msg of messages) {
          everyRobot((r) => r.setFace(FACE.THINK));
          setStatus('Pensando…');
          const dots = showTyping();
          await wait(CONFIG.typingDelayMs);
          dots.remove();

          everyRobot((r) => { r.restoreMood(); r.setTalking(true); });
          setStatus('Escribiendo…');
          if (msg.tone === 'alerta') everyRobot((r) => r.shake());
          await renderAgentMessage(msg, true);
          everyRobot((r) => r.setTalking(false));

          history.push({ role: 'agent', ...msg });
        }
        persist();
      } finally {
        everyRobot((r) => { r.setTalking(false); r.restoreMood(); });
        setStatus('Análisis predictivo en tiempo real');
        setBusy(false);
      }
    };

    const respond = (intent, paramKey) => {
      let fresh;
      try {
        fresh = collectModuleData();
      } catch (error) {
        console.error('[Agente IA] Error leyendo el módulo:', error);
        return speak([{ tone: 'alerta', text: 'No pude leer los datos del módulo. Recarga la página e inténtalo de nuevo.' }]);
      }
      return speak(buildMessages(intent, fresh, paramKey));
    };

    const ask = (label, intent, paramKey) => {
      if (busy) return;
      renderUserMessage(label);
      history.push({ role: 'user', text: label });
      showWelcome(false);
      robots.header && robots.header.hop();
      respond(intent, paramKey);
    };

    // ---- Preguntas a la IA real -------------------------------------------
    const remoteEnabled = Boolean(safeHref(GLOBAL.url_preguntar) && GLOBAL.ia_disponible);

    const csrfToken = () => {
      const field = ui.form && ui.form.querySelector('[name="csrfmiddlewaretoken"]');
      return field ? field.value : '';
    };

    /**
     * Envía la pregunta al backend.
     * @param {string} question
     * @returns {Promise<Object>} data de la respuesta
     */
    const fetchAnswer = async (question) => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), CONFIG.askTimeoutMs);
      try {
        const response = await fetch(GLOBAL.url_preguntar, {
          method: 'POST',
          credentials: 'same-origin',
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({ pregunta: question }),
        });
        let payload = null;
        try { payload = await response.json(); } catch (error) { payload = null; }
        if (!response.ok || !payload || !payload.success) {
          const fallback = response.status >= 500 ? 'el servidor tuvo un problema.' : `error ${response.status}.`;
          const failure = new Error((payload && payload.message) || fallback);
          failure.status = response.status;
          throw failure;
        }
        return payload.data;
      } catch (error) {
        if (error.name === 'AbortError') {
          const timeout = new Error('La IA tardó demasiado en responder.');
          timeout.status = 504;
          throw timeout;
        }
        throw error;
      } finally {
        clearTimeout(timer);
      }
    };

    /** Convierte la respuesta del backend en un mensaje del chat. */
    const toRemoteMessage = (answer) => ({
      tone: toneFromFindings(answer.hallazgos),
      tag: 'IA · datos del sistema',
      text: answer.respuesta || '',
      rich: {
        findings: answer.hallazgos || [],
        tables: answer.tablas || [],
        recommendations: answer.recomendaciones || [],
        links: answer.enlaces || [],
        excel: answer.url_excel,
        model: answer.modelo,
        notice: answer.aviso || '',
      },
    });

    /**
     * Pregunta a la IA; si falla, responde con las reglas locales.
     * @param {string} question - texto que se envía a la IA
     * @param {string} intent - intención local de respaldo
     * @param {string} [paramKey]
     */
    const respondRemote = async (question, intent, paramKey) => {
      setBusy(true);
      everyRobot((r) => r.setFace(FACE.THINK));
      const steps = ['Revisando piscinas y sensores…', 'Leyendo alertas y reportes…', 'Consultando a la IA…', 'Armando la respuesta…'];
      let step = 0;
      setStatus(steps[0]);
      const ticker = setInterval(() => { step = Math.min(step + 1, steps.length - 1); setStatus(steps[step]); }, 2500);
      const dots = showTyping();
      let messages;
      try {
        messages = [toRemoteMessage(await fetchAnswer(question))];
      } catch (error) {
        console.warn('[Agente IA] La IA no respondió:', error.message);
        const userError = [400, 401, 403, 429].includes(error.status);
        const canFallback = !userError && intent !== 'ayuda';
        let text = error.message;
        if (!userError) {
          text = canFallback
            ? `No pude consultar la IA: ${error.message} Te respondo con lo que tengo a mano:`
            : `No pude consultar la IA: ${error.message} Inténtalo de nuevo en un momento.`;
        }
        messages = [{ tone: 'aviso', text }];
        if (canFallback) {
          try { messages.push(...buildMessages(intent, collectModuleData(), paramKey)); } catch (e) { /* sin datos locales */ }
        }
      } finally {
        clearInterval(ticker);
        dots.remove();
      }
      return speak(messages);
    };

    const askRemote = (label, intent, paramKey, question) => {
      if (busy) return;
      renderUserMessage(label);
      history.push({ role: 'user', text: label });
      showWelcome(false);
      robots.header && robots.header.hop();
      respondRemote(question || label, intent, paramKey);
    };

    // ---- Limpiar chat ---------------------------------------------------
    const clearChat = async () => {
      if (busy) return;
      setBusy(true);
      const bubbles = [...ui.log.children];
      bubbles.forEach((el, i) => {
        el.style.transitionDelay = `${Math.min(i * 30, 300)}ms`;
        el.classList.add('is-leaving');
      });
      everyRobot((r) => r.spin());
      await wait(bubbles.length ? 420 : 0);
      ui.log.replaceChildren();
      history = [];
      storage.clear();
      showWelcome(true);
      robots.welcome && robots.welcome.wave();
      setBusy(false);
      ui.input && ui.input.focus();
    };

    // ---- Restaurar sesión -----------------------------------------------
    const saved = storage.read();
    const signature = analysisSignature(data.analysis);
    let greetIntent = 'bienvenida';
    if (saved && Array.isArray(saved.messages) && saved.messages.length) {
      history = saved.messages;
      history.forEach((msg) => {
        if (msg.role === 'user') renderUserMessage(msg.text);
        else renderAgentMessage(msg, false);
      });
      showWelcome(false);
      greetIntent = saved.signature !== signature ? 'cambio' : null;
    } else {
      showWelcome(true);
    }

    // ---- Abrir / cerrar ---------------------------------------------------
    let greeted = false;
    const open = () => {
      hideTeaser();
      agent.classList.add('is-open');
      ui.panel.setAttribute('aria-hidden', 'false');
      ui.trigger.setAttribute('aria-expanded', 'true');
      if (ui.badge) ui.badge.hidden = true;
      wake();
      everyRobot((r) => r.wave());
      if (!greeted && greetIntent) {
        greeted = true;
        setTimeout(() => respond(greetIntent), reducedMotion ? 0 : 500);
      }
      greeted = true;
      setTimeout(() => ui.input && ui.input.focus({ preventScroll: true }), 320);
    };

    const close = () => {
      agent.classList.remove('is-open');
      ui.panel.setAttribute('aria-hidden', 'true');
      ui.trigger.setAttribute('aria-expanded', 'false');
      robots.trigger && robots.trigger.hop();
    };

    ui.trigger.addEventListener('click', () => (agent.classList.contains('is-open') ? close() : open()));
    ui.trigger.addEventListener('mouseenter', () => robots.trigger && robots.trigger.wave());
    ui.close.addEventListener('click', () => { close(); ui.trigger.focus(); });
    ui.clear.addEventListener('click', clearChat);
    if (ui.teaser) {
      ui.teaser.addEventListener('click', (event) => {
        if (event.target.closest('[data-agent-teaser-close]')) hideTeaser();
        else open();
      });
    }

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && agent.classList.contains('is-open')) {
        close();
        ui.trigger.focus();
      }
    });

    // La rueda del mouse desplaza la fila de chips en horizontal.
    const chipsRow = agent.querySelector('.ia-agent__chips');
    if (chipsRow) {
      chipsRow.addEventListener('wheel', (event) => {
        if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
        event.preventDefault();
        chipsRow.scrollLeft += event.deltaY;
      }, { passive: false });
    }

    agent.querySelectorAll('[data-agent-intent]').forEach((chip) => {
      chip.addEventListener('click', () => {
        const intent = chip.dataset.agentIntent;
        if (remoteEnabled && INTENT_PROMPTS[intent]) askRemote(chip.textContent.trim(), intent, undefined, INTENT_PROMPTS[intent]);
        else ask(chip.textContent.trim(), intent);
      });
    });

    if (ui.form && ui.input) {
      ui.form.addEventListener('submit', (event) => {
        event.preventDefault();
        const query = ui.input.value.trim();
        if (!query || busy) return;
        ui.input.value = '';
        const { intent, paramKey } = resolveQuery(query);
        if (remoteEnabled && !['saludo', 'gracias'].includes(intent)) askRemote(query, intent, paramKey);
        else ask(query, intent, paramKey);
      });
    }

    // ---- Mirada, sueño y despertar ----------------------------------------
    let sleepTimer = null;
    let asleep = false;

    function wake() {
      clearTimeout(sleepTimer);
      if (asleep) {
        asleep = false;
        agent.classList.remove('is-sleeping');
        everyRobot((r) => { r.restoreMood(); r.hop(); });
      }
      if (!reducedMotion) {
        sleepTimer = setTimeout(() => {
          if (agent.classList.contains('is-open')) return;
          asleep = true;
          agent.classList.add('is-sleeping');
          everyRobot((r) => r.setFace(FACE.SLEEP));
        }, CONFIG.sleepAfterMs);
      }
    }

    if (!reducedMotion) {
      let frame = null;
      let pointer = null;
      window.addEventListener('pointermove', (event) => {
        pointer = { x: event.clientX, y: event.clientY };
        if (frame) return;
        frame = requestAnimationFrame(() => {
          frame = null;
          wake();
          everyRobot((r) => r.lookAt(pointer.x, pointer.y));
        });
      }, { passive: true });
      document.addEventListener('mouseleave', () => everyRobot((r) => r.resetLook()));
      wake();
    }

    // El globo de aviso aparece una sola vez por sesión del navegador.
    let teaserShown = false;
    try { teaserShown = sessionStorage.getItem(`${CONFIG.storageKey}_teaser`) === '1'; } catch (error) { /* sin acción */ }
    if (!teaserShown) {
      setTimeout(showTeaser, CONFIG.teaserDelayMs);
      try { sessionStorage.setItem(`${CONFIG.storageKey}_teaser`, '1'); } catch (error) { /* sin acción */ }
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAgent);
  else initAgent();
})();
