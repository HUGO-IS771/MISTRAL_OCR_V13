#!/usr/bin/env python3
"""
Mistral OCR Client - Versión Optimizada
---------------------------------------
Cliente optimizado para la API de Mistral OCR con código refactorizado
para eliminar redundancias y mejorar mantenibilidad.

Versión: 4.0.0 (Optimizada)
"""

import os
import time
import logging
import base64
import re
import mimetypes
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import concurrent.futures
from dotenv import load_dotenv
from mistralai import Mistral
from text_md_optimization import TextOptimizer, MarkdownOptimizer
from image_preprocessor import ImagePreprocessor
from ocr_quality_metrics import QualityScorer
from processing_limits import LIMITS
import datauri
import json
import html as html_lib

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


def _resolve_table_injections(page_content: str, page, use_tokens: bool = False) -> Tuple[str, Dict[str, str]]:
    """
    Resuelve la inyección de tablas manejando índices globales y protección de contenido.

    Args:
        page_content: Markdown original
        page: Objeto Page de Mistral OCR
        use_tokens: Si True, reemplaza con tokens seguros (para optimización posterior)
                    Si False, reemplaza directamente con HTML

    Returns:
        Tuple[str, Dict]: (contenido_modificado, mapa_de_tokens_a_html)
    """
    token_map = {}
    
    # Verificar si hay tablas
    if not hasattr(page, 'tables') or not page.tables:
        return page_content, token_map

    # 1. Encontrar todos los placeholders reales en el texto (ej: tbl-5.html, tbl-12.html)
    # Mistral usa índices globales, no reinician por página.
    # Regex busca patrones 'tbl-NUM.html'
    found_placeholders = sorted(list(set(re.findall(r'tbl-\d+\.html', page_content))), 
                              key=lambda x: int(re.search(r'\d+', x).group()))

    tables = page.tables
    
    # Validación básica
    if not found_placeholders:
        return page_content, token_map
        
    if len(found_placeholders) != len(tables):
        logger.warning(f"Desajuste de tablas: Encontrados {len(found_placeholders)} placeholders para {len(tables)} tablas.")
    
    # 2. Mapear placeholders encontrados a tablas disponibles (en orden)
    for i, (placeholder, table_obj) in enumerate(zip(found_placeholders, tables)):
        # Extraer contenido HTML del objeto tabla
        if hasattr(table_obj, 'content') and isinstance(table_obj.content, str):
            table_html = table_obj.content
        else:
            table_html = str(table_obj)

        # Preparar el contenido a inyectar (Token o HTML final)
        if use_tokens:
            replacement = f"__OCR_TABLE_TOKEN_{i}__"
            # Guardar el mapeo del token al HTML final (envuelto)
            wrapped_table = f'\\n\\n<div class="ocr-table">\\n{table_html}\\n</div>\\n\\n'
            token_map[replacement] = wrapped_table
        else:
            replacement = f'\\n\\n<div class="ocr-table">\\n{table_html}\\n</div>\\n\\n'

        # 3. Realizar reemplazos en el texto
        # Patrones posibles en el markdown
        patterns = [
            f'[{placeholder}]({placeholder})',  # [tbl-1.html](tbl-1.html)
            f'<a href="{placeholder}">{placeholder}</a>', # HTML anchor
            f'[{placeholder}]',
            placeholder # Fallback directo
        ]
        
        replaced = False
        for pattern in patterns:
            if pattern in page_content:
                page_content = page_content.replace(pattern, replacement)
                replaced = True
        
        if not replaced:
             # Intento final con regex para variantes
             clean_ph = re.escape(placeholder)
             page_content = re.sub(rf'\[{clean_ph}\]\({clean_ph}\)', replacement, page_content)

    return page_content, token_map


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
    
    def __init__(self, api_key=None, enable_preprocessing=True, enable_bbox_annotations=False):
        """
        Inicializa el cliente.

        Args:
            api_key: API key de Mistral (opcional, puede usar variable de entorno)
            enable_preprocessing: Si True, preprocesa imágenes para mejorar OCR
            enable_bbox_annotations: Si True, activa descripciones automáticas de imágenes con BBox Annotations
        """
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("Se requiere API key de Mistral")

        self.client = Mistral(api_key=self.api_key)
        self.image_processor = ImageProcessor()
        self.enable_preprocessing = enable_preprocessing
        self.enable_bbox_annotations = enable_bbox_annotations

        # Inicializar preprocesador de imágenes
        if enable_preprocessing:
            self.preprocessor = ImagePreprocessor(enable_all=True)
            logger.info("✓ Preprocesamiento de imágenes ACTIVADO (mejora calidad OCR +30-50%)")
        else:
            self.preprocessor = None
            logger.info("Preprocesamiento de imágenes desactivado")

        # Inicializar BBox annotations si está habilitado
        self.bbox_format = None
        if enable_bbox_annotations:
            try:
                from bbox_annotations import create_bbox_annotation_format
                self.bbox_format = create_bbox_annotation_format()
                logger.info("✓ BBox Annotations ACTIVADO (descripciones automáticas de imágenes)")
            except ImportError:
                logger.warning("bbox_annotations.py no encontrado. BBox annotations desactivado.")
                self.enable_bbox_annotations = False
            except Exception as e:
                logger.warning(f"Error inicializando BBox annotations: {e}. Desactivado.")
                self.enable_bbox_annotations = False

        logger.info("Cliente Mistral OCR inicializado")
    
    # === Métodos principales ===
    
    def process_url(self, url: str, model="mistral-ocr-latest", include_images=True, **kwargs):
        """Procesa documento desde URL."""
        logger.info(f"Procesando URL: {url}")
        return self._process_document({
            "type": "document_url",
            "document_url": url
        }, model, include_images, **kwargs)
    
    def process_local_file(self, file_path: str, model="mistral-ocr-latest",
                          include_images=True, max_size_mb=None, **kwargs):
        """Procesa archivo local."""
        file_path = Path(file_path)
        # Usar límite centralizado si no se especifica
        if max_size_mb is None:
            max_size_mb = LIMITS.DEFAULT_MAX_SIZE_MB
        self._validate_file(file_path, max_size_mb)
        
        logger.info(f"Procesando archivo: {file_path}")
        
        # Subir y procesar
        file_url = self._upload_file(file_path)
        return self._process_document({
            "type": "document_url", 
            "document_url": file_url
        }, model, include_images, **kwargs)
    
    # === Métodos de guardado unificados ===
    
    def save_as_markdown(self, ocr_response, output_path=None, page_offset=0,
                        enrich_images=False, optimize=False, domain="general",
                        extract_header=False, extract_footer=False):
        """
        Método unificado para guardar markdown con análisis de calidad.
        
        Args:
            extract_header: Incluir headers de Mistral OCR 3
            extract_footer: Incluir footers de Mistral OCR 3
        """
        output_path = self._prepare_output_path(output_path, "md")

        # Generar contenido markdown
        content = self._generate_markdown_content(
            ocr_response, page_offset, enrich_images, optimize, domain,
            extract_header=extract_header, extract_footer=extract_footer
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
                  optimize=False, domain="general", extract_header=False, extract_footer=False):
        """
        Guarda solo texto extraído, con optimización legal si se solicita.
        
        Args:
            extract_header: Incluir headers de Mistral OCR 3
            extract_footer: Incluir footers de Mistral OCR 3
        """
        output_path = self._prepare_output_path(output_path, "txt")
        
        # IMPORTANTE: Para dominios legales, usar el mismo pipeline que Markdown
        # para aplicar la optimización de documento completo
        if optimize and domain in ["legal", "articulos"]:
            # Usar el pipeline de markdown optimizado
            # INCLUIR headers/footers si se solicitaron (igual que en Markdown)
            markdown_content = self._process_pages_to_markdown(
                ocr_response, page_offset, optimize=True, domain=domain,
                page_header_fn=None,  # Sin headers de página para texto plano
                image_processor_fn=None,
                include_headers_footers=False,  # Se controla individualmente con extract_header/extract_footer
                extract_header=extract_header,
                extract_footer=extract_footer,
                separator="\n\n"
            )
            # Convertir markdown a texto plano (quitar formato markdown pero mantener estructura)
            text_content = self._extract_plain_text(markdown_content)
        else:
            # Para otros dominios, usar get_text() original
            text_content = self.get_text(ocr_response, page_offset, optimize, domain)

        with open(output_path, "wt", encoding="utf-8") as f:
            f.write(text_content)

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
    
    def save_as_html(self, ocr_response, output_path=None, page_offset=0,
                     optimize=False, domain="general", title="Documento OCR",
                     theme="light"):
        """
        Guarda el documento como HTML premium con imágenes incrustadas.
        
        Args:
            ocr_response: Respuesta OCR de Mistral
            output_path: Ruta de salida (opcional)
            page_offset: Offset para numeración de páginas
            optimize: Aplicar optimización de texto
            domain: Dominio de optimización
            title: Título del documento HTML
            theme: 'light' o 'dark' para el tema visual
            
        Returns:
            Path: Ruta del archivo HTML generado
        """
        output_path = self._prepare_output_path(output_path, "html")

        # Generar contenido HTML directamente (no usar markdown para imágenes)
        html_body = self._generate_html_content_with_images(
            ocr_response, page_offset, optimize, domain
        )

        # Generar HTML completo con estilos premium
        html_content = self._generate_premium_html(
            html_body, title, theme,
            total_pages=len(ocr_response.pages),
            total_images=sum(len(p.images) for p in ocr_response.pages)
        )

        # Guardar archivo
        with open(output_path, "wt", encoding="utf-8") as f:
            f.write(html_content)
        
        logger.info(f"HTML guardado: {output_path}")
        return output_path
    
    def save_json(self, ocr_response, output_path=None):
        """
        Guarda la respuesta completa de la API en formato JSON.
        Útil para depuración y para conservar toda la estructura de Mistral OCR 3.
        """
        output_path = self._prepare_output_path(output_path, "json")
        
        # Convertir objeto de respuesta a diccionario serializable
        try:
            # Si el objeto tiene un método model_dump o dict (Pydantic v2/v1)
            if hasattr(ocr_response, 'model_dump'):
                data = ocr_response.model_dump()
            elif hasattr(ocr_response, 'dict'):
                data = ocr_response.dict()
            else:
                # Fallback manual si no es un objeto Pydantic
                data = json.loads(json.dumps(ocr_response, default=lambda o: getattr(o, '__dict__', str(o))))
        except Exception as e:
            logger.error(f"Error serializando respuesta OCR a JSON: {e}")
            # Intentar fallback más agresivo si falla
            data = str(ocr_response)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"JSON guardado: {output_path}")
        return output_path
    
    def _generate_html_content_with_images(self, ocr_response, page_offset: int,
                                           optimize: bool, domain: str) -> str:
        """
        Genera contenido markdown con imágenes incrustadas como data URIs.
        El markdown será procesado por marked.js en el navegador.

        IMPORTANTE: Escapa referencias jurisprudenciales que usan <> para evitar
        que marked.js las interprete como tags HTML.
        """
        markdown = self._process_pages_to_markdown(
            ocr_response, page_offset, optimize, domain,
            page_header_fn=lambda num: f"\n\n---\n\n## 📄 Página {num}\n\n",
            image_processor_fn=lambda p, c: self._enrich_page_images(p, c, correct_mime=True),
            include_headers_footers=False,
            separator=""
        )

        # Escapar referencias jurisprudenciales que causan problemas con marked.js
        # Estas referencias usan <> y marked.js las interpreta como HTML tags
        markdown = self._escape_legal_references(markdown)

        return markdown

    def _escape_legal_references(self, markdown: str) -> str:
        """
        Escapa referencias jurisprudenciales que usan <> para evitar que marked.js
        las interprete como tags HTML malformados.

        Las referencias jurisprudenciales mexicanas usan formato como:
        - <1a.j. 35/2019 (10a.)>
        - <P.J. 11/2018 (10a.)>
        - <2a./J. 123/2014 (10a.)>

        También maneja casos ALTAMENTE corruptos de Mistral API como:
        - <p.j. 32="" 99,="" p.j.="" 1="" 97="">
        - <p.j. (10a.)="" 21="" 2014="" 2015="" 99="" a="" aplicación="" ...>

        Estrategia: Escapar TODOS los tags que contengan indicadores de referencias
        jurisprudenciales, sin importar cuán corruptos estén.

        Args:
            markdown: Texto markdown con posibles referencias jurisprudenciales

        Returns:
            Markdown con referencias escapadas usando entidades HTML
        """
        import re

        def escape_match(match):
            """Reemplaza < y > por entidades HTML en la referencia."""
            reference = match.group(0)
            return reference.replace('<', '&lt;').replace('>', '&gt;')

        # ESTRATEGIA AGRESIVA: Capturar TODO lo que parezca una referencia legal
        # incluso si está extremadamente corrupto

        # Lista de todos los patrones a escapar
        patterns = [
            # 1. Referencias normales con números y letras
            # <1a.j. 35/2019 (10a.)>, <1a. CCCXXVII/2014 (10a.)>
            r'<\d+[aA]\.(?:/)?[jJ]?\.?\s*[^>]+?>',

            # 2. Referencias que empiezan con P (P.J., p.j.)
            # <P.J. 11/2018 (10a.)>, <p.j. ...>
            r'<[PAp]\.?[jJ]?\.?\s*[^>]+?>',

            # 3. Referencias de registro
            # <Reg. 239099>, <reg. 123456>
            r'<[Rr]eg\.\s*[^>]+?>',

            # 4. Tags con atributos HTML corruptos (contienen ="" o ="")
            # <p.j. 32="" 99,="" ...>, <1a. (10a.)="" 21="" ...>
            r'<[^>]*?=""[^>]*?>',

            # 5. Tags que contienen el patrón (10a.) o (9a.) o similar
            # Esto captura referencias corruptas que contienen épocas
            r'<[^>]*?\(\d+a\.\)[^>]*?>',

            # 6. Tags que contienen números romanos (referencias a artículos)
            # <I/2019>, <CCCXXVII/2014>
            r'<[IVXLCDM]+/\d{4}[^>]*?>',

            # 7. Tags que contienen patrones como "2a./J."
            r'<\d+[aA]\./[JjPp][^>]*?>',
        ]

        escaped_markdown = markdown
        for pattern in patterns:
            escaped_markdown = re.sub(pattern, escape_match, escaped_markdown)

        return escaped_markdown

    def _generate_premium_html(self, body_content: str, title: str, theme: str,
                               total_pages: int, total_images: int) -> str:
        """Genera HTML completo con estilos premium."""

        from html_templates import render_premium_html

        return render_premium_html(
            body_content=body_content,
            title=title,
            theme=theme,
            total_pages=total_pages,
            total_images=total_images
        )

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
        import sys
        import subprocess
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

    def _process_pages_to_markdown(self, ocr_response, page_offset: int,
                                   optimize: bool, domain: str,
                                   page_header_fn=None,
                                   image_processor_fn=None,
                                   include_headers_footers: bool = True,
                                   extract_header: bool = None,
                                   extract_footer: bool = None,
                                   separator: str = "\n\n") -> str:
        """
        Método base unificado para procesar páginas OCR a markdown.

        Args:
            ocr_response: Respuesta OCR de Mistral
            page_offset: Offset para numeración de páginas
            optimize: Aplicar optimización de markdown
            domain: Dominio de optimización
            page_header_fn: Función para generar header de página (recibe page_num)
            image_processor_fn: Función para procesar imágenes (recibe page, content)
            include_headers_footers: Incluir headers/footers de Mistral OCR 3
            separator: Separador entre páginas

        Returns:
            str: Contenido markdown generado
        """
        # Determinar si necesitamos optimización de documento completo (para legal/articulos)
        needs_full_document_optimization = optimize and domain in ["legal", "articulos"]
        
        # Crear optimizador solo para dominios NO legales (optimización por página)
        page_optimizer = MarkdownOptimizer(domain) if (optimize and not needs_full_document_optimization) else None
        
        content_parts = []
        all_token_maps = {}  # Para restaurar tablas después de optimización de doc completo

        for i, page in enumerate(ocr_response.pages):
            page_num = i + 1 + page_offset

            # Header de página (customizable)
            if page_header_fn:
                content_parts.append(page_header_fn(page_num))

            # Encabezado de documento (Mistral OCR 3)
            # Respeta extract_header si se especifica, sino usa include_headers_footers
            # IMPORTANTE: En dominios legales ('articulos', 'legal'), NO incluir el encabezado en el texto
            # para mantener la continuidad, aunque se haya extraído (eliminado del body).
            should_include_header = (extract_header if extract_header is not None else include_headers_footers)
            if domain in ['legal', 'articulos']:
                should_include_header = False
                
            if should_include_header and hasattr(page, 'header') and page.header:
                content_parts.append(f"**Encabezado:** {page.header}\n\n")

            # Obtener contenido markdown
            page_content = page.markdown

            # CRÍTICO: Procesar tablas HTML (reemplazar placeholders tbl-X.html)
            # PROTECCIÓN: Si se va a optimizar, usamos tokens para proteger el HTML
            use_tokens = optimize  # Siempre usar tokens si hay optimización
            page_content, token_map = _resolve_table_injections(page_content, page, use_tokens=use_tokens)
            
            # Guardar token_map para restauración posterior
            all_token_maps.update(token_map)

            # Procesar imágenes (customizable)
            if image_processor_fn:
                page_content = image_processor_fn(page, page_content)

            # Optimizar markdown POR PÁGINA (solo para dominios NO legales)
            if page_optimizer:
                page_content = page_optimizer.optimize_markdown(page_content)
                
                # RESTAURAR tablas protegidas
                if token_map:
                    for token, html_content in token_map.items():
                        page_content = page_content.replace(token, html_content)
                    logger.debug(f"Página {page_num}: {len(token_map)} tablas restauradas post-optimización")

            content_parts.append(page_content)

            # Pie de página de documento (Mistral OCR 3)
            # Respeta extract_footer si se especifica, sino usa include_headers_footers
            # IMPORTANTE: En dominios legales, NO incluir el pie de página
            should_include_footer = (extract_footer if extract_footer is not None else include_headers_footers)
            if domain in ['legal', 'articulos']:
                should_include_footer = False
                
            if should_include_footer and hasattr(page, 'footer') and page.footer:
                content_parts.append(f"\n\n**Pie de página:** {page.footer}")

            # Separador entre páginas
            if i < len(ocr_response.pages) - 1:
                content_parts.append(separator)

        # Ensamblar documento
        full_document = "".join(content_parts)
        
        # OPTIMIZACIÓN DE DOCUMENTO COMPLETO (para legal/articulos)
        if needs_full_document_optimization:
            logger.info(f"🔧 Aplicando optimización de documento completo para dominio: {domain}")
            full_doc_optimizer = MarkdownOptimizer(domain)
            logger.info(f"   Optimizer creado: {full_doc_optimizer}, legal_optimizer: {full_doc_optimizer.legal_optimizer}")
            full_document = full_doc_optimizer.optimize_markdown(full_document)
            logger.info(f"   Optimización completada. Longitud resultado: {len(full_document)} chars")
            
            # Restaurar TODAS las tablas protegidas
            if all_token_maps:
                for token, html_content in all_token_maps.items():
                    full_document = full_document.replace(token, html_content)
                logger.info(f"Documento completo: {len(all_token_maps)} tablas restauradas post-optimización legal")

        return full_document

    def _process_document(self, document: Dict, model: str, include_images: bool, **kwargs):
        """
        Procesa documento con la API.

        Si enable_bbox_annotations está activo, agrega bbox_annotation_format
        para obtener descripciones automáticas de imágenes.
        """
        start_time = time.time()

        # Construir parámetros de la llamada
        process_params = {
            "document": document,
            "model": model,
            "include_image_base64": include_images,
            "table_format": kwargs.get("table_format", "html"),
            "extract_header": kwargs.get("extract_header", False),
            "extract_footer": kwargs.get("extract_footer", False)
        }

        # Agregar BBox annotations si esta habilitado
        if self.enable_bbox_annotations and self.bbox_format:
            if not include_images:
                include_images = True
                process_params["include_image_base64"] = True
                logger.info("BBox annotations requiere include_image_base64=True. Forzando activacion.")
            process_params["bbox_annotation_format"] = self.bbox_format
            logger.info("BBox annotations activado - extrayendo descripciones de imagenes")

        response = self.client.ocr.process(**process_params)

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

        # Obtener URL firmada con retry
        max_retries = 3
        signed_url = None
        for attempt in range(max_retries):
            try:
                signed_url = self.client.files.get_signed_url(
                    file_id=uploaded.id, expiry=24  # 24 horas en lugar de 1
                )
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    # Limpiar archivo preprocesado antes de lanzar excepción
                    if preprocessed_path and preprocessed_path != file_path:
                        self._cleanup_preprocessed_file(preprocessed_path)
                    raise
                logger.warning(f"Error obteniendo URL firmada (intento {attempt + 1}): {e}")
                time.sleep(2 ** attempt)  # Backoff exponencial

        # Limpiar archivo preprocesado inmediatamente después de subida exitosa
        if preprocessed_path and preprocessed_path != file_path:
            self._cleanup_preprocessed_file(preprocessed_path)

        return signed_url.url

    def _cleanup_preprocessed_file(self, preprocessed_path: Path):
        """
        Limpia archivo preprocesado temporal de forma segura.

        Args:
            preprocessed_path: Ruta del archivo preprocesado a eliminar
        """
        try:
            if preprocessed_path.exists():
                preprocessed_path.unlink()
                logger.debug(f"Archivo preprocesado eliminado: {preprocessed_path.name}")

                # Intentar limpiar directorio si está vacío
                temp_dir = preprocessed_path.parent
                if temp_dir.name == '.temp_preprocessed':
                    try:
                        # Solo eliminar si está vacío
                        if not any(temp_dir.iterdir()):
                            temp_dir.rmdir()
                            logger.debug(f"Directorio temporal eliminado: {temp_dir}")
                    except (OSError, PermissionError):
                        # Directorio no vacío o sin permisos, no es crítico
                        pass
        except Exception as e:
            # No es crítico si falla la limpieza, solo advertir
            logger.warning(f"No se pudo eliminar archivo preprocesado {preprocessed_path.name}: {e}")

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
                                  enrich_images: bool, optimize: bool, domain: str,
                                  extract_header: bool = False, extract_footer: bool = False) -> str:
        """
        Genera contenido markdown según opciones.
        
        Args:
            extract_header: Incluir headers de Mistral OCR 3
            extract_footer: Incluir footers de Mistral OCR 3
        """
        return self._process_pages_to_markdown(
            ocr_response, page_offset, optimize, domain,
            page_header_fn=lambda num: f"# Página {num}\n\n",
            image_processor_fn=lambda p, c: self._enrich_page_images(p, c, correct_mime=True) if enrich_images else c,
            include_headers_footers=False,  # Se controla individualmente con extract_header/extract_footer
            extract_header=extract_header,
            extract_footer=extract_footer,
            separator="\n\n"
        )
    
    def _extract_plain_text(self, markdown: str) -> str:
        """
        Extrae texto plano de markdown, preservando headers y footers de Mistral OCR 3.
        Limpia el formato markdown pero mantiene el contenido estructurado.
        """
        lines = []
        for line in markdown.splitlines():
            # Decodificar entidades HTML y limpiar tags
            line = html_lib.unescape(line)
            line = re.sub(r"</?[a-zA-Z][^>]*>", "", line)
            line = re.sub(r"<([^<>]{1,200})>", r"\1", line)
            # Omitir imágenes
            if line.strip().startswith('!['):
                continue
            
            # PRESERVAR headers y footers de Mistral OCR 3 (convertir formato pero mantener contenido)
            # **Encabezado:** texto -> Encabezado: texto
            if '**Encabezado:**' in line or '**Pie de página:**' in line:
                line = re.sub(r'\*\*Encabezado:\*\*', 'Encabezado:', line)
                line = re.sub(r'\*\*Pie de página:\*\*', 'Pie de página:', line)
            
            # Limpiar formato markdown
            line = re.sub(r'^#+\s*', '', line)  # Encabezados markdown (#, ##, etc.)
            line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)  # Negrita
            line = re.sub(r'\*([^*]+)\*', r'\1', line)  # Cursiva
            line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)  # Enlaces
            
            if line.strip():
                lines.append(line)
        
        return '\n'.join(lines)

    def _enrich_page_images(self, page, markdown_content: str,
                           correct_mime: bool = True) -> str:
        """
        Enriquece markdown con imágenes base64 incrustadas.

        Si BBox annotations está habilitado, también agrega descripciones
        automáticas debajo de cada imagen.

        Args:
            page: Página OCR con imágenes
            markdown_content: Contenido markdown a enriquecer
            correct_mime: Si True, usa MIME type correcto (jpg/png/tiff).
                         Si False, usa 'image/png' genérico (compatibilidad legacy)

        Returns:
            str: Markdown con imágenes incrustadas como data URIs y descripciones
        """
        image_data_map = {}
        image_annotations = {}  # {img_id: annotation_text}

        for img in page.images:
            img_id = getattr(img, 'id', None) or getattr(img, 'image_id', None)
            img_data, extension = self.image_processor.extract_image_data(img)
            if img_data and img_id:
                # Determinar MIME type
                if correct_mime:
                    mime_type = f"image/{extension}" if extension != 'jpg' else "image/jpeg"
                else:
                    mime_type = "image/png"  # Legacy: siempre PNG

                # Crear data URI
                data_uri = f"data:{mime_type};base64,{base64.b64encode(img_data).decode()}"
                image_data_map[img_id] = data_uri

            # Extraer anotacion BBox si existe
            if self.enable_bbox_annotations and img_id:
                annotation = self._extract_bbox_annotation_from_image(img)
                if annotation:
                    # Formatear descripcion para markdown
                    from bbox_annotations import format_image_description
                    desc = format_image_description(annotation, format_type='markdown')
                    if desc:
                        image_annotations[img_id] = desc

        # Reemplazar todas las referencias con data URIs y agregar descripciones
        for img_id, data_uri in image_data_map.items():
            old_ref = f"![{img_id}]({img_id})"
            new_ref = f"![{img_id}]({data_uri})"

            if img_id in image_annotations:
                new_ref += f"\n\n{image_annotations[img_id]}"

            if old_ref in markdown_content:
                markdown_content = markdown_content.replace(old_ref, new_ref)
            else:
                pattern = rf"!\[{re.escape(img_id)}\]\(([^)]+)\)"
                markdown_content = re.sub(pattern, new_ref, markdown_content)

        for img_id, desc in image_annotations.items():
            if img_id in image_data_map:
                continue
            pattern = rf"!\[{re.escape(img_id)}\]\(([^)]+)\)"
            replacement = f"![{img_id}](\\1)\n\n{desc}"
            markdown_content = re.sub(pattern, replacement, markdown_content)

        return markdown_content

    def _extract_bbox_annotation_from_image(self, img) -> Optional[Dict[str, str]]:
        """
        Extrae la anotación BBox de una imagen si existe.

        Args:
            img: Objeto de imagen de Mistral OCR

        Returns:
            Dict con 'image_type', 'short_description', 'summary' o None si no hay anotación
        """
        try:
            # Posibles ubicaciones de la anotacion segun SDK de Mistral
            annotation_data = None
            for attr in ('annotation', 'bbox_annotation', 'structured_annotation', 'annotations', 'bbox_annotations'):
                if hasattr(img, attr):
                    annotation_data = getattr(img, attr)
                    if annotation_data:
                        break

            if isinstance(annotation_data, (list, tuple)):
                selected = None
                for item in annotation_data:
                    if not item:
                        continue
                    if isinstance(item, dict) and item.get('short_description'):
                        selected = item
                        break
                    if hasattr(item, 'short_description') and getattr(item, 'short_description'):
                        selected = item
                        break
                if selected is None and annotation_data:
                    selected = annotation_data[0]
                annotation_data = selected

            if not annotation_data:
                return None

            # Convertir a diccionario estándar
            ann_dict = {}

            if isinstance(annotation_data, dict):
                ann_dict = annotation_data
            elif hasattr(annotation_data, 'model_dump'):
                # Pydantic v2
                ann_dict = annotation_data.model_dump()
            elif hasattr(annotation_data, 'dict'):
                # Pydantic v1
                ann_dict = annotation_data.dict()
            else:
                # Intentar extraer atributos directamente
                if hasattr(annotation_data, 'image_type'):
                    ann_dict['image_type'] = annotation_data.image_type
                if hasattr(annotation_data, 'short_description'):
                    ann_dict['short_description'] = annotation_data.short_description
                if hasattr(annotation_data, 'summary'):
                    ann_dict['summary'] = annotation_data.summary

            # Validar que tenga al menos short_description
            if ann_dict.get('short_description'):
                return {
                    'image_type': ann_dict.get('image_type', 'image'),
                    'short_description': ann_dict.get('short_description', ''),
                    'summary': ann_dict.get('summary', '')
                }

        except Exception as e:
            logger.debug(f"Error extrayendo bbox annotation: {e}")

        return None

    def _validate_batch_files(self, file_paths: List[str]) -> List[Path]:
        """Valida archivos para procesamiento batch."""
        valid_files = []

        for file_path in file_paths:
            path = Path(file_path)
            try:
                # Usar límite centralizado de batch
                self._validate_file(path, LIMITS.BATCH_MAX_SIZE_MB)
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
        
        if 'html' in formats:
            path = output_dir / f"{base_name}.html"
            outputs['html'] = self.save_as_html(
                response, path, page_offset, 
                title=base_name.replace('_', ' ').title()
            )
        
        if 'json' in formats:
            path = output_dir / f"{base_name}.json"
            outputs['json'] = self.save_json(response, path)
        
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
    
    def get_text(self, ocr_response, page_offset: int = 0, optimize: bool = False,
                 domain: str = "general") -> str:
        """
        Extrae todo el texto de la respuesta.

        Args:
            ocr_response: Respuesta OCR de Mistral
            page_offset: Offset para numeración de páginas (default: 0)
            optimize: Aplicar optimización de texto (default: False)
            domain: Dominio de optimización (default: "general")

        Returns:
            str: Texto completo formateado
        """
        optimizer = TextOptimizer(domain) if optimize else None
        texts = []

        for i, page in enumerate(ocr_response.pages):
            page_num = i + 1 + page_offset
            texts.append(f"=== PÁGINA {page_num} ===\n\n")

            text = self._extract_plain_text(page.markdown)
            if optimizer:
                text = optimizer.optimize_text(text)

            texts.append(text)
            if self.enable_bbox_annotations and hasattr(page, 'images') and page.images:
                descriptions = []
                for img in page.images:
                    annotation = self._extract_bbox_annotation_from_image(img)
                    if annotation:
                        from bbox_annotations import format_image_description
                        desc = format_image_description(annotation, format_type='text')
                        if desc:
                            descriptions.append(desc)
                if descriptions:
                    texts.append("\n")
                    texts.append("\n".join(descriptions))
            texts.append("\n\n")
        return "".join(texts)
    
    def get_combined_markdown(self, ocr_response) -> str:
        """Combina markdown de todas las páginas con imágenes."""
        return self._generate_markdown_content(
            ocr_response, 0, enrich_images=True, optimize=False, domain="general"
        )

    @staticmethod
    def cleanup_old_preprocessed_dirs(base_dir: Path = None, max_age_hours: int = 24) -> int:
        """
        Limpia directorios .temp_preprocessed más antiguos que max_age_hours.

        Esta es una función de mantenimiento que puede ejecutarse periódicamente
        para limpiar directorios temporales abandonados por errores o cancelaciones.

        Args:
            base_dir: Directorio base donde buscar (default: directorio actual)
            max_age_hours: Edad máxima en horas (default: 24 horas)

        Returns:
            int: Número de directorios eliminados
        """
        import shutil

        if base_dir is None:
            base_dir = Path.cwd()

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        cleaned_count = 0

        try:
            # Buscar recursivamente directorios .temp_preprocessed
            for temp_dir in base_dir.rglob('.temp_preprocessed'):
                if not temp_dir.is_dir():
                    continue

                try:
                    # Verificar edad del directorio
                    dir_age_seconds = current_time - temp_dir.stat().st_mtime
                    if dir_age_seconds > max_age_seconds:
                        # Eliminar directorio y todo su contenido
                        shutil.rmtree(temp_dir)
                        logger.info(f"Directorio temporal antiguo eliminado: {temp_dir} (edad: {dir_age_seconds/3600:.1f}h)")
                        cleaned_count += 1
                except Exception as e:
                    logger.warning(f"Error eliminando directorio temporal {temp_dir}: {e}")

        except Exception as e:
            logger.error(f"Error durante limpieza de directorios temporales: {e}")

        if cleaned_count > 0:
            logger.info(f"Limpieza completada: {cleaned_count} directorios temporales eliminados")

        return cleaned_count
