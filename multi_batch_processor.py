#!/usr/bin/env python3
"""
Multi-Batch Processor - Wrapper para OCRBatchProcessor
======================================================
DEPRECATED: Este módulo se mantiene por compatibilidad con código existente.
Usar batch_processor.OCRBatchProcessor directamente en código nuevo.

Este archivo ahora actúa como wrapper simple sobre OCRBatchProcessor,
proporcionando la misma API que antes pero usando el procesador unificado.

Versión: 2.0.0 - Wrapper sobre batch_processor.py (Fase 4)
"""

import logging
from typing import List, Dict
from pathlib import Path

# Importar el procesador unificado y sus componentes
from batch_processor import (
    OCRBatchProcessor,
    FileEntry,
    MultiBatchSummary
)
from batch_optimizer import BatchOptimizer

logger = logging.getLogger(__name__)


# ==================== CLASE WRAPPER ====================

class MultiBatchProcessor(OCRBatchProcessor):
    """
    DEPRECATED: Usar OCRBatchProcessor de batch_processor.py

    Esta clase se mantiene por compatibilidad con código existente que usa:
    - from multi_batch_processor import MultiBatchProcessor

    Hereda toda la funcionalidad de OCRBatchProcessor sin duplicar código.
    """

    def __init__(self):
        """
        Inicializa MultiBatchProcessor (wrapper sobre OCRBatchProcessor)

        NOTA: OCRBatchProcessor requiere ocr_client en __init__, pero
        MultiBatchProcessor original no lo requería. Para compatibilidad,
        inicializamos sin cliente y se debe establecer antes de usar.
        """
        # No podemos llamar a super().__init__() sin ocr_client
        # Inicializamos solo el optimizer como en la versión original
        self.optimizer = BatchOptimizer()

        logger.warning(
            "MultiBatchProcessor está deprecado. "
            "Usar OCRBatchProcessor de batch_processor.py en código nuevo."
        )

    def analyze_multiple_files(self, file_paths: List[str]) -> MultiBatchSummary:
        """
        Analiza múltiples archivos PDF y genera recomendaciones.

        Este método mantiene compatibilidad con la API original.

        Args:
            file_paths: Lista de rutas de archivos

        Returns:
            MultiBatchSummary con análisis completo
        """
        logger.warning(
            "MultiBatchProcessor.analyze_multiple_files() está deprecado. "
            "Usar OCRBatchProcessor.analyze_multiple_files() en código nuevo."
        )

        # Implementación directa para evitar recursión infinita
        # Analizar cada archivo individualmente
        file_entries = []
        total_size = 0
        total_pages = 0
        files_requiring_split = 0

        for file_path in file_paths:
            try:
                path = Path(file_path)
                if not path.exists():
                    logger.warning(f"Archivo no encontrado: {file_path}")
                    continue

                # Obtener páginas del PDF
                page_count = self._count_pdf_pages(path)
                if page_count is None:
                    continue

                # Analizar con BatchOptimizer
                analysis = self.optimizer.analyze_pdf(str(path), page_count)

                entry = FileEntry(
                    file_path=path,
                    display_name=path.name,
                    order_index=len(file_entries),
                    analysis=analysis,
                    recommendation=None  # Se genera después si se necesita
                )

                file_entries.append(entry)
                total_size += analysis.total_size_mb
                total_pages += analysis.total_pages

                if analysis.requires_splitting:
                    files_requiring_split += 1
                    entry.recommendation = self.optimizer.calculate_optimal_split(analysis)

            except Exception as e:
                logger.error(f"Error analizando {file_path}: {e}")

        # Calcular archivos estimados después de splits
        total_estimated_files = len(file_entries)
        for entry in file_entries:
            if entry.recommendation:
                total_estimated_files += entry.recommendation.num_files - 1

        # Determinar estrategia global
        if files_requiring_split == 0:
            global_strategy = "process_directly"
        elif files_requiring_split == len(file_entries):
            global_strategy = "split_all"
        else:
            global_strategy = "mixed"

        # Generar warnings si hay archivos que requieren split
        warnings = []
        if files_requiring_split > 0:
            warnings.append(f"{files_requiring_split} archivo(s) requieren división antes de procesamiento")

        # Crear resumen
        return MultiBatchSummary(
            files=file_entries,
            total_size_mb=total_size,
            total_pages=total_pages,
            total_estimated_files=total_estimated_files,
            global_strategy=global_strategy,
            processing_time_estimate=self._estimate_processing_time(total_pages) / 60.0,  # convertir a minutos
            warnings=warnings
        )

    def _count_pdf_pages(self, file_path: Path) -> int:
        """Cuenta páginas de un PDF."""
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            return len(reader.pages)
        except Exception as e:
            logger.error(f"Error contando páginas de {file_path}: {e}")
            return None

    def _estimate_processing_time(self, total_pages: int) -> float:
        """Estima tiempo de procesamiento en segundos."""
        # Aproximadamente 2 segundos por página
        return total_pages * 2.0

    def generate_processing_plan(self, summary: MultiBatchSummary) -> Dict:
        """
        Genera plan detallado de procesamiento.

        Args:
            summary: Resumen de análisis múltiple

        Returns:
            Dict con plan de procesamiento
        """
        logger.warning(
            "MultiBatchProcessor.generate_processing_plan() está deprecado."
        )

        plan = {
            'files': [],
            'page_offset': 0,
            'total_operations': 0,
            'estimated_time': summary.processing_time_estimate
        }

        current_page_offset = 0

        for entry in summary.files:
            file_plan = {
                'original_file': str(entry.file_path),
                'display_name': entry.display_name,
                'page_offset': current_page_offset,
                'operations': []
            }

            if entry.recommendation and entry.analysis:
                if entry.recommendation.num_files == 1:
                    file_plan['operations'].append({
                        'type': 'direct_process',
                        'pages': entry.analysis.total_pages,
                        'estimated_mb': entry.analysis.total_size_mb
                    })
                else:
                    pages_per_file = entry.recommendation.pages_per_file
                    for i in range(entry.recommendation.num_files):
                        start_page = i * pages_per_file + 1
                        end_page = min((i + 1) * pages_per_file, entry.analysis.total_pages)

                        file_plan['operations'].append({
                            'type': 'split_and_process',
                            'part_number': i + 1,
                            'pages_range': (start_page, end_page),
                            'pages_count': end_page - start_page + 1,
                            'estimated_mb': entry.recommendation.estimated_mb_per_file
                        })

                current_page_offset += entry.analysis.total_pages
                plan['total_operations'] += len(file_plan['operations'])

            plan['files'].append(file_plan)

        return plan

    def format_summary_report(self, summary: MultiBatchSummary) -> str:
        """
        Genera reporte formateado del análisis múltiple.

        Args:
            summary: Resumen de análisis

        Returns:
            String con reporte formateado
        """
        logger.warning(
            "MultiBatchProcessor.format_summary_report() está deprecado."
        )

        lines = [
            "=" * 70,
            "ANÁLISIS DE PROCESAMIENTO MÚLTIPLE",
            "=" * 70,
            f"Archivos a procesar: {len(summary.files)}",
            f"Tamaño total: {summary.total_size_mb:.1f} MB",
            f"Páginas totales: {summary.total_pages}",
            f"Densidad promedio: {summary.avg_density:.2f} MB/página",
            f"Archivos estimados tras división: {summary.total_estimated_files}",
            f"Tiempo estimado: {summary.processing_time_estimate:.1f} minutos",
            f"Estrategia global: {summary.global_strategy}",
            ""
        ]

        # Advertencias globales
        if summary.warnings:
            lines.extend([
                "⚠️ ADVERTENCIAS:",
                "-" * 30
            ])
            for warning in summary.warnings:
                lines.append(f"  • {warning}")
            lines.append("")

        # Detalles por archivo
        lines.extend([
            "ANÁLISIS POR ARCHIVO:",
            "-" * 70
        ])

        page_offset = 0
        for i, entry in enumerate(summary.files, 1):
            lines.append(f"\n{i}. {entry.display_name}")

            if entry.analysis:
                lines.extend([
                    f"   📊 Tamaño: {entry.analysis.total_size_mb:.1f} MB",
                    f"   📄 Páginas: {entry.analysis.total_pages} (desde página {page_offset + 1})",
                    f"   🎯 Densidad: {entry.analysis.density_mb_per_page:.2f} MB/página"
                ])

                if entry.recommendation:
                    if entry.recommendation.num_files == 1:
                        lines.append("   ✅ No requiere división")
                    else:
                        lines.extend([
                            f"   📂 División: {entry.recommendation.num_files} archivos",
                            f"   📑 Páginas por archivo: {entry.recommendation.pages_per_file}",
                            f"   💾 MB por archivo: {entry.recommendation.estimated_mb_per_file:.1f}",
                            f"   🏆 Eficiencia: {entry.recommendation.efficiency_score:.0%}"
                        ])

                page_offset += entry.analysis.total_pages
            else:
                lines.append("   ❌ Error en análisis")

        lines.extend([
            "",
            "=" * 70
        ])

        return "\n".join(lines)

    def get_file_processing_order(self, summary: MultiBatchSummary):
        """
        Obtiene orden de procesamiento con offsets de página.

        Args:
            summary: Resumen de análisis

        Returns:
            Lista de tuplas (file_path, page_offset, total_pages)
        """
        logger.warning(
            "MultiBatchProcessor.get_file_processing_order() está deprecado."
        )

        processing_order = []
        page_offset = 0

        for entry in summary.files:
            if entry.analysis:
                processing_order.append((
                    str(entry.file_path),
                    page_offset,
                    entry.analysis.total_pages
                ))
                page_offset += entry.analysis.total_pages

        return processing_order


# ==================== FUNCIONES DE UTILIDAD ====================

def analyze_multiple_pdfs(file_paths: List[str]) -> MultiBatchSummary:
    """
    DEPRECATED: Usar OCRBatchProcessor.analyze_multiple_files()

    Función principal para análisis múltiple.

    Args:
        file_paths: Lista de rutas de archivos

    Returns:
        MultiBatchSummary con análisis
    """
    logger.warning(
        "multi_batch_processor.analyze_multiple_pdfs() está deprecado. "
        "Usar OCRBatchProcessor.analyze_multiple_files() en código nuevo."
    )

    processor = MultiBatchProcessor()
    return processor.analyze_multiple_files(file_paths)


def get_processing_plan(file_paths: List[str]) -> Dict:
    """
    DEPRECATED: Crear OCRBatchProcessor y usar sus métodos

    Obtiene plan completo de procesamiento.

    Args:
        file_paths: Lista de rutas de archivos

    Returns:
        Dict con plan de procesamiento
    """
    logger.warning(
        "multi_batch_processor.get_processing_plan() está deprecado."
    )

    processor = MultiBatchProcessor()
    summary = processor.analyze_multiple_files(file_paths)
    return processor.generate_processing_plan(summary)


# ==================== MENSAJE DE DEPRECACIÓN ====================
# Mensaje cambiado a nivel DEBUG para no mostrar en uso normal
# Si necesitas ver estos mensajes, ejecuta con: logging.basicConfig(level=logging.DEBUG)

logger.debug(
    "⚠️  multi_batch_processor.py está deprecado. "
    "Toda la funcionalidad se ha movido a batch_processor.py (Fase 3). "
    "Este módulo se mantiene como wrapper para compatibilidad."
)
