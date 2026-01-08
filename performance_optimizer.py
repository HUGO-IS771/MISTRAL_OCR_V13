#!/usr/bin/env python3
"""
Performance Optimizer - Wrapper para OCRBatchProcessor
=====================================================
DEPRECATED: Este módulo se mantiene por compatibilidad con código existente.
Usar batch_processor.OCRBatchProcessor directamente en código nuevo.

Este archivo ahora actúa como wrapper simple sobre OCRBatchProcessor,
proporcionando la misma API que antes pero usando el procesador unificado.

Versión: 2.0.0 - Wrapper sobre batch_processor.py (Fase 4)
"""

import logging
from typing import List, Dict, Callable, Tuple
from pathlib import Path

# Importar el procesador unificado
from batch_processor import (
    OCRBatchProcessor,
    PerformanceMetrics,
    create_optimized_processor as _create_optimized_processor,
    estimate_processing_time as _estimate_processing_time
)

logger = logging.getLogger(__name__)


# ==================== CLASE WRAPPER ====================

class BatchProcessor(OCRBatchProcessor):
    """
    DEPRECATED: Usar OCRBatchProcessor de batch_processor.py

    Esta clase se mantiene por compatibilidad con código existente que usa:
    - from performance_optimizer import BatchProcessor

    Hereda toda la funcionalidad de OCRBatchProcessor sin duplicar código.
    """

    def __init__(self, ocr_client, max_workers: int = 3):
        """
        Inicializa BatchProcessor (wrapper sobre OCRBatchProcessor)

        Args:
            ocr_client: Cliente OCR de Mistral
            max_workers: Número máximo de workers concurrentes
        """
        super().__init__(ocr_client, max_workers=max_workers, app=None)
        logger.warning(
            "BatchProcessor está deprecado. "
            "Usar OCRBatchProcessor de batch_processor.py en código nuevo."
        )


# ==================== CLASE DE CONFIGURACIÓN ====================

class PerformanceConfig:
    """
    DEPRECATED: Usar funciones de batch_processor.py directamente

    Configuración de rendimiento adaptativa.
    Mantenido por compatibilidad.
    """

    @staticmethod
    def get_optimal_config(file_count: int, total_size_mb: float) -> Dict:
        """
        Obtiene configuración óptima basada en el lote.

        Args:
            file_count: Número de archivos
            total_size_mb: Tamaño total en MB

        Returns:
            Dict con configuración optimizada
        """
        logger.warning(
            "PerformanceConfig.get_optimal_config() está deprecado. "
            "Usar create_optimized_processor() de batch_processor.py"
        )

        config = {
            'max_workers': 3,
            'base_delay': 1.5,
            'enable_cache': True,
            'parallel_save': True
        }

        # Ajustar según tamaño del lote
        if file_count > 10:
            config['max_workers'] = 2
            config['base_delay'] = 2.5
        elif file_count < 3:
            config['max_workers'] = 4
            config['base_delay'] = 1.0

        # Ajustar según tamaño total
        if total_size_mb > 500:
            config['max_workers'] = 2
            config['base_delay'] = 3.5
        elif total_size_mb < 50:
            config['max_workers'] = 4
            config['base_delay'] = 0.5

        return config

    @staticmethod
    def estimate_processing_time(files_info: List[Dict]) -> float:
        """
        Estima tiempo de procesamiento.

        Args:
            files_info: Lista de información de archivos

        Returns:
            Tiempo estimado en segundos
        """
        logger.warning(
            "PerformanceConfig.estimate_processing_time() está deprecado. "
            "Usar estimate_processing_time() de batch_processor.py"
        )

        # Delegar a la función unificada
        estimated_seconds, _ = _estimate_processing_time(files_info)
        return estimated_seconds


# ==================== FUNCIONES DE UTILIDAD ====================

def create_optimized_processor(ocr_client, file_count: int = 1, total_size_mb: float = 0):
    """
    DEPRECATED: Usar create_optimized_processor() de batch_processor.py

    Crea procesador optimizado con configuración adaptativa.

    Args:
        ocr_client: Cliente OCR
        file_count: Número de archivos
        total_size_mb: Tamaño total en MB

    Returns:
        BatchProcessor (wrapper sobre OCRBatchProcessor)
    """
    logger.warning(
        "performance_optimizer.create_optimized_processor() está deprecado. "
        "Usar batch_processor.create_optimized_processor() en código nuevo."
    )

    # Delegar a la función unificada y envolver en BatchProcessor por compatibilidad
    unified_processor = _create_optimized_processor(ocr_client, file_count, total_size_mb, app=None)

    # Retornar como BatchProcessor para compatibilidad
    # (aunque ya es un OCRBatchProcessor, el tipo es correcto por herencia)
    return unified_processor


def estimate_batch_time(files_info: List[Dict]) -> Tuple[float, str]:
    """
    DEPRECATED: Usar estimate_processing_time() de batch_processor.py

    Estima tiempo de procesamiento y devuelve descripción.

    Args:
        files_info: Lista de información de archivos

    Returns:
        Tuple (segundos, descripción)
    """
    logger.warning(
        "performance_optimizer.estimate_batch_time() está deprecado. "
        "Usar batch_processor.estimate_processing_time() en código nuevo."
    )

    # Delegar completamente a la función unificada
    return _estimate_processing_time(files_info)


# ==================== MENSAJE DE DEPRECACIÓN ====================
# Mensaje cambiado a nivel DEBUG para no mostrar en uso normal
# Si necesitas ver estos mensajes, ejecuta con: logging.basicConfig(level=logging.DEBUG)

logger.debug(
    "⚠️  performance_optimizer.py está deprecado. "
    "Toda la funcionalidad se ha movido a batch_processor.py (Fase 3). "
    "Este módulo se mantiene como wrapper para compatibilidad."
)
