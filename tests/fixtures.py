"""Synthetic fixtures only; generated at test time, never personal resumes."""
import io
import fitz


def pdf_bytes(kind='short'):
    doc=fitz.open()
    if kind=='damaged': return b'%PDF-1.7 broken'
    count=11 if kind=='pages' else 2 if kind=='two_pages' else 1
    for index in range(count):
        page=doc.new_page()
        if kind!='scan':
            lines=['测试同学','教育经历','示例大学 计算机科学 2020.09-2024.06','实习经历','示例公司 软件工程师 2024.07-2025.06','优化服务延迟 30%，维护 12 个项目。']
            if kind=='mixed': lines+=['Example University | Software Engineer','Built a tool for 120 users.']
            if kind=='dense': lines+=['项目经历：设计数据处理流程，提升系统稳定性。']*32
            if kind=='text_limit':
                page.insert_text((10,20),'a'*20001,fontsize=.01)
            else:
                for i,line in enumerate(lines): page.insert_text((45,55+i*18),line,fontname='china-s',fontsize=10)
    if kind=='encrypted':
        data=doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256,owner_pw='owner',user_pw='test')
    else: data=doc.tobytes()
    doc.close()
    return data
