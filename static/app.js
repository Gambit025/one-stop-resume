'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const stages = ['queued', 'reading', 'understanding', 'rendering', 'completed'];
  const labels = {queued:'等待处理', reading:'正在读取文件与模板', understanding:'AI 正在整理内容结构', rendering:'正在排版并生成 PDF', completed:'转换完成'};
  const sessionKey = 'resume-job-v1';
  let templates = [], selectedTemplate = 'minimal', customFile = null, resumeFile = null;
  let credential = null, busy = false, timer = null, pollStarted = 0, lastState = null, polling = false;
  let previewURLs = [], zoom = 1, previewGeneration = 0, warning = false;
  const remember = value => { try {value ? sessionStorage.setItem(sessionKey,JSON.stringify(value)) : sessionStorage.removeItem(sessionKey);} catch (_) {} };
  const headers = () => ({'X-Job-Token':credential.token});
  const showMessage = (text, kind='error') => {$('message').textContent=text; $('message').hidden=!text; $('message').classList.toggle('info',kind==='info');};
  function updateButton() {
    $('generateBtn').disabled = busy || !resumeFile || (!customFile && !templates.some(t=>t.id===selectedTemplate)) || !$('consent').checked;
    $('inputFields').disabled = busy;
    $('consent').disabled = busy;
    $('generateBtn').querySelector('span').textContent = busy ? '正在生成…' : '生成新简历';
    $('submitHint').textContent = busy ? '生成期间无需重复提交，进度会自动更新。' : !resumeFile ? '先上传简历，再开始转换。' : !$('consent').checked ? '阅读并勾选数据处理说明后即可开始。' : '免费额度有限，繁忙时可稍后重试。';
  }
  function fileError(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) return '请选择 PDF 文件，其他格式暂不支持。';
    if (file.size>10*1024*1024) return '文件超过 10 MB，请压缩或精简后重试。';
    if (!file.size) return '文件为空，请重新选择。';
    return '';
  }
  function chooseResume(file) {
    if (!file || busy) return;
    const error=fileError(file); $('fileError').textContent=error;
    if (error) {$('resumeInput').value=''; return;}
    resumeFile=file;showMessage('');$('resumeDrop').classList.add('has-file');
    $('fileTitle').textContent=file.name;
    $('fileDetail').textContent=(file.size/1024/1024).toFixed(2)+' MB · 已选择';
    $('browseLabel').textContent='替换文件';
    $('templateSection').hidden=false;
    updateButton();
  }
  $('resumeInput').addEventListener('change',event=>chooseResume(event.target.files[0]));
  ['dragenter','dragover'].forEach(type=>$('resumeDrop').addEventListener(type,event=>{
    event.preventDefault(); if (!busy) $('resumeDrop').classList.add('dragging');
  }));
  ['dragleave','drop'].forEach(type=>$('resumeDrop').addEventListener(type,event=>{event.preventDefault(); $('resumeDrop').classList.remove('dragging');}));
  $('resumeDrop').addEventListener('drop',event=>chooseResume(event.dataTransfer.files[0]));
  $('templateInput').addEventListener('change',event=>{
    const file=event.target.files[0]; if(!file)return;
    const error=fileError(file); $('customError').textContent=error;
    if(error){event.target.value='';return;}
    customFile=file; $('customName').textContent=file.name+' · '+(file.size/1024/1024).toFixed(2)+' MB';
    $('clearCustom').hidden=false;
    document.querySelectorAll('[name="template"]').forEach(input=>{input.checked=false;});
    if(!credential || lastState?.state!=='completed') $('previewSubtitle').textContent='自定义模板 · 生成后查看实际结果';
    updateButton();
  });
  $('clearCustom').addEventListener('click',()=>{
    customFile=null; $('templateInput').value=''; $('customName').textContent='模板只用于测量版式，不会复制模板中的经历。';
    $('clearCustom').hidden=true; $('customError').textContent='';
    document.querySelectorAll('[name="template"]').forEach(input=>{input.checked=input.value===selectedTemplate;});
    samplePreview(); updateButton();
  });
  $('consent').addEventListener('change',updateButton);
  function revokePreview() { previewGeneration++; previewURLs.forEach(url=>URL.revokeObjectURL(url));previewURLs=[]; }
  function samplePreview() {
    if(lastState?.state==='completed')return;
    const template=templates.find(t=>t.id===selectedTemplate);if(!template)return;
    revokePreview(); const img=new Image();img.src=template.preview||template.thumb;img.width=794;img.height=1123;img.className='paper';
    img.alt=template.name+'模板示意，示例内容不是你的简历';
    $('paperStack').replaceChildren(img);
    $('previewTitle').textContent='版式预览';$('previewSubtitle').textContent=template.name+' · 模板示意';
    $('previewCaption').textContent='生成后，这里会显示实际 PDF 的逐页预览。';zoom=1;applyZoom();
  }
  async function loadTemplates() {
    $('retryTemplates').hidden=true;$('templateError').textContent='正在加载模板…';
    try{
      const response=await fetch('/api/templates',{signal:AbortSignal.timeout(12000)});
      if(!response.ok)throw new Error('templates');
      templates=await response.json();if(!Array.isArray(templates)||!templates.length)throw new Error('templates');
      const fragment=document.createDocumentFragment();
      for(const t of templates){
        const label=document.createElement('label');label.className='template-option';
        const radio=document.createElement('input');radio.type='radio';radio.name='template';radio.value=t.id;radio.checked=!customFile&&t.id===selectedTemplate;
        const body=document.createElement('span');body.className='template-body';
        const img=new Image();img.src=t.thumb;img.width=39;img.height=55;img.alt='';img.loading='lazy';
        const description=document.createElement('span'),name=document.createElement('strong'),detail=document.createElement('small');
        name.textContent=t.name;detail.textContent=t.id==='minimal'?'推荐 · 清晰经典':t.desc;
        description.append(name,detail);body.append(img,description);label.append(radio,body);fragment.append(label);
        radio.addEventListener('change',()=>{
          selectedTemplate=t.id;customFile=null;$('templateInput').value='';$('clearCustom').hidden=true;
          $('customName').textContent='模板只用于测量版式，不会复制模板中的经历。';$('customError').textContent='';samplePreview();updateButton();
        });
      }
      $('templateGrid').replaceChildren(fragment);$('templateError').textContent='';samplePreview();updateButton();
    }catch(_){$('templateError').textContent='模板未能加载。你可以重试，或上传自己的模板。';$('retryTemplates').hidden=false;updateButton();}
  }
  $('retryTemplates').addEventListener('click',loadTemplates);
  function applyZoom(){
    const box=getComputedStyle($('previewViewport'));
    const available=Math.max(1,$('previewViewport').clientWidth-parseFloat(box.paddingLeft)-parseFloat(box.paddingRight));
    const width=Math.max(100,Math.round(Math.min(available,794)*zoom));
    $('paperStack').style.width=width+'px';
    $('zoomLevel').textContent=Math.round(width/794*100)+'%';
  }
  $('zoomIn').addEventListener('click',()=>{zoom=Math.min(2.5,zoom+.15);applyZoom();});
  $('zoomOut').addEventListener('click',()=>{zoom=Math.max(.5,zoom-.15);applyZoom();});
  $('zoomFit').addEventListener('click',()=>{zoom=1;applyZoom();});
  new ResizeObserver(()=>applyZoom()).observe($('previewViewport'));
  async function request(path,options={}){
    let response;
    try{response=await fetch(path,{...options,signal:AbortSignal.timeout(15000)});}
    catch(_){throw new Error('网络连接暂时中断，请检查网络后重试。');}
    if(!response.ok){
      const data=await response.json().catch(()=>({}));
      const error=new Error(data.error||'服务暂时不可用，请稍后重试。');error.status=response.status;throw error;
    }
    return response;
  }
  function setBusy(value){busy=value;updateButton();}
  function displayStage(state){
    $('jobStatus').hidden=false;
    $('stageLabel').textContent=labels[state.stage]||'正在处理';
    $('elapsed').textContent='已等待 '+state.elapsed_seconds+' 秒';
    const index=stages.indexOf(state.stage);
    document.querySelectorAll('#stages li').forEach((item,i)=>{
      item.classList.toggle('current',i===index);item.classList.toggle('done',i<index);
      if(i===index)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');
    });
    $('stageHint').textContent=state.state==='queued' ? '当前排队位置：'+state.queue_position+'。最多同时处理一份简历。' : '后台正在实际处理，生成总等待时间最多 120 秒。';
  }
  async function poll(){
    if(!credential||polling)return;
    polling=true;
    const thisId=credential.job_id;
    try{
      const response=await request('/api/jobs/'+thisId,{headers:headers()});
      const state=await response.json();if(thisId!==credential?.job_id)return;
      lastState=state;
      if(state.state==='completed'){
        $('jobStatus').hidden=true;showMessage('');await showResult(state);if(thisId===credential?.job_id)setBusy(false);return;
      }
      if(state.state==='failed'){
        setBusy(false);$('jobStatus').hidden=true;showMessage(state.result?.message||'生成失败，请重试。');remember(null);return;
      }
      displayStage(state);
      if(Date.now()-pollStarted>135000)throw new Error('等待超时。可刷新页面查询已有任务，或取消后重试。');
      timer=setTimeout(poll,document.hidden?10000:2000);
    }catch(error){
      if(thisId!==credential?.job_id)return;
      if(error.status===404){resetExpired(error.message);return;}
      showMessage(error.message);
      if(Date.now()-pollStarted<135000){timer=setTimeout(poll,document.hidden?10000:4000);}
      else{setBusy(false);$('stageHint').textContent='查询已停止。刷新可恢复查询，或取消当前任务。';}
    }finally{polling=false;}
  }
  function resetExpired(message,kind='error'){
    clearTimeout(timer);credential=null;lastState=null;remember(null);setBusy(false);
    $('jobStatus').hidden=true;$('resultActions').hidden=true;revokePreview();samplePreview();showMessage(message,kind);
  }
  async function showResult(state){
    const result=state.result, id=credential.job_id;
    warning=!!result.verification.needs_review;
    $('resultActions').hidden=false;$('pageCount').textContent=result.pages+' 页';
    $('reviewAckWrap').hidden=!warning;$('reviewAck').checked=false;
    const counts=result.verification.checks.filter(c=>c.missing_characters||c.added_characters||c.missing_numbers||c.added_numbers||c.missing_fragments||c.added_fragments);
    $('reviewNotice').classList.toggle('warning',warning);
    $('reviewNotice').textContent=warning ? '自动核对发现差异：'+counts.map(c=>(c.target==='pdf'?'PDF':'内容结构')+'中可能缺少 '+c.missing_characters+' 个字符、新增 '+c.added_characters+' 个字符，数字差异 '+(c.missing_numbers+c.added_numbers)+' 处、词句片段差异 '+((c.missing_fragments||0)+(c.added_fragments||0))+' 处').join('；')+'。请对照原文检查，排版和文本提取也可能造成差异。' : '自动字符、词句片段与数字核对未发现差异。仍请人工检查姓名、联系方式、日期、经历和排版。';
    $('downloadBtn').disabled=warning;
    $('expiryText').textContent='结果有效至 '+new Date(state.expires_at*1000).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'});
    $('downloadStatus').textContent='请在一小时内下载，服务重启也会使结果失效。';
    $('previewTitle').textContent='你的新简历';$('previewSubtitle').textContent=result.pages+' 页 · 与下载 PDF 一致';
    $('previewCaption').textContent='逐页预览来自生成后的 PDF。请核对内容后下载。';
    revokePreview();const generation=previewGeneration;$('paperStack').replaceChildren();zoom=1;
    for(let i=1;i<=result.pages;i++){
      try{
        const response=await request('/api/preview/'+id+'/'+i,{headers:headers()});const blob=await response.blob();
        if(generation!==previewGeneration)return;
        const url=URL.createObjectURL(blob);previewURLs.push(url);
        const img=new Image();img.src=url;img.className='paper';img.width=794;img.height=1123;img.alt='生成简历第 '+i+' 页';
        $('paperStack').append(img);applyZoom();
      }catch(error){
        if(error.status===404){resetExpired('预览已过期，请重新生成。');return;}
        $('previewCaption').textContent='部分预览未能加载，可尝试下载 PDF，或刷新恢复预览。';break;
      }
    }
    if(window.innerWidth<=700){$('previewPanel').scrollIntoView({behavior:'auto',block:'start'});$('previewPanel').focus({preventScroll:true});}
  }
  $('reviewAck').addEventListener('change',()=>{$('downloadBtn').disabled=warning&&!$('reviewAck').checked;});
  $('resumeForm').addEventListener('submit',async event=>{
    event.preventDefault();if($('generateBtn').disabled)return;
    clearTimeout(timer);showMessage('');setBusy(true);$('resultActions').hidden=true;
    $('previewSubtitle').textContent='正在生成新结果，预览将在完成后更新';
    $('jobStatus').hidden=false;$('stageLabel').textContent='正在上传并验证 PDF';$('elapsed').textContent='';$('stageHint').textContent='请稍候，正在验证文件。';
    const form=new FormData();form.append('resume',resumeFile);
    if(customFile)form.append('template',customFile);else form.append('template_id',selectedTemplate);
    try{
      // POST is never retried automatically: a lost response must not create duplicate AI jobs.
      const response=await request('/api/jobs',{method:'POST',body:form});
      const next=await response.json();const previous=credential;credential=next;remember(next);
      if(previous)fetch('/api/jobs/'+previous.job_id,{method:'DELETE',headers:{'X-Job-Token':previous.token}}).catch(()=>{});
      lastState=null;pollStarted=Date.now();await poll();
    }catch(error){setBusy(false);$('jobStatus').hidden=true;showMessage(error.message);}
  });
  async function removeJob(){
    if(!credential)return;clearTimeout(timer);const id=credential.job_id;
    try{
      await request('/api/jobs/'+id,{method:'DELETE',headers:headers()});
      if(credential?.job_id!==id)return;
      resetExpired('任务文件已删除。你可以继续生成新的简历。','info');
    }catch(error){if(error.status===404)resetExpired('任务已过期或文件已删除。','info');else showMessage('删除未能确认：'+error.message+' 文件仍按原保留期限自动清理。');}
  }
  $('deleteJob').addEventListener('click',removeJob);$('cancelJob').addEventListener('click',removeJob);
  $('downloadBtn').addEventListener('click',async()=>{
    if(!credential || (warning&&!$('reviewAck').checked))return;
    $('downloadBtn').disabled=true;$('downloadStatus').textContent='正在准备下载…';
    try{
      const response=await request('/api/download/'+credential.job_id,{headers:headers()});
      const blob=await response.blob();if(!blob.type.includes('pdf'))throw new Error('未收到 PDF 文件，请重试。');
      const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='简历.pdf';document.body.append(link);link.click();link.remove();
      setTimeout(()=>URL.revokeObjectURL(url),60000);$('downloadStatus').textContent='PDF 已准备好，请查看浏览器下载记录。';
    }catch(error){$('downloadStatus').textContent=error.message;if(error.status===404)resetExpired('结果已过期，请重新生成。');}
    finally{$('downloadBtn').disabled=warning&&!$('reviewAck').checked;}
  });
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&busy&&credential){clearTimeout(timer);poll();}});
  window.addEventListener('pagehide',()=>{clearTimeout(timer);});
  async function init(){
    loadTemplates();updateButton();
    try{
      const saved=JSON.parse(sessionStorage.getItem(sessionKey)||'null');
      if(saved&&/^[a-f0-9]{32}$/.test(saved.job_id)&&typeof saved.token==='string'){
        credential=saved;pollStarted=Date.now();setBusy(true);await poll();
      }
    }catch(_){remember(null);}
  }
  init();
})();
