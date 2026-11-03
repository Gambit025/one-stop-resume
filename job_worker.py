"""Disposable conversion child. Only safe, structured error messages leave this process."""
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata

import fitz


def atomic_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def validate_content(content):
    if not isinstance(content, dict) or not isinstance(content.get('name',''), str):
        raise ValueError('invalid_structure')
    if not isinstance(content.get('contact',''), str) or not isinstance(content.get('sections'), list):
        raise ValueError('invalid_structure')
    for section in content['sections']:
        if not isinstance(section, dict) or not isinstance(section.get('title',''), str) or not isinstance(section.get('entries'),list):
            raise ValueError('invalid_structure')
        for entry in section['entries']:
            if not isinstance(entry,dict):
                raise ValueError('invalid_structure')
            for key in ('header','date','subtitle'):
                if not isinstance(entry.get(key,''),str):
                    raise ValueError('invalid_structure')
            for key in ('details','items'):
                if not isinstance(entry.get(key,[]),list) or any(not isinstance(t,str) for t in entry.get(key,[])):
                    raise ValueError('invalid_structure')
    return content


def flatten(value):
    if isinstance(value,str):
        return value
    if isinstance(value,list):
        return '\n'.join(flatten(v) for v in value)
    if isinstance(value,dict):
        return '\n'.join(flatten(v) for v in value.values())
    return ''


def characters(text):
    return collections.Counter(c for c in unicodedata.normalize('NFKC',text).lower() if c.isalnum())


def verify(source, structured, rendered):
    """Conservative multiset check; reports differences, never claims semantic equivalence."""
    src = characters(source)
    checks = []
    for label,text in [('structure',structured),('pdf',rendered)]:
        out = characters(text)
        missing, added = sum((src-out).values()),sum((out-src).values())
        numbers = collections.Counter(re.findall(r'\d+(?:[.\-/]\d+)*',source))
        out_numbers = collections.Counter(re.findall(r'\d+(?:[.\-/]\d+)*',text))
        checks.append(dict(target=label, missing_characters=missing, added_characters=added,
                           missing_numbers=sum((numbers-out_numbers).values()),
                           added_numbers=sum((out_numbers-numbers).values())))
    # Display only counts; never include resume fragments in logs or error messages.
    return dict(needs_review=any(any(c[k] for k in ('missing_characters','added_characters','missing_numbers','added_numbers')) for c in checks),
                checks=checks, note='自动核对字符和数字数量，无法保证语义、顺序及版式完全一致，请人工检查姓名、联系方式、日期和经历。')


def run(folder):
    from llm_generator import extract_precise_style, generate_css, extract_text, structure_resume_via_llm, assemble_html, html_to_pdf
    manifest = json.loads((folder/'input.json').read_text())
    timings = {}
    def phase(stage):
        atomic_json(folder/'progress.json',{'stage':stage})
    phase('reading')
    start = time.monotonic()
    source = extract_text(manifest['resume'])
    if not source.strip() or len(source)>20000:
        raise ValueError('invalid_pdf')
    template = Path(manifest['template'])
    # Cache only public built-in template measurements, never user content.
    cache = folder.parent.parent/'style-cache'
    style = None
    if manifest['builtin']:
        cache.mkdir(exist_ok=True)
        fingerprint = hashlib.sha256(template.read_bytes()+b'style-v1').hexdigest()
        cached = cache/f'{fingerprint}.json'
        if cached.exists():
            try:
                style = json.loads(cached.read_text())
            except ValueError:
                pass
    if style is None:
        style = extract_precise_style(str(template))
        if manifest['builtin']:
            atomic_json(cached,style)
    timings['reading'] = round(time.monotonic()-start,3)
    phase('understanding')
    start = time.monotonic()
    content = validate_content(structure_resume_via_llm(source))
    timings['understanding'] = round(time.monotonic()-start,3)
    phase('rendering')
    start = time.monotonic()
    html = assemble_html(generate_css(style),content)
    (folder/'output.html').write_text(html,encoding='utf-8')
    html_to_pdf(html,str(folder/'output.pdf'))
    with fitz.open(folder/'output.pdf') as pdf:
        if len(pdf)>20:
            raise ValueError('too_many_output_pages')
        output_text = '\n'.join(p.get_text() for p in pdf)
        pages = len(pdf)
        for i,page in enumerate(pdf):
            page.get_pixmap(matrix=fitz.Matrix(1.35,1.35),alpha=False).save(folder/f'page-{i+1}.png')
    timings['rendering'] = round(time.monotonic()-start,3)
    verification = verify(source,flatten(content),output_text)
    # Raw resume and HTML are no longer needed once preview/PDF verification finishes.
    for path in (folder/'resume.pdf',folder/'template.pdf',folder/'output.html',folder/'input.json'):
        path.unlink(missing_ok=True)
    atomic_json(folder/'result.json',dict(ok=True,pages=pages,timings=timings,verification=verification))


if __name__=='__main__':
    folder = Path(sys.argv[1])
    try:
        run(folder)
    except Exception as exc:
        # Do not serialize SDK errors, network bodies, input text, or credentials.
        message = str(exc)
        if '免费额度' in message or '频繁' in message:
            code, safe = 'quota','AI 免费额度或调用频率已达上限，请稍后重试。'
        elif '密钥' in message or '权限' in message:
            code, safe = 'configuration','AI 服务配置暂不可用，请联系网站维护者。'
        elif '连接' in message or 'timed out' in message:
            code, safe = 'network','AI 服务暂时连接失败，请稍后重试。'
        elif isinstance(exc,ValueError):
            code, safe = 'invalid_output','无法可靠解析或排版这份简历，请重试或更换模板。'
        else:
            code, safe = 'generation_failed','生成未完成，请重试；若仍失败，可更换模板。'
        atomic_json(folder/'result.json',dict(ok=False,code=code,message=safe))
        sys.exit(1)
