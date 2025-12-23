#!/usr/bin/env python3
"""
Performance Optimizer - Optimizador de rendimiento para procesamiento OCR
Implementa estrategias avanzadas para maximizar velocidad de procesamiento.
"""

import time
import asyncio
import threading
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Callable, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Métricas de rendimiento para análisis."""
    upload_time: float = 0.0
    processing_time: float = 0.0
    save_time: float = 0.0
    total_time: float = 0.0
    file_size_mb: float = 0.0
    pages_count: int = 0
    
    @property
    def pages_per_second(self) -> float:
        return self.pages_count / self.total_time if self.total_time > 0 else 0
    
    @property
    def mb_per_second(self) -> float:
        return self.file_size_mb / self.total_time if self.total_time > 0 else 0


class BatchProcessor:
    """Procesador optimizado para múltiples archivos."""
    
    def __init__(self, ocr_client, max_workers: int = 3):
        self.ocr_client = ocr_client
        self.max_workers = max_workers  # Reducido para evitar rate limits
        self.metrics = []

        # Configuración de delays adaptativos mejorada
        self.base_delay = 1.5  # Delay base entre requests (reducido de 2.0s)
        self.adaptive_delay = self.base_delay
        self.rate_limit_backoff = 1.5  # Factor de backoff
        self.adaptive_reduction_factor = 0.9  # Factor de reducción (más agresivo, era 0.95)

        # Cache de archivos subidos
        self.upload_cache = {}
    
    def process_files_optimized(self, files_info: List[Dict], 
                              config: Dict, progress_callback: Callable = None) -> Dict:
        """
        Procesa archivos con optimizaciones de rendimiento.
        
        Args:
            files_info: Lista de diccionarios con info de archivos
            config: Configuración de procesamiento
            progress_callback: Callback para reportar progreso
        """
        start_time = time.time()
        results = {'success': [], 'failed': []}
        
        # Estrategia 1: Agrupar por tamaño similar para mejor paralelización
        grouped_files = self._group_files_by_size(files_info)
        
        # Debug logging de agrupación
        logger.info(f"=== AGRUPACIÓN POR TAMAÑO ===")
        for group_name, files_group in grouped_files.items():
            logger.info(f"Grupo {group_name}: {len(files_group)} archivos")
            for idx, f in enumerate(files_group):
                size_mb = f.get('size_mb', 0)
                logger.info(f"  {group_name} {idx+1}: {Path(f['file_path']).name} ({size_mb:.1f} MB)")
        
        # Estrategia 2: Procesar grupos con diferentes niveles de concurrencia
        for group_name, files_group in grouped_files.items():
            if len(files_group) == 0:
                logger.info(f"Saltando grupo {group_name}: 0 archivos")
                continue
            logger.info(f"Procesando grupo {group_name}: {len(files_group)} archivos")
            
            # Ajustar workers según el grupo
            workers = self._get_optimal_workers(group_name, len(files_group))
            
            group_results = self._process_group_concurrent(
                files_group, config, workers, progress_callback
            )
            
            logger.info(f"Grupo {group_name} completado: {len(group_results['success'])} éxitos, {len(group_results['failed'])} fallos")
            
            results['success'].extend(group_results['success'])
            results['failed'].extend(group_results['failed'])
        
        # Finalizar métricas
        total_time = time.time() - start_time
        self._log_performance_summary(results, total_time)
        
        return results
    
    def _group_files_by_size(self, files_info: List[Dict]) -> Dict[str, List[Dict]]:
        """Agrupa archivos por tamaño para optimizar procesamiento."""
        small_files = []    # < 10MB
        medium_files = []   # 10-30MB  
        large_files = []    # > 30MB
        
        for file_info in files_info:
            file_path = Path(file_info['file_path'])
            size_mb = file_path.stat().st_size / (1024 * 1024)
            
            file_info['size_mb'] = size_mb
            
            if size_mb < 10:
                small_files.append(file_info)
            elif size_mb < 30:
                medium_files.append(file_info)
            else:
                large_files.append(file_info)
        
        return {
            'large': large_files,    # Procesar primero (más lentos)
            'medium': medium_files,
            'small': small_files     # Procesar al final (más rápidos)
        }
    
    def _get_optimal_workers(self, group_name: str, file_count: int) -> int:
        """Determina número óptimo de workers según el grupo."""
        if group_name == 'large':
            return min(2, file_count)  # Archivos grandes: máximo 2 concurrent
        elif group_name == 'medium':
            return min(3, file_count)  # Archivos medianos: máximo 3
        else:
            return min(4, file_count)  # Archivos pequeños: máximo 4

    def _get_delay_for_file(self, file_size_mb: float) -> float:
        """Calcula delay adaptativo basado en tamaño del archivo."""
        if file_size_mb < 5:
            return 0.5  # Archivos pequeños: delay mínimo
        elif file_size_mb < 30:
            return 1.5  # Archivos medianos: delay moderado
        else:
            return 4.0  # Archivos grandes: delay mayor para evitar saturación
    
    def _process_group_concurrent(self, files_group: List[Dict], config: Dict,
                                workers: int, progress_callback: Callable) -> Dict:
        """Procesa un grupo de archivos de forma concurrente."""
        results = {'success': [], 'failed': []}
        
        if not files_group:
            return results
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Enviar tareas con delay escalonado basado en tamaño
            futures = {}

            for i, file_info in enumerate(files_group):
                # Delay adaptativo basado en tamaño del archivo
                if i > 0:
                    file_size_mb = file_info.get('size_mb', 0)
                    size_based_delay = self._get_delay_for_file(file_size_mb)
                    # Combinar con delay adaptativo (usar el mayor)
                    effective_delay = max(size_based_delay, self.adaptive_delay)
                    logger.debug(f"Delay para {file_info['file_path']}: {effective_delay:.1f}s (tamaño: {file_size_mb:.1f}MB)")
                    time.sleep(effective_delay)

                future = executor.submit(
                    self._process_single_file_with_metrics,
                    file_info, config
                )
                futures[future] = file_info
            
            # Recoger resultados con manejo de rate limits
            completed_count = 0
            for future in as_completed(futures):
                file_info = futures[future]
                
                try:
                    result = future.result()
                    results['success'].append(result)

                    # Actualizar delay adaptativo (éxito = reducir delay) - factor más agresivo
                    self.adaptive_delay = max(0.5, self.adaptive_delay * self.adaptive_reduction_factor)
                    
                except Exception as e:
                    error_str = str(e)
                    
                    # Solo manejar rate limits aquí (los errores 3310 ya se manejan internamente)
                    if self._is_rate_limit_error(error_str):
                        logger.warning(f"Rate limit detectado, aumentando delay a {self.adaptive_delay * self.rate_limit_backoff:.1f}s")
                        self.adaptive_delay *= self.rate_limit_backoff
                        
                        # Reintentar después de delay
                        time.sleep(self.adaptive_delay * 2)
                        try:
                            retry_result = self._process_single_file_with_metrics(file_info, config)
                            results['success'].append(retry_result)
                            continue
                        except Exception as retry_e:
                            error_str = str(retry_e)
                    
                    results['failed'].append({
                        'file': file_info['file_path'],
                        'error': error_str
                    })
                
                completed_count += 1
                if progress_callback:
                    progress_callback(completed_count, len(files_group))
        
        return results
    
    def _process_single_file_with_metrics(self, file_info: Dict, config: Dict) -> Dict:
        """Procesa un archivo individual con métricas de rendimiento."""
        file_path = file_info['file_path']
        page_offset = file_info['page_offset']
        
        metrics = PerformanceMetrics()
        metrics.file_size_mb = file_info.get('size_mb', 0)
        
        total_start = time.time()
        max_retries = 2  # Máximo 2 reintentos para error 3310
        
        for attempt in range(max_retries + 1):
            try:
                # 1. Subida optimizada (con cache, pero forzar nueva subida si es retry por 3310)
                upload_start = time.time()
                if attempt > 0:
                    # Limpiar cache si es un retry
                    file_path_obj = Path(file_path)
                    file_key = f"{file_path_obj.name}_{file_path_obj.stat().st_mtime}_{file_path_obj.stat().st_size}"
                    if file_key in self.upload_cache:
                        logger.info(f"Limpiando cache para retry de {file_path_obj.name}")
                        del self.upload_cache[file_key]
                
                file_url = self._upload_file_cached(file_path, force_fresh=(attempt > 0))
                metrics.upload_time = time.time() - upload_start
                
                # Validar URL antes de procesar
                logger.info(f"URL generada: {file_url[:100]}...")
                
                # Pequeña pausa después de la subida para asegurar disponibilidad
                if attempt > 0:
                    time.sleep(2)  # Extra delay en reintentos
                
                # 2. Procesamiento OCR
                process_start = time.time()
                response = self.ocr_client.client.ocr.process(
                    document={
                        "type": "document_url",
                        "document_url": file_url
                    },
                    model=config.get('model', 'mistral-ocr-latest'),
                    include_image_base64=config.get('include_images', True)
                )
                metrics.processing_time = time.time() - process_start
                metrics.pages_count = len(response.pages)
                
                # 3. Guardado optimizado
                save_start = time.time()
                saved_files = self._save_results_optimized(
                    response, file_info, config, page_offset
                )
                metrics.save_time = time.time() - save_start
                
                metrics.total_time = time.time() - total_start
                self.metrics.append(metrics)
                
                if attempt > 0:
                    logger.info(f"✅ Archivo procesado exitosamente en intento {attempt + 1}: {Path(file_path).name}")
                
                return {
                    'file': file_path,
                    'response': response,
                    'saved_files': saved_files,
                    'metrics': metrics,
                    'page_offset': page_offset
                }
                
            except Exception as e:
                error_str = str(e)
                
                # Si es error 3310 y no hemos agotado los reintentos
                if self._is_url_fetch_error(error_str) and attempt < max_retries:
                    logger.warning(f"⚠️  Error 3310 en intento {attempt + 1} para {Path(file_path).name}, reintentando...")
                    logger.debug(f"Error completo: {error_str}")
                    time.sleep(3 * (attempt + 1))  # Espera progresiva: 3s, 6s
                    continue
                
                # Si llegamos aquí, hemos agotado los reintentos o es otro tipo de error
                metrics.total_time = time.time() - total_start
                logger.error(f"❌ Error procesando {file_path} después de {attempt + 1} intento(s): {error_str}")
                raise
    
    def _upload_file_cached(self, file_path: str, force_fresh: bool = False) -> str:
        """Sube archivo con sistema de cache mejorado para evitar re-subidas."""
        file_path = Path(file_path)

        # Limpiar cache de entradas expiradas periódicamente
        self._cleanup_expired_cache()

        # Usar hash MD5 como clave primaria (detecta duplicados independiente del nombre)
        content = file_path.read_bytes()
        file_hash = hashlib.md5(content).hexdigest()

        # Verificar cache (solo si no forzamos subida fresca)
        if not force_fresh and file_hash in self.upload_cache:
            cache_entry = self.upload_cache[file_hash]
            # Verificar si no ha expirado (URLs válidas por 24 horas, usar 12 horas para seguridad)
            if time.time() - cache_entry['timestamp'] < 43200:  # 12 horas (mejorado desde 6)
                logger.info(f"✓ Usando URL cacheada para {file_path.name} (hash: {file_hash[:8]}...)")
                return cache_entry['url']
            else:
                logger.info(f"Cache expirado para {file_path.name}, subiendo de nuevo")
                del self.upload_cache[file_hash]

        # Subir archivo
        logger.info(f"Subiendo {'(forzado)' if force_fresh else ''} {file_path.name} ({len(content)/(1024*1024):.1f} MB)")
        uploaded = self.ocr_client.client.files.upload(
            file={"file_name": file_path.name, "content": content},
            purpose="ocr"
        )

        # Aumentar tiempo de expiración y añadir retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                signed_url = self.ocr_client.client.files.get_signed_url(
                    file_id=uploaded.id, expiry=24  # 24 horas en lugar de 1
                )
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Error obteniendo URL firmada (intento {attempt + 1}): {e}")
                time.sleep(2 ** attempt)  # Backoff exponencial

        # Guardar en cache con hash MD5 y metadata adicional
        self.upload_cache[file_hash] = {
            'url': signed_url.url,
            'timestamp': time.time(),
            'filename': file_path.name,
            'size_mb': len(content) / (1024 * 1024)
        }

        logger.info(f"✓ Archivo cacheado (hash: {file_hash[:8]}..., válido por 12 horas)")

        return signed_url.url

    def _cleanup_expired_cache(self):
        """Limpia entradas de cache expiradas (>12 horas)."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.upload_cache.items()
            if current_time - entry['timestamp'] > 43200  # 12 horas
        ]

        if expired_keys:
            for key in expired_keys:
                filename = self.upload_cache[key].get('filename', 'unknown')
                del self.upload_cache[key]
            logger.info(f"Limpiadas {len(expired_keys)} entradas expiradas del cache")
    
    def _save_results_optimized(self, response, file_info: Dict, 
                              config: Dict, page_offset: int) -> Dict:
        """Guarda resultados de forma optimizada usando threads."""
        saved_files = {}
        save_tasks = []
        
        # Preparar tareas de guardado con numeración de páginas
        original_file = file_info.get('original_file', file_info['file_path'])
        original_base_name = Path(original_file).stem
        output_dir = config.get('output_dir', '.')
        
        # Calcular rango de páginas si es parte de un archivo dividido
        total_pages = len(response.pages)
        start_page = page_offset + 1
        end_page = page_offset + len(response.pages)
        
        # Generar nombre base con numeración de páginas si es necesario
        if file_info['file_path'] != original_file and total_pages > 0:
            # Es parte de un archivo dividido - incluir rango de páginas
            base_name = f"{original_base_name}_pag{start_page:04d}-{end_page:04d}"
        else:
            # Archivo único - usar nombre original
            base_name = original_base_name
        
        if config.get('save_md', False):
            save_tasks.append(('md', f"{base_name}.md"))
        
        if config.get('save_txt', False):
            save_tasks.append(('txt', f"{base_name}.txt"))
        
        if config.get('save_html', False):
            save_tasks.append(('html', f"{base_name}.html"))
        
        if config.get('save_images', False):
            save_tasks.append(('images', f"{base_name}_images"))
        
        # Ejecutar guardado en paralelo con más workers para mayor velocidad
        with ThreadPoolExecutor(max_workers=5) as save_executor:
            save_futures = {}
            
            for save_type, filename in save_tasks:
                future = save_executor.submit(
                    self._save_single_format,
                    response, save_type, output_dir, filename, page_offset, base_name
                )
                save_futures[future] = (save_type, filename)
            
            # Recoger resultados de guardado
            for future in as_completed(save_futures):
                save_type, filename = save_futures[future]
                try:
                    saved_path = future.result()
                    saved_files[save_type] = saved_path
                except Exception as e:
                    logger.error(f"Error guardando {save_type}: {str(e)}")
        
        return saved_files
    
    def _save_single_format(self, response, save_type: str, output_dir: str,
                          filename: str, page_offset: int, title: str = None) -> str:
        """Guarda un formato específico."""
        output_path = Path(output_dir) / filename
        
        if save_type == 'md':
            return self.ocr_client.save_as_markdown(response, output_path, page_offset)
        elif save_type == 'txt':
            return self.ocr_client.save_text(response, output_path, page_offset)
        elif save_type == 'html':
            # Usar el título formateado o el nombre del archivo
            doc_title = title.replace('_', ' ').title() if title else "Documento OCR"
            return self.ocr_client.save_as_html(response, output_path, page_offset, title=doc_title)
        elif save_type == 'images':
            return self.ocr_client.save_images(response, output_path, page_offset)
        
        return str(output_path)
    
    def _is_rate_limit_error(self, error_str: str) -> bool:
        """Detecta errores de rate limit."""
        rate_limit_indicators = [
            '429', 'rate limit', 'too many requests', 
            'quota exceeded', 'throttled', 'rate exceeded'
        ]
        error_lower = error_str.lower()
        return any(indicator in error_lower for indicator in rate_limit_indicators)
    
    def _is_url_fetch_error(self, error_str: str) -> bool:
        """Detecta errores de acceso a URLs (código 3310)."""
        url_error_indicators = [
            '3310', 'could not be fetched from url', 
            'file could not be fetched', 'invalid_request_file'
        ]
        error_lower = error_str.lower()
        return any(indicator in error_lower for indicator in url_error_indicators)
    
    def _log_performance_summary(self, results: Dict, total_time: float):
        """Registra resumen de rendimiento."""
        if not self.metrics:
            return
        
        avg_upload = sum(m.upload_time for m in self.metrics) / len(self.metrics)
        avg_process = sum(m.processing_time for m in self.metrics) / len(self.metrics)
        avg_save = sum(m.save_time for m in self.metrics) / len(self.metrics)
        total_pages = sum(m.pages_count for m in self.metrics)
        total_mb = sum(m.file_size_mb for m in self.metrics)
        
        logger.info(f"=== RESUMEN DE RENDIMIENTO ===")
        logger.info(f"Archivos procesados: {len(results['success'])}")
        logger.info(f"Archivos fallidos: {len(results['failed'])}")
        logger.info(f"Tiempo total: {total_time:.1f}s")
        logger.info(f"Páginas totales: {total_pages}")
        logger.info(f"Velocidad: {total_pages/total_time:.1f} páginas/s")
        logger.info(f"Tiempo promedio - Subida: {avg_upload:.1f}s, Procesamiento: {avg_process:.1f}s, Guardado: {avg_save:.1f}s")
        logger.info(f"Throughput: {total_mb/total_time:.1f} MB/s")


class PerformanceConfig:
    """Configuración de rendimiento adaptativa."""
    
    @staticmethod
    def get_optimal_config(file_count: int, total_size_mb: float) -> Dict:
        """Obtiene configuración óptima basada en el lote."""
        config = {
            'max_workers': 3,
            'base_delay': 1.5,  # Reducido de 2.0s
            'enable_cache': True,
            'parallel_save': True
        }

        # Ajustar según tamaño del lote
        if file_count > 10:
            config['max_workers'] = 2  # Reducir concurrencia para lotes grandes
            config['base_delay'] = 2.5  # Reducido de 3.0s
        elif file_count < 3:
            config['max_workers'] = 4  # Aumentar para lotes pequeños
            config['base_delay'] = 1.0  # Reducido de 1.5s

        # Ajustar según tamaño total
        if total_size_mb > 500:  # Lote muy grande
            config['max_workers'] = 2
            config['base_delay'] = 3.5  # Reducido de 4.0s
        elif total_size_mb < 50:  # Lote pequeño
            config['max_workers'] = 4
            config['base_delay'] = 0.5  # Reducido de 1.0s - archivos pequeños pueden ir más rápido

        return config
    
    @staticmethod
    def estimate_processing_time(files_info: List[Dict]) -> float:
        """Estima tiempo de procesamiento basado en métricas históricas."""
        total_pages = 0
        total_size_mb = 0
        
        for file_info in files_info:
            # Estimación basada en tamaño (asumiendo ~2 páginas por MB para PDFs típicos)
            size_mb = file_info.get('size_mb', 0)
            if size_mb > 0:
                estimated_pages = max(1, int(size_mb * 2))
                total_pages += estimated_pages
                total_size_mb += size_mb
        
        # Estimación conservadora: 0.5 páginas por segundo (incluyendo subida, procesamiento y guardado)
        base_time = total_pages / 0.5
        
        # Factor de overhead por número de archivos
        file_overhead = len(files_info) * 2  # 2 segundos por archivo de overhead
        
        # Total con margen de seguridad del 20%
        estimated_time = (base_time + file_overhead) * 1.2
        
        return estimated_time


# Funciones de utilidad para integración
def create_optimized_processor(ocr_client, file_count: int, total_size_mb: float):
    """Crea procesador optimizado con configuración adaptativa."""
    perf_config = PerformanceConfig.get_optimal_config(file_count, total_size_mb)
    return BatchProcessor(ocr_client, max_workers=perf_config['max_workers'])


def estimate_batch_time(files_info: List[Dict]) -> Tuple[float, str]:
    """Estima tiempo de procesamiento y devuelve descripción."""
    estimated_seconds = PerformanceConfig.estimate_processing_time(files_info)
    
    if estimated_seconds < 60:
        description = f"{estimated_seconds:.0f} segundos"
    elif estimated_seconds < 3600:
        minutes = estimated_seconds / 60
        description = f"{minutes:.1f} minutos"
    else:
        hours = estimated_seconds / 3600
        minutes = (estimated_seconds % 3600) / 60
        description = f"{hours:.0f}h {minutes:.0f}m"
    
    return estimated_seconds, description