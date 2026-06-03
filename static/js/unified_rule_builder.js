/**
 * Unified Rule Builder — PrizmAI Automation Engine
 * Manages the WHEN / IF / THEN / OTHERWISE modal form.
 */
'use strict';

const UnifiedRuleBuilder = (() => {

  // ─── State ───────────────────────────────────────────────────────────────

  let state = {
    boardId: null,
    ruleId: null,        // null = create, integer = edit
    trigger: '',
    triggerConfig: {},
    conditionLogic: 'AND',
    conditions: [],      // [{attribute, operator, value}]
    actions: [],         // [{type, target, message}]
    otherwiseActions: [], // same format
    otherwiseExpanded: false,
  };

  let boardData = { members: [], columns: [], labels: [] };

  // ─── Trigger display map ─────────────────────────────────────────────────

  // ─── Trigger / Attribute / Action labels ─────────────────────────────────
  // Grouped per the seven-group UI taxonomy (Task State / Time & Activity /
  // AI & Risk / Hierarchy & Dependencies / AI Tools & Platform /
  // Communications / Scheduled). The render code flattens these for label
  // lookup but the template renders <optgroup> blocks from the groups.

  const TRIGGER_GROUPS = {
    'Task State': {
      task_created:              'Task is created',
      task_completed:            'Task is completed',
      task_assigned:             'Task is assigned',
      task_unassigned:           'Task is unassigned',
      task_moved_to_column:      'Task is moved to a column',
      task_status_changed:       'Task status (column) changed',
      task_priority_changed:     'Task priority changes',
      task_progress_changed:     'Task progress changed',
      task_description_updated:  'Task description updated',
      task_due_date_changed:     'Task due date changed',
      task_label_added:          'Task label added',
    },
    'Time & Activity': {
      task_overdue:              'Task becomes overdue',
      task_idle:                 'Task is idle (no updates for N days)',
      task_start_date_reached:   'Task start date reached',
      task_completion_threshold: 'Completion threshold reached',
      due_date_approaching:      'Due date is approaching',
    },
    'AI & Risk': {
      risk_level_changed:        'Risk level changed',
      risk_level_critical:       'Risk level becomes critical',
      predicted_late:            'Predicted to miss due date',
      schedule_status_changed:   'Schedule status changed',
      complexity_increased:      'Complexity increased',
    },
    'Hierarchy & Dependencies': {
      subtask_completed:         'A subtask completed',
      all_subtasks_completed:    'All subtasks completed',
      dependency_completed:      'A blocking dependency completed',
      dependency_overdue:        'A blocking dependency became overdue',
      checklist_completed:       'Checklist fully completed',
      checklist_item_added:      'Checklist item added',
      milestone_reached:         'Milestone reached',
      parent_status_changed:     'Parent task status changed',
    },
    'AI Tools & Platform': {
      coach_suggestion_created:  'AI Coach suggestion created',
      conflict_detected:         'Conflict detected',
      discovery_idea_scored:     'Discovery idea AI-scored',
      discovery_idea_submitted:  'Discovery idea submitted',
      immunity_score_dropped:    'Immunity score dropped',
      hospice_risk_triggered:    'Hospice risk threshold reached',
      scope_creep_detected:      'Scope creep detected',
      prediction_confidence_dropped: 'Prediction confidence dropped',
      retrospective_finalized:   'Retrospective finalized',
    },
    'Communications': {
      comment_added:             'Comment added to a task',
      mention_received:          'Assignee was @-mentioned',
      attachment_added:          'Attachment added to a task',
      task_thread_message:       'Task thread message posted',
    },
    'Scheduled': {
      scheduled_daily:           'Every day at a set time',
      scheduled_weekly:          'Every week on a set day',
      scheduled_monthly:         'Every month on a set date',
    },
  };

  const ACTION_GROUPS = {
    'Task State': {
      set_priority:             'Set priority',
      set_progress:             'Set progress %',
      set_description:          'Set description',
      append_to_description:    'Append to description',
      add_label:                'Add label',
      remove_label:             'Remove label',
      assign_to_user:           'Assign to user',
      clear_assignee:           'Clear assignee',
      move_to_column:           'Move to column',
      set_due_date:             'Set due date',
      set_start_date:           'Set start date',
      clear_due_date:           'Clear due date',
      close_task:               'Close task',
    },
    'AI & Risk': {
      set_risk_level:           'Set risk level',
      request_ai_analysis:      'Request AI analysis',
      flag_for_review:          'Flag for review',
      add_risk_indicator:       'Add risk indicator',
      add_mitigation_strategy:  'Add mitigation strategy',
    },
    'Hierarchy & Dependencies': {
      cascade_due_date:         'Cascade due date to subtasks',
      cascade_priority:         'Cascade priority to subtasks',
      assign_subtasks_to:       'Assign all subtasks',
      complete_parent_if_all_subtasks_done: 'Complete parent if all subtasks done',
      notify_blocked_tasks:     'Notify tasks blocked by this one',
      auto_check_checklist:     'Auto-check a checklist item',
      add_checklist_item:       'Add a checklist item',
      add_subtask:              'Add a subtask',
    },
    'Resources & Workload': {
      set_workload_impact:      'Set workload impact',
      set_estimated_hours:      'Set estimated hours',
      set_estimated_cost:       'Set estimated cost',
      assign_to_best_skill_match: 'Assign to best skill match',
      assign_to_lightest_workload: 'Assign to lightest workload',
      add_required_skill:       'Add required skill',
      escalate_to_owner:        'Escalate to board owner',
    },
    'AI Tools & Platform': {
      acknowledge_coach_suggestion: 'Acknowledge coach suggestion',
      resolve_conflict:         'Mark conflict resolved',
      promote_discovery_idea:   'Promote discovery idea to task',
      apply_stress_test_vaccine: 'Apply stress-test vaccine',
      create_memory_node:       'Create memory-graph node',
      generate_status_report:   'Generate PrizmBrief status report',
      add_stakeholder_engagement: 'Log stakeholder engagement',
    },
    'Communications & Memory': {
      send_notification:        'Send notification',
      notify_stakeholders:      'Notify all stakeholders',
      mention_users_in_comment: 'Mention users in a comment',
      start_task_thread:        'Start a task thread',
      link_wiki_page:           'Link an existing wiki page',
      create_wiki_page:         'Create a new wiki page',
      capture_decision:         'Capture decision as memory node',
      capture_lesson:           'Capture lesson as memory node',
      post_comment:             'Post a comment',
      log_time_entry:           'Log time entry',
    },
  };

  const ATTRIBUTE_GROUPS = {
    'Task State': {
      priority:           'Priority',
      assignee:           'Assignee',
      created_by:         'Created by',
      status:             'Status (column)',
      column:             'Column',
      label:              'Label',
      title:              'Title',
      description:        'Description',
      progress:           'Progress',
      checklist_progress: 'Checklist progress',
      has_comments:       'Has comments',
      has_attachments:    'Has attachments',
    },
    'Time & Activity': {
      due_date:           'Due date',
      start_date:         'Start date',
      idle_days:          'Idle days',
      time_in_column:     'Time in column',
      stale_high_priority:'Stale high-priority',
    },
    'AI & Risk': {
      risk_level:         'Risk level',
      risk_score:         'Risk score',
      predicted_completion: 'Predicted completion',
      prediction_confidence: 'Prediction confidence',
      complexity_score:   'Complexity score',
      schedule_status:    'Schedule status',
      lss_classification: 'LSS classification',
      ai_risk_score:      'AI risk score',
    },
    'Hierarchy & Dependencies': {
      all_subtasks_done:  'All subtasks done',
      parent_status:      'Parent status',
      subtask_count:      'Subtask count',
      subtask_completion_pct: 'Subtask completion %',
      has_dependencies:   'Has dependencies',
      has_blocked_tasks:  'Has blocked tasks',
      dependency_status:  'Dependency status',
      item_type:          'Item type',
      phase:              'Phase',
      is_root_task:       'Is root task',
    },
    'Resources & Workload': {
      workload_impact:    'Workload impact',
      skill_match_score:  'Skill match score',
      required_skills:    'Required skills',
      collaboration_required: 'Collaboration required',
      estimated_cost:     'Estimated cost',
      estimated_hours:    'Estimated hours',
      hours_logged:       'Hours logged',
      cost_variance_pct:  'Cost variance %',
      assignee_workload:  'Assignee workload',
    },
    'AI Tools & Platform': {
      board_has_active_conflicts: 'Board has active conflicts',
      board_immunity_score: 'Board immunity score',
      board_scope_creep_pct: 'Board scope creep %',
      board_velocity_trend: 'Board velocity trend',
      board_predicted_overrun_days: 'Board predicted overrun (days)',
    },
  };

  // Flattened lookups built once for label rendering (preview, edit views).
  const TRIGGER_LABELS = Object.assign({}, ...Object.values(TRIGGER_GROUPS));
  const ACTION_LABELS  = Object.assign({}, ...Object.values(ACTION_GROUPS));
  const ATTRIBUTE_LABELS = Object.assign({}, ...Object.values(ATTRIBUTE_GROUPS));

  // ─── Init ────────────────────────────────────────────────────────────────

  function init(boardId) {
    state.boardId = boardId;
    _bindStaticEvents();
  }

  function _bindStaticEvents() {
    // + New Rule button
    document.addEventListener('click', e => {
      if (e.target.closest('[data-action="open-builder"]')) {
        const btn = e.target.closest('[data-action="open-builder"]');
        const ruleId = btn.dataset.ruleId ? parseInt(btn.dataset.ruleId) : null;
        open(ruleId);
      }
      if (e.target.closest('[data-action="duplicate-rule"]')) {
        const btn = e.target.closest('[data-action="duplicate-rule"]');
        duplicateRule(parseInt(btn.dataset.ruleId));
      }
      if (e.target.closest('[data-action="delete-rule"]')) {
        const btn = e.target.closest('[data-action="delete-rule"]');
        deleteRule(parseInt(btn.dataset.ruleId), btn.dataset.ruleName);
      }
      if (e.target.closest('[data-action="toggle-rule"]')) {
        const btn = e.target.closest('[data-action="toggle-rule"]');
        toggleRule(parseInt(btn.dataset.ruleId));
      }
    });

    // Save & activate
    const saveBtn = document.getElementById('rbSaveBtn');
    if (saveBtn) saveBtn.addEventListener('click', save);

    // Cancel
    const cancelBtn = document.getElementById('rbCancelBtn');
    if (cancelBtn) cancelBtn.addEventListener('click', close);
  }

  // ─── Open / close ────────────────────────────────────────────────────────

  async function open(ruleId = null) {
    state.ruleId = ruleId;
    reset();

    // Load board data (members, columns, labels)
    try {
      const resp = await fetch(`/boards/${state.boardId}/automations/builder-data/`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (resp.ok) boardData = await resp.json();
    } catch (_) {}

    const modal = document.getElementById('ruleBuilderModal');
    if (!modal) return;

    // Set modal title
    modal.querySelector('#rbModalTitle').textContent =
      ruleId ? 'Edit automation rule' : 'Create automation rule';

    // If editing, load rule data
    if (ruleId) {
      try {
        const resp = await fetch(
          `/boards/${state.boardId}/automations/rules/${ruleId}/`,
          { headers: { 'X-Requested-With': 'XMLHttpRequest' } }
        );
        if (resp.ok) {
          const rule = await resp.json();
          _loadRule(rule);
        }
      } catch (_) {}
    }

    _renderAll();
    bootstrap.Modal.getOrCreateInstance(modal).show();
  }

  function close() {
    const modal = document.getElementById('ruleBuilderModal');
    if (modal) bootstrap.Modal.getInstance(modal)?.hide();
  }

  function reset() {
    state.trigger = '';
    state.triggerConfig = {};
    state.conditionLogic = 'AND';
    state.conditions = [];
    state.actions = [{ type: '', target: '', message: '' }];
    state.otherwiseActions = [];
    state.otherwiseExpanded = false;
    document.getElementById('rbRuleName').value = '';
    _clearErrors();
  }

  function _loadRule(rule) {
    document.getElementById('rbRuleName').value = rule.name || '';
    state.trigger = rule.trigger_type || '';
    state.triggerConfig = rule.trigger_config || {};
    state.conditionLogic = rule.condition_logic || 'AND';
    state.conditions = rule.conditions ? [...rule.conditions] : [];
    state.actions = rule.actions && rule.actions.length
      ? [...rule.actions]
      : [{ type: '', target: '', message: '' }];
    state.otherwiseActions = rule.otherwise_actions ? [...rule.otherwise_actions] : [];
    state.otherwiseExpanded = state.otherwiseActions.length > 0;
  }

  // ─── Render all sections ─────────────────────────────────────────────────

  function _renderAll() {
    _renderTrigger();
    _renderConditions();
    _renderActions('then');
    _renderActions('otherwise');
    _renderOtherwiseHeader();
    _renderLogicToggle();
    updatePreview();
  }

  // ─── WHEN section ────────────────────────────────────────────────────────

  function _renderTrigger() {
    const sel = document.getElementById('rbTriggerSelect');
    if (!sel) return;
    sel.value = state.trigger;

    const desc = document.getElementById('rbTriggerDesc');
    if (desc) {
      if (state.trigger && TRIGGER_LABELS[state.trigger]) {
        desc.textContent = `Rule fires: ${TRIGGER_LABELS[state.trigger].toLowerCase()}`;
        desc.style.display = '';
      } else {
        desc.style.display = 'none';
      }
    }

    _renderTriggerSubFields();
  }

  function _renderTriggerSubFields() {
    const container = document.getElementById('rbTriggerSubFields');
    if (!container) return;
    container.innerHTML = '';

    const tt = state.trigger;
    const cfg = state.triggerConfig;

    if (tt === 'task_moved_to_column') {
      container.innerHTML = `
        <div class="mt-2">
          <label class="form-label small">To column</label>
          <select class="form-select form-select-sm" id="rbTrigSubColumn">
            <option value="">Any column</option>
            ${boardData.columns.map(c =>
              `<option value="${_esc(c.name)}" ${cfg.column_name === c.name ? 'selected' : ''}>${_esc(c.name)}</option>`
            ).join('')}
          </select>
        </div>`;
      document.getElementById('rbTrigSubColumn').addEventListener('change', e => {
        state.triggerConfig.column_name = e.target.value;
        updatePreview();
      });

    } else if (tt === 'task_completion_threshold') {
      const thresholds = [25, 50, 75, 100];
      container.innerHTML = `
        <div class="mt-2">
          <label class="form-label small">When</label>
          <select class="form-select form-select-sm" id="rbTrigSubThreshold">
            ${thresholds.map(v =>
              `<option value="${v}" ${(cfg.threshold || 100) == v ? 'selected' : ''}>${v}%</option>`
            ).join('')}
          </select>
        </div>`;
      document.getElementById('rbTrigSubThreshold').addEventListener('change', e => {
        state.triggerConfig.threshold = parseInt(e.target.value);
        updatePreview();
      });

    } else if (tt === 'due_date_approaching') {
      container.innerHTML = `
        <div class="mt-2 d-flex align-items-center gap-2">
          <label class="form-label small mb-0">Within</label>
          <input type="number" class="form-control form-control-sm" id="rbTrigSubDays"
            min="1" max="30" value="${cfg.days || 2}" style="width:80px">
          <span class="small">days</span>
        </div>`;
      document.getElementById('rbTrigSubDays').addEventListener('input', e => {
        state.triggerConfig.days = parseInt(e.target.value) || 2;
        updatePreview();
      });

    } else if (tt === 'scheduled_daily') {
      container.innerHTML = `
        <div class="mt-2 d-flex align-items-center gap-2">
          <label class="form-label small mb-0">At</label>
          <input type="time" class="form-control form-control-sm" id="rbTrigSubTime"
            value="${cfg.time || '09:00'}" style="width:130px">
        </div>`;
      document.getElementById('rbTrigSubTime').addEventListener('change', e => {
        state.triggerConfig.time = e.target.value;
        updatePreview();
      });

    } else if (tt === 'scheduled_weekly') {
      const days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
      container.innerHTML = `
        <div class="mt-2 d-flex align-items-center gap-2 flex-wrap">
          <label class="form-label small mb-0">On</label>
          <select class="form-select form-select-sm" id="rbTrigSubDay" style="width:140px">
            ${days.map(d =>
              `<option value="${d}" ${cfg.day === d ? 'selected' : ''}>${d}</option>`
            ).join('')}
          </select>
          <label class="form-label small mb-0">at</label>
          <input type="time" class="form-control form-control-sm" id="rbTrigSubTime"
            value="${cfg.time || '09:00'}" style="width:130px">
        </div>`;
      document.getElementById('rbTrigSubDay').addEventListener('change', e => {
        state.triggerConfig.day = e.target.value; updatePreview();
      });
      document.getElementById('rbTrigSubTime').addEventListener('change', e => {
        state.triggerConfig.time = e.target.value; updatePreview();
      });

    } else if (tt === 'task_status_changed') {
      container.innerHTML = `
        <div class="mt-2 d-flex align-items-center gap-2 flex-wrap">
          <label class="form-label small mb-0">From</label>
          <select class="form-select form-select-sm" id="rbTrigSubFrom" style="width:160px">
            <option value="">Any column</option>
            ${boardData.columns.map(c =>
              `<option value="${_esc(c.name)}" ${cfg.from === c.name ? 'selected' : ''}>${_esc(c.name)}</option>`
            ).join('')}
          </select>
          <label class="form-label small mb-0">to</label>
          <select class="form-select form-select-sm" id="rbTrigSubTo" style="width:160px">
            <option value="">Any column</option>
            ${boardData.columns.map(c =>
              `<option value="${_esc(c.name)}" ${cfg.to === c.name ? 'selected' : ''}>${_esc(c.name)}</option>`
            ).join('')}
          </select>
        </div>`;
      document.getElementById('rbTrigSubFrom').addEventListener('change', e => {
        state.triggerConfig.from = e.target.value; updatePreview();
      });
      document.getElementById('rbTrigSubTo').addEventListener('change', e => {
        state.triggerConfig.to = e.target.value; updatePreview();
      });

    } else if (tt === 'task_idle') {
      container.innerHTML = `
        <div class="mt-2 d-flex align-items-center gap-2">
          <label class="form-label small mb-0">Idle for</label>
          <input type="number" class="form-control form-control-sm" id="rbTrigSubIdleDays"
            min="1" max="365" value="${cfg.idle_days || 7}" style="width:80px">
          <span class="small">days</span>
        </div>`;
      document.getElementById('rbTrigSubIdleDays').addEventListener('input', e => {
        state.triggerConfig.idle_days = parseInt(e.target.value) || 7;
        updatePreview();
      });

    } else if (tt === 'task_label_added') {
      const opts = (boardData.labels || []).map(l =>
        `<option value="${_esc(l.name)}" ${cfg.label_name === l.name ? 'selected' : ''}>${_esc(l.name)}</option>`
      ).join('');
      container.innerHTML = `
        <div class="mt-2">
          <label class="form-label small">When this label is added</label>
          <select class="form-select form-select-sm" id="rbTrigSubLabel">
            <option value="">Any label</option>
            ${opts}
          </select>
        </div>`;
      document.getElementById('rbTrigSubLabel').addEventListener('change', e => {
        state.triggerConfig.label_name = e.target.value;
        updatePreview();
      });

    } else if (tt === 'scheduled_monthly') {
      container.innerHTML = `
        <div class="mt-2 d-flex align-items-center gap-2 flex-wrap">
          <label class="form-label small mb-0">On day</label>
          <input type="number" class="form-control form-control-sm" id="rbTrigSubDom"
            min="1" max="31" value="${cfg.day_of_month || 1}" style="width:80px">
          <label class="form-label small mb-0">at</label>
          <input type="time" class="form-control form-control-sm" id="rbTrigSubTime"
            value="${cfg.time || '09:00'}" style="width:130px">
        </div>`;
      document.getElementById('rbTrigSubDom').addEventListener('input', e => {
        state.triggerConfig.day_of_month = parseInt(e.target.value) || 1; updatePreview();
      });
      document.getElementById('rbTrigSubTime').addEventListener('change', e => {
        state.triggerConfig.time = e.target.value; updatePreview();
      });
    }
  }

  // ─── IF section ──────────────────────────────────────────────────────────

  function _renderConditions() {
    const container = document.getElementById('rbConditionsBody');
    if (!container) return;

    if (state.conditions.length === 0) {
      container.innerHTML = `
        <p class="text-muted small mb-2" id="rbNoConditions">
          No conditions added. The rule will fire for all tasks matching the trigger.
        </p>`;
    } else {
      container.innerHTML = '';
      state.conditions.forEach((cond, idx) => {
        if (idx > 0) {
          const sep = document.createElement('div');
          sep.className = 'condition-separator text-muted small';
          sep.dataset.sepIdx = idx;
          sep.textContent = `─── ${state.conditionLogic} ───`;
          container.appendChild(sep);
        }
        container.insertAdjacentHTML('beforeend', _conditionRowHtml(cond, idx));
        _bindConditionRow(idx);
      });
    }

    // + Add condition button
    let addBtn = document.getElementById('rbAddCondition');
    if (!addBtn) {
      addBtn = document.createElement('button');
      addBtn.type = 'button';
      addBtn.id = 'rbAddCondition';
      addBtn.className = 'btn btn-sm btn-outline-secondary mt-2';
      addBtn.innerHTML = '<i class="fas fa-plus me-1"></i>Add condition';
      addBtn.addEventListener('click', addCondition);
      container.after(addBtn);
    }
  }

  function _renderGroupedOptions(groups, selectedValue) {
    // Emits one <optgroup> block per group, with the entries inside each group.
    // ``groups`` is an object: { 'Group Name': { value: label, ... }, ... }.
    return Object.entries(groups).map(([groupName, entries]) => {
      const options = Object.entries(entries).map(([v, l]) =>
        `<option value="${v}" ${selectedValue === v ? 'selected' : ''}>${l}</option>`
      ).join('');
      if (!options) return '';
      return `<optgroup label="${_esc(groupName)}">${options}</optgroup>`;
    }).join('');
  }

  function _conditionRowHtml(cond, idx) {
    const attributes = _renderGroupedOptions(ATTRIBUTE_GROUPS, cond.attribute);

    const operators = _operatorsFor(cond.attribute).map(([v, l]) =>
      `<option value="${v}" ${cond.operator === v ? 'selected' : ''}>${l}</option>`
    ).join('');

    const valueHtml = _conditionValueHtml(cond, idx);

    return `
      <div class="d-flex align-items-center gap-2 mb-2 flex-wrap condition-row" data-idx="${idx}">
        <select class="form-select form-select-sm" style="max-width:160px"
          id="rbCondAttr_${idx}" aria-label="Condition attribute">
          <option value="">Select attribute</option>
          ${attributes}
        </select>
        <select class="form-select form-select-sm" style="max-width:160px"
          id="rbCondOp_${idx}" aria-label="Condition operator">
          ${operators}
        </select>
        <span id="rbCondValueWrap_${idx}">${valueHtml}</span>
        <button type="button" class="btn btn-sm btn-outline-danger"
          aria-label="Remove condition" onclick="UnifiedRuleBuilder.removeCondition(${idx})">
          <i class="fas fa-times"></i>
        </button>
      </div>`;
  }

  function _operatorsFor(attribute) {
    const IS_ISNOT_EMPTY = [['is','is'],['is_not','is not'],['is_empty','is empty'],['is_not_empty','is not empty']];
    const GTE_LTE = [['gte','≥'],['lte','≤'],['equals','=']];
    const BOOL = [['is_true','is true'],['is_false','is false']];
    const TEXT = [['contains','contains'],['does_not_contain','does not contain'],['is_empty','is empty'],['is_not_empty','is not empty']];

    const map = {
      // Phase 1a
      priority:           IS_ISNOT_EMPTY,
      assignee:           IS_ISNOT_EMPTY,
      column:             [['is','is'],['is_not','is not']],
      label:              [['has','has'],['does_not_have','does not have'],['is_empty','is empty'],['is_not_empty','is not empty']],
      due_date:           [['within_days','is due within next N days'],['is_overdue','is overdue'],['is_empty','is empty'],['is_not_empty','is not empty']],
      progress:           GTE_LTE,
      all_subtasks_done:  BOOL,
      stale_high_priority:BOOL,
      // Phase 1b — task fields
      status:             [['is','is'],['is_not','is not']],
      created_by:         IS_ISNOT_EMPTY,
      start_date:         [['is_past','is in the past'],['is_today','is today'],['within_days','starts within next N days'],['is_empty','is empty'],['is_not_empty','is not empty']],
      description:        TEXT,
      title:              [['contains','contains'],['does_not_contain','does not contain']],
      checklist_progress: GTE_LTE,
      has_comments:       [['is_true','any'],['is_false','none'],['count_gte','count ≥'],['count_lte','count ≤']],
      has_attachments:    BOOL,
      idle_days:          [['gte','≥'],['lte','≤']],
      time_in_column:     [['gte','≥'],['lte','≤']],
      // Phase 2 — risk & AI
      risk_level:         [['is','is'],['is_not','is not'],['is_at_least','is at least']],
      risk_score:         GTE_LTE,
      predicted_completion: [['before_due','before due'],['after_due','after due'],['within_days_of_due','within N days of due']],
      prediction_confidence: [['gte','≥'],['lte','≤']],
      complexity_score:   GTE_LTE,
      schedule_status:    [['is','is']],
      lss_classification: [['is','is'],['is_not','is not']],
      ai_risk_score:      [['gte','≥'],['lte','≤']],
      // Phase 3 — hierarchy
      parent_status:      [['is','is'],['is_not','is not']],
      subtask_count:      GTE_LTE,
      subtask_completion_pct: [['gte','≥'],['lte','≤']],
      has_dependencies:   BOOL,
      has_blocked_tasks:  BOOL,
      dependency_status:  [['all_complete','all complete'],['any_overdue','any overdue'],['any_blocked','any blocked']],
      item_type:          [['is','is']],
      phase:              [['is','is'],['is_not','is not']],
      is_root_task:       BOOL,
      // Phase 4 — resource & cost
      workload_impact:    [['is','is'],['is_at_least','is at least']],
      skill_match_score:  [['gte','≥'],['lte','≤']],
      required_skills:    [['contains','contains'],['count_gte','count ≥'],['is_empty','is empty']],
      collaboration_required: BOOL,
      estimated_cost:     [['gte','≥'],['lte','≤']],
      estimated_hours:    [['gte','≥'],['lte','≤']],
      hours_logged:       [['gte','≥'],['lte','≤']],
      cost_variance_pct:  [['gte','≥'],['lte','≤']],
      assignee_workload:  [['gte','≥'],['lte','≤']],
      // Phase 5 — board-scoped
      board_has_active_conflicts: [['is_true','any'],['count_gte','count ≥']],
      board_immunity_score: [['gte','≥'],['lte','≤']],
      board_scope_creep_pct: [['gte','≥'],['lte','≤']],
      board_velocity_trend: [['is','is']],
      board_predicted_overrun_days: [['gte','≥']],
    };
    return map[attribute] || [['is','is'],['is_not','is not']];
  }

  function _conditionValueHtml(cond, idx) {
    const op = cond.operator || '';
    const attr = cond.attribute || '';
    const NO_VALUE_OPS = ['is_empty','is_not_empty','is_true','is_false','is_overdue','is_past','is_today'];

    if (!attr || NO_VALUE_OPS.includes(op)) return '';

    if (attr === 'priority') {
      return `<select class="form-select form-select-sm" style="max-width:140px" id="rbCondVal_${idx}" aria-label="Condition value">
        ${['Urgent','High','Medium','Low'].map(p =>
          `<option value="${p}" ${cond.value === p ? 'selected':''}>${p}</option>`).join('')}
      </select>`;
    }
    if (attr === 'assignee') {
      return `<select class="form-select form-select-sm" style="max-width:180px" id="rbCondVal_${idx}" aria-label="Condition value">
        <option value="">Select member</option>
        <option value="none" ${cond.value === 'none' ? 'selected':''}>None (Unassigned)</option>
        ${boardData.members.map(m =>
          `<option value="${m.id}" ${cond.value == m.id ? 'selected':''}>${_esc(m.username)}</option>`).join('')}
      </select>`;
    }
    if (attr === 'column' || attr === 'status') {
      return `<select class="form-select form-select-sm" style="max-width:180px" id="rbCondVal_${idx}" aria-label="Condition value">
        <option value="">Select column</option>
        ${boardData.columns.map(c =>
          `<option value="${_esc(c.name)}" ${cond.value === c.name ? 'selected':''}>${_esc(c.name)}</option>`).join('')}
      </select>`;
    }
    if (attr === 'label') {
      const labelOpts = (boardData.labels || []).map(l =>
        `<option value="${_esc(l.name)}" ${cond.value === l.name ? 'selected':''}>${_esc(l.name)}</option>`
      ).join('');
      return `<select class="form-select form-select-sm" style="max-width:180px" id="rbCondVal_${idx}" aria-label="Condition value">
        <option value="">Select label</option>
        ${labelOpts}
      </select>`;
    }
    if (attr === 'due_date' && op === 'within_days') {
      return `<input type="number" class="form-control form-control-sm" id="rbCondVal_${idx}"
        min="1" max="30" style="width:80px" value="${cond.value||2}" aria-label="Days"> <span class="small">days</span>`;
    }
    if (attr === 'start_date' && op === 'within_days') {
      return `<input type="number" class="form-control form-control-sm" id="rbCondVal_${idx}"
        min="1" max="30" style="width:80px" value="${cond.value||2}" aria-label="Days"> <span class="small">days</span>`;
    }
    if (attr === 'progress' || attr === 'checklist_progress') {
      return `<div class="input-group input-group-sm" style="width:110px">
        <input type="number" class="form-control form-control-sm" id="rbCondVal_${idx}"
          min="0" max="100" value="${cond.value||0}" aria-label="Progress %">
        <span class="input-group-text">%</span>
      </div>`;
    }
    if (attr === 'idle_days' || attr === 'time_in_column') {
      return `<div class="input-group input-group-sm" style="width:110px">
        <input type="number" class="form-control form-control-sm" id="rbCondVal_${idx}"
          min="1" max="365" value="${cond.value||1}" aria-label="Days">
        <span class="input-group-text">days</span>
      </div>`;
    }
    if (attr === 'description' || attr === 'title') {
      return `<input type="text" class="form-control form-control-sm" id="rbCondVal_${idx}"
        style="max-width:240px" placeholder="Text to match"
        value="${_esc(cond.value||'')}" aria-label="Condition value">`;
    }
    if (attr === 'created_by') {
      return `<select class="form-select form-select-sm" style="max-width:180px" id="rbCondVal_${idx}" aria-label="Condition value">
        <option value="">Select member</option>
        ${boardData.members.map(m =>
          `<option value="${m.id}" ${cond.value == m.id ? 'selected':''}>${_esc(m.username)}</option>`).join('')}
      </select>`;
    }
    if (attr === 'has_comments' && (op === 'count_gte' || op === 'count_lte')) {
      return `<input type="number" class="form-control form-control-sm" id="rbCondVal_${idx}"
        min="0" max="999" style="width:80px" value="${cond.value||1}" aria-label="Comment count">`;
    }
    // Generic numeric/text fallback so any attribute requiring a value still
    // renders an editable control instead of silently leaving the row blank.
    return `<input type="text" class="form-control form-control-sm" id="rbCondVal_${idx}"
      style="max-width:200px" placeholder="Value"
      value="${_esc(cond.value||'')}" aria-label="Condition value">`;
  }

  function _bindConditionRow(idx) {
    const attrSel = document.getElementById(`rbCondAttr_${idx}`);
    const opSel   = document.getElementById(`rbCondOp_${idx}`);

    if (attrSel) {
      attrSel.addEventListener('change', e => {
        state.conditions[idx].attribute = e.target.value;
        state.conditions[idx].operator = '';
        state.conditions[idx].value = null;
        _renderConditions();
        updatePreview();
      });
    }
    if (opSel) {
      // Sync state with the rendered operator dropdown — first option shows as
      // selected without firing a change event.
      if (!state.conditions[idx].operator && opSel.value) {
        state.conditions[idx].operator = opSel.value;
      }
      opSel.addEventListener('change', e => {
        state.conditions[idx].operator = e.target.value;
        state.conditions[idx].value = null;
        _renderConditionValue(idx);
        updatePreview();
      });
    }
    _bindConditionValue(idx);
  }

  function _renderConditionValue(idx) {
    const wrap = document.getElementById(`rbCondValueWrap_${idx}`);
    if (wrap) {
      wrap.innerHTML = _conditionValueHtml(state.conditions[idx], idx);
      _bindConditionValue(idx);
    }
  }

  function _bindConditionValue(idx) {
    const valEl = document.getElementById(`rbCondVal_${idx}`);
    if (valEl) {
      // Same sync-on-render trick as actions: a SELECT without an explicit
      // `selected` option visually shows option 0, but the change event never
      // fires, leaving state.value as null.
      if (valEl.tagName === 'SELECT' && state.conditions[idx].value == null && valEl.value) {
        state.conditions[idx].value = valEl.value;
      }
      valEl.addEventListener('change', e => {
        state.conditions[idx].value = e.target.value || null;
        updatePreview();
      });
      valEl.addEventListener('input', e => {
        state.conditions[idx].value = e.target.value || null;
        updatePreview();
      });
    }
  }

  function addCondition() {
    state.conditions.push({ attribute: '', operator: 'is', value: null });
    _renderConditions();
    updatePreview();
  }

  function removeCondition(idx) {
    state.conditions.splice(idx, 1);
    _renderConditions();
    updatePreview();
  }

  function _renderLogicToggle() {
    const andBtn = document.getElementById('rbLogicAnd');
    const orBtn  = document.getElementById('rbLogicOr');
    if (!andBtn || !orBtn) return;

    if (state.conditionLogic === 'AND') {
      andBtn.setAttribute('aria-checked', 'true');
      andBtn.classList.add('active-and');
      orBtn.setAttribute('aria-checked', 'false');
      orBtn.classList.remove('active-or');
    } else {
      orBtn.setAttribute('aria-checked', 'true');
      orBtn.classList.add('active-or');
      andBtn.setAttribute('aria-checked', 'false');
      andBtn.classList.remove('active-and');
    }

    // Refresh separators
    document.querySelectorAll('.condition-separator').forEach(sep => {
      sep.textContent = `─── ${state.conditionLogic} ───`;
    });

    const hint = document.getElementById('rbConditionHint');
    if (hint) {
      hint.textContent = state.conditionLogic === 'AND'
        ? 'All conditions must be true (AND logic). Switch to OR if any condition should match.'
        : 'Any one condition being true is enough (OR logic).';
    }
  }

  function setConditionLogic(mode) {
    state.conditionLogic = mode;
    _renderLogicToggle();
    updatePreview();
  }

  // ─── THEN / OTHERWISE sections ───────────────────────────────────────────

  function _renderActions(branch) {
    const containerId = branch === 'then' ? 'rbActionsBody' : 'rbOtherwiseBody';
    const container = document.getElementById(containerId);
    if (!container) return;

    const actionList = branch === 'then' ? state.actions : state.otherwiseActions;

    if (branch === 'otherwise' && !state.otherwiseExpanded) {
      container.style.display = 'none';
      return;
    }
    container.style.display = '';
    container.innerHTML = '';

    actionList.forEach((action, idx) => {
      container.insertAdjacentHTML('beforeend', _actionRowHtml(action, idx, branch));
      _bindActionRow(idx, branch);
    });

    let addBtn = document.getElementById(`rbAddAction_${branch}`);
    if (!addBtn) {
      addBtn = document.createElement('button');
      addBtn.type = 'button';
      addBtn.id = `rbAddAction_${branch}`;
      addBtn.className = 'btn btn-sm btn-outline-secondary mt-2';
      addBtn.innerHTML = '<i class="fas fa-plus me-1"></i>Add action';
      addBtn.addEventListener('click', () => addAction(branch));
      container.after(addBtn);
    }
    addBtn.style.display = (branch === 'otherwise' && !state.otherwiseExpanded) ? 'none' : '';
  }

  function _actionRowHtml(action, idx, branch) {
    const actionType = action.type || '';
    const ACTIONS_WITH_NO_TARGET = ['close_task', 'post_comment'];
    const ACTIONS_WITH_MESSAGE = ['send_notification', 'post_comment', 'create_wiki_page'];
    const showTarget = !!actionType && !ACTIONS_WITH_NO_TARGET.includes(actionType);
    const showMessage = ACTIONS_WITH_MESSAGE.includes(actionType);

    // Per-action copy for the message field so the label matches its purpose.
    const MESSAGE_COPY = {
      create_wiki_page: { label: 'Page content (optional):', ph: 'Body of the new wiki page. Supports {task_title}.' },
      post_comment:     { label: 'Comment (optional):',      ph: 'e.g. Auto-flagged: {task_title} needs review.' },
    };
    const msgCopy = MESSAGE_COPY[actionType] ||
      { label: 'Message (optional):', ph: 'e.g. Task {task_title} is overdue.' };

    const actionOptions = _renderGroupedOptions(ACTION_GROUPS, actionType);

    const targetHtml = showTarget ? `
      <span class="small text-muted mx-1">to</span>
      <span id="rbActionTargetWrap_${branch}_${idx}">${_actionTargetHtml(action, idx, branch)}</span>
    ` : '';

    const demoHintHtml = (
      actionType === 'send_notification' &&
      (boardData.is_official_demo_board || boardData.is_sandbox_copy)
    ) ? `
      <div class="small text-muted mt-1 ps-1">
        <i class="fas fa-info-circle me-1"></i>
        On demo boards, notifications are redirected to you so the test stays self-contained.
      </div>` : '';

    const messageHtml = showMessage ? `
      <div class="mt-2 ps-1">
        <label class="form-label small text-muted">${msgCopy.label}</label>
        <textarea class="form-control form-control-sm" rows="2"
          id="rbActionMsg_${branch}_${idx}"
          placeholder="${_esc(msgCopy.ph)}"
          aria-label="Action message">${_esc(action.message || '')}</textarea>
      </div>
    ` : '';

    return `
      <div class="action-card mb-2" data-idx="${idx}" data-branch="${branch}">
        <div class="d-flex align-items-center gap-2 flex-wrap">
          <select class="form-select form-select-sm" style="max-width:180px"
            id="rbActionType_${branch}_${idx}" aria-label="Action type">
            <option value="">Select action</option>
            ${actionOptions}
          </select>
          ${targetHtml}
          <button type="button" class="btn btn-sm btn-outline-danger ms-auto"
            aria-label="Remove action"
            onclick="UnifiedRuleBuilder.removeAction(${idx}, '${branch}')">
            <i class="fas fa-times"></i>
          </button>
        </div>
        ${demoHintHtml}
        ${messageHtml}
      </div>`;
  }

  function _actionTargetHtml(action, idx, branch) {
    const actionType = action.type || '';
    const target = action.target || '';

    if (actionType === 'set_priority') {
      return `<select class="form-select form-select-sm" style="max-width:140px"
        id="rbActionTarget_${branch}_${idx}" aria-label="Priority">
        ${['Urgent','High','Medium','Low'].map(p =>
          `<option value="${p}" ${target === p ? 'selected':''}>${p}</option>`).join('')}
      </select>`;
    }
    if (actionType === 'assign_to_user' || actionType === 'send_notification') {
      const NOTIFY_TARGETS = [
        ['task_assignee','Task assignee'],['all_board_members','All board members'],
        ['rule_creator','Rule creator'],
      ];
      const opts = NOTIFY_TARGETS.map(([v,l]) =>
        `<option value="${v}" ${target === v ? 'selected':''}>${l}</option>`
      ).join('');
      const memberOpts = boardData.members.map(m =>
        `<option value="${m.id}" ${target == m.id ? 'selected':''}>${_esc(m.username)}</option>`
      ).join('');
      return `<select class="form-select form-select-sm" style="max-width:180px"
        id="rbActionTarget_${branch}_${idx}" aria-label="Notification target">
        ${opts}
        <optgroup label="Specific member">${memberOpts}</optgroup>
      </select>`;
    }
    if (actionType === 'move_to_column') {
      return `<select class="form-select form-select-sm" style="max-width:180px"
        id="rbActionTarget_${branch}_${idx}" aria-label="Target column">
        <option value="">Select column</option>
        ${boardData.columns.map(c =>
          `<option value="${_esc(c.name)}" ${target === c.name ? 'selected':''}>${_esc(c.name)}</option>`
        ).join('')}
      </select>`;
    }
    if (actionType === 'set_due_date') {
      return `<select class="form-select form-select-sm" style="max-width:160px"
        id="rbActionTarget_${branch}_${idx}" aria-label="Due date">
        ${[['today','Today'],['in_2_days','In 2 days'],['in_7_days','In 7 days'],
           ['in_14_days','In 14 days'],['in_30_days','In 30 days']].map(([v,l]) =>
          `<option value="${v}" ${target === v ? 'selected':''}>${l}</option>`).join('')}
      </select>`;
    }
    if (actionType === 'add_label' || actionType === 'remove_label') {
      return `<input type="text" class="form-control form-control-sm"
        id="rbActionTarget_${branch}_${idx}" style="max-width:160px"
        placeholder="Label name" value="${_esc(target)}" aria-label="Label name">`;
    }
    if (actionType === 'log_time_entry') {
      return `<input type="number" class="form-control form-control-sm"
        id="rbActionTarget_${branch}_${idx}" min="0.5" step="0.5" style="width:90px"
        value="${target || 1}" aria-label="Hours"> <span class="small">hours</span>`;
    }
    // Action-specific hints so free-text targets explain what to type.
    const TARGET_PLACEHOLDERS = {
      create_wiki_page:        'New page title',
      link_wiki_page:          'Existing page slug',
      append_to_description:   'Text to append',
      auto_check_checklist:    'Checklist item text',
      promote_discovery_idea:  'Idea title',
      assign_subtasks_to:      'Username',
    };
    const placeholder = TARGET_PLACEHOLDERS[actionType] || 'Value';
    return `<input type="text" class="form-control form-control-sm"
      id="rbActionTarget_${branch}_${idx}" style="max-width:180px"
      placeholder="${_esc(placeholder)}" value="${_esc(target)}" aria-label="Target value">`;
  }

  function _bindActionRow(idx, branch) {
    const typeSel = document.getElementById(`rbActionType_${branch}_${idx}`);
    if (typeSel) {
      typeSel.addEventListener('change', e => {
        const actionList = branch === 'then' ? state.actions : state.otherwiseActions;
        actionList[idx].type = e.target.value;
        actionList[idx].target = '';
        actionList[idx].message = '';
        _renderActions(branch);
        updatePreview();
      });
    }
    const targetEl = document.getElementById(`rbActionTarget_${branch}_${idx}`);
    if (targetEl) {
      // Sync state with the rendered select's actual value. A SELECT with no
      // explicit `selected` option shows the first option as visually selected,
      // but the change event never fires, leaving state.target as '' and the
      // rule saving with an empty recipient/priority/etc.
      if (targetEl.tagName === 'SELECT') {
        const actionList = branch === 'then' ? state.actions : state.otherwiseActions;
        if (!actionList[idx].target && targetEl.value) {
          actionList[idx].target = targetEl.value;
        }
      }
      const ev = targetEl.tagName === 'SELECT' ? 'change' : 'input';
      targetEl.addEventListener(ev, e => {
        const actionList = branch === 'then' ? state.actions : state.otherwiseActions;
        actionList[idx].target = e.target.value;
        updatePreview();
      });
    }
    const msgEl = document.getElementById(`rbActionMsg_${branch}_${idx}`);
    if (msgEl) {
      msgEl.addEventListener('input', e => {
        const actionList = branch === 'then' ? state.actions : state.otherwiseActions;
        actionList[idx].message = e.target.value;
      });
    }
  }

  function addAction(branch) {
    if (branch === 'then') {
      state.actions.push({ type: '', target: '', message: '' });
    } else {
      state.otherwiseActions.push({ type: '', target: '', message: '' });
    }
    _renderActions(branch);
    updatePreview();
  }

  function removeAction(idx, branch) {
    if (branch === 'then') {
      state.actions.splice(idx, 1);
      if (state.actions.length === 0) {
        state.actions.push({ type: '', target: '', message: '' });
      }
    } else {
      state.otherwiseActions.splice(idx, 1);
    }
    _renderActions(branch);
    updatePreview();
  }

  // ─── OTHERWISE section ───────────────────────────────────────────────────

  function _renderOtherwiseHeader() {
    const btn = document.getElementById('rbOtherwiseToggleBtn');
    if (!btn) return;

    if (state.otherwiseExpanded) {
      btn.textContent = '− Remove else branch';
      btn.classList.replace('btn-outline-secondary', 'btn-outline-danger');

      const noIfWarning = document.getElementById('rbOtherwiseNoIfWarning');
      if (noIfWarning) {
        noIfWarning.style.display = state.conditions.length === 0 ? '' : 'none';
      }
    } else {
      btn.textContent = '+ Add else branch';
      btn.classList.replace('btn-outline-danger', 'btn-outline-secondary');
    }

    const body = document.getElementById('rbOtherwiseBody');
    if (body) body.style.display = state.otherwiseExpanded ? '' : 'none';

    const addBtn = document.getElementById('rbAddAction_otherwise');
    if (addBtn) addBtn.style.display = state.otherwiseExpanded ? '' : 'none';
  }

  function toggleOtherwiseBranch() {
    if (state.otherwiseExpanded) {
      // Confirm removal if there are actions
      if (state.otherwiseActions.length > 0) {
        const confirmEl = document.getElementById('rbOtherwiseConfirm');
        if (confirmEl) {
          confirmEl.style.display = '';
          return;
        }
      }
      _collapseOtherwise();
    } else {
      state.otherwiseExpanded = true;
      if (state.otherwiseActions.length === 0) {
        state.otherwiseActions.push({ type: '', target: '', message: '' });
      }
      _renderOtherwiseHeader();
      _renderActions('otherwise');
    }
  }

  function _collapseOtherwise() {
    state.otherwiseExpanded = false;
    state.otherwiseActions = [];
    _renderOtherwiseHeader();
    _renderActions('otherwise');
    updatePreview();
    const confirmEl = document.getElementById('rbOtherwiseConfirm');
    if (confirmEl) confirmEl.style.display = 'none';
  }

  function confirmRemoveOtherwise() { _collapseOtherwise(); }
  function cancelRemoveOtherwise() {
    const confirmEl = document.getElementById('rbOtherwiseConfirm');
    if (confirmEl) confirmEl.style.display = 'none';
  }

  // ─── Live preview ────────────────────────────────────────────────────────

  function updatePreview() {
    const el = document.getElementById('rbPreviewText');
    if (!el) return;

    const trigText = state.trigger
      ? (TRIGGER_LABELS[state.trigger] || state.trigger).toLowerCase()
      : null;

    const condParts = state.conditions
      .filter(c => c.attribute && c.operator)
      .map(c => _formatCondText(c));
    const sep = state.conditionLogic === 'AND' ? ' and ' : ' or ';
    const condText = condParts.length
      ? `if ${condParts.join(sep)}, `
      : '';

    const actParts = state.actions
      .filter(a => a.type)
      .map(a => _formatActionText(a));
    const thenText = actParts.length
      ? `then ${actParts.join(' and ')}`
      : null;

    const elseActParts = state.otherwiseActions
      .filter(a => a.type)
      .map(a => _formatActionText(a));
    const elseText = elseActParts.length
      ? `, otherwise ${elseActParts.join(' and ')}`
      : '';

    if (!trigText && !thenText) {
      el.innerHTML = '<em class="text-muted">When ____, then ____.</em>';
      return;
    }

    const trigSpan  = trigText ? trigText : '<em class="text-muted">____</em>';
    const thenSpan  = thenText ? thenText : '<em class="text-muted">____</em>';
    el.innerHTML = `When ${trigSpan}, ${condText}${thenSpan}${elseText}.`;
  }

  function _formatCondText(c) {
    const attr = ATTRIBUTE_LABELS[c.attribute] || c.attribute;
    const opMap = {
      is:'is', is_not:'is not', is_empty:'is empty', is_not_empty:'is not empty',
      has:'has', does_not_have:'does not have', gte:'≥', lte:'≤', equals:'=',
      within_days:'is within next', is_overdue:'is overdue', is_true:'is true', is_false:'is false',
      contains:'contains', does_not_contain:'does not contain',
      is_past:'is in the past', is_today:'is today',
      count_gte:'count ≥', count_lte:'count ≤',
    };
    const op = opMap[c.operator] || c.operator;
    let displayVal = c.value;
    // Assignee/created_by store the member ID as the value but should read as a
    // username in the preview (mirrors how _formatActionText resolves targets).
    if ((c.attribute === 'assignee' || c.attribute === 'created_by') &&
        c.value != null && c.value !== '' && c.value !== 'none') {
      const numId = parseInt(c.value, 10);
      const member = !isNaN(numId) && boardData.members.find(m => m.id === numId);
      if (member) displayVal = member.username;
    } else if (c.value === 'none') {
      displayVal = 'unassigned';
    }
    let val = displayVal !== null && displayVal !== undefined && displayVal !== '' ? ` ${displayVal}` : '';
    if (c.operator === 'within_days' && val) val = `${val} days`;
    return `${attr} ${op}${val}`;
  }

  function _formatActionText(a) {
    const label = ACTION_LABELS[a.type] || a.type;
    const NOTIFY_LABELS = {
      task_assignee:'task assignee', all_board_members:'all board members',
      rule_creator:'rule creator',
    };
    let target = '';
    if (a.target) {
      if (NOTIFY_LABELS[a.target]) {
        target = NOTIFY_LABELS[a.target];
      } else {
        const numId = parseInt(a.target, 10);
        const member = !isNaN(numId) && boardData.members.find(m => m.id === numId);
        target = member ? member.username : a.target;
      }
    }
    return target ? `${label.toLowerCase()} to ${target}` : label.toLowerCase();
  }

  // ─── Validation ──────────────────────────────────────────────────────────

  function validate() {
    const errors = [];
    const name = (document.getElementById('rbRuleName')?.value || '').trim();

    if (!name)          errors.push({ field: 'rbRuleName', msg: 'Please enter a rule name.' });
    if (name.length > 120) errors.push({ field: 'rbRuleName', msg: 'Rule name must be 120 characters or fewer.' });
    if (!state.trigger) errors.push({ field: 'rbTriggerSelect', msg: 'Please select a trigger in the WHEN section.' });

    if (state.trigger === 'scheduled_daily' && !state.triggerConfig.time)
      errors.push({ field: 'rbTrigSubTime', msg: 'Please set a time for the scheduled trigger.' });
    if (state.trigger === 'scheduled_weekly' && !state.triggerConfig.day)
      errors.push({ field: 'rbTrigSubDay', msg: 'Please choose a day for the weekly schedule.' });
    if (state.trigger === 'scheduled_monthly') {
      const dom = state.triggerConfig.day_of_month;
      if (!dom || dom < 1 || dom > 31)
        errors.push({ field: 'rbTrigSubDom', msg: 'Please enter a valid day of month (1–31).' });
    }

    if (!state.actions.some(a => a.type))
      errors.push({ field: 'rbActionsBody', msg: 'Please add at least one action in the THEN section.' });

    state.actions.forEach((a, i) => {
      if (!a.type)
        errors.push({ field: `rbActionType_then_${i}`, msg: 'Please select an action type.' });
    });

    const NO_VALUE_OPS = ['is_empty','is_not_empty','is_true','is_false','is_overdue','is_past','is_today'];
    state.conditions.forEach((c, i) => {
      if (!c.attribute) {
        errors.push({ field: `rbCondAttr_${i}`, msg: 'Please complete all condition fields or remove the incomplete row.' });
        return;
      }
      if (!c.operator) {
        errors.push({ field: `rbCondOp_${i}`, msg: 'Please choose an operator for this condition.' });
        return;
      }
      if (!NO_VALUE_OPS.includes(c.operator)) {
        const v = c.value;
        const isBlank = v === null || v === undefined || (typeof v === 'string' && v.trim() === '');
        if (isBlank) {
          errors.push({ field: `rbCondVal_${i}`, msg: 'This condition needs a value to match against.' });
        }
      }
    });

    // Trigger-config required-field validation for newly wired triggers.
    if (state.trigger === 'task_idle') {
      const d = parseInt(state.triggerConfig.idle_days);
      if (!d || d < 1) {
        errors.push({ field: 'rbTrigSubIdleDays', msg: 'Please enter how many idle days should trigger the rule.' });
      }
    }
    if (state.trigger === 'due_date_approaching') {
      const d = parseInt(state.triggerConfig.days);
      if (!d || d < 1) {
        errors.push({ field: 'rbTrigSubDays', msg: 'Please enter how many days ahead to watch for.' });
      }
    }

    return errors;
  }

  function _showErrors(errors) {
    _clearErrors();
    errors.forEach(({ field, msg }) => {
      const el = document.getElementById(field);
      if (el) {
        el.classList.add('is-invalid');
        const fb = document.createElement('div');
        fb.className = 'invalid-feedback';
        fb.textContent = msg;
        el.parentNode.insertBefore(fb, el.nextSibling);
      }
    });
    // Also show a summary at the top
    const summary = document.getElementById('rbErrorSummary');
    if (summary && errors.length) {
      summary.textContent = errors[0].msg;
      summary.style.display = '';
    }
  }

  function _clearErrors() {
    document.querySelectorAll('#ruleBuilderModal .is-invalid').forEach(el => {
      el.classList.remove('is-invalid');
    });
    document.querySelectorAll('#ruleBuilderModal .invalid-feedback').forEach(el => el.remove());
    const summary = document.getElementById('rbErrorSummary');
    if (summary) summary.style.display = 'none';
  }

  // ─── Save ────────────────────────────────────────────────────────────────

  async function save() {
    _clearErrors();
    const errors = validate();
    if (errors.length) { _showErrors(errors); return; }

    const name = document.getElementById('rbRuleName').value.trim();
    const payload = {
      name,
      trigger_type: state.trigger,
      trigger_config: state.triggerConfig,
      condition_logic: state.conditionLogic,
      conditions: state.conditions.filter(c => c.attribute && c.operator),
      actions: state.actions.filter(a => a.type),
      otherwise_actions: state.otherwiseActions.filter(a => a.type),
    };

    const url = state.ruleId
      ? `/boards/${state.boardId}/automations/rules/${state.ruleId}/update/`
      : `/boards/${state.boardId}/automations/rules/create/`;

    const saveBtn = document.getElementById('rbSaveBtn');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Saving…'; }

    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': _getCsrf(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify(payload),
      });

      const data = await resp.json();

      if (!resp.ok) {
        const errs = data.errors || [data.error || 'An error occurred.'];
        _showErrors(errs.map(msg => ({ field: 'rbErrorSummary', msg })));
        return;
      }

      close();
      // Reload the page to show the updated rule list
      window.location.reload();

    } catch (_) {
      _showErrors([{ field: 'rbErrorSummary', msg: 'Network error — please try again.' }]);
    } finally {
      if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Save & activate'; }
    }
  }

  // ─── Rule list actions ───────────────────────────────────────────────────

  async function toggleRule(ruleId) {
    try {
      const resp = await fetch(
        `/boards/${state.boardId}/automations/rules/${ruleId}/toggle/`,
        {
          method: 'POST',
          headers: { 'X-CSRFToken': _getCsrf(), 'Accept': 'application/json' },
        }
      );
      if (resp.ok) window.location.reload();
    } catch (_) {}
  }

  async function deleteRule(ruleId, ruleName) {
    const confirmEl = document.getElementById(`rbDeleteConfirm_${ruleId}`);
    if (confirmEl) {
      confirmEl.style.display = confirmEl.style.display === 'none' ? '' : 'none';
      return;
    }
    if (!confirm(`Delete rule "${ruleName}"? This cannot be undone.`)) return;
    try {
      const resp = await fetch(
        `/boards/${state.boardId}/automations/rules/${ruleId}/delete/`,
        {
          method: 'POST',
          headers: {
            'X-CSRFToken': _getCsrf(),
            'Accept': 'application/json',
          },
        }
      );
      if (resp.ok) window.location.reload();
    } catch (_) {}
  }

  async function duplicateRule(ruleId) {
    try {
      const resp = await fetch(
        `/boards/${state.boardId}/automations/rules/${ruleId}/duplicate/`,
        {
          method: 'POST',
          headers: { 'X-CSRFToken': _getCsrf(), 'Accept': 'application/json' },
        }
      );
      if (resp.ok) {
        const rule = await resp.json();
        open(rule.id);
      }
    } catch (_) {}
  }

  // ─── Utilities ───────────────────────────────────────────────────────────

  function _esc(str) {
    return String(str || '')
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function _getCsrf() {
    const el = document.querySelector('[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
  }

  // ─── Trigger select wiring (called from template) ────────────────────────

  function onTriggerChange(value) {
    state.trigger = value;
    state.triggerConfig = {};
    _renderTrigger();
    updatePreview();
  }

  // ─── Public API ──────────────────────────────────────────────────────────

  return {
    init, open, close, reset,
    addCondition, removeCondition, setConditionLogic,
    addAction, removeAction,
    toggleOtherwiseBranch, confirmRemoveOtherwise, cancelRemoveOtherwise,
    toggleRule, deleteRule, duplicateRule,
    onTriggerChange,
    updatePreview, save,
  };

})();
