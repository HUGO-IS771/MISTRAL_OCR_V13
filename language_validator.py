#!/usr/bin/env python3
"""
Language Validator - Validación lingüística para correcciones OCR
Valida correcciones regex contra diccionario para evitar falsos positivos.

Versión: 1.0.0
"""

import re
import logging
from typing import Set, Dict, List, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ContextualCorrector:
    """
    Corrector contextual que valida correcciones OCR contra diccionario.

    Evita falsos positivos al verificar que las correcciones regex
    realmente mejoran la validez lingüística del texto.
    """

    def __init__(self, language="es", use_cache=True):
        """
        Inicializa el corrector contextual.

        Args:
            language: Código de idioma (por defecto "es" para español)
            use_cache: Si True, cachea palabras validadas para mejor rendimiento
        """
        self.language = language
        self.use_cache = use_cache

        # Cache de palabras válidas
        self._valid_words_cache: Set[str] = set()
        self._invalid_words_cache: Set[str] = set()

        # Diccionario de palabras comunes en español (fallback si no hay hunspell)
        self.common_spanish_words = self._load_common_spanish_words()

        # Intentar cargar hunspell si está disponible
        self.spellchecker = self._init_spellchecker()

        logger.info(f"ContextualCorrector inicializado (idioma: {language})")

    def _init_spellchecker(self):
        """Inicializa spellchecker con hunspell si está disponible."""
        try:
            from spellchecker import SpellChecker
            checker = SpellChecker(language=self.language)
            logger.info("✓ Spellchecker (pyspellchecker) cargado exitosamente")
            return checker
        except ImportError:
            logger.warning(
                "pyspellchecker no disponible. "
                "Instalar con: pip install pyspellchecker"
            )
            logger.info("Usando diccionario básico incorporado")
            return None

    def _load_common_spanish_words(self) -> Set[str]:
        """
        Carga conjunto de palabras comunes en español.

        Este es un fallback básico si no hay spellchecker disponible.
        """
        # Palabras españolas más comunes (frecuencia > 1000 en corpus)
        common_words = {
            # Artículos y preposiciones
            'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
            'de', 'del', 'a', 'al', 'en', 'con', 'por', 'para', 'sin', 'sobre',
            # Verbos comunes
            'es', 'son', 'está', 'están', 'hay', 'tiene', 'tienen', 'hace',
            'ser', 'estar', 'haber', 'tener', 'hacer', 'poder', 'decir',
            'ir', 'ver', 'dar', 'saber', 'querer', 'llegar', 'pasar',
            # Pronombres
            'yo', 'tú', 'él', 'ella', 'nosotros', 'vosotros', 'ellos', 'ellas',
            'me', 'te', 'se', 'nos', 'os', 'le', 'lo', 'la',
            'mi', 'tu', 'su', 'nuestro', 'vuestro',
            'este', 'ese', 'aquel', 'esta', 'esa', 'aquella',
            # Sustantivos comunes
            'persona', 'año', 'día', 'tiempo', 'caso', 'parte', 'forma',
            'problema', 'mano', 'lugar', 'país', 'momento', 'vez', 'vida',
            'mundo', 'hombre', 'mujer', 'hijo', 'casa', 'trabajo',
            # Adjetivos comunes
            'grande', 'pequeño', 'bueno', 'malo', 'nuevo', 'viejo',
            'primero', 'último', 'otro', 'mismo', 'todo', 'alguno', 'ninguno',
            # Adverbios
            'muy', 'más', 'menos', 'también', 'tampoco', 'siempre', 'nunca',
            'bien', 'mal', 'ahora', 'aquí', 'allí', 'después', 'antes',
            # Conjunciones
            'y', 'o', 'pero', 'porque', 'que', 'si', 'como', 'cuando',
            # Palabras técnicas comunes
            'artículo', 'página', 'número', 'documento', 'archivo', 'texto',
            'imagen', 'tabla', 'dato', 'información', 'sistema', 'proceso',
        }

        return common_words

    def is_valid_word(self, word: str) -> bool:
        """
        Verifica si una palabra es válida en el idioma.

        Args:
            word: Palabra a verificar

        Returns:
            bool: True si la palabra es válida
        """
        if not word or len(word) < 2:
            return False

        # Normalizar
        word_lower = word.lower()

        # Revisar cache primero
        if self.use_cache:
            if word_lower in self._valid_words_cache:
                return True
            if word_lower in self._invalid_words_cache:
                return False

        # Verificar con spellchecker si está disponible
        is_valid = False

        if self.spellchecker:
            # pyspellchecker considera válida si NO está en unknown
            is_valid = word_lower not in self.spellchecker.unknown([word_lower])
        else:
            # Fallback: usar diccionario básico
            is_valid = word_lower in self.common_spanish_words

        # Cachear resultado
        if self.use_cache:
            if is_valid:
                self._valid_words_cache.add(word_lower)
            else:
                self._invalid_words_cache.add(word_lower)

        return is_valid

    def should_apply_correction(
        self,
        original_word: str,
        pattern: str,
        replacement: str
    ) -> bool:
        """
        Determina si una corrección regex debe aplicarse.

        Valida que la corrección realmente mejore la validez lingüística.

        Args:
            original_word: Palabra original
            pattern: Patrón regex
            replacement: Reemplazo

        Returns:
            bool: True si la corrección debe aplicarse
        """
        # Aplicar corrección
        try:
            corrected_word = re.sub(pattern, replacement, original_word)
        except Exception as e:
            logger.warning(f"Error aplicando patrón '{pattern}': {e}")
            return False

        # Si no cambió nada, no aplicar
        if corrected_word == original_word:
            return False

        # Validar ambas palabras
        original_valid = self.is_valid_word(original_word)
        corrected_valid = self.is_valid_word(corrected_word)

        # Decisión:
        # 1. Si original es válida Y corregida es inválida → NO aplicar
        if original_valid and not corrected_valid:
            return False

        # 2. Si original es inválida Y corregida es válida → SÍ aplicar
        if not original_valid and corrected_valid:
            return True

        # 3. Si ambas inválidas → aplicar (puede ser nombre propio, tecnicismo, etc.)
        if not original_valid and not corrected_valid:
            return True

        # 4. Si ambas válidas → NO aplicar (preservar original)
        return False

    def correct_text_with_validation(
        self,
        text: str,
        patterns: List[Tuple[str, str]]
    ) -> Tuple[str, Dict]:
        """
        Aplica correcciones OCR con validación lingüística.

        Args:
            text: Texto a corregir
            patterns: Lista de tuplas (pattern, replacement)

        Returns:
            Tuple[str, Dict]: (texto_corregido, estadísticas)
        """
        corrected = text
        stats = {
            'total_patterns': len(patterns),
            'applied': 0,
            'skipped': 0,
            'corrections': []
        }

        for pattern, replacement in patterns:
            # Encontrar todas las palabras que coinciden con el patrón
            try:
                compiled_pattern = re.compile(pattern)
                matches = compiled_pattern.finditer(corrected)

                for match in reversed(list(matches)):  # Reverso para no afectar índices
                    original_word = match.group(0)

                    # Validar si debe aplicarse
                    if self.should_apply_correction(original_word, pattern, replacement):
                        corrected_word = re.sub(pattern, replacement, original_word)
                        start, end = match.span()

                        # Aplicar corrección
                        corrected = corrected[:start] + corrected_word + corrected[end:]

                        # Registrar
                        stats['applied'] += 1
                        stats['corrections'].append({
                            'original': original_word,
                            'corrected': corrected_word,
                            'pattern': pattern,
                            'position': start
                        })
                    else:
                        stats['skipped'] += 1

            except Exception as e:
                logger.warning(f"Error procesando patrón '{pattern}': {e}")
                continue

        return corrected, stats

    def get_cache_stats(self) -> Dict:
        """Retorna estadísticas del cache."""
        return {
            'valid_words_cached': len(self._valid_words_cache),
            'invalid_words_cached': len(self._invalid_words_cache),
            'total_cached': len(self._valid_words_cache) + len(self._invalid_words_cache)
        }

    def clear_cache(self):
        """Limpia el cache de palabras."""
        self._valid_words_cache.clear()
        self._invalid_words_cache.clear()
        logger.info("Cache de palabras limpiado")


def validate_correction(word: str, pattern: str, replacement: str, language="es") -> bool:
    """
    Función de conveniencia para validar una corrección.

    Args:
        word: Palabra original
        pattern: Patrón regex
        replacement: Reemplazo
        language: Código de idioma

    Returns:
        bool: True si debe aplicarse la corrección
    """
    corrector = ContextualCorrector(language=language)
    return corrector.should_apply_correction(word, pattern, replacement)


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

    # Crear corrector
    corrector = ContextualCorrector(language="es")

    # Probar validación de palabras
    test_words = ["casa", "rn", "docurnento", "México", "ARTiCULO", "zxqwf"]

    print("=== VALIDACIÓN DE PALABRAS ===")
    for word in test_words:
        is_valid = corrector.is_valid_word(word)
        status = "✓ VÁLIDA" if is_valid else "✗ INVÁLIDA"
        print(f"{word:15} → {status}")

    print("\n=== VALIDACIÓN DE CORRECCIONES ===")
    test_corrections = [
        ("rn", r'\brn\b', 'm'),           # "rn" → "m" (OCR error común)
        ("casa", r'casa', 'c4sa'),        # "casa" → "c4sa" (empeora)
        ("docurnento", r'rn', 'm'),       # "docurnento" → "documento" (mejora)
        ("el", r'el', 'eI'),              # "el" → "eI" (empeora)
    ]

    for word, pattern, replacement in test_corrections:
        should_apply = corrector.should_apply_correction(word, pattern, replacement)
        corrected = re.sub(pattern, replacement, word)
        status = "✓ APLICAR" if should_apply else "✗ OMITIR"
        print(f"{word:15} → {corrected:15} | {status}")

    # Mostrar estadísticas del cache
    print("\n=== ESTADÍSTICAS DEL CACHE ===")
    cache_stats = corrector.get_cache_stats()
    print(f"Palabras válidas cacheadas: {cache_stats['valid_words_cached']}")
    print(f"Palabras inválidas cacheadas: {cache_stats['invalid_words_cached']}")
    print(f"Total en cache: {cache_stats['total_cached']}")
