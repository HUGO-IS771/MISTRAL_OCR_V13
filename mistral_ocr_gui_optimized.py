#!/usr/bin/env python3
"""
Mistral OCR GUI - Versión Optimizada y Refactorizada
Interfaz gráfica para el cliente de Mistral OCR con procesamiento de documentos PDF e imágenes.

Versión: 5.0.0 - Refactorizada
Fecha: Agosto 2025
Cambios: Eliminación de duplicidades y consolidación de métodos
"""

import os
import sys
import time
import threading
import webbrowser
import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import customtkinter as ctk
from PIL import Image, ImageTk
import logging
from dotenv import load_dotenv
import mimetypes
import re
from datetime import datetime
import urllib.parse
import subprocess
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from functools import partial

# Importaciones opcionales
try:
    from markdown import markdown
    MARKDOWN_SUPPORT = True
except ImportError:
    MARKDOWN_SUPPORT = False

try:
    from tkhtmlview import HTMLLabel
    HTML_SUPPORT = True
except ImportError:
    HTML_SUPPORT = False
    class HTMLLabel:
        def __init__(self, master, html=None, **kwargs):
            self.frame = ctk.CTkFrame(master)
            self.label = ctk.CTkLabel(
                self.frame,
                text="Instale 'tkhtmlview' para la previsualización HTML: pip install tkhtmlview",
                wraplength=600
            )
            self.label.pack(pady=50, padx=20)
            
        def pack(self, **kwargs):
            self.frame.pack(**kwargs)

from mistral_ocr_client_optimized import MistralOCRClient
from batch_optimizer import analyze_and_recommend, BatchOptimizer
from multi_batch_processor import analyze_multiple_pdfs, MultiBatchProcessor
from performance_optimizer import create_optimized_processor, estimate_batch_time
from split_control_dialog import show_advanced_split_dialog

# Configuración
load_dotenv(override=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mistral_ocr_gui')

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# Constantes
MAX_FILE_SIZE_MB = 50.0
MAX_PAGES_PER_FILE = 135
DEFAULT_PAGES_PER_SPLIT = 70
DEFAULT_WORKERS = 2
SUPPORTED_FORMATS = [
    ("Todos los formatos", "*.pdf;*.jpg;*.jpeg;*.png;*.tiff;*.tif"),
    ("PDF", "*.pdf"),
    ("JPEG", "*.jpg;*.jpeg"),
    ("PNG", "*.png"),
    ("TIFF", "*.tiff;*.tif"),
    ("Todos", "*.*")
]

@dataclass
class ProcessingConfig:
    """Configuración para el procesamiento de documentos"""
    api_key: str
    model: str = "mistral-ocr-2512"
    max_size_mb: float = MAX_FILE_SIZE_MB
    max_pages: int = MAX_PAGES_PER_FILE
    compression_quality: str = "medium"
    output_formats: List[str] = None
    optimize: bool = True
    optimization_domain: str = "legal"
    save_images: bool = True
    
    def __post_init__(self):
        if self.output_formats is None:
            self.output_formats = ['md', 'txt', 'html']


class WidgetFactory:
    """Factory class para crear widgets reutilizables y evitar duplicación"""
    
    @staticmethod
    def create_labeled_entry(parent, label: str, var: tk.Variable, row: int, 
                            column: int = 0, width: int = None, show: str = None) -> ctk.CTkEntry:
        """Crea una entrada con etiqueta de forma estandarizada"""
        ctk.CTkLabel(parent, text=label).grid(
            row=row, column=column, padx=5, pady=5, sticky="w"
        )
        
        entry_params = {"textvariable": var}
        if width:
            entry_params["width"] = width
        if show:
            entry_params["show"] = show
            
        entry = ctk.CTkEntry(parent, **entry_params)
        entry.grid(row=row, column=column+1, padx=5, pady=5, sticky="ew")
        return entry
    
    @staticmethod
    def create_file_browser(parent, label: str, var: tk.Variable, row: int,
                           browse_callback: Callable, filetypes: list = None) -> dict:
        """Crea un campo de entrada con botón de exploración"""
        widgets = {}
        widgets['label'] = ctk.CTkLabel(parent, text=label)
        widgets['label'].grid(row=row, column=0, padx=5, pady=5, sticky="w")
        
        widgets['entry'] = ctk.CTkEntry(parent, textvariable=var)
        widgets['entry'].grid(row=row, column=1, padx=5, pady=5, sticky="ew")
        
        widgets['button'] = ctk.CTkButton(
            parent, text="Examinar", command=lambda: browse_callback(var, filetypes)
        )
        widgets['button'].grid(row=row, column=2, padx=5, pady=5)
        
        return widgets
    
    @staticmethod
    def create_checkbox_group(parent, options: List[Tuple[str, tk.Variable]], 
                             title: str = None) -> ctk.CTkFrame:
        """Crea un grupo de checkboxes"""
        frame = ctk.CTkFrame(parent)
        
        if title:
            ctk.CTkLabel(
                frame, text=title, font=ctk.CTkFont(size=14, weight="bold")
            ).pack(anchor="w", padx=5, pady=5)
        
        for label, var in options:
            ctk.CTkCheckBox(frame, text=label, variable=var).pack(
                anchor="w", padx=10, pady=5
            )
        
        return frame
    
    @staticmethod
    def create_numeric_spinbox(parent, var: tk.Variable, min_val: float = 0,
                              max_val: float = None, default: float = 1) -> ctk.CTkEntry:
        """Crea una entrada numérica con validación"""
        def validate(value):
            if value == "":
                return True
            try:
                val = float(value)
                if min_val is not None and val < min_val:
                    return False
                if max_val is not None and val > max_val:
                    return False
                return True
            except ValueError:
                return False
        
        vcmd = (parent.register(validate), '%P')
        entry = ctk.CTkEntry(
            parent, width=60, textvariable=var, 
            validate="key", validatecommand=vcmd
        )
        
        # Añadir manejador para valores vacíos
        entry.bind("<FocusOut>", lambda e: var.set(default) if not var.get() else None)
        
        return entry


class FileProcessor:
    """Clase unificada para manejar el procesamiento de archivos"""
    
    def __init__(self, ocr_client: MistralOCRClient, app=None):
        self.ocr_client = ocr_client
        self.app = app
        self.validation_result = None  # Para diálogo de validación
        
    def analyze_file(self, filepath: str) -> Dict[str, Any]:
        """Analiza un archivo y retorna su información"""
        try:
            size_mb = self.ocr_client.get_file_size_mb(filepath)
            pages_count = self.ocr_client.estimate_pages_count(filepath)
            mime_type, _ = mimetypes.guess_type(filepath)
            
            # Determinar si requiere división:
            # - Por páginas: si excede MAX_PAGES_PER_FILE
            # - Por tamaño: si excede MAX_FILE_SIZE_MB (aunque no se puedan contar páginas)
            requires_split = size_mb > MAX_FILE_SIZE_MB
            if pages_count is not None:
                requires_split = requires_split or pages_count > MAX_PAGES_PER_FILE
            
            return {
                'path': filepath,
                'size_mb': size_mb,
                'pages': pages_count,
                'mime_type': mime_type,
                'requires_split': requires_split
            }
        except Exception as e:
            logger.error(f"Error analyzing file {filepath}: {e}")
            return None
    
    def process_with_split(self, file_info: Dict, config: ProcessingConfig) -> List[Dict]:
        """Procesa un archivo con validación PRE-división para evitar crear archivos innecesarios"""
        files_to_process = []
        
        if file_info['requires_split']:
            # Determinar número de archivos objetivo
            if hasattr(self, 'target_files_from_modal') and self.target_files_from_modal:
                num_files_target = self.target_files_from_modal
                logger.info(f"Usando configuración del modal: {num_files_target} archivos")
            else:
                # Calcular basado en páginas máximas o tamaño si no hay páginas
                total_pages = file_info.get('pages')
                size_mb = file_info.get('size_mb', 0)
                
                if total_pages is not None:
                    # Calcular por páginas
                    num_files_by_pages = math.ceil(total_pages / config.max_pages)
                else:
                    # Si no hay páginas, estimar por tamaño (asumiendo ~0.5MB por cada 10 páginas típicamente)
                    num_files_by_pages = 1
                
                # Calcular también por tamaño
                num_files_by_size = math.ceil(size_mb / config.max_size_mb)
                
                # Usar el mayor de ambos para garantizar que todos los archivos estén dentro de límites
                num_files_target = max(num_files_by_pages, num_files_by_size, 1)
                logger.info(f"División calculada: {num_files_target} archivos (por páginas: {num_files_by_pages}, por tamaño: {num_files_by_size})")
            
            # VALIDACIÓN PRE-DIVISIÓN: Estimar tamaños ANTES de crear archivos
            try:
                from pre_division_validator import PreDivisionValidator
                from pre_division_dialog import show_pre_division_dialog
                
                pre_validator = PreDivisionValidator(max_size_mb=50.0)
                file_path = Path(file_info['path'])
                
                # Validar si es seguro proceder con la división planeada
                is_safe, analysis = pre_validator.validate_before_split(file_path, num_files_target)
                
                if not is_safe:
                    # LOS ARCHIVOS ESTIMADOS EXCEDERÁN LÍMITES - MOSTRAR MODAL PREVENTIVO
                    logger.warning(f"PRE-VALIDACIÓN: {analysis.files_exceeding_limits}/{num_files_target} archivos estimados excederán 50MB")
                    
                    # Mostrar modal de confirmación PRE-división
                    if self.app:
                        pre_result = None
                        
                        def show_pre_modal():
                            nonlocal pre_result
                            pre_result = show_pre_division_dialog(self.app, analysis, pre_validator)
                        
                        # Ejecutar modal en hilo principal
                        self.app.after_idle(show_pre_modal)
                        
                        # Esperar resultado del modal
                        while pre_result is None:
                            self.app.update_idletasks()
                            self.app.update()
                            time.sleep(0.1)
                        
                        # Procesar decisión del usuario
                        if pre_result.action == 'cancel':
                            logger.info("Usuario canceló la división - no se crearán archivos")
                            # No hay archivos que limpiar porque no se crearon
                            return []
                        elif pre_result.action == 'use_recommendation' or pre_result.action == 'adjust':
                            # Actualizar número de archivos según decisión del usuario
                            num_files_target = pre_result.num_files
                            logger.info(f"Usuario eligió {num_files_target} archivos (pre-validado como seguro)")
                        elif pre_result.action == 'proceed':
                            logger.warning("Usuario eligió proceder creando archivos problemáticos (RIESGOSO)")
                    else:
                        logger.error("No hay app disponible para mostrar modal de pre-validación")
                        return []
                else:
                    logger.info(f"PRE-VALIDACIÓN: División en {num_files_target} archivos es segura, procediendo...")
                
            except Exception as e:
                logger.error(f"Error en pre-validación: {e}")
                # Continuar con división normal como fallback
            
            # Limpiar configuración del modal después de usar
            if hasattr(self, 'target_files_from_modal'):
                self.target_files_from_modal = None
            
            # Ahora SÍ crear archivos físicos (ya pre-validados)
            # Si no tenemos páginas, estimar basándose en tamaño (~4 páginas/MB típicamente)
            total_pages = file_info.get('pages')
            if total_pages is None:
                size_mb = file_info.get('size_mb', 50)
                total_pages = int(size_mb * 4)  # Estimación conservadora
                logger.info(f"Páginas estimadas por tamaño: {total_pages} (basado en {size_mb:.1f}MB)")
            pages_per_file = math.ceil(total_pages / num_files_target)
            
            split_info = self.ocr_client.split_pdf(
                file_info['path'], 
                max_pages_per_file=pages_per_file
            )
            
            # Registrar archivos divididos para limpieza automática
            try:
                from file_cleanup_manager import register_split_files_for_cleanup
                register_split_files_for_cleanup(split_info, Path(file_info['path']))
            except Exception as e:
                logger.warning(f"No se pudo registrar archivos para limpieza: {e}")
            
            # Archivos ya pre-validados - procesar directamente
            logger.info("Archivos divididos creados después de pre-validación")
            
            # Calcular páginas por archivo dividido basado en archivos reales creados
            total_pages = split_info['total_pages']
            actual_files = split_info.get('files', [])
            
            # Distribución real de páginas
            pages_remaining = total_pages
            
            for idx, split_file in enumerate(actual_files):
                if idx == len(actual_files) - 1:
                    # Último archivo recibe todas las páginas restantes
                    pages_in_this_file = pages_remaining
                else:
                    # Distribución uniforme para otros archivos
                    pages_in_this_file = pages_per_file
                
                files_to_process.append({
                    'file_path': split_file,
                    'original_file': file_info['path'],
                    'pages': pages_in_this_file
                })
                
                pages_remaining -= pages_in_this_file
        else:
            files_to_process.append({
                'file_path': file_info['path'],
                'original_file': file_info['path'],
                'pages': file_info.get('pages', 0)
            })
        
        return files_to_process


class UIUpdater:
    """Clase para manejar actualizaciones de UI de forma centralizada"""
    
    def __init__(self, app):
        self.app = app
        
    def update_status(self, message: str):
        """Actualiza la barra de estado"""
        self.app.after(10, lambda: self.app.status_bar.configure(text=message))
    
    def update_progress(self, progress_bar, value: float, status_label=None, text: str = ""):
        """Actualiza una barra de progreso y su etiqueta"""
        self.app.after(10, lambda: progress_bar.set(value))
        if status_label and text:
            percentage = int(value * 100)
            self.app.after(10, lambda: status_label.configure(
                text=f"{percentage}% - {text}"
            ))
    
    def append_to_text(self, text_widget, content: str):
        """Añade texto a un widget de texto"""
        def update():
            text_widget.config(state=tk.NORMAL)
            current = text_widget.get(1.0, tk.END)
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, current + content)
            text_widget.see(tk.END)
            text_widget.config(state=tk.DISABLED)
        
        self.app.after(10, update)
    
    def set_text(self, text_widget, content: str):
        """Reemplaza el contenido de un widget de texto"""
        def update():
            text_widget.config(state=tk.NORMAL)
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, content)
            text_widget.see(tk.END)
            text_widget.config(state=tk.DISABLED)
        
        self.app.after(10, update)


class PreviewManager:
    """Maneja las vistas previas de documentos de forma unificada"""
    
    def __init__(self, app):
        self.app = app
        
    def show_preview(self, ocr_response, mode: str = "Markdown"):
        """Muestra la vista previa según el modo seleccionado"""
        if not ocr_response:
            return
            
        # Limpiar contenedor
        for widget in self.app.preview_container.winfo_children():
            widget.destroy()
        
        # Generar contenido
        content = self._generate_content(ocr_response, mode)
        
        # Actualizar código fuente
        self.app.source_text.delete(1.0, tk.END)
        self.app.source_text.insert(tk.END, content)
        
        # Mostrar vista previa
        self._display_content(content, mode)
    
    def _generate_content(self, ocr_response, mode: str) -> str:
        """Genera el contenido según el modo"""
        if mode == "Markdown":
            return "\n\n---\n\n".join([page.markdown for page in ocr_response.pages])
        
        elif mode == "HTML":
            md_content = "\n\n---\n\n".join([page.markdown for page in ocr_response.pages])
            return markdown(md_content) if MARKDOWN_SUPPORT else md_content
        
        else:  # Texto plano
            plain_text = ""
            for i, page in enumerate(ocr_response.pages):
                plain_text += f"=== PÁGINA {i+1} ===\n\n"
                lines = page.markdown.splitlines()
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('!['):
                        line = re.sub(r'^#+\s*', '', line)
                        plain_text += f"{line}\n"
                plain_text += "\n\n"
            return plain_text
    
    def _display_content(self, content: str, mode: str):
        """Muestra el contenido en el contenedor de vista previa"""
        if mode == "HTML" and HTML_SUPPORT and MARKDOWN_SUPPORT:
            HTMLLabel(self.app.preview_container, html=content).pack(
                fill="both", expand=True
            )
        else:
            # Vista de texto simple para todos los demás casos
            text = scrolledtext.ScrolledText(self.app.preview_container, wrap=tk.WORD)
            text.pack(fill="both", expand=True)
            text.insert(tk.END, content)
            text.config(state=tk.DISABLED)


class MistralOCRApp(ctk.CTk):
    """Aplicación GUI optimizada y refactorizada para Mistral OCR Client."""
    
    def __init__(self):
        super().__init__()
        self.setup_window()
        self.init_variables()
        self.init_helpers()
        self.create_widgets()
        self.ocr_client = None
        self.after(100, self.post_init)
    
    def setup_window(self):
        """Configurar ventana principal"""
        self.title("Mistral OCR - Procesador de Documentos")
        self.geometry("1100x750")
        self.minsize(1000, 700)
    
    def init_helpers(self):
        """Inicializa las clases auxiliares"""
        self.widget_factory = WidgetFactory()
        self.ui_updater = UIUpdater(self)
        self.preview_manager = PreviewManager(self)
        self.file_processor = None  # Se inicializa con ocr_client
    
    def init_variables(self):
        """Inicializar todas las variables de la aplicación"""
        # Variables básicas
        self.api_key = tk.StringVar(value=os.environ.get("MISTRAL_API_KEY", ""))
        self.model = tk.StringVar(value="mistral-ocr-latest")
        
        # Variables de configuración simplificadas
        self.config_vars = {
            'optimization_domain': tk.StringVar(value="legal"),
            'optimize_text': tk.BooleanVar(value=True)
        }
        
        # Variables para batch
        self.batch_vars = {
            'file_paths': [],
            'output_dir': tk.StringVar(),
            'max_size': tk.DoubleVar(value=MAX_FILE_SIZE_MB),
            'max_pages': tk.IntVar(value=MAX_PAGES_PER_FILE),
            'workers': tk.IntVar(value=DEFAULT_WORKERS),
            'formats': {
                'md': tk.BooleanVar(value=True),
                'md_rich': tk.BooleanVar(value=False),
                'txt': tk.BooleanVar(value=True),
                'html': tk.BooleanVar(value=True),
                'pdf': tk.BooleanVar(value=False),
                'images': tk.BooleanVar(value=False)
            },
            'optimize': {
                'enabled': tk.BooleanVar(value=True),
                'domain': tk.StringVar(value="legal")
            }
        }
        
        # Variables de estado
        self.processing = False
        self.ocr_response = None
        self.processing_results = None
        self.view_mode = tk.StringVar(value="Markdown")
        self.auto_optimize = tk.BooleanVar(value=True)
    
    def post_init(self):
        """Inicialización posterior a la creación de widgets"""
        self.validate_all_numeric_inputs()
    
    def create_widgets(self):
        """Crear la interfaz principal con pestañas"""
        # Pestañas principales
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Crear pestañas - Solo 3 pestañas ahora
        tabs = ["Procesamiento", "Visualización", "Acerca de"]
        for tab in tabs:
            self.tab_view.add(tab)
        
        # Configurar contenido de pestañas
        self.setup_unified_processing_tab()  # Pestaña unificada
        self.setup_visualization_tab()
        self.setup_about_tab()
        
        # Barra de estado
        self.status_bar = ctk.CTkLabel(self, text="Listo", anchor="w", height=25)
        self.status_bar.pack(fill="x", padx=10, pady=(5, 10))
    
    def setup_unified_processing_tab(self):
        """Configurar pestaña unificada de procesamiento (individual y lotes)"""
        tab = self.tab_view.tab("Procesamiento")
        scroll_frame = ctk.CTkScrollableFrame(tab, corner_radius=0)
        scroll_frame.pack(fill="both", expand=True)
        
        # Description
        self.create_info_label(
            scroll_frame,
            "Procesamiento de Documentos",
            "Procesa uno o múltiples archivos PDF/imágenes con división automática si es necesario."
        )
        
        # File Selection Section
        self.create_batch_file_section(scroll_frame)
        
        # Options Section
        self.create_batch_options_section(scroll_frame)
        
        # Output Formats Section
        format_frame = self.create_section(scroll_frame, "Formatos de salida")
        formats = [
            ("Markdown", self.batch_vars['formats']['md']),
            ("Markdown enriquecido", self.batch_vars['formats']['md_rich']),
            ("Texto", self.batch_vars['formats']['txt']),
            ("🌐 HTML (con imágenes incrustadas)", self.batch_vars['formats']['html']),
            ("PDF", self.batch_vars['formats']['pdf']),
            ("Imágenes separadas", self.batch_vars['formats']['images']),
            ("Optimizar texto", self.batch_vars['optimize']['enabled'])
        ]
        self.widget_factory.create_checkbox_group(format_frame, formats).pack(
            fill="x", padx=10, pady=5
        )
        
        # Process Button
        self.process_btn = ctk.CTkButton(
            scroll_frame, text="Iniciar procesamiento",
            command=self.start_processing,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40
        )
        self.process_btn.pack(padx=20, pady=15)
        
        # Progress
        self.progress_bar = ctk.CTkProgressBar(scroll_frame)
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 5))
        self.progress_bar.set(0)
        
        self.progress_status = ctk.CTkLabel(scroll_frame, text="Esperando...")
        self.progress_status.pack(pady=(0, 15))
        
        # Results
        self.results_text = self.create_text_area(
            scroll_frame, "Resultados del procesamiento", height=15
        )
    
    def setup_visualization_tab(self):
        """Configurar pestaña de visualización"""
        tab = self.tab_view.tab("Visualización")
        frame = ctk.CTkFrame(tab)
        frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Controls
        controls = ctk.CTkFrame(frame)
        controls.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(controls, text="Modo:").pack(side="left", padx=5)
        
        modes = ["Markdown", "HTML", "Texto plano"]
        mode_menu = ctk.CTkOptionMenu(
            controls, values=modes, variable=self.view_mode,
            command=lambda _: self.update_preview()
        )
        mode_menu.pack(side="left", padx=5)
        
        ctk.CTkButton(
            controls, text="Guardar vista", command=self.save_current_view
        ).pack(side="right", padx=10)
        
        # Preview Tabs
        self.preview_tabs = ctk.CTkTabview(frame)
        self.preview_tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.preview_tabs.add("Vista previa")
        self.preview_tabs.add("Código fuente")
        
        # Preview Container
        self.preview_container = ctk.CTkFrame(self.preview_tabs.tab("Vista previa"))
        self.preview_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.show_placeholder("No hay documento procesado")
        
        # Source Code
        self.source_text = scrolledtext.ScrolledText(
            self.preview_tabs.tab("Código fuente"),
            wrap=tk.WORD, font=("Courier New", 10)
        )
        self.source_text.pack(fill="both", expand=True, padx=5, pady=5)
    
    def setup_about_tab(self):
        """Configurar pestaña Acerca de"""
        tab = self.tab_view.tab("Acerca de")
        frame = ctk.CTkFrame(tab)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Information
        info = [
            ("Mistral OCR - Procesador de Documentos", 20, "bold"),
            ("Versión 5.0.0 - Optimizada y Refactorizada", 14, None),
            ("", 12, None),
            ("Procesa documentos PDF e imágenes con la API de Mistral OCR.", 12, None),
            ("Incluye procesamiento por lotes para documentos grandes.", 12, None),
            ("", 12, None),
            ("✨ Código optimizado: reducción de duplicidades", 12, None),
            ("🚀 Mayor eficiencia y mantenibilidad", 12, None)
        ]
        
        for text, size, weight in info:
            font = ctk.CTkFont(size=size, weight=weight) if weight else ctk.CTkFont(size=size)
            ctk.CTkLabel(frame, text=text, font=font).pack(pady=5)
        
        # Links
        links = ctk.CTkFrame(frame)
        links.pack(pady=20)
        
        ctk.CTkButton(
            links, text="Documentación Mistral",
            command=lambda: webbrowser.open("https://docs.mistral.ai/")
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            links, text="GitHub",
            command=lambda: webbrowser.open("https://github.com/mistralai/cookbook")
        ).pack(side="left", padx=10)
    
    # --- Helper Methods ---
    
    def create_section(self, parent, title: str) -> ctk.CTkFrame:
        """Crear una sección con título"""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(
            frame, text=title, font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        content_frame = ctk.CTkFrame(frame)
        content_frame.pack(fill="x", padx=10, pady=5)
        content_frame.grid_columnconfigure(1, weight=1)
        
        return content_frame
    
    # Método eliminado - opciones integradas en procesamiento unificado
    
    # Método eliminado - opciones integradas en procesamiento unificado
    
    def create_batch_file_section(self, parent):
        """Crear sección de selección de archivos para batch"""
        frame = self.create_section(parent, "Archivos PDF")
        
        # Buttons
        buttons_frame = ctk.CTkFrame(frame)
        buttons_frame.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        
        ctk.CTkButton(
            buttons_frame, text="📁 Cargar archivo único",
            command=self.select_batch_files(single=True)
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame, text="📚 Cargar múltiples archivos",
            command=self.select_batch_files(single=False)
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            buttons_frame, text="🗑️ Limpiar lista",
            command=self.clear_file_list
        ).pack(side="left", padx=5)
        
        # File list
        self.files_list_frame = ctk.CTkScrollableFrame(frame, height=150)
        self.files_list_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        
        # Status label
        self.files_status_label = ctk.CTkLabel(
            frame, text="No hay archivos seleccionados", text_color="gray60"
        )
        self.files_status_label.grid(row=2, column=0, columnspan=3, padx=5, pady=2)
        
        # Output directory
        self.widget_factory.create_file_browser(
            frame, "Directorio salida:", self.batch_vars['output_dir'], 3,
            lambda var, ft: self.browse_directory(var)
        )
    
    def create_batch_options_section(self, parent):
        """Crear sección de opciones para batch"""
        frame = self.create_section(parent, "Opciones")
        
        # Row 1: Size and Pages
        ctk.CTkLabel(frame, text="Tamaño máx (MB):").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.widget_factory.create_numeric_spinbox(
            frame, self.batch_vars['max_size'],
            min_val=1, max_val=500, default=MAX_FILE_SIZE_MB
        ).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        ctk.CTkLabel(frame, text="Páginas máx:").grid(
            row=0, column=2, padx=5, pady=5, sticky="w"
        )
        self.widget_factory.create_numeric_spinbox(
            frame, self.batch_vars['max_pages'],
            min_val=1, max_val=1000, default=MAX_PAGES_PER_FILE
        ).grid(row=0, column=3, padx=5, pady=5, sticky="w")
        
        # Row 2: Workers and Domain
        ctk.CTkLabel(frame, text="Workers:").grid(
            row=1, column=0, padx=5, pady=5, sticky="w"
        )
        self.widget_factory.create_numeric_spinbox(
            frame, self.batch_vars['workers'],
            min_val=1, max_val=10, default=DEFAULT_WORKERS
        ).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        ctk.CTkLabel(frame, text="Dominio:").grid(
            row=1, column=2, padx=5, pady=5, sticky="w"
        )
        ctk.CTkOptionMenu(
            frame, values=["general", "legal", "religious"],
            variable=self.batch_vars['optimize']['domain']
        ).grid(row=1, column=3, padx=5, pady=5, sticky="w")
        
        # Performance optimization
        perf_frame = ctk.CTkFrame(frame)
        perf_frame.grid(row=2, column=0, columnspan=4, padx=5, pady=10, sticky="ew")
        
        ctk.CTkLabel(
            perf_frame, text="⚡ Optimización de Rendimiento",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=10)
        
        ctk.CTkCheckBox(
            perf_frame, text="Auto-optimizar velocidad",
            variable=self.auto_optimize
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            perf_frame, text="🕰️ Estimar tiempo",
            command=self.estimate_processing_time,
            width=120
        ).pack(side="right", padx=10)
    
    def create_text_area(self, parent, title: str, height: int = 10) -> scrolledtext.ScrolledText:
        """Crear área de texto con título"""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(
            frame, text=title, font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        text = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, height=height, font=("Courier New", 10)
        )
        text.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        text.config(state=tk.DISABLED)
        return text
    
    def create_info_label(self, parent, title: str, description: str):
        """Crear etiqueta informativa"""
        ctk.CTkLabel(
            parent, text=title, font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(
            parent, text=description, wraplength=850, justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 10))
    
    # --- File Operations ---
    
    # Método eliminado - ahora se usa select_batch_files
    
    def save_file_dialog(self, var: tk.StringVar, filetypes: list):
        """Abrir diálogo para guardar archivo"""
        initial_dir = ""
        if self.file_path.get():
            initial_dir = os.path.dirname(self.file_path.get())
        
        filepath = filedialog.asksaveasfilename(
            title="Guardar archivo",
            filetypes=filetypes + [("Todos", "*.*")],
            initialdir=initial_dir
        )
        if filepath:
            var.set(filepath)
    
    def browse_directory(self, var: tk.StringVar):
        """Abrir diálogo para seleccionar directorio"""
        directory = filedialog.askdirectory(title="Seleccionar directorio")
        if directory:
            var.set(directory)
    
    def select_batch_files(self, single: bool = False):
        """Selecciona archivos para procesamiento batch"""
        def handler():
            if single:
                filepath = filedialog.askopenfilename(
                    title="Seleccionar archivo PDF",
                    filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")]
                )
                if filepath:
                    self.batch_vars['file_paths'] = [filepath]
            else:
                filepaths = filedialog.askopenfilenames(
                    title="Seleccionar archivos PDF",
                    filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")]
                )
                if filepaths:
                    self.batch_vars['file_paths'] = list(filepaths)
            
            self.update_files_display()
            
            # Analyze and show recommendations if needed
            if self.batch_vars['file_paths']:
                self.analyze_batch_files()
        
        return handler
    
    def analyze_batch_files(self):
        """Analiza archivos seleccionados para batch"""
        if not self.init_ocr_client():
            return
        
        files = self.batch_vars['file_paths']
        
        if len(files) == 1:
            # Single file - show split recommendations
            file_info = self.file_processor.analyze_file(files[0])
            if file_info and file_info['pages']:
                self.show_batch_recommendations(files[0], file_info['pages'])
        elif len(files) > 1:
            # Multiple files - show multi-batch analysis
            try:
                summary = analyze_multiple_pdfs(files)
                self.show_multi_batch_analysis(summary)
            except Exception as e:
                logger.error(f"Error analyzing multiple files: {e}")
                messagebox.showerror("Error", f"Error al analizar archivos: {str(e)}")
    
    def clear_file_list(self):
        """Limpia la lista de archivos"""
        self.batch_vars['file_paths'] = []
        self.update_files_display()
    
    def update_files_display(self):
        """Actualiza la visualización de archivos seleccionados"""
        # Clear current list
        for widget in self.files_list_frame.winfo_children():
            widget.destroy()
        
        files = self.batch_vars['file_paths']
        
        if not files:
            self.files_status_label.configure(
                text="No hay archivos seleccionados", text_color="gray60"
            )
            return
        
        # Update status
        total_size = sum(
            Path(f).stat().st_size / (1024 * 1024) for f in files
        )
        
        status_text = f"{len(files)} archivo{'s' if len(files) > 1 else ''} | {total_size:.1f} MB total"
        self.files_status_label.configure(text=status_text, text_color="green")
        
        # Display files
        for i, file_path in enumerate(files):
            file_frame = ctk.CTkFrame(self.files_list_frame)
            file_frame.pack(fill="x", padx=5, pady=2)
            
            ctk.CTkLabel(
                file_frame, text=f"{i+1}.",
                font=ctk.CTkFont(weight="bold")
            ).pack(side="left", padx=5)
            
            ctk.CTkLabel(
                file_frame, text=os.path.basename(file_path)
            ).pack(side="left", fill="x", expand=True, padx=5)
            
            try:
                size_mb = Path(file_path).stat().st_size / (1024 * 1024)
                ctk.CTkLabel(
                    file_frame, text=f"{size_mb:.1f} MB",
                    text_color="gray60"
                ).pack(side="right", padx=5)
            except:
                pass
            
            ctk.CTkButton(
                file_frame, text="✖", width=30,
                command=lambda idx=i: self.remove_file(idx),
                fg_color="red", hover_color="darkred"
            ).pack(side="right", padx=5)
        
        # Suggest output directory
        if files:
            base_dir = os.path.dirname(files[0])
            if len(files) == 1:
                base_name = os.path.splitext(os.path.basename(files[0]))[0] + "_lotes"
            else:
                base_name = "procesamiento_lotes"
            self.batch_vars['output_dir'].set(os.path.join(base_dir, base_name))
    
    def remove_file(self, index: int):
        """Elimina un archivo de la lista"""
        if 0 <= index < len(self.batch_vars['file_paths']):
            self.batch_vars['file_paths'].pop(index)
            self.update_files_display()
    
    # --- Event Handlers ---
    
    # Método eliminado - funcionalidad integrada en selección de archivos para procesamiento
    
    # Método eliminado - ahora se usa directorio de salida unificado
    
    # --- Processing Methods ---
    
    def init_ocr_client(self) -> bool:
        """Inicializar cliente OCR si es necesario"""
        if not self.ocr_client and self.api_key.get():
            try:
                self.ocr_client = MistralOCRClient(api_key=self.api_key.get())
                self.file_processor = FileProcessor(self.ocr_client, self)
                return True
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo inicializar el cliente: {str(e)}")
                return False
        return bool(self.ocr_client)
    
    # Método eliminado - ahora todo usa start_processing()
    
    # Método eliminado - ahora se guarda desde el procesamiento unificado
    
    # Método eliminado - ahora se muestra desde el procesamiento unificado
    
    def update_preview(self):
        """Actualizar vista previa del documento"""
        if self.ocr_response:
            self.preview_manager.show_preview(self.ocr_response, self.view_mode.get())
    
    def save_current_view(self):
        """Guardar vista actual"""
        if not self.ocr_response:
            messagebox.showerror("Error", "No hay documento para guardar")
            return
        
        mode = self.view_mode.get()
        
        if mode == "Markdown":
            ext, filetypes = ".md", [("Markdown", "*.md")]
        elif mode == "HTML":
            ext, filetypes = ".html", [("HTML", "*.html")]
        else:
            ext, filetypes = ".txt", [("Texto", "*.txt")]
        
        filepath = filedialog.asksaveasfilename(
            title=f"Guardar como {mode}",
            defaultextension=ext,
            filetypes=filetypes + [("Todos", "*.*")]
        )
        
        if filepath:
            try:
                content = self.source_text.get(1.0, tk.END)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Guardado", f"Vista guardada en: {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar: {str(e)}")
    
    def reset_ui(self):
        """Restaurar estado de la interfaz"""
        self.process_btn.configure(state="normal", text="Iniciar procesamiento")
        self.progress_bar.set(0)
        self.processing = False
    
    # --- Compression and Split Methods ---
    
    def compress_file(self):
        """Comprimir archivo PDF seleccionado"""
        if not self.file_path.get():
            messagebox.showerror("Error", "Seleccione un archivo PDF primero")
            return
        
        mime_type, _ = mimetypes.guess_type(self.file_path.get())
        if mime_type != 'application/pdf':
            messagebox.showerror("Error", "Solo se pueden comprimir archivos PDF")
            return
        
        if not self.init_ocr_client():
            return
        
        self.ui_updater.update_status("Comprimiendo PDF...")
        
        thread = threading.Thread(target=self._compress_thread)
        thread.daemon = True
        thread.start()
    
    def _compress_thread(self):
        """Thread para comprimir archivo"""
        try:
            quality = self.config_vars['compression_quality'].get()
            compressed = self.ocr_client.compress_pdf(self.file_path.get(), quality=quality)
            
            # Update selected file
            self.file_path.set(str(compressed))
            self.on_file_selected(str(compressed))
            
            self.ui_updater.update_status("PDF comprimido guardado")
            messagebox.showinfo("Éxito", "PDF comprimido exitosamente")
            
        except Exception as e:
            logger.error(f"Error compressing: {str(e)}")
            messagebox.showerror("Error", f"Error al comprimir: {str(e)}")
            self.ui_updater.update_status("Error al comprimir")
    
    def split_file(self):
        """Dividir archivo PDF seleccionado"""
        if not self.file_path.get():
            messagebox.showerror("Error", "Seleccione un archivo PDF primero")
            return
        
        mime_type, _ = mimetypes.guess_type(self.file_path.get())
        if mime_type != 'application/pdf':
            messagebox.showerror("Error", "Solo se pueden dividir archivos PDF")
            return
        
        if not self.init_ocr_client():
            return
        
        self.ui_updater.update_status("Dividiendo PDF...")
        
        thread = threading.Thread(target=self._split_thread)
        thread.daemon = True
        thread.start()
    
    def _split_thread(self):
        """Thread para dividir archivo"""
        try:
            max_pages = self.batch_vars['max_pages'].get()
            split_info = self.ocr_client.split_pdf(
                self.file_path.get(), max_pages_per_file=max_pages
            )
            
            files_str = "\n".join([str(f) for f in split_info['files']])
            messagebox.showinfo(
                "División completada",
                f"PDF dividido en {len(split_info['files'])} archivos:\n\n{files_str}"
            )
            
            # Select first file
            if split_info['files']:
                self.file_path.set(str(split_info['files'][0]))
                self.on_file_selected(str(split_info['files'][0]))
            
            self.ui_updater.update_status("PDF dividido exitosamente")
            
        except Exception as e:
            logger.error(f"Error splitting: {str(e)}")
            messagebox.showerror("Error", f"Error al dividir: {str(e)}")
            self.ui_updater.update_status("Error al dividir")
    
    # --- Batch Processing Methods ---
    
    def start_processing(self):
        """Iniciar procesamiento por lotes"""
        # Validations
        if not self.api_key.get().strip():
            messagebox.showerror("Error", "Ingrese una API Key de Mistral")
            return
        
        if not self.batch_vars['file_paths']:
            messagebox.showerror("Error", "Seleccione al menos un archivo PDF")
            return
        
        if not self.batch_vars['output_dir'].get():
            messagebox.showerror("Error", "Seleccione un directorio de salida")
            return
        
        # Check selected formats
        formats = [k for k, v in self.batch_vars['formats'].items() if v.get()]
        if not formats:
            messagebox.showerror("Error", "Seleccione al menos un formato de salida")
            return
        
        # Confirm
        if not messagebox.askyesno(
            "Confirmar",
            "¿Iniciar procesamiento por lotes? Esto puede tardar varios minutos."
        ):
            return
        
        # Prepare UI
        self.process_btn.configure(state="disabled", text="Procesando...")
        self.progress_bar.set(0)
        self.progress_status.configure(text="Iniciando procesamiento...")
        self.ui_updater.set_text(self.results_text, "Iniciando procesamiento por lotes...\n")
        
        # Execute in thread
        thread = threading.Thread(target=self._processing_thread)
        thread.daemon = True
        thread.start()
    
    def _processing_thread(self):
        """Thread de procesamiento por lotes"""
        try:
            if not self.init_ocr_client():
                return
            
            # Get configuration
            config = ProcessingConfig(
                api_key=self.api_key.get(),
                model=self.model.get(),
                max_size_mb=self.batch_vars['max_size'].get(),
                max_pages=self.batch_vars['max_pages'].get(),
                output_formats=[k for k, v in self.batch_vars['formats'].items() if v.get()],
                optimize=self.batch_vars['optimize']['enabled'].get(),
                optimization_domain=self.batch_vars['optimize']['domain'].get()
            )
            
            input_files = self.batch_vars['file_paths']
            output_dir = self.batch_vars['output_dir'].get()
            
            # Create directory if needed
            os.makedirs(output_dir, exist_ok=True)
            
            # Process each input file
            all_files_to_process = []
            current_page_offset = 0
            
            self.ui_updater.append_to_text(
                self.results_text,
                f"Preparando {len(input_files)} archivo(s) para procesamiento...\n\n"
            )
            
            for file_idx, file_path in enumerate(input_files):
                self.ui_updater.append_to_text(
                    self.results_text,
                    f"{file_idx + 1}. {os.path.basename(file_path)}\n"
                )
                
                # Get file info
                file_info = self.file_processor.analyze_file(file_path)
                if file_info:
                    # Process with split if needed - with error handling
                    try:
                        files = self.file_processor.process_with_split(file_info, config)
                        
                        # Debug logging
                        logger.info(f"Archivo {file_idx + 1}: {len(files)} archivos generados por process_with_split")
                        for idx, f in enumerate(files):
                            logger.info(f"  - Archivo {idx + 1}: {f['file_path']} ({f.get('pages', 'N/A')} páginas)")
                        
                        self.ui_updater.append_to_text(
                            self.results_text,
                            f"   → {len(files)} archivo(s) preparado(s) para procesamiento\n"
                        )
                        
                        if not files:
                            self.ui_updater.append_to_text(
                                self.results_text,
                                f"   ⚠️ No se generaron archivos para procesar (posible cancelación)\n"
                            )
                            continue
                        
                        # Asignar page_offset incremental a cada archivo dividido
                        for file_dict in files:
                            file_dict.update({
                                'page_offset': current_page_offset,
                                'file_index': file_idx
                            })
                            all_files_to_process.append(file_dict)
                            
                            # Incrementar offset con las páginas de ESTA parte específica
                            if 'pages' in file_dict and file_dict['pages'] is not None:
                                current_page_offset += file_dict['pages']
                            
                    except Exception as e:
                        self.ui_updater.append_to_text(
                            self.results_text,
                            f"   ❌ Error procesando archivo: {str(e)}\n"
                        )
                        logger.error(f"Error en process_with_split: {e}")
                        continue
                else:
                    self.ui_updater.append_to_text(
                        self.results_text,
                        f"   ❌ No se pudo analizar el archivo\n"
                    )
            
            total_files = len(all_files_to_process)
            
            # Debug logging final
            logger.info(f"=== RESUMEN FINAL ===")
            logger.info(f"Total archivos en all_files_to_process: {total_files}")
            for idx, f in enumerate(all_files_to_process):
                logger.info(f"  Final {idx + 1}: {f['file_path']} (offset: {f.get('page_offset', 'N/A')})")
            
            self.ui_updater.append_to_text(
                self.results_text,
                f"\n📊 RESUMEN PRE-PROCESAMIENTO:\n"
                f"   Total archivos a procesar: {total_files}\n"
                f"   Archivos originales: {len(input_files)}\n\n"
            )
            
            if total_files == 0:
                self.ui_updater.append_to_text(
                    self.results_text,
                    f"❌ No hay archivos para procesar. Verifique la validación post-división.\n"
                )
                return
            
            # Process with optimizer if enabled
            if self.auto_optimize.get():
                results = self._process_with_optimizer(
                    all_files_to_process, config, output_dir
                )
            else:
                results = self._process_traditional(
                    all_files_to_process, config, output_dir
                )
            
            # Show summary
            self._show_batch_summary(results)
            
            self.ui_updater.update_progress(
                self.progress_bar, 1.0, self.progress_status,
                "Procesamiento completado"
            )
            
            messagebox.showinfo(
                "Completado",
                f"Procesamiento completado\n"
                f"Exitosos: {len(results['success'])}\n"
                f"Fallidos: {len(results['failed'])}"
            )
            
        except Exception as e:
            logger.error(f"Error in batch: {str(e)}")
            self.ui_updater.append_to_text(
                self.results_text,
                f"\nERROR CRÍTICO: {str(e)}\n"
            )
            messagebox.showerror("Error", f"Error en procesamiento: {str(e)}")
            
        finally:
            self.after(100, lambda: self.process_btn.configure(
                state="normal", text="Iniciar procesamiento"
            ))
    
    def _process_with_optimizer(self, files, config, output_dir):
        """Procesa archivos usando el optimizador"""
        self.ui_updater.append_to_text(
            self.results_text,
            "⚡ Usando procesamiento optimizado...\n\n"
        )
        
        total_size = sum(
            self.file_processor.analyze_file(f['file_path'])['size_mb'] 
            for f in files
        )
        
        # Create optimizer
        optimizer = create_optimized_processor(
            self.ocr_client, len(files), total_size
        )
        
        # Progress callback
        def progress_callback(completed, total):
            self.ui_updater.update_progress(
                self.progress_bar,
                completed / total if total > 0 else 0,
                self.progress_status,
                f"Procesando {completed}/{total}"
            )
        
        # Configuration for optimizer
        opt_config = {
            'model': config.model,
            'include_images': True,
            'output_dir': output_dir,
            'save_md': 'md' in config.output_formats,
            'save_txt': 'txt' in config.output_formats,
            'save_html': 'html' in config.output_formats,
            'save_images': 'images' in config.output_formats
        }
        
        # Process with optimizations
        results = optimizer.process_files_optimized(
            files, opt_config, progress_callback
        )
        
        # Convert format for compatibility
        converted_results = {'success': [], 'failed': []}
        
        for item in results['success']:
            converted_results['success'].append({
                'file': item['file'],
                'original_file': item.get('original_file', item['file']),
                'pages': item.get('metrics', type('', (), {'pages_count': 0})).pages_count,
                'page_offset': item.get('page_offset', 0)
            })
        
        converted_results['failed'] = results['failed']
        
        return converted_results
    
    def _process_traditional(self, files, config, output_dir):
        """Procesa archivos usando el método tradicional"""
        self.ui_updater.append_to_text(
            self.results_text,
            "Usando procesamiento tradicional...\n\n"
        )
        
        results = {'success': [], 'failed': []}
        total_files = len(files)
        
        for i, file_info in enumerate(files):
            file_path = file_info['file_path']
            original_file = file_info['original_file']
            page_offset = file_info['page_offset']
            
            # Show progress
            progress_text = f"Procesando {os.path.basename(file_path)} ({i+1}/{total_files})"
            if file_path != original_file:
                progress_text += f" [Parte de {os.path.basename(original_file)}]"
            
            self.ui_updater.update_progress(
                self.progress_bar,
                i / total_files if total_files > 0 else 0,
                self.progress_status,
                progress_text
            )
            
            try:
                # Process file
                response = self.ocr_client.process_local_file(
                    file_path, model=config.model, include_images=True
                )
                
                # Save in selected formats with page numbering
                original_base_name = os.path.splitext(os.path.basename(original_file))[0]
                
                # Calculate page ranges for this file
                start_page = page_offset + 1
                end_page = page_offset + len(response.pages)
                
                # Create descriptive base name with page range
                if len(files) > 1:
                    base_name = f"{original_base_name}_pag{start_page:04d}-{end_page:04d}"
                else:
                    base_name = original_base_name
                
                if 'md' in config.output_formats:
                    path = os.path.join(output_dir, f"{base_name}.md")
                    self.ocr_client.save_as_markdown(
                        response, path, page_offset,
                        optimize=config.optimize,
                        domain=config.optimization_domain
                    )
                
                if 'txt' in config.output_formats:
                    path = os.path.join(output_dir, f"{base_name}.txt")
                    self.ocr_client.save_text(
                        response, path, page_offset,
                        optimize=config.optimize,
                        domain=config.optimization_domain
                    )
                
                if 'images' in config.output_formats:
                    images_dir = os.path.join(output_dir, f"{base_name}_imagenes")
                    self.ocr_client.save_images(response, images_dir, page_offset)
                
                results['success'].append({
                    'file': file_path,
                    'original_file': original_file,
                    'pages': len(response.pages),
                    'page_offset': page_offset
                })
                
                self.ui_updater.append_to_text(
                    self.results_text,
                    f"✓ Procesado: {os.path.basename(file_path)}\n"
                )
                
            except Exception as e:
                results['failed'].append({
                    'file': file_path,
                    'original_file': original_file,
                    'error': str(e)
                })
                self.ui_updater.append_to_text(
                    self.results_text,
                    f"✗ Error en {os.path.basename(file_path)}: {str(e)}\n"
                )
        
        return results
    
    def _show_batch_summary(self, results):
        """Muestra resumen unificado de procesamiento batch"""
        total_pages = sum(item['pages'] for item in results['success'])
        original_files = len(set(item['original_file'] for item in results['success']))
        
        summary = f"\n{'='*60}\nRESUMEN DE PROCESAMIENTO\n{'='*60}\n"
        
        if original_files > 1:
            summary += f"Archivos originales: {original_files}\n"
        
        summary += f"Archivos procesados: {len(results['success'])}\n"
        summary += f"Archivos fallidos: {len(results['failed'])}\n"
        summary += f"Total de páginas: {total_pages}\n"
        
        # Group by original file if multiple
        if original_files > 1:
            by_original = {}
            for item in results['success']:
                original = item['original_file']
                if original not in by_original:
                    by_original[original] = []
                by_original[original].append(item)
            
            if by_original:
                summary += f"\nDetalles por archivo original:\n"
                for original_file, items in by_original.items():
                    total_pages_file = sum(item['pages'] for item in items)
                    summary += f"  ✓ {os.path.basename(original_file)}: {len(items)} parte(s), {total_pages_file} páginas\n"
        
        if results['failed']:
            summary += f"\nArchivos con errores:\n"
            for fail in results['failed']:
                summary += f"  ✗ {os.path.basename(fail['file'])}: {fail['error']}\n"
        
        summary += f"\nResultados guardados en: {self.batch_vars['output_dir'].get()}\n"
        summary += f"\n✅ Procesamiento completado exitosamente\n"
        
        self.ui_updater.append_to_text(self.results_text, summary)
    
    def show_batch_recommendations(self, filepath, pages_count):
        """Muestra ventana con recomendaciones de división"""
        # Analyze file
        analysis, recommendations = analyze_and_recommend(filepath, pages_count)
        
        # Prepare file info
        file_info = {
            'path': filepath,
            'pages': pages_count,
            'size_mb': analysis.total_size_mb
        }
        
        # Show split control dialog for files that need splitting
        if analysis.requires_splitting and recommendations:
            self.ui_updater.append_to_text(
                self.results_text,
                f"\n⚠️ Archivo excede límites - Mostrando opciones de división...\n"
            )
            
            # Show advanced split dialog with validation support
            validation_summary = None
            if hasattr(self, 'validation_summary'):
                validation_summary = self.validation_summary
            
            dialog_result = show_advanced_split_dialog(self, analysis, recommendations, validation_summary)
            
            if dialog_result and dialog_result.action == 'split':
                # User chose to split with interactive controls
                num_files = dialog_result.num_files
                pages_per_file = dialog_result.pages_per_file
                mb_per_file = analysis.total_size_mb / num_files
                
                # Update configuration to force exact number of files
                # Calculate pages per file to get exactly the requested number of files
                calculated_pages_per_file = math.ceil(analysis.total_pages / num_files)
                self.batch_vars['max_pages'].set(calculated_pages_per_file)
                
                # Store the target number of files for process_with_split to use
                self.target_files_from_modal = num_files
                
                # Show detailed feedback
                config_type = "🤖 Automática" if dialog_result.auto_adjust_applied else "👤 Personalizada"
                self.ui_updater.append_to_text(
                    self.results_text,
                    f"\n✅ División configurada ({config_type}):\n"
                    f"- Dividir en {num_files} archivos\n"
                    f"- {pages_per_file} páginas por archivo\n"
                    f"- ~{mb_per_file:.1f} MB por archivo\n"
                    f"- Configuración: {'Auto-ajustada' if dialog_result.auto_adjust_applied else 'Modificada por usuario'}\n\n"
                )
                
            elif dialog_result and dialog_result.action == 'no_split':
                # User chose to process without splitting
                self.ui_updater.append_to_text(
                    self.results_text,
                    f"\n⚠️ Procesando SIN división (RIESGO):\n"
                    f"- Tamaño: {analysis.total_size_mb:.1f} MB\n"
                    f"- Páginas: {analysis.total_pages}\n"
                    f"- Puede causar errores o timeouts\n\n"
                )
                # Set very high limits to avoid automatic splitting
                self.batch_vars['max_pages'].set(analysis.total_pages + 100)
                self.batch_vars['max_size'].set(analysis.total_size_mb + 50)
                
            else:
                # User cancelled or other action
                action = dialog_result.action if dialog_result else 'cancel'
                self.ui_updater.append_to_text(
                    self.results_text,
                    f"\n❌ Operación cancelada por el usuario ({action})\n\n"
                )
                return
        else:
            # File doesn't require splitting
            self.ui_updater.append_to_text(
                self.results_text,
                f"\n✅ El archivo puede procesarse sin división\n"
                f"- Tamaño: {analysis.total_size_mb:.1f} MB\n"
                f"- Páginas: {pages_count}\n\n"
            )
    
    def show_post_split_validation_modal(self, summary, validator, file_info, config):
        """Mostrar modal de validación post-división en el hilo principal"""
        try:
            from post_split_validation_dialog import show_post_split_validation_dialog
            
            result = show_post_split_validation_dialog(self, summary, validator)
            
            if result and result.action == 'auto_adjust':
                # Continuar procesamiento con ajuste automático
                self.ui_updater.append_to_text(
                    self.results_text,
                    f"\n🤖 Ajuste automático aplicado: {result.adjusted_summary.new_file_count} archivos\n"
                )
                # Reiniciar procesamiento con nuevos parámetros
                self.continue_processing_after_validation(result.adjusted_summary, file_info, config)
            
            elif result and result.action == 'proceed_anyway':
                # Continuar con archivos problemáticos
                self.ui_updater.append_to_text(
                    self.results_text,
                    f"\n⚠️ Usuario eligió proceder con archivos que exceden límites (RIESGOSO)\n"
                )
                # Continuar procesamiento original
                self.continue_processing_anyway(summary, file_info, config)
            
            else:
                # Usuario canceló
                self.ui_updater.append_to_text(
                    self.results_text,
                    f"\n❌ Procesamiento cancelado por el usuario\n"
                )
        
        except Exception as e:
            logger.error(f"Error en modal post-validación: {e}")
            self.ui_updater.append_to_text(
                self.results_text,
                f"\n❌ Error en validación: {str(e)}\n"
            )
    
    def continue_processing_after_validation(self, adjusted_summary, file_info, config):
        """Continuar procesamiento después de validación exitosa"""
        # Implementar lógica para continuar con archivos ajustados
        pass
    
    def continue_processing_anyway(self, summary, file_info, config):
        """Continuar procesamiento con archivos problemáticos"""
        # Implementar lógica para continuar con archivos originales (riesgoso)
        pass
    
    def show_multi_batch_analysis(self, summary):
        """Muestra ventana con análisis de múltiples archivos"""
        # Create dialog window
        dialog = ctk.CTkToplevel(self)
        dialog.title("Análisis de Múltiples Archivos")
        dialog.geometry("800x700")
        dialog.transient(self)
        dialog.grab_set()
        
        # Main frame with scroll
        main_frame = ctk.CTkScrollableFrame(dialog)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title and summary
        ctk.CTkLabel(
            main_frame,
            text="📁 ANÁLISIS DE PROCESAMIENTO MÚLTIPLE",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(0, 15))
        
        summary_text = f"""Archivos: {len(summary.files)}
Tamaño total: {summary.total_size_mb:.1f} MB
Páginas totales: {summary.total_pages}
Archivos estimados tras división: {summary.total_estimated_files}
Tiempo estimado: {summary.processing_time_estimate:.1f} minutos"""
        
        ctk.CTkLabel(
            main_frame, text=summary_text, justify="left",
            font=ctk.CTkFont(size=12)
        ).pack(padx=20, pady=15)
        
        # File details
        for entry in summary.files:
            if entry.analysis:
                file_frame = ctk.CTkFrame(main_frame)
                file_frame.pack(fill="x", pady=5, padx=10)
                
                info_text = f"📁 {entry.display_name}\n"
                info_text += f"  {entry.analysis.total_size_mb:.1f} MB | {entry.analysis.total_pages} páginas"
                
                if entry.recommendation and entry.recommendation.num_files > 1:
                    info_text += f"\n  → Dividir en {entry.recommendation.num_files} partes"
                
                ctk.CTkLabel(
                    file_frame, text=info_text, justify="left",
                    font=ctk.CTkFont(size=11)
                ).pack(padx=10, pady=5, anchor="w")
        
        # Action buttons
        def apply_config():
            if summary.files:
                max_pages = max(
                    (e.recommendation.pages_per_file for e in summary.files
                     if e.recommendation and e.recommendation.num_files > 1),
                    default=150
                )
                self.batch_vars['max_pages'].set(max_pages)
                self.ui_updater.append_to_text(
                    self.results_text,
                    f"\n🎯 Configuración aplicada para {len(summary.files)} archivos\n"
                )
            dialog.destroy()
        
        ctk.CTkButton(
            main_frame, text="Aplicar configuración",
            command=apply_config,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=20)
        
        # Center window
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
    
    def estimate_processing_time(self):
        """Estima el tiempo de procesamiento"""
        if not self.batch_vars['file_paths']:
            messagebox.showinfo("Info", "Seleccione archivos primero")
            return
        
        try:
            # Create file info for estimation
            files_info = []
            for file_path in self.batch_vars['file_paths']:
                path = Path(file_path)
                size_mb = path.stat().st_size / (1024 * 1024)
                files_info.append({
                    'file_path': file_path,
                    'size_mb': size_mb
                })
            
            # Estimate time
            estimated_seconds, time_description = estimate_batch_time(files_info)
            
            # Show estimation
            total_size = sum(info['size_mb'] for info in files_info)
            
            messagebox.showinfo(
                "Estimación de Tiempo",
                f"Archivos: {len(files_info)}\n"
                f"Tamaño total: {total_size:.1f} MB\n\n"
                f"Tiempo estimado: {time_description}\n\n"
                f"Nota: El tiempo real puede variar según la carga de la API."
            )
            
        except Exception as e:
            logger.error(f"Error estimating time: {str(e)}")
            messagebox.showerror("Error", f"Error al estimar tiempo: {str(e)}")
    
    # --- Utility Methods ---
    
    # Método eliminado - no necesario en procesamiento unificado
    
    def validate_all_numeric_inputs(self):
        """Validar todas las entradas numéricas"""
        validations = [
            (self.batch_vars['max_pages'], DEFAULT_PAGES_PER_SPLIT),
            (self.batch_vars['max_size'], MAX_FILE_SIZE_MB),
            (self.batch_vars['max_pages'], MAX_PAGES_PER_FILE),
            (self.batch_vars['workers'], DEFAULT_WORKERS)
        ]
        
        for var, default in validations:
            try:
                value = var.get()
                if not value or float(value) <= 0:
                    var.set(default)
            except (ValueError, tk.TclError):
                var.set(default)
    
    def show_placeholder(self, text: str):
        """Mostrar placeholder en área de previsualización"""
        for widget in self.preview_container.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(
            self.preview_container, text=text,
            font=ctk.CTkFont(size=14), height=300
        ).pack(expand=True)


if __name__ == "__main__":
    app = MistralOCRApp()
    app.mainloop()