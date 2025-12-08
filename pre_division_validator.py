#!/usr/bin/env python3
"""
Pre-Division Validator - Validación ANTES de Crear Archivos
=========================================================
Sistema que calcula y valida tamaños estimados ANTES de dividir físicamente
el PDF, evitando crear archivos innecesarios que excedan límites.

Versión: 1.0.0 - Validación Preventiva
Funcionalidad: Estimación precisa de tamaños pre-división
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging
import math

# Configuración
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('pre_division_validator')

@dataclass
class EstimatedFile:
    """Información de archivo estimado pre-división"""
    index: int
    estimated_size_mb: float
    pages: int
    page_range: str
    exceeds_limit: bool
    recommended_split: Optional[int] = None

@dataclass
class PreDivisionAnalysis:
    """Análisis completo pre-división"""
    original_file: Path
    original_size_mb: float
    total_pages: int
    requested_num_files: int
    estimated_files: List[EstimatedFile]
    all_within_limits: bool
    files_exceeding_limits: int
    recommended_num_files: int
    size_efficiency: float
    
class PreDivisionValidator:
    """Validador que estima tamaños ANTES de crear archivos físicos"""
    
    def __init__(self, max_size_mb: float = 50.0, max_pages: int = 135):
        self.max_size_mb = max_size_mb
        self.max_pages = max_pages
        logger.info(f"Pre-validator inicializado: {max_size_mb}MB, {max_pages} páginas máx")
    
    def analyze_division_plan(self, file_path: Path, num_files: int, 
                            pages_per_file: Optional[List[int]] = None) -> PreDivisionAnalysis:
        """
        Analizar plan de división ANTES de crear archivos físicos
        
        Args:
            file_path: Ruta del archivo original
            num_files: Número de archivos a crear
            pages_per_file: Lista opcional de páginas por archivo
            
        Returns:
            PreDivisionAnalysis con estimaciones detalladas
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
        
        # Obtener información básica
        original_size_mb = file_path.stat().st_size / (1024 * 1024)
        
        # Estimar páginas si no se proporcionan
        try:
            from PyPDF2 import PdfReader
            pdf = PdfReader(file_path)
            total_pages = len(pdf.pages)
        except Exception as e:
            logger.warning(f"No se pudo leer PDF, estimando páginas: {e}")
            # Estimación basada en tamaño (aproximadamente 4 páginas por MB)
            total_pages = max(1, int(original_size_mb * 4))
        
        logger.info(f"Analizando división: {original_size_mb:.1f}MB, {total_pages} páginas → {num_files} archivos")
        
        # Calcular distribución de páginas
        if pages_per_file:
            if len(pages_per_file) != num_files:
                raise ValueError("La lista de páginas debe tener la misma longitud que num_files")
            pages_distribution = pages_per_file
        else:
            # Distribución uniforme
            base_pages = total_pages // num_files
            extra_pages = total_pages % num_files
            pages_distribution = [base_pages + (1 if i < extra_pages else 0) for i in range(num_files)]
        
        # Estimar tamaños de archivos resultantes
        estimated_files = []
        files_exceeding_limits = 0
        size_per_page = original_size_mb / total_pages
        
        current_page = 1
        for i in range(num_files):
            pages = pages_distribution[i]
            estimated_size = pages * size_per_page
            
            # Agregar overhead de PDF (headers, estructura, etc.)
            # Típicamente 2-5% del tamaño original
            overhead_factor = 1.03
            estimated_size *= overhead_factor
            
            exceeds_limit = estimated_size > self.max_size_mb
            if exceeds_limit:
                files_exceeding_limits += 1
            
            # Calcular división recomendada para este archivo si excede
            recommended_split = None
            if exceeds_limit:
                recommended_split = math.ceil(estimated_size / self.max_size_mb)
            
            estimated_file = EstimatedFile(
                index=i,
                estimated_size_mb=estimated_size,
                pages=pages,
                page_range=f"Páginas {current_page}-{current_page + pages - 1}",
                exceeds_limit=exceeds_limit,
                recommended_split=recommended_split
            )
            
            estimated_files.append(estimated_file)
            current_page += pages
        
        # Calcular número recomendado de archivos
        recommended_num_files = self._calculate_optimal_files(original_size_mb, total_pages)
        
        # Calcular eficiencia de tamaño
        max_estimated_size = max(f.estimated_size_mb for f in estimated_files)
        size_efficiency = min(1.0, self.max_size_mb / max_estimated_size) if max_estimated_size > 0 else 1.0
        
        analysis = PreDivisionAnalysis(
            original_file=file_path,
            original_size_mb=original_size_mb,
            total_pages=total_pages,
            requested_num_files=num_files,
            estimated_files=estimated_files,
            all_within_limits=(files_exceeding_limits == 0),
            files_exceeding_limits=files_exceeding_limits,
            recommended_num_files=recommended_num_files,
            size_efficiency=size_efficiency
        )
        
        logger.info(f"Pre-análisis completado: {files_exceeding_limits}/{num_files} archivos excederán límites")
        
        return analysis
    
    def _calculate_optimal_files(self, size_mb: float, total_pages: int) -> int:
        """Calcular número óptimo de archivos"""
        # Basado en tamaño
        size_based = math.ceil(size_mb / (self.max_size_mb * 0.9))  # 90% del límite para margen
        
        # Basado en páginas
        page_based = math.ceil(total_pages / (self.max_pages * 0.9))  # 90% del límite para margen
        
        # Tomar el mayor para garantizar que ambos límites se respeten
        return max(size_based, page_based)
    
    def get_division_recommendations(self, analysis: PreDivisionAnalysis) -> List[Dict]:
        """
        Obtener recomendaciones de división alternativas
        
        Returns:
            Lista de opciones de división con métricas
        """
        recommendations = []
        
        # Opción 1: Número recomendado (óptimo)
        if analysis.recommended_num_files != analysis.requested_num_files:
            opt_analysis = self.analyze_division_plan(
                analysis.original_file, 
                analysis.recommended_num_files
            )
            
            recommendations.append({
                'type': 'recommended',
                'num_files': analysis.recommended_num_files,
                'description': f'División óptima ({analysis.recommended_num_files} archivos)',
                'estimated_max_size': max(f.estimated_size_mb for f in opt_analysis.estimated_files),
                'efficiency': opt_analysis.size_efficiency,
                'all_within_limits': opt_analysis.all_within_limits
            })
        
        # Opción 2: Conservadora (más archivos)
        conservative_files = analysis.recommended_num_files + 2
        if conservative_files <= 20:  # Límite práctico
            cons_analysis = self.analyze_division_plan(
                analysis.original_file, 
                conservative_files
            )
            
            recommendations.append({
                'type': 'conservative',
                'num_files': conservative_files,
                'description': f'División conservadora ({conservative_files} archivos)',
                'estimated_max_size': max(f.estimated_size_mb for f in cons_analysis.estimated_files),
                'efficiency': cons_analysis.size_efficiency,
                'all_within_limits': cons_analysis.all_within_limits
            })
        
        # Opción 3: Rápida (menos archivos pero seguros)
        if analysis.original_size_mb > 100:  # Solo para archivos grandes
            fast_files = max(2, analysis.recommended_num_files - 1)
            if fast_files != analysis.recommended_num_files:
                fast_analysis = self.analyze_division_plan(
                    analysis.original_file, 
                    fast_files
                )
                
                if fast_analysis.all_within_limits:
                    recommendations.append({
                        'type': 'fast',
                        'num_files': fast_files,
                        'description': f'División rápida ({fast_files} archivos)',
                        'estimated_max_size': max(f.estimated_size_mb for f in fast_analysis.estimated_files),
                        'efficiency': fast_analysis.size_efficiency,
                        'all_within_limits': fast_analysis.all_within_limits
                    })
        
        # Ordenar por eficiencia
        recommendations.sort(key=lambda x: x['efficiency'], reverse=True)
        
        return recommendations
    
    def validate_before_split(self, file_path: Path, num_files: int) -> Tuple[bool, PreDivisionAnalysis]:
        """
        Validación rápida antes de dividir
        
        Returns:
            (is_safe_to_proceed, analysis)
        """
        analysis = self.analyze_division_plan(file_path, num_files)
        
        # Es seguro proceder si todos los archivos están dentro de los límites
        is_safe = analysis.all_within_limits
        
        if not is_safe:
            logger.warning(f"ADVERTENCIA: {analysis.files_exceeding_limits}/{num_files} archivos excederán 50MB")
            for est_file in analysis.estimated_files:
                if est_file.exceeds_limit:
                    logger.warning(f"  - Archivo {est_file.index + 1}: ~{est_file.estimated_size_mb:.1f}MB (excede por {est_file.estimated_size_mb - self.max_size_mb:.1f}MB)")
        
        return is_safe, analysis

def create_size_estimation_report(analysis: PreDivisionAnalysis) -> str:
    """Crear reporte detallado de estimaciones"""
    report_lines = [
        "=" * 60,
        "📊 REPORTE DE ESTIMACIÓN PRE-DIVISIÓN",
        "=" * 60,
        f"📄 Archivo: {analysis.original_file.name}",
        f"📏 Tamaño original: {analysis.original_size_mb:.1f} MB",
        f"📑 Total páginas: {analysis.total_pages:,}",
        f"🔢 Archivos solicitados: {analysis.requested_num_files}",
        f"💡 Archivos recomendados: {analysis.recommended_num_files}",
        f"⚡ Eficiencia de tamaño: {analysis.size_efficiency:.0%}",
        "",
        "📋 ESTIMACIONES POR ARCHIVO:",
        "-" * 40
    ]
    
    for est_file in analysis.estimated_files:
        status = "❌ EXCEDE" if est_file.exceeds_limit else "✅ OK"
        report_lines.extend([
            f"Archivo {est_file.index + 1}: ~{est_file.estimated_size_mb:.1f}MB ({est_file.pages} pág) {status}",
            f"  └─ {est_file.page_range}"
        ])
        
        if est_file.exceeds_limit and est_file.recommended_split:
            report_lines.append(f"  └─ 💡 Recomendación: dividir en {est_file.recommended_split} partes")
    
    if not analysis.all_within_limits:
        report_lines.extend([
            "",
            "🚨 PROBLEMAS DETECTADOS:",
            f"❌ {analysis.files_exceeding_limits} archivos excederán el límite de 50MB",
            f"💡 Se recomienda usar {analysis.recommended_num_files} archivos en su lugar"
        ])
    
    report_lines.append("=" * 60)
    
    return "\n".join(report_lines)

# Test function
def test_pre_division_validator():
    """Función de prueba"""
    import tempfile
    
    # Crear archivo de prueba simulado
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        # Simular archivo de 265MB
        tmp.write(b'0' * (265 * 1024 * 1024))
        test_file = Path(tmp.name)
    
    try:
        validator = PreDivisionValidator(max_size_mb=50.0)
        
        # Probar con 5 archivos (que debería fallar)
        print("=== PRUEBA: División en 5 archivos ===")
        is_safe, analysis = validator.validate_before_split(test_file, 5)
        
        print(f"¿Es seguro proceder? {is_safe}")
        print(create_size_estimation_report(analysis))
        
        # Obtener recomendaciones
        recommendations = validator.get_division_recommendations(analysis)
        print(f"\n📋 RECOMENDACIONES ALTERNATIVAS:")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['description']}: ~{rec['estimated_max_size']:.1f}MB máx, "
                  f"eficiencia {rec['efficiency']:.0%}, "
                  f"{'✅ Seguro' if rec['all_within_limits'] else '❌ Problemático'}")
        
    finally:
        # Limpiar archivo de prueba
        test_file.unlink()

if __name__ == "__main__":
    test_pre_division_validator()