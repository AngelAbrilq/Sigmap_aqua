/**
 * SIGMAP-AQUA · Comportamiento responsive global.
 * Archivo: static/js/responsive.js (se carga desde base.html)
 *
 * 1. Menú en celular: inserta el botón ☰ en el encabezado y convierte la
 *    barra lateral en un drawer (tocar fuera, Esc, deslizar o elegir una
 *    opción lo cierra; deslizar desde el borde izquierdo lo abre).
 * 2. Tablas: rotula cada celda con su encabezado (data-label) para que
 *    responsive.css las muestre como tarjetas en pantallas pequeñas, y
 *    envuelve en un contenedor deslizable las que no lo tengan.
 *    Una tabla con data-r-sin-tarjetas se deja como tabla deslizable.
 */
(() => {
  'use strict';

  const MOVIL = window.matchMedia('(max-width: 767px)');
  const MIN_COLUMNAS_TARJETA = 4;
  const SWIPE_MIN_PX = 60;
  const BORDE_SWIPE_PX = 24;
  const PATRON_ANCHA = /mensaje|descrip|justific|detalle|observ|recomend|direcci|ubicaci|correo|email/i;
  const SELECTOR_ACCIONES = 'form, button, .sg-btn, .sg-acciones';

  /* ====================================================================
     1. Menú lateral como drawer
     ==================================================================== */
  function iniciarMenu() {
    const sidebar = document.querySelector('.sidebar');
    const header = document.querySelector('.top-header');
    if (!sidebar || !header) return;

    if (!sidebar.id) sidebar.id = 'menuPrincipal';

    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'r-menu-btn';
    boton.setAttribute('aria-label', 'Abrir menú');
    boton.setAttribute('aria-controls', sidebar.id);
    boton.setAttribute('aria-expanded', 'false');
    boton.innerHTML =
      '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2.2" stroke-linecap="round" aria-hidden="true">' +
      '<line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/>' +
      '<line x1="4" y1="17" x2="14" y2="17"/></svg>';
    header.prepend(boton);

    const fondo = document.createElement('div');
    fondo.className = 'r-menu-fondo';
    fondo.setAttribute('aria-hidden', 'true');
    document.body.appendChild(fondo);

    const abierto = () => document.body.classList.contains('r-menu-abierto');

    const abrir = () => {
      if (!MOVIL.matches || abierto()) return;
      document.body.classList.add('r-menu-abierto');
      boton.setAttribute('aria-expanded', 'true');
      boton.setAttribute('aria-label', 'Cerrar menú');
      const activo = sidebar.querySelector('.nav-item.active') || sidebar.querySelector('.nav-item');
      if (activo) setTimeout(() => activo.focus({ preventScroll: true }), 120);
    };

    const cerrar = ({ devolverFoco = false } = {}) => {
      if (!abierto()) return;
      document.body.classList.remove('r-menu-abierto');
      boton.setAttribute('aria-expanded', 'false');
      boton.setAttribute('aria-label', 'Abrir menú');
      if (devolverFoco) boton.focus({ preventScroll: true });
    };

    boton.addEventListener('click', () => (abierto() ? cerrar() : abrir()));
    fondo.addEventListener('click', () => cerrar());

    document.addEventListener('keydown', (evento) => {
      if (evento.key === 'Escape' && abierto()) cerrar({ devolverFoco: true });
    });

    // Elegir una opción cierra el menú (la navegación sigue normal)
    sidebar.addEventListener('click', (evento) => {
      if (evento.target.closest('a.nav-item')) cerrar();
    });

    // Al pasar a tablet/escritorio el drawer deja de existir
    const alCambiar = () => { if (!MOVIL.matches) cerrar(); };
    if (MOVIL.addEventListener) MOVIL.addEventListener('change', alCambiar);
    else MOVIL.addListener(alCambiar);

    // Gestos: deslizar desde el borde izquierdo abre; hacia la izquierda cierra
    let inicioX = null;
    let inicioY = null;
    document.addEventListener('touchstart', (evento) => {
      if (!MOVIL.matches || evento.touches.length !== 1) return;
      const toque = evento.touches[0];
      const desdeBorde = toque.clientX <= BORDE_SWIPE_PX;
      if (abierto() || desdeBorde) {
        inicioX = toque.clientX;
        inicioY = toque.clientY;
      }
    }, { passive: true });

    document.addEventListener('touchend', (evento) => {
      if (inicioX === null) return;
      const toque = evento.changedTouches[0];
      const dx = toque.clientX - inicioX;
      const dy = Math.abs(toque.clientY - inicioY);
      inicioX = null;
      if (dy > Math.abs(dx)) return; // era scroll vertical
      if (!abierto() && dx > SWIPE_MIN_PX) abrir();
      else if (abierto() && dx < -SWIPE_MIN_PX) cerrar();
    }, { passive: true });
  }

  /* ====================================================================
     2. Tablas: rótulos para vista de tarjetas + contenedor deslizable
     ==================================================================== */

  /** Texto limpio del encabezado de cada columna. */
  const encabezados = (tabla) => {
    const fila = tabla.tHead && tabla.tHead.rows[tabla.tHead.rows.length - 1];
    if (!fila) return [];
    const titulos = [];
    [...fila.cells].forEach((celda) => {
      const texto = celda.textContent.replace(/\s+/g, ' ').trim();
      const span = Number(celda.colSpan) || 1;
      for (let i = 0; i < span; i += 1) titulos.push(texto);
    });
    return titulos;
  };

  /**
   * Rotula las celdas de una tabla. Idempotente: se puede llamar de nuevo
   * cuando la tabla cambia (monitoreo en vivo, filtros por JS).
   * @param {HTMLTableElement} tabla
   */
  function rotularTabla(tabla) {
    const titulos = encabezados(tabla);
    if (titulos.length < MIN_COLUMNAS_TARJETA || tabla.hasAttribute('data-r-sin-tarjetas')) return;

    tabla.classList.add('r-tabla-cards');
    [...tabla.tBodies].forEach((cuerpo) => {
      [...cuerpo.rows].forEach((fila) => {
        let columna = 0;
        [...fila.cells].forEach((celda) => {
          const titulo = titulos[columna] || '';
          if (celda.getAttribute('data-label') !== titulo) celda.setAttribute('data-label', titulo);
          celda.classList.toggle('r-celda-ancha', PATRON_ANCHA.test(titulo));
          celda.classList.toggle('r-celda-acciones', Boolean(celda.querySelector(SELECTOR_ACCIONES)));
          columna += Number(celda.colSpan) || 1;
        });
      });
    });
  }

  /** Número de columnas de la tabla (por encabezado o por su primera fila). */
  const columnas = (tabla) => {
    const titulos = encabezados(tabla);
    if (titulos.length) return titulos.length;
    const fila = tabla.rows[0];
    return fila ? [...fila.cells].reduce((n, c) => n + (Number(c.colSpan) || 1), 0) : 0;
  };

  /**
   * Envuelve tablas anchas sueltas para que se deslicen dentro de su tarjeta.
   * Las tablas chicas de "campo → valor" (fichas de detalle) no lo necesitan
   * y suelen vivir en filas flex junto a otros elementos.
   */
  function envolverTabla(tabla) {
    if (columnas(tabla) < MIN_COLUMNAS_TARJETA) return;
    let padre = tabla.parentElement;
    while (padre && padre !== document.body) {
      const overflow = getComputedStyle(padre).overflowX;
      if (overflow === 'auto' || overflow === 'scroll') return;
      if (padre.classList.contains('dashboard-content')) break;
      padre = padre.parentElement;
    }
    const contenedor = document.createElement('div');
    contenedor.className = 'r-tabla-scroll';
    tabla.parentNode.insertBefore(contenedor, tabla);
    contenedor.appendChild(tabla);
  }

  function procesarTablas(raiz = document) {
    raiz.querySelectorAll('.dashboard-content table').forEach((tabla) => {
      try {
        if (!tabla.dataset.rListo) {
          envolverTabla(tabla);
          tabla.dataset.rListo = '1';
        }
        rotularTabla(tabla);
      } catch (error) {
        console.error('[Responsive] No se pudo adaptar una tabla:', error);
      }
    });
  }

  function observarCambios() {
    const contenido = document.querySelector('.dashboard-content');
    if (!contenido || !window.MutationObserver) return;
    let pendiente = null;
    const observador = new MutationObserver((cambios) => {
      if (!cambios.some((c) => c.addedNodes.length)) return;
      clearTimeout(pendiente);
      pendiente = setTimeout(() => procesarTablas(contenido), 120);
    });
    observador.observe(contenido, { childList: true, subtree: true });
  }

  function iniciar() {
    iniciarMenu();
    procesarTablas();
    observarCambios();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
