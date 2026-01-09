#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legal Document Formatter - Versión Optimizada (Port de Corrector Engine v4.0)
Logica robusta para estructurar documentos legales y artículos.
"""

import re
import logging
import unicodedata
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Any
from enum import Enum, auto

logger = logging.getLogger('mistral_ocr.legal_formatter')

def _formatear_parrafos(texto: str) -> str:
    """
    Formatea el texto para mejorar legibilidad:
    - Separa párrafos con líneas en blanco
    - Asegura espaciado visual antes/después de reformas
    - Limpia espacios múltiples
    - Respeta separadores existentes (---)
    """
    if not texto:
        return ""

    # 1. Limpieza inicial
    texto = texto.replace('\r\n', '\n')
    texto = re.sub(r'[ \t]+', ' ', texto)

    # 2. PROTEGER SEPARADORES EXISTENTES (---)
    # Reemplazar temporalmente separadores para protegerlos
    separadores_protegidos = {}
    contador_sep = 0
    
    def proteger_separador(match):
        nonlocal contador_sep
        placeholder = f"<<<SEPARADOR_{contador_sep}>>>"
        separadores_protegidos[placeholder] = match.group(0)
        contador_sep += 1
        return placeholder
    
    # Proteger líneas que son solo separadores (---)
    texto = re.sub(r'^---+$', proteger_separador, texto, flags=re.MULTILINE)

    # 3. ESPACIADO DE REFORMAS (Líneas con *...*)
    # ESPACIO ANTES de línea con reforma (si no existe ya)
    # Solo aplicar si NO hay ya una línea vacía antes
    texto = re.sub(r'([^\n])\n(\*[^\n]+\*)', r'\1\n\n\2', texto)

    # ESPACIO DESPUÉS de línea con reforma
    # Solo aplicar si NO hay ya una línea vacía después
    texto = re.sub(r'(\*[^\n]+\*)\n(?!\n)(?!\*)', r'\1\n\n', texto)

    # 4. SEPARACIÓN DE PÁRRAFOS: Punto final + mayúscula = nuevo párrafo
    # SOLO si NO hay ya una línea vacía después del punto (evitar duplicación)
    # Proteger abreviaturas comunes
    texto = re.sub(
        r'(?<!Art\.)(?<!Art\s)(?<!Lic\.)(?<!Lic\s)(?<!Inc\.)(?<!Inc\s)(?<!Fracc\.)(?<!Fracc\s)'
        r'(?<!Núm\.)(?<!Núm\s)(?<!No\.)(?<!No\s)(?<!C\.P\.)(?<!C\.P\s)(?<!Sr\.)(?<!Sr\s)'
        r'(?<!Sra\.)(?<!Sra\s)(?<!Dr\.)(?<!Dr\s)(?<!Mtro\.)(?<!Mtro\s)(?<!Ing\.)(?<!Ing\s)'
        r'(?<!etc\.)(?<!etc\s)(?<!v\.g\.)(?<!v\.g\s)(?<!i\.e\.)(?<!i\.e\s)'
        r'\.(\s+)([A-ZÁÉÍÓÚÑ])(?!\n\n)',  # NO aplicar si ya hay \n\n después
        r'.\n\n\2',
        texto
    )

    # 5. SEPARACIÓN ADICIONAL: Punto y seguido sin espacio antes de mayúscula
    # SOLO si NO hay ya una línea vacía después (evitar duplicación)
    texto = re.sub(
        r'(?<!Art\.)(?<!Art\s)(?<!Lic\.)(?<!Lic\s)(?<!Inc\.)(?<!Inc\s)(?<!Fracc\.)(?<!Fracc\s)'
        r'(?<!Núm\.)(?<!Núm\s)(?<!No\.)(?<!No\s)(?<!C\.P\.)(?<!C\.P\s)(?<!Sr\.)(?<!Sr\s)'
        r'(?<!Sra\.)(?<!Sra\s)(?<!Dr\.)(?<!Dr\s)(?<!Mtro\.)(?<!Mtro\s)(?<!Ing\.)(?<!Ing\s)'
        r'(?<!etc\.)(?<!etc\s)(?<!v\.g\.)(?<!v\.g\s)(?<!i\.e\.)(?<!i\.e\s)'
        r'\.([A-ZÁÉÍÓÚÑ])(?!\n\n)',  # NO aplicar si ya hay \n\n después
        r'.\n\n\1',
        texto
    )

    # 6. RESTAURAR SEPARADORES PROTEGIDOS
    for placeholder, separador in separadores_protegidos.items():
        texto = texto.replace(placeholder, separador)

    # 7. Limpiar líneas vacías excesivas (máximo 2 consecutivas)
    # Pero preservar separadores ---
    texto = re.sub(r'(?<!-)\n{3,}(?!-)', '\n\n', texto)

    return texto.strip()

# ==============================
# TIPOS DE DATOS Y ESTRUCTURAS
# ==============================

@dataclass
class MarcadorReforma:
    """Representa una marca de reforma o derogación en texto legal."""
    tipo: str  # 'REFORMADO', 'DEROGADO', 'ADICIONADO', etc.
    texto_completo: str
    referencia_dof: Optional[str] = None

    def a_markdown(self) -> str:
        """Convierte a formato texto simple."""
        return f"{self.texto_completo}"

@dataclass
class Inciso:
    """Representa un inciso (subsección con letra)."""
    letra: str  # 'a', 'b', 'c', etc.
    contenido: str
    reformas: List[MarcadorReforma] = field(default_factory=list)

    def a_markdown(self, nivel: int = 4) -> str:
        """Convierte a formato (letra) contenido)."""
        resultado = f"{self.letra}) {_formatear_parrafos(self.contenido.strip())}"
        if self.reformas:
            resultado += "\n" + "\n".join(r.a_markdown() for r in self.reformas)
        return resultado

@dataclass
class Fraccion:
    """Representa una fracción (subdivisión con número romano)."""
    numero_romano: str  # 'I', 'II', 'III', etc.
    contenido: str
    incisos: List[Inciso] = field(default_factory=list)
    reformas: List[MarcadorReforma] = field(default_factory=list)

    def a_markdown(self, nivel: int = 3) -> str:
        """Convierte a formato (numero. contenido)."""
        resultado = f"{self.numero_romano}. {_formatear_parrafos(self.contenido.strip())}"

        if self.reformas:
            resultado += "\n" + "\n".join(r.a_markdown() for r in self.reformas)

        if self.incisos:
            resultado += "\n\n" + "\n\n".join(i.a_markdown(nivel + 1) for i in self.incisos)

        return resultado

@dataclass
class ArticuloLegal:
    """Representa un artículo legal completo con su estructura jerárquica."""
    numero: str
    numero_base: int
    sufijo: str = ""
    contenido_inicial: str = ""
    fracciones: List[Fraccion] = field(default_factory=list)
    reformas: List[MarcadorReforma] = field(default_factory=list)

    def a_markdown(self, nivel: int = 2, usar_separadores: bool = False) -> str:
        """
        Convierte a formato Markdown.
        Si usar_separadores es True, añade '---' antes del artículo.
        """
        prefix = ""
        if usar_separadores:
            prefix = "\n\n---\n\n"
        else:
            prefix = "\n\n"

        resultado = f"{prefix}**Artículo {self.numero}**. "
        
        if self.contenido_inicial.strip():
            resultado += f"{_formatear_parrafos(self.contenido_inicial.strip())}"

        if self.reformas:
            resultado += "\n" + "\n".join(r.a_markdown() for r in self.reformas)

        if self.fracciones:
            resultado += "\n\n" + "\n\n".join(f.a_markdown(nivel + 1) for f in self.fracciones)

        return resultado.rstrip() + "\n\n"

@dataclass
class EstadisticasProcesamientoDummy:
    """Estadísticas simples para compatibilidad con la lógica portada."""
    articulos_detectados: int = 0
    fracciones_detectadas: int = 0
    incisos_detectados: int = 0
    reformas_detectadas: int = 0
    estructura_legal_procesada: bool = False

# ==============================
# MOTOR DE PROCESAMIENTO
# ==============================

class ProcesadorEstructuraLegal:
    """Procesador especializado para estructurar documentos legales mexicanos."""

    def __init__(self):
        self._inicializar_patrones()
        self._tiene_separadores_existentes = False

    def _inicializar_patrones(self):
        """Inicializa todos los patrones de detección legal."""
        
        # Múltiples patrones para artículos
        # Múltiples patrones para artículos (ahora tolerantes a Markdown)
        # Se agrega ^[#*>\s]* para ignorar caracteres de formato Markdown al inicio
        self.patrones_articulo = [
            r'^[#*>\s]*Art[íi]culo\s+\d+[oº°]?\.?-?',
            r'^[#*>\s]*ART[ÍI]CULO\s+\d+[oº°]?\.?-?',
            r'^[#*>\s]*Art\.\s+\d+[oº°]?\.?-?',
            r'^[#*>\s]*ART\.\s+\d+[oº°]?\.?-?',
            r'^[#*>\s]*Articulo\s+\d+[oº°]?\.?-?',
            r'^[#*>\s]*ARTICULO\s+\d+[oº°]?\.?-?',
            r'^[#*>\s]*Art[íi]culo\s+\d+\.',
            r'^[#*>\s]*ART[ÍI]CULO\s+\d+\.',
            r'^[#*>\s]*Art[íi]culo\s+\d+:',
            r'^[#*>\s]*ART[ÍI]CULO\s+\d+:',
            r'^[#*>\s]*Art[íi]culo\s+\d+\)',
            r'^[#*>\s]*ART[ÍI]CULO\s+\d+\)',
            r'^[#*>\s]*Art[íi]culo\s+\d+\s*-',
            r'^[#*>\s]*ART[ÍI]CULO\s+\d+\s*-',
        ]

        # Múltiples patrones para fracciones
        self.patrones_fraccion = [
            r'^[#*>\s]*[IVXLCDM]+\.-',
            r'^[#*>\s]*[IVXLCDM]+\.',
            r'^[#*>\s]*[IVXLCDM]+\)',
            r'^[#*>\s]*[IVXLCDM]+\s*-',
            r'^[#*>\s]*[IVXLCDM]+:',
            r'^[#*>\s]*[IVXLCDM]+\s+\.-',
            r'^[#*>\s]*[IVXLCDM]+\s+\.',
            r'^[#*>\s]*\([IVXLCDM]+\)',
            r'^[#*>\s]*Inciso\s+[IVXLCDM]+',
            r'^[#*>\s]*Fracción\s+[IVXLCDM]+',
            r'^[#*>\s]*FRACCIÓN\s+[IVXLCDM]+',
        ]

        # Múltiples patrones para incisos (Estrictos con word boundary artificial)
        # Se requiere que no haya palabra previa pegada para evitar falsos positivos
        self.patrones_inciso = [
            r'^[#*>\s]*(?<!\w)[a-z]\)',
            r'^[#*>\s]*(?<!\w)[A-Z]\)',
            r'^[#*>\s]*(?<!\w)[a-z]\.',
            r'^[#*>\s]*(?<!\w)[a-z]\.-',
            r'^[#*>\s]*(?<!\w)[a-z]\s*-',
            r'^[#*>\s]*(?<!\w)\([a-z]\)',
        ]

        # =======================================================================
        # BLINDAJE UNICODE: Clases de caracteres para vocales acentuadas
        # Captura: vocal normal, acentuada, y mojibake común (UTF-8 → Latin-1)
        # =======================================================================
        _A = r'[aáàâãäåAÁÀÂÃÄÅ\u00e1\u00c1]'
        _E = r'[eéèêëEÉÈÊË\u00e9\u00c9]'
        _I = r'[iíìîïIÍÌÎÏ\u00ed\u00cd]'
        _O = r'[oóòôõöOÓÒÔÕÖ\u00f3\u00d3]'
        _U = r'[uúùûüUÚÙÛÜ\u00fa\u00da]'
        _N = r'[nñNÑ\u00f1\u00d1]'

        # Palabras clave con blindaje (pueden tener acentos corruptos)
        _ARTICULO = f'Art{_I}culo'
        _PARRAFO = f'P{_A}rrafo'
        _FRACCION = f'Fracci{_O}n'
        _ADICION = f'Adici{_O}n'
        _DEROGACION = f'Derogaci{_O}n'
        _MODIFICACION = f'Modificaci{_O}n'
        _PUBLICACION = f'Publicaci{_O}n'
        _ULTIMA = f'{_U}ltima'

        # =======================================================================
        # PATRONES DE REFORMA/ADICIÓN CON FECHAS DINÁMICAS
        # Patrones estáticos iniciales que terminan en fechas dinámicas
        # =======================================================================
        
        # Patrón de fecha dinámica: DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY, o formato con meses
        _PATRON_FECHA = r'(?:\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|' \
                       r'\d{1,2}\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+\d{2,4}|' \
                       r'(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+\d{1,2},?\s+\d{2,4})'
        
        # Patrón para múltiples fechas separadas por comas
        _PATRON_FECHAS_MULTIPLES = rf'(?:{_PATRON_FECHA}(?:\s*,\s*{_PATRON_FECHA})*)'

        # Reformas y notas al pie de artículos (Súper catálogo de patrones DOF - BLINDADO)
        # ACTUALIZADO: Incluye patrones específicos con fechas dinámicas
        self.patrones_reforma = [
            # ===== PATRONES DE ADICIÓN CON FECHAS =====
            # 1. Artículo adicionado DOF [fecha]
            re.compile(
                rf'^[#*>\s]*{_ARTICULO}\s+adicionad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 2. Párrafo adicionado DOF [fecha]
            re.compile(
                rf'^[#*>\s]*{_PARRAFO}\s+adicionad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 3. Fracción adicionada DOF [fecha]
            re.compile(
                rf'^[#*>\s]*{_FRACCION}\s+adicionad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 4. Inciso adicionado DOF [fecha]
            re.compile(
                rf'^[#*>\s]*Inciso\s+adicionad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 5. Párrafo con numerales adicionado DOF [fecha]
            re.compile(
                rf'^[#*>\s]*{_PARRAFO}\s+con\s+numerales\s+adicionad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 6. Párrafo con incisos adicionado DOF [fecha]
            re.compile(
                rf'^[#*>\s]*{_PARRAFO}\s+con\s+incisos\s+adicionad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 7. Se ADICIONAN los artículos... [fecha]
            re.compile(
                rf'^[#*>\s]*Se\s+ADICIONAN\s+(?:los\s+)?(?:art{_I}culos?|p{_A}rrafos?|fracciones?|incisos?).*{_PATRON_FECHA}',
                re.IGNORECASE
            ),

            # ===== PATRONES DE REFORMA/MODIFICACIÓN CON FECHAS =====
            # 8. Artículo reformado DOF [fecha]
            re.compile(
                rf'^[#*>\s]*{_ARTICULO}\s+reformad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 9. Párrafo reformado DOF [fecha]
            re.compile(
                rf'^[#*>\s]*{_PARRAFO}\s+reformad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 10. Fracción reformada DOF [fecha]
            re.compile(
                rf'^[#*>\s]*{_FRACCION}\s+reformad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 11. Inciso reformado DOF [fecha]
            re.compile(
                rf'^[#*>\s]*Inciso\s+reformad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 12. Apartado reformado DOF [fecha]
            re.compile(
                rf'^[#*>\s]*Apartado\s+reformad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 13. Fracción recorrida DOF [fecha]
            re.compile(
                rf'^[#*>\s]*{_FRACCION}\s+recorrid[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 14. Párrafo reformado DOF, [fecha], [fecha] (múltiples fechas)
            re.compile(
                rf'^[#*>\s]*{_PARRAFO}\s+reformad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHAS_MULTIPLES}',
                re.IGNORECASE
            ),
            
            # 15. Párrafo adicionado DOF. Reformado DOF [fecha]
            re.compile(
                rf'^[#*>\s]*{_PARRAFO}\s+adicionad[oa]\s+(?:D\.O\.F\.|DOF)\.\s*Reformad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 16. Última reforma publicada DOF [fecha]
            re.compile(
                rf'^[#*>\s]*(?:{_ULTIMA}|Ultima)\s+reforma\s+publicad[oa]\s+(?:D\.O\.F\.|DOF)\s+{_PATRON_FECHA}',
                re.IGNORECASE
            ),
            
            # 17. Se REFORMAN los artículos... [fecha]
            re.compile(
                rf'^[#*>\s]*Se\s+REFORMAN\s+(?:los\s+)?(?:art{_I}culos?|p{_A}rrafos?|fracciones?|incisos?).*{_PATRON_FECHA}',
                re.IGNORECASE
            ),

            # ===== PATRONES GENÉRICOS (sin fecha específica, para compatibilidad) =====
            # 18. Entidad + Cualquier texto + Acción (reformado, adicionado, etc.)
            re.compile(
                rf'^[#*>\s]*(?:{_ARTICULO}|{_PARRAFO}|{_FRACCION}|Inciso|Apartado|Fe de erratas|Numeral|Anexo|Punto)'
                rf'.*(?:reformad[oa]|adicionad[oa]|derogad[oa]|publicad[oa]|recorrid[oa]|modificad[oa]).*',
                re.IGNORECASE
            ),

            # 19. Palabras clave de acción o cambio al inicio + referencia DOF
            re.compile(
                rf'^[#*>\s]*(?:Reforma|{_ADICION}|Adicion|{_DEROGACION}|Derogacion|'
                rf'{_MODIFICACION}|Modificacion|{_PUBLICACION}|Publicacion|'
                rf'Derog{_O}|Derogo|Adicion{_O}|Adiciono|Reform{_O}|Reformo|Modific{_O}|Modifico)'
                rf'.*(?:D\.O\.F\.|DOF|Vigente|C{_O}d|Ley).*',
                re.IGNORECASE
            ),

            # 20. Acciones directas colectivas
            re.compile(r'^[#*>\s]*Se\s+(?:REFORMAN|ADICIONAN|DEROGAN|MODIFICAN)\s+.*', re.IGNORECASE),

            # 21. Etiquetas de (REFORMADO), etc. - con variantes
            re.compile(
                r'^[#*>\s]*\(?(REFORMADO|DEROGADO|ADICIONADO|REFORMADA|DEROGADA|ADICIONADA|MODIFICADO|MODIFICADA)\)?(?:\s+|$)',
                re.IGNORECASE
            ),

            # 22. Notas de vigencia finales (sin fecha específica)
            re.compile(rf'^[#*>\s]*(?:{_ULTIMA}|Ultima)\s+reforma\s+.*', re.IGNORECASE),

            # 23. Patrón amplio: línea que menciona D.O.F. o DOF con fecha (formato flexible)
            re.compile(r'^[#*>\s]*.*(?:D\.O\.F\.|DOF)\s*\d{1,2}.*(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}-\d{1,2}-\d{2,4}).*', re.IGNORECASE),

            # 24. Patrón para "Fe de erratas" con fecha
            re.compile(r'^[#*>\s]*Fe\s+de\s+erratas.*\d{1,2}.*', re.IGNORECASE),
        ]

        # Validación de romanos
        self.patron_romano_valido = re.compile(r'^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$')

    def procesar(self, texto: str, usar_separadores: bool = False) -> str:
        """
        Procesa el texto detectando estructura legal y convirtiéndola a Markdown.
        """
        stats = EstadisticasProcesamientoDummy()
        try:
            texto = self._limpiar_texto_previo(texto)
            
            # PROTECCIÓN DE HEADERS/FOOTERS
            # Evitar que los patrones de artículos detecten texto dentro de headers/footers
            texto, headers_footers_protegidos = self._proteger_headers_footers(texto)
            
            preambulo, articulos = self._extraer_articulos(texto)
            
            # Si no se detectaron artículos, retornar original (restaurando headers)
            if not articulos:
                logger.info("No se detectó estructura legal (artículos).")
                return self._restaurar_headers_footers(texto, headers_footers_protegidos)

            for articulo in articulos:
                self._procesar_articulo(articulo, stats)
            
            logger.info(f"Detectados {len(articulos)} artículos con estructura jerárquica.")
            texto_reconstruido = self._reconstruir_documento(preambulo, articulos, usar_separadores)
            
            # RESTAURACIÓN FINAL DE HEADERS/FOOTERS
            return self._restaurar_headers_footers(texto_reconstruido, headers_footers_protegidos)
        except Exception as e:
            logger.error(f"Error procesando estructura legal: {e}", exc_info=True)
            return texto
    
    def _limpiar_texto_previo(self, texto: str) -> str:
        """Limpieza básica antes del procesamiento estructural"""
        # Normalización Unicode esencial (Fix silencioso)
        if texto:
            texto = unicodedata.normalize('NFC', texto)

        # Unificar saltos de línea
        texto = texto.replace('\r\n', '\n').replace('\r', '\n')
        
        # ELIMINAR NUMEROS DE PAGINA (Ej: "2 de 365", "150 de 1200")
        # Elimina líneas que solo contienen patrón "Numero de Numero"
        texto = re.sub(r'^\s*\d+\s+de\s+\d+\s*$', '', texto, flags=re.IGNORECASE | re.MULTILINE)
        
        # Limpiar espacios múltiples (CORREGIDO: ASIGNAR EL RESULTADO)
        texto = re.sub(r'[ \t]+', ' ', texto)
        
        return texto

    def _proteger_headers_footers(self, texto: str) -> Tuple[str, Dict[str, str]]:
        """
        Detecta y protege headers y footers de Mistral OCR para evitar
        que sean procesados o rotos por la lógica de artículos.
        """
        protegidos = {}
        
        def replacer(match):
            placeholder = f"<<<MISTRAL_HEADER_FOOTER_{len(protegidos)}>>>"
            protegidos[placeholder] = match.group(0)
            return placeholder

        # Usar los mismos patrones robustos que en text_md_optimization
        # Header
        texto = re.sub(
            r'(\*\*Encabezado:\*\*.*?(?=\n\n(?!\*\*Pie de página:\*\*)|$))',
            replacer,
            texto,
            flags=re.DOTALL | re.MULTILINE 
        )
        
        # Footer
        texto = re.sub(
            r'(\n\n\*\*Pie de página:\*\*.*?(?=\n\n|$))',
            replacer,
            texto,
            flags=re.DOTALL | re.MULTILINE
        )
        
        return texto, protegidos

    def _restaurar_headers_footers(self, texto: str, protegidos: Dict[str, str]) -> str:
        """Restaura los headers y footers protegidos."""
        for placeholder, contenido in protegidos.items():
            if placeholder in texto:
                texto = texto.replace(placeholder, contenido)
        return texto

    def _extraer_articulos(self, texto: str) -> Tuple[str, List[ArticuloLegal]]:
        """
        Extrae artículos del texto, respetando separadores existentes (---).
        Los separadores se detectan pero no se incluyen en el contenido de los artículos.
        """
        articulos = []
        lineas = texto.split('\n')
        preambulo_lineas = []
        articulo_actual = None
        contenido_articulo = []
        encontrado_primer_articulo = False
        tiene_separadores_existentes = False

        for linea in lineas:
            linea_limpia = linea.strip()
            es_articulo = False
            es_separador = False

            # Detectar separadores existentes (---)
            if re.match(r'^-{3,}$', linea_limpia):
                es_separador = True
                tiene_separadores_existentes = True
                # Si hay un artículo actual, guardarlo antes del separador
                if articulo_actual:
                    articulo_actual.contenido_inicial = '\n'.join(contenido_articulo).strip()
                    articulos.append(articulo_actual)
                    articulo_actual = None
                    contenido_articulo = []
                # No agregar el separador al contenido, se manejará en reconstrucción
                continue

            # Verificar si la línea coincide con algún patrón de artículo
            if linea_limpia and not es_separador:
                for patron in self.patrones_articulo:
                    if re.match(patron, linea_limpia, re.IGNORECASE):
                        es_articulo = True
                        break

            if es_articulo:
                encontrado_primer_articulo = True
                # Guardar artículo anterior
                if articulo_actual:
                    articulo_actual.contenido_inicial = '\n'.join(contenido_articulo).strip()
                    articulos.append(articulo_actual)

                # Extraer número y sufijos
                numero, numero_base, sufijo = self._extraer_numero_articulo(linea_limpia)

                # Crear nuevo artículo
                articulo_actual = ArticuloLegal(numero=numero, numero_base=numero_base, sufijo=sufijo)
                
                # Reiniciar contenido con lo que sobre de la línea
                resto_linea = self._extraer_resto_linea_articulo(linea_limpia)
                contenido_articulo = [resto_linea] if resto_linea else []
            else:
                if not encontrado_primer_articulo:
                    preambulo_lineas.append(linea)
                elif articulo_actual:
                    contenido_articulo.append(linea)

        # Último artículo
        if articulo_actual:
            articulo_actual.contenido_inicial = '\n'.join(contenido_articulo).strip()
            articulos.append(articulo_actual)

        preambulo = '\n'.join(preambulo_lineas).strip()
        
        # Guardar información sobre separadores existentes para uso en reconstrucción
        self._tiene_separadores_existentes = tiene_separadores_existentes
        
        return preambulo, articulos

    def _extraer_numero_articulo(self, linea: str) -> tuple:
        patron_completo = re.compile(
            r'Art[íi]culo\s+(\d+)([oºa°])?\.?\s*(-[A-Z])?\s*(Bis|Ter|Quáter|Quinquies)?',
            re.IGNORECASE
        )
        match = patron_completo.search(linea)
        if match:
            numero_base = int(match.group(1))
            sufijo = f"{match.group(2) or ''}{match.group(3) or ''} {match.group(4) or ''}".strip()
            numero_completo = f"{numero_base}{sufijo}"
            return numero_completo, numero_base, sufijo

        match_simple = re.search(r'(\d+)', linea)
        if match_simple:
            numero_base = int(match_simple.group(1))
            return str(numero_base), numero_base, ""

        return "0", 0, ""

    def _extraer_resto_linea_articulo(self, linea: str) -> str:
        patron = re.compile(
            r'Art[íi]culo\s+\d+[oºa°]?\.?\s*(?:-[A-Z])?\s*(?:Bis|Ter|Quáter|Quinquies)?\s*\.?\s*(.*)$',
            re.IGNORECASE
        )
        match = patron.search(linea)
        if match:
            return match.group(1).strip()
        return ""

    def _procesar_articulo(self, articulo: ArticuloLegal, stats: Any):
        contenido = articulo.contenido_inicial
        fracciones = self._extraer_fracciones(contenido)
        
        if fracciones:
            lineas = contenido.split('\n')
            intro_lineas = []
            
            # Buscar dónde empiezan las fracciones para separar preámbulo
            for linea in lineas:
                linea_limpia = linea.strip()
                es_inicio_fraccion = False
                if linea_limpia:
                    for patron in self.patrones_fraccion:
                        if re.match(patron, linea_limpia, re.IGNORECASE):
                            numero_romano = self._extraer_numero_romano(linea_limpia)
                            if numero_romano and self._es_numero_romano_valido(numero_romano):
                                es_inicio_fraccion = True
                                break
                if es_inicio_fraccion:
                    break
                intro_lineas.append(linea)
            
            texto_inicial = '\n'.join(intro_lineas).strip()
            texto_inicial, reformas_intro = self._extraer_reformas(texto_inicial)
            
            articulo.contenido_inicial = texto_inicial
            articulo.reformas = reformas_intro
            articulo.fracciones = fracciones

            for fraccion in fracciones:
                self._procesar_fraccion(fraccion, stats)
        else:
            contenido, reformas = self._extraer_reformas(contenido)
            articulo.contenido_inicial = contenido.strip()
            articulo.reformas = reformas

    def _extraer_fracciones(self, contenido: str) -> List[Fraccion]:
        fracciones = []
        lineas = contenido.split('\n')
        fraccion_actual = None
        contenido_fraccion = []

        for linea in lineas:
            linea_limpia = linea.strip()
            es_fraccion = False
            numero_romano = None

            for patron in self.patrones_fraccion:
                match = re.match(patron, linea_limpia, re.IGNORECASE)
                if match:
                    numero_romano = self._extraer_numero_romano(linea_limpia)
                    if numero_romano and self._es_numero_romano_valido(numero_romano):
                        es_fraccion = True
                        break

            if es_fraccion and numero_romano:
                if fraccion_actual:
                    fraccion_actual.contenido = '\n'.join(contenido_fraccion).strip()
                    fracciones.append(fraccion_actual)

                fraccion_actual = Fraccion(numero_romano=numero_romano.upper(), contenido="")
                resto_linea = self._extraer_resto_linea_fraccion(linea_limpia)
                contenido_fraccion = [resto_linea] if resto_linea else []
            elif fraccion_actual:
                contenido_fraccion.append(linea)

        if fraccion_actual:
            fraccion_actual.contenido = '\n'.join(contenido_fraccion).strip()
            fracciones.append(fraccion_actual)

        return fracciones

    def _extraer_numero_romano(self, linea: str) -> str:
        patron = re.compile(r'^(?:Fracción\s+)?([IVXLCDM]+)', re.IGNORECASE)
        match = patron.search(linea)
        return match.group(1) if match else ""

    def _extraer_resto_linea_fraccion(self, linea: str) -> str:
        patron = re.compile(r'^(?:Fracción\s+)?[IVXLCDM]+[\.\-\):\s]+(.*)$', re.IGNORECASE)
        match = patron.search(linea)
        return match.group(1).strip() if match else ""

    def _procesar_fraccion(self, fraccion: Fraccion, stats: Any):
        contenido, reformas = self._extraer_reformas(fraccion.contenido)
        fraccion.reformas = reformas
        incisos = self._extraer_incisos(contenido)
        
        if incisos:
            # Encontrar donde empieza el primer inciso
            primer_pos = -1
            for inciso in incisos:
                pos = contenido.find(f"{inciso.letra})")
                if pos != -1 and (primer_pos == -1 or pos < primer_pos):
                    primer_pos = pos
            
            if primer_pos != -1:
                fraccion.contenido = contenido[:primer_pos].strip()
            
            fraccion.incisos = incisos
            for inciso in incisos:
                cont, refs = self._extraer_reformas(inciso.contenido)
                inciso.contenido = cont
                inciso.reformas = refs
        else:
            fraccion.contenido = contenido

    def _extraer_incisos(self, contenido: str) -> List[Inciso]:
        incisos = []
        lineas = contenido.split('\n')
        inciso_actual = None
        contenido_inciso = []

        for linea in lineas:
            linea_limpia = linea.strip()
            es_inciso = False
            letra = None

            for patron in self.patrones_inciso:
                match = re.match(patron, linea_limpia, re.IGNORECASE)
                if match:
                    letra = self._extraer_letra_inciso(linea_limpia)
                    if letra:
                        es_inciso = True
                        break

            if es_inciso and letra:
                if inciso_actual:
                    inciso_actual.contenido = '\n'.join(contenido_inciso).strip()
                    incisos.append(inciso_actual)

                inciso_actual = Inciso(letra=letra, contenido="")
                resto_linea = self._extraer_resto_linea_inciso(linea_limpia)
                contenido_inciso = [resto_linea] if resto_linea else []
            elif inciso_actual:
                contenido_inciso.append(linea)

        if inciso_actual:
            inciso_actual.contenido = '\n'.join(contenido_inciso).strip()
            incisos.append(inciso_actual)

        return incisos

    def _extraer_letra_inciso(self, linea: str) -> str:
        # Validación estricta: Letra + separador al inicio
        patron = re.compile(r'^[#*>\s\-\(]*([a-zA-Z])(?:[\.\)\-]|\s)', re.IGNORECASE)
        match = patron.search(linea)
        return match.group(1).lower() if match else ""

    def _extraer_resto_linea_inciso(self, linea: str) -> str:
        patron = re.compile(r'^[a-zA-Z][\.\-\):\s]+(.*)$', re.IGNORECASE)
        match = patron.search(linea)
        return match.group(1).strip() if match else ""

    def _extraer_reformas(self, contenido: str) -> Tuple[str, List[MarcadorReforma]]:
        """
        Detecta líneas de reforma y las formatea con cursivas inline.
        Retorna lista vacía de MarcadorReforma para evitar duplicación visual.
        IMPORTANTE: No procesa líneas que ya están envueltas en *...* (evita duplicación).
        """
        lineas = contenido.split('\n')
        lineas_limpias = []

        for linea in lineas:
            linea_strip = linea.strip()

            # SKIP: Si ya está envuelta en cursivas, no procesar de nuevo
            if linea_strip.startswith('*') and linea_strip.endswith('*') and len(linea_strip) > 2:
                lineas_limpias.append(linea)
                continue

            es_reforma = False
            for patron in self.patrones_reforma:
                if patron.search(linea_strip):
                    # Marcar visualmente con cursivas (única representación)
                    lineas_limpias.append(f"*{linea_strip}*")
                    es_reforma = True
                    break

            if not es_reforma:
                lineas_limpias.append(linea)

        # Retornar lista vacía - las reformas ya están inline con cursivas
        return "\n".join(lineas_limpias).strip(), []

    def _reconstruir_documento(self, preambulo: str, articulos: List[ArticuloLegal], usar_separadores: bool) -> str:
        """
        Reconstruye el documento final con espaciado limpio.
        Si ya existen separadores (---) en el documento original, los respeta.
        Solo añade separadores nuevos si usar_separadores=True y no existen separadores previos.
        """
        resultado = []
        if preambulo:
            resultado.append(preambulo.strip())

        # Determinar si debemos usar separadores
        # Solo usar separadores si se solicita Y no existen separadores previos
        usar_sep_final = usar_separadores and not self._tiene_separadores_existentes

        for i, articulo in enumerate(articulos):
            # Añadir separador antes del artículo (excepto el primero)
            if usar_sep_final and i > 0:
                resultado.append("---")
            
            resultado.append(articulo.a_markdown(usar_separadores=False).strip())

        # Unir y limpiar espacios excesivos
        texto_final = "\n\n".join(resultado)
        
        # Limpiar espacios excesivos pero preservar separadores
        # Reemplazar 3+ líneas vacías por 2, pero mantener separadores
        texto_final = re.sub(r'(?<!-)\n{3,}(?!-)', '\n\n', texto_final)

        return texto_final

    def _es_numero_romano_valido(self, texto: str) -> bool:
        return bool(self.patron_romano_valido.match(texto.upper()))

# ==============================
# ADAPTER PARA COMPATIBILIDAD
# ==============================

class LegalTextOptimizer:
    """Clase adaptadora para que text_md_optimization.py pueda usar el nuevo motor."""
    
    def __init__(self, style: str = "markdown"):
        self.style = style
        self.procesador = ProcesadorEstructuraLegal()
        
    def optimize(self, text: str) -> str:
        """
        Optimiza el texto legal estructurándolo.
        Si el estilo es 'articulos', activa los separadores.
        """
        usar_separadores = (self.style == "articulos")
        return self.procesador.procesar(text, usar_separadores=usar_separadores)

# Alias para compatibilidad inversa
LegalDocumentFormatter = LegalTextOptimizer
