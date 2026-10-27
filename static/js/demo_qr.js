/**
 * SIGMAP-AQUA · Acceso de demostración por QR.
 * Archivo: static/js/demo_qr.js
 *
 * Una sola entrada para las tres pantallas, según data-dq en <body>:
 *   - "acceso":     animación de verificación y envío automático del POST.
 *   - "invalido":   robot preocupado.
 *   - "presentacion": cuenta regresiva, feed de ingresos en vivo y confeti.
 * Requiere static/js/sigmap_robot.js cargado antes.
 */
(() => {
  'use strict';

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const { mount, FACE } = window.SigmapRobot || {};
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, reducedMotion ? 0 : ms));

  const TOUR_KEY = 'sigmap_demo_tour';
  const CHAT_KEYS = ['sigmap_ia_chat_v1', 'sigmap_ia_chat_v1_teaser'];
  const POLL_MS = 3000;
  const POLL_MAX_MS = 20000;

  /** Burbujas que suben por el fondo. */
  function crearBurbujas(contenedor, cantidad = 14) {
    if (!contenedor || reducedMotion) return;
    for (let i = 0; i < cantidad; i += 1) {
      const burbuja = document.createElement('span');
      const lado = 8 + Math.random() * 26;
      burbuja.className = 'dq-burbuja';
      burbuja.style.width = `${lado}px`;
      burbuja.style.height = `${lado}px`;
      burbuja.style.left = `${Math.random() * 100}%`;
      burbuja.style.animationDuration = `${9 + Math.random() * 10}s`;
      burbuja.style.animationDelay = `${-Math.random() * 18}s`;
      burbuja.style.setProperty('--deriva', `${(Math.random() - 0.5) * 120}px`);
      contenedor.appendChild(burbuja);
    }
  }

  const storage = (accion) => {
    try { return accion(window.sessionStorage); } catch (error) { return null; }
  };

  /* ====================================================================
     1. Acceso: verificación animada y entrada automática
     ==================================================================== */
  async function iniciarAcceso() {
    const robot = mount && mount(document.querySelector('[data-robot]'), { variant: 'full' });
    const form = document.querySelector('[data-form]');
    const boton = form && form.querySelector('button');
    const checks = [...document.querySelectorAll('[data-checks] li')];
    const barra = document.querySelector('[data-progreso]');
    const slug = document.body.dataset.rol || '';
    let enviado = false;

    const entrar = () => {
      if (enviado || !form) return;
      enviado = true;
      // El asistente IA dará un tour del rol al llegar al panel, con el chat limpio.
      storage((s) => {
        CHAT_KEYS.forEach((key) => s.removeItem(key));
        s.setItem(TOUR_KEY, slug);
      });
      if (boton) {
        boton.disabled = true;
        boton.textContent = 'Entrando…';
      }
      if (robot) robot.hop();
      form.submit();
    };

    if (form) {
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        entrar();
      });
    }

    if (robot) setTimeout(() => robot.wave(), 400);

    for (let i = 0; i < checks.length; i += 1) {
      await wait(650);
      checks[i].classList.add('is-ok');
      if (barra) barra.style.width = `${Math.round(((i + 1) / checks.length) * 100)}%`;
    }
    await wait(700);
    entrar();
  }

  /* ====================================================================
     2. QR inválido
     ==================================================================== */
  function iniciarInvalido() {
    if (!mount) return;
    const robot = mount(document.querySelector('[data-robot]'), { variant: 'full', face: FACE.WARN });
    if (robot) setTimeout(() => robot.shake(), 500);
  }

  /* ====================================================================
     3. Presentación: cuenta regresiva + ingresos en vivo
     ==================================================================== */
  function crearConfeti(canvas) {
    if (!canvas || reducedMotion) return () => {};
    const ctx = canvas.getContext('2d');
    let piezas = [];
    let animando = false;

    const ajustar = () => {
      canvas.width = window.innerWidth * window.devicePixelRatio;
      canvas.height = window.innerHeight * window.devicePixelRatio;
    };
    ajustar();
    window.addEventListener('resize', ajustar);

    const cuadro = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      piezas = piezas.filter((p) => p.vida > 0);
      piezas.forEach((p) => {
        p.vy += 0.18 * window.devicePixelRatio;
        p.x += p.vx;
        p.y += p.vy;
        p.giro += p.vgiro;
        p.vida -= 1;
        ctx.save();
        ctx.globalAlpha = Math.min(1, p.vida / 40);
        ctx.translate(p.x, p.y);
        ctx.rotate(p.giro);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.t / 2, -p.t / 4, p.t, p.t / 2);
        ctx.restore();
      });
      if (piezas.length) requestAnimationFrame(cuadro);
      else animando = false;
    };

    /**
     * Lanza confeti desde un punto de la pantalla.
     * @param {number} x - px en la ventana
     * @param {number} y - px en la ventana
     * @param {string[]} colores
     */
    return (x, y, colores) => {
      const dpr = window.devicePixelRatio;
      for (let i = 0; i < 90; i += 1) {
        const angulo = Math.random() * Math.PI * 2;
        const fuerza = (4 + Math.random() * 8) * dpr;
        piezas.push({
          x: x * dpr,
          y: y * dpr,
          vx: Math.cos(angulo) * fuerza,
          vy: Math.sin(angulo) * fuerza - 6 * dpr,
          giro: Math.random() * Math.PI,
          vgiro: (Math.random() - 0.5) * 0.4,
          t: (6 + Math.random() * 6) * dpr,
          vida: 90 + Math.random() * 40,
          color: colores[i % colores.length],
        });
      }
      if (!animando) {
        animando = true;
        requestAnimationFrame(cuadro);
      }
    };
  }

  function iniciarPresentacion() {
    const datosNodo = document.getElementById('dqDatos');
    let datos = {};
    try {
      datos = JSON.parse(datosNodo.textContent);
    } catch (error) {
      console.error('[Demo QR] Datos de la presentación inválidos:', error);
      return;
    }

    const mascota = mount && mount(document.querySelector('[data-robot]'), { variant: 'full' });
    if (mascota) setTimeout(() => mascota.wave(), 600);

    // ---- cuenta regresiva de vigencia ----
    const reloj = document.querySelector('[data-reloj]');
    const expira = new Date(datos.expira).getTime();
    const pintarReloj = () => {
      if (!reloj) return;
      const restante = Math.max(0, expira - Date.now());
      const h = Math.floor(restante / 3600000);
      const m = Math.floor((restante % 3600000) / 60000);
      const s = Math.floor((restante % 60000) / 1000);
      reloj.textContent = restante ? `${h}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s` : 'vencidos';
    };
    pintarReloj();
    setInterval(pintarReloj, 1000);

    // ---- pantalla completa ----
    const botonPantalla = document.querySelector('[data-pantalla-completa]');
    if (botonPantalla) {
      botonPantalla.addEventListener('click', () => {
        if (document.fullscreenElement) document.exitFullscreen();
        else document.documentElement.requestFullscreen().catch(() => {});
      });
    }
    const botonImprimir = document.querySelector('[data-imprimir]');
    if (botonImprimir) botonImprimir.addEventListener('click', () => window.print());

    // ---- feed en vivo ----
    const lanzarConfeti = crearConfeti(document.querySelector('[data-confeti]'));
    const toasts = document.querySelector('[data-toasts]');
    const estado = document.querySelector('[data-en-vivo]');
    let ultimo = Number(datos.ultimo) || 0;
    let espera = POLL_MS;

    const celebrar = (evento) => {
      const rol = datos.roles[evento.rol] || { titulo: 'Usuario', icono: '👤', color: '#22d3ee', color2: '#5eead4' };
      const card = document.querySelector(`[data-card="${evento.rol}"]`);

      if (card) {
        const contador = card.querySelector('[data-contador]');
        if (contador) contador.textContent = String(Number(contador.textContent) + 1);
        card.classList.remove('is-hit');
        void card.offsetWidth;
        card.classList.add('is-hit');
        const caja = card.getBoundingClientRect();
        lanzarConfeti(caja.left + caja.width / 2, caja.top + caja.height * 0.4, [rol.color, rol.color2, '#ffffff']);
      }
      if (mascota) mascota.wave();

      const toast = document.createElement('div');
      toast.className = 'dq-toast';
      toast.style.setProperty('--rol', rol.color);
      toast.style.setProperty('--rol2', rol.color2);
      toast.setAttribute('role', 'status');
      const icono = document.createElement('span');
      icono.className = 'dq-toast__icono';
      icono.textContent = rol.icono;
      const texto = document.createElement('p');
      const nombre = document.createElement('strong');
      nombre.textContent = evento.nombre;
      texto.append(nombre, `entró como ${rol.titulo} · ${evento.hora}`);
      toast.append(icono, texto);
      toasts.prepend(toast);
      setTimeout(() => {
        toast.classList.add('is-leaving');
        setTimeout(() => toast.remove(), 400);
      }, 6000);
    };

    const consultar = async () => {
      try {
        const respuesta = await fetch(`${datos.url_actividad}?despues=${ultimo}`, {
          headers: { Accept: 'application/json' },
          credentials: 'same-origin',
        });
        if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);
        const cuerpo = await respuesta.json();
        if (!cuerpo.success) throw new Error(cuerpo.message || 'Respuesta sin éxito');
        cuerpo.data.forEach((evento, i) => {
          ultimo = Math.max(ultimo, evento.id);
          setTimeout(() => celebrar(evento), i * 700);
        });
        espera = POLL_MS;
        if (estado) {
          estado.classList.remove('is-off');
          estado.textContent = 'En vivo';
        }
      } catch (error) {
        console.error('[Demo QR] No se pudo consultar la actividad:', error);
        espera = Math.min(espera * 2, POLL_MAX_MS);
        if (estado) {
          estado.classList.add('is-off');
          estado.textContent = 'Reconectando…';
        }
      } finally {
        setTimeout(consultar, espera);
      }
    };
    setTimeout(consultar, POLL_MS);
  }

  document.addEventListener('DOMContentLoaded', () => {
    crearBurbujas(document.querySelector('[data-burbujas]'));
    const pantalla = document.body.dataset.dq;
    if (pantalla === 'acceso') iniciarAcceso();
    else if (pantalla === 'invalido') iniciarInvalido();
    else if (pantalla === 'presentacion') iniciarPresentacion();
  });
})();
