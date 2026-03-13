"""
构建时下载 Noto 字体到 static/fonts/，供 Playwright 渲染时本地加载。
"""
import os
import urllib.request

FONT_DIR = os.path.join(os.path.dirname(__file__), "static", "fonts")
os.makedirs(FONT_DIR, exist_ok=True)

FONTS = [
    ("NotoSansSC-Regular.otf", "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf"),
    ("NotoSansSC-Bold.otf",    "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf"),
    ("NotoSerifSC-Regular.otf","https://github.com/googlefonts/noto-cjk/raw/main/Serif/OTF/SimplifiedChinese/NotoSerifCJKsc-Regular.otf"),
    ("NotoSerifSC-Bold.otf",   "https://github.com/googlefonts/noto-cjk/raw/main/Serif/OTF/SimplifiedChinese/NotoSerifCJKsc-Bold.otf"),
]

for filename, url in FONTS:
    dest = os.path.join(FONT_DIR, filename)
    if os.path.exists(dest):
        print(f"  已存在: {filename}")
        continue
    print(f"  下载: {filename} ...")
    try:
        urllib.request.urlretrieve(url, dest)
        size_mb = os.path.getsize(dest) / 1024 / 1024
        print(f"  完成: {filename} ({size_mb:.1f} MB)")
    except Exception as e:
        print(f"  失败: {filename} — {e}")

print("字体下载完成")
