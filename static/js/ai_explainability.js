/**
 * AI Explainability Module for PrizmAI
 * 
 * Provides reusable components and utilities for explaining AI decisions
 * Implements "Explainable AI" best practices for transparency and trust
 */

const AIExplainability = (() => {
    'use strict';

    /**
     * Render a confidence meter visualization
     * @param {number} confidence - Confidence score (0-1)
     * @param {string} label - Label for the meter
     * @returns {string} HTML string
     */
    function renderConfidenceMeter(confidence, label = 'Confidence') {
        const percentage = Math.round(confidence * 100);
        let colorClass = 'bg-success';
        let textClass = 'text-success';
        
        if (confidence < 0.5) {
            colorClass = 'bg-danger';
            textClass = 'text-danger';
        } else if (confidence < 0.75) {
            colorClass = 'bg-warning';
            textClass = 'text-warning';
        }

        return `
            <div class="confidence-meter mb-3">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="fw-bold">${label}</span>
                    <span class="${textClass} fw-bold">${percentage}%</span>
                </div>
                <div class="progress" style="height: 8px;">
                    <div class="progress-bar ${colorClass}" 
                         role="progressbar" 
                         style="width: ${percentage}%"
                         aria-valuenow="${percentage}" 
                         aria-valuemin="0" 
                         aria-valuemax="100">
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render factor contribution breakdown
     * @param {Array} factors - Array of factor objects with {factor, contribution_percentage, description}
     * @returns {string} HTML string
     */
    function renderFactorBreakdown(factors) {
        if (!factors || factors.length === 0) {
            return '<p class="text-muted">No factor breakdown available</p>';
        }

        // Sort factors by contribution
        const sortedFactors = [...factors].sort((a, b) => 
            (b.contribution_percentage || 0) - (a.contribution_percentage || 0)
        );

        let html = `
            <div class="factor-breakdown">
                <h6 class="fw-bold mb-3">
                    <i class="bi bi-pie-chart"></i> Contributing Factors
                </h6>
        `;

        sortedFactors.forEach((factor, index) => {
            const contribution = factor.contribution_percentage || 0;
            const barWidth = Math.max(5, contribution); // Minimum 5% for visibility
            
            // Color based on contribution level
            let barColor = '#6c757d'; // Gray for low
            if (contribution >= 30) barColor = '#dc3545'; // Red for high
            else if (contribution >= 15) barColor = '#ffc107'; // Yellow for medium

            html += `
                <div class="factor-item mb-3">
                    <div class="d-flex justify-content-between align-items-start mb-1">
                        <div class="factor-name fw-semibold" style="flex: 1;">
                            <span class="badge bg-secondary me-1">${index + 1}</span>
                            ${escapeHtml(factor.factor)}
                        </div>
                        <div class="factor-contribution fw-bold" style="color: ${barColor};">
                            ${contribution}%
                        </div>
                    </div>
                    ${factor.description ? `
                        <div class="factor-description text-muted small mb-2">
                            ${escapeHtml(factor.description)}
                        </div>
                    ` : ''}
                    <div class="progress" style="height: 6px;">
                        <div class="progress-bar" 
                             style="width: ${barWidth}%; background-color: ${barColor};"
                             role="progressbar">
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        return html;
    }

    /**
     * Render calculation method explanation
     * @param {Object} assessment - Risk assessment object
     * @returns {string} HTML string
     */
    function renderCalculationExplanation(assessment) {
        if (!assessment) return '';

        const { risk_score, calculation_method, likelihood, impact } = assessment;

        return `
            <div class="calculation-explanation card bg-light mb-3">
                <div class="card-body">
                    <h6 class="card-title fw-bold">
                        <i class="bi bi-calculator"></i> How We Calculated This
                    </h6>
                    <div class="calculation-formula">
                        ${calculation_method || `Likelihood × Impact = Risk Score`}
                    </div>
                    <div class="calculation-breakdown mt-2">
                        <div class="row text-center">
                            <div class="col-4">
                                <div class="metric-box">
                                    <div class="metric-label text-muted small">Likelihood</div>
                                    <div class="metric-value display-6">${likelihood || '?'}</div>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="metric-box">
                                    <div class="metric-label text-muted small">Impact</div>
                                    <div class="metric-value display-6">${impact || '?'}</div>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="metric-box">
                                    <div class="metric-label text-muted small">Risk Score</div>
                                    <div class="metric-value display-6 text-danger">${risk_score || '?'}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render impact breakdown visualization
     * @param {Object} impactBreakdown - Object with {timeline, resources, quality, stakeholders}
     * @returns {string} HTML string
     */
    function renderImpactBreakdown(impactBreakdown) {
        if (!impactBreakdown) return '';

        const impacts = [
            { label: 'Timeline', value: impactBreakdown.timeline, icon: 'clock' },
            { label: 'Resources', value: impactBreakdown.resources, icon: 'people' },
            { label: 'Quality', value: impactBreakdown.quality, icon: 'star' },
            { label: 'Stakeholders', value: impactBreakdown.stakeholders, icon: 'person-check' }
        ];

        return `
            <div class="impact-breakdown mb-3">
                <h6 class="fw-bold mb-3">
                    <i class="bi bi-target"></i> Impact Breakdown
                </h6>
                <div class="row">
                    ${impacts.map(impact => {
                        const percentage = Math.round((impact.value || 0) * 100);
                        let colorClass = 'text-success';
                        if (percentage >= 70) colorClass = 'text-danger';
                        else if (percentage >= 40) colorClass = 'text-warning';

                        return `
                            <div class="col-6 mb-3">
                                <div class="impact-item">
                                    <div class="d-flex align-items-center mb-1">
                                        <i class="bi bi-${impact.icon} me-2"></i>
                                        <span class="small">${impact.label}</span>
                                    </div>
                                    <div class="d-flex align-items-center">
                                        <div class="progress flex-grow-1" style="height: 6px;">
                                            <div class="progress-bar ${colorClass.replace('text-', 'bg-')}" 
                                                 style="width: ${percentage}%">
                                            </div>
                                        </div>
                                        <span class="${colorClass} fw-bold ms-2 small">${percentage}%</span>
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }

    /**
     * Render model assumptions and limitations
     * @param {Object} explainability - Explainability object with assumptions, limitations
     * @returns {string} HTML string
     */
    function renderAssumptionsAndLimitations(explainability) {
        if (!explainability) return '';

        const { model_assumptions, data_limitations, alternative_interpretations } = explainability;

        return `
            <div class="accordion accordion-flush" id="explainabilityAccordion">
                ${model_assumptions && model_assumptions.length > 0 ? `
                    <div class="accordion-item">
                        <h2 class="accordion-header">
                            <button class="accordion-button collapsed" type="button" 
                                    data-bs-toggle="collapse" data-bs-target="#assumptionsCollapse">
                                <i class="bi bi-lightbulb me-2"></i> Model Assumptions
                            </button>
                        </h2>
                        <div id="assumptionsCollapse" class="accordion-collapse collapse" 
                             data-bs-parent="#explainabilityAccordion">
                            <div class="accordion-body">
                                <ul class="mb-0">
                                    ${model_assumptions.map(a => `<li>${escapeHtml(a)}</li>`).join('')}
                                </ul>
                            </div>
                        </div>
                    </div>
                ` : ''}
                
                ${data_limitations && data_limitations.length > 0 ? `
                    <div class="accordion-item">
                        <h2 class="accordion-header">
                            <button class="accordion-button collapsed" type="button" 
                                    data-bs-toggle="collapse" data-bs-target="#limitationsCollapse">
                                <i class="bi bi-exclamation-triangle me-2"></i> Data Limitations
                            </button>
                        </h2>
                        <div id="limitationsCollapse" class="accordion-collapse collapse" 
                             data-bs-parent="#explainabilityAccordion">
                            <div class="accordion-body">
                                <ul class="mb-0">
                                    ${data_limitations.map(l => `<li>${escapeHtml(l)}</li>`).join('')}
                                </ul>
                            </div>
                        </div>
                    </div>
                ` : ''}
                
                ${alternative_interpretations && alternative_interpretations.length > 0 ? `
                    <div class="accordion-item">
                        <h2 class="accordion-header">
                            <button class="accordion-button collapsed" type="button" 
                                    data-bs-toggle="collapse" data-bs-target="#alternativesCollapse">
                                <i class="bi bi-arrow-left-right me-2"></i> Alternative Interpretations
                            </button>
                        </h2>
                        <div id="alternativesCollapse" class="accordion-collapse collapse" 
                             data-bs-parent="#explainabilityAccordion">
                            <div class="accordion-body">
                                <ul class="mb-0">
                                    ${alternative_interpretations.map(i => `<li>${escapeHtml(i)}</li>`).join('')}
                                </ul>
                            </div>
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Render a complete explainability panel
     * @param {Object} analysis - Full AI analysis with explainability data
     * @param {Object} options - Rendering options
     * @returns {string} HTML string
     */
    function renderExplainabilityPanel(analysis, options = {}) {
        const {
            showConfidence = true,
            showFactors = true,
            showCalculation = true,
            showImpact = true,
            showAssumptions = true
        } = options;

        let html = '<div class="explainability-panel">';

        // Confidence Score
        if (showConfidence && analysis.confidence_score !== undefined) {
            html += renderConfidenceMeter(analysis.confidence_score, 'AI Confidence');
        }

        // Calculation Explanation
        if (showCalculation && analysis.risk_assessment) {
            const assessment = {
                ...analysis.risk_assessment,
                likelihood: analysis.likelihood?.score,
                impact: analysis.impact?.score
            };
            html += renderCalculationExplanation(assessment);
        }

        // Factor Breakdown
        if (showFactors && analysis.risk_assessment?.contributing_factors) {
            html += renderFactorBreakdown(analysis.risk_assessment.contributing_factors);
        }

        // Impact Breakdown
        if (showImpact && analysis.impact?.impact_breakdown) {
            html += renderImpactBreakdown(analysis.impact.impact_breakdown);
        }

        // Assumptions and Limitations
        if (showAssumptions && analysis.explainability) {
            html += `
                <div class="mt-4">
                    <h6 class="fw-bold mb-3">
                        <i class="bi bi-info-circle"></i> Understanding This Analysis
                    </h6>
                    ${renderAssumptionsAndLimitations(analysis.explainability)}
                </div>
            `;
        }

        html += '</div>';
        return html;
    }

    /**
     * Render skill match explanation
     * @param {Object} skillMatch - Skill match data with breakdown
     * @returns {string} HTML string
     */
    function renderSkillMatchExplanation(skillMatch) {
        const { score, required_skills, user_skills, match_breakdown } = skillMatch;

        return `
            <div class="skill-match-explanation">
                <h6 class="fw-bold mb-3">
                    <i class="bi bi-person-check"></i> Why This Person?
                </h6>
                
                ${renderConfidenceMeter(score / 100, 'Skill Match Score')}
                
                <div class="skill-comparison mt-3">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>Required Skill</th>
                                <th>Level Needed</th>
                                <th>User Has</th>
                                <th>Match</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${required_skills.map((req, idx) => {
                                const userSkill = user_skills.find(s => s.name === req.name);
                                const match = match_breakdown?.[idx] || { match: false, score: 0 };
                                const matchIcon = match.match ? 
                                    '<i class="bi bi-check-circle text-success"></i>' : 
                                    '<i class="bi bi-x-circle text-danger"></i>';
                                
                                return `
                                    <tr>
                                        <td>${escapeHtml(req.name)}</td>
                                        <td>${escapeHtml(req.level)}</td>
                                        <td>${userSkill ? escapeHtml(userSkill.level) : 'None'}</td>
                                        <td>${matchIcon} ${Math.round(match.score)}%</td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }

    /**
     * Render deadline prediction explanation
     * @param {Object} prediction - Prediction data with reasoning
     * @returns {string} HTML string
     */
    function renderDeadlinePredictionExplanation(prediction) {
        const { 
            recommended_deadline, 
            confidence_level, 
            reasoning, 
            assumptions,
            velocity_data,
            risk_factors 
        } = prediction;

        return `
            <div class="deadline-prediction-explanation">
                <h6 class="fw-bold mb-3">
                    <i class="bi bi-calendar-check"></i> Why This Deadline?
                </h6>
                
                <div class="alert alert-info mb-3">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>Recommended Deadline:</strong> ${formatDate(recommended_deadline)}
                        </div>
                        <div>
                            <span class="badge bg-primary">${confidence_level}</span>
                        </div>
                    </div>
                </div>

                <div class="reasoning-section mb-3">
                    <h6 class="small fw-bold text-muted">REASONING</h6>
                    <p>${escapeHtml(reasoning)}</p>
                </div>

                ${velocity_data ? `
                    <div class="velocity-section mb-3">
                        <h6 class="small fw-bold text-muted">VELOCITY ANALYSIS</h6>
                        <div class="row text-center">
                            <div class="col-4">
                                <div class="small text-muted">Current Velocity</div>
                                <div class="fw-bold">${velocity_data.current_velocity} h/day</div>
                            </div>
                            <div class="col-4">
                                <div class="small text-muted">Expected Velocity</div>
                                <div class="fw-bold">${velocity_data.expected_velocity} h/day</div>
                            </div>
                            <div class="col-4">
                                <div class="small text-muted">Remaining Effort</div>
                                <div class="fw-bold">${velocity_data.remaining_hours}h</div>
                            </div>
                        </div>
                    </div>
                ` : ''}

                ${assumptions && assumptions.length > 0 ? `
                    <div class="assumptions-section mb-3">
                        <h6 class="small fw-bold text-muted">KEY ASSUMPTIONS</h6>
                        <ul class="small mb-0">
                            ${assumptions.map(a => `<li>${escapeHtml(a)}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}

                ${risk_factors && risk_factors.length > 0 ? `
                    <div class="risk-factors-section">
                        <h6 class="small fw-bold text-muted text-warning">RISK FACTORS</h6>
                        <ul class="small mb-0 text-warning">
                            ${risk_factors.map(r => `<li>${escapeHtml(r)}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Utility: Escape HTML to prevent XSS
     */
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Utility: Format date
     */
    function formatDate(dateString) {
        if (!dateString) return 'Not set';
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', { 
                year: 'numeric', 
                month: 'short', 
                day: 'numeric' 
            });
        } catch {
            return dateString;
        }
    }

    // Public API
    return {
        renderConfidenceMeter,
        renderFactorBreakdown,
        renderCalculationExplanation,
        renderImpactBreakdown,
        renderAssumptionsAndLimitations,
        renderExplainabilityPanel,
        renderSkillMatchExplanation,
        renderDeadlinePredictionExplanation,
        escapeHtml,
        formatDate
    };
})();

// Make available globally
window.AIExplainability = AIExplainability;
