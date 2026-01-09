#!/usr/bin/env python3
"""
Batch Optimizer - Optimizador inteligente de procesamiento por lotes
Analiza archivos PDF y recomienda la mejor estrategia de división.

NOTA: Este módulo ahora usa core_analyzer.py para eliminar código duplicado.
Las clases PDFAnalysis y SplitRecommendation se mantienen por compatibilidad.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from core_analyzer import FileAnalyzer, SplitLimits, FileMetrics, SplitAnalysis, SplitPlan
from processing_limits import LIMITS


@dataclass
class PDFAnalysis:
    """
    Análisis detallado de un archivo PDF.

    DEPRECATED: Usar FileMetrics y SplitAnalysis de core_analyzer.py
    Esta clase se mantiene por compatibilidad con código existente.
    """
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

    @staticmethod
    def from_core_analysis(metrics: FileMetrics, analysis: SplitAnalysis) -> 'PDFAnalysis':
        """Crea PDFAnalysis desde análisis de core_analyzer"""
        return PDFAnalysis(
            file_path=metrics.file_path,
            total_size_mb=metrics.size_mb,
            total_pages=metrics.total_pages,
            density_mb_per_page=metrics.density_mb_per_page,
            requires_splitting=analysis.requires_splitting,
            reason=analysis.reason
        )


@dataclass
class SplitRecommendation:
    """
    Recomendación de división optimizada.

    DEPRECATED: Usar SplitPlan de core_analyzer.py
    Esta clase se mantiene por compatibilidad con código existente.
    """
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
        return (self.estimated_mb_per_file <= LIMITS.safe_max_size_mb and
                self.pages_per_file <= LIMITS.safe_max_pages and
                self.efficiency_score >= 0.8)

    @staticmethod
    def from_split_plan(plan: SplitPlan) -> 'SplitRecommendation':
        """Crea SplitRecommendation desde SplitPlan de core_analyzer"""
        return SplitRecommendation(
            num_files=plan.num_files,
            pages_per_file=plan.pages_per_file,
            estimated_mb_per_file=plan.estimated_mb_per_file,
            total_pages=plan.total_pages,
            total_size_mb=plan.total_size_mb,
            strategy=plan.strategy,
            efficiency_score=plan.efficiency_score,
            warnings=plan.warnings
        )


class BatchOptimizer:
    """
    Optimizador inteligente para procesamiento por lotes.

    REFACTORIZADO: Ahora usa FileAnalyzer de core_analyzer.py internamente.
    La interfaz pública se mantiene igual por compatibilidad.

    LÍMITES: Ahora obtiene límites de processing_limits.py para consistencia.
    """

    def __init__(self):
        # Usar límites centralizados desde processing_limits
        self.limits = SplitLimits(
            max_size_mb=LIMITS.SAFE_MAX_SIZE_MB,
            max_pages=LIMITS.SAFE_MAX_PAGES,
            safety_factor_size=LIMITS.SAFETY_FACTOR_SIZE,
            safety_factor_pages=LIMITS.SAFETY_FACTOR_PAGES,
            pdf_overhead_mb=LIMITS.PDF_OVERHEAD_MB
        )
        self.analyzer = FileAnalyzer(self.limits)

        # Mantener compatibilidad con código legacy
        self.safe_max_size = self.limits.safe_max_size
        self.safe_max_pages = self.limits.safe_max_pages

        # Aliases para compatibilidad
        self.MAX_SIZE_MB = LIMITS.SAFE_MAX_SIZE_MB
        self.MAX_PAGES = LIMITS.SAFE_MAX_PAGES
        self.SAFETY_FACTOR_SIZE = LIMITS.SAFETY_FACTOR_SIZE
        self.SAFETY_FACTOR_PAGES = LIMITS.SAFETY_FACTOR_PAGES
        self.PDF_OVERHEAD_MB = LIMITS.PDF_OVERHEAD_MB

    def analyze_pdf(self, file_path: str, total_pages: int) -> PDFAnalysis:
        """
        Analiza un archivo PDF y determina si necesita división.

        REFACTORIZADO: Usa FileAnalyzer.get_file_metrics() y analyze_split_needs()
        """
        path = Path(file_path)

        # Usar FileAnalyzer para obtener métricas (elimina código duplicado)
        metrics = FileAnalyzer.get_file_metrics(path, total_pages)
        analysis = self.analyzer.analyze_split_needs(metrics)

        # Convertir a PDFAnalysis para compatibilidad
        return PDFAnalysis.from_core_analysis(metrics, analysis)

    def calculate_optimal_split(self, analysis: PDFAnalysis) -> SplitRecommendation:
        """
        Calcula la división óptima basada en peso y páginas.

        REFACTORIZADO: Usa FileAnalyzer.get_optimal_split_plan()
        """
        # Crear análisis de core_analyzer desde PDFAnalysis legacy
        metrics = FileMetrics(
            file_path=analysis.file_path,
            size_mb=analysis.total_size_mb,
            total_pages=analysis.total_pages,
            density_mb_per_page=analysis.density_mb_per_page
        )
        split_analysis = self.analyzer.analyze_split_needs(metrics)

        # Obtener plan óptimo
        plan = self.analyzer.get_optimal_split_plan(split_analysis)

        # Convertir a SplitRecommendation para compatibilidad
        return SplitRecommendation.from_split_plan(plan)

    def _evaluate_split(self, analysis: PDFAnalysis, num_files: int) -> SplitRecommendation:
        """
        Evalúa una configuración de división específica.

        REFACTORIZADO: Usa FileAnalyzer.calculate_split_plan()
        """
        # Crear análisis de core_analyzer
        metrics = FileMetrics(
            file_path=analysis.file_path,
            size_mb=analysis.total_size_mb,
            total_pages=analysis.total_pages,
            density_mb_per_page=analysis.density_mb_per_page
        )
        split_analysis = self.analyzer.analyze_split_needs(metrics)

        # Calcular plan específico
        plan = self.analyzer.calculate_split_plan(split_analysis, num_files)

        # Convertir a SplitRecommendation
        return SplitRecommendation.from_split_plan(plan)

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
        """
        Genera recomendaciones alternativas para el usuario.

        REFACTORIZADO: Usa FileAnalyzer.get_alternative_plans()
        """
        # Crear análisis de core_analyzer
        metrics = FileMetrics(
            file_path=analysis.file_path,
            size_mb=analysis.total_size_mb,
            total_pages=analysis.total_pages,
            density_mb_per_page=analysis.density_mb_per_page
        )
        split_analysis = self.analyzer.analyze_split_needs(metrics)

        # Obtener planes alternativos
        plans = self.analyzer.get_alternative_plans(split_analysis)

        # Convertir a SplitRecommendation
        return [SplitRecommendation.from_split_plan(plan) for plan in plans]
    
    def format_recommendation(self, rec: SplitRecommendation) -> str:
        """
        Formatea una recomendación para mostrar al usuario.

        REFACTORIZADO: Usa FileAnalyzer.format_plan()
        """
        # Convertir a SplitPlan y usar format_plan
        plan = SplitPlan(
            num_files=rec.num_files,
            pages_per_file=rec.pages_per_file,
            estimated_mb_per_file=rec.estimated_mb_per_file,
            total_pages=rec.total_pages,
            total_size_mb=rec.total_size_mb,
            strategy=rec.strategy,
            efficiency_score=rec.efficiency_score,
            warnings=rec.warnings
        )
        return self.analyzer.format_plan(plan)
    
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