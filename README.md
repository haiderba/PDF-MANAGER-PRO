# PDF Manager Pro 🚀

A professional, high-performance web application for bulk PDF processing, cropping, and categorized exporting. Designed for workflows where multiple documents (like IDs, insurance papers, or contracts) need to be processed quickly and consistently.

## Key Features
- **Bulk Upload**: Handle multiple PDF files at once.
- **Interactive Cropping**: Powered by Cropper.js for precise document and profile photo extraction.
- **Bulk Apply**: Apply crop settings and document types across all uploaded PDFs with a single click.
- **Smart Exporting**: Automatically categorizes files into folders (e.g., `Iqama_ID/`, `Insurance_Paper/`) and packages them into a ZIP file.
- **Render Ready**: Optimized for deployment on Render.com with Docker support.

## Tech Stack
- **Backend**: Python (Flask)
- **PDF Processing**: `pdf2image` (Poppler) & `Pillow`
- **Frontend**: Vanilla JavaScript + CSS (Glassmorphism design)
- **Styling**: Modern, responsive UI with Inter typography.

## Local Setup

### Prerequisites
- **Python 3.10+**
- **Poppler**: Required for PDF to image conversion.
  - **macOS**: `brew install poppler`
  - **Ubuntu/Debian**: `sudo apt-get install poppler-utils`

### Installation
1. Clone the repository.
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python app.py
   ```
   Access at `http://127.0.0.1:5000`

## Deployment
This project includes a `Dockerfile` and `render.yaml` for easy deployment to Render.
- **Environment**: Docker
- **Port**: 10000 (standard for Render)
