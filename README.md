<div align="center">

# ✦ One-Stop Resume

### 你只管打磨实力，排版交给机器

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-black?logo=flask)](https://flask.palletsprojects.com)

**给我任意一份神级简历模板，我还你一份专属的完美简历**

[**→ 立即使用**](https://one-stop-resume.up.railway.app)

</div>

---

## 为什么做这个

在求职季，改简历格式绝对是世界上最反人类、最消磨意志的事情之一。在 Word 里痛苦地挣扎 2 个小时：为了对齐一个边距把整个页面的排版搞崩；为了调整行高让一页纸刚好塞下所有的项目经历；好不容易搞完，导出 PDF 一看，怎么还是透着一股廉价感？

**你的时间，应该花在提升内容的含金量上，而不是被行间距折磨。**

你只需上传你现有的 PDF 简历，再加上一份你一眼相中的"别人家的神级模板"——

> **⏳ 30 秒内，魔法发生。**

系统会自动生成一份全新的 PDF 简历：
- **100% 内容无损** — 你的每一个字、每一个数据、每一段经历，都被原封不动地保留
- **像素级完美复刻** — 精确剥离并应用目标模板的字体、字号、配色、模块间距与留白

---

## 它是怎么工作的

三阶段流水线。核心原则：**代码做测量，LLM 做理解**——让每个组件只干自己擅长的事。

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Phase  1     │     │    Phase  2     │     │    Phase  3     │
│                 │     │                 │     │                 │
│   PyMuPDF 精    │     │    LLM 语义     │     │   代码确定性     │
│   确提取模板     │────▶│    结构化简历    │────▶│   组装 + 渲染   │
│   所有排版参数   │     │    内容 → JSON  │     │   HTML → PDF   │
│                 │     │                 │     │                 │
│  ↓ 确定性 CSS   │     │  ↓ 零格式决策   │     │  ↓ 同输入必同输出│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Phase 1 — 精确样式提取（零 AI）

从模板 PDF 坐标系直接读数，精确到 0.1pt：

| 参数 | 示例值 | 提取方式 |
|------|--------|----------|
| 页边距 | 左 36.1pt / 右 33.1pt | `bbox.x0` 最小值 |
| 字号层级 | 姓名 20pt / 标题 12pt / 正文 9pt | span size 频率分布 |
| 行高 | 1.37 | 相邻行 y 坐标差 ÷ 字号 |
| 分割线 | 1.5pt · #1a1a1a | drawing 路径提取 |
| 列表标记 | ◆ vs • vs – | 首字符检测 |
| 日期对齐 | 右对齐 | origin_x > 页宽 × 0.6 |

**零 AI 参与，零猜测，输出纯确定性 CSS。**

### Phase 2 — 语义结构化（LLM）

LLM 只回答一个问题：「这段文字是公司名、职位、日期还是描述？」

```json
{
  "name": "张三",
  "contact": "138xxxx  |  xxx@gmail.com  |  北京",
  "sections": [
    {
      "title": "教育经历",
      "entries": [
        {
          "header": "北京大学",
          "date": "2020.09 – 2024.06",
          "subtitle": "计算机科学与技术  本科",
          "items": ["GPA 3.9 / 4.0", "ACM 校队成员"]
        }
      ]
    }
  ]
}
```

LLM **不参与任何格式决策**——不决定字号、不决定边距、不决定颜色。

### Phase 3 — 确定性组装（代码）

Phase 1 的 CSS + Phase 2 的 JSON → HTML → Playwright 渲染为 PDF。同样的输入永远产生同样的输出，没有任何随机性。

---

## 为什么不直接让 LLM 生成 HTML？

> 我们试过了。效果很差。

| 指标 | LLM 全权负责 | **本方案（各司其职）** |
|------|-------------|----------------------|
| 字号精度 | LLM 猜 12pt（实际 9pt）| ✅ 代码测量 9.0pt |
| 边距精度 | 凭感觉给 | ✅ 测量 36.1pt / 33.1pt |
| 行高精度 | 写 1.5（实际 1.37）| ✅ y 坐标计算 1.37 |
| 分割线 | 有时有，有时没有 | ✅ 代码提取 1.5pt #1a1a1a |
| 列表标记 | 随机 • 或 ◆ | ✅ 代码提取 ◆ |
| 生成耗时 | 2–3 分钟 | ✅ **~30 秒** |
| 结果一致性 | 每次不一样 | ✅ **每次一样** |

**LLM 不擅长精确数值，但擅长理解语义。让它做擅长的事。**

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 2. 配置 Kimi API Key
export KIMI_API_KEY=your_key_here

# 3. 启动
python app.py
```

打开 http://localhost:8080，上传两份 PDF，等 30 秒。

---

## Tech Stack

| 组件 | 技术 | 用途 |
|------|------|------|
| 样式提取 | PyMuPDF | 从 PDF 坐标系精确测量排版参数 |
| 语义理解 | Kimi LLM | 结构化简历内容，输出 JSON |
| PDF 渲染 | Playwright (headless Chromium) | HTML → PDF |
| 后端 | Flask | API 服务 |
| 前端 | Vanilla HTML/CSS/JS | 无框架，零依赖 |

---

## License

MIT · 作者：秦睿涵 · ryan_25@qq.com
