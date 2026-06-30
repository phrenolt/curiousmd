(function() {
  const sidebar = document.getElementById('files');
  const browserList = document.getElementById('browser-list');
  const browserPath = document.getElementById('browser-path');
  const browserStatus = document.getElementById('browser-status');
  const browserUp = document.getElementById('browser-up');
  const browserHome = document.getElementById('browser-home');
  const browserRefresh = document.getElementById('browser-refresh');
  const content = document.getElementById('content');
  const title = document.getElementById('title');
  const input = document.getElementById('search');
  const count = document.getElementById('count');
  const next = document.getElementById('next');
  const prev = document.getElementById('prev');
  const editBtn = document.getElementById('edit-btn');
  const saveBtn = document.getElementById('save-btn');

  let docs = window.__BOOTSTRAP__.docs || [];
  let activeId = window.__BOOTSTRAP__.active || null;
  let browseRoot = window.__BOOTSTRAP__.browse_root || '';
  let browsePath = window.__BOOTSTRAP__.browse_path || '';
  let browseEntries = [];
  let matches = [];
  let idx = -1;
  let editMode = false;
  let editDirty = false;
  let previewTimer;
  let asideSb, contentSb, previewSb, editorSb = null;

  function apiUrl(path, params) {
    if (!params) return path;
    const sep = path.includes('?') ? '&' : '?';
    return path + sep + params;
  }

  const ALLOWED_TAGS = new Set([
    'A', 'BLOCKQUOTE', 'BR', 'CODE', 'DEL', 'EM', 'H1', 'H2', 'H3', 'H4',
    'H5', 'H6', 'HR', 'IMG', 'LI', 'MARK', 'OL', 'P', 'PRE', 'SPAN',
    'STRONG', 'TABLE', 'TBODY', 'TD', 'TH', 'THEAD', 'TR', 'UL'
  ]);
  const ALLOWED_ATTRS = {
    A: new Set(['href', 'rel', 'title']),
    CODE: new Set(['class']),
    H1: new Set(['id']),
    H2: new Set(['id']),
    H3: new Set(['id']),
    H4: new Set(['id']),
    H5: new Set(['id']),
    H6: new Set(['id']),
    IMG: new Set(['alt', 'decoding', 'loading', 'src', 'title']),
    SPAN: new Set(['class']),
    TD: new Set(['class']),
    TH: new Set(['class'])
  };

  function isSafeMarkdownUrl(value, tagName) {
    try {
      const url = new URL(value, window.location.href);
      if (tagName === 'IMG') return url.protocol === 'http:' || url.protocol === 'https:';
      if (tagName === 'A') return ['http:', 'https:', 'mailto:'].includes(url.protocol);
      return false;
    } catch (_) {
      return false;
    }
  }

  function isSafeClass(value, tagName) {
    const classes = value.split(/\s+/).filter(Boolean);
    if (!classes.length) return false;
    return classes.every(c => {
      if (tagName === 'CODE') return /^lang-[A-Za-z0-9_-]+$/.test(c);
      if (tagName === 'SPAN') return c === 'blocked-link' || c === 'blocked-image';
      if (tagName === 'TD' || tagName === 'TH') return /^align-(left|center|right)$/.test(c);
      return false;
    });
  }

  function sanitizeMarkdownHTML(html) {
    const template = document.createElement('template');
    template.innerHTML = html;
    const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_ELEMENT);
    const remove = [];
    while (walker.nextNode()) {
      const el = walker.currentNode;
      const tag = el.tagName;
      if (!ALLOWED_TAGS.has(tag)) {
        remove.push(el);
        continue;
      }
      const allowed = ALLOWED_ATTRS[tag] || new Set();
      for (const attr of Array.from(el.attributes)) {
        const name = attr.name.toLowerCase();
        const value = attr.value;
        if (!allowed.has(name)) {
          el.removeAttribute(attr.name);
          continue;
        }
        if ((name === 'href' || name === 'src') && !isSafeMarkdownUrl(value, tag)) {
          el.removeAttribute(attr.name);
          continue;
        }
        if (name === 'class' && !isSafeClass(value, tag)) {
          el.removeAttribute(attr.name);
          continue;
        }
        if (name === 'rel') el.setAttribute('rel', 'noopener noreferrer');
        if (name === 'loading' && value !== 'lazy') el.setAttribute('loading', 'lazy');
        if (name === 'decoding' && value !== 'async') el.setAttribute('decoding', 'async');
      }
    }
    for (const el of remove) {
      el.replaceWith(document.createTextNode(el.textContent || ''));
    }
    return template.content;
  }

  function setBrowserStatus(msg) {
    browserStatus.textContent = msg || '';
  }

  function renderBrowser() {
    browserPath.textContent = browsePath || browseRoot;
    browserUp.disabled = !browsePath || browsePath === browseRoot;
    browserHome.disabled = !browsePath;
    browserRefresh.disabled = false;
    browserList.innerHTML = '';

    if (!browseEntries.length) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = 'No Markdown files in this folder.';
      browserList.appendChild(li);
      if (asideSb) asideSb.update();
      return;
    }

    for (const entry of browseEntries) {
      const li = document.createElement('li');
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'fs-entry ' + entry.type;

      const icon = document.createElement('span');
      icon.className = 'icon';
      icon.textContent = entry.type === 'dir' ? '▸' : '•';
      button.appendChild(icon);

      const label = document.createElement('span');
      label.className = 'label';
      label.textContent = entry.name;
      button.appendChild(label);

      const fullPath = entry.path || entry.name;
      button.title = entry.type === 'dir' ? ('Open folder: ' + fullPath) : ('Open file: ' + fullPath);
      button.setAttribute('aria-label', button.title);
      button.addEventListener('click', () => {
        if (entry.type === 'dir') loadBrowser(entry.path);
        else openBrowserFile(entry.path);
      });
      li.appendChild(button);
      browserList.appendChild(li);
    }
    if (asideSb) asideSb.update();
  }

  async function loadBrowser(path) {
    const nextPath = path === undefined ? browsePath : path;
    setBrowserStatus('Loading...');
    try {
      const r = await fetch(apiUrl('/api/fs', 'path=' + encodeURIComponent(nextPath || '')));
      if (!r.ok) throw new Error('http ' + r.status);
      const data = await r.json();
      browsePath = data.dir || browseRoot;
      browseEntries = data.entries || [];
      renderBrowser();
      setBrowserStatus(data.error ? data.error : '');
    } catch (e) {
      console.error(e);
      browseEntries = [];
      renderBrowser();
      setBrowserStatus('Failed to load folder: ' + e.message);
    }
  }

  async function openBrowserFile(path) {
    setBrowserStatus('Opening...');
    try {
      const r = await fetch(apiUrl('/api/open', 'path=' + encodeURIComponent(path || '')));
      if (!r.ok) throw new Error('http ' + r.status);
      const data = await r.json();
      docs.push({id: data.id, name: data.name, dir: data.dir || ''});
      await selectDoc(data.id);
      setBrowserStatus('Opened ' + (data.dir ? (data.dir + '/' + data.name) : data.name));
    } catch (e) {
      console.error(e);
      setBrowserStatus('Failed to open file: ' + e.message);
    }
  }

  function renderSidebar() {
    sidebar.innerHTML = '';
    if (!docs.length) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = 'No files open.';
      sidebar.appendChild(li);
      if (asideSb) asideSb.update();
      return;
    }
    for (const d of docs) {
      const li = document.createElement('li');
      if (d.id === activeId) li.classList.add('active');
      const fullPath = d.dir ? (d.dir + '/' + d.name) : d.name;

      li.title = fullPath;

      const name = document.createElement('span');
      name.className = 'name';
      name.title = fullPath;
      name.addEventListener('click', () => selectDoc(d.id));

      const fileSpan = document.createElement('span');
      fileSpan.className = 'file';
      fileSpan.textContent = d.name;
      fileSpan.title = fullPath;
      name.appendChild(fileSpan);

      if (d.dir) {
        const dirSpan = document.createElement('span');
        dirSpan.className = 'dir';
        dirSpan.textContent = d.dir;
        dirSpan.title = fullPath;
        name.appendChild(dirSpan);
      }

      const close = document.createElement('button');
      close.className = 'close';
      close.textContent = '×';
      close.title = 'Close';
      close.type = 'button';
      close.setAttribute('aria-label', 'Close ' + d.name);
      close.addEventListener('click', (e) => { e.stopPropagation(); closeDoc(d.id); });
      li.appendChild(name);
      li.appendChild(close);
      sidebar.appendChild(li);
    }
    if (asideSb) asideSb.update();
  }

  function setEmptyState() {
    activeId = null;
    document.title = '';
    title.textContent = '';
    content.className = 'content empty-state';
    content.innerHTML = '<div><h1>No file selected</h1><p>Choose a Markdown file from the folder browser to start reading.</p></div>';
    clearHighlights();
    if (contentSb) contentSb.update();
  }

  async function selectDoc(id) {
    if (activeId !== id && editMode) {
      if (!canLeaveEdit()) return;
      setEditMode(false);
    }
    try {
      const r = await fetch(apiUrl('/api/docs/' + encodeURIComponent(id) + '/html'));
      if (!r.ok) throw new Error('http ' + r.status);
      const data = await r.json();
      activeId = id;
      content.className = 'content';
      content.replaceChildren(sanitizeMarkdownHTML(data.html));
      title.textContent = data.name;
      title.title = data.dir ? (data.dir + '/' + data.name) : data.name;
      document.title = (data.dir ? (data.dir + '/' + data.name) : data.name)
        .split('/').filter(Boolean).reverse().join(' › ');
      clearHighlights();
      if (input.value) doSearch();
      content.scrollTop = 0;
      if (contentSb) contentSb.update();
      renderSidebar();
    } catch (e) {
      console.error(e);
      alert('Failed to load file: ' + e.message);
    }
  }

  async function closeDoc(id) {
    if (id === activeId && editMode) {
      if (!canLeaveEdit()) return;
      setEditMode(false);
    }
    try {
      const r = await fetch(apiUrl('/api/docs/' + encodeURIComponent(id)), {method: 'DELETE'});
      if (!r.ok) throw new Error('http ' + r.status);
      docs = docs.filter(d => d.id !== id);
      if (activeId === id) {
        if (docs.length) selectDoc(docs[0].id);
        else setEmptyState();
      }
      renderSidebar();
    } catch (e) {
      alert('Failed to close: ' + e.message);
    }
  }

  browserUp.addEventListener('click', () => {
    if (!browsePath) return;
    const parent = browsePath.replace(/\/[^\/]*\/?$/, '') || '/';
    loadBrowser(parent);
  });
  browserHome.addEventListener('click', () => loadBrowser(browseRoot));
  browserRefresh.addEventListener('click', () => loadBrowser(browsePath));

  // ---------- search ----------

  function clearHighlights() {
    content.querySelectorAll('mark.match').forEach(m => {
      const t = document.createTextNode(m.textContent);
      m.parentNode.replaceChild(t, m);
    });
    content.normalize();
    matches = []; idx = -1; count.textContent = '';
  }

  function walk(node, q, qLower) {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.nodeValue;
      const lower = text.toLowerCase();
      let from = 0, hit = lower.indexOf(qLower, from);
      if (hit === -1) return;
      const frag = document.createDocumentFragment();
      while (hit !== -1) {
        if (hit > from) frag.appendChild(document.createTextNode(text.slice(from, hit)));
        const mark = document.createElement('mark');
        mark.className = 'match';
        mark.textContent = text.slice(hit, hit + q.length);
        frag.appendChild(mark);
        matches.push(mark);
        from = hit + q.length;
        hit = lower.indexOf(qLower, from);
      }
      if (from < text.length) frag.appendChild(document.createTextNode(text.slice(from)));
      node.parentNode.replaceChild(frag, node);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    if (['SCRIPT','STYLE','MARK'].includes(node.tagName)) return;
    for (const child of Array.from(node.childNodes)) walk(child, q, qLower);
  }

  function setActive(i) {
    matches.forEach(m => m.classList.remove('active'));
    if (!matches.length) { count.textContent = '0 matches'; return; }
    idx = (i + matches.length) % matches.length;
    matches[idx].classList.add('active');
    matches[idx].scrollIntoView({block: 'center', behavior: 'smooth'});
    count.textContent = (idx + 1) + ' / ' + matches.length;
  }

  function doSearch() {
    clearHighlights();
    const q = input.value;
    if (!q) return;
    walk(content, q, q.toLowerCase());
    setActive(0);
  }

  let timer;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(doSearch, 120);
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (matches.length) setActive(idx + (e.shiftKey ? -1 : 1));
      else doSearch();
    } else if (e.key === 'Escape') {
      input.value = ''; clearHighlights(); input.blur();
    }
  });
  next.addEventListener('click', () => setActive(idx + 1));
  prev.addEventListener('click', () => setActive(idx - 1));

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
      e.preventDefault(); input.focus(); input.select();
    } else if (e.key === 'F3') {
      e.preventDefault(); setActive(idx + (e.shiftKey ? -1 : 1));
    } else if (e.key === '/' && document.activeElement !== input) {
      e.preventDefault(); input.focus();
    }
  });

  // ---------- custom scrollbars ----------

  function makeScrollbar(el) {
    const track = document.createElement('div');
    track.className = 'sb-track';
    const thumb = document.createElement('div');
    thumb.className = 'sb-thumb';
    track.appendChild(thumb);
    document.body.appendChild(track);

    function syncPos() {
      const r = el.getBoundingClientRect();
      track.style.top    = r.top + 'px';
      track.style.height = r.height + 'px';
      track.style.left   = (r.right - 14) + 'px';
    }

    function syncThumb() {
      const { scrollTop, scrollHeight, clientHeight } = el;
      if (scrollHeight <= clientHeight) {
        track.style.opacity = '0';
        track.style.pointerEvents = 'none';
        return;
      }
      track.style.opacity = '1';
      track.style.pointerEvents = '';
      const thumbH = Math.max(clientHeight / scrollHeight * clientHeight, 32);
      const travel  = clientHeight - thumbH;
      thumb.style.height = thumbH + 'px';
      thumb.style.transform = 'translateY(' + (travel * scrollTop / (scrollHeight - clientHeight)) + 'px)';
    }

    let rafPending = false;
    el.addEventListener('scroll', () => {
      if (!rafPending) { rafPending = true; requestAnimationFrame(() => { rafPending = false; syncThumb(); }); }
    }, { passive: true });
    const ro = new ResizeObserver(() => { syncPos(); syncThumb(); });
    ro.observe(el);
    const onResize = () => { syncPos(); syncThumb(); };
    window.addEventListener('resize', onResize, { passive: true });

    thumb.addEventListener('pointerdown', e => {
      e.preventDefault(); e.stopPropagation();
      const startY = e.clientY, startScroll = el.scrollTop;
      const { scrollHeight, clientHeight } = el;
      const travel = clientHeight - thumb.offsetHeight;
      const onMove = ev => {
        el.scrollTop = startScroll + (ev.clientY - startY) / travel * (scrollHeight - clientHeight);
      };
      const onUp = () => {
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
      };
      document.addEventListener('pointermove', onMove);
      document.addEventListener('pointerup', onUp);
    });

    track.addEventListener('pointerdown', e => {
      if (e.target === thumb) return;
      const r = track.getBoundingClientRect();
      el.scrollTo({ top: (e.clientY - r.top) / r.height * (el.scrollHeight - el.clientHeight), behavior: 'smooth' });
    });

    syncPos(); syncThumb();
    return {
      update() { syncPos(); syncThumb(); },
      destroy() { ro.disconnect(); window.removeEventListener('resize', onResize); track.remove(); }
    };
  }

  // ---------- edit ----------

  function canLeaveEdit() {
    if (!editDirty) return true;
    return confirm('You have unsaved changes. Discard?');
  }

  function setEditMode(active) {
    editMode = active;
    editDirty = false;
    editBtn.textContent = active ? 'View' : 'Edit';
    editBtn.classList.toggle('active', active);
    saveBtn.style.display = active ? '' : 'none';
    if (!active && previewSb) { previewSb.destroy(); previewSb = null; }
    if (!active && editorSb) { editorSb.destroy(); editorSb = null; }
  }

  async function enterEditMode() {
    if (!activeId) return;
    try {
      const r = await fetch(apiUrl('/api/docs/' + encodeURIComponent(activeId) + '/raw'));
      if (!r.ok) throw new Error('http ' + r.status);
      const data = await r.json();
      setEditMode(true);
      content.className = 'edit-layout';

      const editorPane = document.createElement('div');
      editorPane.className = 'edit-pane';
      const editorLabel = document.createElement('div');
      editorLabel.className = 'pane-label';
      editorLabel.textContent = 'Markdown';
      const textarea = document.createElement('textarea');
      textarea.id = 'editor';
      textarea.spellcheck = false;
      textarea.value = data.raw;
      editorPane.appendChild(editorLabel);
      editorPane.appendChild(textarea);

      const previewPane = document.createElement('div');
      previewPane.className = 'edit-pane';
      const previewLabel = document.createElement('div');
      previewLabel.className = 'pane-label';
      previewLabel.textContent = 'Preview';
      const previewScroll = document.createElement('div');
      previewScroll.className = 'preview-scroll';
      const previewEl = document.createElement('article');
      previewEl.className = 'content';
      previewScroll.appendChild(previewEl);
      previewPane.appendChild(previewLabel);
      previewPane.appendChild(previewScroll);

      content.replaceChildren(editorPane, previewPane);
      if (contentSb) contentSb.update();
      previewSb = makeScrollbar(previewScroll);
      editorSb = makeScrollbar(textarea);
      doPreview(data.raw);

      textarea.addEventListener('input', () => {
        editDirty = true;
        clearTimeout(previewTimer);
        previewTimer = setTimeout(() => doPreview(textarea.value), 300);
      });
      textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Tab') {
          e.preventDefault();
          const s = e.target.selectionStart, en = e.target.selectionEnd;
          e.target.value = e.target.value.slice(0, s) + '  ' + e.target.value.slice(en);
          e.target.selectionStart = e.target.selectionEnd = s + 2;
          editDirty = true;
          clearTimeout(previewTimer);
          previewTimer = setTimeout(() => doPreview(textarea.value), 300);
        }
      });
      textarea.focus();
    } catch(e) {
      console.error(e);
      alert('Failed to open editor: ' + e.message);
    }
  }

  async function doPreview(md) {
    try {
      const r = await fetch(apiUrl('/api/preview'), {
        method: 'POST',
        headers: {'Content-Type': 'text/plain; charset=utf-8'},
        body: md
      });
      if (!r.ok) return;
      const data = await r.json();
      const el = content.querySelector('.preview-scroll .content');
      if (el) el.replaceChildren(sanitizeMarkdownHTML(data.html));
    } catch(_) {}
  }

  async function saveDoc() {
    const textarea = document.getElementById('editor');
    if (!textarea || !activeId) return;
    try {
      const r = await fetch(apiUrl('/api/docs/' + encodeURIComponent(activeId) + '/content'), {
        method: 'PUT',
        headers: {'Content-Type': 'text/plain; charset=utf-8'},
        body: textarea.value
      });
      if (!r.ok) throw new Error('http ' + r.status);
      editDirty = false;
      saveBtn.textContent = 'Saved ✓';
      saveBtn.classList.add('saved');
      setTimeout(() => { saveBtn.textContent = 'Save'; saveBtn.classList.remove('saved'); }, 1500);
    } catch(e) {
      alert('Save failed: ' + e.message);
    }
  }

  editBtn.addEventListener('click', () => {
    if (!editMode) { if (activeId) enterEditMode(); }
    else { if (canLeaveEdit()) { setEditMode(false); selectDoc(activeId); } }
  });
  saveBtn.addEventListener('click', saveDoc);
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); if (editMode) saveDoc(); }
    if (e.key === 'Escape' && editMode) { if (canLeaveEdit()) { setEditMode(false); selectDoc(activeId); } }
  });

  // ---------- init ----------
  saveBtn.style.display = 'none';
  asideSb   = makeScrollbar(document.querySelector('aside'));
  contentSb = makeScrollbar(content);
  renderSidebar();
  renderBrowser();
  loadBrowser(browsePath);
  if (!activeId) setEmptyState();
  else selectDoc(activeId);
})();
