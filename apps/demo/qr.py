"""
QR con identidad visual de SIGMAP-AQUA.

En lugar del QR cuadrado de siempre: módulos redondos con el degradado del
color de cada rol, marcadores de esquina redondeados y la cabeza del robot
SigmaP Aqua en el centro. Se usa corrección de errores alta (H, 30 %) para que
el logo central no afecte la lectura.

Salidas:
    qr_svg(...)  -> markup SVG para la pantalla de presentación
    qr_png(...)  -> archivo PNG para imprimir (generar_qrs_demo)
"""

import segno

BORDE = 4           # zona silenciosa estándar, en módulos
FINDER = 7          # tamaño de los marcadores de esquina
RADIO_PUNTO = 0.43  # radio de cada módulo, en módulos
FRACCION_LOGO = 0.24
# Redondeo de los marcadores de esquina. Más redondeo se ve más moderno pero
# empeora la lectura en lectores estrictos (medido con OpenCV): 0.3 / 0.15
# mantiene la lectura hasta ~150 px de ancho.
RADIO_FINDER = 0.3
RADIO_FINDER_INTERNO = 0.15


def _matriz(texto):
    """Matriz booleana del QR (True = módulo oscuro)."""
    qr = segno.make(texto, error='h', boost_error=False)
    return [[bool(celda) for celda in fila] for fila in qr.matrix]


def _es_finder(fila, col, n):
    """True si la celda pertenece a uno de los tres marcadores de esquina."""
    return (
        (fila < FINDER and col < FINDER)
        or (fila < FINDER and col >= n - FINDER)
        or (fila >= n - FINDER and col < FINDER)
    )


def _zona_logo(n):
    """Rango (inicio, fin) de filas/columnas reservado al logo central."""
    lado = int(n * FRACCION_LOGO) | 1  # impar, para centrarlo exacto
    inicio = (n - lado) // 2
    return inicio, inicio + lado


def _geometria(texto):
    """
    Calcula las formas a dibujar, independiente del formato de salida.

    :return: dict con n (lado total en módulos), puntos [(x, y)],
             finders [(x, y)] y logo (x0, x1) en coordenadas de módulo
    """
    matriz = _matriz(texto)
    n = len(matriz)
    logo_ini, logo_fin = _zona_logo(n)

    puntos = []
    for fila, valores in enumerate(matriz):
        for col, oscuro in enumerate(valores):
            if not oscuro or _es_finder(fila, col, n):
                continue
            if logo_ini - 1 <= fila < logo_fin + 1 and logo_ini - 1 <= col < logo_fin + 1:
                continue
            puntos.append((col + BORDE, fila + BORDE))

    finders = [(BORDE, BORDE), (BORDE + n - FINDER, BORDE), (BORDE, BORDE + n - FINDER)]
    return {
        'n': n + 2 * BORDE,
        'puntos': puntos,
        'finders': finders,
        'logo': (logo_ini + BORDE, logo_fin + BORDE),
    }


def _robot_svg(cx, cy, r):
    """Cabeza del robot SigmaP Aqua centrada en (cx, cy) con radio r."""
    def p(v):
        return f'{v:.2f}'

    return (
        f'<circle cx="{p(cx)}" cy="{p(cy)}" r="{p(r)}" fill="#ffffff" stroke="#1d3b63" stroke-width="{p(r * 0.09)}"/>'
        f'<circle cx="{p(cx - r * 0.98)}" cy="{p(cy + r * 0.05)}" r="{p(r * 0.2)}" fill="#2f80ed"/>'
        f'<circle cx="{p(cx + r * 0.98)}" cy="{p(cy + r * 0.05)}" r="{p(r * 0.2)}" fill="#2f80ed"/>'
        f'<rect x="{p(cx - r * 0.72)}" y="{p(cy - r * 0.3)}" width="{p(r * 1.44)}" height="{p(r * 0.78)}" '
        f'rx="{p(r * 0.39)}" fill="#0b1f3a"/>'
        f'<path d="M{p(cx - r * 0.5)} {p(cy + r * 0.2)} Q{p(cx - r * 0.32)} {p(cy - r * 0.12)} {p(cx - r * 0.14)} {p(cy + r * 0.2)}" '
        f'fill="none" stroke="#22d3ee" stroke-width="{p(r * 0.12)}" stroke-linecap="round"/>'
        f'<path d="M{p(cx + r * 0.14)} {p(cy + r * 0.2)} Q{p(cx + r * 0.32)} {p(cy - r * 0.12)} {p(cx + r * 0.5)} {p(cy + r * 0.2)}" '
        f'fill="none" stroke="#22d3ee" stroke-width="{p(r * 0.12)}" stroke-linecap="round"/>'
    )


def qr_svg(texto, color, color2, *, uid='qr', titulo='Código QR'):
    """
    QR estilizado como SVG escalable.

    :param texto: URL a codificar
    :param color: color inicial del degradado (hex)
    :param color2: color final del degradado (hex)
    :param uid: prefijo único para los ids del degradado
    :param titulo: texto accesible del QR
    :return: str con el SVG
    """
    g = _geometria(texto)
    n = g['n']
    grad = f'{uid}-grad'

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" role="img" '
        f'aria-label="{titulo}" shape-rendering="geometricPrecision">',
        f'<defs><linearGradient id="{grad}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{color}"/><stop offset="1" stop-color="{color2}"/>'
        f'</linearGradient></defs>',
        f'<rect width="{n}" height="{n}" rx="{n * 0.06:.2f}" fill="#ffffff"/>',
        f'<g fill="url(#{grad})">',
    ]
    partes.extend(
        f'<circle cx="{x + 0.5}" cy="{y + 0.5}" r="{RADIO_PUNTO}"/>' for x, y in g['puntos']
    )
    for x, y in g['finders']:
        partes.append(f'<rect x="{x}" y="{y}" width="7" height="7" rx="{RADIO_FINDER}"/>')
        partes.append(f'<rect x="{x + 1}" y="{y + 1}" width="5" height="5" rx="{RADIO_FINDER_INTERNO}" fill="#ffffff"/>')
        partes.append(f'<rect x="{x + 2}" y="{y + 2}" width="3" height="3" rx="{RADIO_FINDER_INTERNO}"/>')
    partes.append('</g>')

    ini, fin = g['logo']
    centro = (ini + fin) / 2
    lado = fin - ini
    partes.append(
        f'<rect x="{ini - 0.3}" y="{ini - 0.3}" width="{lado + 0.6}" height="{lado + 0.6}" '
        f'rx="{lado * 0.28:.2f}" fill="#ffffff"/>'
    )
    partes.append(_robot_svg(centro, centro, lado * 0.33))
    partes.append('</svg>')
    return ''.join(partes)


def _mezclar(hex_a, hex_b, t):
    """Interpola dos colores hex (t entre 0 y 1)."""
    a = tuple(int(hex_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(hex_b[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))


def qr_png(texto, color, color2, ruta, *, escala=24):
    """
    QR estilizado como PNG para imprimir.

    :param texto: URL a codificar
    :param color: color inicial del degradado (hex)
    :param color2: color final del degradado (hex)
    :param ruta: archivo de salida (.png)
    :param escala: píxeles por módulo
    """
    from PIL import Image, ImageDraw

    g = _geometria(texto)
    n = g['n']
    lado_px = n * escala
    img = Image.new('RGB', (lado_px, lado_px), '#ffffff')
    dibujo = ImageDraw.Draw(img)

    def color_en(x, y):
        return _mezclar(color, color2, (x + y) / (2 * n))

    r = RADIO_PUNTO * escala
    for x, y in g['puntos']:
        cx, cy = (x + 0.5) * escala, (y + 0.5) * escala
        dibujo.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color_en(x, y))

    for x, y in g['finders']:
        tono = color_en(x + 3.5, y + 3.5)
        x0, y0 = x * escala, y * escala
        dibujo.rounded_rectangle((x0, y0, x0 + 7 * escala, y0 + 7 * escala), radius=RADIO_FINDER * escala, fill=tono)
        dibujo.rounded_rectangle((x0 + escala, y0 + escala, x0 + 6 * escala, y0 + 6 * escala),
                                 radius=RADIO_FINDER_INTERNO * escala, fill='#ffffff')
        dibujo.rounded_rectangle((x0 + 2 * escala, y0 + 2 * escala, x0 + 5 * escala, y0 + 5 * escala),
                                 radius=RADIO_FINDER_INTERNO * escala, fill=tono)

    ini, fin = g['logo']
    a, b = (ini - 0.3) * escala, (fin + 0.3) * escala
    dibujo.rounded_rectangle((a, a, b, b), radius=(fin - ini) * 0.28 * escala, fill='#ffffff')

    centro = (ini + fin) / 2 * escala
    radio = (fin - ini) * 0.33 * escala
    borde = max(2, int(radio * 0.09))
    oreja = radio * 0.2
    for dx in (-0.98, 0.98):
        ox = centro + dx * radio
        dibujo.ellipse((ox - oreja, centro - oreja, ox + oreja, centro + oreja), fill='#2f80ed')
    dibujo.ellipse((centro - radio, centro - radio, centro + radio, centro + radio),
                   fill='#ffffff', outline='#1d3b63', width=borde)
    dibujo.rounded_rectangle(
        (centro - radio * 0.72, centro - radio * 0.3, centro + radio * 0.72, centro + radio * 0.48),
        radius=radio * 0.39, fill='#0b1f3a')
    grosor = max(2, int(radio * 0.12))
    for dx in (-0.32, 0.32):
        ox = centro + dx * radio
        caja = (ox - radio * 0.18, centro - radio * 0.08, ox + radio * 0.18, centro + radio * 0.28)
        dibujo.arc(caja, start=200, end=340, fill='#22d3ee', width=grosor)

    img.save(ruta, 'PNG', optimize=True)
