/**
 * AI Timeline Analysis JavaScript
 * Handles Critical Path and Timeline analysis features for the analytics page
 */

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('AI Timeline module loaded');
    initializeTimelineFeatures();
});

function initializeTimelineFeatures() {
    // Critical Path Analysis button
    const criticalPathBtn = document.getElementById('analyze-critical-path-btn');
    if (criticalPathBtn) {
        criticalPathBtn.addEventListener('click', function() {
            const boardId = this.getAttribute('data-board-id');
            analyzeCriticalPath(boardId);
        });
    }
    
    // Timeline Analysis button
    const timelineBtn = document.getElementById('analyze-timeline-btn');
    if (timelineBtn) {
        timelineBtn.addEventListener('click', function() {
            const boardId = this.getAttribute('data-board-id');
            analyzeTimeline(boardId);
        });
    }
}

function analyzeCriticalPath(boardId) {
    const btn = document.getElementById('analyze-critical-path-btn');
    const spinner = document.getElementById('critical-path-spinner');
    const container = document.getElementById('critical-path-container');
    const placeholder = document.getElementById('critical-path-placeholder');
    const contentElement = document.getElementById('critical-path-content');
    
    if (!btn) return;
    
    // Show loading state
    btn.disabled = true;
    if (spinner) spinner.classList.remove('d-none');
    
    fetch('/api/analyze-critical-path/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            board_id: boardId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Hide placeholder and show content
        if (placeholder) placeholder.classList.add('d-none');
        if (container) container.classList.remove('d-none');
        
        // Format the critical path results
        if (contentElement) {
            contentElement.innerHTML = formatCriticalPathResults(data);
        }
    })
    .catch(error => {
        console.error('Error analyzing critical path:', error);
        if (contentElement) {
            contentElement.innerHTML = '<div class="alert alert-danger">Failed to analyze critical path. Please try again.</div>';
        }
        if (placeholder) placeholder.classList.add('d-none');
        if (container) container.classList.remove('d-none');
    })
    .finally(() => {
        // Hide loading state
        btn.disabled = false;
        if (spinner) spinner.classList.add('d-none');
    });
}

function analyzeTimeline(boardId) {
    const btn = document.getElementById('analyze-timeline-btn');
    const spinner = document.getElementById('timeline-spinner');
    const container = document.getElementById('timeline-container');
    const placeholder = document.getElementById('timeline-placeholder');
    const contentElement = document.getElementById('timeline-content');
    
    if (!btn) return;
    
    // Show loading state
    btn.disabled = true;
    if (spinner) spinner.classList.remove('d-none');
    
    fetch('/api/analyze-timeline/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            board_id: boardId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Hide placeholder and show content
        if (placeholder) placeholder.classList.add('d-none');
        if (container) container.classList.remove('d-none');
        
        // Format the timeline results
        if (contentElement) {
            contentElement.innerHTML = formatTimelineResults(data);
        }
    })
    .catch(error => {
        console.error('Error analyzing timeline:', error);
        if (contentElement) {
            contentElement.innerHTML = '<div class="alert alert-danger">Failed to analyze timeline. Please try again.</div>';
        }
        if (placeholder) placeholder.classList.add('d-none');
        if (container) container.classList.remove('d-none');
    })
    .finally(() => {
        // Hide loading state
        btn.disabled = false;
        if (spinner) spinner.classList.add('d-none');
    });
}

function formatCriticalPathResults(data) {
    let html = '<div class="critical-path-results">';
    
    // Analysis summary
    if (data.analysis) {
        html += '<div class="mb-3">';
        html += '<h6 class="text-success"><i class="fas fa-route me-2"></i>Critical Path Analysis</h6>';
        html += '<p>' + escapeHtml(data.analysis) + '</p>';
        html += '</div>';
    }
    
    // Critical tasks
    if (data.critical_tasks && data.critical_tasks.length > 0) {
        html += '<div class="mb-3">';
        html += '<h6 class="text-danger"><i class="fas fa-exclamation-circle me-2"></i>Critical Tasks</h6>';
        html += '<ul class="list-unstyled">';
        data.critical_tasks.forEach(task => {
            const taskText = typeof task === 'string' ? task : task.title || task.name || JSON.stringify(task);
            html += '<li class="mb-2"><i class="fas fa-arrow-right text-danger me-2"></i>' + escapeHtml(taskText) + '</li>';
        });
        html += '</ul>';
        html += '</div>';
    }
    
    // Recommendations
    if (data.recommendations && data.recommendations.length > 0) {
        html += '<div class="mb-3">';
        html += '<h6 class="text-info"><i class="fas fa-lightbulb me-2"></i>Recommendations</h6>';
        html += '<ul class="list-unstyled">';
        data.recommendations.forEach(rec => {
            const recText = typeof rec === 'string' ? rec : rec.description || rec.title || JSON.stringify(rec);
            html += '<li class="mb-2"><i class="fas fa-check-circle text-info me-2"></i>' + escapeHtml(recText) + '</li>';
        });
        html += '</ul>';
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

function formatTimelineResults(data) {
    let html = '<div class="timeline-results">';
    
    // Timeline insights
    if (data.insights) {
        html += '<div class="mb-3">';
        html += '<h6 class="text-primary"><i class="fas fa-clock me-2"></i>Timeline Insights</h6>';
        html += '<p>' + escapeHtml(data.insights) + '</p>';
        html += '</div>';
    }
    
    // Milestones
    if (data.milestones && data.milestones.length > 0) {
        html += '<div class="mb-3">';
        html += '<h6 class="text-success"><i class="fas fa-flag me-2"></i>Key Milestones</h6>';
        html += '<ul class="list-unstyled">';
        data.milestones.forEach(milestone => {
            const milestoneText = typeof milestone === 'string' ? milestone : milestone.name || milestone.title || JSON.stringify(milestone);
            html += '<li class="mb-2"><i class="fas fa-flag-checkered text-success me-2"></i>' + escapeHtml(milestoneText) + '</li>';
        });
        html += '</ul>';
        html += '</div>';
    }
    
    // Risks
    if (data.risks && data.risks.length > 0) {
        html += '<div class="mb-3">';
        html += '<h6 class="text-warning"><i class="fas fa-exclamation-triangle me-2"></i>Timeline Risks</h6>';
        html += '<ul class="list-unstyled">';
        data.risks.forEach(risk => {
            const riskText = typeof risk === 'string' ? risk : risk.description || risk.title || JSON.stringify(risk);
            html += '<li class="mb-2"><i class="fas fa-exclamation-triangle text-warning me-2"></i>' + escapeHtml(riskText) + '</li>';
        });
        html += '</ul>';
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

// Utility function to get CSRF token
function getCSRFToken() {
    return window.CSRF_TOKEN || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

// Utility function to escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
