#!/usr/bin/env python3
"""
Batch Optimizer - Optimizador inteligente de procesamiento por lotes
Analiza archivos PDF y recomienda la mejor estrategia de división.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from pathlib import Path


@dataclass
class PDFAnalysis:
    """Análisis detallado de un archivo PDF."""
    file_path: Path
    total_size_mb: float
    total_pages: int
    density_mb_per_page: float
    requires_splitting: bool
    reason: str = ""
    
    @property
    def size_gb(self) -> float:
        """Tamaño en GB para archivos grandes."""
        return self.total_size_mb / 1024


@dataclass
class SplitRecommendation:
    """Recomendación de división optimizada."""
    num_files: int
    pages_per_file: int
    estimated_mb_per_file: float
    total_pages: int
    total_size_mb: float
    strategy: str
    efficiency_score: float
    warnings: List[str]
    
    @property
    def is_optimal(self) -> bool:
        """Verifica si la recomendación es óptima."""
        return (self.estimated_mb_per_file <= 50 and 
                self.pages_per_file <= 150 and
                self.efficiency_score >= 0.8)


class BatchOptimizer:
    """Optimizador inteligente para procesamiento por lotes."""

    # Límites de la API (optimizados para mejor rendimiento)
    MAX_SIZE_MB = 48.0  # Aumentado de 45MB a 48MB (96% del límite API de 50MB)
    MAX_PAGES = 145     # Aumentado de 135 a 145 páginas (97% del límite API de 150)

    # Factores de seguridad (un solo margen, más eficiente)
    SAFETY_FACTOR_SIZE = 0.97  # 97% del límite (aumentado de 95%)
    SAFETY_FACTOR_PAGES = 0.97  # 97% del límite de páginas (sin cambio)

    # Overhead estimado por archivo PDF
    PDF_OVERHEAD_MB = 0.5
    
    def __init__(self):
        self.safe_max_size = self.MAX_SIZE_MB * self.SAFETY_FACTOR_SIZE
        self.safe_max_pages = int(self.MAX_PAGES * self.SAFETY_FACTOR_PAGES)
    
    def analyze_pdf(self, file_path: str, total_pages: int) -> PDFAnalysis:
        """Analiza un archivo PDF y determina si necesita división."""
        path = Path(file_path)
        size_mb = path.stat().st_size / (1024 * 1024)
        density = size_mb / total_pages if total_pages > 0 else 0
        
        # Determinar si requiere división
        requires_split = False
        reason = ""
        
        if size_mb > self.MAX_SIZE_MB:
            requires_split = True
            reason = f"Tamaño excede límite ({size_mb:.1f}MB > {self.MAX_SIZE_MB}MB)"
        elif total_pages > self.MAX_PAGES:
            requires_split = True
            reason = f"Páginas exceden límite ({total_pages} > {self.MAX_PAGES})"
        
        return PDFAnalysis(
            file_path=path,
            total_size_mb=size_mb,
            total_pages=total_pages,
            density_mb_per_page=density,
            requires_splitting=requires_split,
            reason=reason
        )
    
    def calculate_optimal_split(self, analysis: PDFAnalysis) -> SplitRecommendation:
        """Calcula la división óptima basada en peso y páginas."""
        if not analysis.requires_splitting:
            return self._no_split_recommendation(analysis)
        
        # Calcular divisiones mínimas requeridas
        min_files_by_size = math.ceil(analysis.total_size_mb / self.safe_max_size)
        min_files_by_pages = math.ceil(analysis.total_pages / self.safe_max_pages)
        
        # El número real debe satisfacer ambas restricciones
        required_files = max(min_files_by_size, min_files_by_pages)
        
        # Intentar encontrar una división balanceada
        best_recommendation = None
        best_score = 0
        
        # Probar diferentes números de archivos
        for num_files in range(required_files, required_files + 3):
            recommendation = self._evaluate_split(analysis, num_files)
            if recommendation.efficiency_score > best_score:
                best_score = recommendation.efficiency_score
                best_recommendation = recommendation
        
        return best_recommendation
    
    def _evaluate_split(self, analysis: PDFAnalysis, num_files: int) -> SplitRecommendation:
        """Evalúa una configuración de división específica."""
        pages_per_file = math.ceil(analysis.total_pages / num_files)
        mb_per_file = (analysis.total_size_mb / num_files) + self.PDF_OVERHEAD_MB
        
        warnings = []
        strategy = "balanced"
        
        # Verificar límites
        if mb_per_file > self.safe_max_size:
            warnings.append(f"Archivos pueden exceder límite de tamaño ({mb_per_file:.1f}MB)")
            strategy = "size-constrained"
        
        if pages_per_file > self.safe_max_pages:
            warnings.append(f"Archivos pueden exceder límite de páginas ({pages_per_file})")
            strategy = "page-constrained"
        
        # Calcular puntuación de eficiencia
        size_efficiency = min(1.0, self.safe_max_size / mb_per_file)
        page_efficiency = min(1.0, self.safe_max_pages / pages_per_file)
        balance_score = 1.0 - (abs(size_efficiency - page_efficiency) * 0.5)
        
        # Penalizar por demasiados archivos
        file_penalty = max(0, (num_files - 5) * 0.05)
        
        efficiency_score = (size_efficiency * 0.4 + 
                          page_efficiency * 0.4 + 
                          balance_score * 0.2) - file_penalty
        
        # Ajustar estrategia basada en densidad
        if analysis.density_mb_per_page > 1.0:
            strategy = "high-density" if strategy == "balanced" else f"{strategy}-high-density"
        elif analysis.density_mb_per_page < 0.1:
            strategy = "low-density" if strategy == "balanced" else f"{strategy}-low-density"
        
        return SplitRecommendation(
            num_files=num_files,
            pages_per_file=pages_per_file,
            estimated_mb_per_file=mb_per_file,
            total_pages=analysis.total_pages,
            total_size_mb=analysis.total_size_mb,
            strategy=strategy,
            efficiency_score=efficiency_score,
            warnings=warnings
        )
    
    def _no_split_recommendation(self, analysis: PDFAnalysis) -> SplitRecommendation:
        """Recomendación cuando no se requiere división."""
        return SplitRecommendation(
            num_files=1,
            pages_per_file=analysis.total_pages,
            estimated_mb_per_file=analysis.total_size_mb,
            total_pages=analysis.total_pages,
            total_size_mb=analysis.total_size_mb,
            strategy="no-split-required",
            efficiency_score=1.0,
            warnings=[]
        )
    
    def get_alternative_recommendations(self, analysis: PDFAnalysis) -> List[SplitRecommendation]:
        """Genera recomendaciones alternativas para el usuario."""
        if not analysis.requires_splitting:
            return [self._no_split_recommendation(analysis)]
        
        alternatives = []
        
        # Opción 1: Mínimo número de archivos
        min_files = max(
            math.ceil(analysis.total_size_mb / self.safe_max_size),
            math.ceil(analysis.total_pages / self.safe_max_pages)
        )
        alternatives.append(self._evaluate_split(analysis, min_files))
        
        # Opción 2: Archivos más pequeños para mejor procesamiento
        comfort_files = min_files + 1
        alternatives.append(self._evaluate_split(analysis, comfort_files))
        
        # Opción 3: División por capítulos comunes (50, 100 páginas)
        for chunk_size in [50, 100]:
            if chunk_size < analysis.total_pages:
                num_files = math.ceil(analysis.total_pages / chunk_size)
                rec = self._evaluate_split(analysis, num_files)
                if rec.is_optimal:
                    alternatives.append(rec)
        
        # Ordenar por puntuación
        alternatives.sort(key=lambda x: x.efficiency_score, reverse=True)
        
        # Eliminar duplicados
        seen = set()
        unique_alternatives = []
        for alt in alternatives:
            key = (alt.num_files, alt.pages_per_file)
            if key not in seen:
                seen.add(key)
                unique_alternatives.append(alt)
        
        return unique_alternatives[:3]  # Top 3 opciones
    
    def format_recommendation(self, rec: SplitRecommendation) -> str:
        """Formatea una recomendación para mostrar al usuario."""
        lines = []
        
        if rec.num_files == 1:
            lines.append("✅ No se requiere división")
            lines.append(f"   El archivo puede procesarse directamente")
        else:
            lines.append(f"📊 División recomendada: {rec.num_files} archivos")
            lines.append(f"   • Páginas por archivo: {rec.pages_per_file}")
            lines.append(f"   • Tamaño estimado por archivo: {rec.estimated_mb_per_file:.1f} MB")
            lines.append(f"   • Estrategia: {rec.strategy}")
            lines.append(f"   • Puntuación de eficiencia: {rec.efficiency_score:.0%}")
        
        if rec.warnings:
            lines.append("   ⚠️ Advertencias:")
            for warning in rec.warnings:
                lines.append(f"      - {warning}")
        
        return "\n".join(lines)
    
    def get_summary_report(self, analysis: PDFAnalysis, 
                          recommendations: List[SplitRecommendation]) -> str:
        """Genera un reporte completo del análisis."""
        lines = [
            "=" * 60,
            "ANÁLISIS DE ARCHIVO PDF",
            "=" * 60,
            f"Archivo: {analysis.file_path.name}",
            f"Tamaño total: {analysis.total_size_mb:.1f} MB",
            f"Páginas totales: {analysis.total_pages}",
            f"Densidad: {analysis.density_mb_per_page:.2f} MB/página",
            ""
        ]
        
        if analysis.density_mb_per_page > 1.0:
            lines.append("📸 Archivo con alta densidad (muchas imágenes)")
        elif analysis.density_mb_per_page < 0.1:
            lines.append("📝 Archivo con baja densidad (principalmente texto)")
        
        if analysis.requires_splitting:
            lines.extend([
                "",
                f"⚠️ División requerida: {analysis.reason}",
                ""
            ])
        
        lines.extend([
            "",
            "RECOMENDACIONES:",
            "-" * 60
        ])
        
        for i, rec in enumerate(recommendations, 1):
            if i == 1:
                lines.append(f"\n🏆 OPCIÓN {i} (RECOMENDADA):")
            else:
                lines.append(f"\n📋 OPCIÓN {i}:")
            lines.append(self.format_recommendation(rec))
        
        lines.extend([
            "",
            "=" * 60
        ])
        
        return "\n".join(lines)


# Funciones de utilidad para integración fácil
def analyze_and_recommend(file_path: str, total_pages: int) -> Tuple[PDFAnalysis, List[SplitRecommendation]]:
    """Función principal para análisis y recomendaciones."""
    optimizer = BatchOptimizer()
    analysis = optimizer.analyze_pdf(file_path, total_pages)
    
    if analysis.requires_splitting:
        # Obtener recomendación principal y alternativas
        main_rec = optimizer.calculate_optimal_split(analysis)
        alternatives = optimizer.get_alternative_recommendations(analysis)
        
        # Asegurar que la principal esté primera
        recommendations = [main_rec]
        for alt in alternatives:
            if alt.num_files != main_rec.num_files:
                recommendations.append(alt)
    else:
        recommendations = [optimizer._no_split_recommendation(analysis)]
    
    return analysis, recommendations


def get_quick_recommendation(file_path: str, total_pages: int) -> SplitRecommendation:
    """Obtiene rápidamente la mejor recomendación."""
    optimizer = BatchOptimizer()
    analysis = optimizer.analyze_pdf(file_path, total_pages)
    return optimizer.calculate_optimal_split(analysis)