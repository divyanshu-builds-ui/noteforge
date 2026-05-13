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

# Page sizes at 300 DPI (landscape)
PAGE_SIZES = {
    'a4': (3508, 2480),
    'a3': (4961, 3508),
    'letter': (3300, 2550),
}

A4_WIDTH, A4_HEIGHT = 3508, 2480  # default
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


def add_watermark(page, watermark_text):
    if not watermark_text:
        return page
    pw, ph = page.size
    overlay = Image.new('RGBA', page.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 60)
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), watermark_text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # Diagonal watermark repeated
    for y in range(0, ph, 400):
        for x in range(0, pw, 600):
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
    page_size = options.get('page_size', 'a4')

    page_w, page_h = PAGE_SIZES.get(page_size, (3508, 2480))
    cols, rows = GRID_LAYOUTS.get(grid, (2, 2))
    slides_per_page = cols * rows

    slides = []
    for img in images:
        img = trim_horizontal_whitespace(img)
        if invert:
            img = ImageOps.invert(img.convert('RGB'))
        img = adjust_brightness_contrast(img, brightness, contrast)
        slides.append(img)

    cell_w = page_w // cols
    cell_h = page_h // rows

    pages = []
    total_pages = -(-len(slides) // slides_per_page)  # ceil division

    for i in range(0, len(slides), slides_per_page):
        batch = slides[i:i + slides_per_page]
        page = Image.new('RGB', (page_w, page_h), 'white')

        for idx, s in enumerate(batch):
            row, col = idx // cols, idx % cols
            resized = fit_in_cell(s, cell_w, cell_h)
            x = col * cell_w + (cell_w - resized.size[0]) // 2
            y = row * cell_h + (cell_h - resized.size[1]) // 2
            page.paste(resized, (x, y))

        if borders:
            draw = ImageDraw.Draw(page)
            color = (200, 200, 200)
            for c in range(1, cols):
                x = c * cell_w
                draw.line([(x, 0), (x, page_h)], fill=color, width=2)
            for r in range(1, rows):
                y = r * cell_h
                draw.line([(0, y), (page_w, y)], fill=color, width=2)

        if page_numbers:
            draw = ImageDraw.Draw(page)
            page_num = (i // slides_per_page) + 1
            text = f"{page_num} / {total_pages}"
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
            except:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = page_w - tw - 30
            y = page_h - th - 20
            draw.rounded_rectangle([x-12, y-6, x+tw+12, y+th+6], radius=10, fill=(240,240,240))
            draw.text((x, y), text, fill=(100, 100, 100), font=font)

        if watermark:
            page = add_watermark(page, watermark)

        pages.append(page)

    return pages, len(slides)

# --- Routes ---

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500

@app.errorhandler(413)
def file_too_large(e):
    return jsonify({'error': 'File too large. Max 50 MB allowed.', 'success': False}), 413

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200

@app.route('/stitch')
def stitch():
    return render_template('stitch.html')

@app.route('/how-it-works')
def how_it_works():
    return render_template('how_it_works.html')

@app.route('/guide')
def guide():
    return render_template('guide.html')

@app.route('/features')
def features():
    return render_template('features.html')

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
        # Generate first page thumbnail
        zoom = 100 / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = doc[0].get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        buf = io.BytesIO()
        img.thumbnail((400, 300), Image.LANCZOS)
        img.save(buf, format='JPEG', quality=70)
        thumb = base64.b64encode(buf.getvalue()).decode()
        return jsonify({'total_pages': count, 'preview': thumb})
    finally:
        os.remove(filepath)

@app.route('/generate', methods=['POST'])
def generate():
    files = request.files.getlist('pdf')
    if not files or not files[0].filename:
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
    page_size = request.form.get('page_size', 'a4')
    skip_pages_str = request.form.get('skip_pages', '').strip()
    compress = request.form.get('compress', 'off') == 'on'

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    saved_paths = []

    try:
        # Save all uploaded PDFs
        for file in files:
            filename = f"{uuid.uuid4().hex}.pdf"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            saved_paths.append(filepath)

        # Get total pages across all PDFs
        total = 0
        for fp in saved_paths:
            doc = fitz.open(fp)
            total += len(doc)
            doc.close()

        end_page = min(end_page, total)

        if end_page - start_page + 1 > 40:
            batches = []
            for b_start in range(start_page, end_page + 1, 40):
                b_end = min(b_start + 39, end_page)
                batches.append(f"{b_start}-{b_end}")
            return jsonify({
                'success': False,
                'error': f'Max 40 pages per batch. Total pages: {total}.',
                'tip': f'Process in {len(batches)} batches: ' + ', '.join(batches),
                'total_pages': total,
                'suggested_batches': batches
            }), 400

        # Extract images from all PDFs in sequence
        all_images = []
        for fp in saved_paths:
            doc = fitz.open(fp)
            zoom = 150 / 72
            mat = fitz.Matrix(zoom, zoom)
            for i in range(len(doc)):
                page = doc[i]
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                all_images.append(img)
            doc.close()

        # Apply page range on combined images
        images = all_images[start_page - 1:end_page]

        # Parse and apply skip pages
        skip_set = set()
        if skip_pages_str:
            for part in skip_pages_str.split(','):
                part = part.strip()
                if '-' in part:
                    try:
                        a, b = part.split('-')
                        for p in range(int(a), int(b) + 1):
                            skip_set.add(p)
                    except:
                        pass
                elif part.isdigit():
                    skip_set.add(int(part))

        if skip_set:
            images = [img for i, img in enumerate(images) if (start_page + i) not in skip_set]

        options = {
            'invert': invert,
            'grid': grid,
            'borders': borders,
            'page_numbers': page_numbers,
            'brightness': brightness,
            'contrast': contrast,
            'watermark': watermark,
            'page_size': page_size,
        }
        pages, slide_count = stitch_slides(images, options)

        output_id = uuid.uuid4().hex
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{output_id}_stitched.pdf")

        if compress:
            # Save with reduced quality for smaller file size
            compressed_pages = []
            for p in pages:
                buf = io.BytesIO()
                p.save(buf, format='JPEG', quality=60, optimize=True)
                buf.seek(0)
                compressed_pages.append(Image.open(buf).convert('RGB'))
            compressed_pages[0].save(output_path, format='PDF', save_all=True, append_images=compressed_pages[1:], resolution=150)
        else:
            pages[0].save(output_path, format='PDF', save_all=True, append_images=pages[1:], resolution=300)

        # Apply password protection if requested
        pdf_password = request.form.get('pdf_password', '').strip()
        if pdf_password:
            doc = fitz.open(output_path)
            perm = fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY | fitz.PDF_PERM_ANNOTATE
            encrypt_meth = fitz.PDF_ENCRYPT_AES_256
            doc.save(output_path + '.enc', encryption=encrypt_meth, user_pw=pdf_password, permissions=perm)
            doc.close()
            os.replace(output_path + '.enc', output_path)

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
        for fp in saved_paths:
            if os.path.exists(fp):
                os.remove(fp)

@app.route('/download/<output_id>')
def download(output_id):
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{output_id}_stitched.pdf")
    if not os.path.exists(output_path):
        return "File not found", 404
    filename = request.args.get('name', 'stitched_output.pdf')
    return send_file(output_path, mimetype='application/pdf', as_attachment=True, download_name=filename)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
