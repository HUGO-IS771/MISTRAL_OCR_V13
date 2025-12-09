#!/usr/bin/env python3
"""
OCR Quality Metrics - Sistema de métricas para evaluar calidad de OCR
Proporciona análisis de calidad del texto extraído y optimizado.

Versión: 1.0.0
"""

import re
import logging
from typing import Dict, List, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


class QualityScorer:
    """
    Evaluador de calidad de texto OCR.

    Analiza el texto extraído por OCR y calcula métricas de calidad
    basadas en heurísticas que detectan errores comunes.
    """

    # Caracteres especiales raros que suelen indicar errores OCR
    RARE_CHARS = set('¦§¢£µ¶ªº¿¡')

    # Patrones sospechosos comunes en errores OCR
    SUSPICIOUS_PATTERNS = [
        r'\brn\b',      # "rn" que debería ser "m"
        r'\bcl\b',      # "cl" que debería ser "d"
        r'\bvv\b',      # "vv" que debería ser "w"
        r'\bii\b',      # "ii" que debería ser "ll"
        r'\bIl\b',      # "Il" que debería ser "ll"
        r'\blI\b',      # "lI" que debería ser "ll"
        r'(?<=[a-z])I(?=[a-z])',  # I minúscula entre letras minúsculas
        r'(?<=[A-Z])l(?=[A-Z])',  # l minúscula entre mayúsculas
    ]

    def __init__(self):
        """Inicializa el evaluador de calidad."""
        self.compiled_patterns = [re.compile(p) for p in self.SUSPICIOUS_PATTERNS]

    def calculate_quality_score(self, text: str) -> Dict:
        """
        Calcula el score de calidad del texto OCR.

        Args:
            text: Texto a analizar

        Returns:
            Dict con métricas de calidad:
            {
                'score': float (0-100),  # Score general de calidad
                'suspicious_patterns': int,  # Conteo de patrones sospechosos
                'rare_chars_count': int,  # Caracteres raros encontrados
                'rare_chars_ratio': float,  # Ratio de caracteres raros
                'avg_word_length': float,  # Longitud promedio de palabras
                'mixed_alphanum_words': int,  # Palabras con letras y números mezclados
                'mixed_alphanum_ratio': float,  # Ratio de palabras alfanuméricas
                'total_words': int,  # Total de palabras analizadas
                'total_chars': int,  # Total de caracteres
                'issues': List[str]  # Lista de problemas detectados
            }
        """
        if not text or not text.strip():
            return self._empty_score()

        # Extraer palabras (alfanuméricas)
        words = re.findall(r'\b\w+\b', text)
        total_words = len(words)
        total_chars = len(text)

        if total_words == 0:
            return self._empty_score()

        # Métricas individuales
        suspicious_count = self._count_suspicious_patterns(text)
        rare_chars_count = self._count_rare_chars(text)
        rare_chars_ratio = rare_chars_count / total_chars if total_chars > 0 else 0

        avg_word_length = sum(len(w) for w in words) / total_words
        mixed_alphanum_words = self._count_mixed_alphanum(words)
        mixed_alphanum_ratio = mixed_alphanum_words / total_words

        # Detectar problemas específicos
        issues = self._detect_issues(
            suspicious_count,
            rare_chars_count,
            rare_chars_ratio,
            avg_word_length,
            mixed_alphanum_ratio
        )

        # Calcular score general (0-100)
        score = self._calculate_overall_score(
            suspicious_count,
            rare_chars_ratio,
            mixed_alphanum_ratio,
            avg_word_length,
            total_words
        )

        return {
            'score': round(score, 2),
            'suspicious_patterns': suspicious_count,
            'rare_chars_count': rare_chars_count,
            'rare_chars_ratio': round(rare_chars_ratio, 4),
            'avg_word_length': round(avg_word_length, 2),
            'mixed_alphanum_words': mixed_alphanum_words,
            'mixed_alphanum_ratio': round(mixed_alphanum_ratio, 4),
            'total_words': total_words,
            'total_chars': total_chars,
            'issues': issues
        }

    def _count_suspicious_patterns(self, text: str) -> int:
        """Cuenta ocurrencias de patrones sospechosos."""
        count = 0
        for pattern in self.compiled_patterns:
            matches = pattern.findall(text)
            count += len(matches)
        return count

    def _count_rare_chars(self, text: str) -> int:
        """Cuenta caracteres raros que indican errores OCR."""
        return sum(1 for char in text if char in self.RARE_CHARS)

    def _count_mixed_alphanum(self, words: List[str]) -> int:
        """Cuenta palabras con letras y números mezclados (no IDs)."""
        mixed_count = 0
        for word in words:
            has_letter = any(c.isalpha() for c in word)
            has_digit = any(c.isdigit() for c in word)

            # Considerar mezclado solo si tiene ambos Y no es un patrón común
            if has_letter and has_digit:
                # Excluir patrones válidos como "2do", "3ra", "123abc"
                if not re.match(r'^\d+[a-z]{1,3}$', word.lower()):
                    mixed_count += 1

        return mixed_count

    def _calculate_overall_score(
        self,
        suspicious_count: int,
        rare_chars_ratio: float,
        mixed_alphanum_ratio: float,
        avg_word_length: float,
        total_words: int
    ) -> float:
        """
        Calcula score general de calidad (0-100).

        Score más alto = mejor calidad
        """
        score = 100.0

        # Penalizar patrones sospechosos (hasta -30 puntos)
        suspicious_penalty = min(30, (suspicious_count / max(total_words, 1)) * 100)
        score -= suspicious_penalty

        # Penalizar caracteres raros (hasta -20 puntos)
        rare_chars_penalty = min(20, rare_chars_ratio * 1000)
        score -= rare_chars_penalty

        # Penalizar palabras alfanuméricas mezcladas (hasta -20 puntos)
        mixed_penalty = min(20, mixed_alphanum_ratio * 50)
        score -= mixed_penalty

        # Penalizar longitud promedio anormal (hasta -15 puntos)
        # Longitud ideal: 4-8 caracteres
        if avg_word_length < 3 or avg_word_length > 10:
            length_penalty = min(15, abs(avg_word_length - 6) * 3)
            score -= length_penalty

        # Penalizar documentos muy cortos (menos confiables)
        if total_words < 10:
            score -= 15

        return max(0, min(100, score))

    def _detect_issues(
        self,
        suspicious_count: int,
        rare_chars_count: int,
        rare_chars_ratio: float,
        avg_word_length: float,
        mixed_alphanum_ratio: float
    ) -> List[str]:
        """Detecta y describe problemas de calidad."""
        issues = []

        if suspicious_count > 5:
            issues.append(f"Alto número de patrones sospechosos ({suspicious_count})")

        if rare_chars_count > 10:
            issues.append(f"Muchos caracteres raros encontrados ({rare_chars_count})")

        if rare_chars_ratio > 0.01:  # >1% de caracteres raros
            issues.append(f"Ratio elevado de caracteres raros ({rare_chars_ratio:.2%})")

        if avg_word_length < 3:
            issues.append(f"Palabras muy cortas en promedio ({avg_word_length:.1f} chars)")
        elif avg_word_length > 10:
            issues.append(f"Palabras muy largas en promedio ({avg_word_length:.1f} chars)")

        if mixed_alphanum_ratio > 0.1:  # >10% de palabras mezcladas
            issues.append(f"Muchas palabras con letras y números mezclados ({mixed_alphanum_ratio:.1%})")

        if not issues:
            issues.append("Sin problemas detectados")

        return issues

    def _empty_score(self) -> Dict:
        """Retorna score vacío para texto inválido."""
        return {
            'score': 0.0,
            'suspicious_patterns': 0,
            'rare_chars_count': 0,
            'rare_chars_ratio': 0.0,
            'avg_word_length': 0.0,
            'mixed_alphanum_words': 0,
            'mixed_alphanum_ratio': 0.0,
            'total_words': 0,
            'total_chars': 0,
            'issues': ['Texto vacío o inválido']
        }

    def compare_quality(self, original_text: str, optimized_text: str) -> Dict:
        """
        Compara calidad entre texto original y optimizado.

        Args:
            original_text: Texto OCR original
            optimized_text: Texto después de optimización

        Returns:
            Dict con comparación:
            {
                'original': Dict,  # Métricas del original
                'optimized': Dict,  # Métricas del optimizado
                'improvement': float,  # Mejora en score (%)
                'summary': str  # Resumen de la mejora
            }
        """
        original_metrics = self.calculate_quality_score(original_text)
        optimized_metrics = self.calculate_quality_score(optimized_text)

        improvement = optimized_metrics['score'] - original_metrics['score']
        improvement_pct = (improvement / max(original_metrics['score'], 1)) * 100

        # Generar resumen
        if improvement > 5:
            summary = f"✓ Mejora significativa: +{improvement:.1f} puntos ({improvement_pct:+.1f}%)"
        elif improvement > 0:
            summary = f"✓ Mejora leve: +{improvement:.1f} puntos ({improvement_pct:+.1f}%)"
        elif improvement < -5:
            summary = f"⚠ Empeoramiento: {improvement:.1f} puntos ({improvement_pct:.1f}%)"
        else:
            summary = f"→ Sin cambios significativos ({improvement:.1f} puntos)"

        return {
            'original': original_metrics,
            'optimized': optimized_metrics,
            'improvement': round(improvement, 2),
            'improvement_pct': round(improvement_pct, 2),
            'summary': summary
        }

    def generate_report(self, metrics: Dict) -> str:
        """
        Genera reporte legible de métricas.

        Args:
            metrics: Diccionario de métricas

        Returns:
            str: Reporte formateado
        """
        lines = []
        lines.append("=== REPORTE DE CALIDAD OCR ===")
        lines.append(f"Score General: {metrics['score']:.1f}/100")
        lines.append(f"Palabras analizadas: {metrics['total_words']}")
        lines.append(f"Caracteres totales: {metrics['total_chars']}")
        lines.append("")
        lines.append("Métricas Detalladas:")
        lines.append(f"  - Patrones sospechosos: {metrics['suspicious_patterns']}")
        lines.append(f"  - Caracteres raros: {metrics['rare_chars_count']} ({metrics['rare_chars_ratio']:.2%})")
        lines.append(f"  - Longitud promedio palabra: {metrics['avg_word_length']:.2f}")
        lines.append(f"  - Palabras alfanuméricas: {metrics['mixed_alphanum_words']} ({metrics['mixed_alphanum_ratio']:.2%})")
        lines.append("")
        lines.append("Problemas Detectados:")
        for issue in metrics['issues']:
            lines.append(f"  • {issue}")

        return "\n".join(lines)


def analyze_text_quality(text: str) -> Dict:
    """
    Función de conveniencia para analizar calidad de texto.

    Args:
        text: Texto a analizar

    Returns:
        Dict con métricas de calidad
    """
    scorer = QualityScorer()
    return scorer.calculate_quality_score(text)


def compare_texts(original: str, optimized: str) -> Dict:
    """
    Función de conveniencia para comparar textos.

    Args:
        original: Texto original
        optimized: Texto optimizado

    Returns:
        Dict con comparación
    """
    scorer = QualityScorer()
    return scorer.compare_quality(original, optimized)


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

    # Texto de prueba con errores OCR típicos
    test_text_bad = """
    El articulo 123 dice que eI texto debe ser legible.
    Pero este docurnento tiene rnuchos errores OCR.
    Las letras Il y rn están rnal reconocidas.
    Tambi¦n hay caracteres raros como ¢ y §.
    """

    test_text_good = """
    El artículo 123 dice que el texto debe ser legible.
    Este documento tiene pocos errores OCR.
    Las letras están bien reconocidas.
    No hay caracteres raros.
    """

    scorer = QualityScorer()

    print("=== ANÁLISIS DE TEXTO CON ERRORES ===")
    bad_metrics = scorer.calculate_quality_score(test_text_bad)
    print(scorer.generate_report(bad_metrics))

    print("\n=== ANÁLISIS DE TEXTO LIMPIO ===")
    good_metrics = scorer.calculate_quality_score(test_text_good)
    print(scorer.generate_report(good_metrics))

    print("\n=== COMPARACIÓN ===")
    comparison = scorer.compare_quality(test_text_bad, test_text_good)
    print(comparison['summary'])
