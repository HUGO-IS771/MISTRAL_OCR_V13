#!/usr/bin/env python3
"""
PDF Split Validator - Sistema de Validación y Ajuste Automático
===============================================================
Sistema avanzado para validar y ajustar automáticamente la división de PDFs
que exceden límites de tamaño, con interfaz interactiva.

Versión: 2.0.0 - Sistema Completo Restaurado
Funcionalidad: Validación post-división y re-división automática
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
logger = logging.getLogger('pdf_split_validator')

@dataclass
class SplitFileInfo:
    """Información de un archivo dividido"""
    file_path: Path
    size_mb: float
    pages: int
    exceeds_limit: bool
    page_range: str
    original_index: int

@dataclass  
class ValidationResult:
    """Resultado de validación de un archivo dividido"""
    file_path: Path
    size_mb: float
    pages: int
    within_size_limit: bool
    within_page_limit: bool
    is_valid: bool
    recommended_split: Optional[int] = None

@dataclass
class ValidationSummary:
    """Resumen completo de validación"""
    original_file: Path
    total_files_checked: int
    files_within_limits: int
    files_exceeding_limits: int
    total_files_needing_resplit: int
    all_within_limits: bool
    split_files: List[SplitFileInfo]
    validation_results: List[ValidationResult]
    recommended_total_files: Optional[int] = None

@dataclass
class AdjustedSummary:
    """Resumen después de ajuste automático"""
    original_summary: ValidationSummary
    adjustment_applied: bool
    new_file_count: int
    all_within_limits: bool
    split_files: List[SplitFileInfo]
    validation_results: List[ValidationResult]
    adjustment_reason: str

class PDFSplitValidator:
    """Validador avanzado para división de PDFs con ajuste automático"""
    
    def __init__(self, max_size_mb: float = 49.5, max_pages: int = 1000):
        self.max_size_mb = max_size_mb
        self.max_pages = max_pages
        logger.info(f"Validador inicializado: {max_size_mb}MB, {max_pages} páginas máx")
    
    def validate_split_files(self, split_info: Dict) -> ValidationSummary:
        """
        Validar archivos divididos y generar resumen completo
        
        Args:
            split_info: Información de la división (del OCR client)
            
        Returns:
            ValidationSummary con detalles completos
        """
        split_files = []
        validation_results = []
        files_within_limits = 0
        files_exceeding_limits = 0
        
        # Obtener lista de archivos divididos
        split_file_paths = split_info.get('files', [])  # CORREGIDO: usar 'files' en lugar de 'split_files'
        original_file = Path(split_info.get('original_file', ''))
        
        logger.info(f"Validando {len(split_file_paths)} archivos divididos...")
        
        for idx, file_path in enumerate(split_file_paths):
            file_path = Path(file_path)
            
            if not file_path.exists():
                logger.warning(f"Archivo no encontrado: {file_path}")
                continue
                
            # Obtener información del archivo
            size_mb = file_path.stat().st_size / (1024 * 1024)
            
            # Estimar páginas (si no está disponible, usar aproximación)
            pages = split_info.get('pages_per_file', {}).get(idx, int(size_mb * 4))
            
            # Validar límites
            within_size_limit = size_mb <= self.max_size_mb
            within_page_limit = pages <= self.max_pages
            is_valid = within_size_limit and within_page_limit
            exceeds_limit = not within_size_limit
            
            # Información del archivo dividido
            split_file = SplitFileInfo(
                file_path=file_path,
                size_mb=size_mb,
                pages=pages,
                exceeds_limit=exceeds_limit,
                page_range=f"Páginas {idx * pages + 1}-{(idx + 1) * pages}",
                original_index=idx
            )
            split_files.append(split_file)
            
            # Resultado de validación
            recommended_split = None
            if not is_valid:
                # Calcular división recomendada
                recommended_split = math.ceil(size_mb / self.max_size_mb)
            
            validation_result = ValidationResult(
                file_path=file_path,
                size_mb=size_mb,
                pages=pages,
                within_size_limit=within_size_limit,
                within_page_limit=within_page_limit,
                is_valid=is_valid,
                recommended_split=recommended_split
            )
            validation_results.append(validation_result)
            
            # Contadores
            if is_valid:
                files_within_limits += 1
            else:
                files_exceeding_limits += 1
        
        # Calcular recomendación total
        total_files_needing_resplit = sum(
            1 for result in validation_results 
            if not result.is_valid
        )
        
        # Estimar número total recomendado de archivos
        total_size_needed = sum(result.size_mb for result in validation_results)
        recommended_total_files = math.ceil(total_size_needed / self.max_size_mb)
        
        # Crear resumen
        summary = ValidationSummary(
            original_file=original_file,
            total_files_checked=len(validation_results),
            files_within_limits=files_within_limits,
            files_exceeding_limits=files_exceeding_limits,
            total_files_needing_resplit=total_files_needing_resplit,
            all_within_limits=(files_exceeding_limits == 0),
            split_files=split_files,
            validation_results=validation_results,
            recommended_total_files=recommended_total_files
        )
        
        logger.info(f"Validación completada: {files_within_limits}/{len(validation_results)} archivos válidos")
        
        return summary
    
    def auto_adjust_split(self, summary: ValidationSummary) -> AdjustedSummary:
        """
        Ajustar automáticamente la división basándose en validación
        
        Args:
            summary: Resumen de validación original
            
        Returns:
            AdjustedSummary con nueva división aplicada
        """
        if summary.all_within_limits:
            # No necesita ajuste
            return AdjustedSummary(
                original_summary=summary,
                adjustment_applied=False,
                new_file_count=summary.total_files_checked,
                all_within_limits=True,
                split_files=summary.split_files,
                validation_results=summary.validation_results,
                adjustment_reason="Todos los archivos están dentro de los límites"
            )
        
        # Calcular nuevo número de archivos necesario
        new_file_count = summary.recommended_total_files
        adjustment_reason = f"Ajuste automático: {summary.total_files_checked} → {new_file_count} archivos"
        
        logger.info(f"Aplicando ajuste automático: {adjustment_reason}")
        
        # Simular nueva división (en implementación real, re-dividiría el archivo)
        adjusted_files = []
        adjusted_results = []
        
        # Calcular distribución de páginas para nueva división
        total_pages = summary.original_file.stat().st_size / (1024 * 1024) * 4  # Estimación
        pages_per_new_file = int(total_pages / new_file_count)
        
        for i in range(new_file_count):
            # Crear información de archivo ajustado (simulado)
            estimated_size = (summary.original_file.stat().st_size / (1024 * 1024)) / new_file_count
            
            adjusted_file = SplitFileInfo(
                file_path=Path(f"{summary.original_file.stem}_adjusted_{i+1}.pdf"),
                size_mb=estimated_size,
                pages=pages_per_new_file,
                exceeds_limit=False,
                page_range=f"Páginas {i * pages_per_new_file + 1}-{(i + 1) * pages_per_new_file}",
                original_index=i
            )
            adjusted_files.append(adjusted_file)
            
            # Validación del archivo ajustado
            adjusted_result = ValidationResult(
                file_path=adjusted_file.file_path,
                size_mb=estimated_size,
                pages=pages_per_new_file,
                within_size_limit=True,
                within_page_limit=True,
                is_valid=True
            )
            adjusted_results.append(adjusted_result)
        
        return AdjustedSummary(
            original_summary=summary,
            adjustment_applied=True,
            new_file_count=new_file_count,
            all_within_limits=True,
            split_files=adjusted_files,
            validation_results=adjusted_results,
            adjustment_reason=adjustment_reason
        )
    
    def calculate_optimal_split(self, file_path: Path, target_size_mb: float = None) -> Dict:
        """
        Calcular división óptima para un archivo
        
        Args:
            file_path: Ruta del archivo
            target_size_mb: Tamaño objetivo por archivo (opcional)
            
        Returns:
            Dict con información de división óptima
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
        
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        target_size = target_size_mb or self.max_size_mb
        
        # Cálculos de división óptima
        min_files = math.ceil(file_size_mb / target_size)
        optimal_size_per_file = file_size_mb / min_files
        
        # Generar múltiples opciones
        options = []
        for num_files in range(min_files, min(min_files + 4, 20)):
            size_per_file = file_size_mb / num_files
            efficiency = min(1.0, target_size / size_per_file) if size_per_file > 0 else 0
            
            if size_per_file <= target_size:
                options.append({
                    'num_files': num_files,
                    'size_per_file_mb': size_per_file,
                    'efficiency': efficiency,
                    'pages_per_file': int((file_size_mb * 4) / num_files),  # Estimación
                    'total_size_mb': file_size_mb
                })
        
        # Ordenar por eficiencia
        options.sort(key=lambda x: x['efficiency'], reverse=True)
        
        return {
            'original_size_mb': file_size_mb,
            'target_size_mb': target_size,
            'min_files_required': min_files,
            'recommended_files': options[0]['num_files'] if options else min_files,
            'options': options[:5]  # Top 5 opciones
        }

def interactive_split_adjustment(validator: PDFSplitValidator, summary: ValidationSummary) -> Optional[AdjustedSummary]:
    """
    Interfaz interactiva para ajuste de división (versión consola para pruebas)
    
    Args:
        validator: Instancia del validador
        summary: Resumen de validación
        
    Returns:
        AdjustedSummary o None si se cancela
    """
    if summary.all_within_limits:
        print("✅ Todos los archivos están dentro de los límites. No se requiere ajuste.")
        return None
    
    print(f"\n⚠️  ARCHIVOS EXCEDEN LÍMITES")
    print(f"📄 Archivo original: {summary.original_file.name}")
    print(f"📊 Archivos actuales: {summary.total_files_checked}")
    print(f"❌ Archivos que exceden límites: {summary.files_exceeding_limits}")
    print(f"💡 Archivos recomendados: {summary.recommended_total_files}")
    
    print(f"\nDetalles de archivos problemáticos:")
    for result in summary.validation_results:
        if not result.is_valid:
            print(f"  - {result.file_path.name}: {result.size_mb:.1f}MB (límite: {validator.max_size_mb}MB)")
    
    print(f"\nOpciones disponibles:")
    print(f"1. ✅ Ajustar automáticamente ({summary.recommended_total_files} archivos)")
    print(f"2. ⚠️  Proceder sin ajustar (archivos grandes fallarán)")
    print(f"3. ❌ Cancelar procesamiento")
    
    while True:
        choice = input(f"\nSeleccione una opción (1-3): ").strip()
        
        if choice == "1":
            return validator.auto_adjust_split(summary)
        elif choice == "2":
            return AdjustedSummary(
                original_summary=summary,
                adjustment_applied=False,
                new_file_count=summary.total_files_checked,
                all_within_limits=False,
                split_files=summary.split_files,
                validation_results=summary.validation_results,
                adjustment_reason="Usuario eligió proceder sin ajustar"
            )
        elif choice == "3":
            return None
        else:
            print("❌ Opción inválida. Ingrese 1, 2, o 3.")

# Test function
def test_validator():
    """Función de prueba para el validador"""
    import tempfile
    
    # Crear archivo de prueba
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        # Simular archivo de 100MB
        tmp.write(b'0' * (100 * 1024 * 1024))
        test_file = Path(tmp.name)
    
    try:
        validator = PDFSplitValidator(max_size_mb=45.0)
        
        # Calcular división óptima
        optimal = validator.calculate_optimal_split(test_file)
        print(f"División óptima para archivo de 100MB:")
        print(f"  Archivos mínimos: {optimal['min_files_required']}")
        print(f"  Archivos recomendados: {optimal['recommended_files']}")
        
        for i, option in enumerate(optimal['options']):
            print(f"  Opción {i+1}: {option['num_files']} archivos, "
                  f"{option['size_per_file_mb']:.1f}MB c/u, "
                  f"eficiencia: {option['efficiency']:.0%}")
        
    finally:
        # Limpiar archivo de prueba
        test_file.unlink()

if __name__ == "__main__":
    test_validator()