/**
 * Wiki AI Assistant - Dual Mode Support
 * - Meeting Analysis Mode: For meeting notes
 * - Documentation Mode: For general documentation
 */

// Global variables
let currentAnalysisId = null;
let currentAnalysisResults = null;
let currentAnalysisType = null; // 'meeting' or 'documentation'
let selectedActionItems = new Set();
let availableBoards = [];

// Detect page type and show appropriate AI assistant button
function detectPageTypeAndShowButton() {
    const meetingBtn = document.getElementById('analyzeMeetingBtn');
    const docsBtn = document.getElementById('analyzeDocsBtn');
    
    if (!meetingBtn || !docsBtn) return;
    
    // Use category-based detection (passed from backend)
    // This is more reliable than keyword matching
    if (categoryAiType === 'meeting') {
        meetingBtn.style.display = 'inline-block';
        docsBtn.style.display = 'none';
    } else if (categoryAiType === 'documentation') {
        meetingBtn.style.display = 'none';
        docsBtn.style.display = 'inline-block';
    } else if (categoryAiType === 'none') {
        // No AI assistant for this category
        meetingBtn.style.display = 'none';
        docsBtn.style.display = 'none';
    } else {
        // Fallback: if category type not set, use documentation as default
        meetingBtn.style.display = 'none';
        docsBtn.style.display = 'inline-block';
    }
}

// Process meeting notes with AI
async function processMeetingNotes() {
    currentAnalysisType = 'meeting';
    const modal = new bootstrap.Modal(document.getElementById('meetingAssistantModal'));
    const modalBody = document.getElementById('meetingModalBody');
    modal.show();
    
    // Show processing state
    modalBody.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-success mb-3" role="status" style="width: 3rem; height: 3rem;">
                <span class="visually-hidden">Processing...</span>
            </div>
            <h5>Analyzing meeting notes with AI...</h5>
            <p class="text-muted">Extracting action items, decisions, blockers, and risks...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`/wiki/api/wiki-page/${wikiPageId}/analyze/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentAnalysisId = data.analysis_id;
            currentAnalysisResults = data.analysis_results;
            displayMeetingAnalysisResults(data.analysis_results);
            
            // Load available boards
            await loadAvailableBoards();
            document.getElementById('createTasksBtn').style.display = 'inline-block';
        } else {
            showModalError(modalBody, data.error || 'Failed to analyze meeting notes');
        }
    } catch (error) {
        console.error('Error:', error);
        showModalError(modalBody, 'An error occurred while processing. Please try again.');
    }
}

// Process documentation with AI
async function processDocumentation() {
    currentAnalysisType = 'documentation';
    const modal = new bootstrap.Modal(document.getElementById('documentationAssistantModal'));
    const modalBody = document.getElementById('docsModalBody');
    modal.show();
    
    // Show processing state
    modalBody.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-info mb-3" role="status" style="width: 3rem; height: 3rem;">
                <span class="visually-hidden">Processing...</span>
            </div>
            <h5>Analyzing documentation with AI...</h5>
            <p class="text-muted">Extracting key information and suggestions...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`/wiki/api/wiki-page/${wikiPageId}/analyze-documentation/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentAnalysisResults = data.analysis_results;
            displayDocumentationAnalysisResults(data.analysis_results);
            
            // Load available boards if there are action items
            if (data.analysis_results.action_items && data.analysis_results.action_items.length > 0) {
                await loadAvailableBoards();
                document.getElementById('createDocsTasksBtn').style.display = 'inline-block';
            }
        } else {
            showModalError(modalBody, data.error || 'Failed to analyze documentation');
        }
    } catch (error) {
        console.error('Error:', error);
        showModalError(modalBody, 'An error occurred while processing. Please try again.');
    }
}

// Display meeting analysis results
function displayMeetingAnalysisResults(results) {
    const modalBody = document.getElementById('meetingModalBody');
    const summary = results.meeting_summary || {};
    const actionItems = results.action_items || [];
    const decisions = results.decisions || [];
    const blockers = results.blockers || [];
    const risks = results.risks || [];
    
    selectedActionItems.clear();
    actionItems.forEach((_, index) => selectedActionItems.add(index));
    
    modalBody.innerHTML = `
        <!-- Summary -->
        <div class="card mb-3">
            <div class="card-header bg-light">
                <h6 class="mb-0"><i class="fas fa-clipboard-list"></i> Meeting Summary</h6>
            </div>
            <div class="card-body">
                <h6>${summary.title || 'Meeting Summary'}</h6>
                <p>${summary.summary || 'No summary available'}</p>
                ${summary.participants_detected && summary.participants_detected.length > 0 ? 
                    `<p><strong>Participants:</strong> ${summary.participants_detected.join(', ')}</p>` : ''}
                ${summary.meeting_type ? `<span class="badge bg-secondary">${summary.meeting_type}</span>` : ''}
                ${summary.confidence ? `<span class="badge bg-info ms-2">${summary.confidence} confidence</span>` : ''}
            </div>
        </div>
        
        <!-- Tabs -->
        <ul class="nav nav-tabs mb-3" role="tablist">
            <li class="nav-item">
                <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#actionItemsTab">
                    <i class="fas fa-tasks"></i> Action Items <span class="badge bg-primary ms-1">${actionItems.length}</span>
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#decisionsTab">
                    <i class="fas fa-check-circle"></i> Decisions <span class="badge bg-info ms-1">${decisions.length}</span>
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#blockersTab">
                    <i class="fas fa-exclamation-triangle"></i> Blockers <span class="badge bg-warning ms-1">${blockers.length}</span>
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#risksTab">
                    <i class="fas fa-shield-alt"></i> Risks <span class="badge bg-danger ms-1">${risks.length}</span>
                </button>
            </li>
        </ul>
        
        <div class="tab-content">
            <div class="tab-pane fade show active" id="actionItemsTab">
                ${renderActionItems(actionItems, 'meeting')}
            </div>
            <div class="tab-pane fade" id="decisionsTab">
                ${renderDecisions(decisions)}
            </div>
            <div class="tab-pane fade" id="blockersTab">
                ${renderBlockers(blockers)}
            </div>
            <div class="tab-pane fade" id="risksTab">
                ${renderRisks(risks)}
            </div>
        </div>
    `;
}

// Display documentation analysis results
function displayDocumentationAnalysisResults(results) {
    const modalBody = document.getElementById('docsModalBody');
    const summary = results.documentation_summary || {};
    const keyPoints = results.key_points || [];
    const actionItems = results.action_items || [];
    const suggestions = results.suggested_improvements || [];
    const relatedTopics = results.related_topics || [];
    const metadata = results.metadata || {};
    
    selectedActionItems.clear();
    actionItems.forEach((_, index) => selectedActionItems.add(index));
    
    modalBody.innerHTML = `
        <!-- Summary -->
        <div class="card mb-3">
            <div class="card-header bg-light">
                <h6 class="mb-0"><i class="fas fa-file-alt"></i> Documentation Summary</h6>
            </div>
            <div class="card-body">
                <h6>${summary.title || 'Documentation Analysis'}</h6>
                <p>${summary.summary || 'No summary available'}</p>
                <div class="mt-2">
                    ${summary.document_type ? `<span class="badge bg-secondary">${summary.document_type}</span>` : ''}
                    ${summary.completeness ? `<span class="badge bg-${summary.completeness === 'complete' ? 'success' : 'warning'} ms-2">${summary.completeness}</span>` : ''}
                    ${summary.target_audience ? `<span class="badge bg-info ms-2">For: ${summary.target_audience}</span>` : ''}
                </div>
            </div>
        </div>
        
        <!-- Key Points -->
        ${keyPoints.length > 0 ? `
        <div class="card mb-3">
            <div class="card-header bg-light">
                <h6 class="mb-0"><i class="fas fa-list"></i> Key Points</h6>
            </div>
            <div class="card-body">
                <ul class="mb-0">
                    ${keyPoints.map(point => `<li>${point}</li>`).join('')}
                </ul>
            </div>
        </div>
        ` : ''}
        
        <!-- Tabs -->
        <ul class="nav nav-tabs mb-3" role="tablist">
            <li class="nav-item">
                <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#docsActionItemsTab">
                    <i class="fas fa-tasks"></i> Action Items <span class="badge bg-primary ms-1">${actionItems.length}</span>
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#suggestionsTab">
                    <i class="fas fa-lightbulb"></i> Suggestions <span class="badge bg-warning ms-1">${suggestions.length}</span>
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#relatedTab">
                    <i class="fas fa-link"></i> Related <span class="badge bg-info ms-1">${relatedTopics.length}</span>
                </button>
            </li>
        </ul>
        
        <div class="tab-content">
            <div class="tab-pane fade show active" id="docsActionItemsTab">
                ${actionItems.length > 0 ? renderActionItems(actionItems, 'docs') : '<p class="text-muted">No action items found in this documentation.</p>'}
            </div>
            <div class="tab-pane fade" id="suggestionsTab">
                ${renderSuggestions(suggestions)}
            </div>
            <div class="tab-pane fade" id="relatedTab">
                ${relatedTopics.length > 0 ? `
                    <div class="list-group">
                        ${relatedTopics.map(topic => `
                            <div class="list-group-item">
                                <i class="fas fa-tag text-primary me-2"></i>${topic}
                            </div>
                        `).join('')}
                    </div>
                ` : '<p class="text-muted">No related topics identified.</p>'}
            </div>
        </div>
    `;
}

// Render action items (works for both modes)
function renderActionItems(items, mode) {
    if (items.length === 0) {
        return '<p class="text-muted">No action items detected</p>';
    }
    
    const checkboxId = mode === 'docs' ? 'docsActionItem' : 'actionItem';
    
    return items.map((item, index) => `
        <div class="card mb-3">
            <div class="card-body">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" id="${checkboxId}${index}" 
                           onchange="toggleActionItem(${index})" checked>
                    <label class="form-check-label" for="${checkboxId}${index}">
                        <h6 class="mb-1">${item.title}</h6>
                    </label>
                </div>
                <p class="mb-2 ms-4">${item.description || ''}</p>
                <div class="ms-4">
                    <span class="badge bg-${getPriorityColor(item.priority)}">${item.priority || 'medium'}</span>
                    ${item.suggested_assignee ? `<span class="badge bg-secondary"><i class="fas fa-user"></i> ${item.suggested_assignee}</span>` : ''}
                    ${item.due_date_suggestion ? `<span class="badge bg-info"><i class="fas fa-calendar"></i> ${item.due_date_suggestion}</span>` : ''}
                    ${item.estimated_effort ? `<span class="badge bg-light text-dark"><i class="fas fa-clock"></i> ${item.estimated_effort}</span>` : ''}
                    ${item.type ? `<span class="badge bg-light text-dark ms-1">${item.type}</span>` : ''}
                </div>
                ${item.source_context ? `<small class="text-muted ms-4 d-block mt-2"><i class="fas fa-quote-left"></i> ${item.source_context}</small>` : ''}
            </div>
        </div>
    `).join('');
}

// Render decisions
function renderDecisions(decisions) {
    if (decisions.length === 0) {
        return '<p class="text-muted">No decisions detected</p>';
    }
    
    return decisions.map(decision => `
        <div class="card mb-3">
            <div class="card-body">
                <h6 class="mb-2"><i class="fas fa-check-circle text-success"></i> ${decision.decision}</h6>
                <p class="mb-2"><strong>Context:</strong> ${decision.context || 'N/A'}</p>
                <p class="mb-2"><strong>Impact:</strong> ${decision.impact || 'N/A'}</p>
                ${decision.requires_action ? `
                    <div class="alert alert-warning mb-0">
                        <strong>Action Required:</strong> ${decision.action_description || 'Follow-up needed'}
                    </div>
                ` : ''}
            </div>
        </div>
    `).join('');
}

// Render blockers
function renderBlockers(blockers) {
    if (blockers.length === 0) {
        return '<p class="text-muted">No blockers detected</p>';
    }
    
    return blockers.map(blocker => `
        <div class="card mb-3 border-${getSeverityColor(blocker.severity)}">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <h6 class="mb-2"><i class="fas fa-exclamation-triangle text-warning"></i> ${blocker.blocker}</h6>
                    <span class="badge bg-${getSeverityColor(blocker.severity)}">${blocker.severity || 'medium'}</span>
                </div>
                <p class="mb-2"><strong>Affected Area:</strong> ${blocker.affected_area || 'N/A'}</p>
                ${blocker.suggested_resolution ? `<p class="mb-2"><strong>Resolution:</strong> ${blocker.suggested_resolution}</p>` : ''}
                ${blocker.owner ? `<p class="mb-0"><strong>Owner:</strong> ${blocker.owner}</p>` : ''}
            </div>
        </div>
    `).join('');
}

// Render risks
function renderRisks(risks) {
    if (risks.length === 0) {
        return '<p class="text-muted">No risks detected</p>';
    }
    
    return risks.map(risk => `
        <div class="card mb-3">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <h6 class="mb-2"><i class="fas fa-shield-alt text-danger"></i> ${risk.risk}</h6>
                    <span class="badge bg-${getProbabilityColor(risk.probability)}">${risk.probability || 'medium'} probability</span>
                </div>
                <p class="mb-2"><strong>Impact:</strong> ${risk.impact || 'N/A'}</p>
                ${risk.mitigation ? `<p class="mb-0"><strong>Mitigation:</strong> ${risk.mitigation}</p>` : ''}
            </div>
        </div>
    `).join('');
}

// Render suggestions
function renderSuggestions(suggestions) {
    if (suggestions.length === 0) {
        return '<p class="text-muted">No improvements suggested</p>';
    }
    
    return suggestions.map(suggestion => `
        <div class="card mb-3">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <h6 class="mb-2"><i class="fas fa-lightbulb text-warning"></i> ${suggestion.area}</h6>
                    <div>
                        <span class="badge bg-${getPriorityColor(suggestion.priority)}">Priority: ${suggestion.priority}</span>
                        <span class="badge bg-secondary ms-1">Effort: ${suggestion.effort}</span>
                    </div>
                </div>
                <p class="mb-0">${suggestion.suggestion}</p>
            </div>
        </div>
    `).join('');
}

// Toggle action item selection
function toggleActionItem(index) {
    if (selectedActionItems.has(index)) {
        selectedActionItems.delete(index);
    } else {
        selectedActionItems.add(index);
    }
}

// Show task creation modal (for meeting analysis)
function showTaskCreationModal() {
    if (selectedActionItems.size === 0) {
        alert('Please select at least one action item');
        return;
    }
    
    document.getElementById('selectedTasksCount').textContent = selectedActionItems.size;
    const taskModal = new bootstrap.Modal(document.getElementById('taskCreationModal'));
    taskModal.show();
}

// Show task creation modal (for documentation analysis)
function showDocsTaskCreationModal() {
    if (selectedActionItems.size === 0) {
        alert('Please select at least one action item');
        return;
    }
    
    document.getElementById('selectedTasksCount').textContent = selectedActionItems.size;
    const taskModal = new bootstrap.Modal(document.getElementById('taskCreationModal'));
    taskModal.show();
}

// Load available boards
async function loadAvailableBoards() {
    try {
        const response = await fetch('/wiki/api/boards/', {
            headers: {
                'X-CSRFToken': csrfToken
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            availableBoards = data.boards;
            const boardSelect = document.getElementById('boardSelect');
            boardSelect.innerHTML = '<option value="">-- Select a board --</option>' +
                data.boards.map(board => `<option value="${board.id}">${board.name}</option>`).join('');
        }
    } catch (error) {
        console.error('Error loading boards:', error);
    }
}

// Update column select based on selected board
function updateColumnSelect() {
    const boardId = document.getElementById('boardSelect').value;
    const columnSelect = document.getElementById('columnSelect');
    
    if (!boardId) {
        columnSelect.innerHTML = '<option value="">-- Default column --</option>';
        return;
    }
    
    const board = availableBoards.find(b => b.id == boardId);
    if (board && board.columns) {
        columnSelect.innerHTML = '<option value="">-- Default column --</option>' +
            board.columns.map(col => `<option value="${col.id}">${col.name}</option>`).join('');
    }
}

// Confirm task creation
async function confirmTaskCreation() {
    const boardId = document.getElementById('boardSelect').value;
    
    if (!boardId) {
        alert('Please select a board');
        return;
    }
    
    const columnId = document.getElementById('columnSelect').value;
    
    document.getElementById('confirmCreateTasksBtn').disabled = true;
    document.getElementById('taskCreationProgress').style.display = 'block';
    
    try {
        let endpoint;
        let requestBody;
        
        if (currentAnalysisType === 'meeting' && currentAnalysisId) {
            // Meeting analysis has its own task creation endpoint
            endpoint = `/wiki/api/meeting-analysis/${currentAnalysisId}/create-tasks/`;
            requestBody = {
                board_id: boardId,
                column_id: columnId || null,
                selected_action_items: Array.from(selectedActionItems)
            };
        } else {
            // Documentation analysis - create tasks directly (we'll need to add this endpoint)
            // For now, show error
            throw new Error('Task creation from documentation analysis not yet implemented');
        }
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        
        document.getElementById('taskCreationProgress').style.display = 'none';
        
        if (data.success) {
            document.getElementById('taskCreationResult').innerHTML = `
                <div class="alert alert-success">
                    <h6><i class="fas fa-check-circle"></i> Tasks Created Successfully!</h6>
                    <p>${data.total_created} task(s) created</p>
                    <ul>
                        ${data.created_tasks.map(task => `<li><a href="${task.url}">${task.title}</a></li>`).join('')}
                    </ul>
                </div>
            `;
            document.getElementById('taskCreationResult').style.display = 'block';
            document.getElementById('confirmCreateTasksBtn').style.display = 'none';
        } else {
            document.getElementById('taskCreationResult').innerHTML = `
                <div class="alert alert-danger">
                    <h6><i class="fas fa-exclamation-circle"></i> Error</h6>
                    <p>${data.error || 'Failed to create tasks'}</p>
                </div>
            `;
            document.getElementById('taskCreationResult').style.display = 'block';
            document.getElementById('confirmCreateTasksBtn').disabled = false;
        }
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('taskCreationProgress').style.display = 'none';
        document.getElementById('taskCreationResult').innerHTML = `
            <div class="alert alert-danger">
                <p>${error.message || 'An error occurred. Please try again.'}</p>
            </div>
        `;
        document.getElementById('taskCreationResult').style.display = 'block';
        document.getElementById('confirmCreateTasksBtn').disabled = false;
    }
}

// Show error in modal
function showModalError(modalBody, message) {
    modalBody.innerHTML = `
        <div class="alert alert-danger">
            <h5><i class="fas fa-exclamation-circle"></i> Processing Failed</h5>
            <p>${message}</p>
        </div>
    `;
}

// Helper functions
function getPriorityColor(priority) {
    const colors = {
        'urgent': 'danger',
        'high': 'warning',
        'medium': 'primary',
        'low': 'secondary'
    };
    return colors[priority] || 'secondary';
}

function getSeverityColor(severity) {
    const colors = {
        'critical': 'danger',
        'high': 'warning',
        'medium': 'info',
        'low': 'secondary'
    };
    return colors[severity] || 'secondary';
}

function getProbabilityColor(probability) {
    const colors = {
        'high': 'danger',
        'medium': 'warning',
        'low': 'success'
    };
    return colors[probability] || 'secondary';
}

// Handle back navigation to previous page
function goBack() {
    if (document.referrer && document.referrer !== window.location.href) {
        window.history.back();
    } else {
        window.location.href = wikiListUrl;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    detectPageTypeAndShowButton();
});
