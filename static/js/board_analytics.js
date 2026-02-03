/**
 * Board Analytics JavaScript
 * Handles all charts, modals, and interactive features for the analytics page
 */

// Global variables
let chartsInitialized = false;
let priorityChartInstance = null;

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
    
    // Listen for accessibility mode changes to update chart colors
    window.addEventListener('accessibilityModeChanged', function(e) {
        console.log('Accessibility mode changed:', e.detail.colorblindMode);
        updateChartsForAccessibility();
    });
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
    
    // Use accessibility-aware color palette
    const priorityColors = window.PrizmAccessibility ? 
        window.PrizmAccessibility.getPriorityColors() : {
            'Urgent': 'rgba(220, 53, 69, 0.8)',  // Red
            'High': 'rgba(255, 193, 7, 0.8)',    // Orange/Yellow
            'Medium': 'rgba(54, 162, 235, 0.8)', // Blue
            'Low': 'rgba(40, 167, 69, 0.8)'      // Green
        };
    
    // Store chart instance for later updates
    priorityChartInstance = new Chart(priorityCtx, {
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

/**
 * Update chart colors when accessibility mode changes
 */
function updateChartsForAccessibility() {
    if (priorityChartInstance) {
        const priorityDataElement = document.getElementById('tasks-by-priority-data');
        if (priorityDataElement) {
            try {
                const priorityData = JSON.parse(priorityDataElement.textContent);
                const priorityColors = window.PrizmAccessibility ? 
                    window.PrizmAccessibility.getPriorityColors() : {
                        'Urgent': 'rgba(220, 53, 69, 0.8)',
                        'High': 'rgba(255, 193, 7, 0.8)',
                        'Medium': 'rgba(54, 162, 235, 0.8)',
                        'Low': 'rgba(40, 167, 69, 0.8)'
                    };
                
                priorityChartInstance.data.datasets[0].backgroundColor = 
                    priorityData.map(item => priorityColors[item.priority] || 'rgba(108, 117, 125, 0.8)');
                priorityChartInstance.update();
                console.log('Priority chart colors updated for accessibility mode');
            } catch (e) {
                console.error('Failed to update priority chart:', e);
            }
        }
    }
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
    
    // Check if array is empty or all counts are zero
    const totalCount = leanData.reduce((sum, item) => sum + item.count, 0);
    
    if (leanData.length === 0 || totalCount === 0) {
        console.warn('No lean data available or all counts are zero');
        // Display a message in the chart container
        const chartContainer = leanCtx.parentElement;
        chartContainer.innerHTML = `
            <div class="text-center py-5">
                <i class="fas fa-chart-pie fa-3x text-muted mb-3"></i>
                <p class="text-muted">No Lean Six Sigma data available</p>
                <small class="text-muted">Tasks need to be categorized as Value-Added, Necessary NVA, or Waste/Eliminate</small>
            </div>
        `;
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
                    cornerRadius: 8,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            const value = context.raw;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = Math.round((value / total) * 100);
                            return `${context.label}: ${value} tasks (${percentage}%)`;
                        },
                        labelColor: function(context) {
                            // Ensure tooltip color box matches the actual segment
                            return {
                                borderColor: context.dataset.backgroundColor[context.dataIndex],
                                backgroundColor: context.dataset.backgroundColor[context.dataIndex],
                                borderWidth: 2,
                                borderRadius: 2
                            };
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
                intersect: true,
                mode: 'point'
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
    .then(response => {
        // Handle different status codes
        if (response.status === 429) {
            // Quota exceeded
            return response.json().then(data => {
                throw new Error(data.error || 'API quota exceeded. Please wait and try again.');
            });
        }
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Failed to generate AI summary');
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Check if summary is present and valid
        if (!data.summary) {
            throw new Error('No summary data received from AI service');
        }
        
        // Debug: log what we received
        console.log('AI Summary response type:', typeof data.summary);
        console.log('AI Summary data:', data.summary);
        
        // Hide placeholder and show content
        placeholder.classList.add('d-none');
        container.classList.remove('d-none');
        
        // Handle both structured and simple string responses
        let formattedSummary;
        let summaryData = data.summary;
        
        // If summary is a string that looks like JSON, try to parse it
        if (typeof summaryData === 'string') {
            const trimmed = summaryData.trim();
            if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
                try {
                    summaryData = JSON.parse(summaryData);
                    console.log('Parsed JSON string into object:', summaryData);
                } catch (e) {
                    console.log('String looks like JSON but failed to parse:', e);
                    // Keep as string
                }
            }
        }
        
        // Now format based on the actual type
        if (typeof summaryData === 'string') {
            // Plain string summary
            formattedSummary = formatAISummary(summaryData);
        } else if (summaryData !== null && typeof summaryData === 'object') {
            // Structured JSON with explainability
            formattedSummary = formatStructuredAISummary(summaryData);
        } else {
            throw new Error('Invalid summary format received');
        }
        
        textElement.innerHTML = formattedSummary;
        
        // Show the download PDF button
        const downloadBtn = document.getElementById('download-pdf-summary');
        if (downloadBtn) {
            downloadBtn.classList.remove('d-none');
        }
    })
    .catch(error => {
        console.error('Error generating AI summary:', error);
        const errorMessage = error.message || 'Failed to generate AI summary. Please try again.';
        textElement.innerHTML = `<div class="alert alert-warning">
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>Unable to generate AI summary</strong><br>
            ${errorMessage}
        </div>`;
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
    // Handle null or undefined
    if (summary === null || summary === undefined) {
        return '<p class="text-muted">No summary available.</p>';
    }
    
    // Handle objects - try to extract a string or format as structured
    if (typeof summary === 'object') {
        // Check for common summary properties
        if (summary.executive_summary) {
            summary = summary.executive_summary;
        } else if (summary.summary) {
            summary = summary.summary;
        } else if (summary.markdown_summary) {
            summary = summary.markdown_summary;
        } else {
            // It's a structured object, use the structured formatter
            console.log('formatAISummary received object, delegating to formatStructuredAISummary');
            return formatStructuredAISummary(summary);
        }
    }
    
    // This function handles plain string summaries (legacy format)
    if (typeof summary !== 'string') {
        console.error('formatAISummary expects a string, got:', typeof summary);
        return '<p>Error formatting summary</p>';
    }
    
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

function formatStructuredAISummary(summary) {
    // Defensive check for null/undefined summary
    if (!summary || typeof summary !== 'object') {
        console.error('formatStructuredAISummary received invalid summary:', summary);
        return '<div class="alert alert-warning">Unable to format AI summary. Please try again.</div>';
    }
    
    // Check if the summary object might be a wrapper with a nested JSON string
    // This handles cases where the AI returns the JSON as a string inside a field
    if (summary.executive_summary && typeof summary.executive_summary === 'string') {
        const execSummary = summary.executive_summary.trim();
        // Check if executive_summary itself contains JSON (indicating double-encoding issue)
        if (execSummary.startsWith('{') && execSummary.includes('"executive_summary"')) {
            try {
                const parsed = JSON.parse(execSummary);
                if (parsed && typeof parsed === 'object') {
                    console.log('Detected nested JSON in executive_summary, re-parsing...');
                    summary = parsed;
                }
            } catch (e) {
                console.log('Failed to parse nested JSON in executive_summary');
            }
        }
    }
    
    // Also check if there's a nested 'summary' field that needs extraction
    if (summary.summary && typeof summary.summary === 'object' && !summary.executive_summary) {
        console.log('Extracting nested summary object');
        summary = summary.summary;
    }
    
    // This function handles structured JSON summaries with explainability
    let html = '<div class="structured-ai-summary">';
    
    // Executive Summary
    if (summary.executive_summary) {
        html += '<div class="mb-4">';
        html += '<h5 class="text-primary"><i class="fas fa-chart-line me-2"></i>Executive Summary</h5>';
        html += '<p class="lead">' + escapeHtml(summary.executive_summary) + '</p>';
        
        // Confidence and Quality Indicators
        if (summary.confidence_score || summary.analysis_quality) {
            html += '<div class="d-flex gap-2 mb-3">';
            if (summary.confidence_score) {
                const confidence = Math.round(summary.confidence_score * 100);
                const confColor = confidence >= 80 ? 'success' : confidence >= 60 ? 'warning' : 'secondary';
                html += '<span class="badge bg-' + confColor + '">Confidence: ' + confidence + '%</span>';
            }
            if (summary.analysis_quality) {
                html += '<span class="badge bg-info">Data: ' + summary.analysis_quality.data_completeness + '</span>';
            }
            html += '</div>';
        }
        html += '</div>';
    }
    
    // Health Assessment
    if (summary.health_assessment) {
        const health = summary.health_assessment;
        const healthColors = {healthy: 'success', at_risk: 'warning', critical: 'danger'};
        const healthColor = healthColors[health.overall_score] || 'secondary';
        
        html += '<div class="mb-4">';
        html += '<h6 class="text-' + healthColor + '"><i class="fas fa-heartbeat me-2"></i>Project Health</h6>';
        html += '<span class="badge bg-' + healthColor + ' mb-2">' + escapeHtml(health.overall_score || 'Unknown').toUpperCase() + '</span>';
        if (health.score_reasoning) {
            html += '<p class="text-muted small">' + escapeHtml(health.score_reasoning) + '</p>';
        }
        
        // Render health indicators if present
        if (health.health_indicators && Array.isArray(health.health_indicators) && health.health_indicators.length > 0) {
            html += '<div class="mt-3">';
            html += '<p class="mb-2"><strong>Health Indicators:</strong></p>';
            html += '<div class="table-responsive"><table class="table table-sm table-bordered">';
            html += '<thead class="table-light"><tr><th>Indicator</th><th>Status</th><th>Value</th><th>Benchmark</th><th>Impact</th></tr></thead><tbody>';
            health.health_indicators.forEach(indicator => {
                if (!indicator) return;
                const statusColors = {positive: 'success', negative: 'danger', neutral: 'secondary'};
                const statusColor = statusColors[indicator.status] || 'secondary';
                html += '<tr>';
                html += '<td>' + escapeHtml(indicator.indicator || '') + '</td>';
                html += '<td><span class="badge bg-' + statusColor + '">' + escapeHtml(indicator.status || 'N/A') + '</span></td>';
                html += '<td>' + escapeHtml(indicator.value || 'N/A') + '</td>';
                html += '<td>' + escapeHtml(indicator.benchmark || 'N/A') + '</td>';
                html += '<td class="small">' + escapeHtml(indicator.impact_on_score || '') + '</td>';
                html += '</tr>';
            });
            html += '</tbody></table></div>';
            html += '</div>';
        }
        html += '</div>';
    }
    
    // Key Insights
    if (summary.key_insights && Array.isArray(summary.key_insights) && summary.key_insights.length > 0) {
        html += '<div class="mb-4">';
        html += '<h6 class="text-info"><i class="fas fa-lightbulb me-2"></i>Key Insights</h6>';
        summary.key_insights.forEach(insight => {
            if (!insight) return; // Skip null/undefined items
            const confBadge = insight.confidence ? '<span class="badge bg-secondary me-2">' + insight.confidence + '</span>' : '';
            html += '<div class="card mb-2 border-left-info">';
            html += '<div class="card-body py-2">';
            html += '<p class="mb-1">' + confBadge + escapeHtml(insight.insight || 'Insight') + '</p>';
            if (insight.evidence) {
                html += '<small class="text-muted"><strong>Evidence:</strong> ' + escapeHtml(String(insight.evidence)) + '</small>';
            }
            html += '</div></div>';
        });
        html += '</div>';
    }
    
    // Areas of Concern
    if (summary.areas_of_concern && Array.isArray(summary.areas_of_concern) && summary.areas_of_concern.length > 0) {
        html += '<div class="mb-4">';
        html += '<h6 class="text-danger"><i class="fas fa-exclamation-triangle me-2"></i>Areas of Concern</h6>';
        summary.areas_of_concern.forEach(concern => {
            if (!concern) return; // Skip null/undefined items
            const severityColors = {critical: 'danger', high: 'warning', medium: 'info', low: 'secondary'};
            const severityColor = severityColors[concern.severity] || 'secondary';
            html += '<div class="alert alert-' + severityColor + ' py-2 mb-2">';
            html += '<strong>' + escapeHtml(concern.concern || 'Concern') + '</strong>';
            if (concern.recommended_action) {
                html += '<p class="mb-0 mt-1 small"><i class="fas fa-arrow-right me-1"></i>' + escapeHtml(String(concern.recommended_action)) + '</p>';
            }
            html += '</div>';
        });
        html += '</div>';
    }
    
    // Process Improvement Recommendations
    if (summary.process_improvement_recommendations && Array.isArray(summary.process_improvement_recommendations) && summary.process_improvement_recommendations.length > 0) {
        html += '<div class="mb-4">';
        html += '<h6 class="text-success"><i class="fas fa-rocket me-2"></i>Recommendations</h6>';
        summary.process_improvement_recommendations.forEach((rec, idx) => {
            if (!rec) return; // Skip null/undefined items
            html += '<div class="card mb-2">';
            html += '<div class="card-body py-2">';
            html += '<div class="d-flex justify-content-between align-items-start">';
            html += '<div><strong>' + (idx + 1) + '. ' + escapeHtml(rec.recommendation || 'Recommendation') + '</strong></div>';
            if (rec.implementation_effort) {
                const effortColor = rec.implementation_effort === 'low' ? 'success' : rec.implementation_effort === 'medium' ? 'warning' : 'danger';
                html += '<span class="badge bg-' + effortColor + '">' + String(rec.implementation_effort) + ' effort</span>';
            }
            html += '</div>';
            if (rec.expected_impact) {
                html += '<p class="mb-0 mt-1 small text-muted">' + escapeHtml(String(rec.expected_impact)) + '</p>';
            }
            html += '</div></div>';
        });
        html += '</div>';
    }
    
    // Lean Analysis
    if (summary.lean_analysis) {
        const lean = summary.lean_analysis;
        html += '<div class="mb-4">';
        html += '<h6 class="text-warning"><i class="fas fa-cogs me-2"></i>Lean Six Sigma Analysis</h6>';
        if (lean.value_stream_efficiency) {
            html += '<p><strong>Value Stream Efficiency:</strong> <span class="badge bg-info">' + String(lean.value_stream_efficiency).toUpperCase() + '</span></p>';
        }
        if (lean.waste_identification && Array.isArray(lean.waste_identification) && lean.waste_identification.length > 0) {
            html += '<p class="mb-1"><strong>Waste Identified:</strong></p><ul class="small">';
            lean.waste_identification.forEach(waste => {
                if (!waste) return; // Skip null/undefined items
                html += '<li>' + escapeHtml(waste.waste_type || 'Waste') + ' (' + (waste.tasks_affected || 0) + ' tasks)</li>';
            });
            html += '</ul>';
        }
        html += '</div>';
    }
    
    // Action Items
    if (summary.action_items && Array.isArray(summary.action_items) && summary.action_items.length > 0) {
        html += '<div class="mb-4">';
        html += '<h6 class="text-primary"><i class="fas fa-tasks me-2"></i>Immediate Action Items</h6>';
        html += '<ol class="ps-3">';
        summary.action_items.forEach(item => {
            if (!item) return; // Skip null/undefined items
            const urgencyColors = {immediate: 'danger', this_week: 'warning', this_month: 'info'};
            const urgencyColor = urgencyColors[item.urgency] || 'secondary';
            const urgencyText = String(item.urgency || 'planned').replace('_', ' ');
            html += '<li class="mb-2">';
            html += escapeHtml(item.action || 'Action item');
            html += ' <span class="badge bg-' + urgencyColor + ' ms-2">' + urgencyText + '</span>';
            html += '</li>';
        });
        html += '</ol></div>';
    }
    
    html += '</div>';
    return html;
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
            // Try to extract common property names for display
            text = text.name || text.title || text.value || text.description || text.insight || text.recommendation || text.concern || text.action || JSON.stringify(text);
        }
    }
    
    // Convert to string if not already
    text = String(text);
    
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
