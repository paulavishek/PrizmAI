/**
 * Meeting Transcript Extraction JavaScript
 * Handles AI-powered task extraction from meeting transcripts
 */

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const fileUploadZone = document.getElementById('file-upload-zone');
    const transcriptFile = document.getElementById('transcript-file');
    const transcriptText = document.getElementById('transcript-text');
    const extractTasksBtn = document.getElementById('extract-tasks-btn');
    const aiProcessing = document.getElementById('ai-processing');
    const taskReviewSection = document.getElementById('task-review-section');
    const fileInfo = document.getElementById('file-info');
    const clearFileBtn = document.getElementById('clear-file');
    
    // State
    let extractedTasks = [];
    let selectedTasks = new Set();
    
    // Initialize
    init();
    
    function init() {
        setupFileUpload();
        setupEventListeners();
    }
    
    function setupFileUpload() {
        // File input change
        transcriptFile.addEventListener('change', handleFileSelect);
        
        // Drag and drop
        fileUploadZone.addEventListener('dragover', handleDragOver);
        fileUploadZone.addEventListener('dragleave', handleDragLeave);
        fileUploadZone.addEventListener('drop', handleFileDrop);
        
        // Click to upload
        fileUploadZone.addEventListener('click', () => {
            transcriptFile.click();
        });
        
        // Clear file
        clearFileBtn.addEventListener('click', clearFile);
    }
    
    function setupEventListeners() {
        extractTasksBtn.addEventListener('click', extractTasks);
        
        // Task selection buttons (will be dynamically added)
        document.addEventListener('click', handleTaskSelection);
        
        // Bulk selection buttons
        document.getElementById('select-all-tasks')?.addEventListener('click', selectAllTasks);
        document.getElementById('deselect-all-tasks')?.addEventListener('click', deselectAllTasks);
        
        // Create tasks button
        document.getElementById('create-selected-tasks')?.addEventListener('click', createSelectedTasks);
    }
    
    function handleDragOver(e) {
        e.preventDefault();
        fileUploadZone.classList.add('dragover');
    }
    
    function handleDragLeave(e) {
        e.preventDefault();
        fileUploadZone.classList.remove('dragover');
    }
    
    function handleFileDrop(e) {
        e.preventDefault();
        fileUploadZone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            transcriptFile.files = files;
            handleFileSelect();
        }
    }
    
    function handleFileSelect() {
        const file = transcriptFile.files[0];
        if (!file) return;
        
        // Validate file
        const allowedTypes = ['text/plain', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
        if (!allowedTypes.includes(file.type) && !file.name.toLowerCase().endsWith('.txt') && !file.name.toLowerCase().endsWith('.docx') && !file.name.toLowerCase().endsWith('.pdf')) {
            showError('Unsupported file type. Please upload .txt, .docx, or .pdf files.');
            return;
        }
        
        if (file.size > 10 * 1024 * 1024) {
            showError('File size too large. Maximum 10MB allowed.');
            return;
        }
        
        // Show file info
        document.getElementById('file-name').textContent = file.name;
        document.getElementById('file-size').textContent = formatFileSize(file.size);
        fileInfo.classList.remove('d-none');
        
        // Process file
        processFile(file);
    }
    
    function clearFile() {
        transcriptFile.value = '';
        fileInfo.classList.add('d-none');
        transcriptText.value = '';
    }
    
    function processFile(file) {
        const formData = new FormData();
        formData.append('transcript_file', file);
        formData.append('csrfmiddlewaretoken', getCsrfToken());
        
        showLoading('Processing file...', 'Please wait while we extract text from your file.');
        
        fetch('/api/process-transcript-file/', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            hideLoading();
            if (data.success) {
                transcriptText.value = data.extracted_text;
                showSuccess('File processed successfully! You can now extract tasks or edit the text.');
            } else {
                showError(data.error || 'Failed to process file');
            }
        })
        .catch(error => {
            hideLoading();
            showError('Error processing file: ' + error.message);
        });
    }
    
    function extractTasks() {
        const transcript = transcriptText.value.trim();
        if (!transcript) {
            showError('Please enter or upload a meeting transcript.');
            return;
        }
        
        const boardId = document.getElementById('board-id').value;
        const meetingContext = {
            meeting_type: document.getElementById('meeting-type').value,
            date: document.getElementById('meeting-date').value,
            title: document.getElementById('meeting-title').value || 'Meeting',
            participants: document.getElementById('participants').value
                .split(',')
                .map(p => p.trim())
                .filter(p => p)
        };
        
        // Show processing
        showProcessing();
        
        // API call
        fetch('/api/extract-tasks-from-transcript/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                transcript: transcript,
                board_id: boardId,
                meeting_context: meetingContext
            })
        })
        .then(response => response.json())
        .then(data => {
            hideProcessing();
            if (data.error) {
                showError(data.error);
            } else {
                extractedTasks = data.extracted_tasks || [];
                displayExtractedTasks(data);
            }
        })
        .catch(error => {
            hideProcessing();
            showError('Error extracting tasks: ' + error.message);
        });
    }
    
    function displayExtractedTasks(data) {
        const summary = data.extraction_summary;
        const tasks = data.extracted_tasks;
        const followUps = data.suggested_follow_ups || [];
        const unresolvedItems = data.unresolved_items || [];
        
        // Update summary
        displayExtractionSummary(summary);
        
        // Display tasks
        displayTaskCards(tasks);
        
        // Display additional insights
        displayAdditionalInsights(followUps, unresolvedItems);
        
        // Update UI
        document.getElementById('task-count-badge').textContent = `${tasks.length} tasks found`;
        taskReviewSection.classList.remove('d-none');
        
        // Scroll to results
        taskReviewSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    function displayExtractionSummary(summary) {
        const summaryEl = document.getElementById('extraction-summary');
        const confidenceClass = `confidence-${summary.confidence_level}`;
        
        summaryEl.innerHTML = `
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <h5><i class="fas fa-brain me-2"></i>AI Analysis Summary</h5>
                    <p class="mb-2">${summary.meeting_summary}</p>
                    <small>
                        <span class="confidence-indicator ${confidenceClass}"></span>
                        Confidence: ${summary.confidence_level.toUpperCase()}
                        ${summary.processing_notes ? ' • ' + summary.processing_notes : ''}
                    </small>
                </div>
                <div class="text-end">
                    <div class="h2 mb-0">${summary.total_tasks_found}</div>
                    <small>tasks found</small>
                </div>
            </div>
        `;
    }
    
    function displayTaskCards(tasks) {
        const container = document.getElementById('extracted-tasks-container');
        container.innerHTML = '';
        
        tasks.forEach((task, index) => {
            const taskCard = createTaskCard(task, index);
            container.appendChild(taskCard);
        });
        
        updateSelectionCount();
    }
    
    function createTaskCard(task, index) {
        const cardDiv = document.createElement('div');
        cardDiv.className = 'col-md-6 col-lg-4 mb-3';
        
        // Use accessibility-aware color mapping
        const isColorblindMode = window.PrizmAccessibility && window.PrizmAccessibility.isColorblindModeActive();
        const priorityColors = isColorblindMode ? {
            low: 'secondary',      // Gray
            medium: 'info',        // Blue
            high: 'warning',       // Orange
            urgent: 'danger'       // Red
        } : {
            low: 'success',
            medium: 'warning',
            high: 'danger',
            urgent: 'dark'
        };
        
        cardDiv.innerHTML = `
            <div class="task-card p-3" data-task-index="${index}">
                <div class="form-check mb-2">
                    <input class="form-check-input task-checkbox" type="checkbox" 
                           id="task-${index}" data-task-index="${index}">
                    <label class="form-check-label fw-bold" for="task-${index}">
                        ${escapeHtml(task.title)}
                    </label>
                </div>
                
                <div class="mb-2">
                    <span class="badge bg-${priorityColors[task.priority] || 'secondary'} priority-badge">
                        ${task.priority.toUpperCase()}
                    </span>
                    <span class="badge bg-info priority-badge">
                        ${task.category.replace('_', ' ').toUpperCase()}
                    </span>
                    ${task.estimated_effort ? `<span class="badge bg-light text-dark priority-badge">${task.estimated_effort}</span>` : ''}
                </div>
                
                <p class="text-muted small mb-2">${escapeHtml(task.description)}</p>
                
                ${task.suggested_assignee ? `
                    <div class="mb-2">
                        <small><strong>Suggested assignee:</strong> ${escapeHtml(task.suggested_assignee)}
                        <span class="badge bg-${task.assignee_confidence === 'high' ? 'success' : task.assignee_confidence === 'medium' ? 'warning' : 'danger'} ms-1">
                            ${task.assignee_confidence}
                        </span></small>
                    </div>
                ` : ''}
                
                ${task.due_date_suggestion ? `
                    <div class="mb-2">
                        <small><strong>Suggested due date:</strong> ${task.due_date_suggestion}</small>
                    </div>
                ` : ''}
                
                ${task.success_criteria ? `
                    <div class="mb-2">
                        <small><strong>Success criteria:</strong> ${escapeHtml(task.success_criteria)}</small>
                    </div>
                ` : ''}
                
                ${task.source_context ? `
                    <div class="source-context">
                        <small><strong>From transcript:</strong><br>"${escapeHtml(task.source_context)}"</small>
                    </div>
                ` : ''}
                
                <div class="mt-2">
                    <button type="button" class="btn btn-sm btn-outline-primary me-1 edit-task-btn" 
                            data-task-index="${index}">
                        <i class="fas fa-edit"></i> Edit
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-danger delete-task-btn" 
                            data-task-index="${index}">
                        <i class="fas fa-trash"></i> Remove
                    </button>
                </div>
            </div>
        `;
        
        return cardDiv;
    }
    
    function displayAdditionalInsights(followUps, unresolvedItems) {
        const container = document.getElementById('additional-insights');
        container.innerHTML = '';
        
        if (followUps.length > 0 || unresolvedItems.length > 0) {
            const insightsDiv = document.createElement('div');
            insightsDiv.className = 'col-12';
            
            let html = '<div class="row">';
            
            if (followUps.length > 0) {
                html += `
                    <div class="col-md-6">
                        <div class="card border-left-info">
                            <div class="card-body">
                                <h6 class="text-info"><i class="fas fa-calendar-plus me-2"></i>Suggested Follow-ups</h6>
                                <ul class="list-unstyled mb-0">
                                    ${followUps.map(followUp => `
                                        <li class="mb-2">
                                            <span class="badge bg-info">${followUp.type}</span>
                                            <small class="ms-2">${escapeHtml(followUp.description)} 
                                            ${followUp.timeframe ? `(${followUp.timeframe})` : ''}</small>
                                        </li>
                                    `).join('')}
                                </ul>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            if (unresolvedItems.length > 0) {
                html += `
                    <div class="col-md-6">
                        <div class="card border-left-warning">
                            <div class="card-body">
                                <h6 class="text-warning"><i class="fas fa-question-circle me-2"></i>Items Needing Clarification</h6>
                                <ul class="list-unstyled mb-0">
                                    ${unresolvedItems.map(item => `
                                        <li class="mb-1"><small>${escapeHtml(item)}</small></li>
                                    `).join('')}
                                </ul>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            html += '</div>';
            insightsDiv.innerHTML = html;
            container.appendChild(insightsDiv);
        }
    }
    
    function handleTaskSelection(e) {
        if (e.target.classList.contains('task-checkbox')) {
            const taskIndex = parseInt(e.target.dataset.taskIndex);
            const taskCard = e.target.closest('.task-card');
            
            if (e.target.checked) {
                selectedTasks.add(taskIndex);
                taskCard.classList.add('selected');
            } else {
                selectedTasks.delete(taskIndex);
                taskCard.classList.remove('selected');
            }
            
            updateSelectionCount();
        } else if (e.target.classList.contains('edit-task-btn')) {
            const taskIndex = parseInt(e.target.dataset.taskIndex);
            editTask(taskIndex);
        } else if (e.target.classList.contains('delete-task-btn')) {
            const taskIndex = parseInt(e.target.dataset.taskIndex);
            deleteTask(taskIndex);
        }
    }
    
    function selectAllTasks() {
        selectedTasks.clear();
        document.querySelectorAll('.task-checkbox').forEach((checkbox, index) => {
            checkbox.checked = true;
            selectedTasks.add(index);
            checkbox.closest('.task-card').classList.add('selected');
        });
        updateSelectionCount();
    }
    
    function deselectAllTasks() {
        selectedTasks.clear();
        document.querySelectorAll('.task-checkbox').forEach(checkbox => {
            checkbox.checked = false;
            checkbox.closest('.task-card').classList.remove('selected');
        });
        updateSelectionCount();
    }
    
    function updateSelectionCount() {
        const count = selectedTasks.size;
        const countEl = document.getElementById('selected-count');
        const createBtn = document.getElementById('create-selected-tasks');
        
        if (countEl) {
            countEl.textContent = `${count} task${count !== 1 ? 's' : ''} selected`;
        }
        
        if (createBtn) {
            createBtn.disabled = count === 0;
        }
    }
    
    function editTask(taskIndex) {
        const task = extractedTasks[taskIndex];
        if (!task) return;
        
        // Create a simple edit modal or inline editing
        const newTitle = prompt('Edit task title:', task.title);
        if (newTitle && newTitle !== task.title) {
            task.title = newTitle;
            // Re-render the task card
            displayTaskCards(extractedTasks);
        }
    }
    
    function deleteTask(taskIndex) {
        if (confirm('Are you sure you want to remove this task?')) {
            extractedTasks.splice(taskIndex, 1);
            selectedTasks.clear(); // Reset selection
            displayTaskCards(extractedTasks);
            
            // Update task count
            document.getElementById('task-count-badge').textContent = `${extractedTasks.length} tasks found`;
        }
    }
    
    function createSelectedTasks() {
        if (selectedTasks.size === 0) return;
        
        const approvedTasks = Array.from(selectedTasks).map(index => extractedTasks[index]);
        const boardId = document.getElementById('board-id').value;
        
        showLoading('Creating tasks...', 'Please wait while we add the selected tasks to your board.');
        
        fetch('/api/create-tasks-from-extraction/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                board_id: boardId,
                approved_tasks: approvedTasks
            })
        })
        .then(response => response.json())
        .then(data => {
            hideLoading();
            if (data.success) {
                showTaskCreationSuccess(data);
            } else {
                showError(data.error || 'Failed to create tasks');
            }
        })
        .catch(error => {
            hideLoading();
            showError('Error creating tasks: ' + error.message);
        });
    }
    
    function showTaskCreationSuccess(data) {
        const modal = new bootstrap.Modal(document.getElementById('success-modal'));
        const detailsEl = document.getElementById('success-details');
        
        let html = `
            <div class="alert alert-success">
                <h6><i class="fas fa-check-circle me-2"></i>Successfully created ${data.total_created} task${data.total_created !== 1 ? 's' : ''}!</h6>
            </div>
        `;
        
        if (data.created_tasks.length > 0) {
            html += '<h6>Created Tasks:</h6><ul>';
            data.created_tasks.forEach(task => {
                html += `<li><a href="${task.url}" target="_blank">${escapeHtml(task.title)}</a></li>`;
            });
            html += '</ul>';
        }
        
        if (data.errors.length > 0) {
            html += '<div class="alert alert-warning mt-3"><h6>Some issues occurred:</h6><ul>';
            data.errors.forEach(error => {
                html += `<li>${escapeHtml(error)}</li>`;
            });
            html += '</ul></div>';
        }
        
        detailsEl.innerHTML = html;
        modal.show();
    }
    
    // Utility functions
    function showProcessing() {
        aiProcessing.classList.remove('d-none');
        taskReviewSection.classList.add('d-none');
        extractTasksBtn.disabled = true;
    }
    
    function hideProcessing() {
        aiProcessing.classList.add('d-none');
        extractTasksBtn.disabled = false;
    }
    
    function showLoading(title, message) {
        // Simple loading implementation - you can enhance this
        showProcessing();
        const processingBody = aiProcessing.querySelector('.card-body');
        processingBody.innerHTML = `
            <div class="spinner-border text-info mb-3" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <h5>${title}</h5>
            <p class="text-muted">${message}</p>
        `;
    }
    
    function hideLoading() {
        hideProcessing();
    }
    
    function showError(message) {
        // Create and show error alert
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show';
        alertDiv.innerHTML = `
            <i class="fas fa-exclamation-triangle me-2"></i>${escapeHtml(message)}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Insert at top of page
        const container = document.querySelector('.container-fluid');
        container.insertBefore(alertDiv, container.firstChild);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
    
    function showSuccess(message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-success alert-dismissible fade show';
        alertDiv.innerHTML = `
            <i class="fas fa-check-circle me-2"></i>${escapeHtml(message)}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.container-fluid');
        container.insertBefore(alertDiv, container.firstChild);
        
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 3000);
    }
    
    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
    
    function escapeHtml(text) {
        // Handle null, undefined, or empty values
        if (text === null || text === undefined) {
            return '';
        }
        
        // Handle objects and arrays - convert to readable string
        if (typeof text === 'object') {
            // If it's an array, join with commas
            if (Array.isArray(text)) {
                return text.map(item => escapeHtml(item)).join(', ');
            }
            // If it's an object, try to extract a meaningful value
            if (text.toString && text.toString() !== '[object Object]') {
                text = text.toString();
            } else {
                text = text.name || text.title || text.value || text.description || JSON.stringify(text);
            }
        }
        
        // Convert to string if not already
        text = String(text);
        
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
});
