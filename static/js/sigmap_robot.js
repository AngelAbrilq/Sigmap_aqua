/**
 * SIGMAP-AQUA · Robot SigmaP Aqua en SVG.
 * Archivo: static/js/sigmap_robot.js
 *
 * Lo usan el asistente IA flotante (ia_agente.js) y las pantallas de acceso
 * por QR. Expone window.SigmapRobot = { FACE, buildRobotSvg, Robot, mount }.
 */
(() => {
  'use strict';

  const BLINK_MIN_MS = 2600;
  const BLINK_MAX_MS = 5200;

  /** Expresiones disponibles del robot. */
  const FACE = Object.freeze({
    HAPPY: 'happy',
    OPEN: 'open',
    WARN: 'warn',
    ALERT: 'alert',
    THINK: 'think',
    SLEEP: 'sleep',
  });

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const randomBetween = (min, max) => min + Math.random() * (max - min);

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
      }, randomBetween(BLINK_MIN_MS, BLINK_MAX_MS));
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

  /**
   * Dibuja un robot dentro de un contenedor y devuelve su controlador.
   * @param {Element} host
   * @param {{variant?: 'full'|'bust'|'head', face?: string}} [options]
   * @returns {Robot|null}
   */
  function mount(host, { variant = 'full', face } = {}) {
    if (!host) return null;
    const uid = `rb-${variant}-${Math.random().toString(36).slice(2, 7)}`;
    host.innerHTML = buildRobotSvg(uid, { variant });
    const robot = new Robot(host.querySelector('svg'));
    if (face) robot.setMood(face);
    return robot;
  }

  window.SigmapRobot = Object.freeze({ FACE, buildRobotSvg, Robot, mount });
})();
