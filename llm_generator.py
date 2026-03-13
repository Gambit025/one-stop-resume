"""
三阶段简历格式转换引擎：
  Phase 1: 代码精确提取模板 PDF 样式 → 确定性 CSS
  Phase 2: LLM 只做语义结构化 → JSON
  Phase 3: 代码组装 HTML（CSS + JSON 内容）
"""
import os
import json
import tempfile
import fitz
from openai import OpenAI

KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_BASE_URL = "https://api.moonshot.cn/v1"
TEXT_MODEL = "kimi-k2-turbo-preview"


# ═══════════════════════════════════════════════════════════
# Phase 1: 精确提取模板样式，生成确定性 CSS
# ═══════════════════════════════════════════════════════════

def extract_precise_style(template_pdf: str) -> dict:
    """从模板 PDF 中精确测量所有排版参数。"""
    doc = fitz.open(template_pdf)
    page = doc[0]
    pw, ph = page.rect.width, page.rect.height

    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

    lines = []
    for block in blocks["blocks"]:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            spans_data = []
            for span in line["spans"]:
                if not span["text"].strip():
                    continue
                spans_data.append({
                    "text": span["text"],
                    "size": round(span["size"], 1),
                    "font": span["font"],
                    "bold": "Bold" in span["font"] or "bold" in span["font"].lower(),
                    "serif": "Serif" in span["font"] or "serif" in span["font"].lower(),
                    "color": f'#{span["color"]:06x}',
                    "origin_x": round(span["origin"][0], 1),
                    "origin_y": round(span["origin"][1], 1),
                })
            if spans_data:
                lines.append({
                    "bbox": [round(v, 1) for v in line["bbox"]],
                    "spans": spans_data,
                })

    if not lines:
        doc.close()
        return _default_style()

    # --- 页边距 ---
    all_x0 = [l["bbox"][0] for l in lines]
    all_x2 = [l["bbox"][2] for l in lines]
    margin_left = round(min(all_x0), 1)
    margin_right = round(pw - max(all_x2), 1)
    margin_top = round(lines[0]["bbox"][1], 1)
    content_width = round(pw - margin_left - margin_right, 1)

    # --- 字号角色分类 ---
    size_counts = {}
    for l in lines:
        for s in l["spans"]:
            sz = s["size"]
            size_counts[sz] = size_counts.get(sz, 0) + 1

    sorted_sizes = sorted(size_counts.keys(), reverse=True)
    body_size = max(size_counts, key=size_counts.get)

    name_size = sorted_sizes[0] if sorted_sizes else 20.0

    section_title_size = None
    for sz in sorted_sizes:
        if sz == name_size or sz == body_size:
            continue
        bold_count = sum(1 for l in lines for s in l["spans"] if s["size"] == sz and s["bold"])
        if bold_count >= 2:
            section_title_size = sz
            break
    if section_title_size is None:
        section_title_size = sorted_sizes[1] if len(sorted_sizes) > 1 else 12.0

    entry_header_sizes = [sz for sz in sorted_sizes if sz != name_size and sz != section_title_size and sz != body_size and sz > body_size]
    entry_header_size = entry_header_sizes[0] if entry_header_sizes else round(body_size + 1, 1)

    # --- 字体族 ---
    name_spans = [s for l in lines for s in l["spans"] if s["size"] == name_size]
    body_spans = [s for l in lines for s in l["spans"] if s["size"] == body_size and not s["bold"]]
    section_spans = [s for l in lines for s in l["spans"] if s["size"] == section_title_size and s["bold"]]

    name_font = "sans-serif" if (name_spans and not name_spans[0]["serif"]) else "serif"
    body_font = "serif" if (body_spans and body_spans[0]["serif"]) else "sans-serif"
    section_font = "sans-serif" if (section_spans and not section_spans[0]["serif"]) else "serif"

    # --- 颜色 ---
    name_color = name_spans[0]["color"] if name_spans else "#1a1a1a"
    body_color = body_spans[0]["color"] if body_spans else "#333333"
    bold_spans_all = [s for l in lines for s in l["spans"] if s["bold"] and s["size"] != name_size]
    bold_color = bold_spans_all[0]["color"] if bold_spans_all else "#1a1a1a"

    # --- 行间距 ---
    body_line_gaps = []
    for i in range(1, len(lines)):
        s0 = lines[i - 1]["spans"][0]["size"]
        s1 = lines[i]["spans"][0]["size"]
        if s0 == body_size and s1 == body_size:
            gap = lines[i]["bbox"][1] - lines[i - 1]["bbox"][1]
            if 5 < gap < 25:
                body_line_gaps.append(gap)

    avg_body_gap = round(sum(body_line_gaps) / len(body_line_gaps), 1) if body_line_gaps else round(body_size * 1.4, 1)
    body_line_height = round(avg_body_gap / body_size, 2)

    # --- 章节间距 ---
    section_gaps = []
    for i, l in enumerate(lines):
        if l["spans"][0]["size"] == section_title_size and l["spans"][0]["bold"]:
            if i > 0:
                gap = l["bbox"][1] - lines[i - 1]["bbox"][3]
                if gap > 5:
                    section_gaps.append(gap)
    section_margin_top = round(sum(section_gaps) / len(section_gaps), 1) if section_gaps else 15.0

    # --- 列表标记 ---
    bullet_char = "•"
    bullet_indent = 9.0
    bullet_lines = [l for l in lines if any("◆" in s["text"] or "•" in s["text"] for s in l["spans"])]
    if bullet_lines:
        bl = bullet_lines[0]
        bullet_indent = round(bl["bbox"][0] - margin_left, 1)
        if "◆" in bl["spans"][0]["text"]:
            bullet_char = "◆"

    # --- 姓名对齐 ---
    name_line = lines[0] if lines else None
    name_center_x = (name_line["bbox"][0] + name_line["bbox"][2]) / 2 if name_line else pw / 2
    name_centered = abs(name_center_x - pw / 2) < 50

    # --- 联系方式对齐 ---
    contact_centered = False
    if len(lines) > 1:
        cl = lines[1]
        contact_center_x = (cl["bbox"][0] + cl["bbox"][2]) / 2
        contact_centered = abs(contact_center_x - pw / 2) < 50

    # --- 分割线 ---
    drawings = page.get_drawings()
    has_divider = len(drawings) > 0
    divider_width = 1.0
    divider_color = "#1a1a1a"
    if has_divider:
        d = drawings[0]
        divider_width = round(d.get("width") or 1.0, 1)
        c = d.get("color") or d.get("fill") or (0.1, 0.1, 0.1)
        if isinstance(c, tuple) and len(c) == 3:
            r, g, b = [int(v * 255) for v in c]
            divider_color = f"#{r:02x}{g:02x}{b:02x}"

    # --- 日期右对齐检测 ---
    date_right_aligned = False
    for l in lines:
        if len(l["spans"]) >= 2:
            last_span = l["spans"][-1]
            if last_span["origin_x"] > pw * 0.6:
                date_right_aligned = True
                break

    doc.close()

    return {
        "page_width": round(pw, 1),
        "page_height": round(ph, 1),
        "margin_left": margin_left,
        "margin_right": margin_right,
        "margin_top": margin_top,
        "content_width": content_width,
        "name_size": name_size,
        "name_font": name_font,
        "name_color": name_color,
        "name_centered": name_centered,
        "contact_size": round(body_size, 1),
        "contact_centered": contact_centered,
        "section_title_size": section_title_size,
        "section_title_font": section_font,
        "section_margin_top": section_margin_top,
        "entry_header_size": entry_header_size,
        "body_size": body_size,
        "body_font": body_font,
        "body_color": body_color,
        "body_line_height": body_line_height,
        "bold_color": bold_color,
        "bullet_char": bullet_char,
        "bullet_indent": bullet_indent,
        "has_divider": has_divider,
        "divider_width": divider_width,
        "divider_color": divider_color,
        "date_right_aligned": date_right_aligned,
    }


def _default_style():
    return {
        "page_width": 595.3, "page_height": 841.9,
        "margin_left": 36.0, "margin_right": 36.0, "margin_top": 20.0,
        "content_width": 523.0,
        "name_size": 20.0, "name_font": "sans-serif", "name_color": "#1a1a1a", "name_centered": True,
        "contact_size": 9.0, "contact_centered": True,
        "section_title_size": 12.0, "section_title_font": "sans-serif", "section_margin_top": 15.0,
        "entry_header_size": 10.0,
        "body_size": 9.0, "body_font": "serif", "body_color": "#333333",
        "body_line_height": 1.4, "bold_color": "#1a1a1a",
        "bullet_char": "◆", "bullet_indent": 9.0,
        "has_divider": True, "divider_width": 1.5, "divider_color": "#1a1a1a",
        "date_right_aligned": True,
    }


def generate_css(style: dict) -> str:
    """从精确测量的样式参数生成确定性 CSS。"""
    s = style
    sans = "'Noto Sans SC', 'Helvetica Neue', Arial, sans-serif"
    serif = "'Noto Serif SC', 'Georgia', 'Times New Roman', serif"

    name_ff = sans if s["name_font"] == "sans-serif" else serif
    body_ff = serif if s["body_font"] == "serif" else sans
    section_ff = sans if s["section_title_font"] == "sans-serif" else serif

    return f"""@page {{ size: A4; margin: 0; }}

body {{
  width: {s['page_width']}pt;
  margin: 0 auto;
  padding: {s['margin_top']}pt {s['margin_right']}pt 20pt {s['margin_left']}pt;
  box-sizing: border-box;
  font-family: {body_ff};
  font-size: {s['body_size']}pt;
  color: {s['body_color']};
  line-height: {s['body_line_height']};
}}

.name {{
  font-family: {name_ff};
  font-size: {s['name_size']}pt;
  font-weight: 700;
  color: {s['name_color']};
  text-align: {'center' if s['name_centered'] else 'left'};
  margin: 0 0 4pt 0;
}}

.contact {{
  font-size: {s['contact_size']}pt;
  text-align: {'center' if s['contact_centered'] else 'left'};
  margin-bottom: 6pt;
}}

.section {{
  margin-top: {s['section_margin_top']}pt;
}}

.section-title {{
  font-family: {section_ff};
  font-size: {s['section_title_size']}pt;
  font-weight: 700;
  color: {s['bold_color']};
  margin: 0;
  padding-bottom: 3pt;
  {'border-bottom: ' + str(s['divider_width']) + 'pt solid ' + s['divider_color'] + ';' if s['has_divider'] else ''}
  margin-bottom: 6pt;
}}

.entry {{
  margin-top: 4pt;
}}

.entry-header {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: {s['entry_header_size']}pt;
  font-weight: 700;
  color: {s['bold_color']};
  margin: 0;
}}

.entry-header .date {{
  font-weight: 400;
  font-size: {round(s['body_size'] + 0.5, 1)}pt;
  white-space: nowrap;
  margin-left: 12pt;
}}

.entry-subtitle {{
  font-size: {s['body_size'] + 1}pt;
  font-weight: 700;
  color: {s['bold_color']};
  margin: 1pt 0;
}}

.entry-detail {{
  margin: 1pt 0;
}}

.item-list {{
  list-style: none;
  padding: 0;
  margin: 2pt 0 0 0;
}}

.item-list li {{
  padding-left: {s['bullet_indent'] + 12}pt;
  text-indent: -{s['bullet_indent'] + 2}pt;
  margin-bottom: 1pt;
}}

.item-list li::before {{
  content: '{s['bullet_char']}';
  display: inline-block;
  width: {s['bullet_indent'] + 2}pt;
}}

.bold {{
  font-weight: 700;
  color: {s['bold_color']};
}}"""


# ═══════════════════════════════════════════════════════════
# Phase 2: LLM 只做语义结构化
# ═══════════════════════════════════════════════════════════

def extract_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()


def structure_resume_via_llm(resume_text: str) -> dict:
    """LLM 只负责理解简历内容的语义结构，输出 JSON。"""
    client = OpenAI(api_key=KIMI_API_KEY, base_url=KIMI_BASE_URL)

    system_prompt = """你是一个简历结构分析专家。你的唯一任务是分析简历纯文字，输出结构化 JSON。

你不需要做任何格式化或排版工作，只需要理解内容的语义角色。

输出严格遵循以下 JSON 格式（不要输出任何其他内容）：

```json
{
  "name": "姓名",
  "contact": "联系方式（单行，保留原文分隔符）",
  "sections": [
    {
      "title": "章节标题（如：教育经历、实习经历、科研成果、竞赛奖项等）",
      "entries": [
        {
          "header": "机构/公司/奖项名称",
          "date": "日期（如有）",
          "subtitle": "职位/专业/补充说明（如有，否则为空字符串）",
          "details": ["非列表项的补充文字行（如有）"],
          "items": ["列表项1（带具体描述的条目）", "列表项2"]
        }
      ]
    }
  ]
}
```

关键规则：
1. 每一个字都必须来自原文，不能增删改任何文字
2. 正确区分 header（机构名/奖项名）、date（日期）、subtitle（职位/专业）、details（补充说明行）、items（详细描述列表项）
3. 如果一个条目没有列表项描述，items 为空数组
4. 只输出 JSON，不要任何解释"""

    resp = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请分析以下简历的结构：\n\n{resume_text}"},
        ],
        temperature=0.1,
    )

    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)

    return json.loads(raw)


# ═══════════════════════════════════════════════════════════
# Phase 3: 代码组装 HTML
# ═══════════════════════════════════════════════════════════

def assemble_html(css: str, content: dict) -> str:
    """用确定性代码将 CSS 和结构化内容组装成 HTML。"""

    def esc(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    parts = [
        '<!DOCTYPE html>',
        '<html lang="zh-CN">',
        '<head>',
        '<meta charset="UTF-8">',
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700&family=Noto+Serif+SC:wght@400;700&display=swap" rel="stylesheet">',
        f'<style>{css}</style>',
        '</head>',
        '<body>',
    ]

    parts.append(f'<div class="name">{esc(content.get("name", ""))}</div>')
    parts.append(f'<div class="contact">{esc(content.get("contact", ""))}</div>')

    for section in content.get("sections", []):
        parts.append('<div class="section">')
        parts.append(f'  <div class="section-title">{esc(section.get("title", ""))}</div>')

        for entry in section.get("entries", []):
            parts.append('  <div class="entry">')

            header = entry.get("header", "")
            date = entry.get("date", "")
            if header:
                if date:
                    parts.append(f'    <div class="entry-header"><span>{esc(header)}</span><span class="date">{esc(date)}</span></div>')
                else:
                    parts.append(f'    <div class="entry-header"><span>{esc(header)}</span></div>')

            subtitle = entry.get("subtitle", "")
            if subtitle:
                parts.append(f'    <div class="entry-subtitle">{esc(subtitle)}</div>')

            for detail in entry.get("details", []):
                if detail:
                    parts.append(f'    <div class="entry-detail">{esc(detail)}</div>')

            items = entry.get("items", [])
            if items:
                parts.append('    <ul class="item-list">')
                for item in items:
                    parts.append(f'      <li>{esc(item)}</li>')
                parts.append('    </ul>')

            parts.append('  </div>')
        parts.append('</div>')

    parts.append('</body>')
    parts.append('</html>')

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
# PDF 输出 + 主流程
# ═══════════════════════════════════════════════════════════

def html_to_pdf(html_content: str, output_path: str):
    from playwright.sync_api import sync_playwright

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        f.write(html_content)
        tmp_html = f.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"file://{tmp_html}")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            page.pdf(
                path=output_path,
                format="A4",
                margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
                print_background=True,
            )
            browser.close()
    finally:
        os.unlink(tmp_html)


def generate_resume(resume_pdf: str, template_pdf: str, output_dir: str) -> dict:
    """三阶段流程：精确样式 → 语义结构化 → 组装输出"""
    os.makedirs(output_dir, exist_ok=True)

    print("[Phase 1/3] 精确提取模板样式...")
    style = extract_precise_style(template_pdf)
    css = generate_css(style)
    print(f"  提取完成: name={style['name_size']}pt, body={style['body_size']}pt, margin={style['margin_left']}pt")

    with open(os.path.join(output_dir, "style.json"), "w", encoding="utf-8") as f:
        json.dump(style, f, ensure_ascii=False, indent=2)
    with open(os.path.join(output_dir, "style.css"), "w", encoding="utf-8") as f:
        f.write(css)

    print("[Phase 2/3] LLM 语义结构化...")
    resume_text = extract_text(resume_pdf)
    content = structure_resume_via_llm(resume_text)
    print(f"  识别到 {len(content.get('sections', []))} 个板块")

    with open(os.path.join(output_dir, "content.json"), "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

    print("[Phase 3/3] 组装 HTML 并生成 PDF...")
    html = assemble_html(css, content)

    html_path = os.path.join(output_dir, "output.html")
    pdf_path = os.path.join(output_dir, "output.pdf")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    html_to_pdf(html, pdf_path)
    print(f"  完成: {html_path}")

    return {"html_path": html_path, "pdf_path": pdf_path, "style": style}


if __name__ == "__main__":
    result = generate_resume(
        "/Users/qinruihan/Desktop/简历agent/秦睿涵-最新.pdf",
        "/Users/qinruihan/Desktop/RYAN/杨璇-简历.pdf",
        "/Users/qinruihan/Desktop/简历agent/llm_test_output",
    )
    print(f"\nHTML: {result['html_path']}")
    print(f"PDF:  {result['pdf_path']}")
