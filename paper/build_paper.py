import markdown
from pathlib import Path
import webbrowser
import os
base_dir = os.path.dirname(os.path.abspath(__file__))

# Requirements:
#   pip install markdown pymdown-extensions pygments

INPUT_FILES = [
    os.path.join(base_dir, "PRE_REGISTRATION.md"), 
    os.path.join(base_dir, "PAPER.md")
]

OUTPUT_DIR = Path("output_html")

# NOTE: this template uses __TITLE__ / __CONTENT__ placeholders instead of
# str.format() so the embedded JavaScript (with its own { } braces) doesn't
# need to be escaped. Stored as a raw string so MathJax's `\(` / `\)`
# delimiters survive intact.
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>__TITLE__</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&family=Courier+Prime:wght@400;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">

<script>
window.MathJax = {
  tex: {
    inlineMath:  [['\\(', '\\)'], ['$', '$']],
    displayMath: [['\\[', '\\]'], ['$$', '$$']],
    processEscapes: true,
    processEnvironments: true,
    tags: 'ams'
  },
  options: {
    skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
    ignoreHtmlClass: 'tex2jax_ignore',
    processHtmlClass: 'arithmatex'
  },
  svg: { fontCache: 'global' }
};
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>

<style>
  body { font-family: 'Inter', sans-serif; color: #000; background: #f5f5f5; line-height: 1.65; }
  .font-mono { font-family: 'Courier Prime', monospace; }
  .page { max-width: 210mm; margin: 2rem auto; padding: 18mm; border: 1px solid #ccc; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }

  /* Headings */
  .content h1 { font-size: 2.25rem; font-weight: 900; letter-spacing: -0.04em; margin-bottom: 1rem; border-bottom: 3px solid #000; padding-bottom: 0.5rem; }
  .content h2 { font-size: 1.5rem;  font-weight: 800; margin-top: 2rem;   margin-bottom: 1rem;   border-bottom: 1.5px solid #000; padding-bottom: 0.25rem; }
  .content h3 { font-size: 1.2rem;  font-weight: 700; margin-top: 1.5rem; margin-bottom: 0.5rem; }
  .content h4 { font-size: 1.05rem; font-weight: 700; margin-top: 1.25rem; margin-bottom: 0.5rem; font-style: italic; }

  /* Body */
  .content p  { margin-bottom: 1rem; text-align: justify; hyphens: auto; }
  .content ul { list-style-type: disc;    padding-left: 1.5rem; margin-bottom: 1rem; }
  .content ol { list-style-type: decimal; padding-left: 1.5rem; margin-bottom: 1rem; }
  .content li { margin-bottom: 0.25rem; }
  .content a  { color: #1a4d8c; text-decoration: underline; }
  .content hr { border: none; border-top: 1px solid #ccc; margin: 2rem 0; }
  .content img{ max-width: 100%; height: auto; margin: 1rem auto; display: block; }

  /* Tables */
  .content table { width: 100%; border-collapse: collapse; margin: 1.5rem 0; font-size: 0.9rem; }
  .content th    { border-top: 2px solid #000; border-bottom: 2px solid #000; padding: 0.5rem; text-align: left; font-weight: 800; }
  .content td    { border-bottom: 1px solid #ccc; padding: 0.5rem; vertical-align: top; }

  /* Blockquotes & inline code */
  .content blockquote { border-left: 4px solid #000; padding: 0.5rem 1rem; background: #f4f4f4; font-style: italic; margin: 1rem 0; }
  .content code       { font-family: 'Courier Prime', monospace; background: #f4f4f4; padding: 0.15rem 0.35rem; font-size: 0.9em; border-radius: 2px; }

  /* Code blocks (fenced + codehilite/pygments) */
  .content pre, .codehilite { background: #1e1e1e; color: #f8f8f2; padding: 1rem; border-radius: 4px; overflow-x: auto; margin: 1rem 0; font-size: 0.85rem; }
  .content pre code, .codehilite pre { background: transparent; color: inherit; padding: 0; margin: 0; }
  .codehilite .k, .codehilite .kd, .codehilite .kn { color: #66d9ef; }
  .codehilite .s, .codehilite .s1, .codehilite .s2 { color: #e6db74; }
  .codehilite .c, .codehilite .c1, .codehilite .cm { color: #75715e; font-style: italic; }
  .codehilite .nb { color: #ae81ff; }
  .codehilite .mi, .codehilite .mf { color: #ae81ff; }

  /* Definition lists */
  .content dl { margin: 1rem 0; }
  .content dt { font-weight: 700; margin-top: 0.5rem; }
  .content dd { margin-left: 1.5rem; margin-bottom: 0.5rem; }

  /* Footnotes */
  .footnote        { font-size: 0.85rem; border-top: 1px solid #000; margin-top: 3rem; padding-top: 1rem; }
  .footnote ol     { padding-left: 1.25rem; }
  .footnote li     { margin-bottom: 0.5rem; }
  sup a, .footnote-ref, .footnote-backref { text-decoration: none; color: #1a4d8c; }

  /* Task lists */
  .task-list-item        { list-style-type: none; margin-left: -1.25rem; }
  .task-list-item input  { margin-right: 0.5rem; }

  /* Display math spacing */
  mjx-container[display="true"] { margin: 1rem 0 !important; }

/* Print */
  @media print {
    body { background: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .page { border: none; margin: 0; padding: 0; max-width: none; box-shadow: none; }
    .content h2, .content h3 { page-break-after: avoid; }
    .content table, .content img, .content blockquote, .content pre, mjx-container[display="true"] { page-break-inside: avoid; }
    
    /* Printer-friendly code blocks */
    .content pre, .codehilite { 
      background: #f4f4f4 !important; 
      color: #000 !important; 
      border: 1px solid #ccc; 
      white-space: pre-wrap !important; /* Prevents code from running off the page */
      word-wrap: break-word !important;
    }
    .content pre code, .codehilite pre { 
      color: #000 !important; 
    }
    
    /* Override light syntax highlighting colors for white paper */
    .codehilite span { color: #000 !important; }
    .codehilite .c, .codehilite .c1, .codehilite .cm { 
      color: #555 !important; 
      font-style: italic !important; 
    }
  }
</style>
</head>
<body>
<main class="page content">
__CONTENT__
</main>
</body>
</html>
"""


def build_paper():
    OUTPUT_DIR.mkdir(exist_ok=True)

    extensions = [
        "extra",                 # tables, fenced_code, footnotes, attr_list, def_list, abbr
        "sane_lists",            # don't merge unrelated adjacent lists
        "smarty",                # curly quotes, en/em dashes, ellipses
        "toc",                   # heading anchors
        "codehilite",            # syntax highlighting (needs pygments)
        "pymdownx.arithmatex",   # robust LaTeX math handling
        "pymdownx.tilde",        # ~~strikethrough~~
        "pymdownx.caret",        # ^superscript^
        "pymdownx.tasklist",     # - [x] task lists
    ]

    extension_configs = {
        # generic=True emits \(...\) and \[...\] which MathJax v3 handles natively
        "pymdownx.arithmatex": {"generic": True, "preview": False},
        "codehilite":          {"guess_lang": False, "noclasses": False},
        "toc":                 {"permalink": False},
        "pymdownx.tasklist":   {"custom_checkbox": True},
    }

    out_path = None
    for file_path in INPUT_FILES:
        # Fresh instance per file avoids footnote-number bleed-through
        md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
        path = Path(file_path)
        if not path.exists():
            print(f"⚠️  File not found: {path}")
            continue

        print(f"📄 Processing: {path.name}")
        raw_md = path.read_text(encoding="utf-8")

        try:
            html_content = md.convert(raw_md)
        except Exception as e:
            print(f"❌ Failed to convert {path.name}: {e}")
            continue

        final_html = (
            HTML_TEMPLATE
            .replace("__TITLE__", path.stem)
            .replace("__CONTENT__", html_content)
        )

        out_path = OUTPUT_DIR / f"{path.stem}.html"
        out_path.write_text(final_html, encoding="utf-8")
        print(f"✅ Generated: {out_path}")

    if out_path is not None:
        webbrowser.open(f"file://{out_path.resolve()}")


if __name__ == "__main__":
    build_paper()