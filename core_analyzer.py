#!/usr/bin/env python3
"""
Core Analyzer - Analizador Central de Archivos PDF
===================================================
Módulo consolidado que centraliza toda la lógica de análisis, validación
y cálculo de división de archivos PDF.

Este módulo elimina la duplicación de código presente en:
- batch_optimizer.py
- pre_division_validator.py
- pdf_split_validator.py

Versión: 1.0.0 - Consolidación Fase 1
"""

import math
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger('core_analyzer')


@dataclass
class FileMetrics:
    """Métricas básicas de un archivo PDF"""
    file_path: Path
    size_mb: float
    total_pages: int
    density_mb_per_page: float

    @property
    def size_gb(self) -> float:
        """Tamaño en GB para archivos grandes."""
        return self.size_mb / 1024


@dataclass
class SplitLimits:
    """Límites configurables para división de archivos"""
    max_size_mb: float = 48.0
    max_pages: int = 145
    safety_factor_size: float = 0.97
    safety_factor_pages: float = 0.97
    pdf_overhead_mb: float = 0.5

    @property
    def safe_max_size(self) -> float:
        """Tamaño máximo seguro con margen de seguridad"""
        return self.max_size_mb * self.safety_factor_size

    @property
    def safe_max_pages(self) -> int:
        """Páginas máximas seguras con margen de seguridad"""
        return int(self.max_pages * self.safety_factor_pages)


@dataclass
class SplitAnalysis:
    """Análisis completo de división de archivos"""
    metrics: FileMetrics
    limits: SplitLimits
    requires_splitting: bool
    reason: str = ""
    min_files_by_size: int = 1
    min_files_by_pages: int = 1
    required_files: int = 1

    @property
    def exceeds_size_limit(self) -> bool:
        """Verifica si excede límite de tamaño"""
        return self.metrics.size_mb > self.limits.max_size_mb

    @property
    def exceeds_page_limit(self) -> bool:
        """Verifica si excede límite de páginas"""
        return self.metrics.total_pages > self.limits.max_pages


@dataclass
class SplitPlan:
    """Plan de división optimizado"""
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
        """Verifica si el plan es óptimo"""
        return (self.estimated_mb_per_file <= 50 and
                self.pages_per_file <= 150 and
                self.efficiency_score >= 0.8)


class FileAnalyzer:
    """
    Analizador central de archivos PDF

    Consolida toda la lógica de:
    - Análisis de archivos (tamaño, páginas, densidad)
    - Validación de límites
    - Cálculo de división óptima
    - Recomendaciones de split
    """

    def __init__(self, limits: Optional[SplitLimits] = None):
        """
        Inicializa el analizador

        Args:
            limits: Límites personalizados (usa defaults si no se especifica)
        """
        self.limits = limits or SplitLimits()
        logger.info(f"FileAnalyzer inicializado: {self.limits.max_size_mb}MB, {self.limits.max_pages} páginas")

    @staticmethod
    def get_file_metrics(file_path: Path, total_pages: Optional[int] = None) -> FileMetrics:
        """
        Obtiene métricas básicas de un archivo PDF

        Esta función centraliza el cálculo repetido en múltiples módulos:
        - size_mb = file_path.stat().st_size / (1024 * 1024)
        - density = size_mb / total_pages

        Args:
            file_path: Ruta al archivo PDF
            total_pages: Número de páginas (si se conoce)

        Returns:
            FileMetrics con toda la información calculada
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        # Cálculo unificado de tamaño (antes duplicado 15+ veces)
        size_mb = file_path.stat().st_size / (1024 * 1024)

        # Obtener páginas si no se proporcionan
        if total_pages is None:
            try:
                from PyPDF2 import PdfReader
                pdf = PdfReader(file_path)
                total_pages = len(pdf.pages)
            except Exception as e:
                logger.warning(f"No se pudo leer PDF, estimando páginas: {e}")
                # Estimación: ~4 páginas por MB
                total_pages = max(1, int(size_mb * 4))

        # Cálculo unificado de densidad (antes duplicado 8+ veces)
        density = size_mb / total_pages if total_pages > 0 else 0

        return FileMetrics(
            file_path=file_path,
            size_mb=size_mb,
            total_pages=total_pages,
            density_mb_per_page=density
        )

    def analyze_split_needs(self, metrics: FileMetrics) -> SplitAnalysis:
        """
        Analiza si un archivo necesita división

        Centraliza la lógica duplicada de validación de límites presente en:
        - batch_optimizer.py (líneas 77-82)
        - pre_division_validator.py (líneas 112-114)
        - pdf_split_validator.py (líneas 112-114)

        Args:
            metrics: Métricas del archivo

        Returns:
            SplitAnalysis con resultado completo
        """
        requires_split = False
        reason = ""

        # Validación unificada de límites (antes duplicada 12+ veces)
        if metrics.size_mb > self.limits.max_size_mb:
            requires_split = True
            reason = f"Tamaño excede límite ({metrics.size_mb:.1f}MB > {self.limits.max_size_mb}MB)"
        elif metrics.total_pages > self.limits.max_pages:
            requires_split = True
            reason = f"Páginas exceden límite ({metrics.total_pages} > {self.limits.max_pages})"

        # Cálculo unificado de archivos necesarios (antes duplicado 9+ veces)
        min_files_by_size = math.ceil(metrics.size_mb / self.limits.safe_max_size)
        min_files_by_pages = math.ceil(metrics.total_pages / self.limits.safe_max_pages)
        required_files = max(min_files_by_size, min_files_by_pages)

        return SplitAnalysis(
            metrics=metrics,
            limits=self.limits,
            requires_splitting=requires_split,
            reason=reason,
            min_files_by_size=min_files_by_size,
            min_files_by_pages=min_files_by_pages,
            required_files=required_files
        )

    def calculate_split_plan(self, analysis: SplitAnalysis, num_files: Optional[int] = None) -> SplitPlan:
        """
        Calcula plan de división optimizado

        Centraliza la lógica duplicada presente en:
        - batch_optimizer.py (_evaluate_split, líneas 118-162)
        - pdf_split_validator.py (calculate_optimal_split, líneas 249-294)
        - pre_division_validator.py (_calculate_optimal_files, líneas 156-165)

        Args:
            analysis: Análisis de necesidades de split
            num_files: Número específico de archivos (None = calcular óptimo)

        Returns:
            SplitPlan con la división calculada
        """
        if not analysis.requires_splitting:
            return self._no_split_plan(analysis)

        # Si no se especifica, usar el número requerido
        if num_files is None:
            num_files = analysis.required_files

        # Cálculos de división (lógica unificada)
        pages_per_file = math.ceil(analysis.metrics.total_pages / num_files)
        mb_per_file = (analysis.metrics.size_mb / num_files) + self.limits.pdf_overhead_mb

        warnings = []
        strategy = "balanced"

        # Verificar límites
        if mb_per_file > self.limits.safe_max_size:
            warnings.append(f"Archivos pueden exceder límite de tamaño ({mb_per_file:.1f}MB)")
            strategy = "size-constrained"

        if pages_per_file > self.limits.safe_max_pages:
            warnings.append(f"Archivos pueden exceder límite de páginas ({pages_per_file})")
            strategy = "page-constrained"

        # Calcular puntuación de eficiencia
        size_efficiency = min(1.0, self.limits.safe_max_size / mb_per_file) if mb_per_file > 0 else 0
        page_efficiency = min(1.0, self.limits.safe_max_pages / pages_per_file) if pages_per_file > 0 else 0
        balance_score = 1.0 - (abs(size_efficiency - page_efficiency) * 0.5)

        # Penalizar por demasiados archivos
        file_penalty = max(0, (num_files - 5) * 0.05)

        efficiency_score = (size_efficiency * 0.4 +
                          page_efficiency * 0.4 +
                          balance_score * 0.2) - file_penalty

        # Ajustar estrategia basada en densidad
        if analysis.metrics.density_mb_per_page > 1.0:
            strategy = "high-density" if strategy == "balanced" else f"{strategy}-high-density"
        elif analysis.metrics.density_mb_per_page < 0.1:
            strategy = "low-density" if strategy == "balanced" else f"{strategy}-low-density"

        return SplitPlan(
            num_files=num_files,
            pages_per_file=pages_per_file,
            estimated_mb_per_file=mb_per_file,
            total_pages=analysis.metrics.total_pages,
            total_size_mb=analysis.metrics.size_mb,
            strategy=strategy,
            efficiency_score=efficiency_score,
            warnings=warnings
        )

    def get_optimal_split_plan(self, analysis: SplitAnalysis) -> SplitPlan:
        """
        Obtiene el plan de división óptimo evaluando múltiples opciones

        Args:
            analysis: Análisis de necesidades de split

        Returns:
            SplitPlan óptimo
        """
        if not analysis.requires_splitting:
            return self._no_split_plan(analysis)

        best_plan = None
        best_score = 0

        # Probar diferentes números de archivos
        for num_files in range(analysis.required_files, analysis.required_files + 3):
            plan = self.calculate_split_plan(analysis, num_files)
            if plan.efficiency_score > best_score:
                best_score = plan.efficiency_score
                best_plan = plan

        return best_plan

    def get_alternative_plans(self, analysis: SplitAnalysis) -> List[SplitPlan]:
        """
        Genera planes de división alternativos

        Args:
            analysis: Análisis de necesidades de split

        Returns:
            Lista de planes alternativos ordenados por eficiencia
        """
        if not analysis.requires_splitting:
            return [self._no_split_plan(analysis)]

        alternatives = []

        # Opción 1: Mínimo número de archivos
        alternatives.append(self.calculate_split_plan(analysis, analysis.required_files))

        # Opción 2: Archivos más pequeños para mejor procesamiento
        comfort_files = analysis.required_files + 1
        alternatives.append(self.calculate_split_plan(analysis, comfort_files))

        # Opción 3: División por capítulos comunes (50, 100 páginas)
        for chunk_size in [50, 100]:
            if chunk_size < analysis.metrics.total_pages:
                num_files = math.ceil(analysis.metrics.total_pages / chunk_size)
                plan = self.calculate_split_plan(analysis, num_files)
                if plan.is_optimal:
                    alternatives.append(plan)

        # Ordenar por puntuación y eliminar duplicados
        alternatives.sort(key=lambda x: x.efficiency_score, reverse=True)

        seen = set()
        unique_alternatives = []
        for alt in alternatives:
            key = (alt.num_files, alt.pages_per_file)
            if key not in seen:
                seen.add(key)
                unique_alternatives.append(alt)

        return unique_alternatives[:3]  # Top 3 opciones

    def _no_split_plan(self, analysis: SplitAnalysis) -> SplitPlan:
        """Plan cuando no se requiere división"""
        return SplitPlan(
            num_files=1,
            pages_per_file=analysis.metrics.total_pages,
            estimated_mb_per_file=analysis.metrics.size_mb,
            total_pages=analysis.metrics.total_pages,
            total_size_mb=analysis.metrics.size_mb,
            strategy="no-split-required",
            efficiency_score=1.0,
            warnings=[]
        )

    def format_plan(self, plan: SplitPlan) -> str:
        """Formatea un plan para mostrar al usuario"""
        lines = []

        if plan.num_files == 1:
            lines.append("✅ No se requiere división")
            lines.append(f"   El archivo puede procesarse directamente")
        else:
            lines.append(f"📊 División recomendada: {plan.num_files} archivos")
            lines.append(f"   • Páginas por archivo: {plan.pages_per_file}")
            lines.append(f"   • Tamaño estimado por archivo: {plan.estimated_mb_per_file:.1f} MB")
            lines.append(f"   • Estrategia: {plan.strategy}")
            lines.append(f"   • Puntuación de eficiencia: {plan.efficiency_score:.0%}")

        if plan.warnings:
            lines.append("   ⚠️ Advertencias:")
            for warning in plan.warnings:
                lines.append(f"      - {warning}")

        return "\n".join(lines)


# Funciones de utilidad para compatibilidad con código existente
def quick_analyze(file_path: str, total_pages: Optional[int] = None,
                 max_size_mb: float = 48.0, max_pages: int = 145) -> Tuple[FileMetrics, SplitAnalysis, SplitPlan]:
    """
    Función rápida de análisis completo

    Args:
        file_path: Ruta al archivo
        total_pages: Número de páginas (opcional)
        max_size_mb: Límite de tamaño
        max_pages: Límite de páginas

    Returns:
        Tuple (metrics, analysis, optimal_plan)
    """
    limits = SplitLimits(max_size_mb=max_size_mb, max_pages=max_pages)
    analyzer = FileAnalyzer(limits)

    metrics = FileAnalyzer.get_file_metrics(Path(file_path), total_pages)
    analysis = analyzer.analyze_split_needs(metrics)
    optimal_plan = analyzer.get_optimal_split_plan(analysis)

    return metrics, analysis, optimal_plan
