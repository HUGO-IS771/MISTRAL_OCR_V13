#!/usr/bin/env python3
"""
Batch Processor - Procesador Unificado de Archivos OCR
======================================================
Módulo consolidado que centraliza toda la lógica de procesamiento por lotes:
- Procesamiento individual y múltiple
- Gestión de concurrencia y rendimiento
- División inteligente de archivos
- Caché de uploads
- Numeración continua de páginas

Este módulo elimina la duplicación de código presente en:
- performance_optimizer.py (BatchProcessor)
- multi_batch_processor.py (MultiBatchProcessor)
- mistral_ocr_gui_optimized.py (FileProcessor)

Versión: 1.0.0 - Consolidación Fase 3
Funcionalidad: Procesamiento OCR unificado y optimizado
"""

import os
import re
import time
import math
import hashlib
import logging
import mimetypes
from pathlib import Path
from typing import List, Dict, Callable, Optional, Tuple, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

# Importar componentes consolidados de fases anteriores
from core_analyzer import FileAnalyzer, FileMetrics, SplitAnalysis, SplitPlan, SplitLimits
from batch_optimizer import BatchOptimizer, PDFAnalysis, SplitRecommendation
from processing_limits import LIMITS

logger = logging.getLogger(__name__)


# ==================== DATACLASSES ====================

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


@dataclass
class FileEntry:
    """Entrada de archivo en procesamiento múltiple."""
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


@dataclass
class ProcessingResult:
    """Resultado del procesamiento de un archivo."""
    file_path: str
    response: Any
    saved_files: Dict[str, str]
    metrics: PerformanceMetrics
    page_offset: int
    error: Optional[str] = None


# ==================== PROCESADOR UNIFICADO ====================

class OCRBatchProcessor:
    """
    Procesador unificado de archivos OCR con optimizaciones de rendimiento.

    Consolida:
    - BatchProcessor de performance_optimizer.py
    - MultiBatchProcessor de multi_batch_processor.py
    - FileProcessor de mistral_ocr_gui_optimized.py
    """

    # Usar límites centralizados
    MAX_SIZE_MB = LIMITS.safe_max_size_mb
    MAX_PAGES = LIMITS.safe_max_pages

    def __init__(self, ocr_client, max_workers: int = 3, app=None):
        """
        Inicializa el procesador unificado.

        Args:
            ocr_client: Cliente OCR de Mistral
            max_workers: Número máximo de workers concurrentes
            app: Referencia a la aplicación GUI (opcional)
        """
        self.ocr_client = ocr_client
        self.max_workers = max_workers
        self.app = app
        self.metrics = []

        # Configuración de delays adaptativos
        self.base_delay = 1.5
        self.adaptive_delay = self.base_delay
        self.rate_limit_backoff = 1.5
        self.adaptive_reduction_factor = 0.9

        # Cache de archivos subidos
        self.upload_cache = {}

        # Optimizador para análisis
        self.optimizer = BatchOptimizer()

        # Analizador de core
        self.limits = SplitLimits(max_size_mb=self.MAX_SIZE_MB, max_pages=self.MAX_PAGES)
        self.analyzer = FileAnalyzer(self.limits)

        logger.info(f"OCRBatchProcessor inicializado: {max_workers} workers, {self.MAX_SIZE_MB}MB límite")

    # ==================== ANÁLISIS DE ARCHIVOS ====================

    def analyze_file(self, filepath: str) -> Dict[str, Any]:
        """
        Analiza un archivo individual y retorna información detallada.

        Consolida:
        - FileProcessor.analyze_file() de mistral_ocr_gui_optimized.py
        """
        try:
            size_mb = self.ocr_client.get_file_size_mb(filepath)
            pages_count = self.ocr_client.estimate_pages_count(filepath)
            mime_type, _ = mimetypes.guess_type(filepath)

            # Usar core_analyzer para análisis
            file_path = Path(filepath)
            metrics = FileAnalyzer.get_file_metrics(file_path, pages_count)
            analysis = self.analyzer.analyze_split_needs(metrics)

            return {
                'path': filepath,
                'size_mb': size_mb,
                'pages': pages_count,
                'mime_type': mime_type,
                'requires_split': analysis.requires_splitting,
                'metrics': metrics,
                'analysis': analysis
            }
        except Exception as e:
            logger.error(f"Error analizando {filepath}: {e}")
            return None

    def analyze_multiple_files(self, file_paths: List[str]) -> MultiBatchSummary:
        """
        Analiza múltiples archivos y genera resumen consolidado.

        Consolida:
        - MultiBatchProcessor.analyze_multiple_files() de multi_batch_processor.py
        """
        # Ordenar archivos inteligentemente
        sorted_paths = self._sort_files_intelligently(file_paths)

        file_entries = []
        total_size = 0
        total_pages = 0
        total_files = 0
        warnings = []

        for i, file_path in enumerate(sorted_paths):
            try:
                entry = self._analyze_single_file_for_batch(file_path, i)
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

        # Estimación de tiempo (0.5 min por archivo)
        processing_time = total_files * 0.5

        return MultiBatchSummary(
            files=file_entries,
            total_size_mb=total_size,
            total_pages=total_pages,
            total_estimated_files=total_files,
            global_strategy=global_strategy,
            processing_time_estimate=processing_time,
            warnings=list(set(warnings))
        )

    def _analyze_single_file_for_batch(self, file_path: str, order_index: int) -> FileEntry:
        """Analiza archivo individual para procesamiento por lotes."""
        path = Path(file_path)
        display_name = path.name

        entry = FileEntry(
            file_path=path,
            display_name=display_name,
            order_index=order_index
        )

        try:
            pages_count = self.ocr_client.estimate_pages_count(file_path)

            if pages_count:
                entry.analysis = self.optimizer.analyze_pdf(file_path, pages_count)
                entry.recommendation = self.optimizer.calculate_optimal_split(entry.analysis)

        except Exception as e:
            # Crear análisis básico si falla
            size_mb = entry.file_size_mb
            entry.analysis = PDFAnalysis(
                file_path=path,
                total_size_mb=size_mb,
                total_pages=0,
                density_mb_per_page=0,
                requires_splitting=size_mb > self.MAX_SIZE_MB,
                reason=f"No se pudo analizar: {str(e)}"
            )

        return entry

    # ==================== PROCESAMIENTO DE ARCHIVOS ====================

    def process_files_optimized(self, files_info: List[Dict],
                               config: Dict, progress_callback: Callable = None) -> Dict:
        """
        Procesa archivos con optimizaciones de rendimiento.

        Consolida:
        - BatchProcessor.process_files_optimized() de performance_optimizer.py

        Args:
            files_info: Lista de diccionarios con info de archivos
            config: Configuración de procesamiento
            progress_callback: Callback para reportar progreso
        """
        start_time = time.time()
        results = {'success': [], 'failed': []}

        # Agrupar por tamaño para mejor paralelización
        grouped_files = self._group_files_by_size(files_info)

        # Debug logging
        logger.info(f"=== AGRUPACIÓN POR TAMAÑO ===")
        for group_name, files_group in grouped_files.items():
            logger.info(f"Grupo {group_name}: {len(files_group)} archivos")

        # Procesar grupos con diferentes niveles de concurrencia
        for group_name, files_group in grouped_files.items():
            if len(files_group) == 0:
                continue

            logger.info(f"Procesando grupo {group_name}: {len(files_group)} archivos")

            # Ajustar workers según el grupo
            workers = self._get_optimal_workers(group_name, len(files_group))

            group_results = self._process_group_concurrent(
                files_group, config, workers, progress_callback
            )

            logger.info(f"Grupo {group_name} completado: {len(group_results['success'])} éxitos")

            results['success'].extend(group_results['success'])
            results['failed'].extend(group_results['failed'])

        # Métricas finales
        total_time = time.time() - start_time
        self._log_performance_summary(results, total_time)

        return results

    def process_with_split(self, file_info: Dict, config: Any) -> List[Dict]:
        """
        Procesa archivo con división si es necesario.

        Consolida:
        - FileProcessor.process_with_split() de mistral_ocr_gui_optimized.py

        Args:
            file_info: Información del archivo
            config: Configuración de procesamiento

        Returns:
            Lista de archivos procesados
        """
        files_to_process = []

        if file_info.get('requires_split', False):
            # Determinar número de archivos objetivo
            num_files_target = self._calculate_split_target(file_info, config)

            # Pre-validación (si está disponible)
            num_files_target = self._pre_validate_split(file_info, num_files_target, config)

            if num_files_target == 0:
                # Usuario canceló
                return []

            # Crear archivos divididos
            total_pages = file_info.get('pages')
            if total_pages is None:
                size_mb = file_info.get('size_mb', 50)
                total_pages = int(size_mb * 4)

            pages_per_file = math.ceil(total_pages / num_files_target)

            split_info = self.ocr_client.split_pdf(
                file_info['path'],
                max_pages_per_file=pages_per_file
            )

            # Registrar para limpieza
            try:
                from file_cleanup_manager import register_split_files_for_cleanup
                register_split_files_for_cleanup(split_info, Path(file_info['path']))
            except Exception as e:
                logger.warning(f"No se pudo registrar archivos para limpieza: {e}")

            # Preparar archivos divididos
            for idx, split_file in enumerate(split_info.get('files', [])):
                start_page = idx * pages_per_file
                end_page = min(start_page + pages_per_file, total_pages)
                pages_count = max(0, end_page - start_page)
                files_to_process.append({
                    'file_path': split_file,
                    'page_offset': idx * pages_per_file,
                    'size_mb': Path(split_file).stat().st_size / (1024 * 1024),
                    'original_file': file_info['path'],
                    'pages': pages_count
                })
        else:
            # Procesamiento directo sin división
            files_to_process.append({
                'file_path': file_info['path'],
                'page_offset': 0,
                'size_mb': file_info.get('size_mb', 0),
                'original_file': file_info['path'],
                'pages': file_info.get('pages')
            })

        return files_to_process

    def _calculate_split_target(self, file_info: Dict, config: Any) -> int:
        """Calcula número objetivo de archivos para división."""
        if hasattr(self, 'target_files_from_modal') and self.target_files_from_modal:
            return self.target_files_from_modal

        total_pages = file_info.get('pages')
        size_mb = file_info.get('size_mb', 0)

        max_size = getattr(config, 'max_size_mb', self.MAX_SIZE_MB)
        max_pages = getattr(config, 'max_pages', self.MAX_PAGES)

        if total_pages is not None:
            num_files_by_pages = math.ceil(total_pages / max_pages)
        else:
            num_files_by_pages = 1

        num_files_by_size = math.ceil(size_mb / max_size)

        return max(num_files_by_pages, num_files_by_size, 1)

    def _pre_validate_split(self, file_info: Dict, num_files_target: int, config: Any) -> int:
        """Pre-valida división antes de crear archivos físicos."""
        try:
            from pre_division_validator import PreDivisionValidator
            from pre_division_dialog import show_pre_division_dialog

            pre_validator = PreDivisionValidator(max_size_mb=LIMITS.safe_max_size_mb)
            file_path = Path(file_info['path'])

            is_safe, analysis = pre_validator.validate_before_split(file_path, num_files_target)

            if not is_safe and self.app:
                # Mostrar diálogo de validación
                pre_result = None

                def show_pre_modal():
                    nonlocal pre_result
                    pre_result = show_pre_division_dialog(self.app, analysis, pre_validator)

                self.app.after_idle(show_pre_modal)

                while pre_result is None:
                    self.app.update_idletasks()
                    self.app.update()
                    time.sleep(0.1)

                if pre_result.action == 'cancel':
                    return 0  # Cancelar
                elif pre_result.action in ['use_recommendation', 'adjust']:
                    return pre_result.num_files

        except Exception as e:
            logger.error(f"Error en pre-validación: {e}")

        return num_files_target

    # ==================== PROCESAMIENTO CONCURRENTE ====================

    def _process_group_concurrent(self, files_group: List[Dict], config: Dict,
                                 workers: int, progress_callback: Callable) -> Dict:
        """Procesa grupo de archivos de forma concurrente."""
        results = {'success': [], 'failed': []}

        if not files_group:
            return results

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}

            for i, file_info in enumerate(files_group):
                if i > 0:
                    file_size_mb = file_info.get('size_mb', 0)
                    effective_delay = self._get_delay_for_file(file_size_mb)
                    time.sleep(effective_delay)

                future = executor.submit(
                    self._process_single_file_with_metrics,
                    file_info, config
                )
                futures[future] = file_info

            # Recoger resultados
            completed_count = 0
            for future in as_completed(futures):
                file_info = futures[future]

                try:
                    result = future.result()
                    results['success'].append(result)

                    # Reducir delay adaptativo
                    self.adaptive_delay = max(0.5, self.adaptive_delay * self.adaptive_reduction_factor)

                except Exception as e:
                    error_str = str(e)

                    # Manejo de rate limits
                    if self._is_rate_limit_error(error_str):
                        logger.warning(f"Rate limit detectado, aumentando delay")
                        self.adaptive_delay *= self.rate_limit_backoff
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

    def _process_single_file_with_metrics(self, file_info: Dict, config: Dict) -> ProcessingResult:
        """Procesa archivo individual con métricas."""
        file_path = file_info['file_path']
        page_offset = file_info['page_offset']

        metrics = PerformanceMetrics()
        metrics.file_size_mb = file_info.get('size_mb', 0)

        total_start = time.time()
        max_retries = 2

        for attempt in range(max_retries + 1):
            try:
                # 1. Subida con caché
                upload_start = time.time()
                file_url = self._upload_file_cached(file_path, force_fresh=(attempt > 0))
                metrics.upload_time = time.time() - upload_start

                if attempt > 0:
                    time.sleep(2)

                # 2. Procesamiento OCR
                process_start = time.time()
                include_images = config.get("include_images", True)
                process_params = {
                    "document": {
                        "type": "document_url",
                        "document_url": file_url
                    },
                    "model": config.get('model', 'mistral-ocr-latest'),
                    "include_image_base64": include_images,
                    "table_format": config.get("table_format", "html"),
                    "extract_header": config.get("extract_header", False),
                    "extract_footer": config.get("extract_footer", False)
                }

                if getattr(self.ocr_client, 'enable_bbox_annotations', False):
                    process_params["include_image_base64"] = True
                    bbox_format = getattr(self.ocr_client, 'bbox_format', None)
                    if bbox_format:
                        process_params["bbox_annotation_format"] = bbox_format

                response = self.ocr_client.client.ocr.process(**process_params)
                metrics.processing_time = time.time() - process_start
                metrics.pages_count = len(response.pages)

                # 3. Guardado
                save_start = time.time()
                saved_files = self._save_results_optimized(
                    response, file_info, config, page_offset
                )
                metrics.save_time = time.time() - save_start

                metrics.total_time = time.time() - total_start
                self.metrics.append(metrics)

                return ProcessingResult(
                    file_path=file_path,
                    response=response,
                    saved_files=saved_files,
                    metrics=metrics,
                    page_offset=page_offset
                )

            except Exception as e:
                error_str = str(e)

                if self._is_url_fetch_error(error_str) and attempt < max_retries:
                    logger.warning(f"Error 3310 en intento {attempt + 1}, reintentando...")
                    time.sleep(3 * (attempt + 1))
                    continue

                metrics.total_time = time.time() - total_start
                logger.error(f"Error procesando {file_path}: {error_str}")
                raise

    # ==================== CACHÉ DE UPLOADS ====================

    def _upload_file_cached(self, file_path: str, force_fresh: bool = False) -> str:
        """Sube archivo con sistema de caché."""
        file_path = Path(file_path)

        self._cleanup_expired_cache()

        # Hash MD5 como clave
        content = file_path.read_bytes()
        file_hash = hashlib.md5(content).hexdigest()

        # Verificar caché
        if not force_fresh and file_hash in self.upload_cache:
            cache_entry = self.upload_cache[file_hash]
            if time.time() - cache_entry['timestamp'] < 43200:  # 12 horas
                logger.info(f"Usando URL cacheada para {file_path.name}")
                return cache_entry['url']
            else:
                del self.upload_cache[file_hash]

        # Subir archivo
        logger.info(f"Subiendo {file_path.name} ({len(content)/(1024*1024):.1f} MB)")
        uploaded = self.ocr_client.client.files.upload(
            file={"file_name": file_path.name, "content": content},
            purpose="ocr"
        )

        # Obtener URL firmada
        signed_url = self.ocr_client.client.files.get_signed_url(
            file_id=uploaded.id, expiry=24
        )

        # Guardar en caché
        self.upload_cache[file_hash] = {
            'url': signed_url.url,
            'timestamp': time.time(),
            'filename': file_path.name,
            'size_mb': len(content) / (1024 * 1024)
        }

        logger.info(f"Archivo cacheado (hash: {file_hash[:8]}...)")

        return signed_url.url

    def _cleanup_expired_cache(self):
        """Limpia entradas de caché expiradas."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.upload_cache.items()
            if current_time - entry['timestamp'] > 43200
        ]

        if expired_keys:
            for key in expired_keys:
                del self.upload_cache[key]
            logger.info(f"Limpiadas {len(expired_keys)} entradas expiradas del caché")

    # ==================== GUARDADO DE RESULTADOS ====================

    def _save_results_optimized(self, response, file_info: Dict,
                               config: Dict, page_offset: int) -> Dict:
        """Guarda resultados de forma optimizada."""
        saved_files = {}
        save_tasks = []

        # Preparar tareas de guardado
        original_file = file_info.get('original_file', file_info['file_path'])
        original_base_name = Path(original_file).stem
        output_dir = config.get('output_dir', '.')

        # Calcular nombre base con páginas
        total_pages = len(response.pages)
        start_page = page_offset + 1
        end_page = page_offset + total_pages

        if file_info['file_path'] != original_file and total_pages > 0:
            base_name = f"{original_base_name}_pag{start_page:04d}-{end_page:04d}"
        else:
            base_name = original_base_name

        # Determinar formatos a guardar
        if config.get('save_md', False):
            save_tasks.append(('md', f"{base_name}.md"))
        if config.get('save_txt', False):
            save_tasks.append(('txt', f"{base_name}.txt"))
        if config.get('save_html', False):
            save_tasks.append(('html', f"{base_name}.html"))
        if config.get('save_images', False):
            save_tasks.append(('images', f"{base_name}_images"))
        if config.get('save_json', False):
            save_tasks.append(('json', f"{base_name}.json"))

        # Ejecutar guardado en paralelo
        with ThreadPoolExecutor(max_workers=5) as save_executor:
            save_futures = {}

            for save_type, filename in save_tasks:
                future = save_executor.submit(
                    self._save_single_format,
                    response, save_type, output_dir, filename, page_offset, config, base_name
                )
                save_futures[future] = (save_type, filename)

            # Recoger resultados
            for future in as_completed(save_futures):
                save_type, filename = save_futures[future]
                try:
                    saved_path = future.result()
                    saved_files[save_type] = saved_path
                except Exception as e:
                    logger.error(f"Error guardando {save_type}: {str(e)}")

        return saved_files

    def _save_single_format(self, response, save_type: str, output_dir: str,
                           filename: str, page_offset: int, config: Dict, title: str = None) -> str:
        """Guarda un formato específico."""
        output_path = Path(output_dir) / filename
        
        # Obtener parámetros de optimización
        optimize = config.get('optimize', False)
        domain = config.get('optimization_domain', 'general')
        extract_header = config.get('extract_header', False)
        extract_footer = config.get('extract_footer', False)

        if save_type == 'md':
            return self.ocr_client.save_as_markdown(
                response, output_path, page_offset, 
                optimize=optimize, domain=domain,
                extract_header=extract_header, extract_footer=extract_footer
            )
        elif save_type == 'txt':
            return self.ocr_client.save_text(
                response, output_path, page_offset,
                optimize=optimize, domain=domain,
                extract_header=extract_header, extract_footer=extract_footer
            )
        elif save_type == 'html':
            doc_title = title.replace('_', ' ').title() if title else "Documento OCR"
            return self.ocr_client.save_as_html(
                response, output_path, page_offset, 
                optimize=optimize, domain=domain, title=doc_title
            )
        elif save_type == 'images':
            return self.ocr_client.save_images(response, output_path, page_offset)
        elif save_type == 'json':
            return self.ocr_client.save_json(response, output_path)

        return str(output_path)

    # ==================== UTILIDADES ====================

    def _group_files_by_size(self, files_info: List[Dict]) -> Dict[str, List[Dict]]:
        """Agrupa archivos por tamaño."""
        small_files = []    # < 10MB
        medium_files = []   # 10-30MB
        large_files = []    # > 30MB

        for file_info in files_info:
            size_mb = file_info.get('size_mb', 0)
            if size_mb == 0:
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
            'large': large_files,
            'medium': medium_files,
            'small': small_files
        }

    def _get_optimal_workers(self, group_name: str, file_count: int) -> int:
        """Determina número óptimo de workers."""
        if group_name == 'large':
            return min(2, file_count)
        elif group_name == 'medium':
            return min(3, file_count)
        else:
            return min(4, file_count)

    def _get_delay_for_file(self, file_size_mb: float) -> float:
        """Calcula delay adaptativo basado en tamaño."""
        if file_size_mb < 5:
            return 0.5
        elif file_size_mb < 30:
            return 1.5
        else:
            return 4.0

    def _sort_files_intelligently(self, file_paths: List[str]) -> List[str]:
        """Ordena archivos de forma inteligente."""
        def extract_order_key(filepath):
            filename = os.path.basename(filepath).lower()

            patterns = [
                (r'vol(?:umen)?[_\s]*(\d+)', 1),
                (r'tomo[_\s]*(\d+)', 1),
                (r'parte[_\s]*(\d+)', 1),
                (r'(\d+)', 1),
            ]

            for pattern, num_type in patterns:
                match = re.search(pattern, filename)
                if match:
                    return (0, int(match.group(1)))

            return (1, filename)

        return sorted(file_paths, key=extract_order_key)

    def _determine_global_strategy(self, entries: List[FileEntry]) -> str:
        """Determina estrategia global."""
        if not entries:
            return "no-files"

        requires_split = any(e.analysis and e.analysis.requires_splitting for e in entries)
        high_density = sum(1 for e in entries if e.analysis and e.analysis.density_mb_per_page > 1.0)
        low_density = sum(1 for e in entries if e.analysis and e.analysis.density_mb_per_page < 0.1)

        total = len(entries)

        if not requires_split:
            return "direct-processing"
        elif high_density > total * 0.6:
            return "image-heavy-collection"
        elif low_density > total * 0.6:
            return "text-heavy-collection"
        else:
            return "mixed-content-collection"

    def _is_rate_limit_error(self, error_str: str) -> bool:
        """Detecta errores de rate limit."""
        indicators = ['429', 'rate limit', 'too many requests']
        return any(ind in error_str.lower() for ind in indicators)

    def _is_url_fetch_error(self, error_str: str) -> bool:
        """Detecta errores de URL (código 3310)."""
        indicators = ['3310', 'could not be fetched from url']
        return any(ind in error_str.lower() for ind in indicators)

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
        logger.info(f"Tiempo total: {total_time:.1f}s")
        logger.info(f"Páginas totales: {total_pages}")
        logger.info(f"Velocidad: {total_pages/total_time:.1f} páginas/s")
        logger.info(f"Tiempos promedio - Subida: {avg_upload:.1f}s, OCR: {avg_process:.1f}s, Guardado: {avg_save:.1f}s")


# ==================== FUNCIONES DE UTILIDAD ====================

def create_optimized_processor(ocr_client, file_count: int = 1, total_size_mb: float = 0, app=None):
    """
    Crea procesador optimizado con configuración adaptativa.

    Args:
        ocr_client: Cliente OCR
        file_count: Número de archivos a procesar
        total_size_mb: Tamaño total en MB
        app: Referencia a aplicación GUI
    """
    # Determinar workers óptimos
    if file_count > 10:
        max_workers = 2
    elif file_count < 3:
        max_workers = 4
    else:
        max_workers = 3

    if total_size_mb > 500:
        max_workers = 2
    elif total_size_mb < 50:
        max_workers = 4

    return OCRBatchProcessor(ocr_client, max_workers=max_workers, app=app)


def estimate_processing_time(files_info: List[Dict]) -> Tuple[float, str]:
    """
    Estima tiempo de procesamiento.

    Returns:
        Tuple (segundos, descripción)
    """
    total_pages = 0
    total_size_mb = 0

    for file_info in files_info:
        size_mb = file_info.get('size_mb', 0)
        if size_mb > 0:
            estimated_pages = max(1, int(size_mb * 2))
            total_pages += estimated_pages
            total_size_mb += size_mb

    # 0.5 páginas por segundo + overhead
    base_time = total_pages / 0.5
    file_overhead = len(files_info) * 2
    estimated_seconds = (base_time + file_overhead) * 1.2

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
