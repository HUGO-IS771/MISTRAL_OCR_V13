#!/usr/bin/env python3
"""
Table Detector - Detección y preservación de tablas en texto OCR
Identifica estructuras tabulares y las convierte a formato markdown.

Versión: 1.0.0
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TableRegion:
    """Representa una región tabular detectada."""
    start_line: int
    end_line: int
    rows: int
    cols: int
    content: List[List[str]]  # Matriz de celdas
    confidence: float  # 0-1
    separator_chars: str  # Caracteres separadores detectados


class TableDetector:
    """
    Detector de tablas en texto OCR.

    Utiliza heurísticas para identificar estructuras tabulares en texto
    extraído por OCR y las convierte a tablas markdown.
    """

    # Caracteres que indican separadores de tabla
    TABLE_CHARS = {
        'vertical': set('|│┃┆┇┊┋'),
        'horizontal': set('─━═-_'),
        'corners': set('┌┐└┘╔╗╚╝╭╮╰╯'),
        'crosses': set('├┤┬┴┼╠╣╦╩╬'),
    }

    # Caracteres de tabla combinados
    ALL_TABLE_CHARS = set().union(*TABLE_CHARS.values())

    def __init__(self, min_confidence=0.6):
        """
        Inicializa el detector de tablas.

        Args:
            min_confidence: Confianza mínima para considerar una tabla (0-1)
        """
        self.min_confidence = min_confidence
        logger.info(f"TableDetector inicializado (confianza mínima: {min_confidence})")

    def detect_tables(self, text: str) -> List[TableRegion]:
        """
        Detecta todas las tablas en el texto.

        Args:
            text: Texto a analizar

        Returns:
            List[TableRegion]: Lista de tablas detectadas
        """
        if not text or not text.strip():
            return []

        lines = text.splitlines()
        tables = []
        i = 0

        while i < len(lines):
            # Intentar detectar inicio de tabla
            table = self._try_detect_table_from_line(lines, i)

            if table and table.confidence >= self.min_confidence:
                tables.append(table)
                i = table.end_line + 1  # Saltar líneas de la tabla
            else:
                i += 1

        logger.info(f"Detectadas {len(tables)} tablas")
        return tables

    def _try_detect_table_from_line(self, lines: List[str], start_idx: int) -> Optional[TableRegion]:
        """
        Intenta detectar una tabla comenzando desde una línea específica.

        Args:
            lines: Lista de líneas del texto
            start_idx: Índice de línea inicial

        Returns:
            Optional[TableRegion]: Tabla detectada o None
        """
        if start_idx >= len(lines):
            return None

        # Verificar si la línea parece inicio de tabla
        if not self._is_table_like_line(lines[start_idx]):
            return None

        # Expandir región tabular
        end_idx = self._find_table_end(lines, start_idx)

        if end_idx - start_idx < 2:  # Mínimo 2 líneas para ser tabla
            return None

        # Extraer líneas de la tabla
        table_lines = lines[start_idx:end_idx + 1]

        # Parsear tabla
        cells_matrix, separator_char = self._parse_table_lines(table_lines)

        if not cells_matrix or len(cells_matrix) < 2:
            return None

        # Calcular dimensiones
        rows = len(cells_matrix)
        cols = max(len(row) for row in cells_matrix) if cells_matrix else 0

        # Calcular confianza
        confidence = self._calculate_confidence(table_lines, cells_matrix, separator_char)

        return TableRegion(
            start_line=start_idx,
            end_line=end_idx,
            rows=rows,
            cols=cols,
            content=cells_matrix,
            confidence=confidence,
            separator_chars=separator_char
        )

    def _is_table_like_line(self, line: str) -> bool:
        """
        Determina si una línea parece parte de una tabla.

        Heurísticas:
        - Tiene separadores verticales (|, │, etc.)
        - Tiene caracteres de tabla
        - Tiene espaciado consistente
        """
        if not line or not line.strip():
            return False

        # Contar caracteres de tabla
        table_char_count = sum(1 for c in line if c in self.ALL_TABLE_CHARS)

        # Debe tener al menos 2 caracteres de tabla
        if table_char_count < 2:
            return False

        # Debe tener separadores verticales O ser línea de separación horizontal
        has_vertical = any(c in self.TABLE_CHARS['vertical'] for c in line)
        has_horizontal = any(c in self.TABLE_CHARS['horizontal'] for c in line)

        return has_vertical or (has_horizontal and table_char_count >= 5)

    def _find_table_end(self, lines: List[str], start_idx: int) -> int:
        """
        Encuentra el índice de la última línea de la tabla.

        Args:
            lines: Lista de líneas
            start_idx: Índice de inicio

        Returns:
            int: Índice de línea final
        """
        end_idx = start_idx

        for i in range(start_idx + 1, len(lines)):
            if self._is_table_like_line(lines[i]):
                end_idx = i
            else:
                # Si hay línea vacía, puede ser fin de tabla
                if not lines[i].strip():
                    break
                # Si hay 2 líneas consecutivas sin formato tabla, terminar
                if i > start_idx + 1 and not self._is_table_like_line(lines[i - 1]):
                    end_idx = i - 2
                    break

        return end_idx

    def _parse_table_lines(self, table_lines: List[str]) -> Tuple[List[List[str]], str]:
        """
        Parsea líneas de tabla a matriz de celdas.

        Args:
            table_lines: Líneas que componen la tabla

        Returns:
            Tuple[List[List[str]], str]: (matriz_celdas, separador_usado)
        """
        # Detectar separador principal
        separator = self._detect_main_separator(table_lines)

        # Filtrar líneas de separación horizontal (solo decoración)
        content_lines = []
        for line in table_lines:
            # Líneas con solo caracteres horizontales/esquinas son decoración
            stripped = line.strip()
            if stripped and not all(c in self.TABLE_CHARS['horizontal'] | self.TABLE_CHARS['corners'] | self.TABLE_CHARS['crosses'] | {' '} for c in stripped):
                content_lines.append(line)

        # Parsear cada línea en celdas
        cells_matrix = []
        for line in content_lines:
            cells = self._split_line_by_separator(line, separator)
            if cells:  # Solo agregar si hay celdas válidas
                cells_matrix.append(cells)

        return cells_matrix, separator

    def _detect_main_separator(self, lines: List[str]) -> str:
        """
        Detecta el carácter separador principal de columnas.

        Args:
            lines: Líneas de la tabla

        Returns:
            str: Carácter separador más común
        """
        separator_counts = {}

        for line in lines:
            for char in self.TABLE_CHARS['vertical']:
                count = line.count(char)
                separator_counts[char] = separator_counts.get(char, 0) + count

        if not separator_counts:
            return '|'  # Fallback

        # Retornar el más común
        return max(separator_counts, key=separator_counts.get)

    def _split_line_by_separator(self, line: str, separator: str) -> List[str]:
        """
        Divide una línea en celdas usando el separador.

        Args:
            line: Línea a dividir
            separator: Carácter separador

        Returns:
            List[str]: Lista de celdas (limpiadas)
        """
        # Dividir por separador
        parts = line.split(separator)

        # Limpiar celdas (eliminar espacios)
        cells = []
        for part in parts:
            cleaned = part.strip()
            # Solo agregar si no está vacía O si es entre separadores
            if cleaned or (len(parts) > 2 and part == parts[0]):  # Primera/última pueden ser vacías
                cells.append(cleaned)

        # Remover primera/última si están vacías (separadores al inicio/fin)
        if cells and not cells[0]:
            cells = cells[1:]
        if cells and not cells[-1]:
            cells = cells[:-1]

        return cells

    def _calculate_confidence(
        self,
        table_lines: List[str],
        cells_matrix: List[List[str]],
        separator: str
    ) -> float:
        """
        Calcula confianza de que es una tabla real.

        Factores:
        - Consistencia de número de columnas
        - Presencia de separadores
        - Ratio de caracteres de tabla
        """
        if not table_lines or not cells_matrix:
            return 0.0

        confidence = 0.0

        # Factor 1: Consistencia de columnas (40% peso)
        col_counts = [len(row) for row in cells_matrix]
        if col_counts:
            most_common_cols = max(set(col_counts), key=col_counts.count)
            consistency = col_counts.count(most_common_cols) / len(col_counts)
            confidence += consistency * 0.4

        # Factor 2: Presencia de separadores (30% peso)
        total_chars = sum(len(line) for line in table_lines)
        separator_chars = sum(line.count(separator) for line in table_lines)
        if total_chars > 0:
            separator_ratio = min(1.0, separator_chars / (total_chars * 0.1))  # 10% o más es bueno
            confidence += separator_ratio * 0.3

        # Factor 3: Mínimo de filas y columnas (30% peso)
        has_min_structure = len(cells_matrix) >= 2 and most_common_cols >= 2
        confidence += (1.0 if has_min_structure else 0.0) * 0.3

        return min(1.0, max(0.0, confidence))

    def to_markdown_table(self, table: TableRegion) -> str:
        """
        Convierte una tabla detectada a formato markdown.

        Args:
            table: Región tabular

        Returns:
            str: Tabla en formato markdown
        """
        if not table.content or table.rows < 1:
            return ""

        lines = []

        # Normalizar número de columnas (rellenar con vacíos)
        max_cols = table.cols
        normalized_content = []
        for row in table.content:
            normalized_row = list(row)
            while len(normalized_row) < max_cols:
                normalized_row.append("")
            normalized_content.append(normalized_row[:max_cols])  # Truncar si excede

        # Primera fila (header)
        if normalized_content:
            header = normalized_content[0]
            lines.append("| " + " | ".join(header) + " |")

            # Línea separadora
            lines.append("| " + " | ".join(["---"] * max_cols) + " |")

            # Filas de datos
            for row in normalized_content[1:]:
                lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def extract_and_convert_tables(self, text: str) -> Tuple[str, List[Dict]]:
        """
        Extrae tablas y retorna texto con tablas en markdown.

        Args:
            text: Texto original

        Returns:
            Tuple[str, List[Dict]]: (texto_con_tablas_markdown, info_tablas)
        """
        tables = self.detect_tables(text)

        if not tables:
            return text, []

        lines = text.splitlines()
        result_lines = []
        table_info = []
        last_processed = 0

        for table in sorted(tables, key=lambda t: t.start_line):
            # Agregar líneas antes de la tabla
            result_lines.extend(lines[last_processed:table.start_line])

            # Convertir tabla a markdown
            markdown_table = self.to_markdown_table(table)
            result_lines.append("\n" + markdown_table + "\n")

            # Guardar info
            table_info.append({
                'start_line': table.start_line,
                'end_line': table.end_line,
                'rows': table.rows,
                'cols': table.cols,
                'confidence': table.confidence
            })

            last_processed = table.end_line + 1

        # Agregar líneas restantes
        result_lines.extend(lines[last_processed:])

        return "\n".join(result_lines), table_info


def detect_and_convert_tables(text: str, min_confidence=0.6) -> Tuple[str, List[Dict]]:
    """
    Función de conveniencia para detectar y convertir tablas.

    Args:
        text: Texto a procesar
        min_confidence: Confianza mínima

    Returns:
        Tuple[str, List[Dict]]: (texto_con_tablas, info_tablas)
    """
    detector = TableDetector(min_confidence=min_confidence)
    return detector.extract_and_convert_tables(text)


if __name__ == "__main__":
    # Ejemplo de uso
    import sys
    import io

    # Configurar salida UTF-8 para Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Texto de prueba con tabla
    test_text = """
    Este es un documento con una tabla.

    | Nombre    | Edad | Ciudad       |
    |-----------|------|--------------|
    | Juan      | 25   | Madrid       |
    | María     | 30   | Barcelona    |
    | Pedro     | 28   | Valencia     |

    Y aquí continúa el texto normal después de la tabla.

    Otra tabla con formato diferente:

    ┌───────────┬──────┬──────────────┐
    │ Producto  │ Cant │ Precio       │
    ├───────────┼──────┼──────────────┤
    │ Manzanas  │ 10   │ $5.00        │
    │ Peras     │ 15   │ $7.50        │
    └───────────┴──────┴──────────────┘

    Fin del documento.
    """

    detector = TableDetector(min_confidence=0.5)

    print("=== DETECCIÓN DE TABLAS ===")
    tables = detector.detect_tables(test_text)

    for i, table in enumerate(tables, 1):
        print(f"\nTabla {i}:")
        print(f"  Líneas: {table.start_line} - {table.end_line}")
        print(f"  Dimensiones: {table.rows} filas × {table.cols} columnas")
        print(f"  Confianza: {table.confidence:.2%}")
        print(f"  Separador: '{table.separator_chars}'")

    print("\n=== CONVERSIÓN A MARKDOWN ===")
    converted_text, info = detector.extract_and_convert_tables(test_text)
    print(converted_text)

    print(f"\n=== RESUMEN ===")
    print(f"Tablas procesadas: {len(info)}")
