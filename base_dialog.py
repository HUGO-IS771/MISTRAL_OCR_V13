#!/usr/bin/env python3
"""
Base Dialog - Clase Base para Diálogos de Validación
====================================================
Clase base que consolida código duplicado en los diálogos de validación:
- split_control_dialog.py
- post_split_validation_dialog.py
- pre_division_dialog.py

Versión: 1.0.0 - Consolidación Fase 2
Funcionalidad: Herencia y métodos comunes para diálogos
"""

import tkinter as tk
import customtkinter as ctk
from typing import Optional, Callable, Tuple
from abc import ABC, abstractmethod


class BaseValidationDialog(ctk.CTkToplevel, ABC):
    """
    Clase base abstracta para diálogos de validación

    Proporciona funcionalidad común para todos los diálogos de validación:
    - Configuración de ventana modal
    - Centrado sobre ventana padre
    - Creación de headers con iconos
    - Creación de botones de acción
    - Gestión de resultados

    Las clases derivadas deben implementar:
    - create_content(): Contenido específico del diálogo
    - on_confirm(): Acción cuando se confirma
    """

    def __init__(self, parent, title: str, width: int = 700, height: int = 600):
        """
        Inicializa el diálogo base

        Args:
            parent: Ventana padre
            title: Título de la ventana
            width: Ancho de la ventana
            height: Alto de la ventana
        """
        super().__init__(parent)

        self.parent_window = parent
        self.dialog_width = width
        self.dialog_height = height
        self.result = None

        # Configurar ventana
        self.setup_window(title)

        # Modal behavior
        self.transient(parent)
        self.grab_set()
        self.focus_set()

        # Centrar sobre padre
        self.geometry(f"{width}x{height}")
        self.center_on_parent(parent)

    def setup_window(self, title: str, resizable: bool = True):
        """
        Configurar propiedades básicas de la ventana

        Args:
            title: Título de la ventana
            resizable: Si la ventana es redimensionable
        """
        self.title(title)
        self.resizable(resizable, False)  # Horizontal resizable, vertical fijo

        # Configurar grid principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # Content area expandible

    def center_on_parent(self, parent):
        """
        Centrar el diálogo sobre la ventana padre

        Código duplicado eliminado de:
        - split_control_dialog.py (líneas 95-100)
        - post_split_validation_dialog.py (líneas 70-75)
        - pre_division_dialog.py (líneas 72-77)

        Args:
            parent: Ventana padre
        """
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog_width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog_height // 2)
        self.geometry(f"{self.dialog_width}x{self.dialog_height}+{x}+{y}")

    def create_header(
        self,
        icon: str,
        title: str,
        subtitle: str,
        bg_color: str = "darkred",
        title_color: str = "white",
        subtitle_color: str = "lightcoral",
        badge_text: Optional[str] = None,
        badge_color: str = "yellow"
    ) -> ctk.CTkFrame:
        """
        Crear header unificado con icono, título y subtítulo

        Código duplicado eliminado de:
        - split_control_dialog.py (create_header, líneas 110-158)
        - post_split_validation_dialog.py (create_critical_header, líneas 84-129)
        - pre_division_dialog.py (create_warning_header, líneas 86-131)

        Args:
            icon: Emoji para el icono
            title: Título principal
            subtitle: Subtítulo explicativo
            bg_color: Color de fondo del header
            title_color: Color del título
            subtitle_color: Color del subtítulo
            badge_text: Texto opcional para badge (ej: "3/5 PROBLEMÁTICOS")
            badge_color: Color del texto del badge

        Returns:
            Frame del header creado
        """
        header_frame = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=10)
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))
        header_frame.grid_columnconfigure(1, weight=1)

        # Icono grande
        icon_label = ctk.CTkLabel(
            header_frame,
            text=icon,
            font=ctk.CTkFont(size=36, weight="bold")
        )
        icon_label.grid(row=0, column=0, padx=(20, 15), pady=15, rowspan=2)

        # Frame de títulos
        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=15)
        title_frame.grid_columnconfigure(0, weight=1)

        # Título principal
        title_label = ctk.CTkLabel(
            title_frame,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=title_color
        )
        title_label.pack(anchor="w")

        # Subtítulo
        subtitle_label = ctk.CTkLabel(
            title_frame,
            text=subtitle,
            font=ctk.CTkFont(size=13),
            text_color=subtitle_color
        )
        subtitle_label.pack(anchor="w", pady=(3, 0))

        # Badge opcional
        if badge_text:
            badge_label = ctk.CTkLabel(
                header_frame,
                text=badge_text,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=badge_color,
                fg_color="red",
                corner_radius=8
            )
            badge_label.grid(row=0, column=2, padx=(10, 20), pady=15, sticky="ne")

        return header_frame

    def create_info_row(
        self,
        parent_frame: ctk.CTkFrame,
        label: str,
        value: str,
        value_color: str = "white"
    ) -> None:
        """
        Crear fila de información (label: value)

        Patrón repetido en todos los diálogos para mostrar información.

        Args:
            parent_frame: Frame padre donde agregar la fila
            label: Etiqueta (ej: "Archivo:")
            value: Valor a mostrar
            value_color: Color del valor
        """
        row_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        row_frame.pack(fill="x", padx=10, pady=3)

        label_widget = ctk.CTkLabel(
            row_frame,
            text=label,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray60"
        )
        label_widget.pack(side="left")

        value_widget = ctk.CTkLabel(
            row_frame,
            text=value,
            font=ctk.CTkFont(size=12),
            text_color=value_color
        )
        value_widget.pack(side="left", padx=(10, 0))

    def create_action_buttons(
        self,
        buttons_config: list[Tuple[str, str, Callable, Optional[str]]],
        show_cancel: bool = True
    ) -> ctk.CTkFrame:
        """
        Crear botones de acción unificados

        Código duplicado eliminado de todos los diálogos.

        Args:
            buttons_config: Lista de tuplas (texto, color, callback, icon)
                Ejemplo: [("Aceptar", "green", self.on_accept, "✅")]
            show_cancel: Si mostrar botón de cancelar

        Returns:
            Frame de botones creado
        """
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=99, column=0, sticky="ew", padx=20, pady=20)
        button_frame.grid_columnconfigure(0, weight=1)

        # Contenedor para los botones (alineados a la derecha)
        buttons_container = ctk.CTkFrame(button_frame, fg_color="transparent")
        buttons_container.pack(side="right")

        # Botones personalizados
        for text, color, callback, icon in buttons_config:
            display_text = f"{icon} {text}" if icon else text
            btn = ctk.CTkButton(
                buttons_container,
                text=display_text,
                command=callback,
                fg_color=color,
                hover_color=self._darken_color(color),
                font=ctk.CTkFont(size=13, weight="bold"),
                height=36,
                corner_radius=8
            )
            btn.pack(side="left", padx=5)

        # Botón cancelar
        if show_cancel:
            cancel_btn = ctk.CTkButton(
                buttons_container,
                text="❌ Cancelar",
                command=self.on_cancel,
                fg_color="gray30",
                hover_color="gray20",
                font=ctk.CTkFont(size=13),
                height=36,
                corner_radius=8
            )
            cancel_btn.pack(side="left", padx=5)

        return button_frame

    def _darken_color(self, color: str) -> str:
        """
        Oscurecer un color para hover

        Args:
            color: Color base

        Returns:
            Color oscurecido
        """
        color_map = {
            "green": "darkgreen",
            "blue": "darkblue",
            "red": "darkred",
            "orange": "darkorange",
            "gray30": "gray20"
        }
        return color_map.get(color, color)

    def on_cancel(self):
        """Cancelar el diálogo"""
        self.result = None
        self.destroy()

    def wait_for_result(self):
        """
        Esperar a que el usuario responda

        Returns:
            El resultado del diálogo
        """
        self.wait_window()
        return self.result

    @abstractmethod
    def create_content(self):
        """
        Crear el contenido específico del diálogo

        DEBE ser implementado por las clases derivadas.
        """
        pass

    @abstractmethod
    def on_confirm(self):
        """
        Acción cuando se confirma el diálogo

        DEBE ser implementado por las clases derivadas.
        """
        pass


class ScrollableContentDialog(BaseValidationDialog):
    """
    Diálogo base con área de contenido scrolleable

    Útil para diálogos con mucho contenido que necesitan scroll.
    """

    def __init__(self, parent, title: str, width: int = 700, height: int = 600):
        """
        Inicializa diálogo con scroll

        Args:
            parent: Ventana padre
            title: Título
            width: Ancho
            height: Alto
        """
        self.scrollable_frame = None
        super().__init__(parent, title, width, height)

    def create_scrollable_area(self) -> ctk.CTkScrollableFrame:
        """
        Crear área scrolleable para contenido

        Returns:
            Frame scrolleable
        """
        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        return self.scrollable_frame


# Funciones de utilidad para crear componentes comunes
def create_section_title(parent: ctk.CTkFrame, text: str, icon: str = "📊") -> ctk.CTkLabel:
    """
    Crear título de sección estandarizado

    Args:
        parent: Frame padre
        text: Texto del título
        icon: Icono opcional

    Returns:
        Label del título
    """
    title = ctk.CTkLabel(
        parent,
        text=f"{icon} {text}",
        font=ctk.CTkFont(size=15, weight="bold")
    )
    title.pack(pady=(15, 10))
    return title


def create_info_section(parent: ctk.CTkFrame, title: str, bg_color: str = "gray15") -> ctk.CTkFrame:
    """
    Crear sección de información con fondo

    Args:
        parent: Frame padre
        title: Título de la sección
        bg_color: Color de fondo

    Returns:
        Frame de la sección
    """
    section_frame = ctk.CTkFrame(parent, fg_color=bg_color)
    section_frame.pack(fill="x", padx=15, pady=(0, 10))

    if title:
        title_label = ctk.CTkLabel(
            section_frame,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="skyblue"
        )
        title_label.pack(anchor="w", padx=10, pady=(8, 5))

    return section_frame


def create_labeled_value(
    parent: ctk.CTkFrame,
    label: str,
    value: str,
    value_color: str = "white",
    pack: bool = True
) -> Tuple[ctk.CTkLabel, ctk.CTkLabel]:
    """
    Crear par label-value

    Args:
        parent: Frame padre
        label: Etiqueta
        value: Valor
        value_color: Color del valor
        pack: Si hacer pack automáticamente

    Returns:
        Tupla (label_widget, value_widget)
    """
    row_frame = ctk.CTkFrame(parent, fg_color="transparent")
    if pack:
        row_frame.pack(fill="x", padx=10, pady=3)

    label_widget = ctk.CTkLabel(
        row_frame,
        text=label,
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color="gray60"
    )
    label_widget.pack(side="left")

    value_widget = ctk.CTkLabel(
        row_frame,
        text=value,
        font=ctk.CTkFont(size=12),
        text_color=value_color
    )
    value_widget.pack(side="left", padx=(10, 0))

    return label_widget, value_widget
