# Fix: HTML Tables Not Rendering in Export

## Problema Identificado

Las tablas HTML generadas por Mistral OCR no se procesan correctamente al exportar a HTML premium.

## Causa Raíz

Mistral OCR retorna tablas como HTML nativo cuando se usa `table_format: "html"`:
```python
process_params = {
    "table_format": "html",  # ← Genera <table> en page.markdown
}
```

El contenido `page.markdown` contiene:
- Markdown estándar para texto
- **HTML puro para tablas** (`<table>`, `<tr>`, `<td>`, etc.)

### Flujo de Procesamiento

1. **OCR Response** → `page.markdown` contiene: texto markdown + `<table>` HTML
2. **_generate_html_content_with_images()** → Genera markdown con imágenes data URI
3. **Escape JavaScript** → Escapa backticks, backslashes, etc.
4. **HTML Template** → Inserta en template literal de JS: `` `{body_content}` ``
5. **marked.js (navegador)** → Convierte markdown → HTML

### Problema en Paso 5

**marked.js por defecto EN VERSIONES ANTIGUAS sanitizaba HTML**, pero en versiones modernas (v4+) permite HTML passthrough. Sin embargo, necesitamos asegurar que el renderer preserve el HTML.

## Solución Implementada

### 1. Configuración de marked.js Renderer

Actualizado [html_templates.py](html_templates.py#L365-L376):

```javascript
// Configure renderer to preserve HTML tables from Mistral OCR
const renderer = new marked.Renderer();
const originalHtml = renderer.html || ((html) => html);
renderer.html = function(html) {
    // Pass through all HTML unchanged (including <table>, <tr>, <td>, etc.)
    return html;
};

marked.use({ renderer });
```

**Qué hace:**
- Crea un renderer personalizado para marked.js
- Sobrescribe el método `html()` para pasar TODO el HTML sin modificar
- Registra el renderer con `marked.use()`

### 2. Estilos CSS para Tablas

Ya implementados en [html_templates.py](html_templates.py#L195-L217):

```css
table {
    width: 100%;
    border-collapse: collapse;
    margin: 1.5rem 0;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

thead {
    background-color: {table_header_bg};
}

th, td {
    padding: 0.75rem 1rem;
    text-align: left;
    border-bottom: 1px solid {border_color};
}

tbody tr:nth-child(even) {
    background-color: {table_alt_bg};
}
```

**Características:**
- Diseño responsive (100% ancho)
- Bordes redondeados con sombra
- Colores alternados en filas (zebra striping)
- Headers con background destacado
- Adapta colores según tema (light/dark)

### 3. Escape de JavaScript Mejorado

Potencialmente necesita mejora en [mistral_ocr_client_optimized.py:331-336](mistral_ocr_client_optimized.py#L331-L336):

```python
# Escapar caracteres especiales para JavaScript
escaped_markdown = (markdown
    .replace('\\', '\\\\')
    .replace('`', '\\`')
    .replace('$', '\\$')
    .replace('</script>', '<\\/script>')
)
```

**Posibles problemas:**
- No escapa `${` para template literals
- Podría no manejar correctamente backticks dentro de atributos HTML

**Solución recomendada:**
```python
escaped_markdown = (markdown
    .replace('\\', '\\\\')       # Backslashes primero
    .replace('`', '\\`')         # Backticks
    .replace('${', '\\${')       # Template literal interpolation
    .replace('</script>', '<\\/script>')  # Cierre de script tags
)
```

## Testing Checklist

Para verificar que las tablas se renderizan correctamente:

- [ ] Procesar PDF con tablas usando GUI
- [ ] Exportar a HTML premium
- [ ] Abrir HTML en navegador
- [ ] Verificar que tablas aparecen formateadas
- [ ] Verificar estilos CSS aplicados
- [ ] Verificar responsive design
- [ ] Probar tema light y dark
- [ ] Verificar que imágenes y tablas coexisten

## Archivos Modificados

1. **html_templates.py** ✅
   - Líneas 357-376: Configuración de marked.js con renderer personalizado
   - Líneas 195-217: Estilos CSS para tablas (ya existían)

2. **mistral_ocr_client_optimized.py** (pendiente mejora opcional)
   - Líneas 331-336: Escape de JavaScript podría mejorarse

## Notas Técnicas

### ¿Por qué marked.js?

Mistral OCR retorna markdown mezclado con HTML. Opciones:

1. **Usar marked.js** (actual) ✅
   - Pro: Procesa markdown GFM + HTML nativo
   - Pro: Biblioteca estándar, bien mantenida
   - Con: Necesita configuración para HTML passthrough

2. **Procesar servidor-side con Python**
   - Pro: Control total del rendering
   - Con: Más complejo, más dependencias (markdown, beautifulsoup)
   - Con: Pierde ventajas del rendering cliente-side

3. **Solo insertar HTML directamente**
   - Pro: Simple
   - Con: Pierde capacidad de procesar markdown
   - Con: No maneja texto markdown de OCR

**Decisión:** Mantener marked.js con renderer personalizado es la mejor opción.

### Compatibilidad de Versiones

marked.js desde CDN:
```html
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
```

Esto carga la última versión. El renderer personalizado es compatible con:
- marked v4.x ✅
- marked v5.x ✅ (actual)

## Resultado Esperado

Después de la corrección, al exportar a HTML:

```html
<!-- En el navegador, después de marked.parse() -->
<table>
  <thead>
    <tr>
      <th>Columna 1</th>
      <th>Columna 2</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Dato 1</td>
      <td>Dato 2</td>
    </tr>
    <!-- ... más filas ... -->
  </tbody>
</table>
```

Con estilos CSS aplicados automáticamente.
