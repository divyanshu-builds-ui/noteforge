import os
import io
import uuid
import base64
import numpy as np
import fitz  # PyMuPDF
from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image, ImageOps, ImageDraw, ImageFont, ImageEnhance

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# --- Config ---
A4_WIDTH, A4_HEIGHT = 3508, 2480  # A4 landscape at 300 DPI
WHITESPACE_THRESH = 240
PADDING = 15

# Grid layouts: name -> (cols, rows)
GRID_LAYOUTS = {
    '2x1': (2, 1),
    '2x2': (2, 2),
    '3x2': (3, 2),
    '3x3': (3, 3),
    '1x2': (1, 2),
    '1x4': (1, 4),
}

# Theme colors
THEMES = {
    'dark': {'bg': '#06060b', 'card': '#14141c', 'text': '#e4e4e7', 'accent': '#667eea'},
    'light': {'bg': '#f8fafc', 'card': '#ffffff', 'text': '#1e293b', 'accent': '#667eea'},
}

def pdf_to_images(pdf_path, start_page=1, end_page=9999):
    doc = fitz.open(pdf_path)
    images = []
    end_page = min(end_page, len(doc))
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

def adjust_brightness_contrast(img, brightness=1.0, contrast=1.0):
    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    return img

def fit_in_cell(img, cell_w, cell_h):
    w, h = img.size
    scale = min((cell_w - 2*PADDING) / w, (cell_h - 2*PADDING) / h)
    new_w, new_h = int(w * scale), int(h * scale)
    return img.resize((new_w, new_h), Image.LANCZOS)

def draw_borders(page, cols, rows, cell_w, cell_h):
    draw = ImageDraw.Draw(page)
    color = (200, 200, 200)
    # Vertical lines
    for c in range(1, cols):
        x = c * cell_w
        draw.line([(x, 0), (x, A4_HEIGHT)], fill=color, width=2)
    # Horizontal lines
    for r in range(1, rows):
        y = r * cell_h
        draw.line([(0, y), (A4_WIDTH, y)], fill=color, width=2)

def add_page_number(page, page_num, total_pages):
    draw = ImageDraw.Draw(page)
    text = f"{page_num} / {total_pages}"
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = A4_WIDTH - tw - 30
    y = A4_HEIGHT - th - 20
    draw.rounded_rectangle([x-12, y-6, x+tw+12, y+th+6], radius=10, fill=(240,240,240))
    draw.text((x, y), text, fill=(100, 100, 100), font=font)

def add_watermark(page, watermark_text):
    if not watermark_text:
        return page
    overlay = Image.new('RGBA', page.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 60)
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), watermark_text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # Diagonal watermark repeated
    for y in range(0, A4_HEIGHT, 400):
        for x in range(0, A4_WIDTH, 600):
            txt_img = Image.new('RGBA', (tw + 20, th + 20), (255, 255, 255, 0))
            txt_draw = ImageDraw.Draw(txt_img)
            txt_draw.text((10, 10), watermark_text, fill=(180, 180, 180, 40), font=font)
            rotated = txt_img.rotate(30, expand=True, fillcolor=(0, 0, 0, 0))
            overlay.paste(rotated, (x, y), rotated)
    page_rgba = page.convert('RGBA')
    return Image.alpha_composite(page_rgba, overlay).convert('RGB')

def stitch_slides(images, options):
    invert = options.get('invert', True)
    grid = options.get('grid', '2x2')
    borders = options.get('borders', False)
    page_numbers = options.get('page_numbers', False)
    brightness = options.get('brightness', 1.0)
    contrast = options.get('contrast', 1.0)
    watermark = options.get('watermark', '')

    cols, rows = GRID_LAYOUTS.get(grid, (2, 2))
    slides_per_page = cols * rows

    slides = []
    for img in images:
        img = trim_horizontal_whitespace(img)
        if invert:
            img = ImageOps.invert(img.convert('RGB'))
        img = adjust_brightness_contrast(img, brightness, contrast)
        slides.append(img)

    cell_w = A4_WIDTH // cols
    cell_h = A4_HEIGHT // rows

    pages = []
    total_pages = -(-len(slides) // slides_per_page)  # ceil division

    for i in range(0, len(slides), slides_per_page):
        batch = slides[i:i + slides_per_page]
        page = Image.new('RGB', (A4_WIDTH, A4_HEIGHT), 'white')

        for idx, s in enumerate(batch):
            row, col = idx // cols, idx % cols
            resized = fit_in_cell(s, cell_w, cell_h)
            x = col * cell_w + (cell_w - resized.size[0]) // 2
            y = row * cell_h + (cell_h - resized.size[1]) // 2
            page.paste(resized, (x, y))

        if borders:
            draw_borders(page, cols, rows, cell_w, cell_h)

        if page_numbers:
            page_num = (i // slides_per_page) + 1
            add_page_number(page, page_num, total_pages)

        if watermark:
            page = add_watermark(page, watermark)

        pages.append(page)

    return pages, len(slides)

# --- Routes ---

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(413)
def file_too_large(e):
    return jsonify({'error': 'File too large. Max 50 MB allowed.', 'success': False}), 413

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/how-it-works')
def how_it_works():
    return render_template('how_it_works.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/get-page-count', methods=['POST'])
def get_page_count():
    file = request.files.get('pdf')
    if not file:
        return jsonify({'error': 'No file'}), 400

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filename = f"{uuid.uuid4().hex}.pdf"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        doc = fitz.open(filepath)
        count = len(doc)
        doc.close()
        return jsonify({'total_pages': count})
    finally:
        os.remove(filepath)

@app.route('/generate', methods=['POST'])
def generate():
    file = request.files.get('pdf')
    if not file:
        return jsonify({'error': 'No file uploaded'}), 400

    start_page = int(request.form.get('start_page', 1))
    end_page = int(request.form.get('end_page', 9999))
    invert = request.form.get('invert', 'off') == 'on'
    grid = request.form.get('grid', '2x2')
    borders = request.form.get('borders', 'off') == 'on'
    page_numbers = request.form.get('page_numbers', 'off') == 'on'
    brightness = float(request.form.get('brightness', 1.0))
    contrast = float(request.form.get('contrast', 1.0))
    watermark = request.form.get('watermark', '').strip()

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filename = f"{uuid.uuid4().hex}.pdf"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        doc = fitz.open(filepath)
        total = len(doc)
        doc.close()
        end_page = min(end_page, total)

        if end_page - start_page + 1 > 40:
            batches = []
            for b_start in range(start_page, end_page + 1, 40):
                b_end = min(b_start + 39, end_page)
                batches.append(f"{b_start}-{b_end}")
            return jsonify({
                'success': False,
                'error': f'Max 40 pages per batch. Your PDF has {total} pages.',
                'tip': f'Process in {len(batches)} batches: ' + ', '.join(batches),
                'total_pages': total,
                'suggested_batches': batches
            }), 400

        images = pdf_to_images(filepath, start_page, end_page)
        options = {
            'invert': invert,
            'grid': grid,
            'borders': borders,
            'page_numbers': page_numbers,
            'brightness': brightness,
            'contrast': contrast,
            'watermark': watermark,
        }
        pages, slide_count = stitch_slides(images, options)

        output_id = uuid.uuid4().hex
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{output_id}_stitched.pdf")
        pages[0].save(output_path, format='PDF', save_all=True, append_images=pages[1:], resolution=300)

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
