/**
 * Priority Suggestion Widget
 * AI-powered priority suggestions with explainability
 */

class PrioritySuggestionWidget {
    constructor(options = {}) {
        this.boardId = options.boardId;
        this.taskId = options.taskId || null;
        this.containerId = options.containerId || 'priority-suggestion-container';
        this.priorityFieldId = options.priorityFieldId || 'id_priority';
        this.onAccept = options.onAccept || null;
        this.onReject = options.onReject || null;
        
        this.suggestion = null;
        this.isVisible = false;
    }
    
    /**
     * Initialize the widget
     */
    init() {
        // Create container if it doesn't exist
        if (!document.getElementById(this.containerId)) {
            this._createContainer();
        }
        
        // Setup click handler for existing button (don't create duplicate)
        this._setupTriggerButton();
        
        // Auto-suggest on certain field changes
        this._setupAutoTriggers();
    }
    
    /**
     * Get priority suggestion from API
     */
    async getSuggestion(taskData = {}) {
        const spinner = document.getElementById('priority-ai-spinner');
        const button = document.getElementById('suggest-priority-btn');
        
        try {
            // Show spinner and disable button
            if (spinner) spinner.classList.remove('d-none');
            if (button) button.disabled = true;
            
            const requestData = {
                board_id: this.boardId,
                ...taskData
            };
            
            if (this.taskId) {
                requestData.task_id = this.taskId;
            }
            
            const response = await fetch('/api/suggest-priority/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this._getCsrfToken()
                },
                body: JSON.stringify(requestData)
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to get priority suggestion');
            }
            
            this.suggestion = await response.json();
            this._displaySuggestion();
            
        } catch (error) {
            console.error('Error getting priority suggestion:', error);
            this._showError(error.message || 'Failed to get priority suggestion. Please try again.');
        } finally {
            // Hide spinner and enable button
            if (spinner) spinner.classList.add('d-none');
            if (button) button.disabled = false;
        }
    }
    
    /**
     * Display the suggestion in the UI with enhanced explainability
     */
    _displaySuggestion() {
        if (!this.suggestion) return;
        
        const container = document.getElementById(this.containerId);
        
        const priorityLabels = {
            'urgent': { text: 'Urgent', class: 'danger', icon: '🔥' },
            'high': { text: 'High', class: 'warning', icon: '⚠️' },
            'medium': { text: 'Medium', class: 'info', icon: 'ℹ️' },
            'low': { text: 'Low', class: 'secondary', icon: '📌' }
        };
        
        const priority = this.suggestion.suggested_priority;
        const label = priorityLabels[priority] || priorityLabels.medium;
        const confidence = (this.suggestion.confidence * 100).toFixed(0);
        
        container.innerHTML = `
            <div class="alert alert-${label.class} border-start border-5 border-${label.class} shadow-sm mb-3" role="alert">
                <div class="d-flex align-items-start">
                    <div class="flex-grow-1">
                        <!-- Header: AI Suggestion with Confidence -->
                        <h6 class="alert-heading mb-3">
                            ${label.icon} AI Suggests: <strong>${label.text} Priority</strong>
                            <span class="badge bg-${label.class} ms-2">${confidence}% confident</span>
                        </h6>
                        
                        <!-- Score Bar -->
                        ${this._renderPriorityScoreBar(label.class)}
                        
                        <!-- Primary Reasoning (Consolidated) -->
                        <div class="mt-3 mb-3">
                            ${this._renderConsolidatedReasoning(label.class)}
                        </div>
                        
                        <!-- Actions -->
                        <div class="mt-3 d-flex flex-wrap gap-2">
                            <button type="button" class="btn btn-sm btn-${label.class}" onclick="event.preventDefault(); prioritySuggestion.acceptSuggestion()">
                                <i class="fas fa-check"></i> Accept ${label.text}
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-secondary" onclick="event.preventDefault(); prioritySuggestion.rejectSuggestion()">
                                <i class="fas fa-times"></i> Dismiss
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-info" onclick="event.preventDefault(); prioritySuggestion.toggleDetails()">
                                <i class="fas fa-chart-bar"></i> Full Analysis
                            </button>
                        </div>
                    </div>
                    
                    <button type="button" class="btn-close ms-2" onclick="prioritySuggestion.hideSuggestion()"></button>
                </div>
                
                <!-- Expandable Full Details -->
                <div id="suggestion-details" class="mt-3 pt-3 border-top" style="display: none;">
                    ${this._renderEnhancedDetails()}
                </div>
            </div>
        `;
        
        this.isVisible = true;
        container.style.display = 'block';
    }
    
    /**
     * Render priority score bar with visual indicator
     */
    _renderPriorityScoreBar(labelClass) {
        if (!this.suggestion.reasoning?.analysis_score) return '';
        
        // Extract score numbers (e.g., "6/12" -> 6, 12)
        const scoreMatch = this.suggestion.reasoning.analysis_score.match(/(\d+)\/(\d+)/);
        if (!scoreMatch) return '';
        
        const score = parseInt(scoreMatch[1]);
        const maxScore = parseInt(scoreMatch[2]);
        const percentage = (score / maxScore) * 100;
        
        // Color code based on percentage
        let barColor = 'secondary';
        if (percentage >= 67) barColor = 'danger';      // 8+/12 = red (urgent/high)
        else if (percentage >= 42) barColor = 'warning'; // 5-7/12 = orange (medium/high)
        else if (percentage >= 25) barColor = 'info';    // 3-4/12 = blue (medium)
        
        return `
            <div class="mb-3">
                <div class="d-flex align-items-center justify-content-between small mb-2">
                    <span class="fw-bold">
                        <i class="fas fa-tachometer-alt me-1"></i>Priority Score
                    </span>
                    <span class="badge bg-${barColor}">${this.suggestion.reasoning.analysis_score}</span>
                </div>
                <div class="progress" style="height: 8px;">
                    <div class="progress-bar bg-${barColor}" role="progressbar" 
                         style="width: ${percentage}%" 
                         aria-valuenow="${score}" aria-valuemin="0" aria-valuemax="${maxScore}">
                    </div>
                </div>
                <div class="d-flex justify-content-between mt-1" style="font-size: 0.7rem; color: #999;">
                    <span>Low</span>
                    <span>High</span>
                </div>
            </div>
        `;
    }
    
    /**
     * Render consolidated reasoning with key factors
     */
    _renderConsolidatedReasoning(labelClass) {
        const factors = this.suggestion.reasoning?.top_factors || 
                       this.suggestion.contributing_factors || [];
        
        if (factors.length === 0) {
            return '<p class="small text-muted mb-0"><em>Analysis based on task attributes, due date, and project context</em></p>';
        }
        
        // Get top 3 most impactful factors
        const topFactors = factors.slice(0, 3);
        
        // Create icons map for common factors with better visuals
        const factorIcons = {
            'days_until_due': '📅',
            'is_overdue': '⏰',
            'complexity_score': '🧩',
            'blocking_count': '🚧',
            'blocked_by_count': '⛔',
            'assignee_workload': '👤',
            'collaboration_required': '👥',
            'risk_score': '⚠️',
            'has_subtasks': '📋',
            'keywords_detected': '🔑',
            'high_impact': '💥',
            'low_urgency': '🔻',
            'high_urgency': '🔺'
        };
        
        const factorHtml = topFactors.map(factor => {
            const factorName = factor.factor || '';
            let icon = factorIcons[factorName] || '•';
            const desc = factor.description || factor.factor || '';
            const importance = factor.importance || factor.contribution_percentage;
            
            // Determine if this is a positive or negative factor
            let prefix = '';
            let iconClass = '';
            if (desc.toLowerCase().includes('high-impact') || desc.toLowerCase().includes('critical')) {
                prefix = '✅';
                iconClass = 'text-success';
            } else if (desc.toLowerCase().includes('low urgency') || desc.toLowerCase().includes('8 days away')) {
                prefix = '🔻';
                iconClass = 'text-warning';
            }
            
            let importanceHtml = '';
            if (importance) {
                const pct = typeof importance === 'number' ? 
                    (importance > 1 ? importance : importance * 100).toFixed(0) : importance;
                let weightClass = 'secondary';
                // Color code by importance
                if (pct >= 30) weightClass = 'danger';
                else if (pct >= 20) weightClass = 'warning';
                else if (pct >= 10) weightClass = 'info';
                importanceHtml = ` <span class="badge bg-${weightClass}" style="font-size: 0.65rem;">${pct}%</span>`;
            }
            
            return `
                <div class="d-flex align-items-start mb-2">
                    <span class="me-2" style="font-size: 1.1rem;">${prefix || icon}</span>
                    <span class="flex-grow-1">
                        <span class="fw-medium">${desc}</span>${importanceHtml}
                    </span>
                </div>
            `;
        }).join('');
        
        return `
            <div class="p-3 bg-light bg-opacity-50 rounded border border-${labelClass} border-opacity-25">
                <h6 class="small fw-bold mb-2 text-${labelClass}">
                    <i class="fas fa-lightbulb me-1"></i>Primary Reasoning:
                </h6>
                ${factorHtml}
            </div>
        `;
    }
    
    /**
     * Render enhanced detailed information with full explainability
     */
    _renderEnhancedDetails() {
        const modelInfo = this.suggestion.is_ml_based 
            ? `<span class="badge bg-success">ML Model v${this.suggestion.model_version || 1}</span>`
            : `<span class="badge bg-info">AI Analysis</span>`;
        
        const reasoning = this.suggestion.reasoning || {};
        const assumptions = this.suggestion.assumptions || reasoning.assumptions || [];
        const factors = this.suggestion.contributing_factors || reasoning.top_factors || [];
        const workloadImpact = this.suggestion.workload_impact;
        const urgencyIndicators = this.suggestion.urgency_indicators;
        const impactIndicators = this.suggestion.impact_indicators;
        
        return `
            <div class="explainability-details">
                <div class="row">
                    <div class="col-md-6">
                        <h6 class="small fw-bold text-muted mb-2">
                            <i class="bi bi-gear me-1"></i>HOW IT WORKS
                        </h6>
                        <p class="small mb-2">${modelInfo}</p>
                        <p class="small mb-2">
                            <strong>Confidence Level:</strong> 
                            ${this.suggestion.reasoning?.confidence_level || (this.suggestion.confidence >= 0.75 ? 'High' : this.suggestion.confidence >= 0.5 ? 'Medium' : 'Low')}
                        </p>
                        ${reasoning.methodology ? `
                            <p class="small mb-2"><strong>Method:</strong> ${reasoning.methodology}</p>
                        ` : ''}
                    </div>
                    
                    <div class="col-md-6">
                        ${factors.length > 0 ? `
                            <h6 class="small fw-bold text-muted mb-2">
                                <i class="bi bi-bar-chart me-1"></i>FACTOR BREAKDOWN
                            </h6>
                            ${factors.map(f => `
                                <div class="d-flex justify-content-between align-items-center small mb-1">
                                    <span>${f.factor || f.description}</span>
                                    ${f.contribution_percentage ? `
                                        <div class="progress" style="width: 60px; height: 6px;">
                                            <div class="progress-bar bg-${f.contribution_percentage > 25 ? 'danger' : 'secondary'}" 
                                                 style="width: ${f.contribution_percentage}%"></div>
                                        </div>
                                    ` : ''}
                                </div>
                            `).join('')}
                        ` : ''}
                    </div>
                </div>
                
                ${urgencyIndicators || impactIndicators ? `
                    <div class="row mt-3">
                        ${urgencyIndicators ? `
                            <div class="col-md-6">
                                <h6 class="small fw-bold text-danger mb-2">
                                    <i class="bi bi-clock me-1"></i>URGENCY INDICATORS
                                </h6>
                                <ul class="small mb-0 ps-3">
                                    ${Object.entries(urgencyIndicators).map(([k, v]) => 
                                        `<li><strong>${k}:</strong> ${v}</li>`
                                    ).join('')}
                                </ul>
                            </div>
                        ` : ''}
                        ${impactIndicators ? `
                            <div class="col-md-6">
                                <h6 class="small fw-bold text-primary mb-2">
                                    <i class="bi bi-bullseye me-1"></i>IMPACT INDICATORS
                                </h6>
                                <ul class="small mb-0 ps-3">
                                    ${Object.entries(impactIndicators).map(([k, v]) => 
                                        `<li><strong>${k}:</strong> ${v}</li>`
                                    ).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>
                ` : ''}
                
                ${workloadImpact ? `
                    <div class="mt-3">
                        <h6 class="small fw-bold text-muted mb-2">
                            <i class="bi bi-person-workspace me-1"></i>WORKLOAD IMPACT
                        </h6>
                        <p class="small mb-0">${typeof workloadImpact === 'string' ? workloadImpact : JSON.stringify(workloadImpact)}</p>
                    </div>
                ` : ''}
                
                ${assumptions.length > 0 ? `
                    <div class="mt-3">
                        <h6 class="small fw-bold text-warning mb-2">
                            <i class="bi bi-exclamation-triangle me-1"></i>ASSUMPTIONS MADE
                        </h6>
                        <ul class="small mb-0 ps-3 text-muted">
                            ${assumptions.map(a => `<li>${a}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
        `;
    }
    
    /**
     * Accept the suggested priority
     */
    async acceptSuggestion() {
        const priorityField = document.getElementById(this.priorityFieldId);
        if (priorityField) {
            priorityField.value = this.suggestion.suggested_priority;
            
            // Trigger change event
            priorityField.dispatchEvent(new Event('change', { bubbles: true }));
        }
        
        // Log decision
        await this._logDecision('ai_accepted', this.suggestion.suggested_priority);
        
        // Callback
        if (this.onAccept) {
            this.onAccept(this.suggestion.suggested_priority);
        }
        
        this._showSuccess(`Priority set to ${this.suggestion.suggested_priority}`);
        this.hideSuggestion();
    }
    
    /**
     * Reject the suggestion
     */
    async rejectSuggestion() {
        const priorityField = document.getElementById(this.priorityFieldId);
        const actualPriority = priorityField ? priorityField.value : 'medium';
        
        // Log decision
        await this._logDecision('ai_rejected', actualPriority);
        
        // Callback
        if (this.onReject) {
            this.onReject();
        }
        
        this.hideSuggestion();
    }
    
    /**
     * Select an alternative priority
     */
    async selectAlternative(priority) {
        const priorityField = document.getElementById(this.priorityFieldId);
        if (priorityField) {
            priorityField.value = priority;
            priorityField.dispatchEvent(new Event('change', { bubbles: true }));
        }
        
        // Log as modified
        await this._logDecision('ai_rejected', priority, 'Selected alternative suggestion');
        
        this._showSuccess(`Priority set to ${priority}`);
        this.hideSuggestion();
    }
    
    /**
     * Toggle detailed information
     */
    toggleDetails() {
        const details = document.getElementById('suggestion-details');
        if (details) {
            details.style.display = details.style.display === 'none' ? 'block' : 'none';
        }
    }
    
    /**
     * Hide the suggestion
     */
    hideSuggestion() {
        const container = document.getElementById(this.containerId);
        if (container) {
            container.style.display = 'none';
        }
        this.isVisible = false;
    }
    
    /**
     * Log priority decision to backend for learning
     */
    async _logDecision(decisionType, actualPriority, feedbackNotes = '') {
        if (!this.taskId) return; // Only log for existing tasks
        
        try {
            await fetch('/api/log-priority-decision/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this._getCsrfToken()
                },
                body: JSON.stringify({
                    task_id: this.taskId,
                    priority: actualPriority,
                    decision_type: decisionType,
                    suggested_priority: this.suggestion.suggested_priority,
                    confidence: this.suggestion.confidence,
                    reasoning: this.suggestion.reasoning,
                    feedback_notes: feedbackNotes
                })
            });
        } catch (error) {
            console.error('Error logging decision:', error);
        }
    }
    
    /**
     * Create the container element
     */
    _createContainer() {
        const priorityField = document.getElementById(this.priorityFieldId);
        if (!priorityField) return;
        
        const container = document.createElement('div');
        container.id = this.containerId;
        container.style.display = 'none';
        
        // Insert before priority field
        priorityField.parentElement.insertBefore(container, priorityField);
    }
    
    /**
     * Setup trigger button click handler
     */
    _setupTriggerButton() {
        // Use existing button from template
        const button = document.getElementById('suggest-priority-btn');
        if (!button) {
            console.warn('Priority suggestion button not found');
            return;
        }
        
        button.onclick = () => this._triggerSuggestion();
    }
    
    /**
     * Setup auto-triggers for suggestions
     */
    _setupAutoTriggers() {
        // Auto-suggest when due date changes
        const dueDateField = document.getElementById('id_due_date');
        if (dueDateField) {
            dueDateField.addEventListener('change', () => {
                if (!this.isVisible) {
                    setTimeout(() => this._triggerSuggestion(), 500);
                }
            });
        }
        
        // Auto-suggest when complexity changes
        const complexityField = document.getElementById('id_complexity_score');
        if (complexityField) {
            complexityField.addEventListener('change', () => {
                if (!this.isVisible) {
                    setTimeout(() => this._triggerSuggestion(), 500);
                }
            });
        }
    }
    
    /**
     * Trigger suggestion based on current form data
     */
    async _triggerSuggestion() {
        const taskData = this._getTaskDataFromForm();
        await this.getSuggestion(taskData);
    }
    
    /**
     * Extract task data from form
     */
    _getTaskDataFromForm() {
        const data = {};
        
        const fields = [
            'title', 'description', 'due_date', 'complexity_score',
            'collaboration_required', 'risk_score'
        ];
        
        fields.forEach(field => {
            const element = document.getElementById(`id_${field}`);
            if (element) {
                if (element.type === 'checkbox') {
                    data[field] = element.checked;
                } else {
                    data[field] = element.value;
                }
            }
        });
        
        return data;
    }
    
    /**
     * Show success message
     */
    _showSuccess(message) {
        // You can customize this based on your notification system
        if (typeof showToast !== 'undefined') {
            showToast(message, 'success');
        } else {
            alert(message);
        }
    }
    
    /**
     * Show error message
     */
    _showError(message) {
        if (typeof showToast !== 'undefined') {
            showToast(message, 'error');
        } else {
            alert(message);
        }
    }
    
    /**
     * Get CSRF token
     */
    _getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
}

// Global instance for easy access
let prioritySuggestion = null;

// Initialize on document ready
document.addEventListener('DOMContentLoaded', function() {
    // Auto-initialize if we're on a task form with board_id available
    const boardIdElement = document.querySelector('[data-board-id]');
    const taskIdElement = document.querySelector('[data-task-id]');
    
    if (boardIdElement) {
        const boardId = boardIdElement.dataset.boardId;
        const taskId = taskIdElement ? taskIdElement.dataset.taskId : null;
        
        prioritySuggestion = new PrioritySuggestionWidget({
            boardId: boardId,
            taskId: taskId
        });
        
        prioritySuggestion.init();
    }
});
