# ⚡ NoteForge — Smart PDF Stitcher

> Stitch class note slides into compact, print-ready PDFs. Save paper & ink.

🔗 **Live:** [noteforge-by-divyanshu.up.railway.app](https://noteforge-by-divyanshu.up.railway.app)

![NoteForge Screenshot](assets/Screenshot_2026-04-29_01-24-12.png)

---

## 🎯 What is NoteForge?

NoteForge is a web app built for students who want to print their class notes (PDF slides) efficiently. It takes bulky slide-per-page PDFs and stitches multiple slides onto a single page in a grid layout — saving up to **75% paper** and **80% ink**.

No signup. No watermark (unless you want one). No BS.

---

## ✨ Features

### Core
| Feature | Description |
|---------|-------------|
| 📐 Custom Grid Layouts | 6 layouts — `2×2`, `2×1`, `3×2`, `3×3`, `1×2`, `1×4` |
| 🎨 Smart Color Invert | Dark backgrounds → white. Saves ~80% ink |
| ✂️ Auto Whitespace Trim | Detects & removes unnecessary horizontal margins |
| 📄 Page Range Selection | Process only the pages you need (40 pages/batch) |
| 🚫 Selective Page Removal | Skip specific pages or ranges (e.g. `3, 7, 12-15`) |
| 📑 Multiple PDF Merge | Upload 2-3 PDFs and stitch them together in sequence |
| 📄 Custom Page Size | A4, Letter, A3 output support |

### Customization
| Feature | Description |
|---------|-------------|
| 📏 Border Lines | Separator lines between slides |
| #️⃣ Page Numbers | Auto page numbers (1/20 style) on every output page |
| 📝 Watermark | Diagonal watermark (name/subject) on every page |
| ☀️ Brightness & Contrast | Fine-tune brightness (50–150%) and contrast (50–200%) |
| 🔒 Password Protection | AES-256 encrypt output PDF with a password |
| 📦 Compression | Reduce output file size by ~40-60% for sharing |

### UX & Polish
| Feature | Description |
|---------|-------------|
| 🌙 Dark / Light Theme | Toggle with auto-save preference |
| 📱 PWA (Installable) | Install as app on phone/desktop, works offline |
| ⌨️ Keyboard Shortcuts | `Ctrl+U` upload, `Ctrl+G` generate, `Esc` cancel |
| 📊 Stats & History | Track conversions, slides processed, pages saved |
| 🎯 Step Progress Bar | Clear 4-step indicator (Upload → Configure → Generate → Download) |
| 👁️ Quick Preview | First page thumbnail shown immediately after upload |
| 📋 Live Estimate | Shows expected output pages before generating |
| 🎉 Confetti & Sound | Celebration animation + sound on successful generation |
| 🖨️ Print Directly | Print output without downloading first |
| 📤 Share | WhatsApp, Telegram, Copy Link, Native Share |
| 💾 Remember Settings | Last used settings auto-saved for next session |
| 🔄 Reset Button | One-click reset all settings to defaults |
| ⚡ Splash Screen | Animated logo on first visit (per session) |
| 🌐 Offline Page | Graceful offline fallback with retry |
| 🔔 Network Detection | Toast notifications for online/offline status |

---

## 🖼️ Screenshots

| Dashboard | Stitch Tool |
|-----------|-------------|
| ![Dashboard](assets/Screenshot_2026-04-29_01-24-12.png) | ![Stitch](assets/Screenshot_2026-04-29_01-24-34.png) |

---

## 🛠️ Tech Stack

- **Backend:** Python, Flask
- **PDF Processing:** PyMuPDF (fitz)
- **Image Processing:** Pillow, NumPy
- **Frontend:** Jinja2 templates, vanilla CSS/JS
- **Icons:** Lucide Icons (SVG)
- **PWA:** Service Worker + Web App Manifest
- **Deployment:** Railway / Docker / Vercel

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+

### Local Setup

```bash
git clone https://github.com/divyanshu-builds-ui/Noteforge.git
cd Noteforge
pip install -r requirements.txt
python app.py
```

App runs at `http://localhost:5000`

### Docker

```bash
docker build -t noteforge .
docker run -p 5000:5000 noteforge
```

---

## 📁 Project Structure

```
Noteforge/
├── app.py              # Flask app with all routes & PDF processing
├── stitch_notes.py     # CLI script for quick local stitching
├── api/
│   └── index.py        # Vercel serverless entry point
├── static/
│   ├── style.css       # Global styles + animations
│   ├── sw.js           # Service worker (PWA + offline)
│   ├── offline.html    # Offline fallback page
│   ├── manifest.json   # PWA manifest
│   └── icon-*.png      # App icons
├── templates/
│   ├── base.html       # Base layout (navbar, sidebar, footer, splash)
│   ├── index.html      # Dashboard
│   ├── stitch.html     # Main stitching tool
│   ├── features.html   # Features page
│   ├── how_it_works.html
│   ├── guide.html
│   ├── about.html
│   ├── 404.html        # Not found page
│   └── 500.html        # Server error page
├── Dockerfile
├── vercel.json
└── requirements.txt
```

---

## 🌐 Deployment

### Railway (Recommended)

Live at: [noteforge-by-divyanshu.up.railway.app](https://noteforge-by-divyanshu.up.railway.app)

### Vercel (Serverless)

```bash
vercel --prod
```

### Docker (Self-hosted)

```bash
docker build -t noteforge .
docker run -d -p 5000:5000 noteforge
```

---

## 🧑‍💻 CLI Usage

```bash
python stitch_notes.py "path/to/your-notes.pdf"
```

Outputs `*_stitched.pdf` with 2×2 grid, inverted colors, and trimmed whitespace.

---

## ⚙️ Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_CONTENT_LENGTH` | 50 MB | Max upload file size |
| Page sizes | A4, Letter, A3 | Output page dimensions at 300 DPI |
| `WHITESPACE_THRESH` | 240 | Threshold for whitespace detection |
| Max pages per batch | 40 | Large PDFs are split into batches |

---

## 📄 License

MIT

---

## 🙌 Contributing

PRs welcome! Feel free to open issues for bugs or feature requests.

---

Built with ⚡ by **[Divyanshu Gupta](https://github.com/divyanshu-builds-ui)**
