#!/usr/bin/env python3
"""
Split Control Dialog - Modal Interactivo de División Automática
===============================================================
Diálogo modal COMPLETO para control interactivo de división automática.
Incluye controles para modificar número de archivos, validación en tiempo real,
y opciones avanzadas de ajuste automático.

Versión: 2.0.0 - Sistema Completo Restaurado  
Funcionalidad: Modal interactivo con controles avanzados
"""

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from typing import List, Optional, Callable, Dict
from dataclasses import dataclass
import math
from pathlib import Path
from batch_optimizer import SplitRecommendation, PDFAnalysis
from pdf_split_validator import PDFSplitValidator, ValidationSummary
from processing_limits import LIMITS

@dataclass
class InteractiveSplitResult:
    """Resultado del diálogo interactivo"""
    action: str  # 'split', 'no_split', 'cancel', 'auto_adjust'
    num_files: Optional[int] = None
    pages_per_file: Optional[int] = None
    validation_summary: Optional[ValidationSummary] = None
    user_modified: bool = False
    auto_adjust_applied: bool = False

class AdvancedSplitControlDialog(ctk.CTkToplevel):
    """Diálogo modal COMPLETO e interactivo para división automática"""
    
    def __init__(self, parent, analysis: PDFAnalysis, recommendations: List[SplitRecommendation], 
                 validation_summary: Optional[ValidationSummary] = None):
        super().__init__(parent)
        
        self.analysis = analysis
        self.recommendations = recommendations
        self.validation_summary = validation_summary
        self.result = None
        
        # Variables de control interactivo con validación mejorada
        default_num_files = recommendations[0].num_files if recommendations and len(recommendations) > 0 else 3
        default_pages_per_file = recommendations[0].pages_per_file if recommendations and len(recommendations) > 0 else max(100, int(analysis.total_pages / default_num_files))
        
        # Asegurar valores válidos
        default_num_files = max(1, min(20, int(default_num_files)))
        default_pages_per_file = max(10, min(1000, int(default_pages_per_file)))
        
        # Crear variables con valores iniciales válidos
        self.num_files_var = tk.IntVar(value=default_num_files)
        self.pages_per_file_var = tk.IntVar(value=default_pages_per_file)
        self.auto_adjust_var = tk.BooleanVar(value=True)
        self.show_validation_var = tk.BooleanVar(value=bool(validation_summary))
        
        # Variables para controlar callbacks durante inicialización
        self._initializing = True
        self._updating = False
        
        # Variables calculadas
        self.estimated_mb_per_file = tk.DoubleVar()
        self.efficiency_score = tk.DoubleVar()
        self.total_estimated_size = tk.DoubleVar()
        
        self.setup_window()
        self.create_widgets()
        self.update_calculations()
        
        # Modal behavior
        self.transient(parent)
        self.grab_set()
        self.focus_set()
        
        # Center on parent
        self.geometry("800x700")
        self.center_on_parent(parent)
        
        # Bind events después de completar inicialización
        self.after_idle(self._setup_event_bindings)
        
        # Wait for user response
        self.wait_window()
    
    def setup_window(self):
        """Configurar la ventana del diálogo"""
        self.title("🔧 Control Avanzado de División Automática")
        self.resizable(True, True)
        
        # Configurar grid principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # Content area expandible
    
    def center_on_parent(self, parent):
        """Centrar el diálogo sobre la ventana padre"""
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (800 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (700 // 2)
        self.geometry(f"800x700+{x}+{y}")
    
    def create_widgets(self):
        """Crear todos los widgets del diálogo"""
        self.create_header()
        self.create_file_info_section()
        self.create_interactive_controls()
        self.create_validation_section()
        self.create_buttons()
    
    def create_header(self):
        """Crear el encabezado con información crítica"""
        header_frame = ctk.CTkFrame(self)
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Icon grande y llamativo
        icon_label = ctk.CTkLabel(
            header_frame, 
            text="⚠️", 
            font=ctk.CTkFont(size=32, weight="bold")
        )
        icon_label.grid(row=0, column=0, padx=(20, 15), pady=20, rowspan=2)
        
        # Título principal
        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=(20, 5))
        title_frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(
            title_frame,
            text="ARCHIVO EXCEDE LÍMITES - CONTROL DE DIVISIÓN",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="orange"
        )
        title_label.grid(row=0, column=0, sticky="w")
        
        # Mensaje explicativo
        message_label = ctk.CTkLabel(
            title_frame,
            text="Configure la división óptima o aplique ajuste automático para procesar el archivo.",
            font=ctk.CTkFont(size=13),
            text_color="gray70"
        )
        message_label.grid(row=1, column=0, sticky="w", pady=(3, 0))
        
        # Status badge
        if self.validation_summary and not self.validation_summary.all_within_limits:
            status_label = ctk.CTkLabel(
                header_frame,
                text="🚨 VALIDACIÓN REQUERIDA",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="red",
                fg_color="darkred",
                corner_radius=15
            )
            status_label.grid(row=0, column=2, padx=(0, 20), pady=20, sticky="ne")
    
    def create_file_info_section(self):
        """Crear sección con información detallada del archivo"""
        info_frame = ctk.CTkFrame(self)
        info_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        info_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # Título de sección
        section_title = ctk.CTkLabel(
            info_frame,
            text="📋 INFORMACIÓN DEL ARCHIVO",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        section_title.grid(row=0, column=0, columnspan=4, pady=(15, 10))
        
        # Cards de información
        file_name = self.analysis.file_path.name
        if len(file_name) > 35:
            file_name = file_name[:32] + "..."
        
        cards_data = [
            ("📄", "Archivo", file_name, "blue"),
            ("📏", "Tamaño", f"{self.analysis.total_size_mb:.1f} MB", "orange"),
            ("📑", "Páginas", f"{self.analysis.total_pages:,}", "green"),
            ("⚡", "Densidad", f"{self.analysis.density_mb_per_page:.2f} MB/pág", "purple")
        ]
        
        for i, (icon, label, value, color) in enumerate(cards_data):
            self.create_info_card(info_frame, i, icon, label, value, color)
    
    def create_info_card(self, parent, col, icon, label, value, color):
        """Crear tarjeta de información"""
        card_frame = ctk.CTkFrame(parent, fg_color=f"gray20")
        card_frame.grid(row=1, column=col, padx=8, pady=(0, 15), sticky="ew", ipady=10)
        
        icon_label = ctk.CTkLabel(card_frame, text=icon, font=ctk.CTkFont(size=20))
        icon_label.pack(pady=(8, 2))
        
        label_label = ctk.CTkLabel(
            card_frame, 
            text=label, 
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="gray60"
        )
        label_label.pack()
        
        value_label = ctk.CTkLabel(
            card_frame, 
            text=value, 
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=color
        )
        value_label.pack(pady=(1, 8))
    
    def create_interactive_controls(self):
        """Crear los controles interactivos principales"""
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        controls_frame.grid_columnconfigure((0, 1), weight=1)
        controls_frame.grid_rowconfigure(2, weight=1)
        
        # Título de controles
        controls_title = ctk.CTkLabel(
            controls_frame,
            text="🎛️ CONTROLES INTERACTIVOS DE DIVISIÓN",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        controls_title.grid(row=0, column=0, columnspan=2, pady=(15, 20))
        
        # Panel izquierdo - Controles principales
        left_panel = ctk.CTkFrame(controls_frame)
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(15, 10), pady=(0, 15))
        left_panel.grid_columnconfigure(1, weight=1)
        
        self.create_main_controls(left_panel)
        
        # Panel derecho - Información en tiempo real
        right_panel = ctk.CTkFrame(controls_frame)
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(10, 15), pady=(0, 15))
        
        self.create_realtime_info(right_panel)
        
        # Panel inferior - Opciones preestablecidas
        options_panel = ctk.CTkFrame(controls_frame)
        options_panel.grid(row=2, column=0, columnspan=2, sticky="ew", padx=15, pady=(10, 15))
        
        self.create_preset_options(options_panel)
    
    def create_main_controls(self, parent):
        """Crear controles principales"""
        # Título del panel
        panel_title = ctk.CTkLabel(
            parent,
            text="🔧 Configuración de División",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        panel_title.grid(row=0, column=0, columnspan=2, pady=(15, 20))
        
        # Control de número de archivos
        files_label = ctk.CTkLabel(parent, text="📊 Número de archivos:", font=ctk.CTkFont(size=12, weight="bold"))
        files_label.grid(row=1, column=0, sticky="w", padx=(15, 10), pady=(0, 5))
        
        files_frame = ctk.CTkFrame(parent, fg_color="transparent")
        files_frame.grid(row=1, column=1, sticky="ew", padx=(0, 15), pady=(0, 5))
        files_frame.grid_columnconfigure(1, weight=1)
        
        # Slider para número de archivos
        self.files_slider = ctk.CTkSlider(
            files_frame,
            from_=1,
            to=20,
            number_of_steps=19,
            width=200
        )
        self.files_slider.grid(row=0, column=1, sticky="ew", padx=(10, 10))
        self.files_slider.set(self.num_files_var.get())
        
        # Entry para valor exacto
        self.files_entry = ctk.CTkEntry(files_frame, width=60)
        self.files_entry.grid(row=0, column=2, padx=(5, 0))
        self.files_entry.insert(0, str(self.num_files_var.get()))
        
        # Bind manual events para slider y entry
        self.files_slider.configure(command=self._on_files_slider_changed)
        self.files_entry.bind('<KeyRelease>', self._on_files_entry_changed)
        self.files_entry.bind('<FocusOut>', self._on_files_entry_changed)
        
        # Control de páginas por archivo
        pages_label = ctk.CTkLabel(parent, text="📄 Páginas por archivo:", font=ctk.CTkFont(size=12, weight="bold"))
        pages_label.grid(row=2, column=0, sticky="w", padx=(15, 10), pady=(15, 5))
        
        pages_frame = ctk.CTkFrame(parent, fg_color="transparent")
        pages_frame.grid(row=2, column=1, sticky="ew", padx=(0, 15), pady=(15, 5))
        pages_frame.grid_columnconfigure(1, weight=1)
        
        # Slider para páginas
        max_pages = min(1000, self.analysis.total_pages)
        self.pages_slider = ctk.CTkSlider(
            pages_frame,
            from_=10,
            to=max_pages,
            width=200
        )
        self.pages_slider.grid(row=0, column=1, sticky="ew", padx=(10, 10))
        self.pages_slider.set(self.pages_per_file_var.get())
        
        # Entry para páginas
        self.pages_entry = ctk.CTkEntry(pages_frame, width=60)
        self.pages_entry.grid(row=0, column=2, padx=(5, 0))
        self.pages_entry.insert(0, str(self.pages_per_file_var.get()))
        
        # Bind manual events para slider y entry
        self.pages_slider.configure(command=self._on_pages_slider_changed)
        self.pages_entry.bind('<KeyRelease>', self._on_pages_entry_changed)
        self.pages_entry.bind('<FocusOut>', self._on_pages_entry_changed)
        
        # Checkbox de auto-ajuste
        self.auto_adjust_checkbox = ctk.CTkCheckBox(
            parent,
            text="🤖 Ajuste automático si excede límites",
            variable=self.auto_adjust_var,
            font=ctk.CTkFont(size=12)
        )
        self.auto_adjust_checkbox.grid(row=3, column=0, columnspan=2, pady=(20, 10), padx=15, sticky="w")
        
        # Botón de cálculo automático
        calc_button = ctk.CTkButton(
            parent,
            text="⚡ Calcular División Óptima",
            command=self.calculate_optimal,
            height=35
        )
        calc_button.grid(row=4, column=0, columnspan=2, pady=(10, 15), padx=15, sticky="ew")
    
    def create_realtime_info(self, parent):
        """Crear panel de información en tiempo real"""
        # Título del panel
        panel_title = ctk.CTkLabel(
            parent,
            text="📊 Información en Tiempo Real",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        panel_title.pack(pady=(15, 20))
        
        # Frame para métricas
        metrics_frame = ctk.CTkFrame(parent, fg_color="gray15")
        metrics_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        # Métricas calculadas
        self.mb_per_file_label = ctk.CTkLabel(
            metrics_frame,
            text="💾 MB por archivo: --",
            font=ctk.CTkFont(size=12)
        )
        self.mb_per_file_label.pack(pady=(10, 5), padx=10)
        
        self.efficiency_label = ctk.CTkLabel(
            metrics_frame,
            text="⚡ Eficiencia: --",
            font=ctk.CTkFont(size=12)
        )
        self.efficiency_label.pack(pady=5, padx=10)
        
        self.total_size_label = ctk.CTkLabel(
            metrics_frame,
            text="📏 Tamaño total: --",
            font=ctk.CTkFont(size=12)
        )
        self.total_size_label.pack(pady=(5, 10), padx=10)
        
        # Indicador de estado
        self.status_frame = ctk.CTkFrame(parent)
        self.status_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="✅ Configuración válida",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="green"
        )
        self.status_label.pack(pady=15)
    
    def create_preset_options(self, parent):
        """Crear opciones preestablecidas"""
        # Título
        preset_title = ctk.CTkLabel(
            parent,
            text="🎯 Opciones Preestablecidas",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        preset_title.pack(pady=(15, 10))
        
        # Frame para botones
        buttons_frame = ctk.CTkFrame(parent, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=15, pady=(0, 15))
        buttons_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # Botones de presets
        presets = [
            ("🌟 Recomendado", self.apply_recommended, "blue"),
            ("⚡ Rápido (2 archivos)", self.apply_fast, "orange"),
            ("🔧 Conservador", self.apply_conservative, "green")
        ]
        
        for i, (text, command, color) in enumerate(presets):
            btn = ctk.CTkButton(
                buttons_frame,
                text=text,
                command=command,
                fg_color=color,
                height=35
            )
            btn.grid(row=0, column=i, padx=5, pady=5, sticky="ew")
    
    def create_validation_section(self):
        """Crear sección de validación si hay problemas"""
        if not self.validation_summary or self.validation_summary.all_within_limits:
            return
        
        validation_frame = ctk.CTkFrame(self)
        validation_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=10)
        
        # Título de validación
        val_title = ctk.CTkLabel(
            validation_frame,
            text="🚨 VALIDACIÓN - ARCHIVOS QUE EXCEDEN LÍMITES",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="red"
        )
        val_title.pack(pady=(15, 10))
        
        # Lista de problemas
        problems_text = ctk.CTkTextbox(validation_frame, height=100)
        problems_text.pack(fill="x", padx=15, pady=(0, 15))
        
        problems_content = f"📊 Total archivos: {self.validation_summary.total_files_checked}\n"
        problems_content += f"❌ Archivos problemáticos: {self.validation_summary.files_exceeding_limits}\n"
        problems_content += f"💡 Archivos recomendados: {self.validation_summary.recommended_total_files}\n\n"
        
        for result in self.validation_summary.validation_results:
            if not result.is_valid:
                problems_content += f"• {result.file_path.name}: {result.size_mb:.1f}MB (límite: 50MB)\n"
        
        problems_text.insert("1.0", problems_content)
        problems_text.configure(state="disabled")
    
    def create_buttons(self):
        """Crear botones de acción"""
        button_frame = ctk.CTkFrame(self)
        button_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=(10, 20))
        button_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # Botones principales
        buttons = [
            ("❌ Cancelar", self.cancel_action, "gray40", "gray50"),
            ("⚠️ Procesar Sin Dividir", self.no_split_action, "orange", "darkorange"),
            ("🤖 Ajuste Automático", self.auto_adjust_action, "purple", "darkmagenta"),
            ("✅ Aplicar División", self.apply_action, "green", "darkgreen")
        ]
        
        for i, (text, command, fg_color, hover_color) in enumerate(buttons):
            btn = ctk.CTkButton(
                button_frame,
                text=text,
                command=command,
                fg_color=fg_color,
                hover_color=hover_color,
                height=40,
                font=ctk.CTkFont(size=12, weight="bold")
            )
            btn.grid(row=0, column=i, padx=8, pady=15, sticky="ew")
    
    def _setup_event_bindings(self):
        """Configurar event bindings después de inicialización completa"""
        self._initializing = False
        self.num_files_var.trace_add('write', self.on_values_changed)
        self.pages_per_file_var.trace_add('write', self.on_values_changed)
        self.update_calculations()
    
    # Event handlers y métodos de cálculo
    def on_values_changed(self, *args):
        """Callback cuando cambian los valores"""
        if not getattr(self, '_initializing', False):
            self.update_calculations()
    
    def _on_files_slider_changed(self, value):
        """Callback para slider de archivos"""
        if getattr(self, '_updating', False): return
        
        self._updating = True
        try:
            int_value = int(round(value))
            self.num_files_var.set(int_value)
            self.files_entry.delete(0, tk.END)
            self.files_entry.insert(0, str(int_value))
            
            # Lógica matemática: Recalcular páginas
            if int_value > 0:
                new_pages = math.ceil(self.analysis.total_pages / int_value)
                self.pages_per_file_var.set(new_pages)
                self.pages_slider.set(new_pages)
                self.pages_entry.delete(0, tk.END)
                self.pages_entry.insert(0, str(new_pages))
            
            if not getattr(self, '_initializing', False):
                self.update_calculations()
        except Exception as e:
            print(f"Error en slider callback: {e}")
        finally:
            self._updating = False
    
    def _on_files_entry_changed(self, event=None):
        """Callback para entry de archivos"""
        if getattr(self, '_updating', False): return
        
        try:
            value_str = self.files_entry.get().strip()
            if value_str and value_str.isdigit():
                value = int(value_str)
                if 1 <= value <= 20:
                    self._updating = True  # Bloquear actualizaciones recursivas
                    
                    self.num_files_var.set(value)
                    self.files_slider.set(value)
                    
                    # Lógica matemática: Recalcular páginas
                    new_pages = math.ceil(self.analysis.total_pages / value)
                    self.pages_per_file_var.set(new_pages)
                    self.pages_slider.set(new_pages)
                    self.pages_entry.delete(0, tk.END)
                    self.pages_entry.insert(0, str(new_pages))
                    
                    if not getattr(self, '_initializing', False):
                        self.update_calculations()
        except Exception as e:
            print(f"Error en entry callback: {e}")
        finally:
            self._updating = False
    
    def _on_pages_slider_changed(self, value):
        """Callback para slider de páginas"""
        if getattr(self, '_updating', False): return
        
        self._updating = True
        try:
            int_value = int(round(value))
            self.pages_per_file_var.set(int_value)
            self.pages_entry.delete(0, tk.END)
            self.pages_entry.insert(0, str(int_value))
            
            # Lógica matemática: Recalcular archivos
            if int_value > 0:
                new_files = math.ceil(self.analysis.total_pages / int_value)
                
                # Actualizar sliders de archivos (dentro de límites prácticos)
                new_files = max(1, min(20, new_files))  # Mantener dentro del rango del slider
                
                self.num_files_var.set(new_files)
                self.files_slider.set(new_files)
                self.files_entry.delete(0, tk.END)
                self.files_entry.insert(0, str(new_files))
            
            if not getattr(self, '_initializing', False):
                self.update_calculations()
        except Exception as e:
            print(f"Error en pages slider callback: {e}")
        finally:
            self._updating = False
    
    def _on_pages_entry_changed(self, event=None):
        """Callback para entry de páginas"""
        if getattr(self, '_updating', False): return
        
        try:
            value_str = self.pages_entry.get().strip()
            if value_str and value_str.isdigit():
                value = int(value_str)
                max_pages = min(1000, self.analysis.total_pages)
                if 10 <= value <= max_pages:
                    self._updating = True
                    
                    self.pages_per_file_var.set(value)
                    self.pages_slider.set(value)
                    
                    # Lógica matemática: Recalcular archivos
                    new_files = math.ceil(self.analysis.total_pages / value)
                    new_files = max(1, min(20, new_files))
                    
                    self.num_files_var.set(new_files)
                    self.files_slider.set(new_files)
                    self.files_entry.delete(0, tk.END)
                    self.files_entry.insert(0, str(new_files))
                    
                    if not getattr(self, '_initializing', False):
                        self.update_calculations()
        except Exception as e:
            print(f"Error en pages entry callback: {e}")
        finally:
            self._updating = False
    
    def update_calculations(self):
        """Actualizar cálculos en tiempo real"""
        try:
            # Obtener valores con validación mejorada
            num_files = self.num_files_var.get()
            pages_per_file = self.pages_per_file_var.get()
            
            if num_files <= 0 or pages_per_file <= 0:
                return
            
            # Calcular métricas
            mb_per_file = self.analysis.total_size_mb / num_files
            total_pages_calculated = num_files * pages_per_file
            efficiency = min(1.0, 50.0 / mb_per_file) if mb_per_file > 0 else 0
            
            # Actualizar labels
            self.mb_per_file_label.configure(text=f"💾 MB por archivo: {mb_per_file:.1f} MB")
            self.efficiency_label.configure(text=f"⚡ Eficiencia: {efficiency:.0%}")
            self.total_size_label.configure(text=f"📏 Total calculado: {total_pages_calculated:,} páginas")
            
            # Estado de validación
            is_valid = mb_per_file <= LIMITS.safe_max_size_mb and pages_per_file <= LIMITS.safe_max_pages
            
            if is_valid:
                self.status_label.configure(
                    text="✅ Configuración válida",
                    text_color="green"
                )
            else:
                issues = []
                if mb_per_file > LIMITS.safe_max_size_mb:
                    issues.append(f"MB excede límite ({mb_per_file:.1f} > {LIMITS.safe_max_size_mb:.1f})")
                if pages_per_file > LIMITS.safe_max_pages:
                    issues.append(f"Páginas exceden límite ({pages_per_file} > {LIMITS.safe_max_pages})")
                
                self.status_label.configure(
                    text=f"❌ {', '.join(issues)}",
                    text_color="red"
                )
            
            # Almacenar valores calculados
            self.estimated_mb_per_file.set(mb_per_file)
            self.efficiency_score.set(efficiency)
            self.total_estimated_size.set(total_pages_calculated)
            
        except Exception as e:
            print(f"Error updating calculations: {e}")
    
    def _update_values(self, num_files, pages_per_file):
        """Actualizar valores de manera segura"""
        try:
            # Validar valores
            num_files = max(1, min(20, int(num_files)))
            pages_per_file = max(10, min(1000, int(pages_per_file)))
            
            # Actualizar variables
            self.num_files_var.set(num_files)
            self.pages_per_file_var.set(pages_per_file)
            
            # Actualizar widgets
            self.files_slider.set(num_files)
            self.pages_slider.set(pages_per_file)
            
            self.files_entry.delete(0, tk.END)
            self.files_entry.insert(0, str(num_files))
            
            self.pages_entry.delete(0, tk.END)
            self.pages_entry.insert(0, str(pages_per_file))
            
            # Actualizar cálculos
            self.update_calculations()
            
        except Exception as e:
            print(f"Error actualizando valores: {e}")
    
    def calculate_optimal(self):
        """Calcular división óptima automáticamente"""
        try:
            # Usar el primer recommendation como base
            if self.recommendations:
                optimal = self.recommendations[0]
                self._update_values(optimal.num_files, optimal.pages_per_file)
            else:
                # Cálculo manual
                optimal_files = math.ceil(self.analysis.total_size_mb / (LIMITS.safe_max_size_mb * 0.9))
                optimal_pages = math.ceil(self.analysis.total_pages / optimal_files)
                self._update_values(optimal_files, min(optimal_pages, LIMITS.safe_max_pages))
            
        except Exception as e:
            messagebox.showerror("Error", f"Error calculando división óptima: {e}")
    
    def apply_recommended(self):
        """Aplicar configuración recomendada"""
        if self.recommendations:
            rec = self.recommendations[0]
            self._update_values(rec.num_files, rec.pages_per_file)
    
    def apply_fast(self):
        """Aplicar configuración rápida (2 archivos)"""
        pages = min(math.ceil(self.analysis.total_pages / 2), LIMITS.safe_max_pages)
        self._update_values(2, pages)
    
    def apply_conservative(self):
        """Aplicar configuración conservadora"""
        conservative_files = math.ceil(self.analysis.total_size_mb / 40.0)  # Más conservador
        pages = min(math.ceil(self.analysis.total_pages / conservative_files), 100)
        self._update_values(conservative_files, pages)
    
    # Actions
    def apply_action(self):
        """Aplicar configuración de división"""
        try:
            num_files = self.num_files_var.get()
            pages_per_file = self.pages_per_file_var.get()
        except tk.TclError:
            messagebox.showerror("Error", "Valores inválidos en la configuración")
            return
            
        if num_files <= 0 or pages_per_file <= 0:
            messagebox.showerror("Error", "Los valores deben ser mayores a 0")
            return
            
        self.result = InteractiveSplitResult(
            action='split',
            num_files=num_files,
            pages_per_file=pages_per_file,
            validation_summary=self.validation_summary,
            user_modified=True,
            auto_adjust_applied=False
        )
        self.destroy()
    
    def auto_adjust_action(self):
        """Aplicar ajuste automático"""
        try:
            if self.validation_summary:
                recommended_files = self.validation_summary.recommended_total_files or math.ceil(self.analysis.total_size_mb / (LIMITS.safe_max_size_mb * 0.9))
            else:
                recommended_files = math.ceil(self.analysis.total_size_mb / (LIMITS.safe_max_size_mb * 0.9))
            
            recommended_pages = min(math.ceil(self.analysis.total_pages / recommended_files), LIMITS.safe_max_pages)
            
            self.result = InteractiveSplitResult(
                action='split',
                num_files=recommended_files,
                pages_per_file=recommended_pages,
                validation_summary=self.validation_summary,
                user_modified=False,
                auto_adjust_applied=True
            )
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en ajuste automático: {e}")
    
    def no_split_action(self):
        """Procesar sin división"""
        result = messagebox.askyesno(
            "Procesar Sin Dividir - CONFIRMACIÓN",
            f"⚠️ ADVERTENCIA: Está a punto de procesar un archivo que excede límites.\n\n"
            f"📄 Archivo: {self.analysis.file_path.name}\n"
            f"📏 Tamaño: {self.analysis.total_size_mb:.1f} MB (límite: 50 MB)\n"
            f"📑 Páginas: {self.analysis.total_pages:,}\n\n"
            f"🚨 RIESGOS:\n"
            f"• El procesamiento puede fallar\n"
            f"• Timeouts probables\n"
            f"• Consumo excesivo de memoria\n"
            f"• API puede rechazar la solicitud\n\n"
            f"❓ ¿Continuar de todos modos?"
        )
        
        if result:
            self.result = InteractiveSplitResult(
                action='no_split',
                validation_summary=self.validation_summary
            )
            self.destroy()
    
    def cancel_action(self):
        """Cancelar operación"""
        self.result = InteractiveSplitResult(action='cancel')
        self.destroy()

def show_advanced_split_dialog(parent, analysis: PDFAnalysis, recommendations: List[SplitRecommendation], 
                              validation_summary: Optional[ValidationSummary] = None) -> Optional[InteractiveSplitResult]:
    """
    Mostrar el diálogo avanzado de división interactiva
    
    Args:
        parent: Ventana padre
        analysis: Análisis del PDF
        recommendations: Lista de recomendaciones
        validation_summary: Resumen de validación (opcional)
        
    Returns:
        InteractiveSplitResult con la decisión del usuario
    """
    dialog = AdvancedSplitControlDialog(parent, analysis, recommendations, validation_summary)
    return dialog.result

# Test function
def test_advanced_dialog():
    """Función de prueba para el diálogo avanzado"""
    import os
    from pathlib import Path
    
    # Mock data for testing
    test_analysis = PDFAnalysis(
        file_path=Path("test_large_document.pdf"),
        total_size_mb=127.3,
        total_pages=850,
        density_mb_per_page=0.15,
        requires_splitting=True
    )
    
    test_recommendations = [
        SplitRecommendation(
            num_files=3,
            pages_per_file=284,
            estimated_mb_per_file=42.4,
            efficiency_score=0.85,
            reason="Recommended optimal split"
        ),
        SplitRecommendation(
            num_files=4,
            pages_per_file=213,
            estimated_mb_per_file=31.8,
            efficiency_score=0.91,
            reason="More conservative approach"
        )
    ]
    
    # Create test window
    root = ctk.CTk()
    root.withdraw()  # Hide main window
    
    result = show_advanced_split_dialog(root, test_analysis, test_recommendations)
    
    if result:
        print(f"Action: {result.action}")
        if result.action == 'split':
            print(f"Files: {result.num_files}")
            print(f"Pages per file: {result.pages_per_file}")
            print(f"User modified: {result.user_modified}")
            print(f"Auto adjust: {result.auto_adjust_applied}")
    else:
        print("Dialog was cancelled")
    
    root.destroy()

if __name__ == "__main__":
    test_advanced_dialog()