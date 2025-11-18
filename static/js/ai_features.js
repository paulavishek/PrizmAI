/**
 * JavaScript functionality for AI-powered features in TaskFlow
 */

document.addEventListener('DOMContentLoaded', function() {
    // AI Task Description Generator
    initAITaskDescription();
    
    // AI Comment Summarizer
    initAICommentSummarizer();
    
    // AI LSS Classification Suggestion
    initAILssClassification();
    
    // AI Analytics Summary
    initAIAnalyticsSummary();
    
    // Initialize priority suggestion
    initPrioritySuggestion();
    
    // Initialize deadline prediction
    initDeadlinePrediction();
    
    // Initialize column recommendations
    initColumnRecommendations();
    
    // Initialize task breakdown suggestions
    initTaskBreakdown();
    
    // Initialize workflow optimization
    initWorkflowOptimization();
});

/**
 * Initialize AI Task Description Generator
 */
function initAITaskDescription() {
    const generateButton = document.getElementById('generate-ai-description');
    const titleInput = document.getElementById('id_title');
    const descriptionTextarea = document.getElementById('id_description');
    const aiSpinner = document.getElementById('ai-spinner');
    
    if (generateButton && titleInput && descriptionTextarea) {
        generateButton.addEventListener('click', function() {
            const title = titleInput.value.trim();
            
            if (!title) {
                alert('Please enter a task title first.');
                return;
            }
            
            // Show spinner
            aiSpinner.classList.remove('d-none');
            generateButton.disabled = true;
            
            // Make API call to our backend endpoint
            fetch('/api/generate-task-description/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({ title: title })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.description) {
                    descriptionTextarea.value = data.description;
                } else {
                    alert('Could not generate description. Please try again or enter description manually.');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred. Please try again or enter description manually.');
            })
            .finally(() => {
                // Hide spinner
                aiSpinner.classList.add('d-none');
                generateButton.disabled = false;
            });
        });
    }
}

/**
 * Initialize AI Comment Summarizer
 */
function initAICommentSummarizer() {
    const summarizeButton = document.getElementById('summarize-comments');
    const summaryContainer = document.getElementById('comment-summary-container');
    const summaryText = document.getElementById('comment-summary-text');
    const summarySpinner = document.getElementById('summary-spinner');
    
    if (summarizeButton && summaryContainer && summaryText) {
        summarizeButton.addEventListener('click', function() {
            const taskId = summarizeButton.getAttribute('data-task-id');
            
            if (!taskId) return;
            
            // Show spinner
            if (summarySpinner) summarySpinner.classList.remove('d-none');
            summarizeButton.disabled = true;
            
            // Make API call
            fetch(`/api/summarize-comments/${taskId}/`, {
                method: 'GET',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.summary) {
                    summaryText.innerHTML = data.summary;
                    summaryContainer.classList.remove('d-none');
                } else {
                    alert('Could not generate summary. Please try again.');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while generating summary.');
            })
            .finally(() => {
                // Hide spinner
                if (summarySpinner) summarySpinner.classList.add('d-none');
                summarizeButton.disabled = false;
            });
        });
    }
}

/**
 * Initialize AI Lean Six Sigma Classification
 */
function initAILssClassification() {
    const classifyButton = document.getElementById('suggest-lss-classification');
    const suggestionContainer = document.getElementById('lss-suggestion-container');
    const suggestionText = document.getElementById('lss-suggestion-text');
    const classifySpinner = document.getElementById('classify-spinner');
    
    if (!classifyButton || !suggestionContainer || !suggestionText) return;
    
    // Check if we're on the task creation page
    const titleInput = document.getElementById('id_title');
    const descriptionTextarea = document.getElementById('id_description');
    const isTaskCreation = titleInput && descriptionTextarea;
    
    // Check if we're on the task detail page
    const taskId = classifyButton.getAttribute('data-task-id');
    const isTaskDetail = !!taskId;
    
    if (!(isTaskCreation || isTaskDetail)) return;
    
    classifyButton.addEventListener('click', function() {
        let title = '';
        let description = '';
        
        if (isTaskCreation) {
            // Get data from inputs on creation page
            title = titleInput.value.trim();
            description = descriptionTextarea ? descriptionTextarea.value.trim() : '';
            
            if (!title) {
                alert('Please enter a task title first.');
                return;
            }
        } else if (isTaskDetail) {
            // For task detail page, get the title and description from the form
            const titleField = document.querySelector('input[name="title"]');
            const descriptionField = document.querySelector('textarea[name="description"]');
            
            if (titleField) title = titleField.value.trim();
            if (descriptionField) description = descriptionField.value.trim();
            
            if (!title) {
                alert('Could not find task title.');
                return;
            }
        }
        
        // Show spinner
        if (classifySpinner) classifySpinner.classList.remove('d-none');
        classifyButton.disabled = true;
        
        // Make API call
        fetch('/api/suggest-lss-classification/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: JSON.stringify({ 
                title: title,
                description: description
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.classification && data.justification) {
                let suggestionHtml = `This activity is likely <strong>${data.classification}</strong>. `;
                suggestionHtml += data.justification;
                
                suggestionText.innerHTML = suggestionHtml;
                suggestionContainer.classList.remove('d-none');
            } else {
                alert('Could not generate LSS classification. Please try again.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while generating LSS classification.');
        })
        .finally(() => {
            // Hide spinner
            if (classifySpinner) classifySpinner.classList.add('d-none');
            classifyButton.disabled = false;
        });
    });
}

/**
 * Initialize AI Analytics Summary
 */
function initAIAnalyticsSummary() {
    const generateButton = document.getElementById('generate-ai-summary');
    const summaryContainer = document.getElementById('ai-summary-container');
    const summaryText = document.getElementById('ai-summary-text');
    const summaryPlaceholder = document.getElementById('ai-summary-placeholder');
    const summarySpinner = document.getElementById('ai-summary-spinner');
    
    if (generateButton && summaryContainer && summaryText && summaryPlaceholder) {
        generateButton.addEventListener('click', function() {
            const boardId = generateButton.getAttribute('data-board-id');
            
            if (!boardId) {
                console.error('Board ID not found');
                return;
            }
            
            // Show spinner and disable button
            if (summarySpinner) summarySpinner.classList.remove('d-none');
            generateButton.disabled = true;
            
            // Make API call
            fetch(`/api/summarize-board-analytics/${boardId}/`, {
                method: 'GET',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || '',
                    'Content-Type': 'application/json'
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.summary) {
                    // Convert markdown-like text to HTML for better display
                    const formattedSummary = formatSummaryText(data.summary);
                    summaryText.innerHTML = formattedSummary;
                    
                    // Show summary and hide placeholder
                    summaryContainer.classList.remove('d-none');
                    summaryPlaceholder.classList.add('d-none');
                    
                    // Change button text to indicate it can be regenerated
                    generateButton.innerHTML = '<i class="fas fa-sync me-1"></i> Regenerate Summary';
                } else {
                    alert('Could not generate analytics summary. Please try again.');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while generating the analytics summary. Please try again.');
            })
            .finally(() => {
                // Hide spinner and re-enable button
                if (summarySpinner) summarySpinner.classList.add('d-none');
                generateButton.disabled = false;
            });
        });
    }
}

/**
 * Format summary text for better HTML display
 */
function formatSummaryText(text) {
    // Convert markdown-like formatting to HTML
    let formatted = text
        // Convert ** bold ** to <strong>
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Convert ## headers to h4
        .replace(/^## (.+)$/gm, '<h4>$1</h4>')
        // Convert - bullet points to proper list items
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        // Convert line breaks to proper paragraphs
        .replace(/\n\n/g, '</p><p>')
        // Wrap the whole thing in paragraphs
        .replace(/^(.+)$/gm, function(match, p1) {
            // Don't wrap if it's already a heading or list item
            if (p1.startsWith('<h4>') || p1.startsWith('<li>')) {
                return p1;
            }
            return '<p>' + p1 + '</p>';
        });
    
    // Wrap consecutive list items in ul tags
    formatted = formatted.replace(/(<li>.*?<\/li>)(\s*<li>.*?<\/li>)*/g, function(match) {
        return '<ul>' + match + '</ul>';
    });
    
    // Clean up any empty paragraphs
    formatted = formatted.replace(/<p><\/p>/g, '');
    
    return formatted;
}

/**
 * AI Enhancement Features - New Functions
 */

/**
 * Suggest optimal priority for a task using AI
 */
function suggestTaskPriority(taskData, callback) {
    const aiSpinner = document.getElementById('priority-ai-spinner');
    const suggestButton = document.getElementById('suggest-priority-btn');
    
    if (aiSpinner) aiSpinner.classList.remove('d-none');
    if (suggestButton) suggestButton.disabled = true;
    
    fetch('/api/suggest-task-priority/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        body: JSON.stringify(taskData)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to get priority suggestion');
        }
        return response.json();
    })
    .then(data => {
        if (aiSpinner) aiSpinner.classList.add('d-none');
        if (suggestButton) suggestButton.disabled = false;
        
        if (callback) callback(null, data);
    })
    .catch(error => {
        console.error('Error suggesting priority:', error);
        if (aiSpinner) aiSpinner.classList.add('d-none');
        if (suggestButton) suggestButton.disabled = false;
        
        if (callback) callback(error, null);
    });
}

/**
 * Predict realistic deadline for a task using AI
 */
function predictTaskDeadline(taskData, callback) {
    const aiSpinner = document.getElementById('deadline-ai-spinner');
    const predictButton = document.getElementById('predict-deadline-btn');
    
    if (aiSpinner) aiSpinner.classList.remove('d-none');
    if (predictButton) predictButton.disabled = true;
    
    fetch('/api/predict-deadline/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        body: JSON.stringify(taskData)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to predict deadline');
        }
        return response.json();
    })
    .then(data => {
        if (aiSpinner) aiSpinner.classList.add('d-none');
        if (predictButton) predictButton.disabled = false;
        
        if (callback) callback(null, data);
    })
    .catch(error => {
        console.error('Error predicting deadline:', error);
        if (aiSpinner) aiSpinner.classList.add('d-none');
        if (predictButton) predictButton.disabled = false;
        
        if (callback) callback(error, null);
    });
}

/**
 * Get AI recommendations for board column structure
 */
function recommendBoardColumns(boardData, callback) {
    const aiSpinner = document.getElementById('columns-ai-spinner');
    const recommendButton = document.getElementById('recommend-columns-btn');
    
    if (aiSpinner) aiSpinner.classList.remove('d-none');
    if (recommendButton) recommendButton.disabled = true;
    
    fetch('/api/recommend-columns/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        body: JSON.stringify(boardData)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to get column recommendations');
        }
        return response.json();
    })
    .then(data => {
        if (aiSpinner) aiSpinner.classList.add('d-none');
        if (recommendButton) recommendButton.disabled = false;
        
        if (callback) callback(null, data);
    })
    .catch(error => {
        console.error('Error getting column recommendations:', error);
        if (aiSpinner) aiSpinner.classList.add('d-none');
        if (recommendButton) recommendButton.disabled = false;
        
        if (callback) callback(error, null);
    });
}

/**
 * Suggest task breakdown for complex tasks using AI
 */
function suggestTaskBreakdown(taskData, callback) {
    const aiSpinner = document.getElementById('breakdown-ai-spinner');
    const breakdownButton = document.getElementById('suggest-breakdown-btn');
    
    if (aiSpinner) aiSpinner.classList.remove('d-none');
    if (breakdownButton) breakdownButton.disabled = true;
    
    fetch('/api/suggest-task-breakdown/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        body: JSON.stringify(taskData)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to get task breakdown suggestions');
        }
        return response.json();
    })
    .then(data => {
        if (aiSpinner) aiSpinner.classList.add('d-none');
        if (breakdownButton) breakdownButton.disabled = false;
        
        if (callback) callback(null, data);
    })
    .catch(error => {
        console.error('Error suggesting task breakdown:', error);
        if (aiSpinner) aiSpinner.classList.add('d-none');
        if (breakdownButton) breakdownButton.disabled = false;
        
        if (callback) callback(error, null);
    });
}

/**
 * Analyze workflow and get optimization recommendations using AI
 */
function analyzeWorkflowOptimization(boardId, callback) {
    const aiSpinner = document.getElementById('workflow-ai-spinner');
    const analyzeButton = document.getElementById('analyze-workflow-btn');
    
    if (aiSpinner) aiSpinner.classList.remove('d-none');
    if (analyzeButton) analyzeButton.disabled = true;
      // Get CSRF token safely
    let csrfToken = '';
    
    // Try multiple sources for CSRF token
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    
    if (window.CSRF_TOKEN) {
        csrfToken = window.CSRF_TOKEN;
    } else if (csrfInput) {
        csrfToken = csrfInput.value;
    } else if (csrfMeta) {
        csrfToken = csrfMeta.getAttribute('content');
    } else {
        // Try to get from cookie as last resort
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                csrfToken = value;
                break;
            }
        }
    }
    
    if (!csrfToken) {
        console.error('CSRF token not found');
        if (aiSpinner) aiSpinner.classList.add('d-none');
        if (analyzeButton) analyzeButton.disabled = false;
        if (callback) callback(new Error('CSRF token not found'), null);
        return;
    }
    
    fetch('/api/analyze-workflow-optimization/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ board_id: boardId })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        if (aiSpinner) aiSpinner.classList.add('d-none');
        if (analyzeButton) analyzeButton.disabled = false;
        
        if (callback) callback(null, data);
    })
    .catch(error => {
        console.error('Error analyzing workflow:', error);
        if (aiSpinner) aiSpinner.classList.add('d-none');
        if (analyzeButton) analyzeButton.disabled = false;
        
        if (callback) callback(error, null);
    });
}

/**
 * Initialize Priority Suggestion Feature
 */
function initPrioritySuggestion() {
    const suggestButton = document.getElementById('suggest-priority-btn');
    if (!suggestButton) return;
    
    suggestButton.addEventListener('click', function() {
        const titleInput = document.getElementById('id_title');
        const descriptionInput = document.getElementById('id_description');
        const dueDateInput = document.getElementById('id_due_date');
        const prioritySelect = document.getElementById('id_priority');
        const boardId = this.dataset.boardId;
        const taskId = this.dataset.taskId;
        
        if (!titleInput || !titleInput.value.trim()) {
            alert('Please enter a task title first.');
            return;
        }
        
        const taskData = {
            title: titleInput.value.trim(),
            description: descriptionInput ? descriptionInput.value : '',
            due_date: dueDateInput ? dueDateInput.value : '',
            current_priority: prioritySelect ? prioritySelect.value : 'medium',
            board_id: boardId,
            task_id: taskId
        };
        
        suggestTaskPriority(taskData, function(error, data) {
            if (error) {
                alert('Failed to get priority suggestion. Please try again.');
                return;
            }
            
            displayPrioritySuggestion(data);
        });
    });
}

/**
 * Display priority suggestion results
 */
function displayPrioritySuggestion(data) {
    const resultDiv = document.getElementById('priority-suggestion-result');
    if (!resultDiv) return;
    
    let html = `
        <div class="alert alert-info">
            <h6><i class="fas fa-robot"></i> AI Priority Suggestion</h6>
            <p><strong>Suggested Priority:</strong> <span class="badge badge-${getPriorityBadgeClass(data.suggested_priority)}">${data.suggested_priority.toUpperCase()}</span></p>
            <p><strong>Confidence:</strong> ${data.confidence}</p>
            <p><strong>Reasoning:</strong> ${data.reasoning}</p>
    `;
    
    if (data.recommendations && data.recommendations.length > 0) {
        html += '<p><strong>Recommendations:</strong></p><ul>';
        data.recommendations.forEach(rec => {
            html += `<li>${rec}</li>`;
        });
        html += '</ul>';
    }
    
    html += `
            <button type="button" class="btn btn-sm btn-primary" onclick="applyPrioritySuggestion('${data.suggested_priority}')">
                Apply Suggestion
            </button>
        </div>
    `;
    
    resultDiv.innerHTML = html;
    resultDiv.classList.remove('d-none');
}

/**
 * Apply suggested priority to the form
 */
function applyPrioritySuggestion(priority) {
    const prioritySelect = document.getElementById('id_priority');
    if (prioritySelect) {
        prioritySelect.value = priority;
        
        // Trigger change event if needed
        const event = new Event('change', { bubbles: true });
        prioritySelect.dispatchEvent(event);
    }
    
    // Hide the suggestion
    const resultDiv = document.getElementById('priority-suggestion-result');
    if (resultDiv) {
        resultDiv.classList.add('d-none');
    }
}

/**
 * Initialize Deadline Prediction Feature
 */
function initDeadlinePrediction() {
    const predictButton = document.getElementById('predict-deadline-btn');
    if (!predictButton) return;
    
    predictButton.addEventListener('click', function() {
        const titleInput = document.getElementById('id_title');
        const descriptionInput = document.getElementById('id_description');
        const prioritySelect = document.getElementById('id_priority');
        const assignedToSelect = document.getElementById('id_assigned_to');
        const boardId = this.dataset.boardId;
        const taskId = this.dataset.taskId;
        
        if (!titleInput || !titleInput.value.trim()) {
            alert('Please enter a task title first.');
            return;
        }
        
        const taskData = {
            title: titleInput.value.trim(),
            description: descriptionInput ? descriptionInput.value : '',
            priority: prioritySelect ? prioritySelect.value : 'medium',
            assigned_to: assignedToSelect ? assignedToSelect.options[assignedToSelect.selectedIndex].text : 'Unassigned',
            board_id: boardId,
            task_id: taskId
        };
        
        predictTaskDeadline(taskData, function(error, data) {
            if (error) {
                alert('Failed to predict deadline. Please try again.');
                return;
            }
            
            displayDeadlinePrediction(data);
        });
    });
}

/**
 * Display deadline prediction results with explainability
 */
function displayDeadlinePrediction(data) {
    const resultDiv = document.getElementById('deadline-prediction-result');
    if (!resultDiv) return;
    
    // Use AIExplainability module for enhanced visualization
    let html = `
        <div class="alert alert-success mb-3">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <h6 class="mb-1"><i class="fas fa-calendar-alt"></i> AI Deadline Prediction</h6>
                    <div class="deadline-display">
                        <strong>Recommended Deadline:</strong> 
                        <span class="badge bg-primary fs-6">${formatDate(data.recommended_deadline)}</span>
                    </div>
                </div>
                <button type="button" class="btn btn-sm btn-primary" onclick="applyDeadlinePrediction('${data.recommended_deadline}')">
                    <i class="fas fa-check"></i> Apply Deadline
                </button>
            </div>
        </div>
    `;
    
    // Add confidence meter
    if (data.confidence_score !== undefined) {
        html += AIExplainability.renderConfidenceMeter(data.confidence_score, 'Prediction Confidence');
    }
    
    // Add detailed explanation
    html += `
        <div class="card mb-3">
            <div class="card-header bg-light">
                <h6 class="mb-0"><i class="bi bi-info-circle"></i> Why This Deadline?</h6>
            </div>
            <div class="card-body">
                <div class="reasoning-section mb-3">
                    <h6 class="small fw-bold text-muted">REASONING</h6>
                    <p>${data.reasoning}</p>
                </div>
    `;
    
    // Velocity analysis
    if (data.velocity_analysis) {
        const velocity = data.velocity_analysis;
        html += `
            <div class="velocity-section mb-3">
                <h6 class="small fw-bold text-muted">VELOCITY ANALYSIS</h6>
                <div class="row text-center">
                    <div class="col-3">
                        <div class="metric-box">
                            <div class="small text-muted">Current</div>
                            <div class="fw-bold">${velocity.current_velocity}</div>
                        </div>
                    </div>
                    <div class="col-3">
                        <div class="metric-box">
                            <div class="small text-muted">Expected</div>
                            <div class="fw-bold">${velocity.expected_velocity}</div>
                        </div>
                    </div>
                    <div class="col-3">
                        <div class="metric-box">
                            <div class="small text-muted">Trend</div>
                            <div class="fw-bold">${velocity.velocity_trend}</div>
                        </div>
                    </div>
                    <div class="col-3">
                        <div class="metric-box">
                            <div class="small text-muted">Remaining</div>
                            <div class="fw-bold">${velocity.remaining_effort_hours}h</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Calculation breakdown
    if (data.calculation_breakdown) {
        const calc = data.calculation_breakdown;
        html += `
            <div class="calculation-breakdown mb-3">
                <h6 class="small fw-bold text-muted">CALCULATION BREAKDOWN</h6>
                <table class="table table-sm">
                    <tbody>
                        <tr>
                            <td>Base Estimate</td>
                            <td class="text-end fw-bold">${calc.base_estimate_days} days</td>
                        </tr>
                        <tr>
                            <td>Complexity Factor</td>
                            <td class="text-end">×${calc.complexity_factor}</td>
                        </tr>
                        <tr>
                            <td>Workload Adjustment</td>
                            <td class="text-end">×${calc.workload_adjustment}</td>
                        </tr>
                        <tr>
                            <td>Priority Adjustment</td>
                            <td class="text-end">×${calc.priority_adjustment}</td>
                        </tr>
                        <tr class="table-active">
                            <td><strong>Buffer Time</strong></td>
                            <td class="text-end fw-bold">+${calc.buffer_days} days</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        `;
    }
    
    // Contributing factors
    if (data.contributing_factors && data.contributing_factors.length > 0) {
        html += AIExplainability.renderFactorBreakdown(data.contributing_factors);
    }
    
    // Alternative scenarios
    if (data.alternative_scenarios) {
        html += `
            <div class="scenarios-section mb-3">
                <h6 class="small fw-bold text-muted">ALTERNATIVE SCENARIOS</h6>
                <div class="row">
                    <div class="col-4 text-center">
                        <div class="scenario-box optimistic">
                            <div class="small text-success">Optimistic</div>
                            <div class="fw-bold">${formatDate(data.alternative_scenarios.optimistic)}</div>
                        </div>
                    </div>
                    <div class="col-4 text-center">
                        <div class="scenario-box realistic">
                            <div class="small text-primary">Realistic</div>
                            <div class="fw-bold">${formatDate(data.recommended_deadline)}</div>
                        </div>
                    </div>
                    <div class="col-4 text-center">
                        <div class="scenario-box pessimistic">
                            <div class="small text-danger">Pessimistic</div>
                            <div class="fw-bold">${formatDate(data.alternative_scenarios.pessimistic)}</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Assumptions
    if (data.assumptions && data.assumptions.length > 0) {
        html += `
            <div class="assumptions-section mb-3">
                <h6 class="small fw-bold text-muted">KEY ASSUMPTIONS</h6>
                <ul class="small mb-0">
                    ${data.assumptions.map(a => `<li>${a}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    html += '</div></div>';
    
    // Risk factors
    if (data.risk_factors && data.risk_factors.length > 0) {
        html += `
            <div class="alert alert-warning">
                <h6 class="alert-heading"><i class="bi bi-exclamation-triangle"></i> Risk Factors</h6>
                <ul class="mb-0">
                    ${data.risk_factors.map(risk => `<li>${risk}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    // Recommendations
    if (data.recommendations && data.recommendations.length > 0) {
        html += `
            <div class="alert alert-info">
                <h6 class="alert-heading"><i class="bi bi-lightbulb"></i> Recommendations</h6>
                <ul class="mb-0">
                    ${data.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    resultDiv.innerHTML = html;
    resultDiv.classList.remove('d-none');
}

/**
 * Apply predicted deadline to the form
 */
function applyDeadlinePrediction(deadline) {
    const dueDateInput = document.getElementById('id_due_date');
    if (dueDateInput) {
        // Convert date (YYYY-MM-DD) to datetime-local format (YYYY-MM-DDTHH:MM)
        // Set default time to end of day (23:59) for deadline
        const dateTimeValue = deadline + 'T23:59';
        dueDateInput.value = dateTimeValue;
        
        // Trigger change event if needed
        const event = new Event('change', { bubbles: true });
        dueDateInput.dispatchEvent(event);
        
        // Show success feedback
        dueDateInput.classList.add('is-valid');
        setTimeout(() => {
            dueDateInput.classList.remove('is-valid');
        }, 2000);
    }
    
    // Hide the prediction
    const resultDiv = document.getElementById('deadline-prediction-result');
    if (resultDiv) {
        resultDiv.classList.add('d-none');
    }
}

/**
 * Utility function to get priority badge class
 */
function getPriorityBadgeClass(priority) {
    switch(priority.toLowerCase()) {
        case 'urgent': return 'danger';
        case 'high': return 'warning';
        case 'medium': return 'info';
        case 'low': return 'secondary';
        default: return 'secondary';
    }
}

/**
 * Utility function to format date
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    });
}

/**
 * Initialize Column Recommendations Feature
 */
function initColumnRecommendations() {
    const recommendButton = document.getElementById('recommend-columns-btn');
    if (!recommendButton) return;
    
    recommendButton.addEventListener('click', function() {
        const nameInput = document.getElementById('id_name');
        const descriptionInput = document.getElementById('id_description');
        const projectTypeSelect = document.getElementById('project_type');
        const teamSizeSelect = document.getElementById('team_size');
        
        if (!nameInput || !nameInput.value.trim()) {
            alert('Please enter a board name first.');
            return;
        }
        
        const boardData = {
            name: nameInput.value.trim(),
            description: descriptionInput ? descriptionInput.value : '',
            project_type: projectTypeSelect ? projectTypeSelect.value : 'general',
            team_size: teamSizeSelect ? teamSizeSelect.value : '2-5',
            organization_type: 'general'
        };
        
        recommendBoardColumns(boardData, function(error, data) {
            if (error) {
                alert('Failed to get column recommendations. Please try again.');
                return;
            }
            
            displayColumnRecommendations(data);
        });
    });
}

/**
 * Display column recommendations results
 */
function displayColumnRecommendations(data) {
    const resultDiv = document.getElementById('column-recommendations-result');
    if (!resultDiv) return;
    
    let html = `
        <div class="alert alert-info">
            <h6><i class="fas fa-columns"></i> AI Column Recommendations</h6>
            <p><strong>Workflow Type:</strong> ${data.workflow_type}</p>
            <p><strong>Reasoning:</strong> ${data.reasoning}</p>
            
            <h6 class="mt-3">Recommended Columns:</h6>
            <div class="row">
    `;
    
    if (data.recommended_columns && data.recommended_columns.length > 0) {
        data.recommended_columns.forEach(column => {
            html += `
                <div class="col-md-6 mb-2">
                    <div class="card border-left" style="border-left: 4px solid ${column.color_suggestion || '#007bff'} !important;">
                        <div class="card-body py-2">
                            <h6 class="card-title mb-1">${column.name}</h6>
                            <p class="card-text small text-muted">${column.description}</p>
                        </div>
                    </div>
                </div>
            `;
        });
    }
    
    html += `
            </div>
            
            <h6 class="mt-3">Workflow Tips:</h6>
            <ul class="small">
    `;
    
    if (data.workflow_tips && data.workflow_tips.length > 0) {
        data.workflow_tips.forEach(tip => {
            html += `<li>${tip}</li>`;
        });
    }
    
    html += `
            </ul>
            
            <div class="mt-3">
                <button type="button" class="btn btn-sm btn-success" onclick="applyColumnRecommendations()">
                    Use These Columns
                </button>
                <button type="button" class="btn btn-sm btn-outline-secondary" onclick="hideColumnRecommendations()">
                    Maybe Later
                </button>
            </div>
        </div>
    `;    resultDiv.innerHTML = html;
    resultDiv.classList.remove('d-none');
    
    // Store recommendations for later use
    window.currentColumnRecommendations = data;
}

/**
 * Apply column recommendations
 */
function applyColumnRecommendations() {
    const data = window.currentColumnRecommendations;
    if (!data || !data.recommended_columns) {
        alert('Error: No column recommendations data found. Please get recommendations first.');
        return;
    }
    
    // Find the form
    const form = document.querySelector('form[method="post"]') || document.querySelector('form');
    if (!form) {
        alert('Error: Could not find the form. Please refresh the page and try again.');
        return;
    }
    
    // Store the recommended columns in a hidden input field
    let hiddenInput = document.getElementById('recommended_columns');
    if (!hiddenInput) {
        hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.id = 'recommended_columns';
        hiddenInput.name = 'recommended_columns';
        form.appendChild(hiddenInput);
    }
    
    // Store the recommended columns as JSON
    hiddenInput.value = JSON.stringify(data.recommended_columns);
    
    // Show success message
    const columnList = data.recommended_columns.map(col => `• ${col.name}`).join('\n');
    const message = `✅ Column recommendations applied!\n\nColumns to be created:\n${columnList}\n\nClick "Create Board" to proceed with these columns.`;
    
    alert(message);
    hideColumnRecommendations();
}

/**
 * Hide column recommendations
 */
function hideColumnRecommendations() {
    const resultDiv = document.getElementById('column-recommendations-result');
    if (resultDiv) {
        resultDiv.classList.add('d-none');
    }
}

/**
 * Initialize Task Breakdown Feature
 */
function initTaskBreakdown() {
    const breakdownButton = document.getElementById('suggest-breakdown-btn');
    if (!breakdownButton) return;
    
    breakdownButton.addEventListener('click', function() {
        const titleInput = document.getElementById('id_title');
        const descriptionInput = document.getElementById('id_description');
        const prioritySelect = document.getElementById('id_priority');
        const dueDateInput = document.getElementById('id_due_date');
        
        if (!titleInput || !titleInput.value.trim()) {
            alert('Please enter a task title first.');
            return;
        }
        
        const taskData = {
            title: titleInput.value.trim(),
            description: descriptionInput ? descriptionInput.value : '',
            priority: prioritySelect ? prioritySelect.value : 'medium',
            due_date: dueDateInput ? dueDateInput.value : '',
            estimated_effort: ''
        };
        
        suggestTaskBreakdown(taskData, function(error, data) {
            if (error) {
                alert('Failed to analyze task breakdown. Please try again.');
                return;
            }
            
            displayTaskBreakdown(data);
        });
    });
}

/**
 * Display task breakdown results
 */
function displayTaskBreakdown(data) {
    const resultDiv = document.getElementById('task-breakdown-result');
    if (!resultDiv) return;
    
    let html = `
        <div class="alert alert-${data.is_breakdown_recommended ? 'warning' : 'info'}">
            <h6><i class="fas fa-sitemap"></i> Task Complexity Analysis</h6>
            <p><strong>Complexity Score:</strong> ${data.complexity_score}/10</p>
            <p><strong>Breakdown Recommended:</strong> ${data.is_breakdown_recommended ? 'Yes' : 'No'}</p>
            <p><strong>Analysis:</strong> ${data.reasoning}</p>
    `;
    
    if (data.is_breakdown_recommended && data.subtasks && data.subtasks.length > 0) {
        html += '<h6 class="mt-3">Suggested Subtasks:</h6>';
        html += '<div class="list-group list-group-flush">';
        
        data.subtasks.forEach((subtask, index) => {
            html += `
                <div class="list-group-item">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${subtask.order}. ${subtask.title}</h6>
                        <small class="text-muted">${subtask.estimated_effort}</small>
                    </div>
                    <p class="mb-1">${subtask.description}</p>
                    <small class="text-${getPriorityBadgeClass(subtask.priority)}">Priority: ${subtask.priority}</small>
                    ${subtask.dependencies.length > 0 ? 
                        `<small class="ms-3 text-info">Depends on: ${subtask.dependencies.join(', ')}</small>` : 
                        ''
                    }
                </div>
            `;
        });
        html += '</div>';
        
        if (data.workflow_suggestions && data.workflow_suggestions.length > 0) {
            html += '<h6 class="mt-3">Workflow Suggestions:</h6><ul>';
            data.workflow_suggestions.forEach(suggestion => {
                html += `<li>${suggestion}</li>`;
            });
            html += '</ul>';
        }
        
        if (data.risk_considerations && data.risk_considerations.length > 0) {
            html += '<h6 class="mt-3">Risk Considerations:</h6><ul>';
            data.risk_considerations.forEach(risk => {
                html += `<li class="text-warning">${risk}</li>`;
            });
            html += '</ul>';
        }
        
        html += `
            <div class="mt-3">
                <button type="button" class="btn btn-sm btn-success me-2" onclick="createSubtasksFromBreakdown()">
                    Create as Separate Tasks
                </button>
                <button type="button" class="btn btn-sm btn-info" onclick="addBreakdownToDescription()">
                    Add to Description
                </button>
            </div>
        `;
    }
    
    html += '</div>';
    
    resultDiv.innerHTML = html;
    resultDiv.classList.remove('d-none');
    
    // Store breakdown data for later use
    window.currentTaskBreakdown = data;
}

/**
 * Add breakdown to task description
 */
function addBreakdownToDescription() {
    const data = window.currentTaskBreakdown;
    if (!data || !data.subtasks) return;
    
    const descriptionInput = document.getElementById('id_description');
    if (!descriptionInput) return;
    
    let breakdownText = '\n\n**Subtask Breakdown:**\n';
    data.subtasks.forEach(subtask => {
        breakdownText += `- [ ] ${subtask.title} (${subtask.estimated_effort})\n`;
        if (subtask.description) {
            breakdownText += `  ${subtask.description}\n`;
        }
    });
    
    descriptionInput.value += breakdownText;
    
    // Hide breakdown result
    const resultDiv = document.getElementById('task-breakdown-result');
    if (resultDiv) {
        resultDiv.classList.add('d-none');
    }
    
    alert('Subtask breakdown added to description!');
}

/**
 * Create separate tasks from breakdown
 */
function createSubtasksFromBreakdown() {
    const data = window.currentTaskBreakdown;
    if (!data || !data.subtasks) {
        alert('No subtask data available. Please generate a breakdown first.');
        return;
    }
    
    // Get board and column information
    const predictButton = document.getElementById('predict-deadline-btn');
    const boardId = predictButton ? predictButton.dataset.boardId : null;
    
    if (!boardId) {
        alert('Board information not found. Please refresh the page and try again.');
        return;
    }
      // Try to get column from URL or form context
    let columnId = null;
    
    // Method 1: Check URL parameters (for column-specific task creation)
    const urlParams = new URLSearchParams(window.location.search);
    const urlColumnId = urlParams.get('column_id');
    
    // Method 2: Check URL path for column ID pattern (like /columns/5/create-task/)
    const pathMatch = window.location.pathname.match(/\/columns\/(\d+)\/create-task/);
    const pathColumnId = pathMatch ? pathMatch[1] : null;
    
    // Method 3: Check for hidden column input in form
    const columnInput = document.querySelector('input[name="column"]');
    const formColumnId = columnInput ? columnInput.value : null;
    
    // Method 4: Check for column selector dropdown
    const columnSelect = document.querySelector('select[name="column"]');
    const selectColumnId = columnSelect ? columnSelect.value : null;
    
    // Use the first available column ID
    columnId = urlColumnId || pathColumnId || formColumnId || selectColumnId;
    
    console.log('Column detection:', {
        urlColumnId, pathColumnId, formColumnId, selectColumnId, 
        finalColumnId: columnId
    });
    
    // If still no column, ask user to select default column (first column)
    if (!columnId) {
        // This is a fallback - in most cases we should have column context
        console.log('No column context found, will use board default');
    }
    
    // Get original task title for reference
    const titleInput = document.getElementById('id_title');
    const originalTaskTitle = titleInput ? titleInput.value.trim() : 'Unknown Task';
      // Show confirmation dialog
    const confirmMessage = `This will create ${data.subtasks.length} separate tasks:\n\n` +
        data.subtasks.map((task, i) => `${i+1}. ${task.title} (${task.priority} priority)`).join('\n') +
        '\n\nThese tasks will be created in the board. Do you want to proceed?';
    
    if (!confirm(confirmMessage)) {
        return;
    }
    
    // Show loading state
    const createButton = document.querySelector('button[onclick="createSubtasksFromBreakdown()"]');
    const originalText = createButton.textContent;
    createButton.textContent = 'Creating Tasks...';
    createButton.disabled = true;
    
    // Prepare API request data
    const requestData = {
        board_id: parseInt(boardId),
        column_id: columnId ? parseInt(columnId) : null,
        subtasks: data.subtasks,
        original_task_title: originalTaskTitle
    };
    
    // Make API call
    fetch('/api/create-subtasks/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        body: JSON.stringify(requestData)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })    .then(result => {
        if (result.success) {
            // Create detailed success message
            let message = `🎉 Successfully created ${result.created_count} out of ${result.total_subtasks} tasks!`;
            
            if (result.created_tasks && result.created_tasks.length > 0) {
                message += '\n\nCreated tasks:';
                result.created_tasks.forEach(task => {
                    message += `\n• ${task.title} (${task.priority} priority)`;
                });
            }
            
            if (result.errors && result.errors.length > 0) {
                message += '\n\n⚠️ Some issues occurred:';
                result.errors.forEach(error => {
                    message += `\n• ${error}`;
                });
            }
            
            alert(message);
            
            // Hide the breakdown result
            const resultDiv = document.getElementById('task-breakdown-result');
            if (resultDiv) {
                resultDiv.classList.add('d-none');
            }
            
            // Clear the stored breakdown data
            window.currentTaskBreakdown = null;
            
            // Optionally redirect to board view to see created tasks
            const viewTasksMessage = result.created_count > 0 ? 
                'Would you like to go to the board to see the created tasks?' :
                'Would you like to go to the board?';
                
            if (confirm(viewTasksMessage)) {
                window.location.href = `/boards/${boardId}/`;
            }
            
        } else {
            alert('❌ Failed to create tasks. Please try again.');
        }
    })
    .catch(error => {
        console.error('Error creating subtasks:', error);
        alert('An error occurred while creating tasks. Please try again.');
    })
    .finally(() => {
        // Restore button state
        createButton.textContent = originalText;
        createButton.disabled = false;
    });
}

/**
 * Initialize Workflow Optimization Feature
 */
function initWorkflowOptimization() {
    const analyzeButton = document.getElementById('analyze-workflow-btn');
    if (!analyzeButton) {
        // Only log this message if we're on a board detail page
        if (window.location.pathname.includes('/boards/') && /\/boards\/\d+\/$/.test(window.location.pathname)) {
            console.log('Workflow optimization button not found on this board page');
        }
        return;
    }
    
    console.log('Initializing workflow optimization feature');
    
    analyzeButton.addEventListener('click', function() {
        const boardId = this.dataset.boardId;
        
        console.log('Analyze workflow button clicked, board ID:', boardId);
        
        if (!boardId) {
            console.error('Board ID not found in button dataset');
            alert('Board ID not found. Please refresh the page and try again.');
            return;
        }
        
        analyzeWorkflowOptimization(boardId, function(error, data) {
            if (error) {
                console.error('Workflow analysis error:', error);
                alert('Failed to analyze workflow: ' + error.message + '. Please try again.');
                return;
            }
            
            console.log('Workflow analysis successful:', data);
            displayWorkflowOptimization(data);
        });
    });
}

/**
 * Display workflow optimization results
 */
function displayWorkflowOptimization(data) {
    const container = document.getElementById('workflow-optimization-container');
    const placeholder = document.getElementById('workflow-optimization-placeholder');
    const content = document.getElementById('workflow-optimization-content');
    
    if (!container || !content) return;
    
    let html = `
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h5><i class="fas fa-heartbeat me-2"></i>Overall Workflow Health</h5>
                    <span class="badge badge-${getHealthScoreBadgeClass(data.overall_health_score)} badge-lg">
                        ${data.overall_health_score}/10
                    </span>
                </div>
                <p class="text-muted">${data.workflow_insights}</p>
            </div>
        </div>
    `;
    
    // Bottlenecks Section
    if (data.bottlenecks && data.bottlenecks.length > 0) {
        html += `
            <div class="row mb-4">
                <div class="col-md-12">
                    <h6><i class="fas fa-exclamation-triangle text-danger me-2"></i>Identified Bottlenecks</h6>
                    <div class="row">
        `;
        
        data.bottlenecks.forEach(bottleneck => {
            html += `
                <div class="col-md-6 mb-3">
                    <div class="card border-${getSeverityBorderClass(bottleneck.severity)}">
                        <div class="card-body">
                            <h6 class="card-title">
                                ${bottleneck.location} 
                                <span class="badge badge-${getSeverityBadgeClass(bottleneck.severity)}">${bottleneck.severity}</span>
                            </h6>
                            <p class="card-text small">${bottleneck.description}</p>
                            <small class="text-muted">Type: ${bottleneck.type}</small>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += `
                    </div>
                </div>
            </div>
        `;
    }
    
    // Quick Wins Section
    if (data.quick_wins && data.quick_wins.length > 0) {
        html += `
            <div class="row mb-4">
                <div class="col-md-12">
                    <h6><i class="fas fa-rocket text-success me-2"></i>Quick Wins</h6>
                    <div class="list-group">
        `;
        
        data.quick_wins.forEach(win => {
            html += `
                <div class="list-group-item d-flex align-items-center">
                    <i class="fas fa-check-circle text-success me-2"></i>
                    ${win}
                </div>
            `;
        });
        
        html += `
                    </div>
                </div>
            </div>
        `;
    }
    
    // Optimization Recommendations
    if (data.optimization_recommendations && data.optimization_recommendations.length > 0) {
        html += `
            <div class="row mb-4">
                <div class="col-md-12">
                    <h6><i class="fas fa-lightbulb text-warning me-2"></i>Optimization Recommendations</h6>
                    <div class="accordion" id="recommendationsAccordion">
        `;
        
        // Sort recommendations by priority
        const sortedRecs = data.optimization_recommendations.sort((a, b) => a.priority - b.priority);
        
        sortedRecs.forEach((rec, index) => {
            html += `
                <div class="accordion-item">
                    <h2 class="accordion-header" id="heading${index}">
                        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" 
                                data-bs-target="#collapse${index}" aria-expanded="false" aria-controls="collapse${index}">
                            <div class="d-flex justify-content-between w-100 me-3">
                                <span>${rec.title}</span>
                                <div>
                                    <span class="badge badge-${getImpactBadgeClass(rec.impact)} me-1">${rec.impact} impact</span>
                                    <span class="badge badge-outline-secondary">${rec.effort} effort</span>
                                </div>
                            </div>
                        </button>
                    </h2>
                    <div id="collapse${index}" class="accordion-collapse collapse" aria-labelledby="heading${index}" 
                         data-bs-parent="#recommendationsAccordion">
                        <div class="accordion-body">
                            <p>${rec.description}</p>
                            <small class="text-muted">Category: ${rec.category} | Priority: ${rec.priority}</small>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += `
                    </div>
                </div>
            </div>
        `;
    }
    
    // Next Steps
    if (data.next_steps && data.next_steps.length > 0) {
        html += `
            <div class="row">
                <div class="col-md-12">
                    <h6><i class="fas fa-tasks text-info me-2"></i>Recommended Next Steps</h6>
                    <ol class="list-group list-group-numbered">
        `;
        
        data.next_steps.forEach(step => {
            html += `
                <li class="list-group-item">${step}</li>
            `;
        });
        
        html += `
                    </ol>
                </div>
            </div>
        `;
    }
    
    content.innerHTML = html;
    container.classList.remove('d-none');
    placeholder.classList.add('d-none');
}

/**
 * Utility functions for workflow optimization display
 */
function getHealthScoreBadgeClass(score) {
    if (score >= 8) return 'success';
    if (score >= 6) return 'warning';
    return 'danger';
}

function getSeverityBadgeClass(severity) {
    switch(severity.toLowerCase()) {
        case 'high': return 'danger';
        case 'medium': return 'warning';
        case 'low': return 'info';
        default: return 'secondary';
    }
}

function getSeverityBorderClass(severity) {
    switch(severity.toLowerCase()) {
        case 'high': return 'danger';
        case 'medium': return 'warning';
        case 'low': return 'info';
        default: return 'secondary';
    }
}

function getImpactBadgeClass(impact) {
    switch(impact.toLowerCase()) {
        case 'high': return 'success';
        case 'medium': return 'info';
        case 'low': return 'secondary';
        default: return 'secondary';
    }
}


