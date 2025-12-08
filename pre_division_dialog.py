#!/usr/bin/env python3
"""
Pre-Division Dialog - Modal de Confirmación ANTES de Dividir
==========================================================
Modal que aparece ANTES de crear archivos físicos cuando se estima
que algunos archivos excederán los límites de 50MB.

Permite al usuario ver las ESTIMACIONES y decidir ANTES de crear archivos.

Versión: 1.0.0 - Validación Preventiva
Funcionalidad: Confirmación y ajuste antes de división física
"""

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from typing import List, Optional, Dict
from dataclasses import dataclass
from pathlib import Path
import math
from pre_division_validator import PreDivisionAnalysis, PreDivisionValidator

@dataclass
class PreDivisionResult:
    """Resultado del diálogo pre-división"""
    action: str  # 'proceed', 'adjust', 'cancel', 'use_recommendation'
    num_files: Optional[int] = None
    use_recommended: bool = False
    selected_recommendation: Optional[Dict] = None

class PreDivisionDialog(ctk.CTkToplevel):
    """Modal de confirmación ANTES de crear archivos físicos"""
    
    def __init__(self, parent, analysis: PreDivisionAnalysis, validator: PreDivisionValidator):
        super().__init__(parent)
        
        self.analysis = analysis
        self.validator = validator
        self.result = None
        self.recommendations = validator.get_division_recommendations(analysis)
        
        # Variables para ajuste
        self.custom_files_var = tk.IntVar(value=analysis.recommended_num_files)
        
        self.setup_window()
        self.create_widgets()
        
        # Modal behavior
        self.transient(parent)
        self.grab_set()
        self.focus_set()
        
        # Center on parent
        self.geometry("750x650")
        self.center_on_parent(parent)
        
        # Bind events
        self.custom_files_var.trace_add('write', self.on_custom_value_changed)
        
        # Wait for user response
        self.wait_window()
    
    def setup_window(self):
        """Configurar ventana"""
        self.title("⚠️ Confirmación Pre-División - Archivos Estimados Exceden Límites")
        self.resizable(True, False)
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # Content area expandible
    
    def center_on_parent(self, parent):
        """Centrar sobre ventana padre"""
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (750 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (650 // 2)
        self.geometry(f"750x650+{x}+{y}")
    
    def create_widgets(self):
        """Crear todos los widgets"""
        self.create_warning_header()
        self.create_estimation_analysis()
        self.create_solution_options()
        self.create_action_buttons()
    
    def create_warning_header(self):
        """Header de advertencia preventiva"""
        header_frame = ctk.CTkFrame(self, fg_color="darkorange", corner_radius=10)
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Icon de advertencia
        warning_icon = ctk.CTkLabel(
            header_frame, 
            text="⚠️", 
            font=ctk.CTkFont(size=32, weight="bold")
        )
        warning_icon.grid(row=0, column=0, padx=(20, 15), pady=15, rowspan=2)
        
        # Título preventivo
        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=15)
        title_frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(
            title_frame,
            text="ESTIMACIÓN: ARCHIVOS EXCEDERÁN LÍMITES",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="white"
        )
        title_label.pack(anchor="w")
        
        # Mensaje explicativo
        msg_label = ctk.CTkLabel(
            title_frame,
            text="La división actual creará archivos que excedan 50MB (ESTIMADO)",
            font=ctk.CTkFont(size=13),
            text_color="lightyellow"
        )
        msg_label.pack(anchor="w", pady=(3, 0))
        
        # Stats preventivas
        stats_label = ctk.CTkLabel(
            header_frame,
            text=f"{self.analysis.files_exceeding_limits}/{self.analysis.requested_num_files} PROBLEMÁTICOS",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="yellow",
            fg_color="red",
            corner_radius=8
        )
        stats_label.grid(row=0, column=2, padx=(10, 20), pady=15, sticky="ne")
    
    def create_estimation_analysis(self):
        """Análisis detallado de estimaciones"""
        analysis_frame = ctk.CTkFrame(self)
        analysis_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=10)
        analysis_frame.grid_columnconfigure(0, weight=1)
        
        # Título del análisis
        analysis_title = ctk.CTkLabel(
            analysis_frame,
            text="📊 ANÁLISIS DE ESTIMACIONES PRE-DIVISIÓN",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        analysis_title.pack(pady=(15, 10))
        
        # Información del archivo original
        orig_info_frame = ctk.CTkFrame(analysis_frame, fg_color="gray15")
        orig_info_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        orig_file_name = self.analysis.original_file.name
        if len(orig_file_name) > 50:
            orig_file_name = orig_file_name[:47] + "..."
        
        orig_label = ctk.CTkLabel(
            orig_info_frame,
            text=f"📄 Archivo: {orig_file_name} ({self.analysis.original_size_mb:.1f}MB, {self.analysis.total_pages:,} páginas)",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        orig_label.pack(pady=(10, 5), padx=15)
        
        # Información de división solicitada vs recomendada
        division_info = (f"🔢 División solicitada: {self.analysis.requested_num_files} archivos\\n"
                        f"💡 División recomendada: {self.analysis.recommended_num_files} archivos\\n"
                        f"⚡ Eficiencia estimada: {self.analysis.size_efficiency:.0%}")
        
        division_label = ctk.CTkLabel(
            orig_info_frame,
            text=division_info,
            font=ctk.CTkFont(size=11),
            justify="left"
        )
        division_label.pack(pady=(0, 10), padx=15, anchor="w")
        
        # Lista de archivos estimados
        estimates_frame = ctk.CTkFrame(analysis_frame)
        estimates_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        estimates_title = ctk.CTkLabel(
            estimates_frame,
            text="📋 ESTIMACIONES DE ARCHIVOS RESULTANTES:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="orange"
        )
        estimates_title.pack(pady=(10, 8))
        
        # ScrollableFrame para lista de estimaciones
        self.estimates_scroll = ctk.CTkScrollableFrame(estimates_frame, height=150)
        self.estimates_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Populate estimates list
        for est_file in self.analysis.estimated_files:
            self.create_estimate_item(est_file)
    
    def create_estimate_item(self, est_file):
        """Crear item de estimación individual"""
        color = "darkred" if est_file.exceeds_limit else "darkgreen"
        
        item_frame = ctk.CTkFrame(self.estimates_scroll, fg_color=color)
        item_frame.pack(fill="x", pady=2, padx=5)
        item_frame.grid_columnconfigure(1, weight=1)
        
        # Icon de estado
        icon = "❌" if est_file.exceeds_limit else "✅"
        status_icon = ctk.CTkLabel(item_frame, text=icon, font=ctk.CTkFont(size=14))
        status_icon.grid(row=0, column=0, padx=(10, 8), pady=8)
        
        # Info del archivo estimado
        info_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=5)
        info_frame.grid_columnconfigure(0, weight=1)
        
        # Nombre del archivo estimado
        name_label = ctk.CTkLabel(
            info_frame,
            text=f"Archivo {est_file.index + 1} - {est_file.page_range}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="white"
        )
        name_label.grid(row=0, column=0, sticky="w")
        
        # Detalles de la estimación
        if est_file.exceeds_limit:
            details_text = f"~{est_file.estimated_size_mb:.1f} MB (EXCEDE por {est_file.estimated_size_mb - 50:.1f} MB)"
            if est_file.recommended_split:
                details_text += f" • Necesita {est_file.recommended_split} divisiones más"
        else:
            details_text = f"~{est_file.estimated_size_mb:.1f} MB (dentro del límite)"
        
        details_label = ctk.CTkLabel(
            info_frame,
            text=details_text,
            font=ctk.CTkFont(size=10),
            text_color="lightcoral" if est_file.exceeds_limit else "lightgreen"
        )
        details_label.grid(row=1, column=0, sticky="w", pady=(2, 0))
    
    def create_solution_options(self):
        """Opciones de solución preventiva"""
        solutions_frame = ctk.CTkFrame(self)
        solutions_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=10)
        solutions_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Título de soluciones
        solutions_title = ctk.CTkLabel(
            solutions_frame,
            text="🔧 OPCIONES ANTES DE CREAR ARCHIVOS",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        solutions_title.grid(row=0, column=0, columnspan=2, pady=(15, 20))
        
        # Opción 1: Usar recomendación automática
        auto_frame = ctk.CTkFrame(solutions_frame, fg_color="darkgreen")
        auto_frame.grid(row=1, column=0, sticky="nsew", padx=(15, 8), pady=(0, 10))
        
        auto_title = ctk.CTkLabel(
            auto_frame,
            text=f"🤖 USAR DIVISIÓN RECOMENDADA ({self.analysis.recommended_num_files} archivos)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="lightgreen"
        )
        auto_title.pack(pady=(15, 8))
        
        auto_desc = ctk.CTkLabel(
            auto_frame,
            text=f"• Garantiza archivos < 50MB\\n"
                 f"• Basado en análisis automático\\n"
                 f"• Eficiencia: {self.analysis.size_efficiency:.0%}\\n"
                 f"• Opción más segura",
            font=ctk.CTkFont(size=11),
            justify="left"
        )
        auto_desc.pack(pady=(0, 10), padx=15, anchor="w")
        
        auto_button = ctk.CTkButton(
            auto_frame,
            text="✅ Usar Recomendación",
            command=self.use_recommendation_action,
            fg_color="green",
            hover_color="darkgreen",
            height=35
        )
        auto_button.pack(pady=(0, 15), padx=15, fill="x")
        
        # Opción 2: Ajuste personalizado
        custom_frame = ctk.CTkFrame(solutions_frame, fg_color="darkorange")
        custom_frame.grid(row=1, column=1, sticky="nsew", padx=(8, 15), pady=(0, 10))
        
        custom_title = ctk.CTkLabel(
            custom_frame,
            text="🎛️ AJUSTE PERSONALIZADO",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="lightyellow"
        )
        custom_title.pack(pady=(15, 8))
        
        # Control personalizado
        custom_control_frame = ctk.CTkFrame(custom_frame, fg_color="transparent")
        custom_control_frame.pack(padx=15, pady=(0, 10))
        
        custom_label = ctk.CTkLabel(custom_control_frame, text="Número de archivos:")
        custom_label.pack()
        
        # Slider para archivos personalizados
        min_files = self.analysis.recommended_num_files
        max_files = min(20, self.analysis.recommended_num_files + 5)
        
        self.custom_slider = ctk.CTkSlider(
            custom_control_frame,
            from_=min_files,
            to=max_files,
            width=150
        )
        self.custom_slider.set(self.custom_files_var.get())
        self.custom_slider.pack(pady=5)
        
        # Entry para valor exacto
        self.custom_entry = ctk.CTkEntry(
            custom_control_frame, 
            width=80,
            justify="center"
        )
        self.custom_entry.insert(0, str(self.custom_files_var.get()))
        self.custom_entry.pack(pady=5)
        
        # Info calculada
        self.custom_info_label = ctk.CTkLabel(
            custom_frame,
            text="Calculando...",
            font=ctk.CTkFont(size=11),
            text_color="lightyellow"
        )
        self.custom_info_label.pack(pady=(0, 10))
        
        # Bind events
        self.custom_slider.configure(command=self._on_slider_changed)
        self.custom_entry.bind('<KeyRelease>', self._on_entry_changed)
        
        custom_button = ctk.CTkButton(
            custom_frame,
            text="🔧 Aplicar Personalizado",
            command=self.custom_adjust_action,
            fg_color="orange",
            hover_color="darkorange",
            height=35
        )
        custom_button.pack(pady=(0, 15), padx=15, fill="x")
        
        # Panel de recomendaciones alternativas
        if self.recommendations:
            recs_frame = ctk.CTkFrame(solutions_frame, fg_color="gray20")
            recs_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=15, pady=(10, 15))
            
            recs_title = ctk.CTkLabel(
                recs_frame,
                text="💡 RECOMENDACIONES ALTERNATIVAS",
                font=ctk.CTkFont(size=12, weight="bold")
            )
            recs_title.pack(pady=(10, 5))
            
            for i, rec in enumerate(self.recommendations[:2]):  # Mostrar top 2
                rec_text = f"{rec['description']}: ~{rec['estimated_max_size']:.1f}MB máx, {rec['efficiency']:.0%} eficiente"
                rec_label = ctk.CTkLabel(
                    recs_frame,
                    text=f"{i+1}. {rec_text}",
                    font=ctk.CTkFont(size=10)
                )
                rec_label.pack(pady=2)
        
        # Actualizar info personalizada
        self.on_custom_value_changed()
    
    def create_action_buttons(self):
        """Botones de acción final"""
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=(10, 15))
        button_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Botón de proceder de todos modos (muy peligroso)
        proceed_button = ctk.CTkButton(
            button_frame,
            text="⚠️ Proceder de Todos Modos (MUY RIESGOSO)",
            command=self.proceed_anyway_action,
            fg_color="red",
            hover_color="darkred",
            height=40
        )
        proceed_button.grid(row=0, column=0, padx=(0, 8), pady=10, sticky="ew")
        
        # Botón cancelar
        cancel_button = ctk.CTkButton(
            button_frame,
            text="❌ Cancelar (No Crear Archivos)",
            command=self.cancel_action,
            fg_color="gray40",
            hover_color="gray50",
            height=40
        )
        cancel_button.grid(row=0, column=1, padx=(8, 0), pady=10, sticky="ew")
    
    # Event handlers
    def _on_slider_changed(self, value):
        """Callback para slider"""
        int_value = int(round(value))
        self.custom_files_var.set(int_value)
        self.custom_entry.delete(0, tk.END)
        self.custom_entry.insert(0, str(int_value))
        self.on_custom_value_changed()
    
    def _on_entry_changed(self, event=None):
        """Callback para entry"""
        try:
            value_str = self.custom_entry.get().strip()
            if value_str and value_str.isdigit():
                value = int(value_str)
                min_val = self.analysis.recommended_num_files
                if min_val <= value <= 20:
                    self.custom_files_var.set(value)
                    self.custom_slider.set(value)
                    self.on_custom_value_changed()
        except:
            pass
    
    def on_custom_value_changed(self, *args):
        """Actualizar info cuando cambia valor personalizado"""
        try:
            custom_files = self.custom_files_var.get()
            if custom_files > 0:
                # Hacer análisis rápido
                quick_analysis = self.validator.analyze_division_plan(
                    self.analysis.original_file, 
                    custom_files
                )
                
                max_size = max(f.estimated_size_mb for f in quick_analysis.estimated_files)
                
                # Actualizar label
                status = "✅ SEGURO" if quick_analysis.all_within_limits else f"❌ {quick_analysis.files_exceeding_limits} PROBLEMÁTICOS"
                
                self.custom_info_label.configure(
                    text=f"~{max_size:.1f} MB máx por archivo - {status}"
                )
                
                # Color coding
                if quick_analysis.all_within_limits:
                    self.custom_info_label.configure(text_color="lightgreen")
                else:
                    self.custom_info_label.configure(text_color="lightcoral")
        except Exception as e:
            self.custom_info_label.configure(text=f"Error: {e}")
    
    # Actions
    def use_recommendation_action(self):
        """Usar división recomendada"""
        self.result = PreDivisionResult(
            action='use_recommendation',
            num_files=self.analysis.recommended_num_files,
            use_recommended=True
        )
        self.destroy()
    
    def custom_adjust_action(self):
        """Aplicar ajuste personalizado"""
        custom_files = self.custom_files_var.get()
        
        if custom_files <= 0:
            messagebox.showwarning("Valor Inválido", "El número de archivos debe ser mayor a 0")
            return
        
        self.result = PreDivisionResult(
            action='adjust',
            num_files=custom_files,
            use_recommended=False
        )
        self.destroy()
    
    def proceed_anyway_action(self):
        """Proceder creando archivos problemáticos (muy peligroso)"""
        result = messagebox.askyesno(
            "⚠️ PROCEDER CREANDO ARCHIVOS PROBLEMÁTICOS - CONFIRMACIÓN CRÍTICA",
            f"🚨 ADVERTENCIA MUY CRÍTICA:\\n\\n"
            f"Está a punto de crear {self.analysis.files_exceeding_limits} archivos \\"
            f"que se estima EXCEDERÁN 50MB.\\n\\n"
            f"📊 Archivos problemáticos estimados:\\n"
            f"{self._get_problem_summary()}\\n\\n"
            f"🚨 CONSECUENCIAS GRAVES:\\n"
            f"• Se crearán archivos físicos inútiles\\n"
            f"• Tendrá que borrar manualmente los archivos\\n"
            f"• Desperdicio de tiempo y espacio\\n"
            f"• Procesamiento OCR fallará de todos modos\\n\\n"
            f"❓ ¿REALMENTE desea crear estos archivos problemáticos?\\n"
            f"(SE RECOMIENDA ENCARECIDAMENTE CANCELAR)"
        )
        
        if result:
            self.result = PreDivisionResult(
                action='proceed',
                num_files=self.analysis.requested_num_files
            )
            self.destroy()
    
    def cancel_action(self):
        """Cancelar (no crear archivos)"""
        self.result = PreDivisionResult(action='cancel')
        self.destroy()
    
    def _get_problem_summary(self) -> str:
        """Obtener resumen de archivos problemáticos"""
        problems = []
        for est_file in self.analysis.estimated_files:
            if est_file.exceeds_limit:
                problems.append(f"• Archivo {est_file.index + 1}: ~{est_file.estimated_size_mb:.1f}MB")
        
        return "\\n".join(problems[:4])  # Mostrar máximo 4

def show_pre_division_dialog(parent, analysis: PreDivisionAnalysis, 
                           validator: PreDivisionValidator) -> Optional[PreDivisionResult]:
    """
    Mostrar modal de confirmación pre-división
    
    Args:
        parent: Ventana padre
        analysis: Análisis pre-división con estimaciones
        validator: Instancia del validador
        
    Returns:
        PreDivisionResult con la decisión del usuario
    """
    dialog = PreDivisionDialog(parent, analysis, validator)
    return dialog.result

# Test function
def test_pre_division_dialog():
    """Función de prueba"""
    import tempfile
    from pre_division_validator import PreDivisionValidator
    
    # Mock análisis problemático
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        tmp.write(b'0' * (265 * 1024 * 1024))  # 265MB
        test_file = Path(tmp.name)
    
    try:
        validator = PreDivisionValidator(max_size_mb=50.0)
        analysis = validator.analyze_division_plan(test_file, 5)  # 5 archivos problemáticos
        
        # Test dialog
        root = ctk.CTk()
        root.withdraw()
        
        result = show_pre_division_dialog(root, analysis, validator)
        
        if result:
            print(f"User action: {result.action}")
            if result.num_files:
                print(f"Files: {result.num_files}")
            print(f"Use recommended: {result.use_recommended}")
        
        root.destroy()
        
    finally:
        test_file.unlink()

if __name__ == "__main__":
    test_pre_division_dialog()