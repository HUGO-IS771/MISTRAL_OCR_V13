#!/usr/bin/env python3
"""
Legal Document Formatter - Formateador de Documentos Legales
-------------------------------------------------------------
Estructura automáticamente textos legales (reglamentos, códigos, leyes)
en formato jerárquico con:
- Títulos, Capítulos, Secciones
- Artículos
- Fracciones (I, II, III...)
- Incisos (a), b), c)...)
- Párrafos

Versión: 1.0.0
Fecha: 2025-12-26
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class LegalElementType(Enum):
    """Tipos de elementos en documentos legales."""
    TITULO = "titulo"
    CAPITULO = "capitulo"
    SECCION = "seccion"
    ARTICULO = "articulo"
    FRACCION = "fraccion"
    INCISO = "inciso"
    PARRAFO = "parrafo"
    TRANSITORIO = "transitorio"


@dataclass
class LegalElement:
    """Representa un elemento estructural de un documento legal."""
    type: LegalElementType
    number: str  # "1", "I", "a)", etc.
    title: str = ""  # Título opcional del elemento
    content: str = ""  # Contenido del elemento
    level: int = 0  # Nivel de indentación
    children: List['LegalElement'] = field(default_factory=list)


class LegalDocumentFormatter:
    """
    Formateador de documentos legales.

    Detecta y estructura elementos legales comunes en legislación mexicana:
    - TÍTULO PRIMERO, SEGUNDO, etc.
    - CAPÍTULO I, II, III, etc.
    - Sección Primera, Segunda, etc.
    - Artículo 1, 2, 3, etc.
    - Fracciones I, II, III, etc.
    - Incisos a), b), c), etc.
    - Párrafos numerados o sin numerar
    """

    def __init__(self, style: str = "markdown"):
        """
        Inicializa el formateador.

        Args:
            style: Estilo de salida ("markdown", "plain", "html")
        """
        self.style = style

        # Patrones para detectar elementos legales
        self._compile_patterns()

    def _compile_patterns(self):
        """Compila patrones regex para detección de elementos legales."""

        # Números romanos para reconocimiento
        roman_pattern = r'[IVXLCDM]+'

        # TÍTULO PRIMERO, TÍTULO SEGUNDO, TÍTULO 1, etc.
        self.titulo_pattern = re.compile(
            r'^[\s]*T[ÍI]TULO\s+('
            r'PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|OCTAVO|NOVENO|D[ÉE]CIMO|'
            r'UND[ÉE]CIMO|DUOD[ÉE]CIMO|'
            r'[IVXLCDM]+|'  # Romanos
            r'\d+'  # Arábigos
            r')[\s]*[:\.\-]?[\s]*(.*)$',
            re.IGNORECASE | re.MULTILINE
        )

        # CAPÍTULO I, CAPÍTULO PRIMERO, etc.
        self.capitulo_pattern = re.compile(
            r'^[\s]*CAP[ÍI]TULO\s+('
            r'PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|OCTAVO|NOVENO|D[ÉE]CIMO|'
            r'[IVXLCDM]+|'
            r'\d+'
            r')[\s]*[:\.\-]?[\s]*(.*)$',
            re.IGNORECASE | re.MULTILINE
        )

        # Sección Primera, Sección I, etc.
        self.seccion_pattern = re.compile(
            r'^[\s]*SECCI[ÓO]N\s+('
            r'PRIMERA|SEGUNDA|TERCERA|CUARTA|QUINTA|SEXTA|S[ÉE]PTIMA|OCTAVA|NOVENA|D[ÉE]CIMA|'
            r'[IVXLCDM]+|'
            r'\d+'
            r')[\s]*[:\.\-]?[\s]*(.*)$',
            re.IGNORECASE | re.MULTILINE
        )

        # Artículo 1, Artículo 1°, Art. 1, Artículo Primero, etc.
        self.articulo_pattern = re.compile(
            r'^[\s]*(?:ART[ÍI]CULO|ART\.?)\s*('
            r'\d+|'  # Números arábigos
            r'PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|OCTAVO|NOVENO|D[ÉE]CIMO|'
            r'UND[ÉE]CIMO|DUOD[ÉE]CIMO|'
            r'[IVXLCDM]+'  # Números romanos
            r')[\s]*[°º]?[\s]*[:\.\-]?[\s]*(.*)$',
            re.IGNORECASE | re.MULTILINE
        )

        # Fracciones: I., I.-, I), I -, etc.
        self.fraccion_pattern = re.compile(
            r'^[\s]*([IVXLCDM]+)[\s]*[\.\)\-:][\s]*(.*)$',
            re.MULTILINE
        )

        # Incisos: a), b), c), a., b., c., etc.
        self.inciso_pattern = re.compile(
            r'^[\s]*([a-z])[\s]*[\)\.\-:][\s]*(.*)$',
            re.IGNORECASE | re.MULTILINE
        )

        # Párrafos numerados: 1., 2., 3., etc. (cuando no son artículos)
        self.parrafo_num_pattern = re.compile(
            r'^[\s]*(\d+)[\s]*[\.\)][\s]+(?!.*(?:ART[ÍI]CULO|CAP[ÍI]TULO|T[ÍI]TULO))(.+)$',
            re.IGNORECASE | re.MULTILINE
        )

        # Transitorios
        self.transitorio_pattern = re.compile(
            r'^[\s]*(?:TRANSITORIOS?|ART[ÍI]CULOS?\s+TRANSITORIOS?)[\s]*$',
            re.IGNORECASE | re.MULTILINE
        )

    def format_legal_document(self, text: str) -> str:
        """
        Formatea un documento legal completo.

        Args:
            text: Texto del documento legal

        Returns:
            str: Documento formateado con estructura jerárquica
        """
        if not text:
            return text

        # Preprocesar texto
        text = self._preprocess_text(text)

        # Detectar y estructurar elementos
        lines = text.split('\n')
        formatted_lines = []
        current_context = {
            'in_articulo': False,
            'in_fraccion': False,
            'last_element': None
        }

        i = 0
        while i < len(lines):
            line = lines[i]
            original_line = line

            # Intentar detectar cada tipo de elemento
            element_type, formatted_line, context_update = self._detect_and_format_line(
                line, current_context
            )

            if element_type:
                formatted_lines.append(formatted_line)
                current_context.update(context_update)
            else:
                # Línea normal - aplicar indentación según contexto
                formatted_lines.append(self._format_plain_line(line, current_context))

            i += 1

        # Unir y limpiar resultado
        result = '\n'.join(formatted_lines)
        result = self._postprocess_text(result)

        return result

    def _preprocess_text(self, text: str) -> str:
        """Preprocesa el texto para facilitar detección."""
        # Normalizar saltos de línea
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # Normalizar espacios múltiples (pero preservar indentación)
        text = re.sub(r'[ \t]+', ' ', text)

        # Asegurar que títulos/capítulos/secciones estén en líneas separadas
        text = re.sub(
            r'([.;:])[\s]*(T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N|ART[ÍI]CULO)',
            r'\1\n\n\2',
            text,
            flags=re.IGNORECASE
        )

        return text

    def _detect_and_format_line(self, line: str, context: dict) -> Tuple[Optional[LegalElementType], str, dict]:
        """
        Detecta el tipo de elemento legal y lo formatea.

        Returns:
            Tuple de (tipo_elemento, línea_formateada, actualizaciones_contexto)
        """
        stripped = line.strip()
        if not stripped:
            return None, line, {}

        # Verificar cada patrón en orden de jerarquía

        # TÍTULO
        match = self.titulo_pattern.match(stripped)
        if match:
            number, title = match.groups()
            formatted = self._format_element(
                LegalElementType.TITULO, number.upper(), title
            )
            return LegalElementType.TITULO, formatted, {
                'in_articulo': False,
                'in_fraccion': False,
                'last_element': LegalElementType.TITULO
            }

        # CAPÍTULO
        match = self.capitulo_pattern.match(stripped)
        if match:
            number, title = match.groups()
            formatted = self._format_element(
                LegalElementType.CAPITULO, number.upper(), title
            )
            return LegalElementType.CAPITULO, formatted, {
                'in_articulo': False,
                'in_fraccion': False,
                'last_element': LegalElementType.CAPITULO
            }

        # SECCIÓN
        match = self.seccion_pattern.match(stripped)
        if match:
            number, title = match.groups()
            formatted = self._format_element(
                LegalElementType.SECCION, number.upper(), title
            )
            return LegalElementType.SECCION, formatted, {
                'in_articulo': False,
                'in_fraccion': False,
                'last_element': LegalElementType.SECCION
            }

        # TRANSITORIOS
        match = self.transitorio_pattern.match(stripped)
        if match:
            formatted = self._format_element(
                LegalElementType.TRANSITORIO, "", "TRANSITORIOS"
            )
            return LegalElementType.TRANSITORIO, formatted, {
                'in_articulo': False,
                'in_fraccion': False,
                'last_element': LegalElementType.TRANSITORIO
            }

        # ARTÍCULO
        match = self.articulo_pattern.match(stripped)
        if match:
            number, content = match.groups()
            formatted = self._format_element(
                LegalElementType.ARTICULO, number, content
            )
            return LegalElementType.ARTICULO, formatted, {
                'in_articulo': True,
                'in_fraccion': False,
                'last_element': LegalElementType.ARTICULO
            }

        # FRACCIÓN (solo si estamos en contexto de artículo)
        if context.get('in_articulo') or context.get('last_element') == LegalElementType.ARTICULO:
            match = self.fraccion_pattern.match(stripped)
            if match:
                number, content = match.groups()
                # Verificar que sea un número romano válido
                if self._is_valid_roman(number):
                    formatted = self._format_element(
                        LegalElementType.FRACCION, number.upper(), content
                    )
                    return LegalElementType.FRACCION, formatted, {
                        'in_articulo': True,
                        'in_fraccion': True,
                        'last_element': LegalElementType.FRACCION
                    }

        # INCISO (solo si estamos en contexto de fracción o artículo)
        if context.get('in_fraccion') or context.get('in_articulo'):
            match = self.inciso_pattern.match(stripped)
            if match:
                letter, content = match.groups()
                formatted = self._format_element(
                    LegalElementType.INCISO, letter.lower(), content
                )
                return LegalElementType.INCISO, formatted, {
                    'in_articulo': context.get('in_articulo', False),
                    'in_fraccion': context.get('in_fraccion', False),
                    'last_element': LegalElementType.INCISO
                }

        return None, line, {}

    def _format_element(self, element_type: LegalElementType, number: str, content: str) -> str:
        """Formatea un elemento legal según el estilo configurado."""
        content = content.strip()

        if self.style == "markdown":
            return self._format_markdown(element_type, number, content)
        elif self.style == "html":
            return self._format_html(element_type, number, content)
        else:
            return self._format_plain(element_type, number, content)

    def _format_markdown(self, element_type: LegalElementType, number: str, content: str) -> str:
        """Formatea elemento en estilo Markdown."""

        if element_type == LegalElementType.TITULO:
            title_text = f"TÍTULO {number}"
            if content:
                title_text += f": {content}"
            return f"\n# {title_text}\n"

        elif element_type == LegalElementType.CAPITULO:
            cap_text = f"CAPÍTULO {number}"
            if content:
                cap_text += f": {content}"
            return f"\n## {cap_text}\n"

        elif element_type == LegalElementType.SECCION:
            sec_text = f"Sección {number}"
            if content:
                sec_text += f": {content}"
            return f"\n### {sec_text}\n"

        elif element_type == LegalElementType.TRANSITORIO:
            return f"\n## TRANSITORIOS\n"

        elif element_type == LegalElementType.ARTICULO:
            art_text = f"**Artículo {number}.**"
            if content:
                art_text += f" {content}"
            return f"\n{art_text}"

        elif element_type == LegalElementType.FRACCION:
            return f"\n   **{number}.** {content}"

        elif element_type == LegalElementType.INCISO:
            return f"\n      *{number})* {content}"

        elif element_type == LegalElementType.PARRAFO:
            return f"\n{content}"

        return content

    def _format_html(self, element_type: LegalElementType, number: str, content: str) -> str:
        """Formatea elemento en estilo HTML."""

        if element_type == LegalElementType.TITULO:
            title_text = f"TÍTULO {number}"
            if content:
                title_text += f": {content}"
            return f'<h1 class="legal-titulo">{title_text}</h1>'

        elif element_type == LegalElementType.CAPITULO:
            cap_text = f"CAPÍTULO {number}"
            if content:
                cap_text += f": {content}"
            return f'<h2 class="legal-capitulo">{cap_text}</h2>'

        elif element_type == LegalElementType.SECCION:
            sec_text = f"Sección {number}"
            if content:
                sec_text += f": {content}"
            return f'<h3 class="legal-seccion">{sec_text}</h3>'

        elif element_type == LegalElementType.TRANSITORIO:
            return f'<h2 class="legal-transitorio">TRANSITORIOS</h2>'

        elif element_type == LegalElementType.ARTICULO:
            return f'<p class="legal-articulo"><strong>Artículo {number}.</strong> {content}</p>'

        elif element_type == LegalElementType.FRACCION:
            return f'<p class="legal-fraccion"><strong>{number}.</strong> {content}</p>'

        elif element_type == LegalElementType.INCISO:
            return f'<p class="legal-inciso"><em>{number})</em> {content}</p>'

        return f'<p>{content}</p>'

    def _format_plain(self, element_type: LegalElementType, number: str, content: str) -> str:
        """Formatea elemento en texto plano con indentación."""

        if element_type == LegalElementType.TITULO:
            title_text = f"TÍTULO {number}"
            if content:
                title_text += f": {content}"
            return f"\n{'='*60}\n{title_text}\n{'='*60}\n"

        elif element_type == LegalElementType.CAPITULO:
            cap_text = f"CAPÍTULO {number}"
            if content:
                cap_text += f": {content}"
            return f"\n{'-'*40}\n{cap_text}\n{'-'*40}\n"

        elif element_type == LegalElementType.SECCION:
            sec_text = f"Sección {number}"
            if content:
                sec_text += f": {content}"
            return f"\n{sec_text}\n"

        elif element_type == LegalElementType.TRANSITORIO:
            return f"\n{'='*40}\nTRANSITORIOS\n{'='*40}\n"

        elif element_type == LegalElementType.ARTICULO:
            return f"\nArtículo {number}. {content}"

        elif element_type == LegalElementType.FRACCION:
            return f"\n    {number}. {content}"

        elif element_type == LegalElementType.INCISO:
            return f"\n        {number}) {content}"

        return content

    def _format_plain_line(self, line: str, context: dict) -> str:
        """Formatea una línea sin elemento detectado, aplicando indentación según contexto."""
        stripped = line.strip()
        if not stripped:
            return ""

        # Aplicar indentación según el último elemento
        last = context.get('last_element')

        if self.style == "markdown":
            if context.get('in_fraccion'):
                return f"      {stripped}"
            elif context.get('in_articulo'):
                return f"   {stripped}"
            return stripped

        elif self.style == "plain":
            if context.get('in_fraccion'):
                return f"        {stripped}"
            elif context.get('in_articulo'):
                return f"    {stripped}"
            return stripped

        return stripped

    def _postprocess_text(self, text: str) -> str:
        """Limpia el texto formateado."""
        # Eliminar líneas vacías excesivas
        text = re.sub(r'\n{4,}', '\n\n\n', text)

        # Asegurar espacio antes de artículos
        text = re.sub(r'([^\n])\n(\*\*Artículo)', r'\1\n\n\2', text)

        return text.strip()

    def _is_valid_roman(self, text: str) -> bool:
        """Verifica si un texto es un número romano válido."""
        # Patrón para números romanos del I al CXXX (suficiente para fracciones)
        roman_pattern = r'^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$'
        return bool(re.match(roman_pattern, text.upper()))


class LegalTextOptimizer:
    """
    Optimizador especializado para textos legales.

    Combina el formateador de documentos legales con correcciones
    específicas para terminología jurídica.
    """

    def __init__(self, style: str = "markdown"):
        self.formatter = LegalDocumentFormatter(style=style)

        # Patrones de corrección específicos para textos legales
        self.legal_corrections = [
            # Abreviaturas comunes
            (r'\bArt\.\s*(\d+)', r'Artículo \1'),
            (r'\barts\.\s*', 'artículos '),
            (r'\bfrac\.\s*', 'fracción '),
            (r'\bfracs\.\s*', 'fracciones '),
            (r'\binc\.\s*', 'inciso '),
            (r'\bpárr\.\s*', 'párrafo '),

            # Términos legales mal reconocidos por OCR
            (r'\bIey\b', 'ley'),
            (r'\bdeI\b', 'del'),
            (r'\baI\b', 'al'),
            (r'\beI\b', 'el'),
            (r'\bIa\b', 'la'),
            (r'\bIos\b', 'los'),
            (r'\bIas\b', 'las'),

            # Números ordinales
            (r'\b(\d+)[oº]\b', r'\1°'),
            (r'\b(\d+)[aª]\b', r'\1ª'),

            # Espaciado en números de artículos
            (r'Artículo(\d+)', r'Artículo \1'),
            (r'artículo(\d+)', r'artículo \1'),
        ]

    def optimize(self, text: str) -> str:
        """
        Optimiza y estructura un texto legal.

        Args:
            text: Texto legal a optimizar

        Returns:
            str: Texto optimizado y estructurado
        """
        # Aplicar correcciones específicas de OCR legal
        for pattern, replacement in self.legal_corrections:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Aplicar formato estructurado
        text = self.formatter.format_legal_document(text)

        return text


def format_legal_text(text: str, style: str = "markdown") -> str:
    """
    Función de conveniencia para formatear texto legal.

    Args:
        text: Texto del documento legal
        style: Estilo de salida ("markdown", "plain", "html")

    Returns:
        str: Texto formateado
    """
    optimizer = LegalTextOptimizer(style=style)
    return optimizer.optimize(text)


# === PRUEBAS ===
if __name__ == "__main__":
    # Texto de ejemplo
    ejemplo = """
    TÍTULO PRIMERO
    Disposiciones Generales

    CAPÍTULO I
    Del Objeto y Ámbito de Aplicación

    Artículo 1. La presente Ley es de orden público e interés social y tiene por objeto:

    I. Regular las actividades contempladas en esta Ley;
    II. Establecer los principios y bases para:
        a) La coordinación entre autoridades;
        b) El fomento de las actividades productivas; y
        c) La protección del medio ambiente.
    III. Definir los procedimientos aplicables.

    Artículo 2. Para los efectos de esta Ley se entiende por:

    I. Autoridad competente: La dependencia o entidad de la Administración Pública Federal;
    II. Beneficiario: La persona física o moral que recibe los apoyos;
    III. Ley: La presente Ley.

    CAPÍTULO II
    De las Autoridades

    Sección Primera
    De la Secretaría

    Artículo 3. La Secretaría tendrá las siguientes atribuciones:

    I. Formular y conducir la política nacional en la materia;
    II. Coordinar las acciones con otras dependencias;
    III. Expedir las disposiciones reglamentarias correspondientes.

    TRANSITORIOS

    Artículo Primero. La presente Ley entrará en vigor al día siguiente de su publicación.

    Artículo Segundo. Se derogan todas las disposiciones que se opongan a esta Ley.
    """

    print("=" * 60)
    print("LEGAL DOCUMENT FORMATTER - PRUEBA")
    print("=" * 60)
    print()

    resultado = format_legal_text(ejemplo, style="markdown")
    print(resultado)
