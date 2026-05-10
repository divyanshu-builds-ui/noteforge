import os
import io
import uuid
import base64
import numpy as np
import fitz  # PyMuPDF
from flask import Flask, render_template, request, send_file, jsonify, make_response
from PIL import Image, ImageOps

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

# --- Config ---
SLIDES_PER_PAGE = 4
A4_WIDTH, A4_HEIGHT = 3508, 2480  # A4 landscape at 300 DPI
WHITESPACE_THRESH = 240
PADDING = 15

def pdf_to_images(pdf_path, start_page=1, end_page=9999):
    """Convert PDF pages to PIL Images using PyMuPDF."""
    doc = fitz.open(pdf_path)
    images = []
    end_page = min(end_page, len(doc))
    # Use 150 DPI for faster processing on serverless
    zoom = 150 / 72
    mat = fitz.Matrix(zoom, zoom)
    for i in range(start_page - 1, end_page):
        page = doc[i]
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()
    return images

def trim_horizontal_whitespace(img):
    arr = np.array(img.convert('L'))
    col_means = arr.mean(axis=0)
    non_white = np.where(col_means < WHITESPACE_THRESH)[0]
    if len(non_white) == 0:
        return img
    left, right = non_white[0], non_white[-1]
    pad = 10
    left = max(0, left - pad)
    right = min(arr.shape[1], right + pad)
    return img.crop((left, 0, right, img.size[1]))

def fit_in_cell(img, cell_w, cell_h):
    w, h = img.size
    scale = min((cell_w - 2*PADDING) / w, (cell_h - 2*PADDING) / h)
    new_w, new_h = int(w * scale), int(h * scale)
    return img.resize((new_w, new_h), Image.LANCZOS)

def stitch_slides(images, invert=True):
    slides = []
    for img in images:
        img = trim_horizontal_whitespace(img)
        if invert:
            img = ImageOps.invert(img.convert('RGB'))
        slides.append(img)

    cell_w = A4_WIDTH // 2
    cell_h = A4_HEIGHT // 2

    pages = []
    for i in range(0, len(slides), SLIDES_PER_PAGE):
        batch = slides[i:i + SLIDES_PER_PAGE]
        page = Image.new('RGB', (A4_WIDTH, A4_HEIGHT), 'white')

        for idx, s in enumerate(batch):
            row, col = idx // 2, idx % 2
            resized = fit_in_cell(s, cell_w, cell_h)
            x = col * cell_w + (cell_w - resized.size[0]) // 2
            y = row * cell_h + (cell_h - resized.size[1]) // 2
            page.paste(resized, (x, y))

        pages.append(page)

    return pages, len(slides)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/how-it-works')
def how_it_works():
    return render_template('how_it_works.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/generate', methods=['POST'])
def generate():
    file = request.files.get('pdf')
    if not file:
        return jsonify({'error': 'No file uploaded'}), 400

    start_page = int(request.form.get('start_page', 1))
    end_page = int(request.form.get('end_page', 9999))
    invert = request.form.get('invert', 'off') == 'on'

    # Limit to 40 pages max per request (memory/time optimization)
    if end_page - start_page + 1 > 40:
        return jsonify({'error': 'Max 40 pages per batch. Please reduce page range.', 'success': False}), 400

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filename = f"{uuid.uuid4().hex}.pdf"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        images = pdf_to_images(filepath, start_page, end_page)
        pages, slide_count = stitch_slides(images, invert)

        # Save stitched PDF
        output_id = uuid.uuid4().hex
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{output_id}_stitched.pdf")
        pages[0].save(output_path, format='PDF', save_all=True, append_images=pages[1:], resolution=300)

        # Generate preview thumbnails (first 4 pages)
        previews = []
        for page in pages[:4]:
            thumb = page.copy()
            thumb.thumbnail((600, 400), Image.LANCZOS)
            buf = io.BytesIO()
            thumb.save(buf, format='JPEG', quality=75)
            previews.append(base64.b64encode(buf.getvalue()).decode())

        return jsonify({
            'success': True,
            'output_id': output_id,
            'previews': previews,
            'pages': len(pages),
            'slides': slide_count
        })
    finally:
        os.remove(filepath)

@app.route('/download/<output_id>')
def download(output_id):
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{output_id}_stitched.pdf")
    if not os.path.exists(output_path):
        return "File not found", 404
    return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name='stitched_output.pdf')

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
