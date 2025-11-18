/**
 * Risk Management Module for PrizmAI Kanban Board
 * 
 * This module provides AI-powered risk scoring, assessment, and mitigation features
 * Integrated with Google Gemini API for intelligent analysis
 */

// Risk Management Module
const RiskManagement = (() => {
    'use strict';

    // Configuration
    const CONFIG = {
        apiEndpoints: {
            calculateRisk: '/api/kanban/calculate-task-risk/',
            getMitigation: '/api/kanban/get-mitigation-suggestions/',
            assessDependencies: '/api/kanban/assess-task-dependencies/'
        },
        riskLevels: {
            1: { level: 'Low', color: '#28a745', bgColor: 'rgba(40, 167, 69, 0.1)' },
            2: { level: 'Medium', color: '#ffc107', bgColor: 'rgba(255, 193, 7, 0.1)' },
            3: { level: 'High', color: '#dc3545', bgColor: 'rgba(220, 53, 69, 0.1)' },
            4: { level: 'Critical', color: '#721c24', bgColor: 'rgba(114, 28, 36, 0.1)' }
        },
        strategyColors: {
            'Avoid': '#dc3545',
            'Mitigate': '#ffc107',
            'Transfer': '#17a2b8',
            'Accept': '#6c757d'
        }
    };

    /**
     * Initialize risk management features for a task
     */
    function initTaskRisk(taskElement) {
        const riskBadge = taskElement.querySelector('[data-risk-badge]');
        if (riskBadge) {
            riskBadge.addEventListener('click', (e) => {
                e.stopPropagation();
                showRiskDetails(taskElement);
            });
        }

        // Add risk assessment button
        const riskAssessBtn = taskElement.querySelector('[data-assess-risk]');
        if (riskAssessBtn) {
            riskAssessBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                assessTaskRisk(taskElement);
            });
        }

        // Add mitigation button
        const mitigationBtn = taskElement.querySelector('[data-get-mitigation]');
        if (mitigationBtn) {
            mitigationBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                getMitigationStrategies(taskElement);
            });
        }
    }

    /**
     * Calculate AI-powered risk score for a task
     */
    async function assessTaskRisk(taskElement) {
        const taskId = taskElement.dataset.taskId;
        const taskTitle = taskElement.querySelector('[data-task-title]')?.textContent || '';
        const taskDescription = taskElement.querySelector('[data-task-description]')?.textContent || '';
        const taskPriority = taskElement.dataset.taskPriority || 'medium';
        const boardId = document.querySelector('[data-board-id]')?.dataset.boardId;

        const assessBtn = taskElement.querySelector('[data-assess-risk]');
        const originalContent = assessBtn?.innerHTML;

        try {
            // Show loading state
            if (assessBtn) {
                assessBtn.disabled = true;
                assessBtn.innerHTML = '<span class="spinner-border spinner-border-sm mr-2"></span>Analyzing...';
            }

            const response = await fetch(CONFIG.apiEndpoints.calculateRisk, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    task_id: taskId,
                    title: taskTitle,
                    description: taskDescription,
                    priority: taskPriority,
                    board_id: boardId
                })
            });

            const data = await response.json();

            if (!response.ok) {
                showNotification('Error calculating risk: ' + data.error, 'danger');
                return;
            }

            if (data.success) {
                const analysis = data.risk_analysis;
                updateTaskRiskDisplay(taskElement, analysis);
                showRiskAnalysisModal(taskTitle, analysis);
                showNotification('Risk assessment completed successfully!', 'success');
            }
        } catch (error) {
            console.error('Error assessing risk:', error);
            showNotification('Failed to assess risk. Please try again.', 'danger');
        } finally {
            if (assessBtn) {
                assessBtn.disabled = false;
                assessBtn.innerHTML = originalContent;
            }
        }
    }

    /**
     * Update task display with risk information
     */
    function updateTaskRiskDisplay(taskElement, riskAnalysis) {
        const riskScore = riskAnalysis.risk_assessment?.risk_score || 0;
        const riskLevel = riskAnalysis.risk_assessment?.risk_level?.toLowerCase() || 'low';
        
        // Map risk score to risk level
        let riskLevelKey = 1;
        if (riskLevel === 'critical' || riskScore >= 7) riskLevelKey = 4;
        else if (riskLevel === 'high' || riskScore >= 5) riskLevelKey = 3;
        else if (riskLevel === 'medium' || riskScore >= 3) riskLevelKey = 2;

        const riskConfig = CONFIG.riskLevels[riskLevelKey];

        // Update or create risk badge
        let riskBadge = taskElement.querySelector('[data-risk-badge]');
        if (!riskBadge) {
            riskBadge = document.createElement('div');
            riskBadge.dataset.riskBadge = '';
            riskBadge.style.cursor = 'pointer';
            const taskHeader = taskElement.querySelector('.task-header');
            if (taskHeader) {
                taskHeader.appendChild(riskBadge);
            }
        }

        riskBadge.className = 'badge';
        riskBadge.style.backgroundColor = riskConfig.bgColor;
        riskBadge.style.color = riskConfig.color;
        riskBadge.style.borderLeft = `4px solid ${riskConfig.color}`;
        riskBadge.innerHTML = `
            <i class="bi bi-exclamation-triangle"></i>
            Risk: ${riskConfig.level} (${riskScore}/9)
        `;
        riskBadge.title = `Click for details`;

        // Add click handler to show details
        riskBadge.addEventListener('click', (e) => {
            e.stopPropagation();
            showRiskAnalysisModal(taskElement.querySelector('[data-task-title]')?.textContent, riskAnalysis);
        });

        // Store analysis in element
        taskElement.dataset.riskAnalysis = JSON.stringify(riskAnalysis);
        taskElement.dataset.riskScore = riskScore;
        taskElement.dataset.riskLevel = riskLevel;
    }

    /**
     * Display risk analysis modal
     */
    function showRiskAnalysisModal(taskTitle, riskAnalysis) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.setAttribute('tabindex', '-1');
        modal.innerHTML = `
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header bg-warning text-dark">
                        <h5 class="modal-title">
                            <i class="bi bi-exclamation-triangle"></i>
                            Risk Assessment: ${taskTitle}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        ${renderRiskAnalysisContent(riskAnalysis)}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" id="getMitigationBtn">
                            <i class="bi bi-shield-check"></i> Get Mitigation Strategies
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        // Handle mitigation button
        modal.querySelector('#getMitigationBtn').addEventListener('click', () => {
            bsModal.hide();
            showMitigationModal(taskTitle, riskAnalysis);
        });

        // Clean up when hidden
        modal.addEventListener('hidden.bs.modal', () => {
            modal.remove();
        });
    }

    /**
     * Render risk analysis content HTML with enhanced explainability
     */
    function renderRiskAnalysisContent(riskAnalysis) {
        const likelihood = riskAnalysis.likelihood || {};
        const impact = riskAnalysis.impact || {};
        const assessment = riskAnalysis.risk_assessment || {};
        const indicators = riskAnalysis.risk_indicators || [];

        // Use AIExplainability module for enhanced visualization
        let html = `<div class="container-fluid">`;

        // Add AI Confidence Meter at the top
        if (riskAnalysis.confidence_score !== undefined) {
            html += `
                <div class="row mb-4">
                    <div class="col-12">
                        ${AIExplainability.renderConfidenceMeter(
                            riskAnalysis.confidence_score, 
                            'AI Analysis Confidence'
                        )}
                    </div>
                </div>
            `;
        }

        // Risk Scores Overview
        html += `
            <div class="row mb-4">
                <div class="col-md-4">
                    <div class="card border-warning">
                        <div class="card-body text-center">
                            <h6 class="text-muted">Likelihood</h6>
                            <div class="display-5 text-warning">${likelihood.score || '-'}</div>
                            <small class="text-muted">${likelihood.percentage_range || '-'}</small>
                            ${likelihood.confidence ? `
                                <div class="mt-2">
                                    <small class="text-muted">Confidence: ${Math.round(likelihood.confidence * 100)}%</small>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card border-danger">
                        <div class="card-body text-center">
                            <h6 class="text-muted">Impact</h6>
                            <div class="display-5 text-danger">${impact.score || '-'}</div>
                            <small class="text-muted">${impact.severity_level || '-'}</small>
                            ${impact.confidence ? `
                                <div class="mt-2">
                                    <small class="text-muted">Confidence: ${Math.round(impact.confidence * 100)}%</small>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card border-info">
                        <div class="card-body text-center">
                            <h6 class="text-muted">Overall Risk</h6>
                            <div class="display-5 text-info">${assessment.risk_score || '-'}/9</div>
                            <small class="text-muted">${assessment.risk_level || '-'}</small>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Calculation Explanation
        if (assessment) {
            html += `
                <div class="row mb-4">
                    <div class="col-12">
                        ${AIExplainability.renderCalculationExplanation({
                            ...assessment,
                            likelihood: likelihood.score,
                            impact: impact.score
                        })}
                    </div>
                </div>
            `;
        }

        // Contributing Factors Breakdown
        if (assessment.contributing_factors && assessment.contributing_factors.length > 0) {
            html += `
                <div class="row mb-4">
                    <div class="col-12">
                        ${AIExplainability.renderFactorBreakdown(assessment.contributing_factors)}
                    </div>
                </div>
            `;
        }

        // Impact Breakdown
        if (impact.impact_breakdown) {
            html += `
                <div class="row mb-4">
                    <div class="col-12">
                        ${AIExplainability.renderImpactBreakdown(impact.impact_breakdown)}
                    </div>
                </div>
            `;
        }

        // Detailed Analysis Cards
        html += `
            <div class="row mb-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header bg-light">
                            <h6 class="mb-0"><i class="bi bi-graph-up"></i> Likelihood Analysis</h6>
                        </div>
                        <div class="card-body">
                            <p><strong>Reasoning:</strong></p>
                            <p>${likelihood.reasoning || 'N/A'}</p>
                            <p><strong>Key Factors:</strong></p>
                            <ul>
                                ${(likelihood.key_factors || []).map(f => `<li>${AIExplainability.escapeHtml(f)}</li>`).join('')}
                            </ul>
                            ${likelihood.factor_weights ? `
                                <p><strong>Factor Weights:</strong></p>
                                <ul class="small">
                                    ${Object.entries(likelihood.factor_weights).map(([k, v]) => 
                                        `<li>${AIExplainability.escapeHtml(k)}: ${(v * 100).toFixed(0)}%</li>`
                                    ).join('')}
                                </ul>
                            ` : ''}
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header bg-light">
                            <h6 class="mb-0"><i class="bi bi-exclamation-triangle"></i> Impact Analysis</h6>
                        </div>
                        <div class="card-body">
                            <p><strong>Reasoning:</strong></p>
                            <p>${impact.reasoning || 'N/A'}</p>
                            <p><strong>Affected Areas:</strong></p>
                            <ul>
                                ${(impact.affected_areas || []).map(a => `<li>${AIExplainability.escapeHtml(a)}</li>`).join('')}
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Risk Indicators
        if (indicators.length > 0) {
            html += `
                <div class="row mb-4">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header bg-light">
                                <h6 class="mb-0"><i class="bi bi-clipboard-check"></i> Risk Indicators to Monitor</h6>
                            </div>
                            <div class="card-body">
                                <div class="table-responsive">
                                    <table class="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>Indicator</th>
                                                <th>Frequency</th>
                                                <th>Alert Threshold</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${indicators.map(ind => `
                                                <tr>
                                                    <td>${AIExplainability.escapeHtml(ind.indicator || '-')}</td>
                                                    <td><small class="badge bg-info">${AIExplainability.escapeHtml(ind.frequency || '-')}</small></td>
                                                    <td><small class="badge bg-warning">${AIExplainability.escapeHtml(ind.threshold || '-')}</small></td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        // Model Assumptions and Limitations
        if (riskAnalysis.explainability) {
            html += `
                <div class="row mb-4">
                    <div class="col-12">
                        ${AIExplainability.renderAssumptionsAndLimitations(riskAnalysis.explainability)}
                    </div>
                </div>
            `;
        }

        html += '</div>';
        return html;
    }
    }

    /**
     * Get mitigation strategies for a task
     */
    async function getMitigationStrategies(taskElement) {
        const taskId = taskElement.dataset.taskId;
        const taskTitle = taskElement.querySelector('[data-task-title]')?.textContent || '';
        const taskDescription = taskElement.querySelector('[data-task-description]')?.textContent || '';
        const boardId = document.querySelector('[data-board-id]')?.dataset.boardId;
        const riskAnalysis = JSON.parse(taskElement.dataset.riskAnalysis || '{}');

        const mitigationBtn = taskElement.querySelector('[data-get-mitigation]');
        const originalContent = mitigationBtn?.innerHTML;

        try {
            if (mitigationBtn) {
                mitigationBtn.disabled = true;
                mitigationBtn.innerHTML = '<span class="spinner-border spinner-border-sm mr-2"></span>Generating...';
            }

            const response = await fetch(CONFIG.apiEndpoints.getMitigation, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    task_id: taskId,
                    title: taskTitle,
                    description: taskDescription,
                    risk_likelihood: riskAnalysis.likelihood?.score || 2,
                    risk_impact: riskAnalysis.impact?.score || 2,
                    risk_indicators: riskAnalysis.risk_indicators || [],
                    board_id: boardId
                })
            });

            const data = await response.json();

            if (!response.ok) {
                showNotification('Error getting mitigation strategies: ' + data.error, 'danger');
                return;
            }

            if (data.success) {
                showMitigationModal(taskTitle, riskAnalysis, data.mitigation_suggestions);
                showNotification('Mitigation strategies generated!', 'success');
            }
        } catch (error) {
            console.error('Error getting mitigation strategies:', error);
            showNotification('Failed to get mitigation strategies. Please try again.', 'danger');
        } finally {
            if (mitigationBtn) {
                mitigationBtn.disabled = false;
                mitigationBtn.innerHTML = originalContent;
            }
        }
    }

    /**
     * Display mitigation strategies modal
     */
    function showMitigationModal(taskTitle, riskAnalysis, mitigationSuggestions) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.setAttribute('tabindex', '-1');
        modal.innerHTML = `
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header bg-success text-white">
                        <h5 class="modal-title">
                            <i class="bi bi-shield-check"></i>
                            Mitigation Strategies for: ${taskTitle}
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        ${renderMitigationContent(mitigationSuggestions)}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        // Clean up when hidden
        modal.addEventListener('hidden.bs.modal', () => {
            modal.remove();
        });
    }

    /**
     * Render mitigation strategies content
     */
    function renderMitigationContent(suggestions) {
        if (!suggestions || suggestions.length === 0) {
            return '<div class="alert alert-info">No mitigation strategies available.</div>';
        }

        return `
            <div class="container-fluid">
                ${suggestions.map((strategy, idx) => {
                    const strategyType = strategy.strategy_type || 'Mitigate';
                    const color = CONFIG.strategyColors[strategyType] || '#6c757d';
                    return `
                        <div class="card mb-3 border-left" style="border-left: 4px solid ${color}">
                            <div class="card-header">
                                <div class="row align-items-center">
                                    <div class="col">
                                        <h6 class="mb-0">
                                            <span class="badge" style="background-color: ${color}">
                                                ${strategyType}
                                            </span>
                                            ${strategy.title || 'Strategy ' + (idx + 1)}
                                        </h6>
                                    </div>
                                    <div class="col-auto">
                                        <small class="text-muted">
                                            Effectiveness: <strong>${strategy.estimated_effectiveness || 'N/A'}%</strong>
                                        </small>
                                    </div>
                                </div>
                            </div>
                            <div class="card-body">
                                <p>${strategy.description || ''}</p>
                                ${strategy.action_steps && strategy.action_steps.length > 0 ? `
                                    <div class="mb-3">
                                        <h6>Action Steps:</h6>
                                        <ol>
                                            ${strategy.action_steps.map(step => `<li>${step}</li>`).join('')}
                                        </ol>
                                    </div>
                                ` : ''}
                                <div class="row">
                                    <div class="col-md-6">
                                        <p><strong>Timeline:</strong> ${strategy.timeline || 'N/A'}</p>
                                    </div>
                                    <div class="col-md-6">
                                        <p><strong>Resources Needed:</strong> ${strategy.resources_required || 'N/A'}</p>
                                    </div>
                                </div>
                                <p>
                                    <strong>Priority:</strong>
                                    <span class="badge" style="background-color: 
                                        ${strategy.priority === 'high' ? '#dc3545' : 
                                          strategy.priority === 'medium' ? '#ffc107' : '#28a745'}">
                                        ${strategy.priority?.toUpperCase() || 'MEDIUM'}
                                    </span>
                                </p>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    /**
     * Show risk details for a task
     */
    function showRiskDetails(taskElement) {
        const riskAnalysis = JSON.parse(taskElement.dataset.riskAnalysis || '{}');
        const taskTitle = taskElement.querySelector('[data-task-title]')?.textContent || 'Task';
        
        if (Object.keys(riskAnalysis).length > 0) {
            showRiskAnalysisModal(taskTitle, riskAnalysis);
        } else {
            showNotification('No risk assessment available. Click assess risk first.', 'info');
        }
    }

    /**
     * Get CSRF token
     */
    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
               document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
    }

    /**
     * Show notification
     */
    function showNotification(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.style.position = 'fixed';
        alertDiv.style.top = '20px';
        alertDiv.style.right = '20px';
        alertDiv.style.zIndex = '9999';
        alertDiv.style.minWidth = '300px';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        document.body.appendChild(alertDiv);

        // Auto dismiss after 5 seconds
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }

    /**
     * Initialize all risk elements on page
     */
    function initAll() {
        document.querySelectorAll('[data-task-card]').forEach(taskElement => {
            initTaskRisk(taskElement);
        });
    }

    // Public API
    return {
        init: initAll,
        initTask: initTaskRisk,
        assessRisk: assessTaskRisk,
        getMitigation: getMitigationStrategies,
        showRiskDetails: showRiskDetails,
        updateDisplay: updateTaskRiskDisplay
    };
})();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', RiskManagement.init);
} else {
    RiskManagement.init();
}
