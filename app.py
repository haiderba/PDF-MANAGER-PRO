import os
import io
import json
import zipfile
import shutil
from flask import Flask, render_template, request, jsonify, url_for, send_from_directory, send_file
from pdf2image import convert_from_path
from PIL import Image
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
TEMP_IMAGES_FOLDER = os.path.join(BASE_DIR, 'temp_images')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')

for folder in [UPLOAD_FOLDER, TEMP_IMAGES_FOLDER, OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_files():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    files = request.files.getlist('files[]')
    pdf_data = {}

    for file in files:
        if file and file.filename.lower().endswith('.pdf'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            try:
                # Convert all pages with lower DPI for speed and smaller file sizes
                images = convert_from_path(filepath, dpi=120)
                pages_info = []
                
                for idx, img in enumerate(images):
                    page_name = f"{filename}_page{idx+1}.jpg"
                    page_path = os.path.join(TEMP_IMAGES_FOLDER, page_name)
                    # Save with reduced quality to dramatically speed up frontend loading
                    img.save(page_path, 'JPEG', quality=75, optimize=True)
                    
                    pages_info.append({
                        'page_index': idx,
                        'url': url_for('temp_image', filename=page_name),
                        'path': page_path,
                        'document_type': "None",
                        'custom_name': f"{os.path.splitext(filename)[0]}",
                        'crop_data': None
                    })
                    
                pdf_data[filename] = {
                    'pages': pages_info
                }
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                continue

    return jsonify({'pdfs': pdf_data})

@app.route('/temp_images/<filename>')
def temp_image(filename):
    return send_from_directory(TEMP_IMAGES_FOLDER, filename)

def get_unique_filename(directory, base_name, extension):
    counter = 1
    filename = f"{base_name}{extension}"
    while os.path.exists(os.path.join(directory, filename)):
        filename = f"{base_name}_{counter}{extension}"
        counter += 1
    return filename

@app.route('/api/export', methods=['POST'])
def export_files():
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Clear existing outputs folder to prevent returning old files in zip
    if os.path.exists(OUTPUT_FOLDER):
        shutil.rmtree(OUTPUT_FOLDER)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    results = []

    for filename, info in data.items():
        base_name = os.path.splitext(filename)[0]
        pages = info.get('pages', [])

        for page in pages:
            doc_type = page.get('document_type', 'Unknown')
            if doc_type == 'Ignore':
                continue
                
            # Create category folder (e.g. Output/Iqama_ID/)
            dir_name = doc_type if doc_type != "None" else "Uncategorized"
            type_dir = os.path.join(OUTPUT_FOLDER, dir_name)
            os.makedirs(type_dir, exist_ok=True)

            try:
                img = Image.open(page['path'])
                crop_data = page.get('crop_data')
                
                if crop_data:
                    # PIL crop expects (left, upper, right, lower)
                    img = img.crop((
                        crop_data['x'], 
                        crop_data['y'], 
                        crop_data['x'] + crop_data['width'], 
                        crop_data['y'] + crop_data['height']
                    ))
                
                custom_name = page.get('custom_name', f"{base_name}_{doc_type}")
                out_filename = get_unique_filename(type_dir, custom_name, '.jpg')
                
                img.save(os.path.join(type_dir, out_filename))
            except Exception as e:
                print(f"Error exporting {filename} page {page['page_index']}: {e}")

        # Extract Profile Photo if requested
        profile_crop = info.get('profile_crop')
        profile_source_page = info.get('profile_source_page')
        
        if profile_crop and profile_source_page is not None:
            try:
                source_page_info = next((p for p in pages if p['page_index'] == profile_source_page), None)
                if source_page_info:
                    photo_dir = os.path.join(OUTPUT_FOLDER, "Photo")
                    os.makedirs(photo_dir, exist_ok=True)
                    
                    img = Image.open(source_page_info['path'])
                    img = img.crop((
                        profile_crop['x'], 
                        profile_crop['y'], 
                        profile_crop['x'] + profile_crop['width'], 
                        profile_crop['y'] + profile_crop['height']
                    ))
                    
                    out_filename = get_unique_filename(photo_dir, base_name, '.jpg')
                    img.save(os.path.join(photo_dir, out_filename))
            except Exception as e:
                print(f"Error exporting profile photo for {filename}: {e}")

        results.append(filename)

    # Create ZIP file in memory
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(OUTPUT_FOLDER):
            for file in files:
                file_path = os.path.join(root, file)
                archive_name = os.path.relpath(file_path, OUTPUT_FOLDER)
                zf.write(file_path, archive_name)
    
    memory_file.seek(0)
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='PDF_Manager_Pro.zip'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
