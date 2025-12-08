#!/usr/bin/env python3
"""
Post-Split Validation Dialog - Modal de Validación Post-División
===============================================================
Modal específico que aparece DESPUÉS de dividir un archivo, cuando se detecta
que algunos archivos divididos aún exceden los límites de 50MB.

Permite al usuario ver los tamaños REALES y decidir cómo proceder.

Versión: 1.0.0 - Validación Post-División
Funcionalidad: Modal para validación en tiempo real post-división
"""

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from typing import List, Optional, Dict
from dataclasses import dataclass
from pathlib import Path
import math
from pdf_split_validator import ValidationSummary, ValidationResult, AdjustedSummary, PDFSplitValidator

@dataclass
class PostSplitResult:
    """Resultado del diálogo post-división"""
    action: str  # 'auto_adjust', 'proceed_anyway', 'cancel', 'custom_adjust'
    adjusted_summary: Optional[AdjustedSummary] = None
    custom_files: Optional[int] = None

class PostSplitValidationDialog(ctk.CTkToplevel):
    """Modal para validación post-división con tamaños reales"""
    
    def __init__(self, parent, validation_summary: ValidationSummary, validator: PDFSplitValidator):
        super().__init__(parent)
        
        self.validation_summary = validation_summary
        self.validator = validator
        self.result = None
        
        # Variables para ajuste personalizado
        self.custom_files_var = tk.IntVar(value=validation_summary.recommended_total_files or 6)
        
        self.setup_window()
        self.create_widgets()
        
        # Modal behavior
        self.transient(parent)
        self.grab_set()
        self.focus_set()
        
        # Center on parent
        self.geometry("700x600")
        self.center_on_parent(parent)
        
        # Bind events
        self.custom_files_var.trace_add('write', self.on_custom_value_changed)
        
        # Wait for user response
        self.wait_window()
    
    def setup_window(self):
        """Configurar ventana"""
        self.title("🚨 Validación Post-División - Archivos Exceden Límites")
        self.resizable(True, False)
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # Content area expandible
    
    def center_on_parent(self, parent):
        """Centrar sobre ventana padre"""
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (700 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (600 // 2)
        self.geometry(f"700x600+{x}+{y}")
    
    def create_widgets(self):
        """Crear todos los widgets"""
        self.create_critical_header()
        self.create_problem_analysis()
        self.create_solution_options()
        self.create_action_buttons()
    
    def create_critical_header(self):
        """Header crítico con alerta"""
        header_frame = ctk.CTkFrame(self, fg_color="darkred", corner_radius=10)
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Icon de alerta crítica
        alert_icon = ctk.CTkLabel(
            header_frame, 
            text="🚨", 
            font=ctk.CTkFont(size=36, weight="bold")
        )
        alert_icon.grid(row=0, column=0, padx=(20, 15), pady=15, rowspan=2)
        
        # Título crítico
        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=15)
        title_frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(
            title_frame,
            text="VALIDACIÓN POST-DIVISIÓN FALLÓ",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="white"
        )
        title_label.pack(anchor="w")
        
        # Mensaje explicativo
        msg_label = ctk.CTkLabel(
            title_frame,
            text="Algunos archivos divididos AÚN exceden el límite de 50MB",
            font=ctk.CTkFont(size=13),
            text_color="lightcoral"
        )
        msg_label.pack(anchor="w", pady=(3, 0))
        
        # Stats rápidas
        stats_label = ctk.CTkLabel(
            header_frame,
            text=f"{self.validation_summary.files_exceeding_limits}/{self.validation_summary.total_files_checked} PROBLEMÁTICOS",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="yellow",
            fg_color="red",
            corner_radius=8
        )
        stats_label.grid(row=0, column=2, padx=(10, 20), pady=15, sticky="ne")
    
    def create_problem_analysis(self):
        """Análisis detallado del problema"""
        analysis_frame = ctk.CTkFrame(self)
        analysis_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=10)
        analysis_frame.grid_columnconfigure(0, weight=1)
        
        # Título del análisis
        analysis_title = ctk.CTkLabel(
            analysis_frame,
            text="📊 ANÁLISIS DETALLADO - TAMAÑOS REALES",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        analysis_title.pack(pady=(15, 10))
        
        # Información del archivo original
        orig_info_frame = ctk.CTkFrame(analysis_frame, fg_color="gray15")
        orig_info_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        orig_file_name = self.validation_summary.original_file.name
        if len(orig_file_name) > 50:
            orig_file_name = orig_file_name[:47] + "..."
        
        orig_label = ctk.CTkLabel(
            orig_info_frame,
            text=f"📄 Archivo original: {orig_file_name}",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        orig_label.pack(pady=(10, 5), padx=15)
        
        # Resumen de problemas
        summary_text = (f"• Total archivos generados: {self.validation_summary.total_files_checked}\n"
                       f"• Archivos válidos: {self.validation_summary.files_within_limits}\n"
                       f"• ❌ Archivos problemáticos: {self.validation_summary.files_exceeding_limits}\n"
                       f"• 💡 División recomendada: {self.validation_summary.recommended_total_files} archivos")
        
        summary_label = ctk.CTkLabel(
            orig_info_frame,
            text=summary_text,
            font=ctk.CTkFont(size=11),
            justify="left"
        )
        summary_label.pack(pady=(0, 10), padx=15, anchor="w")
        
        # Lista detallada de archivos problemáticos
        problems_frame = ctk.CTkFrame(analysis_frame)
        problems_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        problems_title = ctk.CTkLabel(
            problems_frame,
            text="🔍 ARCHIVOS QUE EXCEDEN 50MB:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="orange"
        )
        problems_title.pack(pady=(10, 8))
        
        # ScrollableFrame para lista de problemas
        self.problems_scroll = ctk.CTkScrollableFrame(problems_frame, height=120)
        self.problems_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Populate problems list
        for i, result in enumerate(self.validation_summary.validation_results):
            if not result.is_valid:
                self.create_problem_item(result, i)
    
    def create_problem_item(self, result: ValidationResult, index: int):
        """Crear item de problema individual"""
        item_frame = ctk.CTkFrame(self.problems_scroll, fg_color="darkred")
        item_frame.pack(fill="x", pady=2, padx=5)
        item_frame.grid_columnconfigure(1, weight=1)
        
        # Icon de problema
        problem_icon = ctk.CTkLabel(item_frame, text="❌", font=ctk.CTkFont(size=14))
        problem_icon.grid(row=0, column=0, padx=(10, 8), pady=8)
        
        # Info del archivo
        info_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=5)
        info_frame.grid_columnconfigure(0, weight=1)
        
        # Nombre del archivo
        file_name = result.file_path.name
        if len(file_name) > 35:
            file_name = file_name[:32] + "..."
        
        name_label = ctk.CTkLabel(
            info_frame,
            text=file_name,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="white"
        )
        name_label.grid(row=0, column=0, sticky="w")
        
        # Detalles del problema
        details_text = f"Tamaño: {result.size_mb:.1f} MB (excede por {result.size_mb - 50:.1f} MB)"
        if result.recommended_split:
            details_text += f" • Recomendado: dividir en {result.recommended_split} partes"
        
        details_label = ctk.CTkLabel(
            info_frame,
            text=details_text,
            font=ctk.CTkFont(size=10),
            text_color="lightcoral"
        )
        details_label.grid(row=1, column=0, sticky="w", pady=(2, 0))
    
    def create_solution_options(self):
        """Opciones de solución"""
        solutions_frame = ctk.CTkFrame(self)
        solutions_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=10)
        solutions_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Título de soluciones
        solutions_title = ctk.CTkLabel(
            solutions_frame,
            text="🔧 OPCIONES DE SOLUCIÓN",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        solutions_title.grid(row=0, column=0, columnspan=2, pady=(15, 20))
        
        # Opción 1: Auto-ajuste (recomendado)
        auto_frame = ctk.CTkFrame(solutions_frame, fg_color="darkgreen")
        auto_frame.grid(row=1, column=0, sticky="nsew", padx=(15, 8), pady=(0, 10))
        
        auto_title = ctk.CTkLabel(
            auto_frame,
            text="🤖 AJUSTE AUTOMÁTICO (RECOMENDADO)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="lightgreen"
        )
        auto_title.pack(pady=(15, 8))
        
        recommended_files = self.validation_summary.recommended_total_files or 6
        auto_desc = ctk.CTkLabel(
            auto_frame,
            text=f"• Re-dividir automáticamente en {recommended_files} archivos\n"
                 f"• Garantiza que todos los archivos < 50MB\n"
                 f"• Proceso completamente automático\n"
                 f"• Opción más segura y recomendada",
            font=ctk.CTkFont(size=11),
            justify="left"
        )
        auto_desc.pack(pady=(0, 10), padx=15, anchor="w")
        
        auto_button = ctk.CTkButton(
            auto_frame,
            text="✅ Aplicar Ajuste Automático",
            command=self.auto_adjust_action,
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
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="lightyellow"
        )
        custom_title.pack(pady=(15, 8))
        
        # Control personalizado
        custom_control_frame = ctk.CTkFrame(custom_frame, fg_color="transparent")
        custom_control_frame.pack(padx=15, pady=(0, 10))
        
        custom_label = ctk.CTkLabel(custom_control_frame, text="Número de archivos:")
        custom_label.pack()
        
        # Slider para archivos personalizados
        self.custom_slider = ctk.CTkSlider(
            custom_control_frame,
            from_=recommended_files,
            to=min(20, recommended_files + 10),
            variable=self.custom_files_var,
            width=150
        )
        self.custom_slider.pack(pady=5)
        
        # Entry para valor exacto
        self.custom_entry = ctk.CTkEntry(
            custom_control_frame, 
            textvariable=self.custom_files_var, 
            width=80,
            justify="center"
        )
        self.custom_entry.pack(pady=5)
        
        # Info calculada
        self.custom_info_label = ctk.CTkLabel(
            custom_frame,
            text="~XX MB por archivo",
            font=ctk.CTkFont(size=11),
            text_color="lightyellow"
        )
        self.custom_info_label.pack(pady=(0, 10))
        
        custom_button = ctk.CTkButton(
            custom_frame,
            text="🔧 Aplicar Personalizado",
            command=self.custom_adjust_action,
            fg_color="orange",
            hover_color="darkorange",
            height=35
        )
        custom_button.pack(pady=(0, 15), padx=15, fill="x")
        
        # Actualizar info personalizada
        self.on_custom_value_changed()
    
    def create_action_buttons(self):
        """Botones de acción inferior"""
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=(10, 15))
        button_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Botón de proceder de todos modos (peligroso)
        proceed_button = ctk.CTkButton(
            button_frame,
            text="⚠️ Proceder de Todos Modos (RIESGOSO)",
            command=self.proceed_anyway_action,
            fg_color="red",
            hover_color="darkred",
            height=40
        )
        proceed_button.grid(row=0, column=0, padx=(0, 8), pady=10, sticky="ew")
        
        # Botón cancelar
        cancel_button = ctk.CTkButton(
            button_frame,
            text="❌ Cancelar Procesamiento",
            command=self.cancel_action,
            fg_color="gray40",
            hover_color="gray50",
            height=40
        )
        cancel_button.grid(row=0, column=1, padx=(8, 0), pady=10, sticky="ew")
    
    # Event handlers
    def on_custom_value_changed(self, *args):
        """Actualizar info cuando cambia valor personalizado"""
        try:
            custom_files = self.custom_files_var.get()
            if custom_files > 0:
                # Calcular tamaño estimado por archivo
                total_size = self.validation_summary.original_file.stat().st_size / (1024 * 1024)
                size_per_file = total_size / custom_files
                
                self.custom_info_label.configure(
                    text=f"~{size_per_file:.1f} MB por archivo"
                )
                
                # Color coding
                if size_per_file <= 45:
                    self.custom_info_label.configure(text_color="lightgreen")
                elif size_per_file <= 50:
                    self.custom_info_label.configure(text_color="lightyellow")
                else:
                    self.custom_info_label.configure(text_color="lightcoral")
        except:
            pass
    
    # Actions
    def auto_adjust_action(self):
        """Aplicar ajuste automático"""
        try:
            adjusted_summary = self.validator.auto_adjust_split(self.validation_summary)
            
            self.result = PostSplitResult(
                action='auto_adjust',
                adjusted_summary=adjusted_summary
            )
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en ajuste automático: {e}")
    
    def custom_adjust_action(self):
        """Aplicar ajuste personalizado"""
        custom_files = self.custom_files_var.get()
        
        if custom_files <= 0:
            messagebox.showwarning("Valor Inválido", "El número de archivos debe ser mayor a 0")
            return
        
        self.result = PostSplitResult(
            action='custom_adjust',
            custom_files=custom_files
        )
        self.destroy()
    
    def proceed_anyway_action(self):
        """Proceder sin ajustar (peligroso)"""
        result = messagebox.askyesno(
            "⚠️ PROCEDER SIN AJUSTAR - CONFIRMACIÓN CRÍTICA",
            f"🚨 ADVERTENCIA CRÍTICA:\n\n"
            f"Está a punto de procesar {self.validation_summary.files_exceeding_limits} archivos "
            f"que EXCEDEN el límite de 50MB.\n\n"
            f"📊 Archivos problemáticos:\n"
            f"{self._get_problem_files_summary()}\n\n"
            f"🚨 RIESGOS CRÍTICOS:\n"
            f"• Los archivos grandes FALLARÁN al procesar\n"
            f"• Timeouts garantizados en archivos > 50MB\n"
            f"• Consumo excesivo de memoria\n"
            f"• API rechazará la solicitud\n"
            f"• Pérdida de tiempo de procesamiento\n\n"
            f"❓ ¿Realmente desea continuar SIN ajustar?\n"
            f"(SE RECOMIENDA ENCARECIDAMENTE USAR AJUSTE AUTOMÁTICO)"
        )
        
        if result:
            self.result = PostSplitResult(action='proceed_anyway')
            self.destroy()
    
    def cancel_action(self):
        """Cancelar procesamiento"""
        self.result = PostSplitResult(action='cancel')
        self.destroy()
    
    def _get_problem_files_summary(self) -> str:
        """Obtener resumen de archivos problemáticos"""
        problems = []
        for result in self.validation_summary.validation_results:
            if not result.is_valid:
                problems.append(f"• {result.file_path.name}: {result.size_mb:.1f}MB")
        
        return "\n".join(problems[:5])  # Mostrar máximo 5

def show_post_split_validation_dialog(parent, validation_summary: ValidationSummary, 
                                    validator: PDFSplitValidator) -> Optional[PostSplitResult]:
    """
    Mostrar modal de validación post-división
    
    Args:
        parent: Ventana padre
        validation_summary: Resumen de validación con problemas
        validator: Instancia del validador
        
    Returns:
        PostSplitResult con la decisión del usuario
    """
    dialog = PostSplitValidationDialog(parent, validation_summary, validator)
    return dialog.result

# Test function
def test_post_split_dialog():
    """Función de prueba"""
    import tempfile
    from pdf_split_validator import PDFSplitValidator, ValidationSummary, ValidationResult
    
    # Mock validation summary con problemas
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        test_file = Path(tmp.name)
    
    # Mock results problemáticos
    mock_results = [
        ValidationResult(
            file_path=Path("test_part1.pdf"),
            size_mb=65.2,
            pages=150,
            within_size_limit=False,
            within_page_limit=True,
            is_valid=False,
            recommended_split=2
        ),
        ValidationResult(
            file_path=Path("test_part2.pdf"),
            size_mb=58.7,
            pages=140,
            within_size_limit=False,
            within_page_limit=True,
            is_valid=False,
            recommended_split=2
        ),
        ValidationResult(
            file_path=Path("test_part3.pdf"),
            size_mb=45.1,
            pages=120,
            within_size_limit=True,
            within_page_limit=True,
            is_valid=True
        )
    ]
    
    mock_summary = ValidationSummary(
        original_file=test_file,
        total_files_checked=3,
        files_within_limits=1,
        files_exceeding_limits=2,
        total_files_needing_resplit=2,
        all_within_limits=False,
        split_files=[],
        validation_results=mock_results,
        recommended_total_files=6
    )
    
    validator = PDFSplitValidator(max_size_mb=50.0)
    
    # Test dialog
    root = ctk.CTk()
    root.withdraw()
    
    result = show_post_split_validation_dialog(root, mock_summary, validator)
    
    if result:
        print(f"User action: {result.action}")
        if result.custom_files:
            print(f"Custom files: {result.custom_files}")
    
    root.destroy()
    test_file.unlink()

if __name__ == "__main__":
    test_post_split_dialog()