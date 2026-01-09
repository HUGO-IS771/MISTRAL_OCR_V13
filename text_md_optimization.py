#!/usr/bin/env python3
"""
Optimización de texto y markdown para documentos OCR.
Proporciona funcionalidad real de limpieza y mejora de texto.

Incluye soporte especializado para documentos legales (domain="legal").
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Intentar importar formateador de documentos legales
try:
    from legal_document_formatter import LegalTextOptimizer
    LEGAL_FORMATTER_AVAILABLE = True
except ImportError:
    LEGAL_FORMATTER_AVAILABLE = False
    logger.warning("Formateador legal no disponible (legal_document_formatter no encontrado)")

# Intentar importar validación lingüística (opcional)
try:
    from language_validator import ContextualCorrector
    LINGUISTIC_VALIDATION_AVAILABLE = True
except ImportError:
    LINGUISTIC_VALIDATION_AVAILABLE = False
    logger.warning("Validación lingüística no disponible (language_validator no encontrado)")

# Intentar importar detector de tablas (opcional)
try:
    from table_detector import TableDetector
    TABLE_DETECTION_AVAILABLE = True
except ImportError:
    TABLE_DETECTION_AVAILABLE = False
    logger.warning("Detección de tablas no disponible (table_detector no encontrado)")


class TextOptimizer:
    """Optimizador de texto con correcciones comunes de OCR."""

    def __init__(self, domain="general", custom_replacements=None, use_linguistic_validation=True):
        self.domain = domain
        self.use_linguistic_validation = use_linguistic_validation and LINGUISTIC_VALIDATION_AVAILABLE

        # Validar custom_replacements
        if custom_replacements:
            if not isinstance(custom_replacements, list):
                raise ValueError("custom_replacements debe ser una lista")
            for item in custom_replacements:
                if not isinstance(item, (tuple, list)) or len(item) != 2:
                    raise ValueError("Cada regla debe ser tupla (pattern, replacement)")
        self.custom_replacements = custom_replacements or []

        # Inicializar validador lingüístico si está habilitado
        self.linguistic_corrector = None
        if self.use_linguistic_validation:
            try:
                self.linguistic_corrector = ContextualCorrector(language="es")
                logger.info("✓ Validación lingüística ACTIVADA")
            except Exception as e:
                logger.warning(f"Error inicializando validación lingüística: {e}")
                self.use_linguistic_validation = False
        else:
            logger.info("Validación lingüística desactivada")

        # Inicializar formateador legal si el dominio es "legal"
        self.legal_optimizer = None
        if domain == "legal" and LEGAL_FORMATTER_AVAILABLE:
            try:
                self.legal_optimizer = LegalTextOptimizer(style="plain")
                logger.info("Formateador de documentos legales ACTIVADO (texto plano)")
            except Exception as e:
                logger.warning(f"Error inicializando formateador legal: {e}")
        elif domain == "legal" and not LEGAL_FORMATTER_AVAILABLE:
            logger.warning("Dominio 'legal' seleccionado pero formateador no disponible")

        # Patrones unificados de errores OCR (50+ patrones)
        self.ocr_patterns = [
            # === CONFUSIONES LETRA-NÚMERO (Alta frecuencia) ===
            (r'(?<!\w)l(?=\d)', '1'),  # l antes de números → 1
            (r'(?<=\d)O(?=\d)', '0'),  # O entre números → 0
            (r'(?<=\d)o(?=\d)', '0'),  # o minúscula entre números → 0
            (r'(?<=\d)l(?=\d)', '1'),  # l entre números → 1
            (r'(?<=\d)I(?=\d)', '1'),  # I entre números → 1
            (r'(?<=\d)S(?=\d)', '5'),  # S entre números → 5
            (r'(?<=\d)Z(?=\d)', '2'),  # Z entre números → 2

            # === CONFUSIONES DE LETRAS (Combinaciones comunes) ===
            (r'\brn\b', 'm'),          # "rn" juntos → "m"
            (r'(?<!\w)rn(?=\s)', 'm'), # "rn" al final de palabra → "m"
            (r'\bcl\b', 'd'),          # "cl" → "d"
            (r'\bvv\b', 'w'),          # "vv" → "w"
            (r'\bii\b', 'll'),         # "ii" → "ll"
            (r'\bIl\b', 'll'),         # "Il" → "ll"
            (r'\blI\b', 'll'),         # "lI" → "ll"
            (r'\bnn\b', 'ñ'),          # "nn" en palabras españolas → "ñ"

            # === PALABRAS COMUNES MAL RECONOCIDAS (Español) ===
            (r'\beI\b', 'el'),         # "eI" → "el"
            (r'\bIa\b', 'la'),         # "Ia" → "la"
            (r'\bcle\b', 'de'),        # "cle" → "de"
            (r'\bque\b(?=\d)', 'que '),# "que" pegado a número
            (r'\bel(?=\d)', 'el '),    # "el" pegado a número
            (r'\bla(?=\d)', 'la '),    # "la" pegado a número
            (r'\bde(?=\d)', 'de '),    # "de" pegado a número
            (r'\ben(?=\d)', 'en '),    # "en" pegado a número

            # === PUNTUACIÓN Y CARACTERES ESPECIALES ===
            (r'¦', 'l'),               # Barra vertical → "l"
            (r'§', 'S'),               # Símbolo sección → "S"
            (r'¢', 'c'),               # Símbolo centavo → "c"
            (r'£', 'E'),               # Libra → "E"
            (r'µ', 'u'),               # Mu → "u"
            (r'¶', 'P'),               # Símbolo párrafo → "P"
            (r'º', 'o'),               # Ordinal → "o"
            (r'ª', 'a'),               # Ordinal femenino → "a"

            # === MAYÚSCULAS/MINÚSCULAS CONFUSAS ===
            (r'(?<=\w)l(?=[A-Z])', 'I'), # l antes de mayúscula → I
            (r'(?<=[A-Z])l(?=[A-Z])', 'I'), # l entre mayúsculas → I

            # === ESPACIADO INCORRECTO ===
            (r'([a-záéíóúñ])(\d)', r'\1 \2'),  # Letra pegada a número
            (r'(\d)([a-záéíóúñ])', r'\1 \2'),  # Número pegado a letra
            (r'([.,;:!?])([A-ZÁÉÍÓÚÑ])', r'\1 \2'),  # Puntuación pegada a mayúscula

            # === ACENTOS COMUNES (Español) ===
            (r'\bARTICULO\b', 'ARTÍCULO'),
            (r'\bPAGINA\b', 'PÁGINA'),
            (r'\bNUMERO\b', 'NÚMERO'),
            (r'\bPARAGRAFO\b', 'PARÁGRAFO'),
            (r'\bCAP\s*iTULO\b', 'CAPÍTULO'),

            # === GUIONES Y RAYAS ===
            (r'---+', '—'),            # Múltiples guiones → em-dash
            (r'--', '—'),              # Dos guiones → em-dash
            (r'_+', '_'),              # Múltiples guiones bajos → uno

            # === COMILLAS Y APÓSTROFES ===
            (r"''", '"'),              # Dos apóstrofes → comilla
            (r'``', '"'),              # Dos backticks → comilla
            (r"'([^']{1,50})'", r'"\1"'),  # Apóstrofes como comillas

            # === NÚMEROS ROMANOS MAL FORMADOS ===
            (r'\bI\s+I\b', 'II'),      # "I I" → "II"
            (r'\bI\s+V\b', 'IV'),      # "I V" → "IV"
            (r'\bV\s+I\b', 'VI'),      # "V I" → "VI"

            # === FRACCIONES Y SÍMBOLOS MATEMÁTICOS ===
            (r'1/2', '½'),
            (r'1/4', '¼'),
            (r'3/4', '¾'),
            (r'<=', '≤'),
            (r'>=', '≥'),
            (r'!=', '≠'),
        ]
    
    def optimize_text(self, text):
        """Optimiza el texto aplicando correcciones de OCR."""
        if not text:
            return text

        # Si es dominio legal, usar formateador especializado
        if self.domain == "legal" and self.legal_optimizer:
            return self.legal_optimizer.optimize(text)

        # Aplicar correcciones básicas de espaciado/puntuación
        optimized = self._fix_spacing(text)
        optimized = self._fix_punctuation(optimized)

        # Corregir hifenación de fin de línea (antes de otros patrones)
        optimized = self._fix_hyphenation(optimized)

        # Corregir comillas y paréntesis desemparejados
        optimized = self._fix_unbalanced_pairs(optimized)

        # Aplicar patrones OCR con o sin validación lingüística
        if self.use_linguistic_validation and self.linguistic_corrector:
            # Usar validación lingüística para evitar falsos positivos
            optimized, stats = self.linguistic_corrector.correct_text_with_validation(
                optimized,
                self.ocr_patterns
            )
            logger.debug(
                f"Correcciones OCR con validación: "
                f"{stats['applied']} aplicadas, {stats['skipped']} omitidas"
            )
        else:
            # Aplicar todos los patrones sin validación
            for pattern, replacement in self.ocr_patterns:
                optimized = re.sub(pattern, replacement, optimized)

        # Aplicar reglas personalizadas si existen
        if self.custom_replacements:
            logger.debug(f"Aplicando {len(self.custom_replacements)} reglas personalizadas")

            if self.use_linguistic_validation and self.linguistic_corrector:
                # Con validación
                optimized, custom_stats = self.linguistic_corrector.correct_text_with_validation(
                    optimized,
                    self.custom_replacements
                )
                logger.debug(
                    f"Reglas personalizadas: "
                    f"{custom_stats['applied']} aplicadas, {custom_stats['skipped']} omitidas"
                )
            else:
                # Sin validación
                for pattern, replacement in self.custom_replacements:
                    optimized = re.sub(pattern, replacement, optimized)

        return optimized
    
    def _fix_spacing(self, text):
        """Corrige problemas de espaciado."""
        # Múltiples espacios a uno solo
        text = re.sub(r' +', ' ', text)
        # Espacios antes de puntuación
        text = re.sub(r' +([.,;:!?])', r'\1', text)
        # Asegurar espacio después de puntuación
        text = re.sub(r'([.,;:!?])(?=[A-Za-z])', r'\1 ', text)
        return text
    
    def _fix_punctuation(self, text):
        """Corrige puntuación mal reconocida."""
        # Comillas rectas a tipográficas
        text = re.sub(r'"([^"]*)"', r'"\1"', text)
        # Guiones múltiples a em-dash
        text = re.sub(r'--+', '—', text)
        return text

    def _fix_unbalanced_pairs(self, text):
        """
        Corrige comillas y paréntesis desemparejados.

        Patrones corregidos:
        - "texto' → "texto" (comilla doble + apóstrofe)
        - 'texto" → "texto" (apóstrofe + comilla doble)
        - (texto  → (texto) (paréntesis sin cerrar al fin de línea)
        - texto)  → (texto) (paréntesis sin abrir al inicio)
        """
        # Comillas mezcladas: "texto' → "texto"
        text = re.sub(r'"([^"\']+)\'', r'"\1"', text)

        # Comillas mezcladas invertidas: 'texto" → "texto"
        text = re.sub(r'\'([^"\']+)"', r'"\1"', text)

        # Paréntesis sin cerrar al final de línea: (texto\n → (texto)\n
        text = re.sub(r'\(([^()\n]+)\n', r'(\1)\n', text)

        # Paréntesis sin abrir al inicio de línea: \ntexto) → \n(texto)
        text = re.sub(r'\n([^()\n]+)\)', r'\n(\1)', text)

        # Corchetes sin cerrar al final de línea: [texto\n → [texto]\n
        text = re.sub(r'\[([^\[\]\n]+)\n', r'[\1]\n', text)

        # Corchetes sin abrir al inicio de línea: \ntexto] → \n[texto]
        text = re.sub(r'\n([^\[\]\n]+)\]', r'\n[\1]', text)

        return text

    def _fix_hyphenation(self, text):
        """
        Reúne palabras separadas por guión al final de línea.

        Corrige hifenación de fin de línea típica de documentos con columnas:
        - "docu-\\nmento" → "documento"
        - "infor-\\nmación" → "información"

        Excepciones: No une guiones legítimos (ej: "hijo-padre" en misma línea)
        """
        # Patrón: palabra terminada en guión + salto de línea + continuación minúscula
        # El guión debe estar al final de línea (antes de \n o \r\n)
        # La continuación debe comenzar con minúscula (indica que es parte de la misma palabra)
        pattern = r'(\w+)-\s*[\r\n]+\s*([a-záéíóúüñ])'

        # Reemplazar: unir las partes de la palabra
        text = re.sub(pattern, r'\1\2', text)

        return text


class MarkdownOptimizer(TextOptimizer):
    """Optimizador específico para markdown con detección de tablas."""

    def __init__(self, domain="general", custom_replacements=None,
                 use_linguistic_validation=True, detect_tables=True):
        """
        Inicializa optimizador de markdown.

        Args:
            domain: Dominio de optimización
            custom_replacements: Reglas personalizadas
            use_linguistic_validation: Activar validación lingüística
            detect_tables: Activar detección y preservación de tablas
        """
        super().__init__(domain, custom_replacements, use_linguistic_validation)

        self.detect_tables = detect_tables and TABLE_DETECTION_AVAILABLE
        self.table_detector = None

        # En markdown, forzar formateador legal en estilo markdown
        if domain == "legal" and LEGAL_FORMATTER_AVAILABLE:
            try:
                self.legal_optimizer = LegalTextOptimizer(style="markdown")
                logger.info("Formateador de documentos legales ACTIVADO (markdown)")
            except Exception as e:
                logger.warning(f"Error inicializando formateador legal (markdown): {e}")
        elif domain == "articulos" and LEGAL_FORMATTER_AVAILABLE:
            try:
                self.legal_optimizer = LegalTextOptimizer(style="articulos")
                logger.info("Formateador de ARTÍCULOS ACTIVADO (con separadores)")
            except Exception as e:
                logger.warning(f"Error inicializando formateador de artículos: {e}")


        if self.detect_tables:
            try:
                self.table_detector = TableDetector(min_confidence=0.6)
                logger.info("✓ Detección de tablas ACTIVADA")
            except Exception as e:
                logger.warning(f"Error inicializando detector de tablas: {e}")
                self.detect_tables = False
        else:
            logger.info("Detección de tablas desactivada")

    def optimize_markdown(self, markdown_text):
        """Optimiza markdown manteniendo su estructura y tablas."""
        if not markdown_text:
            return markdown_text

        # 0. Proteger tablas HTML ya embebidas (<table>...</table>)
        protected_html_tables = {}
        if '<table' in markdown_text.lower():
            def _html_table_replacer(match):
                placeholder = f"<<<HTML_TABLE_{len(protected_html_tables)}>>>"
                protected_html_tables[placeholder] = match.group(0)
                return placeholder

            text_to_optimize = re.sub(
                r'(?is)<table\b.*?</table>',
                _html_table_replacer,
                markdown_text
            )
        else:
            text_to_optimize = markdown_text

        # 1. Detectar y extraer tablas si está habilitado
        protected_tables = {}

        if self.detect_tables and self.table_detector:
            # Detectar tablas
            tables = self.table_detector.detect_tables(text_to_optimize)

            if tables:
                logger.info(f"Detectadas {len(tables)} tablas para proteger")

                # Reemplazar tablas con placeholders
                lines = text_to_optimize.splitlines()
                for i, table in enumerate(tables):
                    placeholder = f"<<<TABLE_{i}>>>"

                    # Optimizar solo el contenido de las celdas
                    optimized_table = self._optimize_table_cells(table)

                    # Guardar tabla optimizada
                    protected_tables[placeholder] = optimized_table

                    # Reemplazar región de tabla con placeholder
                    for line_idx in range(table.start_line, table.end_line + 1):
                        if line_idx < len(lines):
                            lines[line_idx] = ""

                    # Insertar placeholder en la primera línea
                    if table.start_line < len(lines):
                        lines[table.start_line] = placeholder

                text_to_optimize = "\n".join(lines)

        # 2. Structured legal formatting for full document
        if (self.domain == "legal" or self.domain == "articulos") and self.legal_optimizer:
            # PROTEGER headers y footers de Mistral OCR 3 antes de optimización legal
            header_footer_placeholders = {}
            
            def _header_footer_replacer(match):
                placeholder = f"<<<HEADER_FOOTER_{len(header_footer_placeholders)}>>>"
                header_footer_placeholders[placeholder] = match.group(0)
                logger.debug(f"Protegiendo header/footer: {match.group(0)[:50]}... -> {placeholder}")
                return placeholder
            
            # Proteger líneas que contienen headers/footers de Mistral OCR 3
            # SOLO proteger líneas que empiezan con **Encabezado:** o **Pie de página:**
            # y capturar solo hasta el final de línea (evitar capturar múltiples líneas)
            # Proteger líneas que contienen headers/footers de Mistral OCR 3
            # MEJORADO: Capturar bloques COMPLETOS de Encabezado y Pie de página (multilínea)
            
            # Header: capturar desde **Encabezado:** hasta vacío o inicio de contenido
            text_to_optimize = re.sub(
                r'(\*\*Encabezado:\*\*.*?(?=\n\n(?!\*\*Pie de página:\*\*)|$))',
                _header_footer_replacer,
                text_to_optimize,
                flags=re.DOTALL | re.MULTILINE 
            )
            
            # Footer: capturar desde \n\n**Pie de página:** hasta el final del bloque
            text_to_optimize = re.sub(
                r'(\n\n\*\*Pie de página:\*\*.*?(?=\n\n|$))',
                _header_footer_replacer,
                text_to_optimize,
                flags=re.DOTALL | re.MULTILINE
            )

            
            image_placeholders = {}

            def _image_replacer(match):
                placeholder = f"<<<IMG_{len(image_placeholders)}>>>"
                image_placeholders[placeholder] = match.group(0)
                return placeholder

            text_to_optimize = re.sub(
                r'!\[[^\]]*\]\([^\)]+\)',
                _image_replacer,
                text_to_optimize
            )

            optimized = self.legal_optimizer.optimize(text_to_optimize)
            
            # RESTAURAR headers y footers protegidos
            logger.debug(f"Restaurando {len(header_footer_placeholders)} headers/footers protegidos")
            # Restaurar directamente (método simple para evitar duplicaciones)
            for placeholder, header_footer_content in header_footer_placeholders.items():
                if placeholder in optimized:
                    optimized = optimized.replace(placeholder, header_footer_content)
                    logger.debug(f"Restaurado placeholder {placeholder}")
                else:
                    logger.debug(f"Placeholder {placeholder} no encontrado en resultado optimizado")

            for placeholder, table_markdown in protected_tables.items():
                optimized = re.sub(
                    rf'^[ \t]*{re.escape(placeholder)}[ \t]*$',
                    table_markdown,
                    optimized,
                    flags=re.MULTILINE
                )

            for placeholder, table_html in protected_html_tables.items():
                optimized = re.sub(
                    rf'^[ \t]*{re.escape(placeholder)}[ \t]*$',
                    table_html,
                    optimized,
                    flags=re.MULTILINE
                )

            for placeholder, image_md in image_placeholders.items():
                optimized = re.sub(
                    rf'^[ \t]*{re.escape(placeholder)}[ \t]*$',
                    image_md,
                    optimized,
                    flags=re.MULTILINE
                )

            return optimized

        # 3. Optimizar texto normal (sin tablas)
        lines = text_to_optimize.split('\n')
        optimized_lines = []

        for line in lines:
            # Preservar placeholders de tablas
            if (line.strip().startswith('<<<TABLE_') or line.strip().startswith('<<<HTML_TABLE_')) and line.strip().endswith('>>>'):
                optimized_lines.append(line)
            # Preservar líneas de imagen
            elif line.strip().startswith('!['):
                optimized_lines.append(line)
            # Optimizar encabezados
            elif line.strip().startswith('#'):
                header_match = re.match(r'^(#+)\s*(.+)', line)
                if header_match:
                    level, content = header_match.groups()
                    optimized_content = self.optimize_text(content)
                    optimized_lines.append(f"{level} {optimized_content}")
                else:
                    optimized_lines.append(line)
            # Optimizar texto normal
            else:
                optimized_lines.append(self.optimize_text(line))

        optimized = '\n'.join(optimized_lines)

        # 4. Restaurar tablas optimizadas
        for placeholder, table_markdown in protected_tables.items():
            optimized = optimized.replace(placeholder, table_markdown)

        # 5. Restaurar tablas HTML embebidas
        for placeholder, table_html in protected_html_tables.items():
            optimized = optimized.replace(placeholder, table_html)

        return optimized

    def _optimize_table_cells(self, table) -> str:
        """
        Optimiza el contenido de las celdas de una tabla.

        Args:
            table: TableRegion con la tabla detectada

        Returns:
            str: Tabla en markdown con celdas optimizadas
        """
        # Optimizar cada celda
        optimized_content = []
        for row in table.content:
            optimized_row = []
            for cell in row:
                # Optimizar solo el texto de la celda
                optimized_cell = self.optimize_text(cell) if cell else ""
                optimized_row.append(optimized_cell)
            optimized_content.append(optimized_row)

        # Crear TableRegion con contenido optimizado
        from table_detector import TableRegion
        optimized_table = TableRegion(
            start_line=table.start_line,
            end_line=table.end_line,
            rows=table.rows,
            cols=table.cols,
            content=optimized_content,
            confidence=table.confidence,
            separator_chars=table.separator_chars
        )

        # Convertir a markdown
        return self.table_detector.to_markdown_table(optimized_table)


class OptimizationProfile:
    """Perfil de optimización configurable."""
    
    def __init__(self, name="default", domain="general"):
        self.name = name
        self.domain = domain
        self.rules = {
            'fix_spacing': True,
            'fix_punctuation': True,
            'apply_domain_rules': True
        }
    
    def get_rules(self):
        """Obtener reglas activas."""
        return {k: v for k, v in self.rules.items() if v}
    
    def set_rule(self, rule_type, rule_value):
        """Activar/desactivar regla específica."""
        self.rules[rule_type] = rule_value
        
    def add_pattern_replacement(self, pattern, replacement):
        """Añadir patrón de reemplazo personalizado."""
        if 'custom_patterns' not in self.rules:
            self.rules['custom_patterns'] = []
        self.rules['custom_patterns'].append((pattern, replacement))