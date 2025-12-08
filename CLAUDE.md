# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Mistral OCR Application

Aplicación OCR optimizada usando Mistral API. Ejecutar con **MISTRAL_OCR_LAUNCHER.bat** para acceder a todas las funcionalidades.

## Estructura Depurada

### 🎯 Punto de Entrada Único
**`MISTRAL_OCR_LAUNCHER.bat`** - Launcher principal con menú interactivo

### 📦 Archivos Core (Esenciales)

#### 1. **mistral_ocr_gui_optimized.py** (Aplicación Principal)
- GUI desktop completa con CustomTkinter
- Procesamiento individual y batch
- Validación PRE y POST división
- Sistema de limpieza automática

#### 2. **mistral_ocr_client_optimized.py** (Motor OCR)
- Cliente optimizado para Mistral API
- Procesamiento de imágenes y PDFs
- Métodos de guardado unificados

### 🔧 Módulos de Optimización

- **batch_optimizer.py** - Cálculo automático de división óptima
- **multi_batch_processor.py** - Procesamiento de múltiples archivos
- **performance_optimizer.py** - Optimizaciones de rendimiento
- **text_md_optimization.py** - Corrección y optimización de texto OCR

### 🛡️ Módulos de Validación

- **pre_division_validator.py** - Validación antes de dividir
- **pre_division_dialog.py** - UI para validación pre-división
- **post_split_validation_dialog.py** - UI para validación post-división
- **pdf_split_validator.py** - Validador de PDFs divididos
- **split_control_dialog.py** - Control avanzado de división
- **file_cleanup_manager.py** - Gestión de limpieza automática


### 🗑️ Archivos Eliminables (Redundantes)

Ejecutar `python cleanup_redundant.py` para limpiar:
- ~~mistral_ocr_streamlit.py~~ (Web v1 no necesaria)
- ~~mistral_ocr_streamlit_v2.py~~ (Web v2 no necesaria)
- ~~launch_mistral_ocr_v2.bat~~ (Launcher duplicado)
- ~~launch_mistral_ocr_web.bat~~ (Launcher duplicado)
- ~~clean.bat~~ (Script de limpieza redundante)
- ~~STREAMLIT INSTRUCTIONS.txt~~ (Documentación obsoleta)

## Key Design Patterns

### 1. **Unified Processing Methods**
All save operations use a single pattern:
```python
def save_as_markdown(self, ocr_response, output_path=None, page_offset=0, 
                    enrich_images=False, optimize=False, domain="general"):
```

### 2. **Dataclass-Based Configuration**
```python
@dataclass
class PDFAnalysis:
    file_path: Path
    total_size_mb: float
    total_pages: int
    density_mb_per_page: float
    requires_splitting: bool
```

### 3. **Factory Pattern for Optimization**
```python
def create_optimized_processor(ocr_client, file_count: int, total_size_mb: float):
    perf_config = PerformanceConfig.get_optimal_config(file_count, total_size_mb)
    return BatchProcessor(ocr_client, max_workers=perf_config['max_workers'])
```

## Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt
pip install mistralai  # Required but not in requirements.txt

# Create API key file
echo "MISTRAL_API_KEY=your_api_key_here" > .env
```

### Run Applications
```bash
# Desktop GUI
python mistral_ocr_gui_optimized.py

# Web interface
streamlit run mistral_ocr_streamlit.py

# Windows launcher (auto-installs dependencies)
lunch_mistral_ocr_web.bat
```

### Testing
```bash
# Test individual modules
python batch_optimizer.py          # Batch optimization
python multi_batch_processor.py    # Multi-file processing
python performance_optimizer.py    # Performance optimizations
python text_md_optimization.py     # Text optimization
```

## API Integration Points

### Main Processing Flow
1. **File Analysis**: `batch_optimizer.analyze_pdf()`
2. **Multi-file Planning**: `multi_batch_processor.analyze_multiple_files()`
3. **Optimized Processing**: `performance_optimizer.process_files_optimized()`
4. **Result Saving**: `mistral_ocr_client_optimized.save_as_markdown()`

### Rate Limits and Performance
- **Max concurrent workers**: 2-4 (adaptive based on file size)
- **File size limits**: 50MB per file
- **Page limits**: 150 pages per file
- **Rate limiting**: 2-4 second delays between requests
- **Caching**: Upload URLs cached for 50 minutes

## Advanced Features

### Automatic Batch Processing
The system automatically calculates optimal file splitting:
```python
# Example: 250MB, 750 pages → 5 files of 50MB/150 pages each
analysis = optimizer.analyze_pdf(file_path, pages_count)
recommendation = optimizer.calculate_optimal_split(analysis)
```

### Multi-File Continuous Processing
Handles multiple documents with continuous page numbering:
```python
summary = processor.analyze_multiple_files(file_paths)
plan = processor.generate_processing_plan(summary)
```

### Performance Optimization
Intelligent grouping and concurrent processing:
```python
# Files grouped by size: small (<10MB), medium (10-30MB), large (>30MB)
grouped_files = processor._group_files_by_size(files_info)
results = processor.process_files_optimized(files_info, config)
```

## Error Handling

- **Rate limits**: Automatic retry with exponential backoff
- **File validation**: Size and format checking before processing
- **Graceful degradation**: Continues processing other files if one fails
- **Detailed logging**: All operations logged for debugging

## Performance Metrics

The system tracks:
- Upload time, processing time, save time
- Pages per second and MB per second
- Cache hit rates
- Rate limit occurrences


## Integration Notes

- Both desktop GUI and web interfaces share the same backend
- All optimization modules are integrated into both interfaces
- Original client methods still available for backward compatibility

## Requirements

### Environment Variable
```bash
MISTRAL_API_KEY=your_api_key_here  # Required in .env file
```

### Key Dependencies
- **mistralai**: Install separately with `pip install mistralai`
- **streamlit>=1.48.0**: Web interface framework
- **customtkinter>=5.2.0**: Modern desktop GUI styling
- **PyPDF2>=3.0.0**: PDF operations
- See requirements.txt for complete list


## Common Development Tasks

### Adding New Features
- **Batch processing**: Extend `BatchOptimizer` class in batch_optimizer.py
- **Performance**: Modify `PerformanceConfig` in performance_optimizer.py
- **UI controls**: Update mistral_ocr_gui_optimized.py or mistral_ocr_streamlit.py

### Programmatic Usage
```python
from mistral_ocr_client_optimized import MistralOCRClient
client = MistralOCRClient()
response = client.process_file("document.pdf")
client.save_as_markdown(response, "output.md")
```

### Streamlit Development
```bash
streamlit run mistral_ocr_streamlit.py --server.runOnSave true  # Auto-reload
streamlit cache clear  # Clear cache
```