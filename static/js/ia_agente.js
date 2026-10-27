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
 * - No llama endpoints nuevos.
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
    sleepAfterMs: 45000,
    teaserDelayMs: 1600,
    teaserDurationMs: 6500,
    storageKey: 'sigmap_ia_chat_v1',
    maxStoredMessages: 60,
  });

  // El robot vive en static/js/sigmap_robot.js (también lo usan las
  // pantallas de acceso por QR). Debe cargarse antes que este archivo.
  const { FACE, buildRobotSvg, Robot } = window.SigmapRobot || {};
  if (!buildRobotSvg) {
    console.error('[Agente IA] Falta static/js/sigmap_robot.js');
    return;
  }

  const PARAM_ALIASES = Object.freeze({
    ph: ['ph', 'acidez', 'acido'],
    turbidez: ['turbidez', 'turbio', 'ntu', 'solidos'],
    temperatura: ['temperatura', 'temp', 'calor', 'frio', 'termic'],
    oxigeno: ['oxigeno', 'od', 'disuelto'],
  });

  /** Bienvenida guiada tras entrar con un QR de demostración (apps/demo). */
  const TOUR_KEY = 'sigmap_demo_tour';
  const TOUR = Object.freeze({
    instructor: {
      tag: 'Acceso por QR · Instructor Líder',
      text: '¡Bienvenido! Entraste con **un escaneo y sin contraseña**: el QR lleva un token firmado por el servidor que vence solo. Como **Instructor Líder** tienes control total: validas los análisis de IA, gestionas usuarios, piscinas y sensores, y revisas la auditoría.',
      link: 'module',
      label: 'Ver el análisis predictivo →',
    },
    operario: {
      tag: 'Acceso por QR · Operario',
      text: '¡Bienvenido! Entraste con **un escaneo y sin contraseña**. Como **Operario** trabajas en campo: monitoreo del agua en tiempo real, alertas de los sensores y análisis con IA.',
      link: 'alerts',
      label: 'Revisar alertas →',
    },
    aprendiz: {
      tag: 'Acceso por QR · Aprendiz',
      text: '¡Bienvenido! Entraste con **un escaneo y sin contraseña**. Como **Aprendiz** estás en modo consulta: gráficas, historial y comparación de periodos, sin modificar datos.',
      link: 'module',
      label: 'Ver el análisis predictivo →',
    },
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
      case 'tour': {
        const guia = TOUR[paramKey];
        const intro = guia
          ? [{ tag: guia.tag, tone: 'ok', text: guia.text, link: { href: data.links[guia.link], label: guia.label } }]
          : [];
        return [...intro, ...buildIntentMessages('bienvenida', data)];
      }

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
    if (/resumen|estado|general|como va/.test(q)) return { intent: 'resumen' };
    if (/alertas|sensor|alarma/.test(q)) return { intent: 'alertas' };
    if (/anomal|alerta|riesgo|problema/.test(q)) return { intent: 'anomalias' };
    if (/recomend|hacer|hoy|accion|consejo/.test(q)) return { intent: 'recomendacion' };
    if (/pendient|vencid|contrast/.test(q)) return { intent: 'pendientes' };
    return { intent: 'ayuda' };
  }

  /** Divide "**negrita**" en segmentos seguros (sin innerHTML). */
  const toSegments = (text) => text.split(/\*\*/).map((part, i) => ({ text: part, bold: i % 2 === 1 })).filter((s) => s.text);

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
      input: agent.querySelector('[data-agent-form] input'),
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

    // ---- Tour tras entrar por QR de demostración ---------------------------
    let tourSlug = '';
    try {
      tourSlug = sessionStorage.getItem(TOUR_KEY) || '';
      if (tourSlug) sessionStorage.removeItem(TOUR_KEY);
    } catch (error) { /* almacenamiento bloqueado: sin tour */ }
    if (TOUR[tourSlug]) greetIntent = 'tour';

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
        setTimeout(() => respond(greetIntent, greetIntent === 'tour' ? tourSlug : undefined), reducedMotion ? 0 : 500);
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
      chip.addEventListener('click', () => ask(chip.textContent.trim(), chip.dataset.agentIntent));
    });

    if (ui.form && ui.input) {
      ui.form.addEventListener('submit', (event) => {
        event.preventDefault();
        const query = ui.input.value.trim();
        if (!query || busy) return;
        ui.input.value = '';
        const { intent, paramKey } = resolveQuery(query);
        ask(query, intent, paramKey);
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

    // Recién llegado por QR: el asistente se presenta solo.
    if (greetIntent === 'tour') {
      setTimeout(open, reducedMotion ? 0 : 1300);
      return;
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
