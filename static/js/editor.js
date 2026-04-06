/* CardHub Community Editor v4 — All fixes applied */
(function () {
'use strict';

const tmpl = JSON.parse(document.getElementById('tmpl-seed').textContent);

const S = {
  id: tmpl._saved_card_id || null,
  templateId: tmpl.id || tmpl.template_id || '',
  bg: tmpl.bg || '',
  bgImage: tmpl.bg_image || tmpl.bgImage || '',
  textColor: tmpl.text_color || '#ffffff',
  fontFamily: tmpl.font_family || 'Playfair Display',
  textAlign: 'center',
  textShadow: true,
  fontSize: {
    title: tmpl.font_size_title || 36,
    subtitle: tmpl.font_size_subtitle || 18,
    details: tmpl.font_size_details || 14,
  },
  elements: [],
  zoom: 1,
  borderRadius: 14,
  padding: 24,
  gap: 8,
  showGrid: false,
  snapToGrid: false,
  rsvpEnabled: tmpl.rsvp_enabled || false,
  tool: 'select',
  history: [],
  historyIndex: -1,
  qrSrc: null,
  idCounter: 0,
  savedId: null,
};

window.snapGrid = false;

const card      = document.getElementById('card');
const elLayer   = document.getElementById('elements');
const cvWrap    = document.getElementById('canvas-wrap');
const bgImgEl   = document.getElementById('bg-img-layer');

const $ = id => document.getElementById(id);

// ── Toast ──
function showToast(msg, type='') {
  let t = $('toast'); if (!t) { t=document.createElement('div'); t.id='toast'; t.className='toast'; document.body.appendChild(t); }
  t.textContent=msg; t.className='toast '+type;
  requestAnimationFrame(()=>requestAnimationFrame(()=>t.classList.add('show')));
  clearTimeout(t._t); t._t=setTimeout(()=>t.classList.remove('show'),2700);
}
window.showToast = showToast;

// ── History ──
function snapshot() { return JSON.stringify({elements:S.elements,bg:S.bg,bgImage:S.bgImage}); }
function pushHistory() {
  S.history = S.history.slice(0, S.historyIndex+1);
  S.history.push(snapshot());
  if (S.history.length>60) S.history.shift();
  S.historyIndex = S.history.length-1;
}
window.undo = function() {
  if (S.historyIndex<=0) return showToast('Nothing to undo');
  S.historyIndex--; restoreSnap(JSON.parse(S.history[S.historyIndex])); showToast('Undone');
};
window.redo = function() {
  if (S.historyIndex>=S.history.length-1) return showToast('Nothing to redo');
  S.historyIndex++; restoreSnap(JSON.parse(S.history[S.historyIndex])); showToast('Redone');
};
function restoreSnap(data) {
  S.elements=data.elements; S.bg=data.bg; S.bgImage=data.bgImage;
  rebuildCanvas(); applyCardBg();
}

// ── Tabs ──
document.querySelectorAll('.panel-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.panel-tab').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.panel-tab-content').forEach(c=>c.classList.remove('active'));
    tab.classList.add('active');
    $('tab-'+tab.dataset.tab).classList.add('active');
  });
});

// ── BACKGROUND ──
function applyCardBg() {
  card.style.background = S.bg;
  if (S.bgImage) {
    bgImgEl.style.backgroundImage = `url('${S.bgImage}')`;
    bgImgEl.style.display = 'block';
  } else {
    bgImgEl.style.backgroundImage = '';
    bgImgEl.style.display = 'none';
  }
}

window.applyBgGradient = function() {
  const c1=$('bg-c1').value, c2=$('bg-c2').value, dir=$('bg-dir').value;
  S.bg = `linear-gradient(${dir},${c1},${c2},${c1})`;
  if (!S.bgImage) applyCardBg();
  pushHistory();
};

window.setPalette = function(c1, c2) {
  $('bg-c1').value=c1; $('bg-c2').value=c2; applyBgGradient();
};

window.uploadBg = async function(input) {
  const file=input.files[0]; if (!file) return;
  const fd=new FormData(); fd.append('image',file);
  showToast('Uploading…');
  const r=await fetch('/api/upload-image',{method:'POST',body:fd});
  const d=await r.json();
  if (!d.url) return showToast('Upload failed','error');
  S.bgImage=d.url; applyCardBg();
  $('bg-zone-txt').innerHTML='✓ Background applied<br><span style="font-size:.68rem;opacity:.6">Click to change</span>';
  $('crop-bg-btn').disabled=false; $('clear-bg-btn').disabled=false;
  showToast('Background applied ✓','success'); pushHistory();
};

window.clearBg = function() {
  S.bgImage=''; applyCardBg();
  $('bg-zone-txt').innerHTML='Click to upload background<br><span style="font-size:.68rem;opacity:.6">JPG, PNG, WebP</span>';
  $('crop-bg-btn').disabled=true; $('clear-bg-btn').disabled=true;
  pushHistory();
};

window.setBgOpacity = function(val) { bgImgEl.style.opacity=val/100; };
window.setBgPosition = function(pos) { bgImgEl.style.backgroundPosition=pos; };

// ── ELEMENTS ──
const newId = () => 'el_'+(++S.idCounter);

function mkEl(type, extra) {
  const cW=card.offsetWidth||600, cH=card.offsetHeight||375;
  return Object.assign({
    id:newId(), type,
    x:Math.round(cW*0.1), y:Math.round(cH*0.3),
    w:Math.round(cW*0.8), h:'auto',
    opacity:1, zIndex:S.elements.length+3,
  }, extra);
}

window.addTextEl = function(content, size, weight) {
  const cW=card.offsetWidth||600, cH=card.offsetHeight||375;
  const el=mkEl('text',{content,size,weight,color:'#ffffff',font:'Playfair Display',align:'center',w:cW*0.8});
  el.x=cW*0.1; el.y=cH*0.35;
  S.elements.push(el); renderEl(el); selectEl(el.id); pushHistory();
};

window.addStickerEl = function(emoji) {
  const cW=card.offsetWidth||600, cH=card.offsetHeight||375;
  const el=mkEl('sticker',{content:emoji,size:40,w:60,h:60});
  el.x=cW*0.4; el.y=cH*0.1;
  S.elements.push(el); renderEl(el); selectEl(el.id); pushHistory();
};

window.uploadImageEl = async function(input) {
  const file=input.files[0]; if (!file) return;
  const fd=new FormData(); fd.append('image',file); showToast('Uploading…');
  const r=await fetch('/api/upload-image',{method:'POST',body:fd});
  const d=await r.json();
  if (!d.url) return showToast('Upload failed','error');
  const cW=card.offsetWidth||600, cH=card.offsetHeight||375;
  const el=mkEl('image',{src:d.url,originalSrc:d.url,w:120,h:120,radius:0,fit:'contain'});
  el.x=cW*0.35; el.y=cH*0.1;
  S.elements.push(el); renderEl(el); selectEl(el.id); pushHistory();
  showToast('Image added ✓','success');
};

window.addQREl = function() {
  if (!S.qrSrc) return;
  const cW=card.offsetWidth||600, cH=card.offsetHeight||375;
  const el=mkEl('image',{src:S.qrSrc,originalSrc:S.qrSrc,w:90,h:90,radius:6,fit:'contain'});
  el.x=cW*0.35; el.y=cH*0.7;
  S.elements.push(el); renderEl(el); selectEl(el.id); pushHistory();
  showToast('QR code added ✓','success');
};

// ── RENDER ELEMENT ──
function renderEl(el) {
  $('wrap_'+el.id)?.remove();
  const wrap=document.createElement('div');
  wrap.className='el-wrap'; wrap.id='wrap_'+el.id;
  wrap.style.cssText=`left:${el.x}px;top:${el.y}px;z-index:${el.zIndex};position:absolute;`;
  if (el.w !== 'auto') wrap.style.width = el.w+'px';

  const content=document.createElement('div');
  content.className='el-content';

  if (el.type==='text') {
    // FIX: Use text color from element, defaulting to white (not dark)
    // FIX: Strip formatting on paste
    // Load font dynamically if not already loaded
    if (el.font && !window._loadedFonts?.has(el.font)) {
      window._loadedFonts = window._loadedFonts || new Set();
      window._loadedFonts.add(el.font);
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(el.font).replace(/%20/g,'+')}:wght@300;400;600;700;800&display=swap`;
      document.head.appendChild(link);
    }
    content.style.cssText=`
      font-size:${el.size}px;font-weight:${el.weight};
      color:${el.color||'#ffffff'};font-family:'${el.font}',serif;
      text-align:${el.align};opacity:${el.opacity||1};
      line-height:1.3;min-width:60px;width:${el.w}px;
      word-break:break-word;white-space:pre-wrap;padding:4px;
      cursor:text;background:transparent;outline:none;
    `;
    content.contentEditable='true';
    content.spellcheck=false;
    content.textContent=el.content;

    // FIX: Strip background color and formatting on paste
    content.addEventListener('paste', e => {
      e.preventDefault();
      const text = (e.clipboardData || window.clipboardData).getData('text/plain');
      document.execCommand('insertText', false, text);
    });

    content.addEventListener('input', () => {
      el.content=content.textContent;
      if ($('prop-content')) $('prop-content').value=el.content;
    });
    content.addEventListener('keydown', e => e.stopPropagation());
    content.addEventListener('dblclick', e => { content.focus(); e.stopPropagation(); });
    content.addEventListener('focus', () => { wrap.style.cursor='text'; selectEl(el.id); });
    content.addEventListener('blur', () => { el.content=content.textContent; pushHistory(); });

  } else if (el.type==='sticker') {
    content.style.cssText=`font-size:${el.size}px;line-height:1;opacity:${el.opacity||1};cursor:move;user-select:none;width:${el.w}px;text-align:center;`;
    content.textContent=el.content;

  } else if (el.type==='image') {
    const img=document.createElement('img');
    img.src=el.src; img.draggable=false;
    img.style.cssText=`width:${el.w}px;height:${el.h}px;object-fit:${el.fit||'contain'};border-radius:${el.radius||0}px;display:block;opacity:${el.opacity||1};`;
    content.appendChild(img);
    content.style.cssText='display:inline-block;cursor:move;';
  }

  // Resize handles
  ['tl','tr','bl','br','tm','bm','ml','mr'].forEach(pos => {
    const h=document.createElement('div');
    h.className='rh '+pos; h.dataset.pos=pos;
    content.appendChild(h); makeResizable(h,wrap,el);
  });

  // Delete btn
  const del=document.createElement('div');
  del.className='el-del'; del.textContent='✕';
  del.addEventListener('click',e=>{e.stopPropagation();deleteEl(el.id);});
  content.appendChild(del);

  wrap.appendChild(content);
  elLayer.appendChild(wrap);

  makeDraggable(wrap,el,content);
  wrap.addEventListener('mousedown',e=>{
    if (e.target.classList.contains('rh')||e.target.classList.contains('el-del')) return;
    selectEl(el.id); e.stopPropagation();
  });
}

// ── DRAG ──
function makeDraggable(wrap, el, contentNode) {
  let dragging=false, ox, oy, startX, startY;
  wrap.addEventListener('mousedown', e => {
    if (e.target.classList.contains('rh')||e.target.classList.contains('el-del')) return;
    if (el.type==='text' && e.target===contentNode && S.selected===el.id) return;
    dragging=true; startX=e.clientX; startY=e.clientY; ox=el.x; oy=el.y;
    e.preventDefault();
  });
  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const sc=S.zoom;
    let nx=ox+(e.clientX-startX)/sc, ny=oy+(e.clientY-startY)/sc;
    if (window.snapGrid) { nx=Math.round(nx/20)*20; ny=Math.round(ny/20)*20; }
    const cW=card.offsetWidth, cH=card.offsetHeight;
    nx=Math.max(-wrap.offsetWidth*0.3, Math.min(cW-wrap.offsetWidth*0.3, nx));
    ny=Math.max(-wrap.offsetHeight*0.3, Math.min(cH-wrap.offsetHeight*0.3, ny));
    el.x=nx; el.y=ny;
    wrap.style.left=nx+'px'; wrap.style.top=ny+'px';
  });
  document.addEventListener('mouseup', () => { if (dragging) { dragging=false; pushHistory(); } });
}

// ── RESIZE ──
function makeResizable(handle, wrap, el) {
  handle.addEventListener('mousedown', e => {
    e.stopPropagation(); e.preventDefault();
    const dir=handle.dataset.pos;
    const startX=e.clientX, startY=e.clientY;
    const startW=wrap.offsetWidth, startH=wrap.offsetHeight;
    const startL=el.x, startT=el.y;
    const onMove=e=>{
      const sc=S.zoom;
      const dx=(e.clientX-startX)/sc, dy=(e.clientY-startY)/sc;
      let nw=startW, nh=startH, nx=startL, ny=startT;
      if (dir.includes('r')) nw=Math.max(40,startW+dx);
      if (dir.includes('l')) { nw=Math.max(40,startW-dx); nx=startL+(startW-nw); }
      if (dir.includes('b')) nh=Math.max(20,startH+dy);
      if (dir.includes('t')) { nh=Math.max(20,startH-dy); ny=startT+(startH-nh); }
      if (dir==='ml'||dir==='mr') nh=startH;
      if (dir==='tm'||dir==='bm') nw=startW;
      el.w=nw; el.x=nx; el.y=ny;
      wrap.style.width=nw+'px'; wrap.style.left=nx+'px'; wrap.style.top=ny+'px';
      if (el.type==='text') wrap.querySelector('.el-content').style.width=nw+'px';
      if (el.type==='image') {
        const img=wrap.querySelector('img');
        if (img) { img.style.width=nw+'px'; el.h=nh; img.style.height=nh+'px'; }
      }
      if (el.type==='sticker') {
        el.size=Math.round(nw*0.55);
        wrap.querySelector('.el-content').style.fontSize=el.size+'px';
        wrap.querySelector('.el-content').style.width=nw+'px'; el.h=nh;
      }
    };
    const onUp=()=>{ document.removeEventListener('mousemove',onMove); document.removeEventListener('mouseup',onUp); pushHistory(); };
    document.addEventListener('mousemove',onMove);
    document.addEventListener('mouseup',onUp);
  });
}

// ── SELECTION ──
function selectEl(id) {
  document.querySelectorAll('.el-wrap').forEach(w=>w.classList.remove('selected'));
  $('el-props')?.classList.add('hidden');
  $('img-props')?.classList.add('hidden');
  if (!id) { S.selected=null; return; }
  S.selected=id;
  const el=S.elements.find(e=>e.id===id); if (!el) return;
  $('wrap_'+id)?.classList.add('selected');

  if (el.type==='text'||el.type==='sticker') {
    $('el-props')?.classList.remove('hidden');
    if ($('prop-content')) $('prop-content').value=el.content;
    if ($('prop-size-disp')) $('prop-size-disp').textContent=el.size;
    if ($('prop-size-val')) $('prop-size-val').textContent=el.size+'px';
    if ($('prop-color')) $('prop-color').value=el.color||'#ffffff';
    if ($('prop-opacity')) $('prop-opacity').value=Math.round((el.opacity||1)*100);
    if ($('prop-font')) {
      $('prop-font').value=el.font||'Playfair Display';
      $('prop-font').style.fontFamily = `'${el.font||'Playfair Display'}', serif`;
    }
  } else if (el.type==='image') {
    $('img-props')?.classList.remove('hidden');
    if ($('img-w-range')) { $('img-w-range').value=el.w||120; $('img-w-val').textContent=(el.w||120)+'px'; }
    if ($('img-h-range')) { $('img-h-range').value=el.h||120; $('img-h-val').textContent=(el.h||120)+'px'; }
    if ($('img-radius')) $('img-radius').value=el.radius||0;
    if ($('img-opacity')) $('img-opacity').value=Math.round((el.opacity||1)*100);
  }
  document.querySelector('[data-tab="text"]')?.click();
}

window.deselectAll = function(e) {
  if (e && (e.target===card||e.target===elLayer||e.target.id==='elements'||e.target.id==='card-spacer'||e.target.id==='bg-img-layer')) {
    S.selected=null;
    document.querySelectorAll('.el-wrap').forEach(w=>w.classList.remove('selected'));
    $('el-props')?.classList.add('hidden');
    $('img-props')?.classList.add('hidden');
  }
};

// ── PROPERTY UPDATES ──
window.updateSelectedProp = function(prop, value) {
  const el=S.elements.find(e=>e.id===S.selected); if (!el) return;
  const wrap=$('wrap_'+el.id);
  if (prop==='content') { el.content=value; const c=wrap?.querySelector('.el-content'); if(c)c.textContent=value; }
  else if (prop==='color') { el.color=value; const c=wrap?.querySelector('.el-content'); if(c)c.style.color=value; }
  else if (prop==='align') { el.align=value; const c=wrap?.querySelector('.el-content'); if(c)c.style.textAlign=value; }
  else if (prop==='weight') { el.weight=value; const c=wrap?.querySelector('.el-content'); if(c)c.style.fontWeight=value; }
  else if (prop==='font') {
    el.font=value;
    const c=wrap?.querySelector('.el-content');
    if(c)c.style.fontFamily=`'${value}',serif`;
    // Dynamically load the font if needed
    if (!window._loadedFonts?.has(value)) {
      window._loadedFonts = window._loadedFonts || new Set();
      window._loadedFonts.add(value);
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(value).replace(/%20/g,'+')}:wght@300;400;600;700;800&display=swap`;
      document.head.appendChild(link);
    }
    // Also update the select display
    const sel = document.getElementById('prop-font');
    if (sel) { sel.value = value; sel.style.fontFamily = `'${value}', serif`; }
  }
  else if (prop==='opacity') { el.opacity=parseFloat(value); const t=wrap?.querySelector('.el-content,img'); if(t)t.style.opacity=value; }
  else if (prop==='fit') { el.fit=value; const img=wrap?.querySelector('img'); if(img)img.style.objectFit=value; }
  else if (prop==='radius') { el.radius=value; const img=wrap?.querySelector('img'); if(img)img.style.borderRadius=value+'px'; }
  pushHistory();
};

window.nudgeFontSize = function(delta) {
  const el=S.elements.find(e=>e.id===S.selected); if (!el||el.type==='image') return;
  el.size=Math.max(8,Math.min(120,el.size+delta));
  const c=$('wrap_'+el.id)?.querySelector('.el-content'); if(c)c.style.fontSize=el.size+'px';
  if ($('prop-size-disp')) $('prop-size-disp').textContent=el.size;
  if ($('prop-size-val')) $('prop-size-val').textContent=el.size+'px';
  pushHistory();
};

window.resizeSelectedImage = function(dim, val) {
  const el=S.elements.find(e=>e.id===S.selected); if (!el||el.type!=='image') return;
  const img=$('wrap_'+el.id)?.querySelector('img'); if (!img) return;
  if (dim==='w') { el.w=+val; img.style.width=val+'px'; if($('img-w-val'))$('img-w-val').textContent=val+'px'; }
  if (dim==='h') { el.h=+val; img.style.height=val+'px'; if($('img-h-val'))$('img-h-val').textContent=val+'px'; }
  const wrap=$('wrap_'+el.id); if(wrap)wrap.style.width=el.w+'px';
};

window.bringForward = function() {
  const el=S.elements.find(e=>e.id===S.selected); if (!el) return;
  el.zIndex=(el.zIndex||3)+1; $('wrap_'+el.id).style.zIndex=el.zIndex; pushHistory();
};
window.sendBackward = function() {
  const el=S.elements.find(e=>e.id===S.selected); if (!el) return;
  el.zIndex=Math.max(3,(el.zIndex||3)-1); $('wrap_'+el.id).style.zIndex=el.zIndex; pushHistory();
};
window.duplicateSelected = function() {
  const el=S.elements.find(e=>e.id===S.selected); if (!el) return;
  const copy=JSON.parse(JSON.stringify(el));
  copy.id=newId(); copy.x+=22; copy.y+=22; copy.zIndex=(copy.zIndex||3)+1;
  S.elements.push(copy); renderEl(copy); selectEl(copy.id); pushHistory();
};
window.deleteSelected = function() { if (S.selected) deleteEl(S.selected); };

function deleteEl(id) {
  S.elements=S.elements.filter(e=>e.id!==id);
  $('wrap_'+id)?.remove(); S.selected=null;
  $('el-props')?.classList.add('hidden');
  $('img-props')?.classList.add('hidden');
  pushHistory();
}

// ── AI TEXT ──
window.loadAI = async function() {
  const btn=$('ai-btn'); if (!btn) return;
  btn.textContent='⏳ Generating…'; btn.disabled=true;
  try {
    const cardTitle=$('live-title')?.textContent||'';
    const category=document.getElementById('tmpl-category')?.value||'general';
    const r=await fetch('/api/ai-text',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({category,theme:cardTitle,context:`Card theme: ${cardTitle}`})});
    const d=await r.json();
    const box=$('ai-box'); if (!box) return;
    box.innerHTML=''; box.classList.remove('hidden');
    const badge=d.ai?'<span style="font-size:.6rem;background:rgba(212,168,67,.2);color:var(--gold);padding:1px 5px;border-radius:3px;margin-left:4px">AI</span>':'';
    d.suggestions.forEach(s=>{
      const div=document.createElement('div');
      div.className='ai-suggestion-item';
      div.innerHTML=s+badge;
      div.addEventListener('click',()=>{
        const el=S.elements.find(e=>e.id===S.selected);
        if (el&&el.type==='text') {
          el.content=s; const c=$('wrap_'+el.id)?.querySelector('.el-content'); if(c)c.textContent=s;
          if ($('prop-content')) $('prop-content').value=s;
          pushHistory(); showToast('Text applied ✓','success');
        } else showToast('Select a text element first','error');
        box.classList.add('hidden');
      });
      box.appendChild(div);
    });
  } catch(e) { showToast('AI unavailable — using suggestions','error'); }
  btn.textContent='🤖 Generate Ideas'; btn.disabled=false;
};

// ── QR ──
let qrTimer;
window.previewQR = function(url) {
  clearTimeout(qrTimer);
  if (!url) return;
  qrTimer=setTimeout(()=>{
    const src=`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(url)}`;
    S.qrSrc=src;
    const p=$('qr-preview'); if(p)p.innerHTML=`<img src="${src}" style="width:90px;height:90px"/>`;
    const b=$('add-qr-btn'); if(b)b.disabled=false;
  },700);
};

// ── CANVAS PROPS ──
window.setCardRadius = function(v) { card.style.borderRadius=v+'px'; if($('card-radius-val'))$('card-radius-val').textContent=v+'px'; };
window.setCanvasOpacity = function(v) { card.style.opacity=v/100; };
window.setCardPadding = function(v) { S.padding=+v; document.getElementById('card-inner')&&(document.getElementById('card-inner').style.padding=v+'px'); if($('padding-val'))$('padding-val').textContent=v; };
window.setElementGap = function(v) { S.gap=+v; document.getElementById('card-inner')&&(document.getElementById('card-inner').style.gap=v+'px'); if($('gap-val'))$('gap-val').textContent=v; };
window.setCanvasSize = function(val) {
  const [w,h]=val.split('x').map(Number);
  card.style.width=w+'px'; $('card-spacer').style.height=h+'px';
  setTimeout(zoomFit,50); showToast(`Canvas: ${w}×${h}px`);
};
window.toggleGrid = function(tog) { tog.classList.toggle('on'); $('grid-overlay').classList.toggle('show',tog.classList.contains('on')); };

// ── ZOOM ──
window.zoomIn  = ()=>{ S.zoom=Math.min(2,S.zoom+0.1); applyZoom(); };
window.zoomOut = ()=>{ S.zoom=Math.max(0.25,S.zoom-0.1); applyZoom(); };
window.zoomFit = ()=>{
  const cv=$('editor-canvas');
  const aw=cv.offsetWidth-80, ah=cv.offsetHeight-100;
  const cw=card.offsetWidth||600, ch=(parseInt($('card-spacer')?.style.height)||375);
  S.zoom=Math.min(1,Math.min(aw/cw,ah/ch)); applyZoom();
};
function applyZoom() { cvWrap.style.transform=`scale(${S.zoom})`; if($('zoom-lbl'))$('zoom-lbl').textContent=Math.round(S.zoom*100)+'%'; }
document.addEventListener('wheel',e=>{if(e.ctrlKey){e.preventDefault();e.deltaY<0?zoomIn():zoomOut();}},{passive:false});

// ── TOOL SELECT ──
window.setActiveTool = function(tool, btn) {
  S.tool=tool;
  document.querySelectorAll('.canvas-tool-btn').forEach(b=>{b.style.background='';b.style.color='';});
  if(btn){btn.style.background='var(--gold-bg)';btn.style.color='var(--gold)';}
};

// ── RSVP ──
window.toggleRSVP = function(tog) {
  tog.classList.toggle('on'); S.rsvpEnabled=tog.classList.contains('on');
  const lnk=$('rsvp-lnk'); if(lnk)lnk.classList.toggle('hidden',!S.rsvpEnabled);
  if (S.rsvpEnabled&&S.savedId) { const d=$('rsvp-link-display'); if(d)d.textContent=location.origin+'/rsvp/'+S.savedId; }
};

// ── EXPORT ──
window.exportAs = function(fmt) {
  if (!window.html2canvas){showToast('Export library loading…','error');return;}
  document.querySelectorAll('.el-del,.rh,#grid-overlay').forEach(e=>e.style.visibility='hidden');
  document.querySelectorAll('.el-wrap').forEach(w=>w.classList.remove('selected'));
  const origZoom=S.zoom; S.zoom=1; cvWrap.style.transform='scale(1)';
  html2canvas(card,{scale:2,useCORS:true,backgroundColor:null,logging:false}).then(canvas=>{
    S.zoom=origZoom; cvWrap.style.transform=`scale(${origZoom})`;
    document.querySelectorAll('.el-del,.rh,#grid-overlay').forEach(e=>e.style.visibility='');
    if (fmt==='svg'){
      const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${card.offsetWidth}" height="${card.offsetHeight}"><image href="${canvas.toDataURL('image/png')}" width="${card.offsetWidth}" height="${card.offsetHeight}"/></svg>`;
      dlBlob(new Blob([svg],{type:'image/svg+xml'}),'card.svg'); return;
    }
    canvas.toBlob(b=>dlBlob(b,`card.${fmt}`),fmt==='jpg'?'image/jpeg':'image/png',0.95);
    showToast(`Exported as ${fmt.toUpperCase()} ✓`,'success');
  }).catch(()=>{document.querySelectorAll('.el-del,.rh').forEach(e=>e.style.visibility='');showToast('Export failed','error');});
};
function dlBlob(blob,name){const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();URL.revokeObjectURL(a.href);}

// ── SAVE ──
window.saveCard = async function() {
  const payload={
    id:S.savedId||undefined, template_id:S.templateId,
    title:S.elements.find(e=>e.type==='text')?.content||'Card',
    subtitle:S.elements.filter(e=>e.type==='text')[1]?.content||'',
    details:S.elements.filter(e=>e.type==='text')[2]?.content||'',
    emoji:'', bg:S.bg, text_color:S.textColor,
    bg_image:S.bgImage, elements:S.elements,
    rsvp_enabled:S.rsvpEnabled,
    font_size_title:S.elements.find(e=>e.type==='text')?.size||36,
    font_size_subtitle:S.elements.filter(e=>e.type==='text')[1]?.size||18,
    font_size_details:S.elements.filter(e=>e.type==='text')[2]?.size||14,
  };
  try {
    const r=await fetch('/api/save-card',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const d=await r.json();
    if (d.success){
      S.savedId=d.id;
      if(S.rsvpEnabled){const ld=$('rsvp-link-display');if(ld)ld.textContent=location.origin+'/rsvp/'+d.id;const lnk=$('rsvp-lnk');if(lnk)lnk.classList.remove('hidden');}
      showToast('Card saved 🎉','success');
      setTimeout(()=>location.href='/my-cards',1400);
    }
  } catch { showToast('Save failed','error'); }
};

// ── BRAND KIT ──
window.applyBrandKit = function(kit) {
  if (kit.colors?.length) {
    if($('bg-c1'))$('bg-c1').value=kit.colors[0];
    if($('bg-c2'))$('bg-c2').value=kit.colors[1]||kit.colors[0];
    applyBgGradient();
  }
  showToast(`Brand kit "${kit.name}" applied`,'success');
};

// ── REBUILD ──
function rebuildCanvas() {
  elLayer.innerHTML='';
  S.elements.forEach(el=>renderEl(el));
  S.selected=null;
  $('el-props')?.classList.add('hidden');
  $('img-props')?.classList.add('hidden');
}

// ── KEYBOARD SHORTCUTS ──
document.addEventListener('keydown', e => {
  const mod=e.ctrlKey||e.metaKey;
  const focused=document.activeElement;
  const isEditing=focused.isContentEditable||['INPUT','TEXTAREA','SELECT'].includes(focused.tagName);
  if(mod&&e.key==='s'){e.preventDefault();saveCard();}
  if(mod&&e.key==='z'&&!e.shiftKey){e.preventDefault();undo();}
  if(mod&&(e.key==='y'||(e.key==='z'&&e.shiftKey))){e.preventDefault();redo();}
  if(mod&&e.key==='d'){e.preventDefault();duplicateSelected();}
  if(mod&&e.key===']'){e.preventDefault();bringForward();}
  if(mod&&e.key==='['){e.preventDefault();sendBackward();}
  if(!isEditing&&(e.key==='Delete'||e.key==='Backspace')){deleteSelected();}
  if(!isEditing&&e.key==='t'){addTextEl('New Text',22,400);}
  if(!isEditing&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){
    const el=S.elements.find(e2=>e2.id===S.selected); if(!el)return;
    const step=e.shiftKey?10:2;
    if(e.key==='ArrowLeft')el.x-=step; if(e.key==='ArrowRight')el.x+=step;
    if(e.key==='ArrowUp')el.y-=step; if(e.key==='ArrowDown')el.y+=step;
    const w=$('wrap_'+el.id); if(w){w.style.left=el.x+'px';w.style.top=el.y+'px';}
    e.preventDefault();
  }
});

// ── INIT ──
function init() {
  // Restore elements (from saved card or community template)
  const seedElements = tmpl.elements || [];
  if (seedElements.length) {
    seedElements.forEach(el => {
      // Rebuild proper element object
      const rebuilt = {
        id: el.id || newId(),
        type: el.type || 'text',
        x: el.x || 50, y: el.y || 100,
        w: el.w || 400, h: el.h || 'auto',
        content: el.content || el.txt || 'Text',
        size: el.size || el.sz || 24,
        weight: el.weight || el.w_style || 700,
        color: el.color || el.col || '#ffffff',
        font: el.font || 'Playfair Display',
        align: el.align || 'center',
        opacity: el.opacity || 1,
        zIndex: el.zIndex || 3,
        src: el.src,
        originalSrc: el.originalSrc || el.src,
        radius: el.radius || 0,
        fit: el.fit || 'contain',
      };
      S.idCounter = Math.max(S.idCounter, parseInt((el.id||'').replace('el_','')||'0'));
      S.elements.push(rebuilt);
      renderEl(rebuilt);
    });
  } else {
    // Seed only one heading from template — user adds rest
    const cW=600, cH=375;
    const heading=mkEl('text',{
      content: tmpl.default_title||tmpl.title||'Your Heading',
      size:42, weight:700, color:tmpl.text_color||'#ffffff',
      font:'Playfair Display', align:'center', w:cW*0.8,
    });
    heading.x=cW*0.1; heading.y=cH*0.38;
    S.elements.push(heading); renderEl(heading);
  }

  // FIX: Restore background image if coming from saved card
  S.bgImage = tmpl.bg_image || tmpl.bgImage || '';
  applyCardBg();

  // Set bg colour pickers from template
  if (S.bg && S.bg.includes('gradient')) {
    const match=S.bg.match(/#[a-fA-F0-9]{6}/g);
    if (match && match.length>=2) {
      if($('bg-c1'))$('bg-c1').value=match[0];
      if($('bg-c2'))$('bg-c2').value=match[match.length-1];
    }
  }

  // Restore bg image UI state
  if (S.bgImage) {
    const txt=$('bg-zone-txt'); if(txt)txt.innerHTML='✓ Background set<br><span style="font-size:.68rem;opacity:.6">Click to change</span>';
    const cb=$('crop-bg-btn'); if(cb)cb.disabled=false;
    const clb=$('clear-bg-btn'); if(clb)clb.disabled=false;
  }

  // Set saved card id for re-saves
  if (tmpl._saved_card_id) S.savedId=tmpl._saved_card_id;

  pushHistory();
  setTimeout(zoomFit, 80);
}

init();
})();
