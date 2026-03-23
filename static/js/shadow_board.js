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
    // Initialize sparklines
    renderSparklines();
    
    // Initialize compare mode
    initCompareMode();
    
    // Initialize branch card actions
    initBranchCardActions();
    
    // Initialize create branch form
    initCreateBranchForm();
    
    // Load saved scenarios into select
    loadScenarios();

    // Poll for branches still calculating their first snapshot
    pollPendingBranches();
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
 * Render sparklines for each branch
 */
function renderSparklines() {
    const branchCards = document.querySelectorAll('.branch-card');
    
    branchCards.forEach(card => {
        const branchId = card.dataset.branchId;
        const canvas = document.getElementById(`sparkline-${branchId}`);
        
        if (!canvas) return;
        
        // Fetch branch snapshots via API
        fetch(`/api/boards/${getBoardId()}/shadow/branch/${branchId}/snapshots/`)
            .then(r => r.json())
            .then(data => {
                if (data.scores && data.scores.length > 0) {
                    drawSparkline(canvas, data.scores);
                } else {
                    const ctx = canvas.getContext('2d');
                    canvas.style.height = '30px';
                    ctx.font = '11px sans-serif';
                    ctx.fillStyle = '#999';
                    ctx.textAlign = 'center';
                    ctx.fillText('No trend data yet', canvas.width / 2, 20);
                }
            })
            .catch(e => console.warn('Could not load sparkline:', e));
    });
}

/**
 * Draw a sparkline chart on a canvas
 */
function drawSparkline(canvas, scores) {
    if (typeof Chart === 'undefined') return;
    
    const ctx = canvas.getContext('2d');
    const colors = scores.map(s => {
        if (s >= 70) return '#198754';
        if (s >= 50) return '#fd7e14';
        return '#dc3545';
    });
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: scores.map((_, i) => i),
            datasets: [{
                label: 'Feasibility',
                data: scores,
                borderColor: '#0d6efd',
                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointBackgroundColor: colors
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => `Feasibility: ${context.parsed.y}%`
                    }
                }
            },
            scales: {
                y: {
                    min: 0,
                    max: 100,
                    ticks: { display: false },
                    grid: { display: false }
                },
                x: {
                    display: false,
                    grid: { display: false }
                }
            }
        }
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

/**
 * Handle branch selection for comparison
 */
function handleBranchSelection() {
    const checked = document.querySelectorAll('.branch-checkbox:checked');
    const compareTable = document.getElementById('compareTable');
    
    // Only allow 2 selections
    if (checked.length > 2) {
        checked[2].previousElementSibling?.click(); // Uncheck the third
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
    
    if (checked.length === 2) {
        // Show comparison
        const branchAId = checked[0].dataset.branchId;
        const branchBId = checked[1].dataset.branchId;
        showComparison(branchAId, branchBId);
    } else {
        // Hide comparison table
        compareTable.style.display = 'none';
    }
}

/**
 * Fetch and display branch comparison
 */
async function showComparison(branchAId, branchBId) {
    try {
        // First get the comparison data (snapshots)
        const response = await fetch(
            `/api/boards/${getBoardId()}/shadow/branches/${branchAId}/${branchBId}/`
        );
        const data = await response.json();
        
        if (data.error) {
            console.error('Comparison error:', data.error);
            return;
        }
        
        renderComparisonTable(data);
        document.getElementById('compareTable').style.display = 'block';
    } catch (e) {
        console.error('Error fetching comparison:', e);
    }
}

/**
 * Render the comparison table
 */
function renderComparisonTable(data) {
    const title = document.getElementById('compareTitle');
    const headerA = document.getElementById('branchAHeader');
    const headerB = document.getElementById('branchBHeader');
    const body = document.getElementById('diffTableBody');
    
    const branchA = data.branch_a;
    const branchB = data.branch_b;
    
    title.textContent = `${branchA.name} vs ${branchB.name}`;
    headerA.textContent = branchA.name;
    headerB.textContent = branchB.name;
    body.innerHTML = '';
    
    const snapA = branchA.snapshot;
    const snapB = branchB.snapshot;
    
    const rows = [
        { label: 'Scope Delta', fieldA: snapA.scope_delta, fieldB: snapB.scope_delta },
        { label: 'Team Delta', fieldA: snapA.team_delta, fieldB: snapB.team_delta },
        { label: 'Deadline Delta (weeks)', fieldA: snapA.deadline_delta_weeks, fieldB: snapB.deadline_delta_weeks },
        { label: 'Feasibility Score', fieldA: snapA.feasibility_score + '%', fieldB: snapB.feasibility_score + '%' },
        { label: 'Projected Completion', fieldA: snapA.projected_completion_date || 'N/A', fieldB: snapB.projected_completion_date || 'N/A' },
        { label: 'Budget Utilization', fieldA: snapA.projected_budget_utilization + '%', fieldB: snapB.projected_budget_utilization + '%' },
    ];
    
    rows.forEach(row => {
        const isConflict = (row.fieldA !== row.fieldB) && 
            (typeof row.fieldA === 'number' && typeof row.fieldB === 'number' &&
             Math.sign(row.fieldA) !== Math.sign(row.fieldB));
        
        const diffClass = row.fieldA === row.fieldB ? 'diff-row-match' : 
                        (isConflict ? 'diff-row-conflict' : 'diff-row-diff');
        
        const tr = document.createElement('tr');
        tr.className = diffClass;
        tr.innerHTML = `
            <td><strong>${row.label}</strong></td>
                    <td>${row.fieldA}</td>
            <td>${row.fieldB}</td>
        `;
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
            // Reload after brief delay to reflect updated branch list
            setTimeout(() => window.location.reload(), 600);
        } else {
            alertError('Could not delete branch: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(e => alertError('Could not delete branch: ' + e.message));
}

/**
 * Toggle star status for branch
 */
function toggleStarBranch(branchId, btn) {
    const isStarred = btn.querySelector('i').classList.contains('fas');
    
    fetch(`/api/boards/${getBoardId()}/shadow/${branchId}/toggle-star/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ starred: !isStarred })
    })
    .then(r => r.json())
    .then(data => {
        // Toggle icon
        btn.querySelector('i').classList.toggle('fas');
        btn.querySelector('i').classList.toggle('far');
    })
    .catch(e => alertError('Could not toggle star: ' + e.message));
}

/**
 * Show commit confirmation modal
 */
function showCommitConfirmation(branchId) {
    // Find branch name for display
    const branchCard = document.querySelector(`[data-branch-id="${branchId}"]`);
    const branchName = branchCard?.querySelector('.card-title').textContent.trim() || 'Unknown';
    
    if (confirm(`Are you sure you want to commit branch "${branchName}"?`)) {
        commitBranch(branchId);
    }
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
