/**
 * Command Palette - Quick Task Search with AI Semantic Search
 * Ctrl+K to open, live filtering, AI-powered semantic matching
 */

let commandPaletteState = {
    isOpen: false,
    searchMode: 'ai', // 'ai' or 'keyword'
    selectedIndex: 0,
    allTasks: [],
    filteredTasks: [],
    searchTimeout: null
};

document.addEventListener('DOMContentLoaded', function() {
    initializeCommandPalette();
});

/**
 * Initialize command palette functionality
 */
function initializeCommandPalette() {
    // Keyboard shortcut (Alt+K)
    // Use capture phase to intercept before browser shortcuts
    document.addEventListener('keydown', function(e) {
        // Alt+K (check both lowercase and uppercase)
        if (e.altKey && !e.ctrlKey && !e.metaKey && (e.key === 'k' || e.key === 'K')) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            openCommandPalette();
            return false;
        }
        
        // ESC to close
        if (e.key === 'Escape' && commandPaletteState.isOpen) {
            e.preventDefault();
            closeCommandPalette();
        }
    }, true); // Use capture phase
    
    // Search input handler
    const searchInput = document.getElementById('commandPaletteInput');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(handleSearch, 300));
        
        // Keyboard navigation in results
        searchInput.addEventListener('keydown', handleKeyboardNavigation);
    }
    
    // Search mode toggle
    const modeToggle = document.getElementById('searchModeToggle');
    if (modeToggle) {
        modeToggle.addEventListener('click', toggleSearchMode);
    }
    
    // Close on backdrop click
    const modal = document.getElementById('commandPaletteModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeCommandPalette();
            }
        });
    }
    
    // Collect all tasks on page load
    collectAllTasks();
}

/**
 * Collect all tasks from the board for quick filtering
 */
function collectAllTasks() {
    commandPaletteState.allTasks = [];
    
    // Get all task cards on the board
    const taskCards = document.querySelectorAll('.kanban-task');
    
    taskCards.forEach(card => {
        const taskId = card.getAttribute('data-task-id');
        const titleElement = card.querySelector('.task-title a');
        const title = titleElement ? titleElement.textContent.trim() : '';
        const descriptionElement = card.querySelector('.task-description');
        const description = descriptionElement ? descriptionElement.textContent.trim() : '';
        const column = card.closest('.kanban-column');
        const columnName = column ? column.querySelector('.column-name-text').textContent.trim() : '';
        
        // Extract priority
        const priorityElement = card.querySelector('.task-priority');
        const priority = priorityElement ? priorityElement.textContent.trim() : '';
        
        // Extract labels
        const labels = [];
        card.querySelectorAll('.task-label').forEach(label => {
            labels.push(label.textContent.trim());
        });
        
        // Extract assignee
        const assigneeElement = card.querySelector('.task-assignee');
        const assignee = assigneeElement ? assigneeElement.textContent.trim() : '';
        
        commandPaletteState.allTasks.push({
            id: taskId,
            title: title,
            description: description,
            column: columnName,
            priority: priority,
            labels: labels,
            assignee: assignee,
            element: card
        });
    });
    
    console.log(`Command Palette: Indexed ${commandPaletteState.allTasks.length} tasks`);
}

/**
 * Open command palette modal
 */
function openCommandPalette() {
    commandPaletteState.isOpen = true;
    commandPaletteState.selectedIndex = 0;
    
    const modal = new bootstrap.Modal(document.getElementById('commandPaletteModal'));
    modal.show();
    
    // Focus search input
    setTimeout(() => {
        const input = document.getElementById('commandPaletteInput');
        if (input) {
            input.value = '';
            input.focus();
        }
        
        // Reset view
        showEmptyState();
    }, 100);
}

/**
 * Close command palette modal
 */
function closeCommandPalette() {
    commandPaletteState.isOpen = false;
    
    const modalElement = document.getElementById('commandPaletteModal');
    const modal = bootstrap.Modal.getInstance(modalElement);
    if (modal) {
        modal.hide();
    }
    
    // Clear any highlights
    clearTaskHighlights();
}

/**
 * Handle search input
 */
function handleSearch(e) {
    const query = e.target.value.trim();
    
    if (!query) {
        showEmptyState();
        return;
    }
    
    if (commandPaletteState.searchMode === 'ai' && query.length >= 3) {
        // AI semantic search
        performAISearch(query);
    } else {
        // Quick keyword search
        performKeywordSearch(query);
    }
}

/**
 * Perform quick keyword search (instant filtering)
 */
function performKeywordSearch(query) {
    const queryLower = query.toLowerCase();
    
    commandPaletteState.filteredTasks = commandPaletteState.allTasks.filter(task => {
        return task.title.toLowerCase().includes(queryLower) ||
               task.description.toLowerCase().includes(queryLower) ||
               task.column.toLowerCase().includes(queryLower) ||
               task.priority.toLowerCase().includes(queryLower) ||
               task.labels.some(label => label.toLowerCase().includes(queryLower)) ||
               task.assignee.toLowerCase().includes(queryLower);
    });
    
    displayResults(commandPaletteState.filteredTasks, false);
}

/**
 * Perform AI semantic search
 */
function performAISearch(query) {
    showLoadingState('AI is analyzing your search...');
    
    fetch(`/api/search-tasks-semantic/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            query: query,
            board_id: getBoardId()
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && data.results) {
            commandPaletteState.filteredTasks = data.results;
            displayResults(data.results, true, data.explanation);
        } else {
            // Fallback to keyword search
            performKeywordSearch(query);
        }
    })
    .catch(error => {
        console.error('AI search failed, falling back to keyword search:', error);
        performKeywordSearch(query);
    });
}

/**
 * Display search results
 */
function displayResults(results, isAISearch = false, explanation = null) {
    const resultsList = document.getElementById('commandPaletteResultsList');
    const emptyState = document.getElementById('commandPaletteEmpty');
    const loadingState = document.getElementById('commandPaletteLoading');
    const resultCount = document.getElementById('resultCount');
    
    // Hide empty and loading states
    emptyState.classList.add('d-none');
    loadingState.classList.add('d-none');
    
    if (results.length === 0) {
        resultsList.classList.add('d-none');
        emptyState.classList.remove('d-none');
        emptyState.innerHTML = `
            <i class="fas fa-search fa-3x mb-3 opacity-25"></i>
            <p class="mb-1">No tasks found</p>
            <small class="text-muted">Try a different search term</small>
        `;
        resultCount.textContent = '';
        return;
    }
    
    // Show results
    resultsList.classList.remove('d-none');
    resultCount.textContent = `${results.length} result${results.length !== 1 ? 's' : ''}`;
    
    // Build results HTML
    let html = '';
    
    // Show AI explanation if available
    if (isAISearch && explanation) {
        html += `
            <div class="list-group-item bg-light border-0">
                <small class="text-muted">
                    <i class="fas fa-brain text-primary me-1"></i> 
                    <strong>AI Understanding:</strong> ${explanation}
                </small>
            </div>
        `;
    }
    
    results.forEach((task, index) => {
        const isSelected = index === commandPaletteState.selectedIndex;
        const taskData = commandPaletteState.allTasks.find(t => t.id == task.id);
        
        html += `
            <div class="list-group-item list-group-item-action command-palette-result ${isSelected ? 'active' : ''}" 
                 data-task-id="${task.id}" 
                 data-index="${index}"
                 style="cursor: pointer; border-left: 3px solid ${getPriorityColor(taskData?.priority || task.priority)};">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6 class="mb-1">
                            ${task.title}
                            ${task.relevance_score ? `<span class="badge bg-success ms-2" style="font-size: 0.65rem;">${Math.round(task.relevance_score * 100)}% match</span>` : ''}
                        </h6>
                        ${task.description ? `<p class="mb-1 small text-muted text-truncate" style="max-width: 600px;">${task.description}</p>` : ''}
                        <div class="d-flex gap-2 mt-2">
                            <span class="badge bg-secondary" style="font-size: 0.7rem;">
                                <i class="fas fa-columns me-1"></i> ${taskData?.column || task.column || 'Unknown'}
                            </span>
                            ${taskData?.priority || task.priority ? `
                                <span class="badge" style="background-color: ${getPriorityColor(taskData?.priority || task.priority)}; font-size: 0.7rem;">
                                    ${taskData?.priority || task.priority}
                                </span>
                            ` : ''}
                            ${task.match_reason ? `<small class="text-muted ms-2"><i class="fas fa-lightbulb me-1"></i>${task.match_reason}</small>` : ''}
                        </div>
                    </div>
                    <div class="text-end">
                        <kbd class="bg-light text-muted px-2 py-1" style="font-size: 0.7rem;">Enter</kbd>
                    </div>
                </div>
            </div>
        `;
    });
    
    resultsList.innerHTML = html;
    
    // Add click handlers
    document.querySelectorAll('.command-palette-result').forEach(item => {
        item.addEventListener('click', function() {
            const taskId = this.getAttribute('data-task-id');
            navigateToTask(taskId);
        });
    });
}

/**
 * Handle keyboard navigation
 */
function handleKeyboardNavigation(e) {
    const results = commandPaletteState.filteredTasks;
    
    if (results.length === 0) return;
    
    switch(e.key) {
        case 'ArrowDown':
            e.preventDefault();
            commandPaletteState.selectedIndex = Math.min(
                commandPaletteState.selectedIndex + 1,
                results.length - 1
            );
            updateSelectedResult();
            break;
            
        case 'ArrowUp':
            e.preventDefault();
            commandPaletteState.selectedIndex = Math.max(
                commandPaletteState.selectedIndex - 1,
                0
            );
            updateSelectedResult();
            break;
            
        case 'Enter':
            e.preventDefault();
            const selectedTask = results[commandPaletteState.selectedIndex];
            if (selectedTask) {
                navigateToTask(selectedTask.id);
            }
            break;
    }
}

/**
 * Update selected result styling
 */
function updateSelectedResult() {
    document.querySelectorAll('.command-palette-result').forEach((item, index) => {
        if (index === commandPaletteState.selectedIndex) {
            item.classList.add('active');
            item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        } else {
            item.classList.remove('active');
        }
    });
}

/**
 * Navigate to task and highlight it
 */
function navigateToTask(taskId) {
    closeCommandPalette();
    
    // Find task card
    const taskCard = document.querySelector(`.kanban-task[data-task-id="${taskId}"]`);
    if (!taskCard) {
        // If task not found on current view, open task detail page
        window.location.href = `/tasks/${taskId}/`;
        return;
    }
    
    // Clear existing highlights
    clearTaskHighlights();
    
    // Scroll to task with smooth animation
    taskCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Add highlight animation
    taskCard.classList.add('task-highlighted');
    
    // Flash effect
    setTimeout(() => {
        taskCard.style.transition = 'all 0.3s ease';
        taskCard.style.transform = 'scale(1.05)';
        taskCard.style.boxShadow = '0 8px 24px rgba(13, 110, 253, 0.4)';
        taskCard.style.borderColor = '#0d6efd';
        taskCard.style.borderWidth = '3px';
    }, 100);
    
    setTimeout(() => {
        taskCard.style.transform = 'scale(1)';
        taskCard.style.boxShadow = '';
    }, 500);
    
    // Remove highlight after 3 seconds
    setTimeout(() => {
        taskCard.classList.remove('task-highlighted');
        taskCard.style.borderColor = '';
        taskCard.style.borderWidth = '';
    }, 3000);
}

/**
 * Clear all task highlights
 */
function clearTaskHighlights() {
    document.querySelectorAll('.task-highlighted').forEach(task => {
        task.classList.remove('task-highlighted');
        task.style.transform = '';
        task.style.boxShadow = '';
        task.style.borderColor = '';
        task.style.borderWidth = '';
    });
}

/**
 * Toggle between AI and keyword search
 */
function toggleSearchMode() {
    commandPaletteState.searchMode = commandPaletteState.searchMode === 'ai' ? 'keyword' : 'ai';
    
    const toggle = document.getElementById('searchModeToggle');
    const input = document.getElementById('commandPaletteInput');
    
    if (commandPaletteState.searchMode === 'ai') {
        toggle.innerHTML = '<i class="fas fa-brain me-1"></i> AI Search';
        toggle.classList.remove('bg-secondary');
        toggle.classList.add('bg-primary');
        input.placeholder = "Search tasks... (try: 'database migration' or 'urgent tasks')";
    } else {
        toggle.innerHTML = '<i class="fas fa-keyboard me-1"></i> Keyword';
        toggle.classList.remove('bg-primary');
        toggle.classList.add('bg-secondary');
        input.placeholder = "Search by keyword...";
    }
    
    // Re-run search if there's a query
    if (input.value.trim()) {
        handleSearch({ target: input });
    }
}

/**
 * Show empty state
 */
function showEmptyState() {
    document.getElementById('commandPaletteEmpty').classList.remove('d-none');
    document.getElementById('commandPaletteLoading').classList.add('d-none');
    document.getElementById('commandPaletteResultsList').classList.add('d-none');
    document.getElementById('resultCount').textContent = '';
}

/**
 * Show loading state
 */
function showLoadingState(message = 'Searching...') {
    document.getElementById('commandPaletteEmpty').classList.add('d-none');
    document.getElementById('commandPaletteLoading').classList.remove('d-none');
    document.getElementById('commandPaletteResultsList').classList.add('d-none');
    document.getElementById('loadingText').textContent = message;
}

/**
 * Get priority color
 */
function getPriorityColor(priority) {
    const colors = {
        'urgent': '#dc3545',
        'high': '#fd7e14',
        'medium': '#ffc107',
        'low': '#20c997'
    };
    return colors[priority?.toLowerCase()] || '#6c757d';
}

/**
 * Get CSRF token
 */
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}

/**
 * Get current board ID
 */
function getBoardId() {
    const boardElement = document.getElementById('kanban-board');
    return boardElement?.getAttribute('data-board-id') || 
           window.location.pathname.match(/\/boards\/(\d+)\//)?.[1] || '';
}

/**
 * Debounce function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Refresh task index when new tasks are added
window.addEventListener('taskCreated', collectAllTasks);
window.addEventListener('taskUpdated', collectAllTasks);
