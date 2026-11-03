"""
Paginación de la API móvil.

PageNumberPagination por defecto ignora `?page_size=`: la app no podría pedir
los 500 puntos que necesita una gráfica de 30 días. Aquí se habilita con un
tope, para que nadie pida la tabla completa de lecturas de un solo golpe.
"""
from rest_framework.pagination import PageNumberPagination


class PaginacionMovil(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 500
