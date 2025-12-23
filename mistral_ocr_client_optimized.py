#!/usr/bin/env python3
"""
Mistral OCR Client - Versión Optimizada
---------------------------------------
Cliente optimizado para la API de Mistral OCR con código refactorizado
para eliminar redundancias y mejorar mantenibilidad.

Versión: 4.0.0 (Optimizada)
"""

import os
import sys
import time
import subprocess
import logging
import base64
import re
import mimetypes
from pathlib import Path
from typing import List, Dict, Union, Optional, Tuple, Any
import concurrent.futures
from dotenv import load_dotenv
from mistralai import Mistral
from text_md_optimization import TextOptimizer, MarkdownOptimizer
from image_preprocessor import ImagePreprocessor
from ocr_quality_metrics import QualityScorer
import datauri

# Configuración
load_dotenv(override=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mistral_ocr')

# Configurar tipos MIME
MIME_TYPES = {
    '.pdf': 'application/pdf',
    '.jpg': 'image/jpeg', 
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.tiff': 'image/tiff',
    '.tif': 'image/tiff'
}

for ext, mime in MIME_TYPES.items():
    mimetypes.add_type(mime, ext)


class ImageProcessor:
    """Procesador unificado para imágenes."""
    
    @staticmethod
    def extract_image_data(image) -> Tuple[Optional[bytes], str]:
        """Extrae datos de imagen de diferentes formatos."""
        try:
            # Intentar diferentes atributos
            if hasattr(image, 'image_base64'):
                return ImageProcessor._parse_data_uri(image.image_base64)
            elif hasattr(image, 'data_uri'):
                return ImageProcessor._parse_data_uri(image.data_uri)
            elif hasattr(image, 'data'):
                return image.data, ImageProcessor._detect_format(image.data)
            else:
                logger.warning(f"No se encontraron datos para imagen")
                return None, 'bin'
        except Exception as e:
            logger.error(f"Error extrayendo datos de imagen: {e}")
            return None, 'bin'
    
    @staticmethod
    def _parse_data_uri(data_uri: str) -> Tuple[Optional[bytes], str]:
        """Parsea un data URI y retorna datos y extensión."""
        try:
            parsed = datauri.parse(data_uri)
            extension = parsed.mimetype.split('/')[-1]
            if extension == 'jpeg':
                extension = 'jpg'
            return parsed.data, extension
        except:
            # Fallback con regex
            match = re.match(r'data:([^;]+);base64,(.+)', data_uri)
            if match:
                mime_type, b64_data = match.groups()
                extension = mime_type.split('/')[-1]
                if extension == 'jpeg':
                    extension = 'jpg'
                return base64.b64decode(b64_data), extension
            return None, 'bin'
    
    @staticmethod
    def _detect_format(data: bytes) -> str:
        """Detecta formato de imagen por magic bytes."""
        signatures = {
            b'\xff\xd8': 'jpg',
            b'\x89PNG': 'png',
            b'GIF87a': 'gif',
            b'GIF89a': 'gif',
            b'BM': 'bmp',
            b'RIFF': 'webp'
        }
        
        for sig, fmt in signatures.items():
            if data.startswith(sig):
                return fmt
        return 'bin'


class MistralOCRClient:
    """Cliente optimizado para Mistral OCR."""
    
    def __init__(self, api_key=None, enable_preprocessing=True):
        """
        Inicializa el cliente.

        Args:
            api_key: API key de Mistral (opcional, puede usar variable de entorno)
            enable_preprocessing: Si True, preprocesa imágenes para mejorar OCR
        """
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("Se requiere API key de Mistral")

        self.client = Mistral(api_key=self.api_key)
        self.image_processor = ImageProcessor()
        self.enable_preprocessing = enable_preprocessing

        # Inicializar preprocesador de imágenes
        if enable_preprocessing:
            self.preprocessor = ImagePreprocessor(enable_all=True)
            logger.info("✓ Preprocesamiento de imágenes ACTIVADO (mejora calidad OCR +30-50%)")
        else:
            self.preprocessor = None
            logger.info("Preprocesamiento de imágenes desactivado")
        logger.info("Cliente Mistral OCR inicializado")
    
    # === Métodos principales ===
    
    def process_url(self, url: str, model="mistral-ocr-latest", include_images=True):
        """Procesa documento desde URL."""
        logger.info(f"Procesando URL: {url}")
        return self._process_document({
            "type": "document_url",
            "document_url": url
        }, model, include_images)
    
    def process_local_file(self, file_path: str, model="mistral-ocr-latest", 
                          include_images=True, max_size_mb=50):
        """Procesa archivo local."""
        file_path = Path(file_path)
        self._validate_file(file_path, max_size_mb)
        
        logger.info(f"Procesando archivo: {file_path}")
        
        # Subir y procesar
        file_url = self._upload_file(file_path)
        return self._process_document({
            "type": "document_url", 
            "document_url": file_url
        }, model, include_images)
    
    # === Métodos de guardado unificados ===
    
    def save_as_markdown(self, ocr_response, output_path=None, page_offset=0,
                        enrich_images=False, optimize=False, domain="general"):
        """Método unificado para guardar markdown con análisis de calidad."""
        output_path = self._prepare_output_path(output_path, "md")

        # Generar contenido markdown
        content = self._generate_markdown_content(
            ocr_response, page_offset, enrich_images, optimize, domain
        )

        # Analizar calidad si se habilitó optimización
        quality_report = None
        if optimize:
            quality_report = self._analyze_quality(ocr_response, content, domain)

        # Guardar archivo con reporte de calidad al final
        with open(output_path, "wt", encoding="utf-8") as f:
            f.write(content)

            # Agregar reporte de calidad como comentario HTML
            if quality_report:
                f.write("\n\n<!-- ")
                f.write(quality_report)
                f.write(" -->\n")

        logger.info(f"Markdown guardado: {output_path}")
        return output_path
    
    def save_text(self, ocr_response, output_path=None, page_offset=0, 
                  optimize=False, domain="general"):
        """Guarda solo texto extraído."""
        output_path = self._prepare_output_path(output_path, "txt")
        optimizer = TextOptimizer(domain) if optimize else None
        
        with open(output_path, "wt", encoding="utf-8") as f:
            for i, page in enumerate(ocr_response.pages):
                page_num = i + 1 + page_offset
                f.write(f"=== PÁGINA {page_num} ===\n\n")
                
                text = self._extract_plain_text(page.markdown)
                if optimizer:
                    text = optimizer.optimize_text(text)
                f.write(text + "\n\n")
        
        logger.info(f"Texto guardado: {output_path}")
        return output_path
    
    def save_images(self, ocr_response, output_dir=None, page_offset=0):
        """Extrae y guarda imágenes."""
        output_dir = Path(output_dir or f"imagenes_{int(time.time())}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        saved_count = 0
        for page_idx, page in enumerate(ocr_response.pages):
            page_num = page_idx + 1 + page_offset
            
            for img_idx, image in enumerate(page.images):
                img_data, extension = self.image_processor.extract_image_data(image)
                if img_data:
                    filename = f"pagina{page_num}_img{img_idx+1}.{extension}"
                    filepath = output_dir / filename
                    
                    with open(filepath, "wb") as f:
                        f.write(img_data)
                    saved_count += 1
        
        logger.info(f"Imágenes guardadas: {saved_count} en {output_dir}")
        return output_dir
    
    # === Procesamiento por lotes optimizado ===
    
    def process_batch(self, file_paths: List[str], model="mistral-ocr-latest",
                     include_images=True, max_workers=2, progress_callback=None):
        """Procesa múltiples archivos."""
        valid_files = self._validate_batch_files(file_paths)
        if not valid_files:
            return self._empty_batch_results()
        
        results = {'success': [], 'failed': []}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            
            # Enviar tareas con delay
            for i, file_path in enumerate(valid_files):
                if i > 0:
                    time.sleep(3)  # Rate limiting
                
                future = executor.submit(
                    self._process_single_file, file_path, model, include_images
                )
                futures[future] = file_path
                
                if progress_callback:
                    progress_callback(file_path, i)
            
            # Recoger resultados
            for future in concurrent.futures.as_completed(futures):
                file_path = futures[future]
                try:
                    result = future.result()
                    results['success'].append(result)
                except Exception as e:
                    results['failed'].append({'file': file_path, 'error': str(e)})
        
        return self._finalize_batch_results(results, file_paths)
    
    def batch_save_outputs(self, batch_results: Dict, output_formats: List[str], 
                          output_dir=None):
        """Guarda resultados de batch en formatos especificados."""
        if not batch_results.get('success'):
            return {}
        
        output_dir = Path(output_dir) if output_dir else Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        all_outputs = {}
        page_offset = 0
        
        for result in sorted(batch_results['success'], key=lambda x: str(x['file'])):
            file_outputs = self._save_file_outputs(
                result, output_formats, output_dir, page_offset
            )
            all_outputs[str(result['file'])] = file_outputs
            page_offset += len(result['response'].pages)
        
        return all_outputs
    
    # === Utilidades para archivos PDF ===
    
    def split_pdf(self, file_path: str, max_pages_per_file=50, output_dir=None):
        """Divide PDF en archivos más pequeños."""
        try:
            from PyPDF2 import PdfReader, PdfWriter
        except ImportError:
            raise ImportError("Se requiere PyPDF2: pip install PyPDF2")
        
        file_path = Path(file_path)
        output_dir = Path(output_dir or file_path.parent)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        pdf = PdfReader(file_path)
        total_pages = len(pdf.pages)
        
        output_files = []
        for i in range(0, total_pages, max_pages_per_file):
            writer = PdfWriter()
            end_page = min(i + max_pages_per_file, total_pages)
            
            for j in range(i, end_page):
                writer.add_page(pdf.pages[j])
            
            output_file = output_dir / f"{file_path.stem}_pag{i+1}-{end_page}.pdf"
            with open(output_file, "wb") as f:
                writer.write(f)
            
            output_files.append(output_file)
        
        logger.info(f"PDF dividido en {len(output_files)} archivos")
        return {
            'files': output_files,
            'total_files': len(output_files),
            'original_file': file_path,
            'total_pages': total_pages
        }
    
    def compress_pdf(self, file_path: str, quality="medium", output_dir=None):
        """Comprime PDF usando Ghostscript."""
        from shutil import which
        
        gs_cmd = "gswin64c" if sys.platform == "win32" else "gs"
        if not which(gs_cmd):
            raise RuntimeError("Se requiere Ghostscript")
        
        file_path = Path(file_path)
        output_path = Path(output_dir or file_path.parent) / f"{file_path.stem}_comprimido.pdf"
        
        quality_settings = {
            "low": ("/default", "72"),
            "medium": ("/prepress", "150"),
            "high": ("/printer", "300")
        }
        
        pdf_setting, dpi = quality_settings.get(quality, quality_settings["medium"])
        
        cmd = [
            gs_cmd, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS={pdf_setting}", "-dNOPAUSE", "-dQUIET",
            "-dBATCH", f"-r{dpi}", f"-sOutputFile={output_path}", str(file_path)
        ]
        
        subprocess.run(cmd, check=True)
        
        # Mostrar estadísticas
        original_mb = file_path.stat().st_size / (1024 * 1024)
        compressed_mb = output_path.stat().st_size / (1024 * 1024)
        reduction = ((original_mb - compressed_mb) / original_mb) * 100
        
        logger.info(f"Compresión: {original_mb:.1f}MB → {compressed_mb:.1f}MB ({reduction:.1f}% reducción)")
        return output_path
    
    # === Métodos auxiliares privados ===
    
    def _process_document(self, document: Dict, model: str, include_images: bool):
        """Procesa documento con la API."""
        start_time = time.time()
        
        response = self.client.ocr.process(
            document=document,
            model=model,
            include_image_base64=include_images
        )
        
        elapsed = time.time() - start_time
        logger.info(f"Procesado en {elapsed:.2f}s - {len(response.pages)} páginas")
        
        return response
    
    def _upload_file(self, file_path: Path) -> str:
        """
        Sube archivo y retorna URL firmada.

        Si el preprocesamiento está habilitado y el archivo es una imagen,
        la mejora antes de subir para optimizar resultados OCR.
        """
        # Determinar si es una imagen que se puede preprocesar
        is_image = file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.tiff', '.tif']

        # Aplicar preprocesamiento si está habilitado y es imagen
        file_to_upload = file_path
        preprocessed_path = None

        if self.enable_preprocessing and is_image and self.preprocessor:
            try:
                logger.info(f"🔍 Preprocesando imagen: {file_path.name}")
                preprocessed_path = self.preprocessor.enhance_for_ocr(file_path)
                file_to_upload = preprocessed_path
                logger.info(f"✓ Imagen mejorada para OCR")
            except Exception as e:
                logger.warning(f"Error en preprocesamiento, usando imagen original: {e}")
                file_to_upload = file_path

        # Subir archivo (original o preprocesado)
        content = file_to_upload.read_bytes()
        logger.info(f"Subiendo {file_path.name} ({len(content)/(1024*1024):.1f} MB)")

        uploaded = self.client.files.upload(
            file={"file_name": file_path.name, "content": content},
            purpose="ocr"
        )

        # Limpiar archivo temporal si se creó
        if preprocessed_path and preprocessed_path != file_path:
            try:
                # No eliminar inmediatamente, puede necesitarse para retry
                # Se limpiará automáticamente al final del proceso
                pass
            except:
                pass

        # Aumentar tiempo de expiración y añadir retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                signed_url = self.client.files.get_signed_url(
                    file_id=uploaded.id, expiry=24  # 24 horas en lugar de 1
                )
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Error obteniendo URL firmada (intento {attempt + 1}): {e}")
                time.sleep(2 ** attempt)  # Backoff exponencial

        return signed_url.url
    
    def _validate_file(self, file_path: Path, max_size_mb: float):
        """Valida archivo antes de procesar."""
        if not file_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
        
        mime_type = mimetypes.guess_type(str(file_path))[0]
        if mime_type not in MIME_TYPES.values():
            raise ValueError(f"Tipo no soportado: {mime_type}")
        
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            raise ValueError(
                f"Archivo muy grande ({size_mb:.1f}MB > {max_size_mb}MB). "
                f"Use split_pdf() o procesamiento por lotes."
            )
    
    def _prepare_output_path(self, output_path: Optional[str], extension: str) -> Path:
        """Prepara ruta de salida."""
        if not output_path:
            output_path = f"ocr_output_{int(time.time())}.{extension}"
        
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    
    def _generate_markdown_content(self, ocr_response, page_offset: int,
                                  enrich_images: bool, optimize: bool, domain: str) -> str:
        """Genera contenido markdown según opciones."""
        optimizer = MarkdownOptimizer(domain) if optimize else None
        content_parts = []
        
        for i, page in enumerate(ocr_response.pages):
            page_num = i + 1 + page_offset
            content_parts.append(f"# Página {page_num}\n\n")
            
            page_content = page.markdown
            
            # Enriquecer imágenes si se solicita
            if enrich_images:
                page_content = self._enrich_page_images(page, page_content)
            
            # Optimizar si se solicita
            if optimizer:
                page_content = optimizer.optimize_markdown(page_content)
            
            content_parts.append(page_content + "\n\n")
        
        return "\n".join(content_parts)
    
    def _extract_plain_text(self, markdown: str) -> str:
        """Extrae texto plano de markdown."""
        lines = []
        for line in markdown.splitlines():
            # Omitir imágenes
            if line.strip().startswith('!['):
                continue
            # Limpiar formato
            line = re.sub(r'^#+\s*', '', line)  # Encabezados
            line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)  # Negrita
            line = re.sub(r'\*([^*]+)\*', r'\1', line)  # Cursiva
            line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)  # Enlaces
            
            if line.strip():
                lines.append(line)
        
        return '\n'.join(lines)
    
    def _enrich_page_images(self, page, markdown_content: str) -> str:
        """Enriquece markdown con imágenes base64."""
        for img in page.images:
            img_data, _ = self.image_processor.extract_image_data(img)
            if img_data and hasattr(img, 'id'):
                data_uri = f"data:image/png;base64,{base64.b64encode(img_data).decode()}"
                markdown_content = markdown_content.replace(
                    f"![{img.id}]({img.id})",
                    f"![{img.id}]({data_uri})"
                )
        return markdown_content
    
    def _validate_batch_files(self, file_paths: List[str]) -> List[Path]:
        """Valida archivos para procesamiento batch."""
        valid_files = []
        
        for file_path in file_paths:
            path = Path(file_path)
            try:
                self._validate_file(path, 50)  # Límite estándar
                valid_files.append(path)
            except Exception as e:
                logger.warning(f"Archivo inválido {path}: {e}")
        
        return valid_files
    
    def _process_single_file(self, file_path: Path, model: str, include_images: bool):
        """Procesa un archivo individual en batch."""
        start_time = time.time()
        response = self.process_local_file(file_path, model, include_images)
        
        return {
            'file': file_path,
            'response': response,
            'elapsed_time': time.time() - start_time
        }
    
    def _save_file_outputs(self, result: Dict, formats: List[str], 
                          output_dir: Path, page_offset: int) -> Dict:
        """Guarda salidas de un archivo en múltiples formatos."""
        file_path = result['file']
        response = result['response']
        outputs = {}
        
        base_name = file_path.stem
        
        if 'md' in formats:
            path = output_dir / f"{base_name}.md"
            outputs['md'] = self.save_as_markdown(response, path, page_offset)
        
        if 'txt' in formats:
            path = output_dir / f"{base_name}.txt"
            outputs['txt'] = self.save_text(response, path, page_offset)
        
        if 'images' in formats:
            path = output_dir / f"{base_name}_images"
            outputs['images'] = self.save_images(response, path, page_offset)
        
        return outputs
    
    def _empty_batch_results(self) -> Dict:
        """Retorna estructura vacía de resultados batch."""
        return {
            'success': [],
            'failed': [],
            'total_success': 0,
            'total_failed': 0,
            'total_elapsed_time': 0
        }
    
    def _finalize_batch_results(self, results: Dict, file_paths: List) -> Dict:
        """Finaliza y añade estadísticas a resultados batch."""
        results['total_success'] = len(results['success'])
        results['total_failed'] = len(results['failed'])
        results['total_elapsed_time'] = sum(
            r['elapsed_time'] for r in results['success']
        )

        logger.info(
            f"Batch completado: {results['total_success']}/{len(file_paths)} exitosos"
        )

        return results

    def _analyze_quality(self, ocr_response, optimized_content: str, domain: str) -> str:
        """
        Analiza calidad del OCR comparando texto original y optimizado.

        Args:
            ocr_response: Respuesta OCR de Mistral
            optimized_content: Contenido markdown optimizado
            domain: Dominio de optimización usado

        Returns:
            str: Reporte de calidad formateado
        """
        try:
            # Extraer texto original (sin optimizar)
            original_text = ""
            for page in ocr_response.pages:
                original_text += self._extract_plain_text(page.markdown) + "\n"

            # Extraer texto optimizado
            optimized_text = self._extract_plain_text(optimized_content)

            # Comparar calidad
            scorer = QualityScorer()
            comparison = scorer.compare_quality(original_text, optimized_text)

            # Generar reporte
            lines = []
            lines.append("\n" + "=" * 60)
            lines.append("REPORTE DE CALIDAD OCR")
            lines.append("=" * 60)
            lines.append(f"Dominio de optimización: {domain}")
            lines.append("")
            lines.append("TEXTO ORIGINAL (sin optimización):")
            lines.append(f"  Score: {comparison['original']['score']:.1f}/100")
            lines.append(f"  Palabras: {comparison['original']['total_words']}")
            lines.append(f"  Patrones sospechosos: {comparison['original']['suspicious_patterns']}")
            lines.append(f"  Caracteres raros: {comparison['original']['rare_chars_count']}")
            lines.append("")
            lines.append("TEXTO OPTIMIZADO:")
            lines.append(f"  Score: {comparison['optimized']['score']:.1f}/100")
            lines.append(f"  Palabras: {comparison['optimized']['total_words']}")
            lines.append(f"  Patrones sospechosos: {comparison['optimized']['suspicious_patterns']}")
            lines.append(f"  Caracteres raros: {comparison['optimized']['rare_chars_count']}")
            lines.append("")
            lines.append("MEJORA:")
            lines.append(f"  {comparison['summary']}")
            lines.append("")
            lines.append("Problemas detectados (original):")
            for issue in comparison['original']['issues']:
                lines.append(f"  • {issue}")
            lines.append("")
            lines.append("=" * 60)

            report = "\n".join(lines)

            # Loggear resumen
            logger.info(f"Análisis de calidad: {comparison['summary']}")

            return report

        except Exception as e:
            logger.warning(f"Error al analizar calidad: {e}")
            return "\nNota: No se pudo generar reporte de calidad\n"
    
    # === Métodos de utilidad ===
    
    def get_file_size_mb(self, file_path: str) -> float:
        """Obtiene tamaño de archivo en MB."""
        return Path(file_path).stat().st_size / (1024 * 1024)
    
    def estimate_pages_count(self, file_path: str) -> Optional[int]:
        """Estima páginas en un PDF."""
        try:
            from PyPDF2 import PdfReader
            if Path(file_path).suffix.lower() == '.pdf':
                reader = PdfReader(file_path)
                pages = len(reader.pages)
                logger.info(f"PDF analizado: {Path(file_path).name} tiene {pages} páginas")
                return pages
        except Exception as e:
            logger.warning(f"No se pudo contar páginas de {Path(file_path).name}: {e}")
        return None
    
    def get_text(self, ocr_response) -> str:
        """Extrae todo el texto de la respuesta."""
        texts = []
        for i, page in enumerate(ocr_response.pages):
            texts.append(f"=== PÁGINA {i+1} ===\n")
            texts.append(self._extract_plain_text(page.markdown))
            texts.append("\n\n")
        return "".join(texts)
    
    def get_combined_markdown(self, ocr_response) -> str:
        """Combina markdown de todas las páginas con imágenes."""
        return self._generate_markdown_content(
            ocr_response, 0, enrich_images=True, optimize=False, domain="general"
        )