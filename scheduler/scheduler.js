// ── Constants ──────────────────────────────────────────────────────
const ROW_H  = 28;
const DAY_MS = 86_400_000;
const MONTHS  = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const ZOOM_PPD = { day: 28, week: 14, month: 5 };

// ── State ──────────────────────────────────────────────────────────
let S = {
  title:    'New Project',
  tasks:    [],
  zoom:     'week',
  selId:    null,
  nextId:   1,
};

// ── Date helpers ───────────────────────────────────────────────────
const toDate = s => new Date(s + 'T00:00:00');
const toStr  = d => d.toISOString().slice(0, 10);
const today  = ()  => toStr(new Date());

function addDays(s, n) {
  const d = toDate(s);
  d.setDate(d.getDate() + n);
  return toStr(d);
}
function diffDays(a, b) {
  return Math.round((toDate(b) - toDate(a)) / DAY_MS);
}

// ── Task helpers ───────────────────────────────────────────────────
function sel()    { return S.tasks.find(t => t.id === S.selId) || null; }
function selIdx() { return S.tasks.findIndex(t => t.id === S.selId); }

function makeTask(overrides = {}) {
  const base = sel();
  const start = base ? addDays(base.end, 1) : today();
  return Object.assign({
    id:           S.nextId++,
    name:         'New Task',
    indent:       base ? base.indent : 0,
    duration:     5,
    start,
    end:          addDays(start, 4),
    predecessors: [],
    complete:     0,
    resource:     '',
    isMilestone:  false,
    isSummary:    false,
    isCritical:   false,
  }, overrides);
}

// Detect summary tasks (any task whose next sibling at deeper indent)
function flagSummaries() {
  for (let i = 0; i < S.tasks.length; i++) {
    const nxt = S.tasks[i + 1];
    S.tasks[i].isSummary = !!(nxt && nxt.indent > S.tasks[i].indent);
  }
}

// Roll up summary start/end from children (bottom-up)
function rollupSummaries() {
  for (let i = S.tasks.length - 1; i >= 0; i--) {
    const t = S.tasks[i];
    if (!t.isSummary) continue;
    const kids = childrenOf(i);
    if (!kids.length) continue;
    t.start    = kids.reduce((m, c) => c.start < m ? c.start : m, kids[0].start);
    t.end      = kids.reduce((m, c) => c.end   > m ? c.end   : m, kids[0].end);
    t.duration = diffDays(t.start, t.end) + 1;
  }
}

function childrenOf(parentIdx) {
  const pi = S.tasks[parentIdx].indent;
  const out = [];
  for (let i = parentIdx + 1; i < S.tasks.length; i++) {
    if (S.tasks[i].indent <= pi) break;
    if (S.tasks[i].indent === pi + 1) out.push(S.tasks[i]);
  }
  return out;
}

// Forward pass: schedule FS dependencies
function scheduleDeps() {
  for (const t of S.tasks) {
    if (!t.predecessors.length || t.isSummary) continue;
    let latest = null;
    for (const pid of t.predecessors) {
      const p = S.tasks.find(x => x.id === pid);
      if (p && (!latest || p.end > latest)) latest = p.end;
    }
    if (latest && t.start <= latest) {
      t.start = addDays(latest, 1);
      t.end   = addDays(t.start, Math.max(0, t.duration - 1));
    }
  }
}

// Critical path: simple longest-path through dependency graph
function computeCritical() {
  const n = S.tasks.length;
  if (!n) return;

  // EF = Early Finish indexed by task id
  const EF = {};
  for (const t of S.tasks) {
    let ef = diffDays(S.tasks[0].start, t.end);
    EF[t.id] = ef;
  }

  // Project end = max EF
  const projEnd = Math.max(...Object.values(EF));

  // LF = Late Finish
  const LF = {};
  for (const t of S.tasks) LF[t.id] = projEnd;

  // Backward pass
  for (let i = S.tasks.length - 1; i >= 0; i--) {
    const t = S.tasks[i];
    // Find tasks that have t as predecessor
    for (const succ of S.tasks) {
      if (succ.predecessors.includes(t.id)) {
        const succLS = LF[succ.id] - (succ.duration - 1);
        const predLF = succLS - 1;
        if (predLF < LF[t.id]) LF[t.id] = predLF;
      }
    }
  }

  for (const t of S.tasks) {
    const totalFloat = LF[t.id] - EF[t.id];
    t.isCritical = totalFloat <= 0 && !t.isSummary;
  }
}

function recompute() {
  flagSummaries();
  scheduleDeps();
  rollupSummaries();
  computeCritical();
}

// ── WBS numbering ──────────────────────────────────────────────────
function wbs(idx) {
  const counters = [];
  let curIndent = -1;
  for (let i = 0; i <= idx; i++) {
    const indent = S.tasks[i].indent;
    if (indent > curIndent) {
      counters.push(1);
    } else if (indent === curIndent) {
      counters[counters.length - 1]++;
    } else {
      while (counters.length > indent + 1) counters.pop();
      counters[counters.length - 1]++;
    }
    curIndent = indent;
  }
  return counters.join('.');
}

// ── Task CRUD ──────────────────────────────────────────────────────
function insertAfterSel(task) {
  const idx = selIdx();
  if (idx < 0) {
    S.tasks.push(task);
  } else {
    // Skip past children of selected
    let ins = idx + 1;
    while (ins < S.tasks.length && S.tasks[ins].indent > S.tasks[idx].indent) ins++;
    S.tasks.splice(ins, 0, task);
  }
  S.selId = task.id;
}

function addTask() {
  insertAfterSel(makeTask());
  recompute(); render(); focusName();
}

function addMilestone() {
  const base = sel();
  const d = base ? base.end : today();
  insertAfterSel(makeTask({ name: 'Milestone', duration: 0, start: d, end: d, isMilestone: true }));
  recompute(); render(); focusName();
}

function deleteTask() {
  const idx = selIdx();
  if (idx < 0) return;
  const indent = S.tasks[idx].indent;
  let end = idx + 1;
  while (end < S.tasks.length && S.tasks[end].indent > indent) end++;
  const removed = S.tasks.splice(idx, end - idx).map(t => t.id);
  for (const t of S.tasks) t.predecessors = t.predecessors.filter(id => !removed.includes(id));
  S.selId = S.tasks[idx]?.id ?? S.tasks[idx - 1]?.id ?? null;
  recompute(); render();
}

function indentTask() {
  const idx = selIdx();
  if (idx < 1) return;
  const t = S.tasks[idx];
  const prev = S.tasks[idx - 1];
  if (t.indent <= prev.indent) { t.indent++; recompute(); render(); }
}

function outdentTask() {
  const idx = selIdx();
  if (idx < 0) return;
  const t = S.tasks[idx];
  if (t.indent > 0) {
    const orig = t.indent;
    t.indent--;
    for (let i = idx + 1; i < S.tasks.length && S.tasks[i].indent > orig; i++) S.tasks[i].indent--;
    recompute(); render();
  }
}

function moveUp() {
  const idx = selIdx();
  if (idx < 1) return;
  const t   = S.tasks[idx];
  let thisEnd = idx + 1;
  while (thisEnd < S.tasks.length && S.tasks[thisEnd].indent > t.indent) thisEnd++;
  let prevStart = idx - 1;
  while (prevStart > 0 && S.tasks[prevStart].indent > S.tasks[idx - 1].indent) prevStart--;
  const block = S.tasks.splice(idx, thisEnd - idx);
  S.tasks.splice(prevStart, 0, ...block);
  recompute(); render();
}

function moveDown() {
  const idx = selIdx();
  if (idx < 0) return;
  const t = S.tasks[idx];
  let thisEnd = idx + 1;
  while (thisEnd < S.tasks.length && S.tasks[thisEnd].indent > t.indent) thisEnd++;
  if (thisEnd >= S.tasks.length) return;
  let nextEnd = thisEnd + 1;
  while (nextEnd < S.tasks.length && S.tasks[nextEnd].indent > S.tasks[thisEnd].indent) nextEnd++;
  const next = S.tasks.splice(thisEnd, nextEnd - thisEnd);
  S.tasks.splice(idx, 0, ...next);
  recompute(); render();
}

function focusName() {
  requestAnimationFrame(() => {
    const inp = document.querySelector(`.task-row.sel .name-input`);
    if (inp) { inp.focus(); inp.select(); }
  });
}

// ── Zoom ───────────────────────────────────────────────────────────
function setZoom(z) {
  S.zoom = z;
  ['day','week','month'].forEach(k => {
    document.getElementById('zoom-' + k).classList.toggle('zoom-active', k === z);
  });
  renderGantt();
}

function ppd() { return ZOOM_PPD[S.zoom]; }

// ── Date range ─────────────────────────────────────────────────────
function dateRange() {
  if (!S.tasks.length) {
    const d = today();
    return { start: addDays(d, -7), end: addDays(d, 60) };
  }
  let s = S.tasks[0].start, e = S.tasks[0].end;
  for (const t of S.tasks) {
    if (t.start < s) s = t.start;
    if (t.end   > e) e = t.end;
  }
  // Start at first of month minus 1 week
  const sd = toDate(s); sd.setDate(1);
  const rangeStart = addDays(toStr(sd), -7);
  // End at end of month + 3 weeks
  const ed = toDate(e); ed.setMonth(ed.getMonth() + 1); ed.setDate(0);
  const rangeEnd = addDays(toStr(ed), 21);
  return { start: rangeStart, end: rangeEnd };
}

// ── Rendering ──────────────────────────────────────────────────────
function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function render() {
  renderTaskGrid();
  renderGantt();
}

function renderTaskGrid() {
  const body = document.getElementById('task-body');
  const frag = document.createDocumentFragment();

  S.tasks.forEach((t, i) => {
    const row = document.createElement('div');
    row.className = 'task-row' +
      (t.id === S.selId   ? ' sel'          : '') +
      (t.isSummary        ? ' is-summary'   : '') +
      (t.isMilestone      ? ' is-milestone' : '') +
      (t.isCritical       ? ' is-critical'  : '');
    row.dataset.id = t.id;

    const icon = t.isMilestone ? '◆' : t.isSummary ? '▼' : '▷';
    const ro   = t.isSummary || t.isMilestone;

    row.innerHTML =
      `<div class="c-wbs">${wbs(i)}</div>` +
      `<div class="c-name name-cell">` +
        `<span class="indent-sp" style="width:${t.indent * 16}px"></span>` +
        `<span class="task-icon">${icon}</span>` +
        `<input class="name-input" value="${esc(t.name)}" data-id="${t.id}" data-f="name">` +
      `</div>` +
      `<div class="c-dur"><input type="number" min="0" value="${t.duration}" data-id="${t.id}" data-f="duration"${ro?' readonly':''}></div>` +
      `<div class="c-start"><input type="date" value="${t.start}" data-id="${t.id}" data-f="start"${ro?' readonly':''}></div>` +
      `<div class="c-fin"><input type="date" value="${t.end}" data-id="${t.id}" data-f="end"${ro?' readonly':''}></div>` +
      `<div class="c-pred"><input value="${t.predecessors.join(',')}" placeholder="1,2" data-id="${t.id}" data-f="predecessors"${t.isSummary?' readonly':''}></div>` +
      `<div class="c-pct"><input type="number" min="0" max="100" value="${t.complete}" data-id="${t.id}" data-f="complete"></div>` +
      `<div class="c-res"><input value="${esc(t.resource)}" data-id="${t.id}" data-f="resource"></div>`;

    row.addEventListener('mousedown', e => {
      if (e.target.tagName !== 'INPUT') { S.selId = t.id; render(); }
    });

    frag.appendChild(row);
  });

  body.innerHTML = '';
  body.appendChild(frag);

  // Wire inputs (event delegation on body)
  body.querySelectorAll('input').forEach(inp => {
    inp.addEventListener('mousedown', e => {
      e.stopPropagation();
      const id = parseInt(inp.dataset.id);
      if (S.selId !== id) { S.selId = id; render(); inp.focus(); }
    });
    inp.addEventListener('change', onCellChange);
    inp.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); inp.blur(); }
    });
  });
}

function onCellChange(e) {
  const inp  = e.target;
  const id   = parseInt(inp.dataset.id);
  const f    = inp.dataset.f;
  const t    = S.tasks.find(x => x.id === id);
  if (!t) return;

  if (f === 'name') {
    t.name = inp.value;
  } else if (f === 'duration') {
    const dur = Math.max(0, parseInt(inp.value) || 0);
    t.duration = dur;
    t.end = addDays(t.start, Math.max(0, dur - 1));
  } else if (f === 'start') {
    if (inp.value) { t.start = inp.value; t.end = addDays(t.start, Math.max(0, t.duration - 1)); }
  } else if (f === 'end') {
    if (inp.value) { t.end = inp.value; t.duration = Math.max(1, diffDays(t.start, t.end) + 1); }
  } else if (f === 'predecessors') {
    t.predecessors = inp.value.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n) && n > 0);
  } else if (f === 'complete') {
    t.complete = Math.max(0, Math.min(100, parseInt(inp.value) || 0));
  } else if (f === 'resource') {
    t.resource = inp.value;
  }

  recompute();
  renderGantt();
  // Refresh readonly cells
  document.querySelectorAll(`.task-row[data-id="${id}"] input[data-f="start"]`).forEach(i => i.value = t.start);
  document.querySelectorAll(`.task-row[data-id="${id}"] input[data-f="end"]`).forEach(i => i.value = t.end);
  document.querySelectorAll(`.task-row[data-id="${id}"] input[data-f="duration"]`).forEach(i => i.value = t.duration);
}

// ── Gantt rendering ────────────────────────────────────────────────
function renderGantt() {
  const { start: rs, end: re } = dateRange();
  const PX   = ppd();
  const todayStr = today();
  const totalDays  = diffDays(rs, re) + 1;
  const totalWidth = totalDays * PX;

  buildGanttHeader(rs, re, PX, todayStr, totalWidth);
  buildGanttBody(rs, PX, todayStr, totalWidth);
}

function buildGanttHeader(rs, re, PX, todayStr, totalWidth) {
  const head = document.getElementById('g-head-inner');

  // Build day list
  const days = [];
  const d = toDate(rs);
  const end = toDate(re);
  while (d <= end) {
    days.push({ str: toStr(d), dow: d.getDay(), num: d.getDate(), m: d.getMonth(), y: d.getFullYear() });
    d.setDate(d.getDate() + 1);
  }

  // Month spans
  let mHtml = '';
  let mStart = 0, curM = -1, curY = -1;
  days.forEach((day, i) => {
    if (day.m !== curM || day.y !== curY) {
      if (curM >= 0) mHtml += `<div class="g-month-cell" style="width:${(i - mStart) * PX}px">${MONTHS[curM]} ${curY}</div>`;
      curM = day.m; curY = day.y; mStart = i;
    }
  });
  mHtml += `<div class="g-month-cell" style="width:${(days.length - mStart) * PX}px">${MONTHS[curM]} ${curY}</div>`;

  // Day cells
  const showNum = PX >= 12;
  const dHtml = days.map(day =>
    `<div class="g-day-cell${day.dow===0||day.dow===6?' wknd':''}${day.str===todayStr?' now':''}" style="width:${PX}px">${showNum ? day.num : ''}</div>`
  ).join('');

  head.style.width = totalWidth + 'px';
  head.innerHTML = `<div class="g-months" style="width:${totalWidth}px">${mHtml}</div><div class="g-days" style="width:${totalWidth}px">${dHtml}</div>`;
}

function buildGanttBody(rs, PX, todayStr, totalWidth) {
  const inner  = document.getElementById('g-inner');
  const totalH = S.tasks.length * ROW_H;

  inner.style.width  = totalWidth + 'px';
  inner.style.height = totalH + 'px';

  // Build all days for shading
  const days = [];
  const d = toDate(rs);
  let dayCount = Math.ceil(totalWidth / PX) + 1;
  for (let i = 0; i < dayCount; i++) {
    days.push({ str: toStr(d), dow: d.getDay() });
    d.setDate(d.getDate() + 1);
  }

  // Weekend shading + today line
  let shadeHtml = '';
  days.forEach((day, i) => {
    if (day.dow === 0 || day.dow === 6) {
      shadeHtml += `<div class="shade shade-wknd" style="left:${i*PX}px;width:${PX}px;height:${totalH}px"></div>`;
    }
    if (day.str === todayStr) {
      shadeHtml += `<div class="shade shade-today" style="left:${i*PX+PX/2}px;height:${totalH}px"></div>`;
    }
  });

  // Task rows + bars
  let rowsHtml = '';
  S.tasks.forEach((t, i) => {
    const y     = i * ROW_H;
    const left  = diffDays(rs, t.start) * PX;
    const width = Math.max(PX * 0.5, (Math.max(1, t.duration) * PX));

    let barHtml = '';
    if (t.isMilestone) {
      barHtml = `<div class="bar-milestone" style="left:${left - 7}px;top:${y + 7}px"></div>
                 <div class="bar-label" style="left:${left + 12}px;top:${y + 4}px;position:absolute;font-size:11px;color:#666;white-space:nowrap">${esc(t.name)}</div>`;
    } else if (t.isSummary) {
      barHtml = `<div class="bar-summary${t.isCritical?' critical':''}" style="left:${left}px;top:${y}px;width:${width}px"></div>`;
    } else {
      const doneW = Math.round(width * t.complete / 100);
      barHtml = `<div class="bar-wrap${t.id===S.selId?' sel':''}" style="left:${left}px;top:${y+4}px;width:${width}px"
                   data-id="${t.id}" onmousedown="startDrag(event,${t.id},'move')">
        <div class="bar${t.isCritical?' critical':''}">
          <div class="bar-done-fill" style="width:${doneW}px"></div>
        </div>
        ${t.resource ? `<span class="bar-label">${esc(t.resource)}</span>` : ''}
        <div class="bar-resize" onmousedown="startDrag(event,${t.id},'resize')"></div>
      </div>`;
    }

    rowsHtml += `<div class="g-row${t.id===S.selId?' sel':''}" style="top:${y}px;width:${totalWidth}px;position:absolute" data-id="${t.id}" onclick="selectRow(${t.id})"></div>`;
    shadeHtml += barHtml;
  });

  // Dependency arrows SVG
  const svgArrows = renderDeps(rs, PX);

  inner.innerHTML = shadeHtml + rowsHtml + svgArrows;
}

function renderDeps(rs, PX) {
  let paths = '';
  S.tasks.forEach((t, toIdx) => {
    for (const pid of t.predecessors) {
      const fromIdx = S.tasks.findIndex(x => x.id === pid);
      if (fromIdx < 0) continue;
      const pred = S.tasks[fromIdx];
      const x1 = (diffDays(rs, pred.end) + 1) * PX;
      const y1 = fromIdx * ROW_H + ROW_H / 2;
      const x2 = diffDays(rs, t.start) * PX;
      const y2 = toIdx  * ROW_H + ROW_H / 2;
      const cx = x1 + Math.max(12, (x2 - x1) * 0.5);
      paths += `<path class="dep-arrow" d="M${x1},${y1} H${cx} V${y2} H${x2}" marker-end="url(#arr)"/>`;
    }
  });
  if (!paths) return '';
  const totalWidth = parseInt(document.getElementById('g-inner').style.width);
  const totalH = S.tasks.length * ROW_H;
  return `<svg class="dep-svg" style="width:${totalWidth}px;height:${totalH}px">
    <defs><marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
      <polygon points="0 0,6 3,0 6" fill="#b03030"/>
    </marker></defs>
    ${paths}
  </svg>`;
}

function selectRow(id) {
  S.selId = id;
  render();
}

// ── Drag bars ──────────────────────────────────────────────────────
let drag = null;

function startDrag(e, id, mode) {
  e.preventDefault();
  e.stopPropagation();
  S.selId = id;
  const t = S.tasks.find(x => x.id === id);
  if (!t) return;
  drag = { id, mode, x0: e.clientX, start0: t.start, end0: t.end, dur0: t.duration };
  document.addEventListener('mousemove', onDragMove);
  document.addEventListener('mouseup', onDragEnd);
  document.body.style.cursor = mode === 'move' ? 'grabbing' : 'e-resize';
}

function onDragMove(e) {
  if (!drag) return;
  const delta = Math.round((e.clientX - drag.x0) / ppd());
  const t = S.tasks.find(x => x.id === drag.id);
  if (!t) return;
  if (drag.mode === 'move') {
    t.start = addDays(drag.start0, delta);
    t.end   = addDays(drag.end0,   delta);
  } else {
    const newDur = Math.max(1, drag.dur0 + delta);
    t.duration = newDur;
    t.end = addDays(drag.start0, newDur - 1);
  }
  recompute();
  renderGantt();
}

function onDragEnd() {
  if (!drag) return;
  drag = null;
  document.removeEventListener('mousemove', onDragMove);
  document.removeEventListener('mouseup', onDragEnd);
  document.body.style.cursor = '';
  render();
}

// ── Scroll sync ────────────────────────────────────────────────────
function initScrollSync() {
  const gBody    = document.getElementById('g-body');
  const taskBody = document.getElementById('task-body');
  const gHeadIn  = document.getElementById('g-head-inner');
  let syncing = false;

  gBody.addEventListener('scroll', () => {
    if (syncing) return; syncing = true;
    taskBody.scrollTop = gBody.scrollTop;
    gHeadIn.style.transform = `translateX(-${gBody.scrollLeft}px)`;
    syncing = false;
  });
  taskBody.addEventListener('scroll', () => {
    if (syncing) return; syncing = true;
    gBody.scrollTop = taskBody.scrollTop;
    syncing = false;
  });
}

// ── Splitter resize ────────────────────────────────────────────────
function initSplitter() {
  const splitter = document.getElementById('splitter');
  const pane     = document.getElementById('task-pane');
  let x0, w0;

  splitter.addEventListener('mousedown', e => {
    x0 = e.clientX; w0 = pane.offsetWidth;
    splitter.classList.add('dragging');
    document.addEventListener('mousemove', onSplitMove);
    document.addEventListener('mouseup',   onSplitEnd);
    e.preventDefault();
  });

  function onSplitMove(e) {
    const newW = Math.max(280, Math.min(900, w0 + e.clientX - x0));
    pane.style.width = newW + 'px';
  }
  function onSplitEnd() {
    splitter.classList.remove('dragging');
    document.removeEventListener('mousemove', onSplitMove);
    document.removeEventListener('mouseup', onSplitEnd);
  }
}

// ── Keyboard shortcuts ─────────────────────────────────────────────
function initKeyboard() {
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT') {
      if (e.key === 'Escape') e.target.blur();
      return;
    }
    if (e.key === 'Insert')                          { addTask(); return; }
    if (e.key === 'Delete')                          { deleteTask(); return; }
    if (e.key === 'Tab' && !e.shiftKey)              { e.preventDefault(); indentTask(); return; }
    if (e.key === 'Tab' &&  e.shiftKey)              { e.preventDefault(); outdentTask(); return; }
    if (e.key === 'ArrowUp'   && e.altKey)           { e.preventDefault(); moveUp(); return; }
    if (e.key === 'ArrowDown' && e.altKey)           { e.preventDefault(); moveDown(); return; }
    if (e.key === 'ArrowUp'   && !e.altKey)          { navRow(-1); return; }
    if (e.key === 'ArrowDown' && !e.altKey)          { navRow(+1); return; }
  });
}

function navRow(delta) {
  const idx = selIdx();
  const newIdx = Math.max(0, Math.min(S.tasks.length - 1, idx + delta));
  if (S.tasks[newIdx]) { S.selId = S.tasks[newIdx].id; render(); }
}

// ── Project title ──────────────────────────────────────────────────
function initTitle() {
  document.getElementById('project-title').addEventListener('change', e => {
    S.title = e.target.value;
    document.title = e.target.value + ' · IMS Builder';
  });
}

// ── Save / Load / Export ───────────────────────────────────────────
function saveProject() {
  localStorage.setItem('ims', JSON.stringify(S));
  setStatus('Saved ✓');
}

function loadProject() {
  const raw = localStorage.getItem('ims');
  if (!raw) { setStatus('No saved project.'); return; }
  Object.assign(S, JSON.parse(raw));
  document.getElementById('project-title').value = S.title;
  document.title = S.title + ' · IMS Builder';
  recompute(); render();
  setStatus('Loaded ✓');
}

function newProject() {
  if (S.tasks.length && !confirm('Start a new project? Unsaved changes will be lost.')) return;
  S = { title: 'New Project', tasks: [], zoom: S.zoom, selId: null, nextId: 1 };
  document.getElementById('project-title').value = 'New Project';
  document.title = 'New Project · IMS Builder';
  render();
}

function exportCSV() {
  const rows = [['WBS','Task Name','Duration','Start','Finish','Predecessors','% Complete','Resource','Critical']];
  S.tasks.forEach((t, i) => rows.push([
    wbs(i), t.name, t.duration, t.start, t.end,
    t.predecessors.join(';'), t.complete, t.resource, t.isCritical ? 'Yes' : ''
  ]));
  const csv  = rows.map(r => r.map(v => `"${String(v ?? '').replace(/"/g,'""')}"`).join(',')).join('\n');
  const a    = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(new Blob([csv], { type: 'text/csv' })),
    download: (S.title || 'project') + '.csv',
  });
  a.click();
}

function setStatus(msg) {
  const el = document.getElementById('status');
  el.textContent = msg;
  setTimeout(() => { el.textContent = 'Ready · Insert=Add Task · Tab=Indent · Del=Delete · Alt+↑↓=Move'; }, 3000);
}

// ── Sample data ────────────────────────────────────────────────────
function loadSample() {
  const b = today();
  S.tasks = [
    { id:1,  name:'Phase 1 — Initiation',    indent:0, duration:10, start:b,              end:addDays(b,9),   predecessors:[],   complete:100, resource:'',       isMilestone:false },
    { id:2,  name:'Define scope & objectives',indent:1,duration:4,  start:b,              end:addDays(b,3),   predecessors:[],   complete:100, resource:'Alice',   isMilestone:false },
    { id:3,  name:'Stakeholder alignment',    indent:1, duration:4,  start:addDays(b,4),  end:addDays(b,7),   predecessors:[2],  complete:100, resource:'Bob',     isMilestone:false },
    { id:4,  name:'Kickoff Complete',         indent:1, duration:0,  start:addDays(b,8),  end:addDays(b,8),   predecessors:[3],  complete:0,   resource:'',        isMilestone:true  },
    { id:5,  name:'Phase 2 — Design',        indent:0, duration:14, start:addDays(b,10), end:addDays(b,23),  predecessors:[1],  complete:40,  resource:'',        isMilestone:false },
    { id:6,  name:'Architecture design',     indent:1, duration:6,  start:addDays(b,10), end:addDays(b,15),  predecessors:[4],  complete:80,  resource:'Carol',   isMilestone:false },
    { id:7,  name:'UI / UX mockups',         indent:1, duration:8,  start:addDays(b,10), end:addDays(b,17),  predecessors:[4],  complete:50,  resource:'Dave',    isMilestone:false },
    { id:8,  name:'Design review gate',      indent:1, duration:0,  start:addDays(b,18), end:addDays(b,18),  predecessors:[6,7],complete:0,   resource:'',        isMilestone:true  },
    { id:9,  name:'Phase 3 — Build',         indent:0, duration:20, start:addDays(b,19), end:addDays(b,38),  predecessors:[5],  complete:0,   resource:'',        isMilestone:false },
    { id:10, name:'Backend development',     indent:1, duration:14, start:addDays(b,19), end:addDays(b,32),  predecessors:[8],  complete:0,   resource:'Eve',     isMilestone:false },
    { id:11, name:'Frontend integration',    indent:1, duration:10, start:addDays(b,23), end:addDays(b,32),  predecessors:[8],  complete:0,   resource:'Frank',   isMilestone:false },
    { id:12, name:'Integration & testing',   indent:1, duration:6,  start:addDays(b,33), end:addDays(b,38),  predecessors:[10,11],complete:0, resource:'Eve',     isMilestone:false },
    { id:13, name:'Phase 4 — Close',         indent:0, duration:5,  start:addDays(b,39), end:addDays(b,43),  predecessors:[9],  complete:0,   resource:'',        isMilestone:false },
    { id:14, name:'UAT sign-off',            indent:1, duration:3,  start:addDays(b,39), end:addDays(b,41),  predecessors:[12], complete:0,   resource:'Alice',   isMilestone:false },
    { id:15, name:'Project Complete',        indent:1, duration:0,  start:addDays(b,42), end:addDays(b,42),  predecessors:[14], complete:0,   resource:'',        isMilestone:true  },
  ];
  S.nextId = 16;
  S.selId  = 1;
}

// ── Init ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadSample();
  recompute();
  render();
  initScrollSync();
  initSplitter();
  initKeyboard();
  initTitle();
});
