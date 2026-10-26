/**
 * SIGMAP-AQUA · Agente IA flotante del módulo "IA - Análisis predictivo".
 * Archivo: static/js/ia_agente.js
 *
 * No llama endpoints nuevos: todo lo que dice el agente se lee del DOM que
 * ya renderiza la vista /ai/ (KPIs, predicciones pendientes, análisis
 * seleccionado, anomalías, recomendaciones y riesgo proyectado).
 */
(() => {
  'use strict';

  const TYPING_DELAY_MS = 550;
  const MAX_TYPE_DURATION_MS = 900;
  const PARAM_ALIASES = {
    ph: ['ph', 'acidez', 'acido'],
    turbidez: ['turbidez', 'turbio', 'ntu', 'solidos'],
    temperatura: ['temperatura', 'temp', 'calor', 'frio', 'termic'],
    oxigeno: ['oxigeno', 'od', 'disuelto'],
  };

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /** @param {string} value */
  const normalize = (value) =>
    (value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim();

  /** @param {Element|null} el */
  const textOf = (el) => (el ? el.textContent.replace(/\s+/g, ' ').trim() : '');

  /** Texto propio de un elemento sin el de sus hijos (ej. "7.0 – 7.4" sin el <small>). */
  const ownText = (el) =>
    el ? [...el.childNodes].filter((n) => n.nodeType === Node.TEXT_NODE).map((n) => n.textContent).join(' ').replace(/\s+/g, ' ').trim() : '';

  /** Primeras N oraciones de un texto largo. */
  const firstSentences = (text, count = 2) => {
    const parts = text.match(/[^.!?]+[.!?]+/g);
    return parts ? parts.slice(0, count).join(' ').trim() : text;
  };

  /**
   * Busca el bloque que sigue a un <h3> cuyo texto contenga `title`.
   * @param {Element} scope
   * @param {string} title
   * @returns {Element|null}
   */
  const blockAfterHeading = (scope, title) => {
    const heading = [...scope.querySelectorAll('h3')].find((h) => normalize(h.textContent).includes(normalize(title)));
    return heading ? heading.nextElementSibling : null;
  };

  /**
   * Recolecta los datos que ya muestra el módulo IA.
   * @returns {{kpis: Object, pending: Array, analysis: Object|null, poolOptions: string}}
   */
  function collectModuleData() {
    const root = document.querySelector('.sg-modulo') || document;

    const kpis = {};
    root.querySelectorAll('.sg-kpi').forEach((card) => {
      const key = normalize(textOf(card.querySelector('.sg-kpi-label')));
      kpis[key] = {
        value: textOf(card.querySelector('.sg-kpi-valor')),
        sub: textOf(card.querySelector('.sg-kpi-sub')),
      };
    });

    const pending = [...root.querySelectorAll('[data-panel="pendientes"] tbody tr')].map((row) => {
      const cells = row.cells;
      return {
        param: textOf(cells[0]),
        targetDay: ownText(cells[1]),
        interval: ownText(cells[2]),
        expected: textOf(cells[2] && cells[2].querySelector('small')),
        probability: parseFloat(textOf(cells[3])) || 0,
        reason: textOf(cells[4]),
        status: textOf(cells[5]),
      };
    }).filter((p) => p.param);

    const detailCard = root.querySelector('.sg-split > .sg-card');
    let analysis = null;

    if (detailCard && detailCard.querySelector('.sg-card-body h3')) {
      const body = detailCard.querySelector('.sg-card-body');
      const title = detailCard.querySelector('.sg-card-head h2');
      const diagnosis = blockAfterHeading(body, 'Diagnóstico');
      const anomaliesBlock = blockAfterHeading(body, 'Anomalías');
      const recsBlock = blockAfterHeading(body, 'Recomendaciones');

      analysis = {
        type: ownText(title),
        confidence: textOf(title && title.querySelector('.sg-chip')),
        pool: textOf(body.querySelector('.sg-alerta strong')),
        meta: textOf(body.querySelector('.sg-alerta')),
        diagnosis: diagnosis && diagnosis.tagName === 'P' ? textOf(diagnosis) : '',
        anomalies: anomaliesBlock
          ? [...anomaliesBlock.querySelectorAll('tbody tr')].map((row) => ({
              param: textOf(row.cells[0]),
              description: textOf(row.cells[1]),
              severity: textOf(row.cells[2]),
            }))
          : [],
        recommendations: recsBlock ? [...recsBlock.querySelectorAll('li')].map(textOf) : [],
        risk: textOf(body.querySelector('.sg-metrica-valor')),
      };
    }

    return { kpis, pending, analysis };
  }

  /** @param {string} severity */
  const toneFromLevel = (severity) => {
    const level = normalize(severity);
    if (level.startsWith('alt') || level.startsWith('crit')) return 'alerta';
    if (level.startsWith('med')) return 'aviso';
    if (level.startsWith('baj')) return 'ok';
    return 'info';
  };

  /** Coincide un nombre de parámetro con una clave de PARAM_ALIASES. */
  const matchParam = (paramName, key) =>
    PARAM_ALIASES[key].some((alias) => normalize(paramName).replace(/\s/g, '').includes(alias.replace(/\s/g, '')));

  /**
   * Genera los mensajes del agente según la intención.
   * @param {string} intent
   * @param {ReturnType<typeof collectModuleData>} data
   * @param {string} [paramKey]
   * @returns {Array<{tag?: string, text: string, tone: string}>}
   */
  function buildMessages(intent, data, paramKey) {
    const { kpis, pending, analysis } = data;
    const overdue = pending.filter((p) => normalize(p.status).includes('vencid'));
    const highAnomalies = analysis ? analysis.anomalies.filter((a) => toneFromLevel(a.severity) === 'alerta') : [];
    const noAnalysis = {
      tone: 'info',
      text: 'Aún no hay un análisis seleccionado. Usa **Generar análisis** a la izquierda para que pueda leer el estado de una piscina.',
    };

    switch (intent) {
      case 'bienvenida': {
        const msgs = [{
          tone: 'info',
          text: '¡Hola! Soy el **Asistente IA de SigmaP Aqua**. Vigilo las predicciones de pH, temperatura, turbidez y oxígeno de tus piscinas.',
        }];
        if (analysis) {
          msgs.push({
            tag: analysis.pool || 'Estado actual',
            tone: toneFromLevel(analysis.risk),
            text: `Riesgo proyectado: **${analysis.risk || 'sin dato'}**. Detecté **${analysis.anomalies.length}** anomalía(s), ${highAnomalies.length} de gravedad alta.`,
          });
        } else {
          msgs.push(noAnalysis);
        }
        if (overdue.length) {
          msgs.push({
            tone: 'aviso',
            text: `Tienes **${overdue.length} predicción(es) vencida(s)** listas para contrastar con los sensores.`,
          });
        }
        return msgs;
      }

      case 'resumen': {
        const precision = kpis['precision del modelo'];
        const hits = kpis.acertadas;
        const msgs = [{
          tag: 'Modelo predictivo',
          tone: 'info',
          text: `Precisión: **${precision ? precision.value : '—'}** (${precision ? precision.sub : 'sin dato'}). Acertadas: **${hits ? hits.value : '0'}** · ${hits ? hits.sub : ''}. Pendientes: **${pending.length}**.`,
        }];
        if (analysis) {
          msgs.push({
            tag: `${analysis.type} · ${analysis.confidence}`,
            tone: toneFromLevel(analysis.risk),
            text: firstSentences(analysis.diagnosis, 2) || 'El análisis no trae texto de diagnóstico.',
          });
          msgs.push({ tone: toneFromLevel(analysis.risk), text: `Riesgo proyectado para **${analysis.pool}**: **${analysis.risk}**.` });
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
        if (rest.length) {
          msgs.push({ tag: 'También conviene', tone: 'info', text: rest.map((r) => `• ${r}`).join('\n') });
        }
        return msgs;
      }

      case 'pendientes': {
        if (!pending.length) {
          return [{ tone: 'ok', text: 'No hay predicciones pendientes. Genera una **Predicción de riesgo** para empezar a medir el acierto del modelo.' }];
        }
        const msgs = [{
          tag: `${pending.length} predicción(es) en seguimiento`,
          tone: 'info',
          text: pending.map((p) => `• **${p.param}** → ${p.interval} (${p.status}, ${p.targetDay})`).join('\n'),
        }];
        if (overdue.length) {
          msgs.push({ tone: 'aviso', text: `Pulsa **Contrastar ${overdue.length} vencida(s)** en "Seguimiento de predicciones" para calcular el acierto real.` });
        }
        return msgs;
      }

      case 'parametro': {
        const label = { ph: 'pH', turbidez: 'Turbidez', temperatura: 'Temperatura', oxigeno: 'Oxígeno disuelto' }[paramKey];
        const anomaly = analysis && analysis.anomalies.find((a) => matchParam(a.param, paramKey));
        const prediction = pending.find((p) => matchParam(p.param, paramKey));
        const msgs = [];
        if (anomaly) msgs.push({ tag: `${label} · gravedad ${anomaly.severity}`, tone: toneFromLevel(anomaly.severity), text: anomaly.description });
        if (prediction) {
          msgs.push({
            tag: `Predicción de ${label}`,
            tone: prediction.probability >= 70 ? 'aviso' : 'info',
            text: `Intervalo previsto **${prediction.interval}** (${prediction.expected}) para el ${prediction.targetDay}. Probabilidad fuera de rango: **${prediction.probability}%**.\n${prediction.reason}`,
          });
        }
        if (!msgs.length) msgs.push({ tone: 'ok', text: `No tengo alertas ni predicciones activas de **${label}** en este momento.` });
        return msgs;
      }

      default:
        return [{
          tone: 'info',
          text: 'Puedo hablarte de **pH**, **turbidez**, **temperatura** u **oxígeno**, o usa los botones rápidos de abajo.',
        }];
    }
  }

  /** Detecta la intención a partir de la consulta escrita. */
  function resolveQuery(query) {
    const q = normalize(query);
    const paramKey = Object.keys(PARAM_ALIASES).find((key) => PARAM_ALIASES[key].some((alias) => q.split(/\W+/).some((w) => w.startsWith(alias))));
    if (paramKey) return { intent: 'parametro', paramKey };
    if (/resumen|estado|general|como va/.test(q)) return { intent: 'resumen' };
    if (/anomal|alerta|riesgo|problema/.test(q)) return { intent: 'anomalias' };
    if (/recomend|hacer|hoy|accion|consejo/.test(q)) return { intent: 'recomendacion' };
    if (/pendient|vencid|contrast/.test(q)) return { intent: 'pendientes' };
    return { intent: 'ayuda' };
  }

  /** Convierte "**negrita**" en segmentos seguros (sin innerHTML). */
  const toSegments = (text) => text.split(/\*\*/).map((part, i) => ({ text: part, bold: i % 2 === 1 })).filter((s) => s.text);

  function initAgent() {
    const agent = document.querySelector('[data-agent]');
    if (!agent) return;

    const trigger = agent.querySelector('[data-agent-toggle]');
    const panel = agent.querySelector('.ia-agent__panel');
    const body = agent.querySelector('.ia-agent__body');
    const badge = agent.querySelector('[data-agent-badge]');
    const form = agent.querySelector('[data-agent-form]');
    const input = form ? form.querySelector('input') : null;
    const controls = agent.querySelectorAll('[data-agent-intent], .ia-agent__send');

    let busy = false;
    let greeted = false;

    // Avatar de respaldo si la imagen no carga
    agent.querySelectorAll('[data-agent-img]').forEach((img) => {
      const useFallback = () => img.closest('[data-agent-avatar]').classList.add('is-fallback');
      if (!img.getAttribute('src')) useFallback();
      else if (img.complete && img.naturalWidth === 0) useFallback();
      img.addEventListener('error', useFallback, { once: true });
    });

    // Badge: anomalías de gravedad alta del análisis actual
    try {
      const data = collectModuleData();
      const high = data.analysis ? data.analysis.anomalies.filter((a) => toneFromLevel(a.severity) === 'alerta').length : 0;
      if (badge && high > 0) {
        badge.textContent = String(high);
        badge.hidden = false;
        trigger.setAttribute('aria-label', `Abrir Asistente IA de SigmaP Aqua (${high} anomalías altas)`);
      }
    } catch (error) {
      console.error('[Agente IA] No se pudieron leer los datos del módulo:', error);
    }

    const scrollToEnd = () => { body.scrollTop = body.scrollHeight; };
    const setBusy = (value) => {
      busy = value;
      controls.forEach((c) => { c.disabled = value; });
    };

    /** Escribe un mensaje con efecto de tecleo. */
    const typeMessage = (msg) => new Promise((resolve) => {
      const bubble = document.createElement('div');
      bubble.className = `ia-msg ia-msg--${msg.tone || 'info'}`;
      if (msg.tag) {
        const tag = document.createElement('span');
        tag.className = 'ia-msg__tag';
        tag.textContent = msg.tag;
        bubble.append(tag, document.createElement('br'));
      }
      const segments = toSegments(msg.text).map((seg) => {
        const node = seg.bold ? document.createElement('strong') : document.createTextNode('');
        bubble.appendChild(node);
        return { node, text: seg.text };
      });
      body.appendChild(bubble);

      const total = segments.reduce((n, s) => n + s.text.length, 0);
      if (prefersReducedMotion || total === 0) {
        segments.forEach((s) => { s.node.textContent = s.text; });
        scrollToEnd();
        resolve();
        return;
      }

      const start = performance.now();
      const duration = Math.min(MAX_TYPE_DURATION_MS, total * 14);
      const step = (now) => {
        let budget = Math.ceil(total * Math.min(1, (now - start) / duration));
        segments.forEach((s) => {
          const take = Math.max(0, Math.min(s.text.length, budget));
          s.node.textContent = s.text.slice(0, take);
          budget -= take;
        });
        scrollToEnd();
        if (now - start < duration) requestAnimationFrame(step);
        else resolve();
      };
      requestAnimationFrame(step);
    });

    const showTyping = () => {
      const dots = document.createElement('div');
      dots.className = 'ia-typing';
      dots.setAttribute('aria-label', 'El asistente está escribiendo');
      dots.innerHTML = '<span></span><span></span><span></span>';
      body.appendChild(dots);
      scrollToEnd();
      return dots;
    };

    /** Reproduce una secuencia de mensajes del agente. */
    const speak = async (messages) => {
      setBusy(true);
      try {
        for (const msg of messages) {
          const dots = showTyping();
          await new Promise((r) => setTimeout(r, prefersReducedMotion ? 0 : TYPING_DELAY_MS));
          dots.remove();
          await typeMessage(msg);
        }
      } finally {
        setBusy(false);
      }
    };

    const respond = (intent, paramKey) => {
      let data;
      try {
        data = collectModuleData();
      } catch (error) {
        console.error('[Agente IA] Error leyendo el módulo:', error);
        return speak([{ tone: 'alerta', text: 'No pude leer los datos del módulo. Recarga la página e inténtalo de nuevo.' }]);
      }
      return speak(buildMessages(intent, data, paramKey));
    };

    const addUserBubble = (text) => {
      const bubble = document.createElement('div');
      bubble.className = 'ia-msg ia-msg--user';
      bubble.textContent = text;
      body.appendChild(bubble);
      scrollToEnd();
    };

    const open = () => {
      agent.classList.add('is-open');
      panel.setAttribute('aria-hidden', 'false');
      trigger.setAttribute('aria-expanded', 'true');
      if (badge) badge.hidden = true;
      if (!greeted) {
        greeted = true;
        respond('bienvenida');
      }
    };

    const close = () => {
      agent.classList.remove('is-open');
      panel.setAttribute('aria-hidden', 'true');
      trigger.setAttribute('aria-expanded', 'false');
      trigger.focus();
    };

    trigger.addEventListener('click', () => (agent.classList.contains('is-open') ? close() : open()));
    agent.querySelector('[data-agent-close]').addEventListener('click', close);

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && agent.classList.contains('is-open')) close();
    });

    agent.querySelectorAll('[data-agent-intent]').forEach((chip) => {
      chip.addEventListener('click', () => {
        if (busy) return;
        addUserBubble(chip.textContent.trim());
        respond(chip.dataset.agentIntent);
      });
    });

    if (form && input) {
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        const query = input.value.trim();
        if (!query || busy) return;
        addUserBubble(query);
        input.value = '';
        const { intent, paramKey } = resolveQuery(query);
        respond(intent, paramKey);
      });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAgent);
  else initAgent();
})();
