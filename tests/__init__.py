"""
Suite de pruebas de SIGMAP-AQUA.

Se ejecuta con:  python manage.py test tests -v 2

Django crea una base de datos temporal (`test_sigmap_agua`), corre las pruebas
y la destruye: NUNCA toca los datos reales del proyecto.

Estructura AAA en cada prueba: Arrange (preparar), Act (ejecutar), Assert
(verificar). Cada modulo cubre camino feliz, caso de error y caso limite.
"""
