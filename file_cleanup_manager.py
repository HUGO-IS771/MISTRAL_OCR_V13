#!/usr/bin/env python3
"""
File Cleanup Manager - Gestión de Limpieza de Archivos Temporales
===============================================================
Sistema para limpiar automáticamente archivos temporales creados durante
el procesamiento, especialmente cuando el usuario cancela operaciones.

Versión: 1.0.0 - Gestión de Limpieza
Funcionalidad: Limpieza segura de archivos temporales
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
import threading
import atexit

# Configuración
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('file_cleanup_manager')

@dataclass
class TemporaryFileInfo:
    """Información de archivo temporal"""
    file_path: Path
    creation_time: float
    original_file: Optional[Path] = None
    file_type: str = "split"  # 'split', 'temp', 'cache'
    cleanup_after: float = 3600  # Limpiar después de 1 hora por defecto

class FileCleanupManager:
    """Gestor para limpiar archivos temporales de forma segura"""
    
    def __init__(self):
        self.temp_files: Set[TemporaryFileInfo] = set()
        self.cleanup_enabled = True
        self.cleanup_thread = None
        self._lock = threading.Lock()
        
        # Registrar limpieza al salir
        atexit.register(self.cleanup_all_on_exit)
        
        logger.info("FileCleanupManager inicializado")
    
    def register_temp_file(self, file_path: Path, original_file: Optional[Path] = None, 
                          file_type: str = "split", cleanup_after: float = 3600):
        """
        Registrar archivo temporal para limpieza automática
        
        Args:
            file_path: Ruta del archivo temporal
            original_file: Archivo original del cual se derivó (opcional)
            file_type: Tipo de archivo ('split', 'temp', 'cache')
            cleanup_after: Segundos después de los cuales limpiar automáticamente
        """
        with self._lock:
            temp_file_info = TemporaryFileInfo(
                file_path=file_path,
                creation_time=time.time(),
                original_file=original_file,
                file_type=file_type,
                cleanup_after=cleanup_after
            )
            
            self.temp_files.add(temp_file_info)
            logger.info(f"Archivo temporal registrado: {file_path} (limpieza en {cleanup_after}s)")
    
    def register_split_files(self, split_info: Dict, original_file: Path):
        """
        Registrar múltiples archivos de división para limpieza
        
        Args:
            split_info: Información de división del OCR client
            original_file: Archivo original que fue dividido
        """
        if 'files' in split_info:
            for split_file_path in split_info['files']:
                self.register_temp_file(
                    Path(split_file_path),
                    original_file=original_file,
                    file_type="split",
                    cleanup_after=7200  # 2 horas para archivos divididos
                )
            
            logger.info(f"Registrados {len(split_info['files'])} archivos divididos para limpieza")
    
    def cleanup_files_for_original(self, original_file: Path, force: bool = False) -> int:
        """
        Limpiar archivos temporales asociados a un archivo original específico
        
        Args:
            original_file: Archivo original
            force: Forzar limpieza inmediata sin importar tiempo de creación
            
        Returns:
            Número de archivos eliminados
        """
        files_to_remove = []
        cleaned_count = 0
        
        with self._lock:
            for temp_file_info in self.temp_files.copy():
                if (temp_file_info.original_file == original_file and
                    (force or self._should_cleanup(temp_file_info))):
                    files_to_remove.append(temp_file_info)
        
        # Limpiar fuera del lock para evitar bloqueos
        for temp_file_info in files_to_remove:
            if self._safe_remove_file(temp_file_info.file_path):
                cleaned_count += 1
                with self._lock:
                    self.temp_files.discard(temp_file_info)
        
        if cleaned_count > 0:
            logger.info(f"Limpiados {cleaned_count} archivos temporales para {original_file.name}")
        
        return cleaned_count
    
    def cleanup_by_pattern(self, pattern: str, file_type: Optional[str] = None) -> int:
        """
        Limpiar archivos que coincidan con un patrón
        
        Args:
            pattern: Patrón del nombre de archivo (usando glob)
            file_type: Tipo de archivo opcional para filtrar
            
        Returns:
            Número de archivos eliminados
        """
        files_to_remove = []
        cleaned_count = 0
        
        with self._lock:
            for temp_file_info in self.temp_files.copy():
                if (temp_file_info.file_path.match(pattern) and
                    (file_type is None or temp_file_info.file_type == file_type)):
                    files_to_remove.append(temp_file_info)
        
        for temp_file_info in files_to_remove:
            if self._safe_remove_file(temp_file_info.file_path):
                cleaned_count += 1
                with self._lock:
                    self.temp_files.discard(temp_file_info)
        
        if cleaned_count > 0:
            logger.info(f"Limpiados {cleaned_count} archivos con patrón '{pattern}'")
        
        return cleaned_count
    
    def immediate_cleanup(self, file_paths: List[Path]) -> int:
        """
        Limpieza inmediata de archivos específicos
        
        Args:
            file_paths: Lista de rutas de archivos a eliminar
            
        Returns:
            Número de archivos eliminados
        """
        cleaned_count = 0
        
        for file_path in file_paths:
            if self._safe_remove_file(file_path):
                cleaned_count += 1
                
                # Remover del registro si existe
                with self._lock:
                    to_remove = None
                    for temp_file_info in self.temp_files:
                        if temp_file_info.file_path == file_path:
                            to_remove = temp_file_info
                            break
                    
                    if to_remove:
                        self.temp_files.discard(to_remove)
        
        if cleaned_count > 0:
            logger.info(f"Limpieza inmediata: {cleaned_count} archivos eliminados")
        
        return cleaned_count
    
    def start_background_cleanup(self, interval: float = 300):
        """
        Iniciar limpieza automática en segundo plano
        
        Args:
            interval: Intervalo en segundos entre limpiezas automáticas
        """
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            self.cleanup_thread = threading.Thread(
                target=self._background_cleanup_worker,
                args=(interval,),
                daemon=True,
                name="FileCleanupWorker"
            )
            self.cleanup_thread.start()
            logger.info(f"Iniciada limpieza automática (cada {interval}s)")
    
    def stop_background_cleanup(self):
        """Detener limpieza automática"""
        self.cleanup_enabled = False
        if self.cleanup_thread:
            logger.info("Deteniendo limpieza automática...")
    
    def get_cleanup_status(self) -> Dict:
        """Obtener estado actual de archivos temporales"""
        with self._lock:
            current_time = time.time()
            
            by_type = {}
            ready_for_cleanup = 0
            total_size = 0
            
            for temp_file_info in self.temp_files:
                file_type = temp_file_info.file_type
                if file_type not in by_type:
                    by_type[file_type] = 0
                by_type[file_type] += 1
                
                if self._should_cleanup(temp_file_info):
                    ready_for_cleanup += 1
                
                try:
                    if temp_file_info.file_path.exists():
                        total_size += temp_file_info.file_path.stat().st_size
                except:
                    pass
            
            return {
                'total_files': len(self.temp_files),
                'by_type': by_type,
                'ready_for_cleanup': ready_for_cleanup,
                'total_size_mb': total_size / (1024 * 1024),
                'cleanup_enabled': self.cleanup_enabled
            }
    
    def cleanup_all_on_exit(self):
        """Limpiar todos los archivos al salir (registrado con atexit)"""
        if not self.cleanup_enabled:
            return
        
        logger.info("Limpieza final al salir de la aplicación...")
        files_to_remove = list(self.temp_files)
        cleaned_count = 0
        
        for temp_file_info in files_to_remove:
            if self._safe_remove_file(temp_file_info.file_path):
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Limpieza final: {cleaned_count} archivos eliminados")
    
    def _background_cleanup_worker(self, interval: float):
        """Worker para limpieza automática en segundo plano"""
        while self.cleanup_enabled:
            try:
                self._periodic_cleanup()
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Error en limpieza automática: {e}")
                time.sleep(interval)
    
    def _periodic_cleanup(self):
        """Limpieza periódica de archivos que han expirado"""
        files_to_remove = []
        
        with self._lock:
            for temp_file_info in self.temp_files.copy():
                if self._should_cleanup(temp_file_info):
                    files_to_remove.append(temp_file_info)
        
        cleaned_count = 0
        for temp_file_info in files_to_remove:
            if self._safe_remove_file(temp_file_info.file_path):
                cleaned_count += 1
                with self._lock:
                    self.temp_files.discard(temp_file_info)
        
        if cleaned_count > 0:
            logger.info(f"Limpieza automática: {cleaned_count} archivos eliminados")
    
    def _should_cleanup(self, temp_file_info: TemporaryFileInfo) -> bool:
        """Determinar si un archivo debe ser limpiado"""
        current_time = time.time()
        age = current_time - temp_file_info.creation_time
        return age > temp_file_info.cleanup_after
    
    def _safe_remove_file(self, file_path: Path) -> bool:
        """Eliminar archivo de forma segura"""
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Archivo eliminado: {file_path}")
                return True
            else:
                logger.debug(f"Archivo ya no existe: {file_path}")
                return False
        except Exception as e:
            logger.warning(f"Error eliminando {file_path}: {e}")
            return False

# Instancia global del gestor
_cleanup_manager = None

def get_cleanup_manager() -> FileCleanupManager:
    """Obtener instancia global del gestor de limpieza"""
    global _cleanup_manager
    if _cleanup_manager is None:
        _cleanup_manager = FileCleanupManager()
        _cleanup_manager.start_background_cleanup()
    return _cleanup_manager

def register_split_files_for_cleanup(split_info: Dict, original_file: Path):
    """Función de conveniencia para registrar archivos divididos"""
    get_cleanup_manager().register_split_files(split_info, original_file)

def cleanup_split_files_for_original(original_file: Path, force: bool = False) -> int:
    """Función de conveniencia para limpiar archivos de un original"""
    return get_cleanup_manager().cleanup_files_for_original(original_file, force)

def immediate_cleanup_files(file_paths: List[Path]) -> int:
    """Función de conveniencia para limpieza inmediata"""
    return get_cleanup_manager().immediate_cleanup(file_paths)

# Test function
def test_cleanup_manager():
    """Función de prueba"""
    import tempfile
    
    # Crear archivos de prueba
    test_files = []
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        
        # Crear archivos de prueba
        for i in range(3):
            test_file = temp_dir / f"test_split_{i}.pdf"
            test_file.write_text(f"Archivo de prueba {i}")
            test_files.append(test_file)
        
        original_file = temp_dir / "original.pdf"
        original_file.write_text("Archivo original")
        
        # Probar el cleanup manager
        manager = FileCleanupManager()
        
        # Registrar archivos con tiempo corto para prueba rápida
        for test_file in test_files:
            manager.register_temp_file(test_file, original_file, "split", cleanup_after=1)
        
        print(f"Estado inicial: {manager.get_cleanup_status()}")
        
        # Esperar y hacer limpieza
        time.sleep(2)
        cleaned = manager.cleanup_files_for_original(original_file, force=True)
        print(f"Archivos limpiados: {cleaned}")
        
        print(f"Estado final: {manager.get_cleanup_status()}")

if __name__ == "__main__":
    test_cleanup_manager()