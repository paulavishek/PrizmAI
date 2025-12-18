/**
 * Board Analytics JavaScript
 * Handles all charts, modals, and interactive features for the analytics page
 */

// Global variables
let chartsInitialized = false;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded - Initializing Analytics');
    console.log('Chart.js available:', typeof Chart !== 'undefined');
    
    // Test if we can find the chart canvases
    console.log('Column chart canvas:', document.getElementById('columnChart'));
    console.log('Priority chart canvas:', document.getElementById('priorityChart'));
    console.log('User chart canvas:', document.getElementById('userChart'));
    console.log('Lean chart canvas:', document.getElementById('leanChart'));
    
    // Test if we can find the data scripts
    console.log('Column data script:', document.getElementById('tasks-by-column-data'));
    console.log('Priority data script:', document.getElementById('tasks-by-priority-data'));
    console.log('User data script:', document.getElementById('tasks-by-user-data'));
    console.log('Lean data script:', document.getElementById('tasks-by-lean-data'));
    
    initializeAnalytics();
});

function initializeAnalytics() {
    console.log('Initializing Analytics...');
    initializeCharts();
    initializeModals();
    setupProgressBars();
    setupMetricCards();
    initializeAIFeatures();
    console.log('Analytics initialization complete');
}

function initializeCharts() {
    console.log('Initializing Charts...');
    if (chartsInitialized) {
        console.log('Charts already initialized, skipping');
        return;
    }
    
    // Chart.js configurations
    Chart.defaults.font.family = 'Nunito';
    Chart.defaults.color = '#858796';
    
    // Initialize all charts
    console.log('Starting chart initialization...');
    initializeColumnChart();
    initializePriorityChart();
    initializeUserChart();
    initializeLeanChart();
    
    chartsInitialized = true;
    console.log('All charts initialized successfully');
}

function initializeColumnChart() {
    const columnCtx = document.getElementById('columnChart');
    if (!columnCtx) {
        console.warn('Column chart canvas not found');
        return;
    }
    
    const columnDataElement = document.getElementById('tasks-by-column-data');
    if (!columnDataElement) {
        console.warn('Column data element not found');
        return;
    }
    
    let columnData;
    try {
        columnData = JSON.parse(columnDataElement.textContent);
    } catch (e) {
        console.error('Failed to parse column data:', e);
        return;
    }
    
    if (columnData.length === 0) {
        console.warn('No column data available');
        return;
    }
    
    console.log('Column data:', columnData);
    
    new Chart(columnCtx, {
        type: 'bar',
        data: {
            labels: columnData.map(item => item.name),
            datasets: [{
                label: 'Tasks',
                data: columnData.map(item => item.count),
                backgroundColor: 'rgba(54, 162, 235, 0.8)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

function initializePriorityChart() {
    const priorityCtx = document.getElementById('priorityChart');
    if (!priorityCtx) {
        console.warn('Priority chart canvas not found');
        return;
    }
    
    const priorityDataElement = document.getElementById('tasks-by-priority-data');
    if (!priorityDataElement) {
        console.warn('Priority data element not found');
        return;
    }
    
    let priorityData;
    try {
        priorityData = JSON.parse(priorityDataElement.textContent);
    } catch (e) {
        console.error('Failed to parse priority data:', e);
        return;
    }
    
    if (priorityData.length === 0) {
        console.warn('No priority data available');
        return;
    }
    
    console.log('Priority data:', priorityData);
      const priorityColors = {
        'Urgent': 'rgba(220, 53, 69, 0.8)',  // Red
        'High': 'rgba(255, 193, 7, 0.8)',    // Orange/Yellow
        'Medium': 'rgba(54, 162, 235, 0.8)', // Blue
        'Low': 'rgba(40, 167, 69, 0.8)'      // Green
    };
    
    new Chart(priorityCtx, {
        type: 'doughnut',
        data: {
            labels: priorityData.map(item => item.priority),
            datasets: [{
                data: priorityData.map(item => item.count),
                backgroundColor: priorityData.map(item => priorityColors[item.priority] || 'rgba(108, 117, 125, 0.8)'),
                borderColor: '#ffffff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function initializeUserChart() {
    const userCtx = document.getElementById('userChart');
    if (!userCtx) {
        console.warn('User chart canvas not found');
        return;
    }
    
    const userDataElement = document.getElementById('tasks-by-user-data');
    if (!userDataElement) {
        console.warn('User data element not found');
        return;
    }
    
    let userData;
    try {
        userData = JSON.parse(userDataElement.textContent);
    } catch (e) {
        console.error('Failed to parse user data:', e);
        return;
    }
    
    if (userData.length === 0) {
        console.warn('No user data available');
        return;
    }
    
    console.log('User data:', userData);
    
    new Chart(userCtx, {
        type: 'bar',
        data: {
            labels: userData.map(item => item.username),
            datasets: [{
                label: 'Assigned Tasks',
                data: userData.map(item => item.count),
                backgroundColor: 'rgba(75, 192, 192, 0.8)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

function initializeLeanChart() {
    const leanCtx = document.getElementById('leanChart');
    if (!leanCtx) {
        console.warn('Lean chart canvas not found');
        return;
    }
    
    const leanDataElement = document.getElementById('tasks-by-lean-data');
    if (!leanDataElement) {
        console.warn('Lean data element not found');
        return;
    }
    
    let leanData;
    try {
        leanData = JSON.parse(leanDataElement.textContent);
    } catch (e) {
        console.error('Failed to parse lean data:', e);
        return;
    }
    
    if (leanData.length === 0) {
        console.warn('No lean data available');
        return;
    }
    
    console.log('Lean data:', leanData);
    
    new Chart(leanCtx, {
        type: 'doughnut',
        data: {
            labels: leanData.map(item => item.name),
            datasets: [{
                data: leanData.map(item => item.count),
                backgroundColor: leanData.map(item => item.color),
                borderColor: '#ffffff',
                borderWidth: 3,
                hoverBorderWidth: 5,
                cutout: '65%'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true,
                        pointStyle: 'circle',
                        font: {
                            size: 12,
                            weight: '500'
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#ffffff',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            const value = context.raw;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = Math.round((value / total) * 100);
                            return `${context.label}: ${value} tasks (${percentage}%)`;
                        }
                    }
                }
            },
            elements: {
                arc: {
                    borderRadius: 8
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            },
            animation: {
                animateRotate: true,
                animateScale: true,
                duration: 1000,
                easing: 'easeOutCubic'
            }
        }
    });
}

function setupProgressBars() {
    // Set width for the overall progress bar
    const overallProgressBar = document.getElementById('overall-progress-bar');
    if (overallProgressBar) {
        const progress = overallProgressBar.getAttribute('data-progress');
        if (progress) {
            overallProgressBar.style.width = progress + '%';
        }
    }

    // Find all progress bars with the progress-dynamic class
    const progressBars = document.querySelectorAll('.progress-dynamic');
    progressBars.forEach(bar => {
        const width = bar.getAttribute('data-width');
        if (width) {
            bar.style.width = width + '%';
        }
    });

    // Apply task progress widths for modal bars using data-progress
    document.querySelectorAll('.task-progress-bar[data-progress]').forEach(bar => {
        const progressValue = bar.getAttribute('data-progress');
        if (progressValue) {
            bar.style.width = progressValue + '%';
        }
    });
}

function initializeModals() {
    // Fix for modals not closing properly
    document.querySelectorAll('.modal button[data-bs-dismiss="modal"]').forEach(btn => {
        btn.addEventListener('click', function() {
            // Get the modal ID from the button's parent modal
            const modal = this.closest('.modal');
            // Use Bootstrap's modal API to hide it properly
            const modalInstance = bootstrap.Modal.getInstance(modal);
            if (modalInstance) {
                modalInstance.hide();
            }
            
            // Also remove any orphaned backdrops
            document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
                backdrop.remove();
            });
            
            // Remove modal-open class from body if no modals are open
            if (!document.querySelector('.modal.show')) {
                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
                document.body.style.paddingRight = '';
            }
        });
    });
}

function setupMetricCards() {
    // Initialize metric cards to open modals when clicked
    const metricCards = document.querySelectorAll('.metrics-card');
    metricCards.forEach(card => {
        card.addEventListener('click', function() {
            const targetModal = this.getAttribute('data-bs-target');
            const modalElement = document.querySelector(targetModal);
            if (modalElement) {
                const modalInstance = new bootstrap.Modal(modalElement);
                modalInstance.show();
            }
        });
    });
}

// AI Features Functions
function initializeAIFeatures() {
    console.log('Initializing AI Features...');
    
    // AI Summary Generation
    const generateAISummaryBtn = document.getElementById('generate-ai-summary');
    if (generateAISummaryBtn) {
        generateAISummaryBtn.addEventListener('click', function() {
            const boardId = this.getAttribute('data-board-id');
            generateAISummary(boardId);
        });
    }
    
    // PDF Download
    const downloadPDFBtn = document.getElementById('download-pdf-summary');
    if (downloadPDFBtn) {
        downloadPDFBtn.addEventListener('click', function() {
            const boardId = this.getAttribute('data-board-id');
            downloadAnalyticsPDF(boardId);
        });
    }
    
    // PDF Download
    const downloadPDFBtn = document.getElementById('download-pdf-summary');
    if (downloadPDFBtn) {
        downloadPDFBtn.addEventListener('click', function() {
            const boardId = this.getAttribute('data-board-id');
            downloadAnalyticsPDF(boardId);
        });
    }
    
    // Workflow Optimization Analysis
    const analyzeWorkflowBtn = document.getElementById('analyze-workflow-btn');
    if (analyzeWorkflowBtn) {
        analyzeWorkflowBtn.addEventListener('click', function() {
            const boardId = this.getAttribute('data-board-id');
            analyzeWorkflow(boardId);
        });
    }
    
    // Note: Critical Path and Timeline analysis are now handled by ai_timeline.js
}

function generateAISummary(boardId) {
    const btn = document.getElementById('generate-ai-summary');
    const spinner = document.getElementById('ai-summary-spinner');
    const container = document.getElementById('ai-summary-container');
    const placeholder = document.getElementById('ai-summary-placeholder');
    const textElement = document.getElementById('ai-summary-text');
    
    // Show loading state
    btn.disabled = true;
    spinner.classList.remove('d-none');
    
    fetch(`/api/summarize-board-analytics/${boardId}/`, {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Hide placeholder and show content
        placeholder.classList.add('d-none');
        container.classList.remove('d-none');
        
        // Convert markdown-like text to HTML for better display
        const formattedSummary = formatAISummary(data.summary);
        textElement.innerHTML = formattedSummary;
        
        // Show the download PDF button
        const downloadBtn = document.getElementById('download-pdf-summary');
        if (downloadBtn) {
            downloadBtn.classList.remove('d-none');
        }
    })
    .catch(error => {
        console.error('Error generating AI summary:', error);
        textElement.innerHTML = '<div class="alert alert-danger">Failed to generate AI summary. Please try again.</div>';
        placeholder.classList.add('d-none');
        container.classList.remove('d-none');
    })
    .finally(() => {
        // Hide loading state
        btn.disabled = false;
        spinner.classList.add('d-none');
    });
}

function downloadAnalyticsPDF(boardId) {
    const btn = document.getElementById('download-pdf-summary');
    const spinner = document.getElementById('pdf-download-spinner');
    
    // Show loading state
    btn.disabled = true;
    spinner.classList.remove('d-none');
    
    // Create a temporary link and trigger download
    const downloadUrl = `/api/download-analytics-pdf/${boardId}/`;
    
    fetch(downloadUrl, {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCSRFToken(),
        },
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to generate PDF');
        }
        return response.blob();
    })
    .then(blob => {
        // Create a temporary URL for the blob
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        
        // Extract filename from Content-Disposition header or use default
        const filename = `Analytics_Summary_${new Date().toISOString().slice(0, 10)}.pdf`;
        a.download = filename;
        
        document.body.appendChild(a);
        a.click();
        
        // Clean up
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        // Show success message
        console.log('PDF downloaded successfully');
    })
    .catch(error => {
        console.error('Error downloading PDF:', error);
        alert('Failed to download PDF. Please try again.');
    })
    .finally(() => {
        // Hide loading state
        btn.disabled = false;
        spinner.classList.add('d-none');
    });
}

function analyzeWorkflow(boardId) {
    const btn = document.getElementById('analyze-workflow-btn');
    const spinner = document.getElementById('workflow-ai-spinner');
    const container = document.getElementById('workflow-optimization-container');
    const placeholder = document.getElementById('workflow-optimization-placeholder');
    const contentElement = document.getElementById('workflow-optimization-content');
    
    // Show loading state
    btn.disabled = true;
    spinner.classList.remove('d-none');
    
    fetch('/api/analyze-workflow-optimization/', {
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
        placeholder.classList.add('d-none');
        container.classList.remove('d-none');
        
        // Format the workflow optimization results
        const formattedContent = formatWorkflowOptimization(data);
        contentElement.innerHTML = formattedContent;
        
    })
    .catch(error => {
        console.error('Error analyzing workflow:', error);
        contentElement.innerHTML = '<div class="alert alert-danger">Failed to analyze workflow. Please try again.</div>';
        placeholder.classList.add('d-none');
        container.classList.remove('d-none');
    })
    .finally(() => {
        // Hide loading state
        btn.disabled = false;
        spinner.classList.add('d-none');
    });
}

// Helper function to format timeline recommendations (kept for formatCriticalPathAnalysis compatibility)
function formatTimelineRecommendations(recommendations) {
    let html = '<div class="timeline-recommendations">';
    
    recommendations.forEach(rec => {
        if (typeof rec === 'object') {
            const priorityColor = rec.priority <= 1 ? 'danger' : rec.priority <= 2 ? 'warning' : 'info';
            const effortBadge = rec.implementation_effort ? 
                '<span class="badge bg-' + (rec.implementation_effort === 'high' ? 'danger' : 
                                             rec.implementation_effort === 'medium' ? 'warning' : 'success') + 
                ' me-2">' + rec.implementation_effort + ' effort</span>' : '';
            
            html += '<div class="card mb-2 border-left-' + priorityColor + '">';
            html += '<div class="card-body py-2">';
            html += '<h6 class="card-title text-' + priorityColor + ' mb-1">';
            if (rec.priority) {
                html += '<span class="badge bg-' + priorityColor + ' me-2">' + rec.priority + '</span>';
            }
            html += escapeHtml(rec.title || 'Recommendation');
            html += '</h6>';
            if (rec.description) {
                html += '<p class="card-text text-muted mb-1" style="font-size: 0.875rem;">' + escapeHtml(rec.description) + '</p>';
            }
            if (rec.expected_impact) {
                html += '<p class="card-text mb-1"><small class="text-success"><strong>Impact:</strong> ' + 
                        escapeHtml(rec.expected_impact) + '</small></p>';
            }
            html += '<div class="d-flex">';
            html += effortBadge;
            if (rec.category) {
                html += '<span class="badge bg-light text-dark">' + escapeHtml(rec.category) + '</span>';
            }
            html += '</div>';
            html += '</div></div>';
        } else {
            html += '<div class="mb-2"><i class="fas fa-lightbulb text-warning me-2"></i>' + escapeHtml(rec) + '</div>';
        }
    });
    
    html += '</div>';
    return html;
}

// Formatting helper functions
function formatAISummary(summary) {
    // Convert basic markdown-like formatting to HTML
    let formatted = summary
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/###\s(.*?)$/gm, '<h5>$1</h5>')
        .replace(/##\s(.*?)$/gm, '<h4>$1</h4>')
        .replace(/^-\s(.*?)$/gm, '<li>$1</li>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/^\s*<li>/gm, '<ul><li>')
        .replace(/<\/li>\s*$/gm, '</li></ul>');
    
    // Wrap in paragraphs
    if (!formatted.startsWith('<')) {
        formatted = '<p>' + formatted + '</p>';
    }
    
    return formatted;
}

function formatWorkflowOptimization(data) {
    let html = '<div class="workflow-optimization-results">';
    
    // Workflow Insights (analysis summary)
    if (data.workflow_insights) {
        html += '<div class="mb-4">';
        html += '<h6 class="text-info"><i class="fas fa-chart-line me-2"></i>Workflow Analysis</h6>';
        html += '<p class="text-muted">' + escapeHtml(data.workflow_insights) + '</p>';
        html += '</div>';
    }
    
    // Overall Health Score
    if (data.overall_health_score !== undefined) {
        const healthColor = data.overall_health_score >= 7 ? 'success' : data.overall_health_score >= 4 ? 'warning' : 'danger';
        html += '<div class="mb-4">';
        html += '<h6 class="text-' + healthColor + '"><i class="fas fa-heartbeat me-2"></i>Overall Health Score</h6>';
        html += '<div class="progress mb-2" style="height: 20px;">';
        html += '<div class="progress-bar bg-' + healthColor + '" style="width: ' + (data.overall_health_score * 10) + '%">';
        html += data.overall_health_score + '/10';
        html += '</div></div>';
        html += '</div>';
    }
    
    // Optimization Recommendations (structured format)
    if (data.optimization_recommendations && data.optimization_recommendations.length > 0) {
        html += '<div class="mb-4">';
        html += '<h6 class="text-warning"><i class="fas fa-lightbulb me-2"></i>Optimization Recommendations</h6>';
        data.optimization_recommendations.forEach(rec => {
            const priorityColor = rec.priority <= 2 ? 'danger' : rec.priority <= 3 ? 'warning' : 'info';
            const impactBadge = '<span class="badge bg-' + (rec.impact === 'high' ? 'danger' : rec.impact === 'medium' ? 'warning' : 'secondary') + ' me-1">' + rec.impact + ' impact</span>';
            const effortBadge = '<span class="badge bg-' + (rec.effort === 'high' ? 'danger' : rec.effort === 'medium' ? 'warning' : 'success') + '">' + rec.effort + ' effort</span>';
            
            html += '<div class="card mb-3 border-left-' + priorityColor + '">';
            html += '<div class="card-body">';
            html += '<h6 class="card-title text-' + priorityColor + '">';
            html += '<span class="badge bg-' + priorityColor + ' me-2">' + rec.priority + '</span>';
            html += escapeHtml(rec.title);
            html += '</h6>';
            html += '<p class="card-text text-muted">' + escapeHtml(rec.description) + '</p>';
            html += '<div class="d-flex">';
            html += impactBadge + effortBadge;
            html += '<span class="badge bg-light text-dark ms-2">' + escapeHtml(rec.category) + '</span>';
            html += '</div>';
            html += '</div></div>';
        });
        html += '</div>';
    }
    
    // Quick Wins
    if (data.quick_wins && data.quick_wins.length > 0) {
        html += '<div class="mb-4">';
        html += '<h6 class="text-success"><i class="fas fa-bolt me-2"></i>Quick Wins</h6>';
        html += '<ul class="list-unstyled">';
        data.quick_wins.forEach(win => {
            html += '<li class="mb-2"><i class="fas fa-check-circle text-success me-2"></i>' + escapeHtml(win) + '</li>';
        });
        html += '</ul>';
        html += '</div>';
    }
    
    // Next Steps
    if (data.next_steps && data.next_steps.length > 0) {
        html += '<div class="mb-4">';
        html += '<h6 class="text-primary"><i class="fas fa-route me-2"></i>Next Steps</h6>';
        html += '<ol class="ps-3">';
        data.next_steps.forEach(step => {
            html += '<li class="mb-2 text-muted">' + escapeHtml(step) + '</li>';
        });
        html += '</ol>';
        html += '</div>';
    }
    
    // Bottlenecks (if any)
    if (data.bottlenecks && data.bottlenecks.length > 0) {
        html += '<div class="mb-4">';
        html += '<h6 class="text-danger"><i class="fas fa-exclamation-triangle me-2"></i>Identified Bottlenecks</h6>';
        html += '<ul class="list-unstyled">';
        data.bottlenecks.forEach(bottleneck => {
            // Handle both string and object bottlenecks
            const bottleneckText = typeof bottleneck === 'string' ? bottleneck : bottleneck.description || bottleneck.title || JSON.stringify(bottleneck);
            html += '<li class="mb-2"><i class="fas fa-exclamation-triangle text-danger me-2"></i>' + escapeHtml(bottleneckText) + '</li>';
        });
        html += '</ul>';
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

function formatCriticalPathAnalysis(data) {
    let html = '<div class="critical-path-results">';
    
    // Analysis summary
    if (data.analysis) {
        html += '<div class="mb-3">';
        html += '<h6 class="text-success">Critical Path Analysis</h6>';
        html += '<p>' + escapeHtml(data.analysis) + '</p>';
        html += '</div>';
    }
    
    // Timeline insights (if available)
    if (data.timeline_insights) {
        const insights = data.timeline_insights;
        html += '<div class="mb-4">';
        html += '<h6 class="text-info"><i class="fas fa-chart-line me-2"></i>Timeline Insights</h6>';
        
        // Project duration
        if (insights.project_duration_weeks) {
            html += '<p><strong>Project Duration:</strong> ' + insights.project_duration_weeks + ' weeks</p>';
        }
        
        // Current progress
        if (insights.current_progress_percentage !== undefined) {
            const progressColor = insights.current_progress_percentage >= 75 ? 'success' : 
                                 insights.current_progress_percentage >= 50 ? 'info' :
                                 insights.current_progress_percentage >= 25 ? 'warning' : 'danger';
            html += '<div class="mb-2">';
            html += '<strong>Current Progress:</strong>';
            html += '<div class="progress mt-1" style="height: 20px;">';
            html += '<div class="progress-bar bg-' + progressColor + '" style="width: ' + insights.current_progress_percentage + '%">';
            html += insights.current_progress_percentage + '%';
            html += '</div></div>';
            html += '</div>';
        }
        
        // Schedule health
        if (insights.schedule_health && insights.schedule_health !== 'not_applicable') {
            const healthColor = insights.schedule_health === 'good' ? 'success' : 
                               insights.schedule_health === 'warning' ? 'warning' : 'danger';
            html += '<p><strong>Schedule Health:</strong> <span class="badge bg-' + healthColor + '">' + 
                    insights.schedule_health.replace('_', ' ').toUpperCase() + '</span></p>';
        }
        
        html += '</div>';
    }
    
    // Critical tasks
    if (data.critical_tasks && data.critical_tasks.length > 0) {
        html += '<div class="mb-3">';
        html += '<h6 class="text-success">Critical Tasks</h6>';
        html += '<ul class="list-unstyled">';
        data.critical_tasks.forEach(task => {
            // Handle both string and object tasks
            const taskText = typeof task === 'string' ? task : task.title || task.name || JSON.stringify(task);
            html += '<li class="mb-2"><i class="fas fa-route text-success me-2"></i>' + escapeHtml(taskText) + '</li>';
        });
        html += '</ul>';
        html += '</div>';
    }
    
    // Recommendations (structured format)
    if (data.recommendations && data.recommendations.length > 0) {
        html += '<div class="mb-4">';
        html += '<h6 class="text-info"><i class="fas fa-lightbulb me-2"></i>Recommendations</h6>';
        data.recommendations.forEach(rec => {
            // Handle structured recommendation objects
            if (typeof rec === 'object') {
                const priorityColor = rec.priority <= 1 ? 'danger' : rec.priority <= 2 ? 'warning' : 'info';
                const effortBadge = rec.implementation_effort ? 
                    '<span class="badge bg-' + (rec.implementation_effort === 'high' ? 'danger' : 
                                                 rec.implementation_effort === 'medium' ? 'warning' : 'success') + 
                    ' me-2">' + rec.implementation_effort + ' effort</span>' : '';
                
                html += '<div class="card mb-3 border-left-' + priorityColor + '">';
                html += '<div class="card-body">';
                html += '<h6 class="card-title text-' + priorityColor + '">';
                if (rec.priority) {
                    html += '<span class="badge bg-' + priorityColor + ' me-2">' + rec.priority + '</span>';
                }
                html += escapeHtml(rec.title || 'Recommendation');
                html += '</h6>';
                if (rec.description) {
                    html += '<p class="card-text text-muted">' + escapeHtml(rec.description) + '</p>';
                }
                if (rec.expected_impact) {
                    html += '<p class="card-text"><small class="text-success"><strong>Impact:</strong> ' + 
                            escapeHtml(rec.expected_impact) + '</small></p>';
                }
                html += '<div class="d-flex">';
                html += effortBadge;
                if (rec.category) {
                    html += '<span class="badge bg-light text-dark">' + escapeHtml(rec.category) + '</span>';
                }
                html += '</div>';
                html += '</div></div>';
            } else {
                // Handle simple string recommendations
                html += '<li class="mb-2"><i class="fas fa-lightbulb text-info me-2"></i>' + escapeHtml(rec) + '</li>';
            }
        });
        html += '</div>';
    }
    
    html += '</div>';
    return html;
}

// Utility functions
function getCSRFToken() {
    return window.CSRF_TOKEN || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
