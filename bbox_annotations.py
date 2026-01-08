#!/usr/bin/env python3
"""
BBox Annotations Support - Soporte para anotaciones de imágenes con Mistral AI
--------------------------------------------------------------------------------
Implementa esquemas Pydantic para extraer descripciones automáticas de imágenes
usando BBox Annotations de Mistral AI.

Funcionalidades:
1. Generar descripciones automáticas de imágenes/figuras/gráficos
2. Incrustar descripciones como captions en HTML (figcaption)
3. Generar descripciones en texto plano para formatos estructurados (MD, TXT)

Versión: 2.0.0
Fecha: 2025-12-26
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging
import re

logger = logging.getLogger('bbox_annotations')


class Image(BaseModel):
    """
    Esquema Pydantic para anotación BBox de una imagen individual.

    Según documentación oficial de Mistral AI:
    https://docs.mistral.ai/capabilities/document_ai/annotations

    Este esquema se usa con bbox_annotation_format para que Mistral
    extraiga automáticamente descripciones de cada imagen detectada.

    Campos:
        image_type: Tipo de imagen (scatter plot, bar chart, diagram, photo, etc.)
        short_description: Descripción breve en inglés (1 oración)
        summary: Resumen detallado del contenido de la imagen
    """
    image_type: str = Field(
        ...,
        description="The type of the image (e.g., scatter plot, bar chart, diagram, photo, table, map, logo)."
    )
    short_description: str = Field(
        ...,
        description="A description in english describing the image in one sentence."
    )
    summary: str = Field(
        ...,
        description="Summarize the image content in detail, including key visual elements, data, and context."
    )


def create_bbox_annotation_format():
    """
    Crea el formato de anotación BBox para usar con Mistral AI SDK.

    Según documentación oficial:
    https://docs.mistral.ai/capabilities/document_ai/annotations

    Returns:
        ResponseFormat: Formato de respuesta compatible con Mistral SDK

    Example:
        >>> from bbox_annotations import create_bbox_annotation_format
        >>> bbox_format = create_bbox_annotation_format()
        >>> response = client.ocr.process(
        ...     model="mistral-ocr-latest",
        ...     document={"type": "document_url", "document_url": url},
        ...     bbox_annotation_format=bbox_format,  # ← Usar bbox_annotation_format
        ...     include_image_base64=True  # ← REQUERIDO para BBox annotations
        ... )
    """
    try:
        from mistralai.extra import response_format_from_pydantic_model

        # Crear formato desde el modelo Image
        bbox_format = response_format_from_pydantic_model(Image)
        logger.info("✓ BBox annotation format creado exitosamente")
        return bbox_format
    except ImportError as e:
        logger.error(f"mistralai SDK no tiene response_format_from_pydantic_model: {e}")
        logger.error("Actualice: pip install --upgrade mistralai")
        raise
    except Exception as e:
        logger.error(f"Error creando bbox annotation format: {e}")
        raise


def extract_image_annotations(ocr_response) -> Dict[int, Dict[str, Dict[str, str]]]:
    """
    Extrae anotaciones BBox de las imágenes en la respuesta OCR.

    Según la documentación oficial, cada imagen en page.images tiene
    su propia anotación BBox si se habilitó bbox_annotation_format.

    Args:
        ocr_response: Respuesta de Mistral OCR con BBox annotations

    Returns:
        Dict[int, Dict[str, Dict[str, str]]]: Estructura {page_idx: {image_id: annotation_dict}}
        Cada annotation_dict contiene: 'image_type', 'short_description', 'summary'

    Example:
        >>> annotations = extract_image_annotations(response)
        >>> annotations[0]['img_001']
        {
            'image_type': 'scatter plot',
            'short_description': 'Comparison of different models based on performance',
            'summary': 'The image consists of two scatter plots...'
        }
    """
    all_annotations = {}

    try:
        if not hasattr(ocr_response, 'pages'):
            logger.warning("OCR response no tiene atributo 'pages'")
            return all_annotations

        for page_idx, page in enumerate(ocr_response.pages):
            if not hasattr(page, 'images'):
                continue

            page_annotations = {}

            # Iterar sobre cada imagen de la página
            for img in page.images:
                # Obtener ID de la imagen
                img_id = getattr(img, 'id', None) or getattr(img, 'image_id', None)
                if not img_id:
                    continue

                # Intentar extraer annotation de diferentes atributos posibles
                annotation_data = None

                # Posibles ubicaciones de la anotación según SDK
                if hasattr(img, 'annotation'):
                    annotation_data = img.annotation
                elif hasattr(img, 'bbox_annotation'):
                    annotation_data = img.bbox_annotation
                elif hasattr(img, 'structured_annotation'):
                    annotation_data = img.structured_annotation

                if annotation_data:
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
                        page_annotations[img_id] = {
                            'image_type': ann_dict.get('image_type', 'image'),
                            'short_description': ann_dict.get('short_description', ''),
                            'summary': ann_dict.get('summary', '')
                        }

            # Solo agregar si hay anotaciones en esta página
            if page_annotations:
                all_annotations[page_idx] = page_annotations
                logger.debug(f"Página {page_idx}: {len(page_annotations)} imágenes anotadas")

    except Exception as e:
        logger.error(f"Error extrayendo image annotations: {e}")

    return all_annotations


def format_image_description(annotation: Dict[str, str], format_type: str = 'text', use_summary: bool = False) -> str:
    """
    Formatea una anotación de imagen para diferentes salidas.

    Args:
        annotation: Diccionario con 'image_type', 'short_description', 'summary'
        format_type: 'text', 'html', o 'markdown'
        use_summary: Si True, usa 'summary' en lugar de 'short_description'

    Returns:
        str: Descripción formateada

    Example:
        >>> ann = {
        ...     'image_type': 'scatter plot',
        ...     'short_description': 'Comparison of models',
        ...     'summary': 'Detailed scatter plot showing...'
        ... }
        >>> format_image_description(ann, 'text')
        'Imagen (scatter plot): Comparison of models'
        >>> format_image_description(ann, 'html')
        '<figcaption><em>scatter plot</em>: Comparison of models</figcaption>'
        >>> format_image_description(ann, 'text', use_summary=True)
        'Imagen (scatter plot): Detailed scatter plot showing...'
    """
    if not annotation:
        return ""

    image_type = annotation.get('image_type', 'image')

    # Elegir qué descripción usar
    if use_summary:
        description = annotation.get('summary', '').strip()
        # Fallback a short_description si summary está vacío
        if not description:
            description = annotation.get('short_description', '').strip()
    else:
        description = annotation.get('short_description', '').strip()

    if not description:
        return ""

    if format_type == 'html':
        return f'<figcaption><em>{image_type}</em>: {description}</figcaption>'
    elif format_type == 'markdown':
        return f'*{image_type}*: {description}'
    else:  # text
        return f'Imagen ({image_type}): {description}'


def get_annotation_summary(image_annotations: Dict[int, Dict[str, Dict[str, str]]]) -> str:
    """
    Genera un resumen de las anotaciones extraídas.

    Args:
        image_annotations: Diccionario {page_idx: {image_id: annotation}}

    Returns:
        str: Resumen formateado

    Example:
        >>> summary = get_annotation_summary(annotations)
        >>> print(summary)
        BBox Annotations Summary:
        - Total pages with images: 3
        - Total images annotated: 7
        - Image types: scatter plot (3), bar chart (2), photo (2)
    """
    if not image_annotations:
        return "No BBox annotations found"

    total_pages = len(image_annotations)
    total_images = sum(len(page_anns) for page_anns in image_annotations.values())

    # Contar tipos de imágenes
    type_counts = {}
    for page_anns in image_annotations.values():
        for img_id, ann in page_anns.items():
            img_type = ann.get('image_type', 'unknown')
            type_counts[img_type] = type_counts.get(img_type, 0) + 1

    type_summary = ', '.join(f"{t} ({c})" for t, c in sorted(type_counts.items()))

    summary = f"""BBox Annotations Summary:
- Total pages with images: {total_pages}
- Total images annotated: {total_images}
- Image types: {type_summary}"""

    return summary


# ============================================================================
# ESQUEMAS ESPECIALIZADOS PARA DIFERENTES TIPOS DE DOCUMENTOS
# ============================================================================

class ImageSpanish(BaseModel):
    """
    Esquema para anotación de imágenes con descripciones en español.
    Ideal para documentos técnicos en español.
    """
    tipo_imagen: str = Field(
        ...,
        description="Tipo de imagen: fotografía, diagrama, gráfico de barras, gráfico de líneas, tabla, esquema, mapa, plano, firma, sello, logo, ecuación, figura técnica, otro"
    )
    descripcion_breve: str = Field(
        ...,
        description="Descripción breve de la imagen en español (1-2 oraciones)"
    )
    descripcion_detallada: str = Field(
        ...,
        description="Descripción detallada del contenido, datos relevantes y contexto de la imagen en español (2-4 oraciones)"
    )


class TechnicalDiagram(BaseModel):
    """
    Esquema especializado para diagramas técnicos de ingeniería.
    Incluye campos para escalas, dimensiones y detalles técnicos.
    """
    diagram_type: str = Field(
        ...,
        description="Tipo de diagrama: plano arquitectónico, corte transversal, perfil geológico, diagrama estructural, diagrama hidráulico, diagrama eléctrico, mapa topográfico, esquema de proceso, otro"
    )
    title: str = Field(
        default="",
        description="Título del diagrama si es visible"
    )
    scale: str = Field(
        default="",
        description="Escala del diagrama si es visible (ej: 1:100, 1:500)"
    )
    main_elements: str = Field(
        ...,
        description="Descripción de los elementos principales mostrados en el diagrama"
    )
    dimensions: str = Field(
        default="",
        description="Dimensiones principales visibles (ancho, alto, profundidad)"
    )
    technical_notes: str = Field(
        default="",
        description="Notas técnicas, materiales, especificaciones visibles"
    )
    summary: str = Field(
        ...,
        description="Resumen completo de lo que muestra el diagrama y su propósito"
    )


class ChartGraph(BaseModel):
    """
    Esquema especializado para gráficos y visualizaciones de datos.
    """
    chart_type: str = Field(
        ...,
        description="Tipo de gráfico: barras, líneas, pastel, dispersión, histograma, área, radar, caja y bigotes, otro"
    )
    title: str = Field(
        default="",
        description="Título del gráfico si es visible"
    )
    x_axis_label: str = Field(
        default="",
        description="Etiqueta del eje X"
    )
    y_axis_label: str = Field(
        default="",
        description="Etiqueta del eje Y"
    )
    data_description: str = Field(
        ...,
        description="Descripción de los datos mostrados en el gráfico"
    )
    trends_insights: str = Field(
        ...,
        description="Tendencias, patrones o conclusiones que se pueden extraer del gráfico"
    )


# ============================================================================
# CONFIGURACIÓN DE ANOTACIONES
# ============================================================================

@dataclass
class AnnotationConfig:
    """Configuración para el procesamiento de anotaciones de imágenes."""

    # Modelo a usar: 'general', 'spanish', 'technical', 'chart'
    model_type: str = "spanish"

    # Incluir descripciones en output HTML
    include_html_captions: bool = True

    # Incluir descripciones en output de texto/markdown
    include_text_descriptions: bool = True

    # Usar descripción detallada (True) o breve (False)
    use_detailed_description: bool = True

    # Formato de caption en texto plano
    text_caption_format: str = "italic"  # "italic", "plain", "blockquote"

    # Prefijo para descripciones de imagen en texto
    text_prefix: str = ""
    text_suffix: str = ""

    def get_model_class(self) -> type:
        """Retorna la clase del modelo según el tipo configurado."""
        models = {
            "general": Image,
            "spanish": ImageSpanish,
            "technical": TechnicalDiagram,
            "chart": ChartGraph
        }
        return models.get(self.model_type, ImageSpanish)


# ============================================================================
# PROCESADOR DE ANOTACIONES PARA HTML Y TEXTO
# ============================================================================

class ImageAnnotationProcessor:
    """
    Procesa anotaciones de imágenes para incrustarlas en HTML y texto.

    Esta clase toma las anotaciones extraídas por Mistral y las formatea
    para diferentes outputs sin modificar el cliente OCR principal.
    """

    def __init__(self, config: Optional[AnnotationConfig] = None):
        """
        Inicializa el procesador.

        Args:
            config: Configuración de anotaciones. Si es None, usa valores por defecto.
        """
        self.config = config or AnnotationConfig()

    def create_bbox_format(self) -> Any:
        """
        Crea el formato de anotación BBox para la API de Mistral.

        Returns:
            Formato compatible con bbox_annotation_format
        """
        try:
            from mistralai.extra import response_format_from_pydantic_model
            model = self.config.get_model_class()
            return response_format_from_pydantic_model(model)
        except ImportError:
            logger.error("mistralai.extra no disponible. Usando schema manual.")
            return self._create_manual_schema()

    def _create_manual_schema(self) -> Dict[str, Any]:
        """Crea schema JSON manualmente para la API."""
        model = self.config.get_model_class()
        return {
            "type": "json_schema",
            "json_schema": model.model_json_schema()
        }

    def extract_annotations_from_response(self, ocr_response) -> Dict[int, List[Dict[str, Any]]]:
        """
        Extrae todas las anotaciones de una respuesta OCR.

        Args:
            ocr_response: Respuesta de Mistral OCR

        Returns:
            Dict[página_idx, List[anotaciones]]
        """
        result = {}

        if not hasattr(ocr_response, 'pages'):
            return result

        for page_idx, page in enumerate(ocr_response.pages):
            page_annotations = []

            if hasattr(page, 'images') and page.images:
                for img_idx, img in enumerate(page.images):
                    annotation = self._extract_single_annotation(img, img_idx)
                    if annotation:
                        page_annotations.append(annotation)

            if page_annotations:
                result[page_idx] = page_annotations

        return result

    def _extract_single_annotation(self, image, index: int) -> Optional[Dict[str, Any]]:
        """Extrae la anotación de una imagen individual."""
        ann_data = None

        # Buscar anotación en diferentes atributos
        for attr in ['annotation', 'bbox_annotation', 'structured_annotation']:
            if hasattr(image, attr):
                ann_data = getattr(image, attr)
                if ann_data:
                    break

        if not ann_data:
            return None

        # Convertir a diccionario
        if isinstance(ann_data, dict):
            ann_dict = ann_data
        elif hasattr(ann_data, 'model_dump'):
            ann_dict = ann_data.model_dump()
        elif hasattr(ann_data, 'dict'):
            ann_dict = ann_data.dict()
        else:
            ann_dict = {}
            for attr in dir(ann_data):
                if not attr.startswith('_'):
                    try:
                        ann_dict[attr] = getattr(ann_data, attr)
                    except:
                        pass

        # Agregar metadatos
        ann_dict['_index'] = index
        ann_dict['_image_id'] = getattr(image, 'id', f'img_{index}')

        return ann_dict

    def format_as_html_caption(self, annotation: Dict[str, Any]) -> str:
        """
        Formatea una anotación como caption HTML (<figcaption>).

        Args:
            annotation: Diccionario con la anotación

        Returns:
            HTML string con el caption
        """
        if not annotation:
            return ""

        # Detectar tipo de modelo y extraer campos
        img_type = self._get_image_type(annotation)
        description = self._get_description(annotation)

        if not description:
            return ""

        # Construir HTML
        parts = []

        if img_type:
            parts.append(f'<strong class="img-type">{img_type}</strong>')

        if description:
            parts.append(f': <span class="img-desc">{description}</span>')

        # Agregar detalles adicionales si existen
        extra = self._get_extra_details(annotation)
        if extra:
            parts.append(f'<br><small class="img-extra">{extra}</small>')

        return f'<figcaption class="bbox-caption">{"".join(parts)}</figcaption>'

    def format_as_text_description(self, annotation: Dict[str, Any]) -> str:
        """
        Formatea una anotación como descripción de texto plano.

        Args:
            annotation: Diccionario con la anotación

        Returns:
            String con la descripción formateada
        """
        if not annotation:
            return ""

        img_type = self._get_image_type(annotation)
        description = self._get_description(annotation)

        if not description:
            return ""

        # Construir texto según formato configurado
        content = f"{img_type}: {description}" if img_type else description

        if self.config.text_caption_format == "italic":
            return f"*[{content}]*"
        elif self.config.text_caption_format == "blockquote":
            return f"> {content}"
        else:  # plain
            return f"[{content}]"

    def _get_image_type(self, annotation: Dict[str, Any]) -> str:
        """Extrae el tipo de imagen de la anotación."""
        for key in ['tipo_imagen', 'image_type', 'diagram_type', 'chart_type']:
            if key in annotation and annotation[key]:
                return str(annotation[key])
        return "Imagen"

    def _get_description(self, annotation: Dict[str, Any]) -> str:
        """Extrae la descripción de la anotación."""
        if self.config.use_detailed_description:
            # Priorizar descripción detallada
            for key in ['descripcion_detallada', 'summary', 'detailed_description',
                       'data_description', 'main_elements']:
                if key in annotation and annotation[key]:
                    return str(annotation[key])

        # Fallback a descripción breve
        for key in ['descripcion_breve', 'short_description', 'title']:
            if key in annotation and annotation[key]:
                return str(annotation[key])

        return ""

    def _get_extra_details(self, annotation: Dict[str, Any]) -> str:
        """Extrae detalles adicionales de la anotación."""
        extras = []

        # Campos adicionales según tipo de diagrama
        for key in ['scale', 'dimensions', 'technical_notes', 'trends_insights',
                   'x_axis_label', 'y_axis_label']:
            if key in annotation and annotation[key]:
                extras.append(f"{key.replace('_', ' ').title()}: {annotation[key]}")

        return " | ".join(extras) if extras else ""

    def enrich_markdown_with_captions(self, markdown: str, page_annotations: List[Dict[str, Any]]) -> str:
        """
        Enriquece markdown con descripciones de imágenes.

        Busca patrones de imagen ![alt](src) y agrega descripciones debajo.

        Args:
            markdown: Contenido markdown original
            page_annotations: Lista de anotaciones de la página

        Returns:
            Markdown enriquecido con descripciones
        """
        if not self.config.include_text_descriptions or not page_annotations:
            return markdown

        # Patrón para imágenes markdown
        img_pattern = r'(!\[[^\]]*\]\([^)]+\))'

        annotation_iter = iter(page_annotations)

        def add_caption(match):
            full_match = match.group(1)
            try:
                ann = next(annotation_iter)
                caption = self.format_as_text_description(ann)
                if caption:
                    return f"{full_match}\n\n{caption}\n"
            except StopIteration:
                pass
            return full_match

        return re.sub(img_pattern, add_caption, markdown)

    def enrich_html_with_captions(self, html_content: str, page_annotations: List[Dict[str, Any]]) -> str:
        """
        Enriquece HTML con figcaptions para imágenes.

        Busca elementos <figure> o <img> y agrega <figcaption>.

        Args:
            html_content: Contenido HTML original
            page_annotations: Lista de anotaciones de la página

        Returns:
            HTML enriquecido con captions
        """
        if not self.config.include_html_captions or not page_annotations:
            return html_content

        # Patrón para figuras o imágenes
        # Buscar <figure>...<img...>...</figure> o <img...> standalone
        figure_pattern = r'(<figure[^>]*>.*?<img[^>]*>)(.*?)(</figure>)'
        img_pattern = r'(<img[^>]*>)(?!</figure>)'

        annotation_iter = iter(page_annotations)

        def add_figure_caption(match):
            figure_start = match.group(1)
            middle = match.group(2)
            figure_end = match.group(3)
            try:
                ann = next(annotation_iter)
                caption = self.format_as_html_caption(ann)
                if caption:
                    return f"{figure_start}{middle}{caption}{figure_end}"
            except StopIteration:
                pass
            return match.group(0)

        def add_img_caption(match):
            img_tag = match.group(1)
            try:
                ann = next(annotation_iter)
                caption = self.format_as_html_caption(ann)
                if caption:
                    return f'<figure class="ocr-image">{img_tag}{caption}</figure>'
            except StopIteration:
                pass
            return img_tag

        # Primero procesar figures existentes
        result = re.sub(figure_pattern, add_figure_caption, html_content, flags=re.DOTALL)

        # Luego procesar imgs standalone (resetear iterador)
        annotation_iter = iter(page_annotations)
        result = re.sub(img_pattern, add_img_caption, result)

        return result


# ============================================================================
# FUNCIONES DE CONVENIENCIA
# ============================================================================

def create_spanish_annotation_format():
    """
    Crea formato de anotación para documentos en español.

    Returns:
        Formato compatible con bbox_annotation_format de Mistral
    """
    processor = ImageAnnotationProcessor(AnnotationConfig(model_type="spanish"))
    return processor.create_bbox_format()


def create_technical_annotation_format():
    """
    Crea formato de anotación para diagramas técnicos.

    Returns:
        Formato compatible con bbox_annotation_format de Mistral
    """
    processor = ImageAnnotationProcessor(AnnotationConfig(model_type="technical"))
    return processor.create_bbox_format()


def create_chart_annotation_format():
    """
    Crea formato de anotación para gráficos y visualizaciones.

    Returns:
        Formato compatible con bbox_annotation_format de Mistral
    """
    processor = ImageAnnotationProcessor(AnnotationConfig(model_type="chart"))
    return processor.create_bbox_format()


def process_ocr_with_annotations(ocr_response, config: Optional[AnnotationConfig] = None) -> Dict[str, Any]:
    """
    Procesa una respuesta OCR y extrae anotaciones formateadas.

    Args:
        ocr_response: Respuesta de Mistral OCR con bbox_annotation_format
        config: Configuración opcional

    Returns:
        Dict con:
            - 'annotations': Dict[página, List[anotaciones]]
            - 'html_captions': Dict[página, List[html_strings]]
            - 'text_captions': Dict[página, List[text_strings]]
            - 'summary': Resumen estadístico
    """
    processor = ImageAnnotationProcessor(config)
    annotations = processor.extract_annotations_from_response(ocr_response)

    result = {
        'annotations': annotations,
        'html_captions': {},
        'text_captions': {},
        'summary': {
            'total_pages': len(annotations),
            'total_images': sum(len(anns) for anns in annotations.values()),
            'types': {}
        }
    }

    for page_idx, page_anns in annotations.items():
        result['html_captions'][page_idx] = [
            processor.format_as_html_caption(ann) for ann in page_anns
        ]
        result['text_captions'][page_idx] = [
            processor.format_as_text_description(ann) for ann in page_anns
        ]

        # Contar tipos
        for ann in page_anns:
            img_type = processor._get_image_type(ann)
            result['summary']['types'][img_type] = result['summary']['types'].get(img_type, 0) + 1

    return result


# ============================================================================
# VALIDACIÓN Y EJEMPLO
# ============================================================================

if __name__ == "__main__":
    print("=== BBOX ANNOTATIONS MODULE v2.0 ===")
    print()

    print("Esquemas disponibles:")
    print(f"  - Image (general, inglés)")
    print(f"  - ImageSpanish (general, español)")
    print(f"  - TechnicalDiagram (diagramas técnicos)")
    print(f"  - ChartGraph (gráficos y visualizaciones)")
    print()

    # Probar procesador
    config = AnnotationConfig(model_type="spanish")
    processor = ImageAnnotationProcessor(config)

    # Ejemplo de anotación
    sample = {
        "tipo_imagen": "Gráfico de barras",
        "descripcion_breve": "Comparación de costos anuales",
        "descripcion_detallada": "El gráfico muestra la evolución de costos de construcción desde 2020 hasta 2024, con un incremento notable del 35% en materiales durante 2022."
    }

    print("Ejemplo de procesamiento:")
    print(f"  Input: {sample}")
    print()
    print(f"  HTML Caption:")
    print(f"    {processor.format_as_html_caption(sample)}")
    print()
    print(f"  Text Caption:")
    print(f"    {processor.format_as_text_description(sample)}")
    print()

    try:
        bbox_format = create_spanish_annotation_format()
        print("[OK] Formato espanol creado exitosamente")
    except Exception as e:
        print(f"[ERROR] {e}")
