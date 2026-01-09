# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Mistral OCR Application

OCR application using Mistral AI API for processing PDFs and images into markdown format. This is a Python desktop application with intelligent batch processing and file splitting capabilities.

## Entry Point

**MISTRAL_OCR_LAUNCHER.bat** - Main Windows launcher with interactive menu for:
- GUI Desktop application (recommended)
- Maintenance utilities
- Help and documentation

## Architecture

### Core Components

**mistral_ocr_client_optimized.py** - OCR processing engine
- `MistralOCRClient` class handles all Mistral API interactions
- `ImageProcessor` class for image data extraction and format detection
- Unified `save_as_markdown()` method for all output operations
- Supports images (.jpg, .png, .tiff) and PDFs

**mistral_ocr_gui_optimized.py** - Desktop GUI application
- Built with CustomTkinter for modern UI
- `ProcessingConfig` dataclass for configuration management
- Single and batch file processing
- Pre-division and post-split validation dialogs
- Automatic cleanup of temporary split files

### Centralized Limits (Single Source of Truth)

**processing_limits.py** - All API limits are defined here
- `ProcessingLimits` frozen dataclass with all limits
- `LIMITS` global singleton instance - import and use this
- Deprecated aliases emit warnings for backward compatibility
- Safe limits are calculated dynamically from API limits × safety factors

**core_analyzer.py** - Unified file analysis logic
- `FileAnalyzer` class consolidates all analysis from batch_optimizer, pre_division_validator, pdf_split_validator
- `FileMetrics`, `SplitAnalysis`, `SplitPlan` dataclasses
- `quick_analyze()` convenience function for one-line analysis

### Optimization Layer

**batch_optimizer.py** - Intelligent file splitting
- `PDFAnalysis` and `SplitRecommendation` dataclasses
- `BatchOptimizer` calculates splits using limits from `processing_limits.py`

**multi_batch_processor.py** - Multi-file coordination
- `MultiBatchProcessor` handles multiple PDFs with continuous page numbering

**performance_optimizer.py** - Concurrency optimization
- `PerformanceConfig` for adaptive worker allocation
- Groups files by size (small <10MB, medium 10-30MB, large >30MB)

**text_md_optimization.py** - Post-processing
- `TextOptimizer` for OCR text cleanup
- `MarkdownOptimizer` for markdown formatting improvements
- Domain-specific optimization (legal, medical, technical, general)

### Validation Layer

**pre_division_validator.py** + **pre_division_dialog.py** - Pre-split validation
**pdf_split_validator.py** + **post_split_validation_dialog.py** - Post-split validation
**split_control_dialog.py** - Advanced split control with manual override
**file_cleanup_manager.py** - Temporary file management

## Key Design Patterns

### Centralized Limits Access
Always import limits from the central module:
```python
from processing_limits import LIMITS

# Access calculated safe limits
max_size = LIMITS.safe_max_size_mb  # 96 MB (100 × 0.96)
max_pages = LIMITS.safe_max_pages   # 900 (1000 × 0.90)

# Check limits
result = LIMITS.check_limits(size_mb=50, pages=200)
if not result.within_limits:
    print(result.exceeded)  # List of exceeded limits
```

### Dataclass-Based Configuration
All major data structures use dataclasses:
```python
@dataclass
class PDFAnalysis:
    file_path: Path
    total_size_mb: float
    total_pages: int
    density_mb_per_page: float
    requires_splitting: bool
    reason: str = ""
```

### Unified Processing Flow
1. Analyze file → `FileAnalyzer.get_file_metrics()` or `BatchOptimizer.analyze_pdf()`
2. Check split needs → `FileAnalyzer.analyze_split_needs()`
3. Calculate split → `FileAnalyzer.get_optimal_split_plan()`
4. Process → `MistralOCRClient.process_file()`
5. Save → `MistralOCRClient.save_as_markdown()`

### Separation of Concerns
- **Logic modules** (batch_optimizer, performance_optimizer, core_analyzer): Pure functions, no UI
- **Dialog modules** (*_dialog.py): UI components that call logic modules
- **Manager modules** (*_processor.py, *_validator.py): Coordinate between logic and UI

## Commands

### Setup
```bash
pip install -r requirements.txt
echo MISTRAL_API_KEY=your_api_key_here > .env
```

### Run
```bash
# Recommended: Use launcher
MISTRAL_OCR_LAUNCHER.bat

# Or run GUI directly
python mistral_ocr_gui_optimized.py
```

## Mistral API Integration

### Critical Constraints (from processing_limits.py)
- **File size**: 100MB absolute limit, 96MB safe limit (96% safety factor)
- **Page count**: 1000 pages absolute limit, 900 pages safe limit (90% safety factor)
- **Rate limiting**: 2 second delays between requests
- **Upload URL caching**: 50 minute cache lifetime

### Programmatic Usage
```python
from mistral_ocr_client_optimized import MistralOCRClient

client = MistralOCRClient()
response = client.process_file("document.pdf")
client.save_as_markdown(response, "output.md")

# With optimization
client.save_as_markdown(
    response, "output.md",
    optimize=True,
    domain="legal",  # or "medical", "technical", "general"
    enrich_images=True
)

# Export to HTML
client.save_as_html(response, "output.html", title="Document", theme="light")
```

### Quick Analysis Example
```python
from core_analyzer import quick_analyze

metrics, analysis, plan = quick_analyze("large_doc.pdf")
if analysis.requires_splitting:
    print(f"Split into {plan.num_files} files, {plan.pages_per_file} pages each")
```

## Important Limits and Behaviors

### File Splitting Logic
Files are split when either condition is met:
- Size exceeds 96MB (safe margin below 100MB API limit)
- Pages exceed 900 (safe margin below 1000 page API limit)

### Supported File Formats
- **PDF**: .pdf
- **Images**: .jpg, .jpeg, .png, .tiff, .tif

### Text Optimization Domains
- **legal**: Legal documents (contract clauses, legal citations)
- **medical**: Medical records (medication names, diagnoses)
- **technical**: Technical documentation (code, specifications)
- **general**: General purpose documents

## Development Notes

### Modifying Limits
Edit only `processing_limits.py`:
```python
@dataclass(frozen=True)
class ProcessingLimits:
    API_MAX_SIZE_MB: float = 100.0   # Change API limits here
    API_MAX_PAGES: int = 1000
    SAFETY_FACTOR_SIZE: float = 0.96  # Change safety factors here
    SAFETY_FACTOR_PAGES: float = 0.90
```

### Adding New Validation Dialogs
1. Import validation logic from corresponding *_validator.py
2. Create CustomTkinter dialog class extending `base_dialog.py`
3. Call logic methods and display results
4. Return user decision (proceed/cancel/modify)

## Environment Requirements

**Required**:
- Python 3.8+
- MISTRAL_API_KEY in .env file

**Key Dependencies** (from requirements.txt):
- mistralai>=1.0.0 (Mistral API client)
- customtkinter>=5.2.0 (Modern GUI framework)
- PyPDF2>=3.0.0 (PDF manipulation)
- Pillow>=9.0.0 (Image processing)
- python-dotenv>=1.0.0 (Environment variables)
- datauri>=2.0.0 (Image data URI parsing)
