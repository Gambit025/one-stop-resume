"""
生成4套内置简历模板 PDF，存入 static/templates/
"""
import os
import json
import tempfile

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "static", "templates")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SAMPLE_CONTENT = {
    "name": "王晓明",
    "contact": "wangxiaoming@email.com | 138-0000-0000 | 北京市 | github.com/xiaoming",
    "sections": [
        {
            "title": "教育经历",
            "entries": [
                {
                    "header": "北京大学",
                    "date": "2020.09 — 2024.06",
                    "subtitle": "计算机科学与技术 · 本科",
                    "items": ["GPA 3.8/4.0，专业前 5%", "主修课程：数据结构、算法分析、机器学习、计算机网络"]
                }
            ]
        },
        {
            "title": "实习经历",
            "entries": [
                {
                    "header": "字节跳动",
                    "date": "2023.07 — 2023.09",
                    "subtitle": "后端开发工程师（实习）",
                    "items": [
                        "负责推荐系统核心模块开发，优化接口响应时间 40%",
                        "设计并实现用户行为数据缓存方案，日均处理请求 1000 万次",
                        "参与代码 Review 及技术文档编写，推动团队规范化建设"
                    ]
                },
                {
                    "header": "腾讯",
                    "date": "2022.12 — 2023.02",
                    "subtitle": "前端开发工程师（实习）",
                    "items": [
                        "参与微信小程序功能迭代，完成 3 个核心页面重构",
                        "引入组件化开发模式，减少重复代码约 30%"
                    ]
                }
            ]
        },
        {
            "title": "项目经历",
            "entries": [
                {
                    "header": "分布式任务调度系统",
                    "date": "2023.03 — 2023.06",
                    "subtitle": "个人项目 · Go / Redis / Docker",
                    "items": [
                        "基于 Raft 协议实现分布式一致性，支持节点动态扩缩容",
                        "任务吞吐量达 5000 TPS，延迟 P99 < 10ms",
                        "开源至 GitHub，获 Star 200+"
                    ]
                }
            ]
        },
        {
            "title": "技能特长",
            "entries": [
                {
                    "header": "编程语言",
                    "date": "",
                    "subtitle": "",
                    "items": ["熟练：Python、Go、JavaScript / TypeScript", "了解：Java、C++、Rust"]
                },
                {
                    "header": "工具与框架",
                    "date": "",
                    "subtitle": "",
                    "items": ["React、Vue、Flask、FastAPI、Docker、Kubernetes、MySQL、Redis"]
                }
            ]
        }
    ]
}

TEMPLATES = [
    {
        "id": "minimal",
        "name": "极简黑白",
        "desc": "简洁克制，适合技术岗",
        "css": """
@page { size: A4; margin: 0; }
body {
  width: 595pt; margin: 0 auto;
  padding: 0 0 28pt 0;
  box-sizing: border-box;
  font-family: 'Noto Sans SC', 'Helvetica Neue', Arial, sans-serif;
  font-size: 9pt; color: #2d2d2d; line-height: 1.5;
}
.header-block {
  background: #111;
  padding: 28pt 48pt 20pt 48pt;
  margin-bottom: 6pt;
}
.name { font-size: 24pt; font-weight: 700; color: #fff; text-align: center; margin: 0 0 6pt; letter-spacing: 2pt; }
.contact { font-size: 8.5pt; text-align: center; color: #aaa; }
.body-wrap { padding: 0 48pt; }
.section { margin-top: 14pt; }
.section-title {
  font-size: 8pt; font-weight: 700; text-transform: uppercase;
  letter-spacing: 2pt; color: #111;
  display: flex; align-items: center; gap: 8pt;
  margin-bottom: 7pt;
}
.section-title::after {
  content: ''; flex: 1; height: 0.75pt; background: #ccc;
}
.entry { margin-top: 6pt; }
.entry-header { display: flex; justify-content: space-between; align-items: baseline; font-weight: 700; font-size: 9.5pt; }
.entry-header .date { font-weight: 400; font-size: 8pt; color: #888; white-space: nowrap; }
.entry-subtitle { font-size: 8.5pt; color: #666; margin: 1.5pt 0 2pt; }
.item-list { list-style: none; padding: 0; margin: 2pt 0 0; }
.item-list li { padding-left: 12pt; text-indent: -7pt; margin-bottom: 1.5pt; }
.item-list li::before { content: '—'; display: inline-block; width: 7pt; color: #bbb; font-size: 8pt; }
"""
    },
    {
        "id": "classic",
        "name": "经典学术",
        "desc": "衬线字体，传统专业风",
        "css": """
@page { size: A4; margin: 0; }
body {
  width: 595pt; margin: 0 auto;
  padding: 0 0 28pt 0;
  box-sizing: border-box;
  font-family: 'Noto Serif SC', 'Georgia', serif;
  font-size: 9.5pt; color: #1a1a1a; line-height: 1.55;
}
.header-block {
  text-align: center;
  padding: 30pt 50pt 16pt 50pt;
  border-bottom: 3pt double #000;
  margin-bottom: 4pt;
}
.name { font-size: 26pt; font-weight: 700; color: #000; margin: 0 0 8pt; letter-spacing: 3pt; }
.contact { font-size: 8.5pt; color: #444; font-family: 'Noto Sans SC', sans-serif; line-height: 1.6; }
.body-wrap { padding: 0 50pt; }
.section { margin-top: 13pt; }
.section-title {
  font-size: 10.5pt; font-weight: 700; color: #000;
  font-family: 'Noto Sans SC', sans-serif;
  letter-spacing: 1pt;
  border-bottom: 1pt solid #000;
  padding-bottom: 2.5pt; margin-bottom: 6pt;
  display: flex; align-items: center; gap: 6pt;
}
.section-title::before { content: '§'; font-size: 9pt; color: #666; font-family: serif; font-weight: 400; }
.entry { margin-top: 6pt; }
.entry-header { display: flex; justify-content: space-between; align-items: baseline; font-weight: 700; font-size: 10pt; font-family: 'Noto Sans SC', sans-serif; }
.entry-header .date { font-weight: 400; font-size: 8.5pt; color: #555; white-space: nowrap; }
.entry-subtitle { font-size: 9pt; font-style: italic; color: #444; margin: 1.5pt 0 2pt; }
.item-list { list-style: none; padding: 0; margin: 2pt 0 0; }
.item-list li { padding-left: 14pt; text-indent: -8pt; margin-bottom: 1.5pt; }
.item-list li::before { content: '◆'; display: inline-block; width: 8pt; font-size: 4.5pt; color: #555; vertical-align: middle; }
"""
    },
    {
        "id": "modern",
        "name": "现代蓝调",
        "desc": "蓝色点缀，清爽现代感",
        "css": """
@page { size: A4; margin: 0; }
body {
  width: 595pt; margin: 0 auto;
  padding: 0 0 28pt 0;
  box-sizing: border-box;
  font-family: 'Noto Sans SC', 'Helvetica Neue', Arial, sans-serif;
  font-size: 9pt; color: #334155; line-height: 1.5;
}
.header-block {
  background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
  padding: 26pt 44pt 20pt 44pt;
  margin-bottom: 4pt;
}
.name { font-size: 26pt; font-weight: 700; color: #fff; text-align: left; margin: 0 0 6pt; letter-spacing: 0.5pt; }
.contact { font-size: 8.5pt; text-align: left; color: #bfdbfe; }
.body-wrap { padding: 0 44pt; }
.section { margin-top: 14pt; }
.section-title {
  font-size: 9.5pt; font-weight: 700; color: #1e40af;
  text-transform: uppercase; letter-spacing: 1.5pt;
  display: flex; align-items: center; gap: 7pt;
  margin-bottom: 7pt;
}
.section-title::after { content: ''; flex: 1; height: 1pt; background: linear-gradient(to right, #bfdbfe, transparent); }
.entry { margin-top: 5pt; }
.entry-header { display: flex; justify-content: space-between; align-items: baseline; font-weight: 700; font-size: 9.5pt; color: #0f172a; }
.entry-header .date {
  font-weight: 400; font-size: 8pt; color: #fff;
  background: #3b82f6; padding: 0.5pt 5pt; border-radius: 2pt;
  white-space: nowrap;
}
.entry-subtitle { font-size: 8.5pt; color: #475569; margin: 2pt 0 2pt; font-weight: 500; }
.item-list { list-style: none; padding: 0; margin: 2pt 0 0; }
.item-list li { padding-left: 12pt; text-indent: -7pt; margin-bottom: 1.5pt; }
.item-list li::before { content: '▸'; display: inline-block; width: 7pt; color: #3b82f6; font-size: 7pt; }
"""
    },
    {
        "id": "bold",
        "name": "粗犷商务",
        "desc": "对比强烈，视觉冲击力强",
        "css": """
@page { size: A4; margin: 0; }
body {
  width: 595pt; margin: 0 auto;
  padding: 0 0 28pt 0;
  box-sizing: border-box;
  font-family: 'Noto Sans SC', 'Helvetica Neue', Arial, sans-serif;
  font-size: 9pt; color: #1c1c1c; line-height: 1.42;
}
.header-block { padding: 36pt 46pt 18pt 46pt; }
.body-wrap { padding: 0 46pt; }
.name { font-size: 28pt; font-weight: 700; color: #000; text-align: left; margin: 0 0 4pt; letter-spacing: -1pt; }
.contact { font-size: 8.5pt; text-align: left; color: #555; }
.section { margin-top: 16pt; }
.section-title {
  font-size: 10pt; font-weight: 700; color: #fff;
  background: #1c1c1c; padding: 3pt 8pt;
  margin-bottom: 7pt; display: inline-block; letter-spacing: 0.5pt;
}
.entry { margin-top: 5pt; }
.entry-header { display: flex; justify-content: space-between; font-weight: 700; font-size: 10pt; color: #000; }
.entry-header .date { font-weight: 400; font-size: 8.5pt; color: #555; }
.entry-subtitle { font-size: 8.5pt; color: #444; margin: 1pt 0; border-left: 2pt solid #1c1c1c; padding-left: 6pt; }
.item-list { list-style: none; padding: 0; margin: 2pt 0 0; }
.item-list li { padding-left: 12pt; text-indent: -7pt; margin-bottom: 1pt; }
.item-list li::before { content: '•'; display: inline-block; width: 7pt; font-size: 8pt; color: #1c1c1c; }
"""
    },
]


def build_html(css: str, c: dict) -> str:
    def esc(t): return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    parts = [
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">',
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@400;700&display=swap" rel="stylesheet">',
        f'<style>{css}</style></head><body>',
        '<div class="header-block">',
        f'<div class="name">{esc(c["name"])}</div>',
        f'<div class="contact">{esc(c["contact"])}</div>',
        '</div>',
        '<div class="body-wrap">',
    ]
    for sec in c["sections"]:
        parts.append('<div class="section">')
        parts.append(f'<div class="section-title">{esc(sec["title"])}</div>')
        for entry in sec["entries"]:
            parts.append('<div class="entry">')
            header, date = entry.get("header", ""), entry.get("date", "")
            if header:
                if date:
                    parts.append(f'<div class="entry-header"><span>{esc(header)}</span><span class="date">{esc(date)}</span></div>')
                else:
                    parts.append(f'<div class="entry-header"><span>{esc(header)}</span></div>')
            subtitle = entry.get("subtitle", "")
            if subtitle:
                parts.append(f'<div class="entry-subtitle">{esc(subtitle)}</div>')
            items = entry.get("items", [])
            if items:
                parts.append('<ul class="item-list">')
                for item in items:
                    parts.append(f'<li>{esc(item)}</li>')
                parts.append('</ul>')
            parts.append('</div>')
        parts.append('</div>')
    parts.append('</div>')  # body-wrap
    parts.append('</body></html>')
    return "\n".join(parts)


def render_pdf_and_thumb(html: str, pdf_path: str, thumb_path: str):
    from playwright.sync_api import sync_playwright

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        f.write(html)
        tmp = f.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"file://{tmp}")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            page.pdf(
                path=pdf_path, format="A4",
                margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
                print_background=True,
            )
            # 截图作缩略图（裁取上半部分）
            page.set_viewport_size({"width": 794, "height": 1123})
            page.screenshot(path=thumb_path, clip={"x": 0, "y": 0, "width": 794, "height": 560})
            browser.close()
    finally:
        os.unlink(tmp)


if __name__ == "__main__":
    meta = []
    for t in TEMPLATES:
        print(f"生成模板: {t['name']} ...")
        html = build_html(t["css"], SAMPLE_CONTENT)
        pdf_path   = os.path.join(OUTPUT_DIR, f"{t['id']}.pdf")
        thumb_path = os.path.join(OUTPUT_DIR, f"{t['id']}.png")
        render_pdf_and_thumb(html, pdf_path, thumb_path)
        meta.append({"id": t["id"], "name": t["name"], "desc": t["desc"],
                     "pdf": f"/static/templates/{t['id']}.pdf",
                     "thumb": f"/static/templates/{t['id']}.png"})
        print(f"  ✓ {pdf_path}")

    with open(os.path.join(OUTPUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("\n全部完成！")
