/**
 * AI Explainability Module for PrizmAI
 * 
 * Provides reusable components and utilities for explaining AI decisions
 * Implements "Explainable AI" best practices for transparency and trust
 * 
 * Enhanced version with comprehensive explainability rendering
 */

const AIExplainability = (() => {
    'use strict';

    /**
     * Render a confidence meter visualization
     * @param {number} confidence - Confidence score (0-1)
     * @param {string} label - Label for the meter
     * @param {string} reasoning - Optional reasoning text
     * @returns {string} HTML string
     */
    function renderConfidenceMeter(confidence, label = 'Confidence', reasoning = '') {
        const percentage = Math.round(confidence * 100);
        let colorClass = 'bg-success';
        let textClass = 'text-success';
        let levelText = 'High';
        
        if (confidence < 0.5) {
            colorClass = 'bg-danger';
            textClass = 'text-danger';
            levelText = 'Low';
        } else if (confidence < 0.75) {
            colorClass = 'bg-warning';
            textClass = 'text-warning';
            levelText = 'Medium';
        }

        return `
            <div class="confidence-meter mb-3">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="fw-bold">
                        <i class="bi bi-speedometer2 me-1"></i>${label}
                    </span>
                    <span class="${textClass} fw-bold">${percentage}% <small class="text-muted">(${levelText})</small></span>
                </div>
                <div class="progress" style="height: 10px;">
                    <div class="progress-bar ${colorClass}" 
                         role="progressbar" 
                         style="width: ${percentage}%"
                         aria-valuenow="${percentage}" 
                         aria-valuemin="0" 
                         aria-valuemax="100">
                    </div>
                </div>
                ${reasoning ? `<small class="text-muted d-block mt-1"><i class="bi bi-info-circle me-1"></i>${escapeHtml(reasoning)}</small>` : ''}
            </div>
        `;
    }

    /**
     * Render a quick explainability badge that can be clicked for more info
     * @param {Object} data - Contains confidence_score and quick summary
     * @returns {string} HTML string
     */
    function renderExplainabilityBadge(data) {
        if (!data || data.confidence_score === undefined) return '';
        
        const confidence = data.confidence_score;
        const percentage = Math.round(confidence * 100);
        let colorClass = 'success';
        
        if (confidence < 0.5) colorClass = 'danger';
        else if (confidence < 0.75) colorClass = 'warning';
        
        return `
            <span class="explainability-badge badge bg-${colorClass} cursor-pointer" 
                  data-bs-toggle="tooltip" 
                  title="AI Confidence: ${percentage}%. Click for details."
                  onclick="AIExplainability.showExplainabilityModal(this)"
                  data-explainability='${JSON.stringify(data).replace(/'/g, "&#39;")}'>
                <i class="bi bi-lightbulb"></i> ${percentage}%
            </span>
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
                        <div class="factor-name fw-semibold" style="flex: 1; color: #212529;">
                            <span class="badge bg-secondary me-1">${index + 1}</span>
                            ${escapeHtml(factor.factor)}
                        </div>
                        <div class="factor-contribution fw-bold" style="color: ${barColor};">
                            ${contribution}%
                        </div>
                    </div>
                    ${factor.description ? `
                        <div class="factor-description small mb-2" style="color: #6c757d;">
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
        // Validate that we have meaningful analysis data
        if (!analysis || Object.keys(analysis).length === 0) {
            return `
                <div class="alert alert-warning">
                    <h6 class="alert-heading"><i class="bi bi-exclamation-triangle me-2"></i>No Analysis Data Available</h6>
                    <p class="mb-0">Risk analysis data is not available for this task. The AI may still be processing the analysis.</p>
                </div>
            `;
        }
        
        // Check if we have the essential data structures
        const hasEssentialData = analysis.risk_assessment || analysis.likelihood || analysis.impact;
        if (!hasEssentialData) {
            return `
                <div class="alert alert-warning">
                    <h6 class="alert-heading"><i class="bi bi-exclamation-triangle me-2"></i>Incomplete Analysis Data</h6>
                    <p class="mb-0">The risk analysis is incomplete. Please try refreshing or contact support if the issue persists.</p>
                </div>
            `;
        }
        
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
     * Render reasoning section with structured explanation
     * @param {Object} reasoning - Reasoning object with method, factors, justification
     * @returns {string} HTML string
     */
    function renderReasoningSection(reasoning) {
        if (!reasoning) return '';

        return `
            <div class="reasoning-section card bg-light mb-3">
                <div class="card-body">
                    <h6 class="card-title fw-bold mb-3">
                        <i class="bi bi-chat-quote"></i> Why This Recommendation?
                    </h6>
                    
                    ${reasoning.methodology ? `
                        <div class="mb-3">
                            <span class="badge bg-secondary mb-1">Methodology</span>
                            <p class="small mb-0">${escapeHtml(reasoning.methodology)}</p>
                        </div>
                    ` : ''}
                    
                    ${reasoning.key_factors && reasoning.key_factors.length > 0 ? `
                        <div class="mb-3">
                            <span class="badge bg-primary mb-2">Key Factors Considered</span>
                            <div class="list-group list-group-flush">
                                ${reasoning.key_factors.map(f => `
                                    <div class="list-group-item bg-transparent px-0 py-2 border-0 border-bottom">
                                        <div class="d-flex justify-content-between align-items-start">
                                            <div>
                                                <strong class="small">${escapeHtml(f.factor)}</strong>
                                                ${f.description ? `<p class="small text-muted mb-0">${escapeHtml(f.description)}</p>` : ''}
                                            </div>
                                            ${f.contribution_percentage !== undefined ? `
                                                <span class="badge bg-${f.contribution_percentage > 25 ? 'danger' : f.contribution_percentage > 10 ? 'warning' : 'secondary'}">
                                                    ${f.contribution_percentage}%
                                                </span>
                                            ` : ''}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                    
                    ${reasoning.confidence_justification ? `
                        <div class="alert alert-info small py-2 mb-0">
                            <i class="bi bi-shield-check me-1"></i>
                            <strong>Confidence basis:</strong> ${escapeHtml(reasoning.confidence_justification)}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    /**
     * Render action items with explainability
     * @param {Array} actions - Array of action objects with rationale
     * @returns {string} HTML string
     */
    function renderActionItems(actions) {
        if (!actions || actions.length === 0) return '';

        return `
            <div class="action-items mb-3">
                <h6 class="fw-bold mb-3">
                    <i class="bi bi-list-check"></i> Recommended Actions
                </h6>
                <div class="list-group">
                    ${actions.map((action, idx) => `
                        <div class="list-group-item">
                            <div class="d-flex w-100 justify-content-between align-items-start">
                                <div>
                                    <span class="badge bg-primary rounded-pill me-2">${idx + 1}</span>
                                    <strong>${escapeHtml(action.action || action.title || action)}</strong>
                                </div>
                                ${action.urgency ? `
                                    <span class="badge bg-${action.urgency === 'immediate' ? 'danger' : action.urgency === 'this_week' ? 'warning' : 'secondary'}">
                                        ${action.urgency.replace('_', ' ')}
                                    </span>
                                ` : ''}
                            </div>
                            ${action.rationale || action.reasoning ? `
                                <p class="small text-muted mt-2 mb-1">
                                    <i class="bi bi-arrow-return-right me-1"></i>
                                    <em>Why:</em> ${escapeHtml(action.rationale || action.reasoning)}
                                </p>
                            ` : ''}
                            ${action.expected_outcome ? `
                                <p class="small text-success mb-0">
                                    <i class="bi bi-check2-circle me-1"></i>
                                    <em>Expected outcome:</em> ${escapeHtml(action.expected_outcome)}
                                </p>
                            ` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    /**
     * Render alternatives comparison
     * @param {Array} alternatives - Array of alternative options
     * @returns {string} HTML string
     */
    function renderAlternatives(alternatives) {
        if (!alternatives || alternatives.length === 0) return '';

        return `
            <div class="alternatives-section mb-3">
                <h6 class="fw-bold mb-3">
                    <i class="bi bi-arrows-angle-expand"></i> Alternative Approaches
                </h6>
                <div class="row">
                    ${alternatives.map(alt => `
                        <div class="col-md-6 mb-2">
                            <div class="card h-100 border-secondary">
                                <div class="card-body py-2">
                                    <h6 class="card-title small mb-1">
                                        ${escapeHtml(alt.approach || alt.alternative || alt.interpretation)}
                                    </h6>
                                    ${alt.tradeoff || alt.would_change ? `
                                        <p class="small text-muted mb-0">
                                            <i class="bi bi-arrow-left-right me-1"></i>
                                            ${escapeHtml(alt.tradeoff || alt.would_change)}
                                        </p>
                                    ` : ''}
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    /**
     * Render scenario analysis (optimistic/realistic/pessimistic)
     * @param {Object} scenarios - Scenario analysis object
     * @returns {string} HTML string
     */
    function renderScenarioAnalysis(scenarios) {
        if (!scenarios) return '';

        const scenarioData = [
            { key: 'optimistic', label: 'Best Case', icon: 'emoji-smile', color: 'success' },
            { key: 'realistic', label: 'Most Likely', icon: 'bullseye', color: 'primary' },
            { key: 'pessimistic', label: 'Worst Case', icon: 'emoji-frown', color: 'danger' }
        ];

        return `
            <div class="scenario-analysis mb-3">
                <h6 class="fw-bold mb-3">
                    <i class="bi bi-diagram-3"></i> Scenario Analysis
                </h6>
                <div class="row">
                    ${scenarioData.map(s => {
                        const scenario = scenarios[s.key + '_scenario'] || scenarios[s.key];
                        if (!scenario) return '';
                        return `
                            <div class="col-md-4 mb-2">
                                <div class="card border-${s.color} h-100">
                                    <div class="card-header bg-${s.color} text-white py-2">
                                        <i class="bi bi-${s.icon} me-1"></i> ${s.label}
                                    </div>
                                    <div class="card-body py-2">
                                        ${scenario.probability ? `
                                            <div class="text-center mb-2">
                                                <span class="display-6">${scenario.probability}%</span>
                                                <small class="d-block text-muted">probability</small>
                                            </div>
                                        ` : ''}
                                        ${scenario.assumptions && scenario.assumptions.length > 0 ? `
                                            <ul class="small mb-0 ps-3">
                                                ${scenario.assumptions.slice(0, 2).map(a => `<li>${escapeHtml(a)}</li>`).join('')}
                                            </ul>
                                        ` : ''}
                                        ${scenario.conditions ? `
                                            <p class="small text-muted mb-0">${escapeHtml(scenario.conditions)}</p>
                                        ` : ''}
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
     * Render health assessment with factors
     * @param {Object} health - Health assessment object
     * @returns {string} HTML string
     */
    function renderHealthAssessment(health) {
        if (!health) return '';

        const statusColors = {
            'healthy': 'success',
            'good': 'success',
            'excellent': 'success',
            'at_risk': 'warning',
            'concerning': 'warning',
            'critical': 'danger',
            'poor': 'danger'
        };

        const color = statusColors[health.overall_status?.toLowerCase()] || 
                     statusColors[health.overall_score?.toLowerCase()] || 'secondary';

        return `
            <div class="health-assessment mb-3">
                <div class="card border-${color}">
                    <div class="card-header bg-${color} text-white">
                        <i class="bi bi-heart-pulse me-2"></i>
                        <strong>Health Assessment:</strong> 
                        ${escapeHtml(health.overall_status || health.overall_score || 'Unknown')}
                    </div>
                    <div class="card-body">
                        ${health.status_reasoning || health.score_reasoning ? `
                            <p class="mb-3">${escapeHtml(health.status_reasoning || health.score_reasoning)}</p>
                        ` : ''}
                        
                        ${health.health_factors && health.health_factors.length > 0 ? `
                            <h6 class="small fw-bold text-muted mb-2">CONTRIBUTING FACTORS</h6>
                            <div class="table-responsive">
                                <table class="table table-sm table-bordered mb-0">
                                    <thead class="table-light">
                                        <tr>
                                            <th>Factor</th>
                                            <th>Status</th>
                                            <th>Impact</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${health.health_factors.map(f => `
                                            <tr>
                                                <td>${escapeHtml(f.factor)}</td>
                                                <td>
                                                    <span class="badge bg-${f.status === 'positive' ? 'success' : f.status === 'negative' ? 'danger' : 'secondary'}">
                                                        ${f.status}
                                                    </span>
                                                </td>
                                                <td class="small">${escapeHtml(f.impact || f.evidence || '')}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            </div>
                        ` : ''}
                        
                        ${health.health_indicators && health.health_indicators.length > 0 ? `
                            <h6 class="small fw-bold text-muted mb-2 mt-3">KEY INDICATORS</h6>
                            ${health.health_indicators.map(ind => `
                                <div class="d-flex justify-content-between align-items-center py-1 border-bottom">
                                    <span class="small">${escapeHtml(ind.indicator)}</span>
                                    <div>
                                        <span class="badge bg-${ind.status === 'positive' ? 'success' : ind.status === 'negative' ? 'danger' : 'secondary'} me-1">
                                            ${ind.value || ind.status}
                                        </span>
                                        ${ind.benchmark ? `<small class="text-muted">vs ${ind.benchmark}</small>` : ''}
                                    </div>
                                </div>
                            `).join('')}
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render a collapsible "Why This?" section
     * @param {Object} data - Explainability data
     * @param {string} id - Unique ID for collapse
     * @returns {string} HTML string
     */
    function renderWhyThisSection(data, id = 'whyThis') {
        if (!data) return '';

        const hasContent = data.reasoning || data.assumptions || data.limitations || 
                          data.contributing_factors || data.methodology;
        
        if (!hasContent) return '';

        return `
            <div class="why-this-section mt-2">
                <button class="btn btn-sm btn-outline-info" type="button" 
                        data-bs-toggle="collapse" data-bs-target="#${id}Collapse">
                    <i class="bi bi-lightbulb me-1"></i> Why This Recommendation?
                </button>
                <div class="collapse mt-2" id="${id}Collapse">
                    <div class="card card-body bg-light">
                        ${data.reasoning ? `
                            <div class="mb-2">
                                <strong class="small text-muted">REASONING:</strong>
                                <p class="small mb-0">${escapeHtml(data.reasoning)}</p>
                            </div>
                        ` : ''}
                        
                        ${data.methodology ? `
                            <div class="mb-2">
                                <strong class="small text-muted">METHODOLOGY:</strong>
                                <p class="small mb-0">${escapeHtml(data.methodology)}</p>
                            </div>
                        ` : ''}
                        
                        ${data.contributing_factors && data.contributing_factors.length > 0 ? `
                            <div class="mb-2">
                                <strong class="small text-muted">KEY FACTORS:</strong>
                                <ul class="small mb-0 ps-3">
                                    ${data.contributing_factors.slice(0, 3).map(f => 
                                        `<li>${escapeHtml(f.factor || f)}: ${f.contribution_percentage ? f.contribution_percentage + '%' : ''} ${f.description ? '- ' + escapeHtml(f.description) : ''}</li>`
                                    ).join('')}
                                </ul>
                            </div>
                        ` : ''}
                        
                        ${data.assumptions && data.assumptions.length > 0 ? `
                            <div class="mb-2">
                                <strong class="small text-muted">ASSUMPTIONS:</strong>
                                <ul class="small mb-0 ps-3 text-warning">
                                    ${data.assumptions.slice(0, 3).map(a => `<li>${escapeHtml(a)}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                        
                        ${data.limitations && data.limitations.length > 0 ? `
                            <div class="mb-0">
                                <strong class="small text-muted">LIMITATIONS:</strong>
                                <ul class="small mb-0 ps-3 text-danger">
                                    ${data.limitations.slice(0, 2).map(l => `<li>${escapeHtml(l)}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render a comprehensive AI insight card
     * @param {Object} insight - AI insight with full explainability
     * @param {Object} options - Display options
     * @returns {string} HTML string
     */
    function renderAIInsightCard(insight, options = {}) {
        const {
            title = 'AI Insight',
            icon = 'bi-robot',
            showConfidence = true,
            showActions = true,
            showAlternatives = true,
            collapsible = false,
            cardId = 'aiInsight'
        } = options;

        const confidence = insight.confidence_score || insight.confidence || 0;
        const confidenceClass = confidence >= 0.75 ? 'success' : confidence >= 0.5 ? 'warning' : 'danger';

        let content = `
            ${showConfidence && confidence ? renderConfidenceMeter(confidence, 'AI Confidence', insight.confidence_reasoning) : ''}
            
            ${insight.executive_summary || insight.summary ? `
                <div class="alert alert-info mb-3">
                    <i class="bi bi-info-circle me-2"></i>
                    ${escapeHtml(insight.executive_summary || insight.summary)}
                </div>
            ` : ''}
            
            ${insight.prediction_reasoning || insight.reasoning_details ? 
                renderReasoningSection(insight.prediction_reasoning || insight.reasoning_details) : ''}
            
            ${insight.health_assessment || insight.task_health ? 
                renderHealthAssessment(insight.health_assessment || insight.task_health) : ''}
            
            ${showActions && (insight.prioritized_actions || insight.action_items || insight.recommendations) ? 
                renderActionItems(insight.prioritized_actions || insight.action_items || insight.recommendations) : ''}
            
            ${insight.scenario_analysis ? renderScenarioAnalysis(insight.scenario_analysis) : ''}
            
            ${showAlternatives && insight.alternative_approaches ? 
                renderAlternatives(insight.alternative_approaches) : ''}
            
            ${renderWhyThisSection({
                reasoning: insight.interpretation_reasoning,
                methodology: insight.analysis_methodology?.approach,
                assumptions: insight.assumptions,
                limitations: insight.limitations,
                contributing_factors: insight.contributing_factors
            }, cardId)}
        `;

        if (collapsible) {
            return `
                <div class="card border-${confidenceClass} mb-3">
                    <div class="card-header bg-${confidenceClass} bg-opacity-10 cursor-pointer" 
                         data-bs-toggle="collapse" data-bs-target="#${cardId}Body">
                        <div class="d-flex justify-content-between align-items-center">
                            <span><i class="bi ${icon} me-2"></i><strong>${title}</strong></span>
                            <span class="badge bg-${confidenceClass}">${Math.round(confidence * 100)}% confident</span>
                        </div>
                    </div>
                    <div class="collapse" id="${cardId}Body">
                        <div class="card-body">${content}</div>
                    </div>
                </div>
            `;
        }

        return `
            <div class="card border-${confidenceClass} mb-3">
                <div class="card-header bg-${confidenceClass} bg-opacity-10">
                    <div class="d-flex justify-content-between align-items-center">
                        <span><i class="bi ${icon} me-2"></i><strong>${title}</strong></span>
                        <span class="badge bg-${confidenceClass}">${Math.round(confidence * 100)}% confident</span>
                    </div>
                </div>
                <div class="card-body">${content}</div>
            </div>
        `;
    }

    /**
     * Show explainability modal (for badge clicks)
     * @param {HTMLElement} element - The clicked element with data-explainability
     */
    function showExplainabilityModal(element) {
        const data = JSON.parse(element.dataset.explainability || '{}');
        
        // Create or get modal
        let modal = document.getElementById('aiExplainabilityModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'aiExplainabilityModal';
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title"><i class="bi bi-lightbulb me-2"></i>AI Explainability</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body" id="aiExplainabilityModalBody"></div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        
        // Populate content
        document.getElementById('aiExplainabilityModalBody').innerHTML = renderAIInsightCard(data, {
            title: 'Understanding This AI Decision',
            showConfidence: true,
            showActions: true,
            showAlternatives: true
        });
        
        // Show modal
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }

    /**
     * Render inline explainability tooltip content
     * @param {Object} data - Basic explainability data
     * @returns {string} HTML for tooltip
     */
    function renderTooltipContent(data) {
        if (!data) return '';
        
        const confidence = data.confidence_score || data.confidence || 0;
        
        return `
            <div class="p-2" style="max-width: 300px;">
                <div class="d-flex justify-content-between mb-2">
                    <strong>AI Confidence</strong>
                    <span>${Math.round(confidence * 100)}%</span>
                </div>
                ${data.reasoning ? `<p class="small mb-1">${escapeHtml(data.reasoning.substring(0, 150))}...</p>` : ''}
                ${data.assumptions && data.assumptions.length > 0 ? `
                    <small class="text-muted">Assumes: ${escapeHtml(data.assumptions[0])}</small>
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
        renderExplainabilityBadge,
        renderFactorBreakdown,
        renderCalculationExplanation,
        renderImpactBreakdown,
        renderAssumptionsAndLimitations,
        renderExplainabilityPanel,
        renderSkillMatchExplanation,
        renderDeadlinePredictionExplanation,
        renderReasoningSection,
        renderActionItems,
        renderAlternatives,
        renderScenarioAnalysis,
        renderHealthAssessment,
        renderWhyThisSection,
        renderAIInsightCard,
        showExplainabilityModal,
        renderTooltipContent,
        escapeHtml,
        formatDate
    };
})();

// Make available globally
window.AIExplainability = AIExplainability;
