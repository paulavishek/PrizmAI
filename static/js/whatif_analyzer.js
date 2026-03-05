/**
 * What-If Scenario Analyzer — Client-side logic
 *
 * Handles slider interactivity, AJAX calls for simulation/save,
 * rendering of impact results, Chart.js visualization, and AI analysis.
 */
(function () {
    'use strict';

    const CFG = window.WHATIF_CONFIG;
    if (!CFG) return;

    const BL = CFG.baseline;   // baseline snapshot from server
    let lastResults = null;     // most recent simulation results
    let lastParams = null;      // most recent input params
    let comparisonChart = null;  // Chart.js instance

    // ── DOM refs ────────────────────────────────────────────────
    const scopeSlider    = document.getElementById('scope-slider');
    const teamSlider     = document.getElementById('team-slider');
    const deadlineSlider = document.getElementById('deadline-slider');
    const scopeVal       = document.getElementById('scope-val');
    const teamVal        = document.getElementById('team-val');
    const deadlineVal    = document.getElementById('deadline-val');
    const scopeAbs       = document.getElementById('scope-abs');
    const teamAbs        = document.getElementById('team-abs');
    const deadlineAbs    = document.getElementById('deadline-abs');

    const btnAnalyze  = document.getElementById('btn-analyze');
    const btnReset    = document.getElementById('btn-reset');
    const btnAI       = document.getElementById('btn-ai');
    const btnSave     = document.getElementById('btn-save');
    const btnConfirmSave = document.getElementById('btn-confirm-save');

    const impactPanel   = document.getElementById('impact-panel');
    const impactLoading = document.getElementById('impact-loading');
    const impactResults = document.getElementById('impact-results');
    const warningsArea  = document.getElementById('warnings-area');

    // ── Helpers ─────────────────────────────────────────────────
    function fmt(n) { return Number(n).toLocaleString(undefined, { maximumFractionDigits: 1 }); }

    function signed(n, suffix) {
        suffix = suffix || '';
        const s = n > 0 ? '+' + fmt(n) : fmt(n);
        return s + suffix;
    }

    function deltaClass(val, inverse) {
        if (val === 0) return 'delta-neutral';
        // For some metrics, positive is bad (delay, cost, utilization).
        // For others, positive is good (team size, velocity).
        if (inverse) return val > 0 ? 'delta-negative' : 'delta-positive';
        return val > 0 ? 'delta-positive' : 'delta-negative';
    }

    function riskBadge(level) {
        const colors = { critical: 'danger', high: 'warning', medium: 'info', low: 'success', unknown: 'secondary' };
        return '<span class="badge bg-' + (colors[level] || 'secondary') + ' text-capitalize">' + level + '</span>';
    }

    function getCookie(name) {
        const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return v ? v.pop() : '';
    }

    // ── Slider updates ──────────────────────────────────────────
    function updateSliderLabels() {
        const sv = parseInt(scopeSlider.value);
        const tv = parseInt(teamSlider.value);
        const dv = parseInt(deadlineSlider.value);

        scopeVal.textContent = (sv >= 0 ? '+' : '') + sv;
        teamVal.textContent  = (tv >= 0 ? '+' : '') + tv;
        deadlineVal.textContent = (dv >= 0 ? '+' : '') + dv + ' days';

        const newTasks = BL.total_tasks + sv;
        scopeAbs.textContent = BL.total_tasks + ' tasks → ' + newTasks + ' tasks';

        const newTeam = Math.max(BL.team_size + tv, 1);
        teamAbs.textContent = BL.team_size + ' → ' + newTeam + ' members';

        if (dv === 0) {
            deadlineAbs.textContent = 'No shift';
        } else {
            const weeks = Math.abs(dv / 7);
            deadlineAbs.textContent = (dv > 0 ? 'Extend ' : 'Shorten ') + weeks + ' week' + (weeks !== 1 ? 's' : '');
        }
    }

    scopeSlider.addEventListener('input', updateSliderLabels);
    teamSlider.addEventListener('input', updateSliderLabels);
    deadlineSlider.addEventListener('input', updateSliderLabels);

    // ── Reset ───────────────────────────────────────────────────
    btnReset.addEventListener('click', function () {
        scopeSlider.value = 0;
        teamSlider.value = 0;
        deadlineSlider.value = 0;
        updateSliderLabels();
        impactPanel.classList.remove('show');
        lastResults = null;
        lastParams = null;
    });

    // ── Analyze ─────────────────────────────────────────────────
    btnAnalyze.addEventListener('click', function () {
        const params = {
            tasks_added: parseInt(scopeSlider.value),
            team_size_delta: parseInt(teamSlider.value),
            deadline_shift_days: parseInt(deadlineSlider.value),
        };

        if (params.tasks_added === 0 && params.team_size_delta === 0 && params.deadline_shift_days === 0) {
            showToast('Move at least one slider to create a scenario.', 'warning');
            return;
        }

        lastParams = params;

        // Show panel with loading
        impactPanel.classList.add('show');
        impactLoading.style.display = 'block';
        impactResults.style.display = 'none';

        fetch(CFG.urls.simulate, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CFG.csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify(params),
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            impactLoading.style.display = 'none';
            if (data.success) {
                lastResults = data.results;
                renderResults(data.results);
                impactResults.style.display = 'block';
            } else {
                showToast(data.error || 'Simulation failed.', 'danger');
            }
        })
        .catch(function(err) {
            impactLoading.style.display = 'none';
            showToast('Network error: ' + err, 'danger');
        });
    });

    // ── Render results ──────────────────────────────────────────
    function renderResults(res) {
        renderWarnings(res.warnings || []);
        renderImpactTable(res.baseline, res.projected, res.deltas);
        renderFeasibility(res.feasibility_score);
        renderConflicts(res.new_conflicts || []);
        renderChart(res.baseline, res.projected);
        resetAISection();
    }

    function renderWarnings(warnings) {
        if (!warnings.length) { warningsArea.innerHTML = ''; return; }
        const items = warnings.map(function(w) { return '<li>' + w + '</li>'; }).join('');
        warningsArea.innerHTML =
            '<div class="alert alert-warning alert-dismissible fade show mb-3">' +
            '<strong><i class="fas fa-info-circle me-1"></i> Heads up:</strong>' +
            '<ul class="warning-list mb-0 mt-1">' + items + '</ul>' +
            '<button class="btn-close" data-bs-dismiss="alert"></button></div>';
    }

    function renderImpactTable(bl, proj, deltas) {
        const rows = [
            { label: 'Total Tasks', bl: fmt(bl.total_tasks), proj: fmt(proj.total_tasks), delta: signed(deltas.tasks), cls: deltaClass(deltas.tasks, true) },
            { label: 'Remaining Tasks', bl: fmt(bl.remaining_tasks), proj: fmt(proj.remaining_tasks), delta: signed(deltas.remaining), cls: deltaClass(deltas.remaining, true) },
            { label: 'Team Size', bl: fmt(bl.team_size), proj: fmt(proj.team_size), delta: signed(deltas.team_size), cls: deltaClass(deltas.team_size, false) },
            { label: 'Velocity (tasks/wk)', bl: fmt(bl.velocity_per_week), proj: fmt(proj.velocity_per_week), delta: signed(deltas.velocity), cls: deltaClass(deltas.velocity, false) },
            { label: 'Budget Spent', bl: bl.budget_currency + ' ' + fmt(bl.budget_spent), proj: proj.budget_currency + ' ' + fmt(proj.budget_spent), delta: signed(deltas.budget_spent, ''), cls: deltaClass(deltas.budget_spent, true) },
            { label: 'Budget Utilization', bl: fmt(bl.budget_utilization_pct) + '%', proj: fmt(proj.budget_utilization_pct) + '%', delta: signed(deltas.budget_utilization_pct, '%'), cls: deltaClass(deltas.budget_utilization_pct, true) },
            { label: 'Predicted Date', bl: bl.predicted_date || 'N/A', proj: proj.predicted_date || 'N/A', delta: signed(deltas.timeline_days, 'd'), cls: deltaClass(deltas.timeline_days, true) },
            { label: 'Delay Probability', bl: fmt(bl.delay_probability) + '%', proj: fmt(proj.delay_probability) + '%', delta: signed(deltas.delay_probability, '%'), cls: deltaClass(deltas.delay_probability, true) },
            { label: 'Risk Level', bl: riskBadge(bl.risk_level), proj: riskBadge(proj.risk_level), delta: '', cls: '' },
            { label: 'Team Utilization', bl: fmt(bl.utilization_pct) + '%', proj: fmt(proj.utilization_pct) + '%', delta: signed(deltas.utilization_pct, '%'), cls: deltaClass(deltas.utilization_pct, true) },
        ];

        var html = '';
        rows.forEach(function(r) {
            html += '<tr><td>' + r.label + '</td>' +
                '<td class="text-center">' + r.bl + '</td>' +
                '<td class="text-center">' + r.proj + '</td>' +
                '<td class="text-center ' + r.cls + '">' + r.delta + '</td></tr>';
        });
        document.getElementById('impact-tbody').innerHTML = html;
    }

    function renderFeasibility(score) {
        const pct = Math.round(score * 100);
        document.getElementById('feasibility-fill').style.width = pct + '%';
        document.getElementById('feasibility-label').textContent = pct + '%';
        const label = document.getElementById('feasibility-label');
        if (pct >= 70) label.className = 'fs-4 fw-bold text-success';
        else if (pct >= 40) label.className = 'fs-4 fw-bold text-warning';
        else label.className = 'fs-4 fw-bold text-danger';
    }

    function renderConflicts(conflicts) {
        const card = document.getElementById('conflicts-card');
        const body = document.getElementById('conflicts-body');
        if (!conflicts.length) { card.style.display = 'none'; return; }
        card.style.display = 'block';
        var html = '';
        conflicts.forEach(function(c) {
            html += '<div class="conflict-item ' + c.severity + '">' +
                '<span class="badge bg-' + (c.severity === 'critical' ? 'danger' : c.severity === 'high' ? 'warning' : 'info') +
                ' text-uppercase me-2">' + c.severity + '</span>' +
                '<span class="badge bg-secondary me-2 text-uppercase">' + c.type.replace(/_/g, ' ') + '</span>' +
                c.description + '</div>';
        });
        body.innerHTML = html;
    }

    function renderChart(bl, proj) {
        const ctx = document.getElementById('comparison-chart').getContext('2d');
        if (comparisonChart) comparisonChart.destroy();

        comparisonChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Delay Probability (%)', 'Budget Utilization (%)', 'Team Utilization (%)', 'Remaining Tasks'],
                datasets: [
                    {
                        label: 'Current',
                        data: [bl.delay_probability, bl.budget_utilization_pct, bl.utilization_pct, bl.remaining_tasks],
                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1,
                    },
                    {
                        label: 'Projected',
                        data: [proj.delay_probability, proj.budget_utilization_pct, proj.utilization_pct, proj.remaining_tasks],
                        backgroundColor: 'rgba(255, 99, 132, 0.7)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' },
                    title: { display: true, text: 'Current vs. Projected Key Metrics' },
                },
                scales: { y: { beginAtZero: true } },
            }
        });
    }

    // ── AI Analysis ─────────────────────────────────────────────
    function resetAISection() {
        document.getElementById('ai-trigger').style.display = 'block';
        document.getElementById('ai-loading').style.display = 'none';
        document.getElementById('ai-result-card').style.display = 'none';
    }

    btnAI.addEventListener('click', function () {
        if (!lastParams) return;
        document.getElementById('ai-trigger').style.display = 'none';
        document.getElementById('ai-loading').style.display = 'block';

        const payload = Object.assign({}, lastParams, { include_ai: true });

        fetch(CFG.urls.simulate, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CFG.csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify(payload),
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            document.getElementById('ai-loading').style.display = 'none';
            if (data.success && data.results.ai_analysis && !data.results.ai_analysis.error) {
                lastResults.ai_analysis = data.results.ai_analysis;
                renderAI(data.results.ai_analysis);
            } else {
                var errMsg = (data.results && data.results.ai_analysis && data.results.ai_analysis.error) || 'AI analysis failed.';
                showToast(errMsg, 'warning');
                document.getElementById('ai-trigger').style.display = 'block';
            }
        })
        .catch(function(err) {
            document.getElementById('ai-loading').style.display = 'none';
            document.getElementById('ai-trigger').style.display = 'block';
            showToast('AI request failed: ' + err, 'danger');
        });
    });

    function renderAI(ai) {
        var html = '';

        // Feasibility badge
        var fColor = ai.feasibility_assessment === 'High' ? 'success' : ai.feasibility_assessment === 'Medium' ? 'warning' : 'danger';
        html += '<div class="mb-3"><span class="badge bg-' + fColor + ' fs-6">Feasibility: ' + ai.feasibility_assessment + '</span>';
        if (ai.confidence !== undefined) {
            html += ' <span class="badge bg-secondary fs-6">Confidence: ' + Math.round(ai.confidence * 100) + '%</span>';
        }
        html += '</div>';

        // Risk summary
        html += '<h6 class="fw-bold">Risk Assessment</h6><p>' + (ai.risk_summary || '') + '</p>';

        // Trade-off analysis
        if (ai.trade_off_analysis) {
            html += '<h6 class="fw-bold">Trade-off Analysis</h6><p>' + ai.trade_off_analysis + '</p>';
        }

        // Mitigations
        if (ai.recommended_mitigations && ai.recommended_mitigations.length) {
            html += '<h6 class="fw-bold">Recommended Mitigations</h6><ul class="mitigation-list">';
            ai.recommended_mitigations.forEach(function(m) { html += '<li>' + m + '</li>'; });
            html += '</ul>';
        }

        // Alternative
        if (ai.alternative_suggestion) {
            html += '<div class="alert alert-info mt-3 mb-0"><i class="fas fa-lightbulb me-1"></i> <strong>Alternative Approach:</strong> ' + ai.alternative_suggestion + '</div>';
        }

        document.getElementById('ai-result-body').innerHTML = html;
        document.getElementById('ai-result-card').style.display = 'block';
    }

    // ── Save Scenario ───────────────────────────────────────────
    btnSave.addEventListener('click', function () {
        if (!lastResults) return;
        var modal = new bootstrap.Modal(document.getElementById('saveModal'));
        document.getElementById('scenario-name').value = '';
        modal.show();
    });

    btnConfirmSave.addEventListener('click', function () {
        var name = document.getElementById('scenario-name').value.trim();
        if (!name) { showToast('Please enter a scenario name.', 'warning'); return; }

        fetch(CFG.urls.save, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CFG.csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({
                name: name,
                input_parameters: lastParams,
                baseline_snapshot: lastResults.baseline,
                impact_results: lastResults,
                ai_analysis: lastResults.ai_analysis || {},
            }),
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var modal = bootstrap.Modal.getInstance(document.getElementById('saveModal'));
            if (modal) modal.hide();
            if (data.success) {
                showToast('Scenario "' + data.name + '" saved!', 'success');
                setTimeout(function() { location.reload(); }, 1200);
            } else {
                showToast(data.error || 'Save failed.', 'danger');
            }
        })
        .catch(function(err) {
            showToast('Save failed: ' + err, 'danger');
        });
    });

    // ── Load saved scenario ─────────────────────────────────────
    document.addEventListener('click', function (e) {
        var loadBtn = e.target.closest('.btn-load-scenario');
        if (loadBtn) {
            try {
                var params = JSON.parse(loadBtn.dataset.params);
                scopeSlider.value = params.tasks_added || 0;
                teamSlider.value = params.team_size_delta || 0;
                deadlineSlider.value = params.deadline_shift_days || 0;
                updateSliderLabels();
                showToast('Scenario loaded. Click "Analyze Impact" to run.', 'info');
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } catch (ex) {
                showToast('Could not load scenario parameters.', 'warning');
            }
        }

        var delBtn = e.target.closest('.btn-delete-scenario');
        if (delBtn) {
            if (!confirm('Delete this saved scenario?')) return;
            var sid = delBtn.dataset.id;
            var url = CFG.urls.deleteTpl.replace('{id}', sid);
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': CFG.csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    var item = delBtn.closest('.scenario-item');
                    if (item) item.remove();
                    showToast('Scenario deleted.', 'success');
                }
            });
        }
    });

    // ── Toast helper ────────────────────────────────────────────
    function showToast(msg, type) {
        type = type || 'info';
        // Use Bootstrap alert as simple toast at top of page
        var el = document.createElement('div');
        el.className = 'alert alert-' + type + ' alert-dismissible fade show position-fixed';
        el.style.cssText = 'top:80px;right:20px;z-index:9999;min-width:300px;max-width:450px;box-shadow:0 4px 12px rgba(0,0,0,.15);';
        el.innerHTML = msg + '<button class="btn-close" data-bs-dismiss="alert"></button>';
        document.body.appendChild(el);
        setTimeout(function () { el.remove(); }, 4000);
    }

    // ── Init ────────────────────────────────────────────────────
    updateSliderLabels();
})();
