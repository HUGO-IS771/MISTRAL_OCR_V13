#!/usr/bin/env python3
"""
HTML templates for Mistral OCR client.

Se conserva el HTML premium fuera del cliente principal para reducir el peso
del modulo principal y cargarlo solo cuando se requiera.

IMPORTANTE: La librería marked.js se incrusta directamente en el HTML para:
1. Evitar bloqueos de seguridad del navegador (CSP, tracking prevention)
2. Permitir visualización offline sin conexión a internet
3. Garantizar que el archivo funcione siempre, sin dependencias externas
"""

import json
from pathlib import Path


def _get_marked_js_library() -> str:
    """
    Carga la librería marked.js desde el archivo local.

    La librería se incrusta directamente en el HTML para evitar:
    - Bloqueos de CDN por políticas de seguridad del navegador
    - Dependencia de conexión a internet
    - Fallos por tracking prevention en Edge/Chrome

    Returns:
        str: Código JavaScript de marked.js minificado
    """
    marked_path = Path(__file__).parent / "marked.min.js"

    if marked_path.exists():
        return marked_path.read_text(encoding='utf-8')
    else:
        # Fallback: Si no existe el archivo, retornar un stub que muestra el markdown en texto plano
        return '''
        // marked.js not found - fallback to plain text display
        console.warn("marked.min.js not found, displaying raw markdown");
        window.marked = {
            parse: function(text) {
                return '<pre style="white-space: pre-wrap; word-wrap: break-word;">' +
                       text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                       '</pre>';
            },
            setOptions: function() {},
            use: function() {}
        };
        '''

def render_premium_html(body_content: str, title: str, theme: str,
                        total_pages: int, total_images: int) -> str:
    """Genera HTML completo con estilos premium."""

    # Serializar contenido markdown de forma segura para JavaScript
    # json.dumps() maneja TODOS los caracteres especiales automáticamente:
    # - Escapa comillas, backslashes, newlines
    # - Convierte a string JSON válido
    # - Maneja unicode correctamente
    body_content_json = json.dumps(body_content)

    # Cargar librería marked.js incrustada (sin CDN)
    marked_js_library = _get_marked_js_library()

    # Colores según tema
    if theme == "dark":
        bg_color = "#1a1a2e"
        text_color = "#eaeaea"
        card_bg = "#16213e"
        accent_color = "#0f3460"
        border_color = "#0f3460"
        header_bg = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
        table_header_bg = "#0f3460"
        table_alt_bg = "#1a1a2e"
        link_color = "#64b5f6"
        code_bg = "#0d1117"
    else:
        bg_color = "#f8fafc"
        text_color = "#1e293b"
        card_bg = "#ffffff"
        accent_color = "#3b82f6"
        border_color = "#e2e8f0"
        header_bg = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
        table_header_bg = "#f1f5f9"
        table_alt_bg = "#f8fafc"
        link_color = "#2563eb"
        code_bg = "#f1f5f9"

    html_template = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="generator" content="Mistral OCR Client v4.0">
    <meta name="description" content="Documento procesado con Mistral OCR - {total_pages} paginas">
    <title>{title}</title>
    
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    
    <style>
        /* === Reset & Base === */
        *, *::before, *::after {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        html {{
            scroll-behavior: smooth;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: {bg_color};
            color: {text_color};
            line-height: 1.7;
            font-size: 16px;
            min-height: 100vh;
        }}
        
        /* === Header Premium === */
        .header {{
            background: {header_bg};
            color: white;
            padding: 2.5rem 2rem;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='m36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
            opacity: 0.5;
        }}
        
        .header h1 {{
            font-size: 2.25rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
            position: relative;
            text-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .header-meta {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            font-size: 0.9rem;
            opacity: 0.9;
            position: relative;
        }}
        
        .header-meta span {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        /* === Main Content === */
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        .content {{
            background: {card_bg};
            border-radius: 16px;
            padding: 3rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 
                        0 2px 4px -1px rgba(0, 0, 0, 0.06);
            border: 1px solid {border_color};
        }}
        
        /* === Typography === */
        h1, h2, h3, h4, h5, h6 {{
            font-weight: 600;
            margin-top: 2rem;
            margin-bottom: 1rem;
            color: {text_color};
        }}
        
        h1 {{ font-size: 2rem; border-bottom: 3px solid {accent_color}; padding-bottom: 0.5rem; }}
        h2 {{ font-size: 1.5rem; border-bottom: 2px solid {border_color}; padding-bottom: 0.4rem; }}
        h3 {{ font-size: 1.25rem; }}
        h4 {{ font-size: 1.1rem; }}
        
        p {{
            margin-bottom: 1.25rem;
            text-align: justify;
            hyphens: auto;
        }}
        
        a {{
            color: {link_color};
            text-decoration: none;
            border-bottom: 1px solid transparent;
            transition: border-color 0.2s ease;
        }}
        
        a:hover {{
            border-bottom-color: {link_color};
        }}
        
        /* === Images === */
        img {{
            max-width: 100%;
            height: auto;
            border-radius: 12px;
            margin: 1.5rem auto;
            display: block;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        
        img:hover {{
            transform: scale(1.02);
            box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.2);
        }}
        
        /* === OCR Images with Figures === */
        .ocr-image {{
            margin: 2rem 0;
            text-align: center;
            background: {table_alt_bg};
            padding: 1.5rem;
            border-radius: 12px;
            border: 1px solid {border_color};
        }}
        
        .ocr-image figcaption {{
            font-size: 0.9rem;
            color: {text_color};
            opacity: 0.7;
            margin-top: 0.75rem;
            font-style: italic;
        }}
        
        /* === Tables === */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1.5rem 0;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}

        thead {{
            background-color: {table_header_bg};
        }}

        th, td {{
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid {border_color};
        }}

        tbody tr:nth-child(even) {{
            background-color: {table_alt_bg};
        }}

        /* === OCR Tables Container === */
        /* Contenedor para tablas extraídas por Mistral OCR */
        .ocr-table {{
            margin: 2rem 0;
            overflow-x: auto;
            border-radius: 12px;
            background: {card_bg};
            padding: 1rem;
            border: 1px solid {border_color};
        }}

        .ocr-table table {{
            margin: 0;
            min-width: 100%;
        }}

        .ocr-table th {{
            background-color: {table_header_bg};
            font-weight: 600;
            white-space: nowrap;
        }}

        .ocr-table td {{
            vertical-align: top;
        }}

        /* Estilos para hover en filas de tablas OCR */
        .ocr-table tbody tr:hover {{
            background-color: {accent_color}20;
        }}
        
        /* === Code Blocks === */
        pre {{
            background: {code_bg};
            padding: 1rem 1.5rem;
            border-radius: 10px;
            overflow-x: auto;
            margin: 1.5rem 0;
        }}
        
        code {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9rem;
        }}
        
        /* === Blockquotes === */
        blockquote {{
            border-left: 4px solid {accent_color};
            background: {table_alt_bg};
            padding: 1rem 1.5rem;
            margin: 1.5rem 0;
            border-radius: 0 12px 12px 0;
        }}
        
        /* === Lists === */
        ul, ol {{
            margin: 1rem 0 1rem 2rem;
        }}
        
        li {{
            margin-bottom: 0.5rem;
        }}
        
        /* === Page Separator === */
        hr {{
            border: none;
            height: 2px;
            background: linear-gradient(90deg, transparent, {accent_color}, transparent);
            margin: 3rem 0;
        }}
        
        /* === Footer === */
        .footer {{
            text-align: center;
            padding: 2rem;
            color: {text_color};
            opacity: 0.7;
            font-size: 0.9rem;
        }}
        
        .footer a {{
            color: {link_color};
            font-weight: 500;
        }}
        
        /* === Floating Buttons === */
        .floating-buttons {{
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            z-index: 1000;
        }}
        
        .floating-button {{
            background: {accent_color};
            color: white;
            border: none;
            padding: 0.75rem 1rem;
            border-radius: 50px;
            cursor: pointer;
            font-size: 0.9rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        
        .floating-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 12px -2px rgba(0, 0, 0, 0.3);
        }}
        
        /* === Responsive === */
        @media (max-width: 768px) {{
            .container {{
                padding: 1rem;
            }}
            
            .content {{
                padding: 1.5rem;
            }}
            
            .header-meta {{
                flex-direction: column;
                gap: 0.5rem;
            }}
            
            .floating-buttons {{
                bottom: 1rem;
                right: 1rem;
            }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <h1>{title}</h1>
        <div class="header-meta">
            <span>{total_pages} paginas</span>
            <span>{total_images} imagenes</span>
            <span>Procesado con Mistral OCR</span>
        </div>
    </header>
    
    <div class="container">
        <main class="content" id="content">
            <!-- Content will be injected by JS -->
        </main>
    </div>
    
    <div class="footer">
        Documento generado con <a href="https://mistral.ai" target="_blank">Mistral OCR</a>
    </div>
    
    <div class="floating-buttons">
        <button class="floating-button" onclick="window.scrollTo({{top: 0, behavior: 'smooth'}})">
            Arriba
        </button>
        <button class="floating-button" onclick="window.print()">
            Imprimir
        </button>
    </div>
    
    <!-- LIBRERIA MARKED.JS INCRUSTADA - Sin dependencia de CDN externo -->
    <!-- Esto garantiza que el archivo funcione sin internet y sin bloqueos de seguridad -->
    <script>
        {marked_js_library}
    </script>
    <script>
        // Markdown content (safely serialized via JSON)
        // json.dumps() maneja TODOS los caracteres especiales automáticamente
        const markdownContent = {body_content_json};

        // Función principal de renderizado - se ejecuta cuando el DOM está listo
        function renderDocumento() {{
            const container = document.getElementById('content');

            // Verificar que marked.js esté disponible
            if (typeof marked === 'undefined') {{
                console.error('marked.js no está disponible');
                container.innerHTML = '<pre style="white-space: pre-wrap; word-wrap: break-word;">' +
                    markdownContent.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') +
                    '</pre>';
                return;
            }}

            try {{
                // Configure marked options for GFM (GitHub Flavored Markdown)
                marked.setOptions({{
                    gfm: true,          // Enable GitHub Flavored Markdown
                    breaks: true,       // Convert \\n to <br>
                    headerIds: true,    // Add IDs to headers
                    mangle: false       // Don't escape email addresses
                }});

                // CRITICAL: Configure renderer to preserve HTML tables from Mistral OCR
                // Mistral OCR returns tables as raw HTML when table_format="html"
                // NOTE: En marked.js v12+, los callbacks reciben objetos token, no strings
                const renderer = {{
                    html(token) {{
                        // token puede ser un objeto {{text: '...'}} o un string directo
                        // Manejar ambos casos para compatibilidad
                        if (typeof token === 'string') {{
                            return token;
                        }}
                        if (token && typeof token.text === 'string') {{
                            return token.text;
                        }}
                        if (token && typeof token.raw === 'string') {{
                            return token.raw;
                        }}
                        // Fallback: convertir a string de forma segura
                        console.warn('HTML token inesperado:', token);
                        return String(token || '');
                    }}
                }};
                marked.use({{ renderer }});

                // Render markdown to HTML
                const htmlContent = marked.parse(markdownContent);
                container.innerHTML = htmlContent;

                // Add special class to images for styling
                container.querySelectorAll('img').forEach((img, index) => {{
                    const figure = document.createElement('figure');
                    figure.classList.add('ocr-image');
                    img.parentNode.insertBefore(figure, img);
                    figure.appendChild(img);

                    const caption = document.createElement('figcaption');
                    const parent = figure.parentElement;
                    let descNode = null;
                    if (parent && parent.nextElementSibling && parent.nextElementSibling.tagName === 'P') {{
                        const candidate = parent.nextElementSibling;
                        if (candidate.querySelector('em')) {{
                            descNode = candidate;
                        }}
                    }}

                    if (descNode) {{
                        caption.innerHTML = descNode.innerHTML;
                        figure.appendChild(caption);
                        descNode.remove();
                    }}

                    // Click to enlarge
                    img.addEventListener('click', () => {{
                        const overlay = document.createElement('div');
                        overlay.style.cssText = `
                            position: fixed;
                            top: 0;
                            left: 0;
                            width: 100%;
                            height: 100%;
                            background: rgba(0,0,0,0.9);
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            z-index: 9999;
                            cursor: zoom-out;
                        `;
                        const enlargedImg = document.createElement('img');
                        enlargedImg.src = img.src;
                        enlargedImg.style.maxWidth = '90%';
                        enlargedImg.style.maxHeight = '90%';
                        enlargedImg.style.boxShadow = '0 0 50px rgba(255,255,255,0.2)';
                        enlargedImg.style.borderRadius = '12px';
                        overlay.appendChild(enlargedImg);
                        overlay.addEventListener('click', () => overlay.remove());
                        document.body.appendChild(overlay);
                    }});
                }});

                // Style horizontal separators
                container.querySelectorAll('hr').forEach(hr => {{
                    hr.classList.add('page-separator');
                }});

                console.log('Documento renderizado exitosamente');

            }} catch (error) {{
                container.innerHTML = '<p style="color: red;">Error al renderizar el documento: ' + error.message + '</p>';
                console.error('Error renderizando markdown:', error);
            }}
        }}

        // Ejecutar renderizado cuando el DOM esté completamente cargado
        // Usar 'load' en lugar de 'DOMContentLoaded' para asegurar que todo el contenido
        // (incluyendo scripts grandes de 5MB+) esté completamente procesado
        window.addEventListener('load', renderDocumento);
    </script>
</body>
</html>'''

    return html_template
