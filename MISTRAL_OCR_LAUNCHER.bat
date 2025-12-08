@echo off
title MISTRAL OCR - LAUNCHER PRINCIPAL
color 0B
cls

:MENU
echo ================================================================================
echo                         MISTRAL OCR V13 - SISTEMA COMPLETO
echo                              LAUNCHER PRINCIPAL
echo ================================================================================
echo.
echo                    Seleccione la opcion que desea ejecutar:
echo.
echo    [1] GUI DESKTOP - Aplicacion completa con todas las funciones
echo        - Validacion PRE y POST division
echo        - Modales interactivos avanzados
echo        - Sistema de limpieza automatica
echo        - Interfaz rapida y responsiva
echo.
echo    [2] UTILIDADES DE MANTENIMIENTO
echo        - Limpiar archivos temporales
echo        - Limpiar archivos redundantes
echo        - Ver estado del sistema
echo.
echo    [3] INFORMACION Y AYUDA
echo        - Ver documentacion
echo        - Requisitos del sistema
echo.
echo    [0] SALIR
echo.
echo ================================================================================
echo.

set /p opcion="Ingrese su opcion (0-3): "

if "%opcion%"=="1" goto GUI_DESKTOP
if "%opcion%"=="2" goto UTILIDADES
if "%opcion%"=="3" goto AYUDA
if "%opcion%"=="0" goto SALIR

echo.
echo ❌ Opcion invalida. Por favor ingrese un numero del 0 al 3.
echo.
pause
cls
goto MENU

:GUI_DESKTOP
cls
echo ================================================================================
echo                      INICIANDO GUI DESKTOP (RECOMENDADO)
echo ================================================================================
echo.
echo 🚀 Iniciando aplicacion desktop con todas las funcionalidades...
echo.
echo Caracteristicas:
echo ✅ Validacion PRE-division inteligente
echo ✅ Modales interactivos completos
echo ✅ Sistema de limpieza automatica
echo ✅ Optimizacion de rendimiento
echo ✅ Procesamiento batch avanzado
echo.
echo Iniciando...
echo.
python mistral_ocr_gui_optimized.py
if %errorlevel% neq 0 (
    echo.
    echo ❌ Error al ejecutar la aplicacion desktop.
    echo    Verifique que Python este instalado y los modulos requeridos.
    echo.
    pause
)
goto MENU


:UTILIDADES
cls
echo ================================================================================
echo                         UTILIDADES DE MANTENIMIENTO
echo ================================================================================
echo.
echo    [1] 🧹 Limpiar archivos temporales (__pycache__, *.tmp, etc.)
echo    [2] 🗑️ Eliminar PDFs divididos antiguos (*_pag*.pdf)
echo    [3] 🧹 LIMPIAR ARCHIVOS REDUNDANTES (streamlit, launchers extras)
echo    [4] 📊 Ver archivos en el directorio
echo    [5] 🔍 Buscar archivos grandes (>50MB)
echo    [6] ⬅️ Volver al menu principal
echo.

set /p util="Seleccione utilidad (1-6): "

if "%util%"=="1" (
    cls
    echo Limpiando archivos temporales...
    echo.
    if exist __pycache__ (
        rmdir /s /q __pycache__
        echo ✅ __pycache__ eliminado
    )
    del *.tmp 2>nul
    del *.temp 2>nul
    del *.log 2>nul
    echo ✅ Archivos temporales eliminados
    echo.
    pause
    goto UTILIDADES
)

if "%util%"=="2" (
    cls
    echo Buscando PDFs divididos...
    echo.
    dir *_pag*.pdf 2>nul
    echo.
    echo ¿Desea eliminar estos archivos?
    choice /C YN /M "Eliminar"
    if %ERRORLEVEL%==1 (
        del *_pag*.pdf 2>nul
        echo ✅ PDFs divididos eliminados
    )
    pause
    goto UTILIDADES
)

if "%util%"=="3" (
    cls
    echo ================================================================================
    echo                    LIMPIEZA DE ARCHIVOS REDUNDANTES
    echo ================================================================================
    echo.
    echo Este script eliminara archivos no esenciales:
    echo - Versiones web de Streamlit
    echo - Launchers secundarios
    echo - Archivos de utilidad duplicados
    echo.
    echo Los archivos se respaldaran antes de eliminar.
    echo.
    python cleanup_redundant.py
    if %errorlevel% neq 0 (
        echo.
        echo ❌ Error al ejecutar el script de limpieza.
        echo.
    )
    pause
    goto UTILIDADES
)

if "%util%"=="4" (
    cls
    echo Archivos en el directorio:
    echo.
    dir /b *.py
    echo.
    echo Archivos de datos:
    dir /b *.pdf *.jpg *.png *.md *.txt 2>nul
    echo.
    pause
    goto UTILIDADES
)

if "%util%"=="5" (
    cls
    echo Buscando archivos grandes (>50MB)...
    echo.
    forfiles /S /M *.* /C "cmd /c if @fsize gtr 52428800 echo @file - @fsize bytes" 2>nul
    echo.
    pause
    goto UTILIDADES
)

if "%util%"=="6" goto MENU

goto UTILIDADES

:AYUDA
cls
echo ================================================================================
echo                         INFORMACION Y AYUDA
echo ================================================================================
echo.
echo 📚 DOCUMENTACION:
echo    - CLAUDE.md: Documentacion completa del proyecto
echo    - requirements.txt: Dependencias necesarias
echo.
echo 💻 REQUISITOS DEL SISTEMA:
echo    - Python 3.8 o superior
echo    - 4GB RAM minimo (8GB recomendado)
echo    - Conexion a Internet para API de Mistral
echo    - API Key de Mistral configurada en .env
echo.
echo 📦 ESTRUCTURA DEL PROYECTO:
echo    CORE:
echo    - mistral_ocr_gui_optimized.py (GUI principal)
echo    - mistral_ocr_client_optimized.py (Motor OCR)
echo.
echo    OPTIMIZADORES:
echo    - batch_optimizer.py
echo    - performance_optimizer.py
echo    - text_md_optimization.py
echo.
echo    VALIDADORES:
echo    - pre_division_validator.py
echo    - split_control_dialog.py
echo.
echo 🔧 INSTALACION DE DEPENDENCIAS:
echo    pip install -r requirements.txt
echo    pip install mistralai
echo.
echo 🔑 CONFIGURACION API KEY:
echo    1. Crear archivo .env en el directorio
echo    2. Agregar: MISTRAL_API_KEY=tu_clave_aqui
echo.
echo ================================================================================
pause
goto MENU

:SALIR
cls
echo ================================================================================
echo                      GRACIAS POR USAR MISTRAL OCR V13
echo ================================================================================
echo.
echo    Sistema desarrollado con:
echo    ❤️  Python + Mistral AI
echo    🚀 Optimizado para alto rendimiento
echo    ✨ Con validacion inteligente PRE y POST division
echo.
echo ================================================================================
echo.
timeout /t 3 >nul
exit