# PLAN DE REFACTORIZACIÓN - mistral_ocr_client_optimized.py

**Fecha:** 2025-12-26
**Archivo:** mistral_ocr_client_optimized.py (1,398 líneas)
**Objetivo:** Eliminar duplicación funcional interna
**Estado:** 📋 En análisis

---

## RESUMEN EJECUTIVO

**Problemas identificados:** 3 áreas principales de duplicación funcional

| Problema | Líneas Afectadas | Duplicación Estimada | Impacto |
|----------|------------------|---------------------|---------|
| Generación markdown/HTML duplicada | 302-355, 1159-1187 | ~60 líneas | Alto |
| Formato "=== PÁGINA ===" duplicado | 201, 1389 | ~5 líneas | Bajo |
| Enriquecimiento de imágenes duplicado | 1174-1175, 308-342 | ~15 líneas | Medio |

**Reducción estimada:** ~80 líneas + mejor mantenibilidad

---

## ANÁLISIS DETALLADO

### 1. DUPLICACIÓN: Generación de Markdown vs HTML

#### Problema Identificado

Dos métodos comparten el **mismo flujo de procesamiento de páginas** con diferencias mínimas:

**Método 1:** `_generate_markdown_content()` (líneas 1159-1187)
```python
def _generate_markdown_content(self, ocr_response, page_offset: int,
                              enrich_images: bool, optimize: bool, domain: str) -> str:
    optimizer = MarkdownOptimizer(domain) if optimize else None
    content_parts = []

    for i, page in enumerate(ocr_response.pages):
        page_num = i + 1 + page_offset
        content_parts.append(f"# Página {page_num}\n\n")

        # Incluir encabezado si existe (Mistral OCR 3)
        if hasattr(page, 'header') and page.header:
            content_parts.append(f"**Encabezado:** {page.header}\n\n")

        page_content = page.markdown

        # Enriquecer imágenes si se solicita
        if enrich_images:
            page_content = self._enrich_page_images(page, page_content)

        # Optimizar si se solicita
        if optimizer:
            page_content = optimizer.optimize_markdown(page_content)

        content_parts.append(page_content + "\n\n")

        # Incluir pie de página si existe (Mistral OCR 3)
        if hasattr(page, 'footer') and page.footer:
            content_parts.append(f"**Pie de página:** {page.footer}\n\n")

    return "\n".join(content_parts)
```

**Método 2:** `_generate_html_content_with_images()` (líneas 302-355)
```python
def _generate_html_content_with_images(self, ocr_response, page_offset: int,
                                       optimize: bool, domain: str) -> str:
    optimizer = MarkdownOptimizer(domain) if optimize else None
    markdown_parts = []

    for i, page in enumerate(ocr_response.pages):
        page_num = i + 1 + page_offset
        markdown_parts.append(f'\n\n---\n\n## 📄 Página {page_num}\n\n')

        # Obtener markdown de la página
        page_content = page.markdown

        # Optimizar si se solicita
        if optimizer:
            page_content = optimizer.optimize_markdown(page_content)

        # Crear diccionario de imágenes con sus data URIs
        image_data_map = {}
        for img in page.images:
            img_data, extension = self.image_processor.extract_image_data(img)
            if img_data and hasattr(img, 'id'):
                # Crear data URI completo
                mime_type = f"image/{extension}" if extension != 'jpg' else "image/jpeg"
                data_uri = f"data:{mime_type};base64,{base64.b64encode(img_data).decode()}"
                image_data_map[img.id] = data_uri

        # Reemplazar referencias de imágenes con data URIs
        for img_id, data_uri in image_data_map.items():
            page_content = page_content.replace(
                f"![{img_id}]({img_id})",
                f"![{img_id}]({data_uri})"
            )

        markdown_parts.append(page_content)

    # Unir todo el contenido markdown
    full_markdown = '\n'.join(markdown_parts)

    # Escapar caracteres especiales para JavaScript
    escaped_markdown = (full_markdown
        .replace('\\', '\\\\')
        .replace('`', '\\`')
        .replace('$', '\\$')
        .replace('</script>', '<\\/script>')
    )

    return escaped_markdown
```

#### Código Duplicado (Flujo Común)

Ambos métodos:
1. ✅ Crean un optimizador si `optimize=True`
2. ✅ Iteran sobre `ocr_response.pages`
3. ✅ Calculan `page_num = i + 1 + page_offset`
4. ✅ Obtienen `page.markdown`
5. ✅ Aplican optimización con `optimizer.optimize_markdown()`
6. ✅ Manejan imágenes (de forma diferente)
7. ✅ Agregan contenido a una lista
8. ✅ Retornan string final

#### Diferencias Clave

| Aspecto | _generate_markdown_content | _generate_html_content_with_images |
|---------|---------------------------|-----------------------------------|
| **Header de página** | `# Página {page_num}` | `## 📄 Página {page_num}` |
| **Encabezados/Footers** | Incluye si existen | No incluye |
| **Imágenes** | Usa `_enrich_page_images()` (PNG genérico) | Crea data URIs con MIME type correcto |
| **Post-procesamiento** | Ninguno | Escapado para JavaScript |
| **Separadores** | `\n\n` | `---` entre páginas |

#### Solución Propuesta

**Crear método base unificado:**

```python
def _process_pages_to_markdown(self, ocr_response, page_offset: int,
                               optimize: bool, domain: str,
                               page_header_fn=None,
                               image_processor_fn=None,
                               include_headers_footers: bool = True,
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
    optimizer = MarkdownOptimizer(domain) if optimize else None
    content_parts = []

    for i, page in enumerate(ocr_response.pages):
        page_num = i + 1 + page_offset

        # Header de página (customizable)
        if page_header_fn:
            content_parts.append(page_header_fn(page_num))

        # Encabezado de documento (Mistral OCR 3)
        if include_headers_footers and hasattr(page, 'header') and page.header:
            content_parts.append(f"**Encabezado:** {page.header}\n\n")

        # Obtener contenido markdown
        page_content = page.markdown

        # Procesar imágenes (customizable)
        if image_processor_fn:
            page_content = image_processor_fn(page, page_content)

        # Optimizar markdown
        if optimizer:
            page_content = optimizer.optimize_markdown(page_content)

        content_parts.append(page_content)

        # Pie de página de documento (Mistral OCR 3)
        if include_headers_footers and hasattr(page, 'footer') and page.footer:
            content_parts.append(f"\n\n**Pie de página:** {page.footer}")

        # Separador entre páginas
        if i < len(ocr_response.pages) - 1:
            content_parts.append(separator)

    return "".join(content_parts)
```

**Refactorizar métodos existentes:**

```python
def _generate_markdown_content(self, ocr_response, page_offset: int,
                              enrich_images: bool, optimize: bool, domain: str) -> str:
    """Genera contenido markdown según opciones."""
    return self._process_pages_to_markdown(
        ocr_response, page_offset, optimize, domain,
        page_header_fn=lambda num: f"# Página {num}\n\n",
        image_processor_fn=self._enrich_page_images if enrich_images else None,
        include_headers_footers=True,
        separator="\n\n"
    )

def _generate_html_content_with_images(self, ocr_response, page_offset: int,
                                       optimize: bool, domain: str) -> str:
    """Genera contenido markdown con imágenes para HTML."""
    # Procesador de imágenes específico para HTML
    def html_image_processor(page, content):
        image_data_map = {}
        for img in page.images:
            img_data, extension = self.image_processor.extract_image_data(img)
            if img_data and hasattr(img, 'id'):
                mime_type = f"image/{extension}" if extension != 'jpg' else "image/jpeg"
                data_uri = f"data:{mime_type};base64,{base64.b64encode(img_data).decode()}"
                image_data_map[img.id] = data_uri

        for img_id, data_uri in image_data_map.items():
            content = content.replace(f"![{img_id}]({img_id})", f"![{img_id}]({data_uri})")

        return content

    markdown = self._process_pages_to_markdown(
        ocr_response, page_offset, optimize, domain,
        page_header_fn=lambda num: f"\n\n---\n\n## 📄 Página {num}\n\n",
        image_processor_fn=html_image_processor,
        include_headers_footers=False,
        separator=""
    )

    # Escapar para JavaScript
    return (markdown
        .replace('\\', '\\\\')
        .replace('`', '\\`')
        .replace('$', '\\$')
        .replace('</script>', '<\\/script>')
    )
```

**Impacto:**
- ✅ Elimina ~50 líneas de código duplicado
- ✅ Un solo lugar para mantener el flujo de procesamiento
- ✅ Más fácil agregar nuevos formatos (PDF, DOCX, etc.)
- ✅ Funciones lambda hacen claro qué es diferente en cada caso

---

### 2. DUPLICACIÓN: Formato "=== PÁGINA ==="

#### Problema Identificado

El formato de header de página se repite en 2 lugares:

**Lugar 1:** `save_text()` (línea 201)
```python
def save_text(self, ocr_response, output_path=None, page_offset=0,
              optimize=False, domain="general"):
    # ...
    for i, page in enumerate(ocr_response.pages):
        page_num = i + 1 + page_offset
        f.write(f"=== PÁGINA {page_num} ===\n\n")  # ← DUPLICADO
        # ...
```

**Lugar 2:** `get_text()` (línea 1389)
```python
def get_text(self, ocr_response) -> str:
    texts = []
    for i, page in enumerate(ocr_response.pages):
        texts.append(f"=== PÁGINA {i+1} ===\n")  # ← DUPLICADO (sin page_offset)
        texts.append(self._extract_plain_text(page.markdown))
        texts.append("\n\n")
    return "".join(texts)
```

#### Diferencias

1. `save_text()` usa `page_offset`, `get_text()` no
2. `save_text()` aplica `TextOptimizer`, `get_text()` no
3. `save_text()` escribe a archivo, `get_text()` retorna string

#### Solución Propuesta

**Refactorizar `get_text()` para usar lógica de `save_text()`:**

```python
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
        texts.append("\n\n")

    return "".join(texts)
```

**Refactorizar `save_text()` para usar `get_text()`:**

```python
def save_text(self, ocr_response, output_path=None, page_offset=0,
              optimize=False, domain="general"):
    """Guarda solo texto extraído."""
    output_path = self._prepare_output_path(output_path, "txt")

    # Usar get_text() para generar contenido
    text_content = self.get_text(ocr_response, page_offset, optimize, domain)

    with open(output_path, "wt", encoding="utf-8") as f:
        f.write(text_content)

    logger.info(f"Texto guardado: {output_path}")
    return output_path
```

**Impacto:**
- ✅ Elimina duplicación del formato "=== PÁGINA ==="
- ✅ `get_text()` ahora soporta optimización y offset (más flexible)
- ✅ `save_text()` simplificado a 9 líneas
- ✅ Un solo lugar para mantener lógica de extracción de texto

---

### 3. DUPLICACIÓN: Enriquecimiento de Imágenes

#### Problema Identificado

El enriquecimiento de imágenes se hace de **2 formas diferentes**:

**Forma 1:** `_enrich_page_images()` (líneas 1207-1217) - **SIEMPRE PNG**
```python
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
```

**Forma 2:** Dentro de `_generate_html_content_with_images()` (líneas 324-340) - **MIME CORRECTO**
```python
# Crear diccionario de imágenes con sus data URIs
image_data_map = {}
for img in page.images:
    img_data, extension = self.image_processor.extract_image_data(img)
    if img_data and hasattr(img, 'id'):
        # Crear data URI completo
        mime_type = f"image/{extension}" if extension != 'jpg' else "image/jpeg"
        data_uri = f"data:{mime_type};base64,{base64.b64encode(img_data).decode()}"
        image_data_map[img.id] = data_uri

# Reemplazar referencias de imágenes con data URIs
for img_id, data_uri in image_data_map.items():
    page_content = page_content.replace(
        f"![{img_id}]({img_id})",
        f"![{img_id}]({data_uri})"
    )
```

#### Problemas

1. **Bug en `_enrich_page_images()`:** Siempre usa `image/png` aunque la imagen sea JPG, TIFF, etc.
2. **Duplicación de lógica:** Mismo flujo (iterar imágenes → extraer datos → crear data URI → reemplazar)
3. **Inconsistencia:** HTML usa MIME correcto, Markdown usa PNG fijo

#### Solución Propuesta

**Corregir y unificar en un solo método:**

```python
def _enrich_page_images(self, page, markdown_content: str,
                       correct_mime: bool = True) -> str:
    """
    Enriquece markdown con imágenes base64 incrustadas.

    Args:
        page: Página OCR con imágenes
        markdown_content: Contenido markdown a enriquecer
        correct_mime: Si True, usa MIME type correcto (jpg/png/tiff).
                     Si False, usa 'image/png' genérico (compatibilidad legacy)

    Returns:
        str: Markdown con imágenes incrustadas como data URIs
    """
    image_data_map = {}

    for img in page.images:
        img_data, extension = self.image_processor.extract_image_data(img)
        if img_data and hasattr(img, 'id'):
            # Determinar MIME type
            if correct_mime:
                mime_type = f"image/{extension}" if extension != 'jpg' else "image/jpeg"
            else:
                mime_type = "image/png"  # Legacy: siempre PNG

            # Crear data URI
            data_uri = f"data:{mime_type};base64,{base64.b64encode(img_data).decode()}"
            image_data_map[img.id] = data_uri

    # Reemplazar todas las referencias
    for img_id, data_uri in image_data_map.items():
        markdown_content = markdown_content.replace(
            f"![{img_id}]({img_id})",
            f"![{img_id}]({data_uri})"
        )

    return markdown_content
```

**Actualizar llamadas:**

```python
# En _generate_markdown_content:
if enrich_images:
    page_content = self._enrich_page_images(page, page_content, correct_mime=True)

# En _generate_html_content_with_images (ahora puede simplificar):
page_content = self._enrich_page_images(page, page_content, correct_mime=True)
```

**Impacto:**
- ✅ **Bugfix:** Ahora usa MIME type correcto (JPG, PNG, TIFF)
- ✅ Elimina ~20 líneas de código duplicado en `_generate_html_content_with_images()`
- ✅ Un solo lugar para mantener lógica de enriquecimiento
- ✅ Flag `correct_mime` permite backward compatibility si es necesario

---

## RESUMEN DE IMPACTO

### Antes de Refactorización

| Métrica | Valor |
|---------|-------|
| **Líneas totales** | 1,398 |
| **Métodos de generación markdown** | 2 independientes |
| **Métodos de extracción texto** | 2 con duplicación |
| **Métodos de imágenes** | 2 con lógica duplicada |
| **Bug MIME type** | 1 (PNG fijo en _enrich_page_images) |

### Después de Refactorización

| Métrica | Valor | Cambio |
|---------|-------|--------|
| **Líneas totales** | ~1,318 | **-80 líneas** |
| **Métodos de generación** | 1 base + 2 wrappers | +1 método base |
| **Métodos de extracción** | 1 unificado | -duplicación |
| **Métodos de imágenes** | 1 unificado | -duplicación |
| **Bugs corregidos** | 0 | **-1 bug** |

---

## BENEFICIOS ESPERADOS

### ✅ Cuantitativos
- **-80 líneas** de código duplicado (~5.7%)
- **-1 bug** (MIME type incorrecto)
- **+3 parámetros** adicionales en métodos públicos (más flexibilidad)
- **1 método base** nuevo (`_process_pages_to_markdown`)

### ✅ Cualitativos
- **Mantenibilidad:** Un solo lugar para cambiar lógica de procesamiento
- **Extensibilidad:** Fácil agregar nuevos formatos de salida
- **Consistencia:** Mismo comportamiento en markdown/HTML/texto
- **Corrección:** MIME types correctos para todas las imágenes
- **Flexibilidad:** `get_text()` ahora soporta optimización

---

## PLAN DE EJECUCIÓN

### Fase 1: Unificar Procesamiento de Páginas (Prioridad ALTA)

1. ✅ Crear `_process_pages_to_markdown()` (método base)
2. ✅ Refactorizar `_generate_markdown_content()` (usar método base)
3. ✅ Refactorizar `_generate_html_content_with_images()` (usar método base)
4. ✅ Test: Verificar que HTML y markdown generan mismo contenido (excepto headers/imágenes)

### Fase 2: Unificar Extracción de Texto (Prioridad MEDIA)

1. ✅ Actualizar `get_text()` para soportar `page_offset`, `optimize`, `domain`
2. ✅ Refactorizar `save_text()` para usar `get_text()` internamente
3. ✅ Test: Verificar que archivos .txt generados son idénticos

### Fase 3: Corregir y Unificar Imágenes (Prioridad ALTA - tiene bug)

1. ✅ Actualizar `_enrich_page_images()` para usar MIME correcto
2. ✅ Agregar parámetro `correct_mime` para backward compatibility
3. ✅ Eliminar código duplicado de `_generate_html_content_with_images()`
4. ✅ Test: Verificar que data URIs usan MIME correcto (JPG, PNG, TIFF)

### Fase 4: Testing y Validación

1. ✅ Test de integración: Procesar PDF real y verificar salidas
2. ✅ Comparar archivos generados antes/después de refactorización
3. ✅ Verificar que no hay regresiones funcionales

---

## RIESGOS Y MITIGACIÓN

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Cambiar comportamiento de métodos públicos | Baja | Alto | `get_text()` mantiene defaults compatibles |
| Romper HTML export | Media | Alto | Tests exhaustivos de HTML generado |
| MIME type incorrecto causa problemas | Baja | Medio | Flag `correct_mime` permite rollback |
| Métodos base muy complejos | Media | Bajo | Funciones lambda mantienen legibilidad |

---

## APROBACIÓN

**Estado:** 📋 Pendiente de aprobación del usuario
**Recomendación:** Ejecutar todas las fases (máximo impacto, bugs corregidos)

---

**Autor:** Claude Sonnet 4.5
**Fecha:** 2025-12-26
**Versión:** 1.0
