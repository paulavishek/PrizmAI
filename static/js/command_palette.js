/**
 * Task Search - Live Filtering with AI Semantic Search
 * Always-visible search bar that filters tasks in real-time
 */

// Prevent duplicate execution if script is loaded multiple times
if (typeof window.taskSearchInitialized === 'undefined') {
    window.taskSearchInitialized = true;

    // Initialize search state
    var searchState = {
        searchMode: 'keyword', // 'ai' or 'keyword'
        searchScope: 'this_board', // 'this_board' or 'all_boards'
        allTasks: [],
        filteredTasks: [],
        searchTimeout: null,
        currentQuery: ''
    };

document.addEventListener('DOMContentLoaded', function() {
    initializeTaskSearch();
});

/**
 * Initialize task search functionality
 */
function initializeTaskSearch() {
    console.log('Task Search: Initializing...');
    
    // Collect all tasks on page load
    collectAllTasks();
    
    // Live search input handler
    const liveSearchInput = document.getElementById('liveSearchInput');
    if (liveSearchInput) {
        liveSearchInput.addEventListener('input', debounce(handleLiveSearch, 300));
        
        // Focus on search when user presses '/' key (common UX pattern)
        document.addEventListener('keydown', function(e) {
            if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
                e.preventDefault();
                liveSearchInput.focus();
            }
            // ESC to clear search and unfocus
            if (e.key === 'Escape' && document.activeElement === liveSearchInput) {
                clearSearch();
                liveSearchInput.blur();
            }
        });
    }
    
    // Clear search button
    const clearBtn = document.getElementById('clearSearchBtn');
    if (clearBtn) {
        clearBtn.addEventListener('click', clearSearch);
    }
    
    // Search mode toggle
    const keywordMode = document.getElementById('keywordMode');
    const aiMode = document.getElementById('aiMode');
    const aiTip = document.getElementById('aiSearchTip');
    
    if (keywordMode) {
        keywordMode.addEventListener('change', function() {
            searchState.searchMode = 'keyword';
            if (aiTip) aiTip.style.display = 'none';
            // Re-run search if there's a query
            if (searchState.currentQuery) {
                handleLiveSearch({ target: document.getElementById('liveSearchInput') });
            }
        });
    }
    
    if (aiMode) {
        aiMode.addEventListener('change', function() {
            searchState.searchMode = 'ai';
            if (aiTip) aiTip.style.display = 'block';
            // Re-run search if there's a query
            if (searchState.currentQuery) {
                handleLiveSearch({ target: document.getElementById('liveSearchInput') });
            }
        });
    }

    // Scope toggle: This Board / All Boards
    const scopeThisBoard = document.getElementById('scopeThisBoard');
    const scopeAllBoards = document.getElementById('scopeAllBoards');
    const searchModeGroup = document.getElementById('searchModeGroup');
    const globalSearchResultsEl = document.getElementById('globalSearchResults');

    function onScopeChange() {
        const allBoardsActive = scopeAllBoards && scopeAllBoards.checked;
        searchState.searchScope = allBoardsActive ? 'all_boards' : 'this_board';
        // Hide AI/keyword toggle when All Boards is active (global search is always keyword)
        if (searchModeGroup) searchModeGroup.style.display = allBoardsActive ? 'none' : '';
        if (globalSearchResultsEl) globalSearchResultsEl.style.display = 'none';
        if (searchState.currentQuery) {
            handleLiveSearch({ target: document.getElementById('liveSearchInput') });
        } else {
            clearSearch();
        }
    }

    if (scopeThisBoard) scopeThisBoard.addEventListener('change', onScopeChange);
    if (scopeAllBoards) scopeAllBoards.addEventListener('change', onScopeChange);

    console.log('Task Search: Initialized successfully!');
}

/**
 * Collect all tasks from the board for quick filtering
 */
function collectAllTasks() {
    searchState.allTasks = [];
    
    // Get all task cards on the board.
    // Main board uses the v2 layout (.kanban-task-v2); the demo board still uses
    // the legacy .kanban-task layout. Support both so live search works on each.
    const taskCards = document.querySelectorAll('.kanban-task-v2, .kanban-task');

    taskCards.forEach(card => {
        // Try data-task-id first, then fallback to parsing the id attribute (format: "task-123")
        let taskId = card.getAttribute('data-task-id');
        if (!taskId) {
            const elementId = card.getAttribute('id');
            if (elementId && elementId.startsWith('task-')) {
                taskId = elementId.replace('task-', '');
            }
        }
        // Title: v2 uses .card-task-title; legacy uses .task-title a
        const titleElement = card.querySelector('.card-task-title, .task-title a');
        const title = titleElement ? titleElement.textContent.trim() : '';
        // Card id (e.g. "SD-17314") is searchable text too (v2 only)
        const taskIdElement = card.querySelector('.card-task-id');
        const taskRef = taskIdElement ? taskIdElement.textContent.trim() : '';
        // Description: v2 cards don't render it; legacy uses .task-description
        const descriptionElement = card.querySelector('.task-description, .card-task-description');
        const description = descriptionElement ? descriptionElement.textContent.trim() : '';
        const column = card.closest('.kanban-column');
        const columnName = column ? column.querySelector('.column-name-text')?.textContent.trim() : '';

        // Extract priority
        const priorityElement = card.querySelector('.task-priority, .card-priority');
        const priority = priorityElement ? priorityElement.textContent.trim() : '';

        // Extract labels (v2 uses .card-label-primary)
        const labels = [];
        card.querySelectorAll('.task-label, .card-label-primary').forEach(label => {
            labels.push(label.textContent.trim());
        });

        // Extract assignee
        const assigneeElement = card.querySelector('.task-assignee, .card-assignee');
        const assignee = assigneeElement ? assigneeElement.textContent.trim() : '';
        
        searchState.allTasks.push({
            id: taskId,
            taskRef: taskRef,
            title: title,
            description: description,
            column: columnName,
            priority: priority,
            labels: labels,
            assignee: assignee,
            element: card
        });
    });
    
    console.log(`Task Search: Indexed ${searchState.allTasks.length} tasks`);
    updateColumnTaskCounts();
}

/**
 * Handle live search input
 */
function handleLiveSearch(e) {
    const query = e.target.value.trim();
    searchState.currentQuery = query;
    
    const clearBtn = document.getElementById('clearSearchBtn');
    const resultCount = document.getElementById('searchResultCount');
    
    if (!query) {
        // Clear filter - show all tasks
        clearSearch();
        return;
    }
    
    // Show clear button
    if (clearBtn) clearBtn.style.display = 'block';
    
    if (searchState.searchMode === 'ai' && query.length >= 3 && searchState.searchScope !== 'all_boards') {
        // AI semantic search (board scope only)
        performAISearch(query);
    } else if (searchState.searchScope === 'all_boards' && query.length >= 2) {
        // Global cross-board keyword search
        performGlobalSearch(query);
    } else {
        // Quick keyword search - instant filtering
        performKeywordFilter(query);
    }
}

/**
 * Perform quick keyword filter (instant, no API call)
 */
function performKeywordFilter(query) {
    const queryLower = query.toLowerCase();
    let matchCount = 0;
    
    searchState.allTasks.forEach(task => {
        // Remove any AI match badges when switching to keyword search
        removeAIMatchBadge(task.element);
        
        const matches =
            task.title.toLowerCase().includes(queryLower) ||
            (task.taskRef && task.taskRef.toLowerCase().includes(queryLower)) ||
            task.description.toLowerCase().includes(queryLower) ||
            task.column.toLowerCase().includes(queryLower) ||
            task.priority.toLowerCase().includes(queryLower) ||
            task.labels.some(label => label.toLowerCase().includes(queryLower)) ||
            task.assignee.toLowerCase().includes(queryLower);
        
        if (matches) {
            task.element.classList.remove('filtered-out');
            matchCount++;
        } else {
            task.element.classList.add('filtered-out');
        }
    });
    
    // Update result count
    const resultCount = document.getElementById('searchResultCount');
    if (resultCount) {
        resultCount.textContent = `${matchCount} of ${searchState.allTasks.length} tasks`;
        resultCount.style.display = 'inline-block';
    }
    
    // Update column task counts
    updateColumnTaskCounts();
    
    console.log(`Keyword Filter: Showing ${matchCount} of ${searchState.allTasks.length} tasks`);
}

/**
 * Perform AI semantic search
 */
function performAISearch(query) {
    const resultCount = document.getElementById('searchResultCount');
    if (resultCount) {
        resultCount.textContent = 'AI searching...';
        resultCount.style.display = 'inline-block';
        resultCount.classList.add('bg-primary');
        resultCount.classList.remove('bg-secondary');
    }
    
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
        console.log('AI Search API Response:', data);
        console.log('Board ID sent:', getBoardId());
        
        if (resultCount) {
            resultCount.classList.remove('bg-primary');
            resultCount.classList.add('bg-secondary');
        }
        
        if (data.success && data.results && data.results.length > 0) {
            // Apply filter based on AI results
            applyAISearchResults(data.results, query);
        } else {
            // Fallback to keyword search
            console.log('AI search returned no results or failed, falling back to keyword search. Data:', data);
            performKeywordFilter(query);
        }
    })
    .catch(error => {
        console.error('AI search error:', error);
        if (resultCount) {
            resultCount.classList.remove('bg-primary');
            resultCount.classList.add('bg-secondary');
        }
        // Fallback to keyword search
        performKeywordFilter(query);
    });
}

/**
 * Apply AI search results as filter
 */
function applyAISearchResults(results, query) {
    console.log('AI Search Results:', results);
    console.log('All Tasks on page:', searchState.allTasks.map(t => ({id: t.id, title: t.title})));
    
    const matchingIds = results.map(r => String(r.id));
    console.log('Matching IDs from AI:', matchingIds);
    
    let matchCount = 0;
    
    searchState.allTasks.forEach(task => {
        const taskIdStr = String(task.id);
        const isMatch = matchingIds.includes(taskIdStr);
        console.log(`Task ${taskIdStr} (${task.title}): match=${isMatch}`);
        
        if (isMatch) {
            task.element.classList.remove('filtered-out');
            matchCount++;
            
            // Add AI match indicator if available
            const matchInfo = results.find(r => String(r.id) === taskIdStr);
            if (matchInfo && matchInfo.relevance_score) {
                addAIMatchBadge(task.element, matchInfo.relevance_score, matchInfo.match_reason);
            }
        } else {
            task.element.classList.add('filtered-out');
            removeAIMatchBadge(task.element);
        }
    });
    
    // Update result count
    const resultCount = document.getElementById('searchResultCount');
    if (resultCount) {
        resultCount.innerHTML = `<i class="fas fa-wand-magic-sparkles me-1"></i>${matchCount} AI matches`;
        resultCount.style.display = 'inline-block';
    }
    
    // Update column task counts
    updateColumnTaskCounts();
    
    console.log(`AI Search: Showing ${matchCount} of ${searchState.allTasks.length} tasks`);
}

/**
 * Add AI match badge to task card
 */
function addAIMatchBadge(element, score, reason) {
    removeAIMatchBadge(element);
    
    const badge = document.createElement('div');
    badge.className = 'ai-match-badge';
    badge.style.cssText = 'position: absolute; top: 5px; right: 5px; background: linear-gradient(135deg, #667eea, #764ba2); color: white; font-size: 0.7rem; padding: 2px 6px; border-radius: 10px; z-index: 10;';
    badge.innerHTML = `<i class="fas fa-wand-magic-sparkles me-1"></i>${Math.round(score * 100)}%`;
    badge.title = reason || 'AI match';
    
    element.style.position = 'relative';
    element.appendChild(badge);
}

/**
 * Remove AI match badge from task card
 */
function removeAIMatchBadge(element) {
    const existing = element.querySelector('.ai-match-badge');
    if (existing) existing.remove();
}

/**
 * Perform global cross-board search via the REST API.
 * Results are shown in a dropdown panel; board cards are not filtered.
 */
function performGlobalSearch(query) {
    const resultCount = document.getElementById('searchResultCount');
    const globalResultsEl = document.getElementById('globalSearchResults');

    if (resultCount) {
        resultCount.textContent = 'Searching…';
        resultCount.style.display = 'inline-block';
    }

    // Show all board cards (not filtered) since we display results externally
    searchState.allTasks.forEach(task => {
        task.element.classList.remove('filtered-out');
        removeAIMatchBadge(task.element);
    });
    updateColumnTaskCounts();

    fetch('/api/v1/search/global/?q=' + encodeURIComponent(query), {
        method: 'GET',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin'
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        var tasks = data.tasks || [];
        var boards = data.boards || [];
        var totalCount = tasks.length + boards.length;

        if (resultCount) {
            resultCount.textContent = totalCount + ' results (all boards)';
            resultCount.style.display = 'inline-block';
        }

        if (!globalResultsEl) return;

        if (totalCount === 0) {
            globalResultsEl.innerHTML = '<p class="text-muted small mb-0 py-1">No results found across your boards.</p>';
            globalResultsEl.style.display = 'block';
            return;
        }

        var html = '<div class="global-search-results border rounded bg-white shadow-sm p-2" style="max-height:340px;overflow-y:auto;">';

        if (boards.length > 0) {
            html += '<div class="fw-semibold text-muted small px-1 mb-1" style="text-transform:uppercase;letter-spacing:.05em;">Boards</div>';
            boards.forEach(function(b) {
                html += '<a href="' + escapeAttr(b.url) + '" class="d-flex align-items-center gap-2 text-decoration-none text-dark px-2 py-1 rounded hover-bg" style="cursor:pointer;">'
                    + '<i class="fas fa-columns text-primary me-1" style="width:16px;"></i>'
                    + '<span>' + escapeHtml(b.name) + '</span>'
                    + '</a>';
            });
            if (tasks.length > 0) html += '<hr class="my-1">';
        }

        if (tasks.length > 0) {
            html += '<div class="fw-semibold text-muted small px-1 mb-1" style="text-transform:uppercase;letter-spacing:.05em;">Tasks</div>';
            tasks.forEach(function(t) {
                var priorityClass = t.priority === 'high' ? 'text-danger' : t.priority === 'medium' ? 'text-warning' : 'text-secondary';
                html += '<a href="' + escapeAttr(t.url) + '" class="d-flex align-items-start gap-2 text-decoration-none text-dark px-2 py-1 rounded hover-bg" style="cursor:pointer;">'
                    + '<i class="fas fa-check-square ' + priorityClass + ' mt-1" style="width:16px;"></i>'
                    + '<div style="min-width:0;">'
                    + '<div class="text-truncate fw-medium">' + escapeHtml(t.title) + '</div>'
                    + '<div class="small text-muted">'
                    + '<span class="badge bg-light text-dark border me-1">' + escapeHtml(t.board_name) + '</span>'
                    + escapeHtml(t.column)
                    + (t.assignee ? ' &middot; ' + escapeHtml(t.assignee) : '')
                    + '</div></div></a>';
            });
        }

        html += '</div>';
        globalResultsEl.innerHTML = html;
        globalResultsEl.style.display = 'block';
    })
    .catch(function(err) {
        console.error('Global search error:', err);
        if (resultCount) resultCount.style.display = 'none';
        if (globalResultsEl) globalResultsEl.style.display = 'none';
    });
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escapeAttr(url) {
    if (!url) return '#';
    // Only allow relative paths and safe absolute URLs
    if (/^https?:\/\//i.test(url) || url.startsWith('/')) return escapeHtml(url);
    return '#';
}

/**
 * Clear search and show all tasks
 */
function clearSearch() {
    const liveSearchInput = document.getElementById('liveSearchInput');
    const clearBtn = document.getElementById('clearSearchBtn');
    const resultCount = document.getElementById('searchResultCount');
    
    if (liveSearchInput) liveSearchInput.value = '';
    if (clearBtn) clearBtn.style.display = 'none';
    if (resultCount) resultCount.style.display = 'none';
    
    searchState.currentQuery = '';
    
    // Show all tasks
    searchState.allTasks.forEach(task => {
        task.element.classList.remove('filtered-out');
        removeAIMatchBadge(task.element);
    });
    
    // Hide global search results panel
    const globalResultsEl = document.getElementById('globalSearchResults');
    if (globalResultsEl) globalResultsEl.style.display = 'none';

    // Update column task counts
    updateColumnTaskCounts();
    
    // Hide live filter badge if exists
    const badge = document.getElementById('liveFilterBadge');
    if (badge) badge.classList.remove('active');
    
    console.log('Search: Cleared - showing all tasks');
}

/**
 * Update column task counts based on visible tasks
 */
function updateColumnTaskCounts() {
    document.querySelectorAll('.kanban-column').forEach(column => {
        const visibleTasks = column.querySelectorAll('.kanban-task-v2:not(.filtered-out), .kanban-task:not(.filtered-out)').length;
        const countElement = column.querySelector('.column-task-count, .column-task-count-badge');
        if (countElement) {
            countElement.textContent = visibleTasks;
        }
    });
}

/**
 * Get CSRF token
 */
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
           document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
}

/**
 * Get current board ID
 */
function getBoardId() {
    const boardElement = document.getElementById('kanban-board');
    return boardElement?.getAttribute('data-board-id') || 
           window.location.pathname.match(/\/boards?\/(\d+)\//)?.[1] || 
           window.location.pathname.match(/\/demo\/board\/(\d+)/)?.[1] || '';
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

// Make functions available globally
window.clearSearch = clearSearch;
window.collectAllTasks = collectAllTasks;

} // End of taskSearchInitialized check
