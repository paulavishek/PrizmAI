/**
 * Shadow Board Frontend JavaScript
 * 
 * Handles:
 * - Sparkline rendering
 * - Compare mode for branches
 * - AJAX calls for branch operations
 * - Modal interactions
 */

document.addEventListener('DOMContentLoaded', function() {
    // Mini sparklines on cards were removed — a single-snapshot branch
    // rendered as a flat line that misleadingly implied long-term
    // stability.  The Feasibility Trend chart on the branch detail page
    // remains the authoritative trend view.

    initCompareMode();
    initBranchCardActions();
    initCreateBranchForm();
    initColorPicker();
    loadScenarios();
    pollPendingBranches();

    const restoreAllBtn = document.getElementById('restoreAllArchivedBtn');
    if (restoreAllBtn) {
        restoreAllBtn.addEventListener('click', restoreAllArchived);
    }

    // Manual refresh button: forces a synchronous recalc against the
    // current board state, then reloads.  Lets the user explicitly
    // resolve the "did anything change?" question after moving tasks,
    // without having to guess whether Celery has finished.
    const refreshBtn = document.getElementById('refreshScoresBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshAllBranchScores);
    }
});

/**
 * Poll branches that are still "Calculating first snapshot..."
 * Auto-reloads the page when all pending branches have snapshots.
 */
function pollPendingBranches() {
    const pendingCards = document.querySelectorAll('.branch-card[data-pending="true"]');
    if (pendingCards.length === 0) return;

    const boardId = getBoardId();
    let pollInterval = setInterval(function() {
        let stillPending = 0;
        const checks = [];

        pendingCards.forEach(function(card) {
            const branchId = card.dataset.branchId;
            if (!branchId) return;

            const p = fetch(`/api/boards/${boardId}/shadow/branch/${branchId}/snapshots/`)
                .then(r => r.json())
                .then(data => {
                    if (data.count && data.count > 0) {
                        // Snapshot arrived — this branch is ready
                        return true;
                    }
                    stillPending++;
                    return false;
                })
                .catch(() => { stillPending++; return false; });
            checks.push(p);
        });

        Promise.all(checks).then(function(results) {
            if (stillPending === 0) {
                clearInterval(pollInterval);
                window.location.reload();
            }
        });
    }, 5000);  // Poll every 5 seconds
}

/**
 * Manual refresh: synchronously recalculate every active branch on this
 * board against the live state, then reload the page so the cards and
 * the Quantum Standup table reflect the new snapshots.
 *
 * Why this exists: signal-driven recalcs run in Celery and can take a
 * few seconds.  Users who move a task and immediately re-open the
 * Shadow Board see "did anything change?" stale data.  The button
 * lets them resolve the question on demand without polling.
 */
function refreshAllBranchScores() {
    const btn = document.getElementById('refreshScoresBtn');
    if (!btn) return;

    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Refreshing…';

    fetch(`/api/boards/${getBoardId()}/shadow/refresh/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
        },
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            // Server already wrote new snapshots; reloading is enough
            // to pick them up everywhere on the page.
            window.location.reload();
        } else {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
            alertError('Could not refresh: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(e => {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
        alertError('Could not refresh: ' + e.message);
    });
}

/**
 * Initialize compare mode toggle
 */
function initCompareMode() {
    const compareToggle = document.getElementById('compareToggle');
    const compareTable = document.getElementById('compareTable');
    const branchGrid = document.getElementById('branchGrid');
    
    if (!compareToggle) return;
    
    compareToggle.addEventListener('change', function() {
        if (this.checked) {
            // Enable compare mode
            branchGrid?.classList.add('compare-mode');
            showCompareCheckboxes();
        } else {
            // Disable compare mode
            branchGrid?.classList.remove('compare-mode');
            hideCompareCheckboxes();
            compareTable.style.display = 'none';
            document.querySelectorAll('.branch-checkbox').forEach(cb => cb.checked = false);
        }
    });
    
    // Event delegation for compare checkboxes
    branchGrid?.addEventListener('change', function(e) {
        if (e.target.classList.contains('branch-checkbox')) {
            handleBranchSelection();
        }
    });
}

/**
 * Show compare checkboxes on branch cards
 */
function showCompareCheckboxes() {
    document.querySelectorAll('.branch-checkbox').forEach(cb => {
        cb.style.display = 'block';
    });
}

/**
 * Hide compare checkboxes
 */
function hideCompareCheckboxes() {
    document.querySelectorAll('.branch-checkbox').forEach(cb => {
        cb.style.display = 'none';
    });
}

// Maximum number of branches that can be compared simultaneously.  Eight
// is the server-side cap too (see get_branches_comparison_multi).  Beyond
// that the diff table stops being useful on a normal monitor.
const MAX_COMPARE_BRANCHES = 8;

/**
 * Handle branch selection for comparison.  Supports N branches (2-8); when
 * the user tries to check a 9th, the click is reverted with a brief hint.
 */
function handleBranchSelection() {
    const checked = Array.from(document.querySelectorAll('.branch-checkbox:checked'));
    const compareTable = document.getElementById('compareTable');

    // Enforce the upper bound.  Uncheck the most recently checked box
    // (i.e., whichever pushed the count over the limit) so the user keeps
    // their earlier selection rather than being silently overridden.
    if (checked.length > MAX_COMPARE_BRANCHES) {
        const overflow = checked[checked.length - 1];
        overflow.checked = false;
        const card = overflow.closest('.branch-card');
        if (card) card.classList.remove('selected');
        alertError(`You can compare up to ${MAX_COMPARE_BRANCHES} branches at a time.`);
        return;
    }

    // Update selected card styling
    document.querySelectorAll('.branch-card').forEach(card => {
        card.classList.remove('selected');
        const checkbox = card.querySelector('.branch-checkbox');
        if (checkbox?.checked) {
            card.classList.add('selected');
        }
    });

    if (checked.length >= 2) {
        const branchIds = checked.map(cb => cb.dataset.branchId);
        showComparison(branchIds);
    } else {
        // Need at least 2 to compare — hide the table.
        compareTable.style.display = 'none';
    }
}

/**
 * Fetch and display N-way branch comparison.
 *
 * @param {string[]} branchIds  Array of branch IDs in click order.
 */
async function showComparison(branchIds) {
    if (!Array.isArray(branchIds) || branchIds.length < 2) return;

    try {
        const qs = new URLSearchParams({ branch_ids: branchIds.join(',') });
        const response = await fetch(
            `/api/boards/${getBoardId()}/shadow/branches-compare/?${qs.toString()}`
        );
        const data = await response.json();

        if (!response.ok || data.error) {
            alertError('Comparison failed: ' + (data.error || response.statusText));
            return;
        }

        renderComparisonTable(data.branches);
        document.getElementById('compareTable').style.display = 'block';
    } catch (e) {
        console.error('Error fetching comparison:', e);
        alertError('Could not load comparison: ' + e.message);
    }
}

/**
 * Render the N-column comparison table.
 *
 * Rebuilds both the table header (one column per branch) and the body
 * rows (one row per field).  Each row highlights:
 *   - diff-row-match: every branch has the same value
 *   - diff-row-conflict: numeric values disagree in sign (e.g. one branch
 *     adds scope, another removes it)
 *   - diff-row-diff: values vary but don't conflict in sign
 *
 * @param {Array} branches  Server payload from /branches-compare/.
 */
function renderComparisonTable(branches) {
    const title = document.getElementById('compareTitle');
    const table = document.getElementById('diffTable');
    const thead = table.querySelector('thead');
    const body = document.getElementById('diffTableBody');

    // Title summarises the comparison set; truncate names so a 6-way
    // comparison doesn't blow up the card header.
    const truncate = (s, n) => (s.length > n ? s.slice(0, n - 1) + '…' : s);
    title.textContent = branches.map(b => truncate(b.name, 30)).join(' vs ');

    // Rebuild the header row entirely so column count matches the
    // selected branch count.  The original static "branchAHeader" /
    // "branchBHeader" cells are replaced.
    const branchColPct = Math.max(8, Math.floor(75 / branches.length));
    thead.innerHTML = '';
    const headerRow = document.createElement('tr');
    const fieldTh = document.createElement('th');
    fieldTh.style.width = '25%';
    fieldTh.textContent = 'Field';
    headerRow.appendChild(fieldTh);
    branches.forEach(b => {
        const th = document.createElement('th');
        th.style.width = `${branchColPct}%`;
        // Coloured swatch so the diff table maps visually back to the
        // cards (which use the same per-branch colour as a left border).
        th.innerHTML = `
            <span class="d-inline-block me-1" style="
                width: 10px; height: 10px; border-radius: 50%;
                background: ${b.color || '#0d6efd'};
            "></span>${b.name}
        `;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    // Build rows.  When ALL branches have missing snapshots, render a
    // single explanatory row.  When SOME branches are missing, fill
    // those cells with a "Calculating…" placeholder so the user
    // understands why a column is sparse.
    body.innerHTML = '';

    const allMissing = branches.every(b => b.snapshot_missing);
    if (allMissing) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td colspan="${branches.length + 1}" class="text-muted text-center py-3">
                <i class="fas fa-hourglass-half me-1"></i>
                None of the selected branches have a snapshot yet — try again in a few seconds.
            </td>
        `;
        body.appendChild(tr);
        return;
    }

    const fields = [
        { label: 'Scope Delta', key: 'scope_delta', suffix: '' },
        { label: 'Team Delta', key: 'team_delta', suffix: '' },
        { label: 'Deadline Delta (weeks)', key: 'deadline_delta_weeks', suffix: '' },
        { label: 'Feasibility Score', key: 'feasibility_score', suffix: '%' },
        { label: 'Projected Completion', key: 'projected_completion_date', suffix: '' },
        { label: 'Budget Utilization', key: 'projected_budget_utilization', suffix: '%' },
    ];

    fields.forEach(field => {
        const values = branches.map(b => {
            if (b.snapshot_missing || !b.snapshot) return null;
            return b.snapshot[field.key];
        });

        // Diff classification across N columns:
        //   - all equal              → match
        //   - any pair has opposite signs (numeric only) → conflict
        //   - otherwise              → diff
        const presentValues = values.filter(v => v !== null && v !== undefined);
        const allEqual = presentValues.length === values.length &&
            presentValues.every(v => v === presentValues[0]);
        let hasSignConflict = false;
        if (!allEqual) {
            const numericVals = presentValues.filter(v => typeof v === 'number' && v !== 0);
            const signs = new Set(numericVals.map(v => Math.sign(v)));
            hasSignConflict = signs.size > 1;
        }
        const rowClass = allEqual
            ? 'diff-row-match'
            : (hasSignConflict ? 'diff-row-conflict' : 'diff-row-diff');

        const tr = document.createElement('tr');
        tr.className = rowClass;
        const labelCell = `<td><strong>${field.label}</strong></td>`;
        const valueCells = values.map(v => {
            if (v === null || v === undefined) {
                return `<td class="text-muted"><small><i class="fas fa-hourglass-half me-1"></i>Calculating…</small></td>`;
            }
            const display = (typeof v === 'number')
                ? `${v}${field.suffix}`
                : `${v}${field.suffix}`;
            return `<td>${display}</td>`;
        }).join('');
        tr.innerHTML = labelCell + valueCells;
        body.appendChild(tr);
    });
}

/**
 * Get branch name by ID (from data attribute)
 */
function getBranchName(branchId) {
    const card = document.querySelector(`[data-branch-id="${branchId}"]`);
    return card?.querySelector('.branch-name')?.textContent || `Branch ${branchId}`;
}

/**
 * Initialize branch card actions (star, commit, view)
 */
function initBranchCardActions() {
    document.addEventListener('click', function(e) {
        const starBtn = e.target.closest('.btn-star');
        if (starBtn) {
            const branchId = starBtn.dataset.branchId;
            toggleStarBranch(branchId, starBtn);
        }
        
        const commitBtn = e.target.closest('.btn-commit');
        if (commitBtn) {
            const branchId = commitBtn.dataset.branchId;
            showCommitConfirmation(branchId);
        }

        const deleteBtn = e.target.closest('.btn-delete');
        if (deleteBtn) {
            const branchId = deleteBtn.dataset.branchId;
            const branchName = deleteBtn.dataset.branchName || 'this branch';
            showDeleteConfirmation(branchId, branchName);
        }

        const restoreBtn = e.target.closest('.btn-restore');
        if (restoreBtn) {
            const branchId = restoreBtn.dataset.branchId;
            restoreBranch(branchId);
        }
    });
}

/**
 * Restore an archived branch back to active
 */
function restoreBranch(branchId) {
    fetch(`/api/boards/${getBoardId()}/shadow/${branchId}/restore/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            setTimeout(() => window.location.reload(), 400);
        } else {
            alertError('Could not restore branch: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(e => alertError('Could not restore branch: ' + e.message));
}

/**
 * Show delete confirmation and delete branch
 */
function showDeleteConfirmation(branchId, branchName) {
    if (!confirm(`Delete "${branchName}"? This will remove all its snapshots and history permanently.`)) return;

    fetch(`/api/boards/${getBoardId()}/shadow/${branchId}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            if (data.restore_message) {
                showSuccess(`Branch deleted. ${data.restore_message}`);
            } else {
                showSuccess('Branch deleted.');
            }
            setTimeout(() => window.location.reload(), 1600);
        } else {
            alertError('Could not delete branch: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(e => alertError('Could not delete branch: ' + e.message));
}

/**
 * Apply star visual state to button icon + card title.
 * Extracted so it can be called for both optimistic apply and error revert.
 */
function applyStarVisuals(icon, btn, starred) {
    if (starred) {
        icon.classList.replace('far', 'fas');
        btn.classList.add('text-warning');
    } else {
        icon.classList.replace('fas', 'far');
        btn.classList.remove('text-warning');
    }

    const card = btn.closest('.branch-card');
    if (!card) return;
    const titleEl = card.querySelector('.card-title');
    if (!titleEl) return;
    const existingTitleStar = titleEl.querySelector('.fa-star');

    if (starred && !existingTitleStar) {
        const newStar = document.createElement('i');
        newStar.className = 'fas fa-star text-warning me-1';
        titleEl.prepend(newStar);
    } else if (!starred && existingTitleStar) {
        existingTitleStar.remove();
    }
}

/**
 * Toggle star status for branch.
 * Optimistic update: UI changes immediately on click; reverted on error.
 */
function toggleStarBranch(branchId, btn) {
    const icon = btn.querySelector('i');
    const wasStarred = icon.classList.contains('fas');
    const nowStarred = !wasStarred;

    // Apply immediately so the user sees instant feedback without waiting
    // for the server round-trip.
    applyStarVisuals(icon, btn, nowStarred);

    fetch(`/api/boards/${getBoardId()}/shadow/${branchId}/toggle-star/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ starred: nowStarred })
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) {
            // Server rejected — revert to previous state
            applyStarVisuals(icon, btn, wasStarred);
        }
    })
    .catch(() => {
        // Network / parse error — revert
        applyStarVisuals(icon, btn, wasStarred);
        alertError('Could not toggle star. Please try again.');
    });
}

/**
 * Show commit confirmation modal
 */
function showCommitConfirmation(branchId) {
    const branchCard = document.querySelector(`[data-branch-id="${branchId}"]`);
    const branchName = branchCard?.querySelector('.card-title')?.textContent.trim() || 'this branch';

    // Populate modal
    const nameEl = document.getElementById('commitBranchName');
    if (nameEl) nameEl.textContent = `"${branchName}"`;

    const modal = new bootstrap.Modal(document.getElementById('commitConfirmModal'));
    modal.show();

    // Wire up confirm button (replace any previous listener)
    const confirmBtn = document.getElementById('confirmCommitBtn');
    const newConfirmBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
    newConfirmBtn.addEventListener('click', function () {
        modal.hide();
        commitBranch(branchId);
    });
}

/**
 * Commit a branch
 */
function commitBranch(branchId) {
    fetch(`/boards/${getBoardId()}/shadow/${branchId}/commit/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ confirm: true })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            showSuccess('Branch committed! Redirecting...');
            setTimeout(() => {
                window.location.href = data.redirect_url || getBoardShadowUrl();
            }, 1500);
        } else {
            alertError(data.error || 'Failed to commit branch');
        }
    })
    .catch(e => alertError('Error: ' + e.message));
}

/**
 * Initialize create branch form
 */
function initCreateBranchForm() {
    const form = document.getElementById('createBranchForm');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        
        fetch(`/boards/${getBoardId()}/shadow/create/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showSuccess(`Branch "${data.branch_name}" created!`);
                bootstrap.Modal.getInstance(document.getElementById('createBranchModal'))?.hide();
                setTimeout(() => window.location.reload(), 1200);
            } else {
                alertError(data.error || 'Failed to create branch');
            }
        })
        .catch(e => alertError('Error: ' + e.message));
    });
}

/**
 * Load saved scenarios into select dropdown
 */
function loadScenarios() {
    const select = document.getElementById('scenarioSelect');
    if (!select) return;
    
    fetch(`/boards/${getBoardId()}/what-if/history/`)
        .then(r => r.json())
        .then(data => {
            if (data.scenarios) {
                data.scenarios.forEach(s => {
                    const option = document.createElement('option');
                    option.value = s.id;
                    option.textContent = `${s.name} (${s.scenario_type})`;
                    select.appendChild(option);
                });
            }
        })
        .catch(e => console.warn('Could not load scenarios:', e));
}

/**
 * Initialize color picker — marks the initially-checked swatch and keeps
 * the .color-selected class in sync so the CSS checkmark + ring shows correctly.
 */
function initColorPicker() {
    const picker = document.querySelector('.branch-color-picker');
    if (!picker) return;

    picker.querySelectorAll('input[type="radio"]').forEach(function(radio) {
        const label = radio.closest('label');
        if (!label) return;

        // Apply selected class to whichever radio starts checked
        if (radio.checked) label.classList.add('color-selected');

        radio.addEventListener('change', function() {
            picker.querySelectorAll('label').forEach(l => l.classList.remove('color-selected'));
            if (radio.checked) label.classList.add('color-selected');
        });
    });
}

/**
 * Restore all archived branches on this board to active.
 */
function restoreAllArchived() {
    fetch(`/api/boards/${getBoardId()}/shadow/restore-all/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            showSuccess(data.message || 'All archived branches restored.');
            setTimeout(() => window.location.reload(), 1200);
        } else {
            alertError('Could not restore branches: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(e => alertError('Could not restore branches: ' + e.message));
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Get CSRF token from DOM
 */
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
           document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
}

/**
 * Get current board ID from URL
 */
function getBoardId() {
    const match = window.location.pathname.match(/\/boards\/(\d+)\//);
    return match ? match[1] : null;
}

/**
 * Get board shadow URL
 */
function getBoardShadowUrl() {
    return `/boards/${getBoardId()}/shadow/`;
}

/**
 * Get branch name from card
 */
function getBranchName(branchId) {
    const card = document.querySelector(`[data-branch-id="${branchId}"]`);
    return card?.querySelector('.card-title').textContent.trim().replace(/★/, '').trim() || `Branch ${branchId}`;
}

/**
 * Show success toast
 */
function showSuccess(message) {
    // Bootstrap toast or simple alert
    const toast = document.createElement('div');
    toast.className = 'alert alert-success alert-dismissible fade show position-fixed';
    toast.style.cssText = 'bottom: 20px; right: 20px; z-index: 9999; max-width: 300px;';
    toast.innerHTML = `
        <i class="fas fa-check-circle me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.remove(), 4000);
}

/**
 * Show error alert
 */
function alertError(message) {
    const toast = document.createElement('div');
    toast.className = 'alert alert-danger alert-dismissible fade show position-fixed';
    toast.style.cssText = 'bottom: 20px; right: 20px; z-index: 9999; max-width: 300px;';
    toast.innerHTML = `
        <i class="fas fa-exclamation-circle me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.remove(), 5000);
}
