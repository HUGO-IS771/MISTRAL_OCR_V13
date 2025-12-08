#!/usr/bin/env python3
"""
Multi-Batch Processor - Procesador de múltiples archivos PDF
Analiza y procesa varios archivos PDF manteniendo orden y numeración continua.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from batch_optimizer import BatchOptimizer, PDFAnalysis, SplitRecommendation


@dataclass
class FileEntry:
    """Entrada de archivo en el procesamiento múltiple."""
    file_path: Path
    display_name: str
    order_index: int
    analysis: Optional[PDFAnalysis] = None
    recommendation: Optional[SplitRecommendation] = None
    
    @property
    def file_size_mb(self) -> float:
        return self.file_path.stat().st_size / (1024 * 1024)


@dataclass
class MultiBatchSummary:
    """Resumen del análisis de múltiples archivos."""
    files: List[FileEntry]
    total_size_mb: float
    total_pages: int
    total_estimated_files: int
    global_strategy: str
    processing_time_estimate: float  # minutos
    warnings: List[str]
    
    @property
    def avg_density(self) -> float:
        if self.total_pages == 0:
            return 0
        return self.total_size_mb / self.total_pages


class MultiBatchProcessor:
    """Procesador para múltiples archivos PDF."""
    
    def __init__(self):
        self.optimizer = BatchOptimizer()
        
    def analyze_multiple_files(self, file_paths: List[str]) -> MultiBatchSummary:
        """Analiza múltiples archivos PDF y genera recomendaciones."""
        # Ordenar archivos por nombre (para mantener secuencia lógica)
        sorted_paths = self._sort_files_intelligently(file_paths)
        
        file_entries = []
        total_size = 0
        total_pages = 0
        total_files = 0
        warnings = []
        
        # Analizar cada archivo
        for i, file_path in enumerate(sorted_paths):
            try:
                entry = self._analyze_single_file(file_path, i)
                file_entries.append(entry)
                
                if entry.analysis:
                    total_size += entry.analysis.total_size_mb
                    total_pages += entry.analysis.total_pages
                    
                if entry.recommendation:
                    total_files += entry.recommendation.num_files
                    warnings.extend(entry.recommendation.warnings)
                    
            except Exception as e:
                warnings.append(f"Error analizando {os.path.basename(file_path)}: {str(e)}")
        
        # Estrategia global
        global_strategy = self._determine_global_strategy(file_entries)
        
        # Estimación de tiempo (asumiendo ~30s por archivo dividido)
        processing_time = total_files * 0.5  # minutos
        
        return MultiBatchSummary(
            files=file_entries,
            total_size_mb=total_size,
            total_pages=total_pages,
            total_estimated_files=total_files,
            global_strategy=global_strategy,
            processing_time_estimate=processing_time,
            warnings=list(set(warnings))  # Eliminar duplicados
        )
    
    def _sort_files_intelligently(self, file_paths: List[str]) -> List[str]:
        """Ordena archivos de forma inteligente (Volumen I, II, III, etc.)."""
        def extract_order_key(filepath):
            filename = os.path.basename(filepath).lower()
            
            # Buscar patrones comunes de numeración
            patterns = [
                (r'vol(?:umen)?[_\s]*(\d+)', 1),  # volumen_1, vol_2, etc.
                (r'tomo[_\s]*(\d+)', 1),          # tomo_1, tomo_2
                (r'parte[_\s]*(\d+)', 1),         # parte_1, parte_2
                (r'libro[_\s]*(\d+)', 1),         # libro_1, libro_2
                (r'capitulo[_\s]*(\d+)', 1),      # capitulo_1
                (r'(\d+)', 1),                    # cualquier número
                (r'vol(?:umen)?[_\s]*([ivx]+)', 2),  # volumen_i, vol_ii (romanos)
                (r'tomo[_\s]*([ivx]+)', 2),       # tomo_i, tomo_ii
            ]
            
            for pattern, num_type in patterns:
                match = re.search(pattern, filename)
                if match:
                    if num_type == 1:  # Números arábigos
                        return (0, int(match.group(1)))
                    else:  # Números romanos
                        roman_to_int = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5, 
                                       'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10}
                        return (0, roman_to_int.get(match.group(1), 999))
            
            # Si no hay patrón, ordenar alfabéticamente
            return (1, filename)
        
        return sorted(file_paths, key=extract_order_key)
    
    def _analyze_single_file(self, file_path: str, order_index: int) -> FileEntry:
        """Analiza un archivo individual."""
        path = Path(file_path)
        display_name = path.name
        
        entry = FileEntry(
            file_path=path,
            display_name=display_name,
            order_index=order_index
        )
        
        try:
            # Contar páginas
            from mistral_ocr_client_optimized import MistralOCRClient
            temp_client = MistralOCRClient()  # Solo para análisis
            pages_count = temp_client.estimate_pages_count(file_path)
            
            if pages_count:
                # Análisis detallado
                entry.analysis = self.optimizer.analyze_pdf(file_path, pages_count)
                entry.recommendation = self.optimizer.calculate_optimal_split(entry.analysis)
        
        except Exception as e:
            # Si falla, crear análisis básico
            size_mb = entry.file_size_mb
            entry.analysis = PDFAnalysis(
                file_path=path,
                total_size_mb=size_mb,
                total_pages=0,
                density_mb_per_page=0,
                requires_splitting=size_mb > 50,
                reason=f"No se pudo analizar: {str(e)}"
            )
        
        return entry
    
    def _determine_global_strategy(self, entries: List[FileEntry]) -> str:
        """Determina la estrategia global basada en todos los archivos."""
        if not entries:
            return "no-files"
        
        requires_split = any(e.analysis and e.analysis.requires_splitting for e in entries)
        high_density_count = sum(1 for e in entries 
                                if e.analysis and e.analysis.density_mb_per_page > 1.0)
        low_density_count = sum(1 for e in entries 
                               if e.analysis and e.analysis.density_mb_per_page < 0.1)
        
        total_files = len(entries)
        
        if not requires_split:
            return "direct-processing"
        elif high_density_count > total_files * 0.6:
            return "image-heavy-collection"
        elif low_density_count > total_files * 0.6:
            return "text-heavy-collection"
        else:
            return "mixed-content-collection"
    
    def generate_processing_plan(self, summary: MultiBatchSummary) -> Dict:
        """Genera plan detallado de procesamiento."""
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
                    # Procesar directamente
                    file_plan['operations'].append({
                        'type': 'direct_process',
                        'pages': entry.analysis.total_pages,
                        'estimated_mb': entry.analysis.total_size_mb
                    })
                else:
                    # Dividir y procesar
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
        """Genera reporte formateado del análisis múltiple."""
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
    
    def get_file_processing_order(self, summary: MultiBatchSummary) -> List[Tuple[str, int, int]]:
        """Obtiene orden de procesamiento con offsets de página."""
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


# Funciones de utilidad
def analyze_multiple_pdfs(file_paths: List[str]) -> MultiBatchSummary:
    """Función principal para análisis múltiple."""
    processor = MultiBatchProcessor()
    return processor.analyze_multiple_files(file_paths)


def get_processing_plan(file_paths: List[str]) -> Dict:
    """Obtiene plan completo de procesamiento."""
    processor = MultiBatchProcessor()
    summary = processor.analyze_multiple_files(file_paths)
    return processor.generate_processing_plan(summary)