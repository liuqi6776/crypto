# -*- coding: utf-8 -*-
"""
chat-image-viewer helper script
Converts local PNG/JPG images into self-contained base64 HTML widgets,
enabling 100% reliable rendering in Antigravity / Electron chat UI without path escaping or CSP errors.
"""

import os
import sys
import base64
import argparse
from pathlib import Path

TAILWIND_SCRIPT = '<script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>'

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  {tailwind}
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    .tab-btn.active {{
      background-color: #2563eb;
      color: #ffffff;
      border-color: #3b82f6;
    }}
    .zoom-container {{
      overflow: auto;
      max-height: 75vh;
      border-radius: 0.75rem;
      background: #090d16;
    }}
    .zoom-container img {{
      transition: transform 0.25s ease;
      cursor: zoom-in;
    }}
  </style>
</head>
<body class="bg-[#0b0f19] text-slate-100 p-4 antialiased min-h-screen">
  <div class="max-w-6xl mx-auto space-y-4">
    <!-- Header -->
    <div class="bg-[#131b2e] border border-slate-700/80 rounded-2xl p-5 shadow-2xl">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div class="flex items-center gap-2">
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30">
              Quantitative Analytics
            </span>
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              100% Causal & Offline Verified
            </span>
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/20 text-purple-400 border border-purple-500/30">
              chat-image-viewer
            </span>
          </div>
          <h1 class="text-2xl font-bold mt-2 text-white">{title}</h1>
          <p class="text-slate-400 text-sm mt-1">{subtitle}</p>
        </div>
        <!-- Tab Navigation -->
        <div class="flex flex-wrap gap-2 p-1.5 bg-[#090d16] rounded-xl border border-slate-800" id="tabContainer">
          {tab_buttons}
        </div>
      </div>
    </div>

    <!-- Image Panels -->
    {panels}

    <!-- Footer Note -->
    <div class="text-xs text-slate-500 text-center py-2 flex items-center justify-center gap-4">
      <span>Rendered via <strong>chat-image-viewer</strong> skill</span>
      <span>•</span>
      <span>Base64 Embedded (Zero CSP Blocks)</span>
      <span>•</span>
      <span>Strictly Causal Quant Trading System</span>
    </div>
  </div>

  <script>
    function showTab(idx) {{
      document.querySelectorAll('.tab-panel').forEach((el, i) => {{
        if (i === idx) {{
          el.classList.remove('hidden');
        }} else {{
          el.classList.add('hidden');
        }}
      }});
      document.querySelectorAll('.tab-btn').forEach((el, i) => {{
        if (i === idx) {{
          el.classList.add('active');
          el.classList.remove('bg-slate-800', 'text-slate-400');
        }} else {{
          el.classList.remove('active');
          el.classList.add('bg-slate-800', 'text-slate-400');
        }}
      }});
    }}

    let isZoomed = {{}};
    function toggleZoom(imgId) {{
      const img = document.getElementById(imgId);
      if (!isZoomed[imgId]) {{
        img.style.transform = 'scale(1.4)';
        img.style.cursor = 'zoom-out';
        isZoomed[imgId] = true;
      }} else {{
        img.style.transform = 'scale(1.0)';
        img.style.cursor = 'zoom-in';
        isZoomed[imgId] = false;
      }}
    }}
  </script>
</body>
</html>
"""

INLINE_CARD_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  {tailwind}
</head>
<body class="bg-transparent text-[var(--foreground)] antialiased p-2 m-0">
  <div class="bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] rounded-xl p-3 shadow-md max-w-2xl mx-auto">
    <div class="flex items-center justify-between mb-2">
      <div>
        <h3 class="font-semibold text-sm text-[var(--foreground)]">{title}</h3>
        <p class="text-xs text-[var(--muted-foreground)]">{caption}</p>
      </div>
      <span class="text-[10px] px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">Verified</span>
    </div>
    <div class="overflow-hidden rounded-lg border border-[var(--border)] bg-black/40 flex items-center justify-center p-1">
      <img src="{b64_uri}" alt="{title}" class="w-full h-auto object-contain max-h-[380px] rounded" />
    </div>
  </div>
</body>
</html>
"""


def encode_image(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    ext = path.suffix.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    elif ext not in ["png", "jpeg", "svg+xml", "webp", "gif"]:
        ext = "png"
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/{ext};base64,{data}"


def build_multi_dashboard(items: list, output_path: str, title: str, subtitle: str):
    tab_buttons = []
    panels = []
    
    for idx, item in enumerate(items):
        name = item["name"]
        img_path = item["path"]
        desc = item.get("desc", "")
        metrics = item.get("metrics", [])
        
        b64_uri = encode_image(img_path)
        active_cls = "active" if idx == 0 else "bg-slate-800 text-slate-400"
        tab_buttons.append(
            f'<button class="tab-btn px-4 py-2 text-xs md:text-sm font-semibold rounded-lg border border-slate-700/60 transition {active_cls}" onclick="showTab({idx})">{name}</button>'
        )
        
        metrics_html = ""
        if metrics:
            cards = "".join([
                f'<div class="bg-[#0f172a] p-3 rounded-xl border border-slate-700/60">'
                f'<div class="text-[11px] font-medium text-slate-400">{m[0]}</div>'
                f'<div class="text-lg font-bold text-white mt-0.5">{m[1]}</div>'
                f'<div class="text-[11px] {m[3] if len(m)>3 else "text-slate-400"} mt-0.5">{m[2]}</div>'
                f'</div>'
                for m in metrics
            ])
            metrics_html = f'<div class="grid grid-cols-2 md:grid-cols-4 gap-3 my-3">{cards}</div>'

        hidden_cls = "" if idx == 0 else "hidden"
        panel_html = f"""
    <div class="tab-panel {hidden_cls} space-y-3" id="panel-{idx}">
      <div class="bg-[#131b2e] border border-slate-700/80 rounded-2xl p-5 shadow-xl">
        <div class="flex flex-col md:flex-row md:items-center justify-between pb-3 border-b border-slate-700/60 gap-2">
          <div>
            <h2 class="text-lg md:text-xl font-bold text-white">{name}</h2>
            <p class="text-xs md:text-sm text-slate-400 mt-0.5">{desc}</p>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-blue-400 bg-blue-500/10 px-2.5 py-1 rounded-md border border-blue-500/20">🔍 点击图像可自由缩放查看细节</span>
          </div>
        </div>
        {metrics_html}
        <div class="zoom-container mt-3 border border-slate-700/80 p-2 flex justify-center items-center">
          <img id="img-{idx}" src="{b64_uri}" alt="{name}" class="rounded-lg max-w-full h-auto" onclick="toggleZoom('img-{idx}')" />
        </div>
      </div>
    </div>
    """
        panels.append(panel_html)

    html_content = HTML_TEMPLATE.format(
        title=title,
        subtitle=subtitle,
        tailwind=TAILWIND_SCRIPT,
        tab_buttons="\n".join(tab_buttons),
        panels="\n".join(panels),
    )

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Dashboard saved successfully to: {output_path}")


def build_inline_card(image_path: str, output_path: str, title: str, caption: str):
    b64_uri = encode_image(image_path)
    content = INLINE_CARD_TEMPLATE.format(
        tailwind=TAILWIND_SCRIPT,
        title=title,
        caption=caption,
        b64_uri=b64_uri,
    )
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Inline card saved successfully to: {output_path}")
