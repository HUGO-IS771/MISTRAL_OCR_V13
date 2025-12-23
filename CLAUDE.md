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

### Optimization Layer

**batch_optimizer.py** - Intelligent file splitting
- `PDFAnalysis` dataclass: file analysis results
- `SplitRecommendation` dataclass: optimal split strategy
- `BatchOptimizer` class calculates splits based on:
  - File size limit: 45MB (with 95% safety factor)
  - Page limit: 135 pages (with 97% safety factor)
  - Density analysis (MB per page)

**multi_batch_processor.py** - Multi-file coordination
- `MultiBatchProcessor` handles multiple PDFs with continuous page numbering
- Generates unified output from split files
- Tracks processing across file boundaries

**performance_optimizer.py** - Concurrency optimization
- `PerformanceConfig` for adaptive worker allocation
- Groups files by size (small <10MB, medium 10-30MB, large >30MB)
- Adjusts concurrency based on total workload

**text_md_optimization.py** - Post-processing
- `TextOptimizer` for OCR text cleanup
- `MarkdownOptimizer` for markdown formatting improvements
- Domain-specific optimization (legal, medical, technical, general)

### Validation Layer

**pre_division_validator.py** + **pre_division_dialog.py** - Pre-split validation
- Validates file before splitting
- Shows analysis and recommendations in UI dialog

**pdf_split_validator.py** + **post_split_validation_dialog.py** - Post-split validation
- Verifies split files integrity
- Confirms page counts and file sizes

**split_control_dialog.py** - Advanced split control
- Custom split configuration UI
- Manual override of automatic recommendations

**file_cleanup_manager.py** - Temporary file management
- Tracks split files created during processing
- Automatic cleanup after successful processing

## Key Design Patterns

### Dataclass-Based Configuration
All major data structures use dataclasses for type safety and clarity:
```python
@dataclass
class PDFAnalysis:
    file_path: Path
    total_size_mb: float
    total_pages: int
    density_mb_per_page: float
    requires_splitting: bool
    reason: str = ""

@dataclass
class ProcessingConfig:
    api_key: str
    model: str = "mistral-ocr-latest"
    max_size_mb: float = 50.0
    max_pages: int = 135
    optimize: bool = True
```

### Unified Processing Flow
All file processing follows the same pattern:
1. Analyze file → `BatchOptimizer.analyze_pdf()`
2. Recommend split (if needed) → `BatchOptimizer.calculate_optimal_split()`
3. Process → `MistralOCRClient.process_file()`
4. Save → `MistralOCRClient.save_as_markdown()`

### Separation of Concerns
- **Logic modules** (batch_optimizer, performance_optimizer): Pure functions, no UI
- **Dialog modules** (*_dialog.py): UI components that call logic modules
- **Manager modules** (*_processor.py, *_validator.py): Coordinate between logic and UI

## Commands

### Setup
```bash
# Install dependencies (includes mistralai)
pip install -r requirements.txt

# Configure API key
echo MISTRAL_API_KEY=your_api_key_here > .env
```

### Run
```bash
# Recommended: Use launcher
MISTRAL_OCR_LAUNCHER.bat

# Or run GUI directly
python mistral_ocr_gui_optimized.py

# Run purge utility
python purge_application.py
```

## Mistral API Integration

### Critical Constraints
The application is designed around Mistral API limitations:
- **File size**: 50MB absolute limit, 45MB working limit (95% safety factor)
- **Page count**: 150 pages absolute limit, 135 pages working limit (97% safety factor)
- **Rate limiting**: 2-4 second delays between requests
- **Upload URL caching**: 50 minute cache lifetime

### Processing Flow
1. File upload → Mistral API (returns URL cached for 50 mins)
2. OCR request → Mistral API with cached URL
3. Response parsing → Extract text and embedded images
4. Text optimization → Domain-specific cleanup
5. Save → Markdown file with optional embedded images

### Programmatic Usage
```python
from mistral_ocr_client_optimized import MistralOCRClient

# Basic usage
client = MistralOCRClient()
response = client.process_file("document.pdf")
client.save_as_markdown(response, "output.md")

# With optimization
client.save_as_markdown(
    response,
    "output.md",
    optimize=True,
    domain="legal",  # or "medical", "technical", "general"
    enrich_images=True
)

# Export to premium HTML with embedded images
client.save_as_html(
    response,
    "output.html",
    title="Mi Documento",
    theme="light"  # or "dark"
)
```

### Batch Processing Example
```python
from batch_optimizer import BatchOptimizer
from mistral_ocr_client_optimized import MistralOCRClient

# Analyze and split large file
optimizer = BatchOptimizer()
analysis = optimizer.analyze_pdf("large_doc.pdf", pages_count=300)

if analysis.requires_splitting:
    recommendation = optimizer.calculate_optimal_split(analysis)
    # recommendation.num_files, recommendation.pages_per_file
    # Use these values to split the PDF
```

## Important Limits and Behaviors

### File Splitting Logic
Files are split when either condition is met:
- Size exceeds 45MB (safety margin below 50MB API limit)
- Pages exceed 135 (safety margin below 150 page API limit)

Split calculations prioritize:
1. Staying under limits with safety margin
2. Creating equal-sized chunks
3. Minimizing number of splits (fewer API calls)

### Supported File Formats
- **PDF**: .pdf
- **Images**: .jpg, .jpeg, .png, .tiff, .tif

MIME types are registered at module import in mistral_ocr_client_optimized.py

### Text Optimization Domains
- **legal**: Legal documents (contract clauses, legal citations)
- **medical**: Medical records (medication names, diagnoses)
- **technical**: Technical documentation (code, specifications)
- **general**: General purpose documents

## Development Notes

### Adding New Validation Dialogs
Dialog modules follow this pattern:
1. Import validation logic from corresponding *_validator.py
2. Create CustomTkinter dialog class
3. Call logic methods and display results
4. Return user decision (proceed/cancel/modify)

### Extending Batch Optimizer
To modify split logic:
- Edit `BatchOptimizer` class in batch_optimizer.py
- Adjust `MAX_SIZE_MB` and `MAX_PAGES` constants
- Modify `SAFETY_FACTOR_SIZE` and `SAFETY_FACTOR_PAGES` for margins

### Error Handling Strategy
- File validation errors → Show dialog, prevent processing
- API errors → Retry with exponential backoff
- Split validation errors → Show issues, allow user override
- Cleanup errors → Log warning, continue

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