"""
Stitch handwritten class notes into compact A4 PDF pages.
- Crops 15% top / 10% bottom (branding removal)
- Trims horizontal whitespace
- Pastes 4 slides in a 2x2 grid on A4 portrait
- Outputs multi-page PDF
"""

import sys
import numpy as np
from pathlib import Path
from PIL import Image, ImageOps
from pdf2image import convert_from_path

# --- Config ---
TOP_CROP = 0.15
BOTTOM_CROP = 0.10
SLIDES_PER_PAGE = 4
A4_WIDTH, A4_HEIGHT = 3508, 2480  # A4 landscape at 300 DPI
WHITESPACE_THRESH = 240
PADDING = 15  # padding inside each cell

def load_images(input_path):
    p = Path(input_path)
    if p.suffix.lower() == '.pdf':
        return convert_from_path(str(p), dpi=200)
    elif p.is_dir():
        exts = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}
        files = sorted(f for f in p.iterdir() if f.suffix.lower() in exts)
        return [Image.open(f) for f in files]
    else:
        return [Image.open(p)]

def crop_branding(img):
    w, h = img.size
    top = int(h * TOP_CROP)
    bottom = int(h * (1 - BOTTOM_CROP))
    return img.crop((0, top, w, bottom))

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
    """Scale image to fit inside cell while maintaining aspect ratio."""
    w, h = img.size
    scale = min((cell_w - 2*PADDING) / w, (cell_h - 2*PADDING) / h)
    new_w, new_h = int(w * scale), int(h * scale)
    return img.resize((new_w, new_h), Image.LANCZOS)

def process_slides(input_path):
    images = load_images(input_path)
    
    slides = []
    for img in images:
        img = trim_horizontal_whitespace(img)
        img = ImageOps.invert(img.convert('RGB'))
        slides.append(img)
    
    # 2x2 grid: 2 columns, 2 rows
    cell_w = A4_WIDTH // 2
    cell_h = A4_HEIGHT // 2
    
    pages = []
    for i in range(0, len(slides), SLIDES_PER_PAGE):
        batch = slides[i:i + SLIDES_PER_PAGE]
        page = Image.new('RGB', (A4_WIDTH, A4_HEIGHT), 'white')
        
        for idx, s in enumerate(batch):
            row, col = idx // 2, idx % 2
            resized = fit_in_cell(s, cell_w, cell_h)
            # Center in its cell
            x = col * cell_w + (cell_w - resized.size[0]) // 2
            y = row * cell_h + (cell_h - resized.size[1]) // 2
            page.paste(resized, (x, y))
        
        pages.append(page)
    
    output = Path(input_path).stem + "_stitched.pdf"
    output_path = str(Path(input_path).parent / output)
    pages[0].save(output_path, save_all=True, append_images=pages[1:], resolution=300)
    print(f"Saved: {output_path} ({len(pages)} pages from {len(slides)} slides)")

if __name__ == '__main__':
    input_path = sys.argv[1] if len(sys.argv) > 1 else "Revision 10 जैव अणु Class Notes.pdf"
    process_slides(input_path)
