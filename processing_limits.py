#!/usr/bin/env python3
"""
Processing Limits - Límites de procesamiento centralizados.
Configuración unificada de límites de la API de Mistral OCR.

ÚNICO PUNTO DE VERDAD para todos los límites de procesamiento.
"""

import warnings
from dataclasses import dataclass
from functools import cached_property
from typing import NamedTuple


class LimitCheckResult(NamedTuple):
    """Resultado de verificación de límites."""
    within_limits: bool
    exceeded: list[str]


@dataclass(frozen=True)
class ProcessingLimits:
    """
    Límites unificados para procesamiento OCR.
    
    Límites absolutos de API Mistral (Actualizados según pruebas exitosas):
    - Tamaño máximo: 100 MB
    - Páginas máximas: 1000
    
    Los límites seguros se calculan aplicando factores de seguridad.
    """
    
    # === LÍMITES ABSOLUTOS DE LA API ===
    API_MAX_SIZE_MB: float = 100.0
    API_MAX_PAGES: int = 1000
    
    # === FACTORES DE SEGURIDAD ===
    SAFETY_FACTOR_SIZE: float = 0.96
    SAFETY_FACTOR_PAGES: float = 0.90
    
    # === CONCURRENCIA ===
    DEFAULT_WORKERS: int = 2
    MAX_WORKERS: int = 10
    MIN_WORKERS: int = 1
    
    # === RATE LIMITING ===
    DELAY_BETWEEN_REQUESTS: float = 2.0
    UPLOAD_URL_CACHE_MINUTES: int = 50
    
    # === PDF OVERHEAD ===
    PDF_OVERHEAD_MB: float = 0.5        # Overhead estimado al dividir PDFs
    
    @cached_property
    def safe_max_size_mb(self) -> float:
        """Tamaño máximo seguro en MB (calculado dinámicamente)."""
        return self.API_MAX_SIZE_MB * self.SAFETY_FACTOR_SIZE
    
    @cached_property
    def safe_max_pages(self) -> int:
        """Páginas máximas seguras (calculado dinámicamente)."""
        return int(self.API_MAX_PAGES * self.SAFETY_FACTOR_PAGES)

    def __getattr__(self, name: str):
        """Manejo centralizado de alias deprecados para compatibilidad hacia atrás."""
        aliases = {
            'SAFE_MAX_SIZE_MB': 'safe_max_size_mb',
            'SAFE_MAX_PAGES': 'safe_max_pages',
            'VALIDATION_SIZE_MB': 'safe_max_size_mb',
            'VALIDATION_PAGES': 'safe_max_pages',
            'DEFAULT_MAX_SIZE_MB': 'safe_max_size_mb',
            'DEFAULT_MAX_PAGES': 'safe_max_pages',
            'BATCH_MAX_SIZE_MB': 'safe_max_size_mb',
            'BATCH_MAX_PAGES': 'safe_max_pages',
            'DELAY_BETWEEN_REQUESTS_SECONDS': 'DELAY_BETWEEN_REQUESTS',
        }
        
        if name in aliases:
            target = aliases[name]
            # Emitir advertencia de deprecación
            warnings.warn(
                f"'{name}' está obsoleto. Use '{target}' en su lugar.",
                DeprecationWarning,
                stacklevel=2
            )
            return getattr(self, target)
        
        raise AttributeError(f"'{type(self).__name__}' objeto no tiene el atributo '{name}'")
    
    def is_within_limits(self, size_mb: float, pages: int) -> bool:
        """Verifica si un archivo está dentro de los límites seguros."""
        return size_mb <= self.safe_max_size_mb and pages <= self.safe_max_pages
    
    def check_limits(self, size_mb: float, pages: int) -> LimitCheckResult:
        """
        Verifica límites y retorna resultado detallado.
        
        Returns:
            LimitCheckResult con estado y lista de excedencias.
        """
        exceeded = []
        
        if size_mb > self.safe_max_size_mb:
            exceeded.append(
                f"Tamaño: {size_mb:.1f} MB excede {self.safe_max_size_mb:.1f} MB"
            )
        
        if pages > self.safe_max_pages:
            exceeded.append(
                f"Páginas: {pages} excede {self.safe_max_pages}"
            )
        
        return LimitCheckResult(
            within_limits=len(exceeded) == 0,
            exceeded=exceeded
        )
    
    def __str__(self) -> str:
        """Representación legible de los límites."""
        return (
            f"Límites Mistral OCR:\n"
            f"  Tamaño máximo seguro: {self.safe_max_size_mb:.1f} MB\n"
            f"  Páginas máximas seguras: {self.safe_max_pages}\n"
            f"  Workers por defecto: {self.DEFAULT_WORKERS}\n"
            f"  (API absolutos: {self.API_MAX_SIZE_MB:.0f} MB / {self.API_MAX_PAGES} págs)"
        )


# === INSTANCIA GLOBAL ÚNICA ===
LIMITS = ProcessingLimits()


# === FUNCIONES DE CONVENIENCIA (compatibilidad hacia atrás) ===

def get_safe_limits() -> tuple[float, int]:
    """Retorna (max_size_mb, max_pages) seguros."""
    return LIMITS.safe_max_size_mb, LIMITS.safe_max_pages


def is_within_limits(size_mb: float, pages: int) -> bool:
    """Verifica si está dentro de límites seguros."""
    return LIMITS.is_within_limits(size_mb, pages)


def get_exceeded_limits(size_mb: float, pages: int) -> list[str]:
    """Identifica qué límites fueron excedidos."""
    return LIMITS.check_limits(size_mb, pages).exceeded


def format_limits_info() -> str:
    """
    Formatea información sobre los límites para mostrar al usuario.
    Mantenida por compatibilidad.
    """
    return str(LIMITS)


if __name__ == "__main__":
    # Configurar filtros para mostrar DeprecationWarnings en la prueba
    warnings.simplefilter('always', DeprecationWarning)
    
    print("=== LÍMITES DE PROCESAMIENTO MISTRAL OCR ===\n")
    print(LIMITS)
    
    print("\n--- Pruebas de Compatibilidad (Alias) ---")
    try:
        # Esto debería disparar una advertencia
        print(f"Accediendo a LIMITS.SAFE_MAX_SIZE_MB (alias): {LIMITS.SAFE_MAX_SIZE_MB}")
        print(f"Accediendo a LIMITS.DEFAULT_MAX_PAGES (alias): {LIMITS.DEFAULT_MAX_PAGES}")
    except Exception as e:
        print(f"Error en alias: {e}")
        
    print("\n--- Validaciones de ejemplo ---")
    test_cases = [(45, 120), (55, 100), (48, 260)]
    for size, pages in test_cases:
        result = LIMITS.check_limits(size, pages)
        status = "✓" if result.within_limits else "✗"
        print(f"  {status} {size} MB, {pages} págs", end="")
        if result.exceeded:
            print(f" → {result.exceeded}")
        else:
            print()
