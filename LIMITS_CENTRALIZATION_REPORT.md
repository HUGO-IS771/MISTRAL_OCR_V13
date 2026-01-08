# Reporte de Centralización de Límites de Procesamiento

## Resumen

Se ha corregido la **inconsistencia #4** relacionada con límites de validación distribuidos en diferentes módulos, creando un único punto de verdad para todos los límites de la API de Mistral OCR.

---

## 🎯 Problema Identificado

### Inconsistencias detectadas:

1. **[mistral_ocr_client_optimized.py:148](mistral_ocr_client_optimized.py#L148)**
   - `process_local_file()` usaba `max_size_mb=50` por defecto

2. **[mistral_ocr_client_optimized.py:1226](mistral_ocr_client_optimized.py#L1226)**
   - `_validate_batch_files()` usaba límite hardcodeado `50`

3. **[batch_optimizer.py:97-98](batch_optimizer.py#L97-L98)**
   - `BatchOptimizer` usaba `MAX_SIZE_MB = 48.0` y `MAX_PAGES = 145`

4. **[mistral_ocr_gui_optimized.py:71-72](mistral_ocr_gui_optimized.py#L71-L72)**
   - GUI usaba `MAX_FILE_SIZE_MB = 50.0` y `MAX_PAGES_PER_FILE = 135`

5. **Validadores** (pre_division_validator, pdf_split_validator, etc.)
   - Usaban valores hardcodeados `50.0`, `45.0`, etc.

### Resultado:
❌ **Comportamiento inconsistente**: Diferentes módulos aplicaban diferentes límites al validar archivos.

---

## ✅ Solución Implementada

### 1. Nuevo archivo centralizado: `processing_limits.py`

Se creó un módulo de configuración unificado con:

```python
from processing_limits import LIMITS

# Límites seguros (con margen de seguridad)
LIMITS.SAFE_MAX_SIZE_MB  # 48.0 MB (96% del límite API)
LIMITS.SAFE_MAX_PAGES    # 135 páginas (90% del límite API)

# Límites absolutos de la API
LIMITS.API_MAX_SIZE_MB   # 50.0 MB
LIMITS.API_MAX_PAGES     # 150 páginas

# Factores de seguridad
LIMITS.SAFETY_FACTOR_SIZE   # 0.96 (4% margen)
LIMITS.SAFETY_FACTOR_PAGES  # 0.90 (10% margen)

# Workers y concurrencia
LIMITS.DEFAULT_WORKERS   # 2
LIMITS.MAX_WORKERS       # 10
```

### 2. Funciones de utilidad incluidas:

```python
from processing_limits import get_safe_limits, is_within_limits, get_exceeded_limits

# Obtener límites
max_size, max_pages = get_safe_limits()

# Validar
if is_within_limits(file_size_mb, pages_count):
    print("Archivo dentro de límites")

# Identificar qué se excedió
exceeded = get_exceeded_limits(file_size_mb, pages_count)
# Retorna: ["Tamaño (55 MB > 48 MB)", "Páginas (150 > 135)"]
```

---

## 📝 Archivos Actualizados

### Archivos principales modificados:

1. **✅ [mistral_ocr_client_optimized.py](mistral_ocr_client_optimized.py)**
   - Importa `LIMITS`
   - `process_local_file()` usa `LIMITS.DEFAULT_MAX_SIZE_MB`
   - `_validate_batch_files()` usa `LIMITS.BATCH_MAX_SIZE_MB`

2. **✅ [batch_optimizer.py](batch_optimizer.py)**
   - Importa `LIMITS`
   - `BatchOptimizer.__init__()` usa límites centralizados
   - Mantiene aliases para compatibilidad

3. **✅ [mistral_ocr_gui_optimized.py](mistral_ocr_gui_optimized.py)**
   - Importa `LIMITS`
   - Constantes ahora usan `LIMITS.SAFE_MAX_SIZE_MB` y `LIMITS.SAFE_MAX_PAGES`

4. **✅ [batch_processor.py](batch_processor.py)**
   - Importa `LIMITS`
   - `MAX_SIZE_MB` y `MAX_PAGES` ahora referencian a `LIMITS`
   - Pre-validación usa `LIMITS.SAFE_MAX_SIZE_MB`

5. **✅ [pre_division_validator.py](pre_division_validator.py)**
   - Importa `LIMITS`
   - Test cases usan `LIMITS.SAFE_MAX_SIZE_MB`

6. **✅ [pdf_split_validator.py](pdf_split_validator.py)**
   - Importa `LIMITS`
   - Test cases usan `LIMITS.SAFE_MAX_SIZE_MB`

7. **✅ [pre_division_dialog.py](pre_division_dialog.py)**
   - Test cases importan y usan `LIMITS.SAFE_MAX_SIZE_MB`

8. **✅ [post_split_validation_dialog.py](post_split_validation_dialog.py)**
   - Test cases importan y usan `LIMITS.SAFE_MAX_SIZE_MB`

---

## 🔍 Verificación de Consistencia

### Antes (comportamiento inconsistente):

| Módulo | Límite Tamaño | Límite Páginas |
|--------|--------------|----------------|
| `process_local_file()` | 50 MB | - |
| `_validate_batch_files()` | 50 MB | - |
| `BatchOptimizer` | 48 MB | 145 |
| GUI | 50 MB | 135 |
| Validadores | 45-50 MB | - |

### Después (comportamiento unificado):

| Módulo | Límite Tamaño | Límite Páginas |
|--------|--------------|----------------|
| **TODOS** | **48 MB** | **135** |

---

## 🎉 Beneficios

1. **✅ Consistencia total**: Todos los módulos usan los mismos límites
2. **✅ Mantenimiento simplificado**: Un solo lugar para ajustar límites
3. **✅ Transparencia**: Documentación clara de límites y márgenes
4. **✅ Seguridad**: Márgenes de seguridad bien definidos (96% tamaño, 90% páginas)
5. **✅ Compatibilidad**: Aliases mantenidos para código legacy
6. **✅ Utilidades**: Funciones helper para validación rápida

---

## 🔧 Uso para Desarrolladores

### Importar límites centralizados:

```python
from processing_limits import LIMITS

# Usar en validaciones
if file_size_mb > LIMITS.SAFE_MAX_SIZE_MB:
    raise ValueError(f"Archivo excede {LIMITS.SAFE_MAX_SIZE_MB} MB")

# Crear configuraciones
config = ProcessingConfig(
    max_size_mb=LIMITS.SAFE_MAX_SIZE_MB,
    max_pages=LIMITS.SAFE_MAX_PAGES
)
```

### Modificar límites globalmente:

Para ajustar límites en toda la aplicación, editar **únicamente** [processing_limits.py](processing_limits.py):

```python
# processing_limits.py
@dataclass(frozen=True)
class ProcessingLimits:
    # Ajustar estos valores cambia TODA la aplicación
    SAFE_MAX_SIZE_MB: float = 48.0  # ← Cambiar aquí
    SAFE_MAX_PAGES: int = 135        # ← Cambiar aquí
```

---

## 📋 Testing

### Ejecutar tests de límites:

```bash
# Test de límites centralizados
python processing_limits.py

# Test de validadores
python pre_division_validator.py
python pdf_split_validator.py
```

### Output esperado:

```
=== LÍMITES DE PROCESAMIENTO MISTRAL OCR ===

Límites de Procesamiento Mistral OCR:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Tamaño máximo: 48.0 MB
• Páginas máximas: 135 páginas
• Workers por defecto: 2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nota: Límites con margen de seguridad aplicado.
API absolutos: 50.0 MB / 150 páginas

Límites seguros: (48.0, 135)

Ejemplo de validación:
  - Archivo de 45 MB, 120 páginas: True
  - Archivo de 55 MB, 100 páginas: False
    Excedidos: ['Tamaño (55.0 MB > 48.0 MB)']
```

---

## ⚠️ Notas Importantes

1. **NO hardcodear límites**: Siempre importar de `processing_limits.py`
2. **Márgenes de seguridad**: Los límites incluyen márgenes para evitar rechazos de API
3. **Límites absolutos**: No intentar usar valores mayores a `API_MAX_SIZE_MB` / `API_MAX_PAGES`
4. **Compatibilidad**: Código legacy sigue funcionando gracias a aliases

---

## 📊 Estructura del módulo

```
processing_limits.py
├── ProcessingLimits (dataclass)
│   ├── API_MAX_SIZE_MB = 50.0
│   ├── API_MAX_PAGES = 150
│   ├── SAFE_MAX_SIZE_MB = 48.0 ⭐
│   ├── SAFE_MAX_PAGES = 135 ⭐
│   ├── SAFETY_FACTOR_SIZE = 0.96
│   ├── SAFETY_FACTOR_PAGES = 0.90
│   ├── PDF_OVERHEAD_MB = 0.5
│   ├── DEFAULT_WORKERS = 2
│   └── MAX_WORKERS = 10
│
├── LIMITS (instancia global) ⭐
│
└── Funciones de utilidad:
    ├── get_safe_limits()
    ├── is_within_limits()
    ├── get_exceeded_limits()
    └── format_limits_info()
```

---

## ✅ Estado del Proyecto

**Inconsistencia #4: RESUELTA** ✅

Todos los límites de procesamiento ahora están centralizados en `processing_limits.py`, eliminando comportamientos inconsistentes entre módulos.

**Fecha**: 2025-12-26
**Versión**: 1.0.0
**Autor**: Refactorización Fase 4
