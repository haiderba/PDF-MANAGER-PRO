import os
import json
import shutil
from flask import Flask, render_template, request, jsonify, url_for, send_from_directory
from pdf2image import convert_from_path
from PIL import Image
from werkzeug.utils import secure_filename
import pytesseract
import cv2
import numpy as np

app = Flask(__name__)

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
TEMP_IMAGES_FOLDER = os.path.join(BASE_DIR, 'temp_images')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs')

for folder in [UPLOAD_FOLDER, TEMP_IMAGES_FOLDER, OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

class DocumentClassifier:
    @staticmethod
    def classify_and_crop(pil_img):
        # OCR for text classification
        try:
            text = pytesseract.image_to_string(pil_img).lower()
        except Exception as e:
            print(f"OCR Error: {e}")
            text = ""
            
        doc_type = "Unknown"
        if any(keyword in text for keyword in ["iqama", "resident", "identity", "kingdom of saudi arabia"]):
            doc_type = "Iqama_ID"
        elif any(keyword in text for keyword in ["insurance", "policy", "medical", "health"]):
            doc_type = "Insurance_Paper"
            
        auto_crop = None
        
        # OpenCV Adaptive Cropping for ID Cards
        if doc_type == "Iqama_ID":
            try:
                cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                edged = cv2.Canny(blurred, 50, 150)
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
                dilated = cv2.dilate(edged, kernel, iterations=2)
                
                contours, _ = cv2.findContours(dilated.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
                    for c in contours:
                        peri = cv2.arcLength(c, True)
                        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                        x, y, w, h = cv2.boundingRect(approx)
                        
                        area = w * h
                        img_area = cv_img.shape[0] * cv_img.shape[1]
                        
                        aspect_ratio = w / float(h)
                        if aspect_ratio < 1:
                            aspect_ratio = 1 / aspect_ratio
                            
                        # Card area > 5% of page, aspect ratio between 1.2 and 2.0
                        if area > img_area * 0.05 and 1.2 < aspect_ratio < 2.0:
                            margin = 15
                            auto_crop = {
                                "x": max(0, x - margin),
                                "y": max(0, y - margin),
                                "width": min(cv_img.shape[1] - x, w + 2*margin),
                                "height": min(cv_img.shape[0] - y, h + 2*margin)
                            }
                            break
            except Exception as e:
                print(f"OpenCV Error: {e}")

        return doc_type, auto_crop

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
                # Convert all pages
                images = convert_from_path(filepath)
                pages_info = []
                
                for idx, img in enumerate(images):
                    page_name = f"{filename}_page{idx+1}.jpg"
                    page_path = os.path.join(TEMP_IMAGES_FOLDER, page_name)
                    img.save(page_path, 'JPEG')
                    
                    pages_info.append({
                        'page_index': idx,
                        'url': url_for('temp_image', filename=page_name),
                        'path': page_path,
                        'document_type': "Pending",
                        'custom_name': f"{os.path.splitext(filename)[0]}_Pending",
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

@app.route('/api/classify', methods=['POST'])
def classify_page():
    data = request.json
    page_path = data.get('path')
    
    if not page_path or not os.path.exists(page_path):
        return jsonify({'error': 'File not found'}), 404
        
    try:
        img = Image.open(page_path)
        doc_type, auto_crop = DocumentClassifier.classify_and_crop(img)
        return jsonify({
            'document_type': doc_type,
            'crop_data': auto_crop
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export', methods=['POST'])
def export_files():
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400

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

    return jsonify({'success': True, 'processed': results})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
