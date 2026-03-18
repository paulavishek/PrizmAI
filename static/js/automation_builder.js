/**
 * PrizmAI — Automation Builder Canvas Engine
 * Visual flowchart builder using vanilla JS + SVG
 *
 * Block types:
 *   trigger   — top-level entry point  (blue)
 *   condition — IF/ELSE branching      (amber)
 *   action    — leaf/chained operation  (green)
 */
(function () {
  'use strict';

  /* ─── Constants ─── */
  const BLOCK_W = 240, BLOCK_H = 60, GAP_Y = 80, GAP_X = 300;
  const COLORS = {
    trigger:   { bg: '#e0f0ff', border: '#0d6efd', text: '#0d47a1' },
    condition: { bg: '#fff8e1', border: '#f59e0b', text: '#78350f' },
    action:    { bg: '#e8f8e8', border: '#198754', text: '#14532d' },
  };
  const ICONS = {
    trigger:   '\uf04b',  // fa-play
    condition: '\uf074',  // fa-random / branch
    action:    '\uf013',  // fa-cog
  };

  /* ─── State ─── */
  let canvas, svg, toolbar, blocksLayer, linesLayer;
  let blocks = {};          // id → {el, data, x, y, children[], else_children[]}
  let rootId = null;
  let dragState = null;     // {blockId, offsetX, offsetY}
  let boardId = null;
  let ruleId  = null;
  let ruleName = '';

  /* ─── Palette definitions ─── */
  const TRIGGERS = [
    { block_type: 'task_created',        label: 'Task Created' },
    { block_type: 'task_completed',      label: 'Task Completed' },
    { block_type: 'moved_to_column',     label: 'Moved to Column' },
    { block_type: 'task_assigned',       label: 'Task Assigned' },
    { block_type: 'priority_changed',    label: 'Priority Changed' },
    { block_type: 'task_overdue',        label: 'Task Overdue' },
    { block_type: 'due_date_approaching',label: 'Due Date Near' },
    { block_type: 'scheduled_daily',     label: 'Scheduled Daily' },
    { block_type: 'scheduled_weekly',    label: 'Scheduled Weekly' },
    { block_type: 'scheduled_monthly',   label: 'Scheduled Monthly' },
  ];
  const CONDITIONS = [
    { block_type: 'priority_equals',      label: 'Priority Equals' },
    { block_type: 'assignee_is',          label: 'Assignee Is' },
    { block_type: 'column_equals',        label: 'Column Equals' },
    { block_type: 'due_date_within',      label: 'Due Within N Days' },
    { block_type: 'task_has_label',       label: 'Has Label' },
    { block_type: 'all_children_complete', label: 'All Subtasks Done' },
    { block_type: 'progress_gte',         label: 'Progress ≥' },
    { block_type: 'stale_high_priority',  label: 'Stale High Priority' },
  ];
  const ACTIONS = [
    { block_type: 'set_priority',     label: 'Set Priority' },
    { block_type: 'add_label',        label: 'Add Label' },
    { block_type: 'remove_label',     label: 'Remove Label' },
    { block_type: 'send_notification',label: 'Send Notification' },
    { block_type: 'move_to_column',   label: 'Move to Column' },
    { block_type: 'assign_to_user',   label: 'Assign to User' },
    { block_type: 'set_due_date',     label: 'Set Due Date' },
    { block_type: 'close_task',       label: 'Close Task' },
    { block_type: 'create_comment',   label: 'Create Comment' },
    { block_type: 'log_time_entry',   label: 'Log Time Entry' },
  ];

  /* ─── UUID ─── */
  function uid() {
    return 'xxxx-xxxx'.replace(/x/g, function () {
      return ((Math.random() * 16) | 0).toString(16);
    });
  }

  /* ─── Cookie helper ─── */
  function getCookie(name) {
    var m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? m.pop() : '';
  }

  /* ─── SVG helpers ─── */
  function svgEl(tag, attrs) {
    var el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    return el;
  }

  /* ─── Initialise ─── */
  function init(canvasEl, bid) {
    canvas = canvasEl;
    boardId = bid;
    canvas.innerHTML = '';
    canvas.style.position = 'relative';
    canvas.style.overflow = 'auto';
    canvas.style.minHeight = '500px';
    canvas.classList.remove('canvas-placeholder');
    canvas.style.border = '1px solid var(--border-color)';
    canvas.style.borderRadius = '12px';
    canvas.style.background = 'var(--bg-primary)';

    // SVG layer for connector lines
    svg = svgEl('svg', { width: '100%', height: '100%', style: 'position:absolute;top:0;left:0;pointer-events:none;overflow:visible;' });
    linesLayer = svgEl('g');
    svg.appendChild(linesLayer);
    canvas.appendChild(svg);

    // DOM layer for blocks
    blocksLayer = document.createElement('div');
    blocksLayer.style.position = 'relative';
    blocksLayer.style.minHeight = '500px';
    canvas.appendChild(blocksLayer);

    // Build toolbar
    _buildToolbar();

    // Top bar (save / name)
    _buildTopBar();
  }

  /* ─── Top bar with rule name + save ─── */
  function _buildTopBar() {
    var bar = document.createElement('div');
    bar.style.cssText = 'display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid var(--border-color);background:var(--card-bg);border-radius:12px 12px 0 0;';
    bar.innerHTML =
      '<input id="canvasRuleName" type="text" class="form-control form-control-sm" style="max-width:260px;" placeholder="Rule name" value="' + _esc(ruleName) + '">' +
      '<button id="canvasSaveBtn" class="btn btn-sm btn-primary"><i class="fas fa-save me-1"></i>Save Rule</button>' +
      '<button id="canvasCloseBtn" class="btn btn-sm btn-outline-secondary ms-auto"><i class="fas fa-times me-1"></i>Close</button>';
    canvas.insertBefore(bar, canvas.firstChild);

    document.getElementById('canvasSaveBtn').addEventListener('click', _saveRule);
    document.getElementById('canvasCloseBtn').addEventListener('click', _closeCanvas);
  }

  /* ─── Toolbar / palette ─── */
  function _buildToolbar() {
    toolbar = document.createElement('div');
    toolbar.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;padding:10px 16px;border-bottom:1px solid var(--border-color);background:var(--bg-secondary);';

    var sections = [
      { label: 'Triggers', items: TRIGGERS, type: 'trigger' },
      { label: 'Conditions', items: CONDITIONS, type: 'condition' },
      { label: 'Actions', items: ACTIONS, type: 'action' },
    ];

    sections.forEach(function (sec) {
      var group = document.createElement('div');
      group.className = 'dropdown';
      group.innerHTML =
        '<button class="btn btn-sm btn-outline-secondary dropdown-toggle" style="border-color:' + COLORS[sec.type].border + ';color:' + COLORS[sec.type].text + ';" data-bs-toggle="dropdown">' +
        sec.label + '</button>' +
        '<ul class="dropdown-menu"></ul>';
      var ul = group.querySelector('ul');
      sec.items.forEach(function (item) {
        var li = document.createElement('li');
        li.innerHTML = '<a class="dropdown-item small" href="#">' + _esc(item.label) + '</a>';
        li.querySelector('a').addEventListener('click', function (e) {
          e.preventDefault();
          _addBlock(sec.type, item.block_type, item.label, {});
        });
        ul.appendChild(li);
      });
      toolbar.appendChild(group);
    });

    canvas.insertBefore(toolbar, canvas.children[1] || null);
  }

  /* ─── Add a block to the canvas ─── */
  function _addBlock(type, block_type, label, config, parentId, isElse) {
    var id = uid();
    var x = 40, y = 40;

    // Position below parent if provided
    if (parentId && blocks[parentId]) {
      var pb = blocks[parentId];
      x = pb.x + (isElse ? GAP_X : 0);
      y = pb.y + GAP_Y + BLOCK_H;
    } else {
      // Find lowest y and place below
      var maxY = 0;
      Object.keys(blocks).forEach(function (bid) { if (blocks[bid].y > maxY) maxY = blocks[bid].y; });
      y = maxY > 0 ? maxY + GAP_Y + BLOCK_H : 40;
    }

    var col = COLORS[type] || COLORS.action;
    var el = document.createElement('div');
    el.className = 'canvas-block';
    el.dataset.blockId = id;
    el.style.cssText =
      'position:absolute;left:' + x + 'px;top:' + y + 'px;width:' + BLOCK_W + 'px;' +
      'min-height:' + BLOCK_H + 'px;border-radius:10px;border:2px solid ' + col.border + ';' +
      'background:' + col.bg + ';color:' + col.text + ';padding:10px 14px;cursor:grab;' +
      'box-shadow:0 2px 8px rgba(0,0,0,.08);user-select:none;z-index:10;';

    el.innerHTML =
      '<div style="display:flex;align-items:center;gap:8px;">' +
        '<span style="font-size:.72rem;text-transform:uppercase;font-weight:700;opacity:.7;">' + type + '</span>' +
        '<span class="ms-auto" style="cursor:pointer;opacity:.5;font-size:.8rem;" data-action="delete" title="Remove">&times;</span>' +
      '</div>' +
      '<div style="font-weight:600;font-size:.88rem;margin-top:4px;" class="block-label">' + _esc(label) + '</div>' +
      '<div class="block-config-summary small" style="margin-top:2px;opacity:.7;"></div>' +
      '<div style="display:flex;gap:4px;margin-top:6px;" class="block-actions">' +
        (type !== 'action' ? '<button class="btn btn-outline-primary" style="font-size:.68rem;padding:1px 6px;" data-action="add-child">+ Child</button>' : '') +
        (type === 'condition' ? '<button class="btn btn-outline-warning" style="font-size:.68rem;padding:1px 6px;" data-action="add-else">+ Else</button>' : '') +
        '<button class="btn btn-outline-secondary" style="font-size:.68rem;padding:1px 6px;" data-action="configure"><i class="fas fa-sliders-h"></i></button>' +
      '</div>';

    blocksLayer.appendChild(el);

    blocks[id] = { el: el, data: { type: type, block_type: block_type, config: config || {} }, x: x, y: y, children: [], else_children: [], parentId: parentId || null, isElse: !!isElse };
    if (!rootId && type === 'trigger') rootId = id;

    // Link to parent
    if (parentId && blocks[parentId]) {
      if (isElse) blocks[parentId].else_children.push(id);
      else blocks[parentId].children.push(id);
    }

    // Drag
    el.addEventListener('mousedown', function (e) {
      if (e.target.dataset.action || e.target.closest('[data-action]')) return;
      dragState = { blockId: id, offsetX: e.clientX - x, offsetY: e.clientY - y };
      el.style.cursor = 'grabbing';
      el.style.zIndex = 100;
      e.preventDefault();
    });

    // Button actions
    el.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-action]');
      if (!btn) return;
      var action = btn.dataset.action;
      if (action === 'delete') _removeBlock(id);
      else if (action === 'add-child') _promptAddChild(id, false);
      else if (action === 'add-else') _promptAddChild(id, true);
      else if (action === 'configure') _openConfigModal(id);
    });

    _updateConfigSummary(id);
    _redrawLines();
    _resizeCanvas();
    return id;
  }

  /* ─── Drag handling ─── */
  document.addEventListener('mousemove', function (e) {
    if (!dragState) return;
    var b = blocks[dragState.blockId];
    if (!b) return;
    b.x = e.clientX - dragState.offsetX;
    b.y = e.clientY - dragState.offsetY;
    b.el.style.left = b.x + 'px';
    b.el.style.top = b.y + 'px';
    _redrawLines();
  });

  document.addEventListener('mouseup', function () {
    if (dragState && blocks[dragState.blockId]) {
      blocks[dragState.blockId].el.style.cursor = 'grab';
      blocks[dragState.blockId].el.style.zIndex = 10;
    }
    dragState = null;
  });

  /* ─── Remove block (and descendants) ─── */
  function _removeBlock(id) {
    var b = blocks[id];
    if (!b) return;
    // Remove from parent
    if (b.parentId && blocks[b.parentId]) {
      var parent = blocks[b.parentId];
      parent.children = parent.children.filter(function (c) { return c !== id; });
      parent.else_children = parent.else_children.filter(function (c) { return c !== id; });
    }
    // Remove descendants recursively
    (b.children.concat(b.else_children)).forEach(function (cid) { _removeBlock(cid); });
    b.el.remove();
    if (rootId === id) rootId = null;
    delete blocks[id];
    _redrawLines();
  }

  /* ─── Connector lines ─── */
  function _redrawLines() {
    while (linesLayer.firstChild) linesLayer.removeChild(linesLayer.firstChild);

    Object.keys(blocks).forEach(function (id) {
      var b = blocks[id];
      b.children.forEach(function (cid) { _drawLine(b, blocks[cid], '#0d6efd'); });
      b.else_children.forEach(function (cid) { _drawLine(b, blocks[cid], '#dc3545'); });
    });
  }

  function _drawLine(from, to, color) {
    if (!from || !to) return;
    var x1 = from.x + BLOCK_W / 2;
    var y1 = from.y + (from.el.offsetHeight || BLOCK_H);
    var x2 = to.x + BLOCK_W / 2;
    var y2 = to.y;

    var midY = (y1 + y2) / 2;
    var path = svgEl('path', {
      d: 'M' + x1 + ',' + y1 + ' C' + x1 + ',' + midY + ' ' + x2 + ',' + midY + ' ' + x2 + ',' + y2,
      stroke: color,
      'stroke-width': '2',
      fill: 'none',
      'marker-end': 'url(#arrowhead)',
    });
    linesLayer.appendChild(path);
  }

  // Arrowhead marker
  function _ensureArrowDef() {
    if (svg.querySelector('defs')) return;
    var defs = svgEl('defs');
    var marker = svgEl('marker', { id: 'arrowhead', markerWidth: '10', markerHeight: '7', refX: '10', refY: '3.5', orient: 'auto' });
    var poly = svgEl('polygon', { points: '0 0, 10 3.5, 0 7', fill: '#6c757d' });
    marker.appendChild(poly);
    defs.appendChild(marker);
    svg.insertBefore(defs, svg.firstChild);
  }

  /* ─── Auto-resize canvas ─── */
  function _resizeCanvas() {
    var maxX = 600, maxY = 500;
    Object.keys(blocks).forEach(function (id) {
      var b = blocks[id];
      if (b.x + BLOCK_W + 40 > maxX) maxX = b.x + BLOCK_W + 40;
      if (b.y + BLOCK_H + 80 > maxY) maxY = b.y + BLOCK_H + 80;
    });
    blocksLayer.style.minWidth = maxX + 'px';
    blocksLayer.style.minHeight = maxY + 'px';
    svg.setAttribute('width', maxX);
    svg.setAttribute('height', maxY);
  }

  /* ─── Prompt user to pick a child type ─── */
  function _promptAddChild(parentId, isElse) {
    var parentType = blocks[parentId].data.type;
    var options = [];
    if (parentType === 'trigger' || parentType === 'condition') {
      options = options.concat(
        CONDITIONS.map(function (c) { return { type: 'condition', block_type: c.block_type, label: c.label }; }),
        ACTIONS.map(function (a) { return { type: 'action', block_type: a.block_type, label: a.label }; })
      );
    } else {
      // Actions can chain to other actions only
      options = ACTIONS.map(function (a) { return { type: 'action', block_type: a.block_type, label: a.label }; });
    }

    // Simple dropdown picker via modal
    var html = '<div class="list-group" style="max-height:300px;overflow-y:auto;">';
    options.forEach(function (opt, i) {
      var col = COLORS[opt.type];
      html += '<button class="list-group-item list-group-item-action d-flex align-items-center gap-2" data-idx="' + i + '">' +
        '<span style="width:10px;height:10px;border-radius:50%;background:' + col.border + ';flex-shrink:0;"></span>' +
        '<span class="small">' + _esc(opt.label) + '</span>' +
        '<span class="badge ms-auto" style="background:' + col.bg + ';color:' + col.text + ';font-size:.68rem;">' + opt.type + '</span>' +
        '</button>';
    });
    html += '</div>';

    _showModal('Add ' + (isElse ? 'Else' : 'Child') + ' Block', html, null, function (modalEl) {
      modalEl.querySelectorAll('[data-idx]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var idx = parseInt(this.dataset.idx);
          var opt = options[idx];
          _addBlock(opt.type, opt.block_type, opt.label, {}, parentId, isElse);
          bootstrap.Modal.getInstance(modalEl).hide();
        });
      });
    });
  }

  /* ─── Config modal ─── */
  function _openConfigModal(id) {
    var b = blocks[id];
    if (!b) return;
    var config = b.data.config || {};

    var html = '<div class="mb-3">';
    html += '<label class="form-label fw-semibold small">Block Type</label>';
    html += '<input class="form-control form-control-sm" disabled value="' + _esc(b.data.block_type) + '">';
    html += '</div>';

    // Generic value field
    html += '<div class="mb-3">';
    html += '<label class="form-label fw-semibold small">Value</label>';
    html += '<input id="configValue" class="form-control form-control-sm" value="' + _esc(config.value || '') + '" placeholder="e.g. high, Review, assignee">';
    html += '</div>';

    // Operator (for conditions)
    if (b.data.type === 'condition') {
      html += '<div class="mb-3">';
      html += '<label class="form-label fw-semibold small">Operator</label>';
      html += '<select id="configOperator" class="form-select form-select-sm">';
      ['is', 'is_not', 'is_empty', 'is_not_empty'].forEach(function (op) {
        html += '<option value="' + op + '"' + (config.operator === op ? ' selected' : '') + '>' + op + '</option>';
      });
      html += '</select></div>';

      // Days field for due_date_within and stale_high_priority
      if (b.data.block_type === 'due_date_within' || b.data.block_type === 'stale_high_priority') {
        html += '<div class="mb-3"><label class="form-label fw-semibold small">Days</label>';
        html += '<input id="configDays" type="number" class="form-control form-control-sm" value="' + (config.days || config.days_stale || 3) + '" min="1">';
        html += '</div>';
      }
    }

    // Text field for create_comment
    if (b.data.block_type === 'create_comment') {
      html += '<div class="mb-3"><label class="form-label fw-semibold small">Comment text</label>';
      html += '<textarea id="configText" class="form-control form-control-sm" rows="2">' + _esc(config.text || '') + '</textarea>';
      html += '</div>';
    }

    _showModal('Configure: ' + _esc(b.data.block_type), html, function () {
      var newConfig = {};
      var valEl = document.getElementById('configValue');
      if (valEl) newConfig.value = valEl.value;
      var opEl = document.getElementById('configOperator');
      if (opEl) newConfig.operator = opEl.value;
      var daysEl = document.getElementById('configDays');
      if (daysEl) {
        if (b.data.block_type === 'stale_high_priority') newConfig.days_stale = daysEl.value;
        else newConfig.days = daysEl.value;
      }
      var textEl = document.getElementById('configText');
      if (textEl) newConfig.text = textEl.value;
      b.data.config = newConfig;
      _updateConfigSummary(id);
    });
  }

  function _updateConfigSummary(id) {
    var b = blocks[id];
    if (!b) return;
    var cfg = b.data.config || {};
    var parts = [];
    if (cfg.value) parts.push(cfg.value);
    if (cfg.operator && cfg.operator !== 'is') parts.push('(' + cfg.operator + ')');
    if (cfg.days) parts.push(cfg.days + ' days');
    if (cfg.days_stale) parts.push(cfg.days_stale + ' days stale');
    if (cfg.text) parts.push('"' + cfg.text.substring(0, 30) + '…"');
    var el = b.el.querySelector('.block-config-summary');
    if (el) el.textContent = parts.join(' · ') || '(click configure)';
  }

  /* ─── Generic modal helper ─── */
  function _showModal(title, bodyHtml, onSave, onShow) {
    // Remove any existing
    var old = document.getElementById('canvasModal');
    if (old) old.remove();

    var div = document.createElement('div');
    div.id = 'canvasModal';
    div.className = 'modal fade';
    div.tabIndex = -1;
    div.innerHTML =
      '<div class="modal-dialog modal-dialog-centered"><div class="modal-content" style="background:var(--card-bg);color:var(--text-primary);">' +
      '<div class="modal-header" style="border-color:var(--border-color);"><h5 class="modal-title">' + title + '</h5>' +
      '<button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>' +
      '<div class="modal-body">' + bodyHtml + '</div>' +
      (onSave ? '<div class="modal-footer" style="border-color:var(--border-color);"><button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button><button type="button" class="btn btn-primary" id="canvasModalSave">Save</button></div>' : '') +
      '</div></div>';
    document.body.appendChild(div);

    var modal = new bootstrap.Modal(div);
    if (onSave) {
      document.getElementById('canvasModalSave').addEventListener('click', function () {
        onSave();
        modal.hide();
      });
    }
    if (onShow) {
      div.addEventListener('shown.bs.modal', function () { onShow(div); });
    }
    modal.show();
    div.addEventListener('hidden.bs.modal', function () { div.remove(); });
  }

  /* ─── Build JSON tree from blocks ─── */
  function _buildTree(id) {
    var b = blocks[id];
    if (!b) return null;
    return {
      id: id,
      type: b.data.type,
      block_type: b.data.block_type,
      config: b.data.config || {},
      children: b.children.map(function (cid) { return _buildTree(cid); }).filter(Boolean),
      else_children: b.else_children.map(function (cid) { return _buildTree(cid); }).filter(Boolean),
    };
  }

  /* ─── Load JSON tree into blocks ─── */
  function _loadTree(node, parentId, isElse) {
    if (!node) return;
    var label = node.block_type;
    // Look up friendly label
    var palette = node.type === 'trigger' ? TRIGGERS : node.type === 'condition' ? CONDITIONS : ACTIONS;
    palette.forEach(function (p) { if (p.block_type === node.block_type) label = p.label; });

    var id = _addBlock(node.type, node.block_type, label, node.config || {}, parentId, isElse);
    // Override position-generated id with the one from JSON (preserves identity)
    if (node.id) {
      blocks[node.id] = blocks[id];
      blocks[node.id].el.dataset.blockId = node.id;
      if (parentId && blocks[parentId]) {
        if (isElse) {
          blocks[parentId].else_children = blocks[parentId].else_children.map(function (c) { return c === id ? node.id : c; });
        } else {
          blocks[parentId].children = blocks[parentId].children.map(function (c) { return c === id ? node.id : c; });
        }
      }
      if (rootId === id) rootId = node.id;
      if (id !== node.id) delete blocks[id];
      id = node.id;
    }

    (node.children || []).forEach(function (child) { _loadTree(child, id, false); });
    (node.else_children || []).forEach(function (child) { _loadTree(child, id, true); });
  }

  /* ─── Save rule_definition to server ─── */
  function _saveRule() {
    if (!rootId) {
      alert('Add at least one trigger block to save.');
      return;
    }
    var nameEl = document.getElementById('canvasRuleName');
    var name = nameEl ? nameEl.value.trim() : '';
    if (!name) { alert('Enter a rule name.'); return; }

    var tree = _buildTree(rootId);
    var rootData = blocks[rootId].data;

    var payload = {
      name: name,
      trigger_type: rootData.block_type,
      trigger_value: (rootData.config || {}).value || '',
      action_type: 'send_notification',
      action_value: '',
      rule_definition: tree,
    };

    // Try to find first action child for the flat action_type/action_value
    var firstAction = _findFirstAction(tree);
    if (firstAction) {
      payload.action_type = firstAction.block_type;
      payload.action_value = (firstAction.config || {}).value || '';
    }

    var url, method;
    if (ruleId) {
      url = '/boards/' + boardId + '/automations/rules/' + ruleId + '/update/';
      method = 'POST';
    } else {
      url = '/boards/' + boardId + '/automations/rules/create/';
      method = 'POST';
    }

    fetch(url, {
      method: method,
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.id) {
          ruleId = data.id;
          alert('Rule saved successfully!');
          location.reload();
        } else {
          alert('Error: ' + (data.error || 'Unknown error'));
        }
      })
      .catch(function (err) { alert('Save failed: ' + err.message); });
  }

  function _findFirstAction(node) {
    if (!node) return null;
    if (node.type === 'action') return node;
    for (var i = 0; i < (node.children || []).length; i++) {
      var found = _findFirstAction(node.children[i]);
      if (found) return found;
    }
    for (var j = 0; j < (node.else_children || []).length; j++) {
      var f2 = _findFirstAction(node.else_children[j]);
      if (f2) return f2;
    }
    return null;
  }

  /* ─── Close canvas ─── */
  function _closeCanvas() {
    location.reload();
  }

  /* ─── Load existing rule into canvas ─── */
  function loadRule(bid, rid) {
    boardId = bid;
    ruleId = rid;
    fetch('/boards/' + bid + '/automations/rules/' + rid + '/', {
      headers: { 'Accept': 'application/json' },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        ruleName = data.name || '';
        var nameEl = document.getElementById('canvasRuleName');
        if (nameEl) nameEl.value = ruleName;
        if (data.rule_definition) {
          _loadTree(data.rule_definition, null, false);
          _autoLayout();
        }
      })
      .catch(function (err) { console.error('Failed to load rule:', err); });
  }

  /* ─── Auto-layout blocks top-down ─── */
  function _autoLayout() {
    if (!rootId) return;
    _layoutNode(rootId, 60, 60);
    _redrawLines();
    _resizeCanvas();
  }

  var _layoutMaxX = 0;
  function _layoutNode(id, x, y) {
    var b = blocks[id];
    if (!b) return y;
    b.x = x; b.y = y;
    b.el.style.left = x + 'px';
    b.el.style.top = y + 'px';

    var nextY = y + BLOCK_H + GAP_Y;
    b.children.forEach(function (cid) {
      nextY = _layoutNode(cid, x, nextY);
    });
    var elseX = x + GAP_X;
    b.else_children.forEach(function (cid) {
      nextY = _layoutNode(cid, elseX, y + BLOCK_H + GAP_Y);
    });
    return nextY;
  }

  /* ─── Load template rule_definition into canvas ─── */
  function loadTemplate(bid, templateRuleDef, templateName) {
    boardId = bid;
    ruleId = null;
    ruleName = templateName || '';
    var nameEl = document.getElementById('canvasRuleName');
    if (nameEl) nameEl.value = ruleName;
    if (templateRuleDef) {
      _loadTree(templateRuleDef, null, false);
      _autoLayout();
    }
  }

  /* ─── Escape HTML ─── */
  function _esc(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  /* ─── Public API ─── */
  window.AutomationBuilder = {
    init: function (canvasEl, bid) {
      init(canvasEl, bid);
      _ensureArrowDef();
    },
    loadRule: loadRule,
    loadTemplate: loadTemplate,
  };
})();
