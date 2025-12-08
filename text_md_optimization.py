#!/usr/bin/env python3
"""
Optimización de texto y markdown para documentos OCR.
Proporciona funcionalidad real de limpieza y mejora de texto.
"""

import re
from typing import Dict, List, Optional, Tuple


class TextOptimizer:
    """Optimizador de texto con correcciones comunes de OCR."""
    
    def __init__(self, domain="general", custom_rules=None, custom_replacements=None):
        self.domain = domain
        self.custom_rules = custom_rules or {}
        self.custom_replacements = custom_replacements or []
        
        # Patrones comunes de errores OCR
        self.ocr_corrections = {
            # Letras confundidas comúnmente
            r'\bl\b': 'I',  # l minúscula por I mayúscula
            r'\bO\b': '0',  # O por 0 en contextos numéricos
            r'(?<!\w)l(?=\d)': '1',  # l antes de números
            r'(?<=\d)O(?=\d)': '0',  # O entre números
            
            # Correcciones específicas por dominio
            'legal': {
                r'ARTiCULO': 'ARTÍCULO',
                r'CONSTlTUClON': 'CONSTITUCIÓN',
                r'lNCISO': 'INCISO',
                r'Parrafo': 'PÁRRAFO',
            },
            'general': {}
        }
    
    def optimize_text(self, text):
        """Optimiza el texto aplicando correcciones de OCR."""
        if not text:
            return text
            
        # Aplicar correcciones básicas
        optimized = self._fix_spacing(text)
        optimized = self._fix_punctuation(optimized)
        
        # Aplicar correcciones de dominio
        if self.domain in self.ocr_corrections:
            for pattern, replacement in self.ocr_corrections[self.domain].items():
                optimized = re.sub(pattern, replacement, optimized)
        
        # Aplicar reglas personalizadas
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


class MarkdownOptimizer(TextOptimizer):
    """Optimizador específico para markdown."""
    
    def optimize_markdown(self, markdown_text):
        """Optimiza markdown manteniendo su estructura."""
        if not markdown_text:
            return markdown_text
            
        lines = markdown_text.split('\n')
        optimized_lines = []
        
        for line in lines:
            # Preservar líneas de imagen
            if line.strip().startswith('!['):
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
        
        return '\n'.join(optimized_lines)


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