#!/usr/bin/env python3
"""
Processing Limits - Límites de procesamiento centralizados
Configuración unificada de límites de la API de Mistral OCR.

ÚNICO PUNTO DE VERDAD para todos los límites de procesamiento.
Todos los módulos deben importar y usar estos valores.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessingLimits:
    """
    Límites unificados para procesamiento OCR.

    Estos valores representan los límites seguros para la API de Mistral OCR,
    calculados con márgenes de seguridad para evitar rechazos.

    Basado en límites de la API de Mistral:
    - Tamaño máximo absoluto: 50 MB
    - Páginas máximas absolutas: 150 páginas

    Con factores de seguridad aplicados:
    - Tamaño: 48 MB (96% del límite)
    - Páginas: 135 (90% del límite)
    """

    # === LÍMITES ABSOLUTOS DE LA API (NO MODIFICAR) ===
    API_MAX_SIZE_MB: float = 50.0
    API_MAX_PAGES: int = 150

    # === LÍMITES SEGUROS (CON MARGEN DE SEGURIDAD) ===
    # Estos son los valores que DEBEN usarse en toda la aplicación
    SAFE_MAX_SIZE_MB: float = 48.0      # 96% del límite (2MB de margen)
    SAFE_MAX_PAGES: int = 135           # 90% del límite (15 páginas de margen)

    # === FACTORES DE SEGURIDAD ===
    SAFETY_FACTOR_SIZE: float = 0.96    # 4% de margen para tamaño
    SAFETY_FACTOR_PAGES: float = 0.90   # 10% de margen para páginas

    # === OVERHEAD DE PDF ===
    PDF_OVERHEAD_MB: float = 0.5        # Overhead estimado al dividir PDFs

    # === LÍMITES PARA VALIDACIONES ===
    # Estos valores se usan en validaciones específicas
    VALIDATION_SIZE_MB: float = SAFE_MAX_SIZE_MB
    VALIDATION_PAGES: int = SAFE_MAX_PAGES

    # === LÍMITES POR DEFECTO PARA PROCESAMIENTO ===
    # Valores por defecto al procesar un archivo individual
    DEFAULT_MAX_SIZE_MB: float = SAFE_MAX_SIZE_MB
    DEFAULT_MAX_PAGES: int = SAFE_MAX_PAGES

    # === LÍMITES PARA BATCH PROCESSING ===
    # Al procesar múltiples archivos, usar límites más conservadores
    BATCH_MAX_SIZE_MB: float = SAFE_MAX_SIZE_MB
    BATCH_MAX_PAGES: int = SAFE_MAX_PAGES

    # === WORKERS Y CONCURRENCIA ===
    DEFAULT_WORKERS: int = 2
    MAX_WORKERS: int = 10
    MIN_WORKERS: int = 1

    # === RATE LIMITING ===
    DELAY_BETWEEN_REQUESTS_SECONDS: float = 2.0
    UPLOAD_URL_CACHE_MINUTES: int = 50


# === INSTANCIA GLOBAL ÚNICA ===
# Usar esta instancia en toda la aplicación
LIMITS = ProcessingLimits()


# === FUNCIONES DE UTILIDAD ===

def get_safe_limits() -> tuple[float, int]:
    """
    Retorna los límites seguros para procesamiento.

    Returns:
        tuple[float, int]: (max_size_mb, max_pages)
    """
    return LIMITS.SAFE_MAX_SIZE_MB, LIMITS.SAFE_MAX_PAGES


def is_within_limits(size_mb: float, pages: int) -> bool:
    """
    Verifica si un archivo está dentro de los límites seguros.

    Args:
        size_mb: Tamaño del archivo en MB
        pages: Número de páginas

    Returns:
        bool: True si está dentro de límites, False en caso contrario
    """
    return (size_mb <= LIMITS.SAFE_MAX_SIZE_MB and
            pages <= LIMITS.SAFE_MAX_PAGES)


def get_exceeded_limits(size_mb: float, pages: int) -> list[str]:
    """
    Identifica qué límites fueron excedidos.

    Args:
        size_mb: Tamaño del archivo en MB
        pages: Número de páginas

    Returns:
        list[str]: Lista de límites excedidos
    """
    exceeded = []

    if size_mb > LIMITS.SAFE_MAX_SIZE_MB:
        exceeded.append(
            f"Tamaño ({size_mb:.1f} MB > {LIMITS.SAFE_MAX_SIZE_MB} MB)"
        )

    if pages > LIMITS.SAFE_MAX_PAGES:
        exceeded.append(
            f"Páginas ({pages} > {LIMITS.SAFE_MAX_PAGES})"
        )

    return exceeded


def format_limits_info() -> str:
    """
    Formatea información sobre los límites para mostrar al usuario.

    Returns:
        str: Información formateada
    """
    separator = "=" * 40
    return f"""Limites de Procesamiento Mistral OCR:
{separator}
- Tamanio maximo: {LIMITS.SAFE_MAX_SIZE_MB} MB
- Paginas maximas: {LIMITS.SAFE_MAX_PAGES} paginas
- Workers por defecto: {LIMITS.DEFAULT_WORKERS}
{separator}
Nota: Limites con margen de seguridad aplicado.
API absolutos: {LIMITS.API_MAX_SIZE_MB} MB / {LIMITS.API_MAX_PAGES} paginas"""


# === VALIDACION DE IMPORTACION ===
if __name__ == "__main__":
    print("=== LIMITES DE PROCESAMIENTO MISTRAL OCR ===")
    print()
    print(format_limits_info())
    print()
    print("Limites seguros:", get_safe_limits())
    print()
    print("Ejemplo de validacion:")
    print(f"  - Archivo de 45 MB, 120 paginas: {is_within_limits(45, 120)}")
    print(f"  - Archivo de 55 MB, 100 paginas: {is_within_limits(55, 100)}")
    print(f"    Excedidos: {get_exceeded_limits(55, 100)}")
