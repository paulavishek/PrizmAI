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
     * Display the suggestion in the UI
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
                        <h6 class="alert-heading mb-2">
                            ${label.icon} AI Suggests: <strong>${label.text} Priority</strong>
                            <span class="badge bg-${label.class} ms-2">${confidence}% confident</span>
                        </h6>
                        
                        <p class="mb-2 small">${this.suggestion.reasoning.explanation}</p>
                        
                        ${this._renderTopFactors()}
                        
                        ${this._renderAlternatives()}
                        
                        <div class="mt-3 d-flex gap-2">
                            <button class="btn btn-sm btn-${label.class}" onclick="prioritySuggestion.acceptSuggestion()">
                                <i class="fas fa-check"></i> Accept ${label.text}
                            </button>
                            <button class="btn btn-sm btn-outline-secondary" onclick="prioritySuggestion.rejectSuggestion()">
                                <i class="fas fa-times"></i> Dismiss
                            </button>
                            <button class="btn btn-sm btn-outline-info" onclick="prioritySuggestion.toggleDetails()">
                                <i class="fas fa-info-circle"></i> Details
                            </button>
                        </div>
                    </div>
                    
                    <button type="button" class="btn-close ms-2" onclick="prioritySuggestion.hideSuggestion()"></button>
                </div>
                
                <div id="suggestion-details" class="mt-3 pt-3 border-top" style="display: none;">
                    ${this._renderDetails()}
                </div>
            </div>
        `;
        
        this.isVisible = true;
        container.style.display = 'block';
    }
    
    /**
     * Render top influencing factors
     */
    _renderTopFactors() {
        const factors = this.suggestion.reasoning.top_factors || [];
        if (factors.length === 0) return '';
        
        const factorItems = factors.slice(0, 3).map(factor => 
            `<li class="text-muted small">${factor.description}</li>`
        ).join('');
        
        return `
            <div class="mb-2">
                <strong class="small">Key factors:</strong>
                <ul class="mb-0 ps-3">
                    ${factorItems}
                </ul>
            </div>
        `;
    }
    
    /**
     * Render alternative priorities
     */
    _renderAlternatives() {
        const alternatives = this.suggestion.alternatives || [];
        if (alternatives.length === 0) return '';
        
        const altButtons = alternatives.map(alt => {
            const conf = (alt.confidence * 100).toFixed(0);
            return `
                <button class="btn btn-sm btn-outline-secondary me-1" 
                        onclick="prioritySuggestion.selectAlternative('${alt.priority}')">
                    ${alt.priority} (${conf}%)
                </button>
            `;
        }).join('');
        
        return `
            <div class="small text-muted mb-2">
                Alternatives: ${altButtons}
            </div>
        `;
    }
    
    /**
     * Render detailed information
     */
    _renderDetails() {
        const modelInfo = this.suggestion.is_ml_based 
            ? `<span class="badge bg-success">ML Model v${this.suggestion.model_version || 1}</span>`
            : `<span class="badge bg-info">Rule-Based</span>`;
        
        return `
            <div class="small">
                <p><strong>Model:</strong> ${modelInfo}</p>
                <p><strong>Confidence Level:</strong> ${this.suggestion.reasoning.confidence_level}</p>
                <p class="mb-0"><strong>Method:</strong> ${this.suggestion.is_ml_based ? 'Machine Learning Classification' : 'Heuristic Rules'}</p>
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
