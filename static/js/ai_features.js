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
                    // Handle both object and string responses from AI
                    let descriptionText;
                    if (typeof data.description === 'object' && data.description !== null) {
                        // Use markdown_description if available, fallback to detailed_description or objective
                        descriptionText = data.description.markdown_description || 
                                         data.description.detailed_description ||
                                         data.description.objective ||
                                         '';
                        // If still empty, try to construct from available fields (using plain text, no Markdown)
                        if (!descriptionText && (data.description.objective || data.description.checklist)) {
                            let parts = [];
                            if (data.description.objective) {
                                parts.push('Objective: ' + data.description.objective);
                            }
                            if (data.description.detailed_description) {
                                parts.push('\n\n' + data.description.detailed_description);
                            }
                            if (data.description.checklist && Array.isArray(data.description.checklist)) {
                                parts.push('\n\nChecklist:');
                                data.description.checklist.forEach(item => {
                                    const itemText = typeof item === 'object' ? item.item : item;
                                    parts.push('\n- ' + itemText);
                                });
                            }
                            descriptionText = parts.join('');
                        }
                    } else {
                        descriptionText = data.description;
                    }
                    descriptionTextarea.value = descriptionText;
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
    const closeButton = document.getElementById('close-summary');
    const exportButton = document.getElementById('export-summary-pdf');
    
    // Store summary data globally for export
    let currentSummaryData = null;
    
    // Check if there's a saved summary in sessionStorage
    if (summarizeButton && summaryContainer && summaryText) {
        const taskId = summarizeButton.getAttribute('data-task-id');
        const savedSummary = sessionStorage.getItem(`comment-summary-${taskId}`);
        
        if (savedSummary) {
            try {
                const summaryData = JSON.parse(savedSummary);
                summaryText.innerHTML = summaryData.formatted;
                currentSummaryData = summaryData.raw;
                summaryContainer.classList.remove('d-none');
                if (exportButton) exportButton.classList.remove('d-none');
            } catch (e) {
                console.error('Failed to load saved summary:', e);
            }
        }
        
        // Close button handler
        if (closeButton) {
            closeButton.addEventListener('click', function() {
                summaryContainer.classList.add('d-none');
                if (exportButton) exportButton.classList.add('d-none');
                // Clear from sessionStorage
                sessionStorage.removeItem(`comment-summary-${taskId}`);
                currentSummaryData = null;
            });
        }
        
        // Export PDF button handler
        if (exportButton) {
            exportButton.addEventListener('click', function() {
                exportCommentSummaryPDF(taskId, currentSummaryData);
            });
        }
        
        // Summarize button handler
        summarizeButton.addEventListener('click', function() {
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
                    // Check if summary is an object or string
                    let summaryText_content = '';
                    if (typeof data.summary === 'object' && data.summary.summary) {
                        // If it's an object, extract the summary field and format it
                        summaryText_content = formatSummaryText(data.summary.summary);
                        currentSummaryData = data.summary;
                    } else if (typeof data.summary === 'string') {
                        // If it's already a string, format it
                        summaryText_content = formatSummaryText(data.summary);
                        currentSummaryData = { summary: data.summary };
                    } else {
                        summaryText_content = 'Could not parse summary format.';
                        currentSummaryData = null;
                    }
                    summaryText.innerHTML = summaryText_content;
                    summaryContainer.classList.remove('d-none');
                    
                    // Show export button
                    if (exportButton && currentSummaryData) {
                        exportButton.classList.remove('d-none');
                    }
                    
                    // Save to sessionStorage for persistence
                    sessionStorage.setItem(`comment-summary-${taskId}`, JSON.stringify({
                        formatted: summaryText_content,
                        raw: currentSummaryData
                    }));
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
 * Export comment summary as PDF
 */
function exportCommentSummaryPDF(taskId, summaryData) {
    const exportButton = document.getElementById('export-summary-pdf');
    const spinner = document.getElementById('pdf-export-spinner');
    
    if (!taskId || !summaryData) {
        alert('No summary data available to export.');
        return;
    }
    
    // Show loading state
    if (exportButton) exportButton.disabled = true;
    if (spinner) spinner.classList.remove('d-none');
    
    // Make API call to generate PDF
    fetch(`/api/download-comment-summary-pdf/${taskId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(summaryData)
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
        a.download = `Comment_Summary_Task_${taskId}_${new Date().toISOString().slice(0, 10)}.pdf`;
        
        document.body.appendChild(a);
        a.click();
        
        // Clean up
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        console.log('PDF downloaded successfully');
    })
    .catch(error => {
        console.error('Error downloading PDF:', error);
        alert('Failed to download PDF. Please try again.');
    })
    .finally(() => {
        // Hide loading state
        if (exportButton) exportButton.disabled = false;
        if (spinner) spinner.classList.add('d-none');
    });
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
                // Map the classification text to the radio button value
                const classificationMap = {
                    'Value-Added': 'value_added',
                    'Necessary Non-Value-Added': 'necessary_nva',
                    'Waste/Eliminate': 'waste'
                };
                
                const radioValue = classificationMap[data.classification];
                if (radioValue) {
                    // Select the appropriate radio button
                    const radioButton = document.getElementById(`lss_${radioValue}`);
                    if (radioButton) {
                        radioButton.checked = true;
                    }
                }
                
                // Use stripMarkdown to clean up AI-generated text
                const stripMarkdown = window.AIExplainability?.stripMarkdown || ((text) => text);
                
                let badgeClass = 'success';
                if (data.classification === 'Necessary Non-Value-Added') badgeClass = 'warning';
                else if (data.classification === 'Waste/Eliminate') badgeClass = 'danger';
                
                let suggestionHtml = `
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div>
                            <strong>✨ AI Suggests:</strong> 
                            <span class="badge bg-${badgeClass} fs-6">${data.classification}</span>
                            ${data.confidence_score ? `<span class="badge bg-secondary ms-1">${Math.round(data.confidence_score * 100)}% confident</span>` : ''}
                        </div>
                        <div>
                            <button type="button" class="btn btn-sm btn-success me-1" onclick="acceptLssClassification('${radioValue}')">
                                <i class="fas fa-check"></i> Accept
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-info" onclick="toggleLssExplain()">
                                <i class="bi bi-lightbulb"></i> Why?
                            </button>
                        </div>
                    </div>
                    <p class="mb-2 small">${stripMarkdown(data.justification)}</p>
                    
                    <div id="lss-explainability" class="why-this-section mt-2" style="display: none;">
                        <div class="why-this-content">
                            ${data.confidence_score ? `
                                <div class="mb-2">
                                    <strong class="small text-muted"><i class="bi bi-speedometer2 me-1"></i>CONFIDENCE</strong>
                                    <div class="progress mt-1" style="height: 15px;">
                                        <div class="progress-bar ${data.confidence_score >= 0.75 ? 'bg-success' : data.confidence_score >= 0.5 ? 'bg-warning' : 'bg-danger'}" 
                                             style="width: ${Math.round(data.confidence_score * 100)}%">
                                            ${Math.round(data.confidence_score * 100)}%
                                        </div>
                                    </div>
                                </div>
                            ` : ''}
                            ${data.contributing_factors && data.contributing_factors.length > 0 ? `
                                <div class="mb-2">
                                    <strong class="small text-muted"><i class="bi bi-pie-chart me-1"></i>KEY FACTORS</strong>
                                    <ul class="small mb-0 ps-3 mt-1">
                                        ${data.contributing_factors.map(f => `
                                            <li>${stripMarkdown(f.description || f.factor || f)}
                                                ${f.contribution_percentage ? `<span class="badge bg-secondary ms-1">${f.contribution_percentage}%</span>` : ''}
                                            </li>
                                        `).join('')}
                                    </ul>
                                </div>
                            ` : ''}
                            ${data.lean_waste_type ? `
                                <div class="mb-2">
                                    <strong class="small text-muted"><i class="bi bi-exclamation-triangle me-1"></i>WASTE TYPE</strong>
                                    <p class="small mb-0 mt-1 text-danger">${data.lean_waste_type}</p>
                                </div>
                            ` : ''}
                            ${data.improvement_suggestions && data.improvement_suggestions.length > 0 ? `
                                <div class="mb-2">
                                    <strong class="small text-muted"><i class="bi bi-lightbulb me-1"></i>IMPROVEMENT IDEAS</strong>
                                    <ul class="small mb-0 ps-3 mt-1">
                                        ${data.improvement_suggestions.map(s => `<li>${stripMarkdown(s)}</li>`).join('')}
                                    </ul>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
                
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
                    // Handle both object and string responses from AI
                    let formattedSummary;
                    if (typeof data.summary === 'object' && data.summary !== null) {
                        // Use structured analytics summary formatter
                        formattedSummary = formatStructuredAnalyticsSummary(data.summary);
                    } else {
                        // Fallback to plain text formatting
                        formattedSummary = formatSummaryText(data.summary);
                    }
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
 * Format structured analytics summary into HTML
 */
function formatStructuredAnalyticsSummary(summary) {
    let html = '<div class="ai-analytics-summary-structured">';
    
    // Helper functions
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    function capitalizeFirst(str) {
        if (!str) return '';
        return str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, ' ');
    }
    
    // Executive Summary
    if (summary.executive_summary) {
        html += `<div class="alert alert-info mb-3">
            <h5 class="alert-heading"><i class="fas fa-chart-bar me-2"></i>Executive Summary</h5>
            <p class="mb-0">${escapeHtml(summary.executive_summary)}</p>
        </div>`;
    }
    
    // Confidence Score
    if (summary.confidence_score) {
        const confidencePercent = Math.round(summary.confidence_score * 100);
        const confidenceClass = confidencePercent >= 70 ? 'bg-success' : confidencePercent >= 40 ? 'bg-warning' : 'bg-danger';
        html += `<div class="mb-3">
            <small class="text-muted">Analysis Confidence:</small>
            <div class="progress" style="height: 20px;">
                <div class="progress-bar ${confidenceClass}" role="progressbar" style="width: ${confidencePercent}%">${confidencePercent}%</div>
            </div>
        </div>`;
    }
    
    // Health Assessment
    if (summary.health_assessment) {
        const health = summary.health_assessment;
        const statusClass = health.overall_score === 'healthy' ? 'success' : health.overall_score === 'at_risk' ? 'warning' : 'danger';
        const statusIcon = health.overall_score === 'healthy' ? 'check-circle' : health.overall_score === 'at_risk' ? 'exclamation-triangle' : 'times-circle';
        html += `<div class="card mb-3 border-${statusClass}">
            <div class="card-header bg-${statusClass} text-white">
                <i class="fas fa-${statusIcon} me-2"></i>Health Assessment: ${capitalizeFirst(health.overall_score || 'Unknown')}
            </div>
            <div class="card-body">
                ${health.score_reasoning ? `<p>${escapeHtml(health.score_reasoning)}</p>` : ''}
                ${health.health_indicators && health.health_indicators.length > 0 ? `
                    <div class="mt-2">
                        ${health.health_indicators.map(ind => `
                            <div class="d-flex align-items-center mb-1">
                                <i class="fas fa-${ind.status === 'positive' ? 'check text-success' : ind.status === 'negative' ? 'times text-danger' : 'minus text-secondary'} me-2"></i>
                                <span><strong>${escapeHtml(ind.indicator)}:</strong> ${escapeHtml(ind.value)} ${ind.benchmark ? `(Expected: ${escapeHtml(ind.benchmark)})` : ''}</span>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        </div>`;
    }
    
    // Key Insights
    if (summary.key_insights && summary.key_insights.length > 0) {
        html += `<div class="card mb-3">
            <div class="card-header bg-primary text-white">
                <i class="fas fa-lightbulb me-2"></i>Key Insights
            </div>
            <div class="card-body">
                <div class="list-group list-group-flush">
                    ${summary.key_insights.map(insight => `
                        <div class="list-group-item px-0">
                            <strong>${escapeHtml(insight.insight)}</strong>
                            ${insight.evidence ? `<p class="small text-muted mb-0 mt-1"><em>Evidence:</em> ${escapeHtml(insight.evidence)}</p>` : ''}
                            ${insight.significance ? `<p class="small mb-0"><em>Significance:</em> ${escapeHtml(insight.significance)}</p>` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>`;
    }
    
    // Areas of Concern
    if (summary.areas_of_concern && summary.areas_of_concern.length > 0) {
        html += `<div class="card mb-3 border-warning">
            <div class="card-header bg-warning text-dark">
                <i class="fas fa-exclamation-triangle me-2"></i>Areas of Concern
            </div>
            <div class="card-body">
                ${summary.areas_of_concern.map(concern => `
                    <div class="border-start border-${concern.severity === 'critical' ? 'danger' : concern.severity === 'high' ? 'warning' : 'info'} ps-2 mb-3">
                        <strong>${escapeHtml(concern.concern)}</strong>
                        <span class="badge bg-${concern.severity === 'critical' ? 'danger' : concern.severity === 'high' ? 'warning' : 'info'} ms-2">${capitalizeFirst(concern.severity)}</span>
                        ${concern.root_cause_hypothesis ? `<p class="small text-muted mb-1 mt-1"><em>Likely Cause:</em> ${escapeHtml(concern.root_cause_hypothesis)}</p>` : ''}
                        ${concern.recommended_action ? `<p class="small mb-0"><strong>Action:</strong> ${escapeHtml(concern.recommended_action)}</p>` : ''}
                    </div>
                `).join('')}
            </div>
        </div>`;
    }
    
    // Recommendations
    if (summary.process_improvement_recommendations && summary.process_improvement_recommendations.length > 0) {
        html += `<div class="card mb-3 border-success">
            <div class="card-header bg-success text-white">
                <i class="fas fa-tasks me-2"></i>Recommendations
            </div>
            <div class="card-body">
                <ol class="mb-0">
                    ${summary.process_improvement_recommendations.map(rec => `
                        <li class="mb-2">
                            <strong>${escapeHtml(rec.recommendation)}</strong>
                            ${rec.rationale ? `<p class="small text-muted mb-0">${escapeHtml(rec.rationale)}</p>` : ''}
                            ${rec.expected_impact ? `<p class="small mb-0"><em>Expected Impact:</em> ${escapeHtml(rec.expected_impact)}</p>` : ''}
                        </li>
                    `).join('')}
                </ol>
            </div>
        </div>`;
    }
    
    // Lean Analysis
    if (summary.lean_analysis) {
        const lean = summary.lean_analysis;
        html += `<div class="card mb-3">
            <div class="card-header">
                <i class="fas fa-chart-line me-2"></i>Lean Six Sigma Analysis
            </div>
            <div class="card-body">
                ${lean.value_stream_efficiency ? `<p><strong>Value Stream Efficiency:</strong> <span class="badge bg-${lean.value_stream_efficiency === 'excellent' ? 'success' : lean.value_stream_efficiency === 'good' ? 'info' : lean.value_stream_efficiency === 'fair' ? 'warning' : 'danger'}">${capitalizeFirst(lean.value_stream_efficiency)}</span></p>` : ''}
                ${lean.efficiency_reasoning ? `<p class="text-muted">${escapeHtml(lean.efficiency_reasoning)}</p>` : ''}
                ${lean.waste_identification && lean.waste_identification.length > 0 ? `
                    <p><strong>Waste Identified:</strong></p>
                    <ul>
                        ${lean.waste_identification.map(w => `<li>${escapeHtml(w.waste_type)}: ${escapeHtml(w.elimination_strategy)}</li>`).join('')}
                    </ul>
                ` : ''}
            </div>
        </div>`;
    }
    
    // Team Performance
    if (summary.team_performance) {
        const team = summary.team_performance;
        html += `<div class="card mb-3">
            <div class="card-header">
                <i class="fas fa-users me-2"></i>Team Performance
            </div>
            <div class="card-body">
                ${team.workload_balance ? `<p><strong>Workload Balance:</strong> ${capitalizeFirst(team.workload_balance)}</p>` : ''}
                ${team.balance_analysis ? `<p class="text-muted">${escapeHtml(team.balance_analysis)}</p>` : ''}
                ${team.capacity_concerns && team.capacity_concerns.length > 0 ? `<p class="text-danger"><strong>Capacity Concerns:</strong> ${team.capacity_concerns.map(c => escapeHtml(c)).join(', ')}</p>` : ''}
            </div>
        </div>`;
    }
    
    // Action Items
    if (summary.action_items && summary.action_items.length > 0) {
        html += `<div class="card mb-3 border-primary">
            <div class="card-header bg-primary text-white">
                <i class="fas fa-list-check me-2"></i>Action Items
            </div>
            <div class="card-body">
                <div class="list-group list-group-flush">
                    ${summary.action_items.map((item, idx) => `
                        <div class="list-group-item px-0 d-flex justify-content-between align-items-start">
                            <div>
                                <strong>${idx + 1}. ${escapeHtml(item.action)}</strong>
                                ${item.owner ? `<br><small class="text-muted">Owner: ${escapeHtml(item.owner)}</small>` : ''}
                                ${item.expected_outcome ? `<p class="small mb-0 mt-1">${escapeHtml(item.expected_outcome)}</p>` : ''}
                            </div>
                            ${item.urgency ? `<span class="badge bg-${item.urgency === 'immediate' ? 'danger' : item.urgency === 'this_week' ? 'warning' : 'info'}">${capitalizeFirst(item.urgency)}</span>` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>`;
    }
    
    // Limitations
    if ((summary.assumptions && summary.assumptions.length > 0) || (summary.limitations && summary.limitations.length > 0)) {
        html += `<div class="card mb-3 border-secondary">
            <div class="card-header bg-light">
                <i class="fas fa-info-circle me-2"></i>Analysis Notes
            </div>
            <div class="card-body small text-muted">
                ${summary.assumptions && summary.assumptions.length > 0 ? `<p class="mb-1"><strong>Assumptions:</strong></p><ul class="mb-2">${summary.assumptions.map(a => `<li>${escapeHtml(a)}</li>`).join('')}</ul>` : ''}
                ${summary.limitations && summary.limitations.length > 0 ? `<p class="mb-1"><strong>Limitations:</strong></p><ul class="mb-0">${summary.limitations.map(l => `<li>${escapeHtml(l)}</li>`).join('')}</ul>` : ''}
            </div>
        </div>`;
    }
    
    html += '</div>';
    return html;
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
        return response.json().then(data => {
            if (!response.ok) {
                // Pass error details including assignee_required flag
                const error = new Error(data.error || 'Failed to predict deadline');
                error.assignee_required = data.assignee_required || false;
                error.message = data.error || 'Failed to predict deadline';
                throw error;
            }
            return data;
        });
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
    
    // Use stripMarkdown to clean up AI-generated text
    const stripMarkdown = window.AIExplainability?.stripMarkdown || ((text) => text);
    
    const priorityClass = getPriorityBadgeClass(data.suggested_priority);
    const confidence = ((data.confidence || 0) * 100).toFixed(0);
    
    // Extract reasoning factors
    const reasoning = data.reasoning || {};
    const factors = reasoning.top_factors || data.contributing_factors || [];
    
    let factorsHtml = '';
    if (factors && factors.length > 0) {
        factorsHtml = `
            <div class="mt-2 p-2 bg-light rounded border">
                <div class="d-flex align-items-start">
                    <i class="fas fa-brain text-primary me-2 mt-1"></i>
                    <div class="flex-grow-1">
                        <strong class="small text-primary">Why AI chose this:</strong>
                        <div class="small text-muted mt-1">
        `;
        
        factors.slice(0, 3).forEach(factor => {
            const desc = factor.description || factor.factor || '';
            const importance = factor.importance || factor.contribution_percentage;
            let importanceBadge = '';
            if (importance) {
                const pct = typeof importance === 'number' ? 
                    (importance > 1 ? importance : importance * 100).toFixed(0) : importance;
                importanceBadge = ` <span class="badge bg-secondary" style="font-size: 0.7rem;">${pct}%</span>`;
            }
            factorsHtml += `<div class="mb-1">• ${desc}${importanceBadge}</div>`;
        });
        
        factorsHtml += `
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    let html = `
        <div class="alert alert-${priorityClass === 'danger' ? 'danger' : priorityClass === 'warning' ? 'warning' : 'info'}">
            <h6><i class="fas fa-robot"></i> AI Priority Suggestion</h6>
            <p><strong>Suggested Priority:</strong> <span class="badge badge-${priorityClass}">${data.suggested_priority.toUpperCase()}</span> 
               <span class="badge bg-secondary">${confidence}% confident</span></p>
            <p class="small"><strong>Reasoning:</strong> ${stripMarkdown(reasoning.explanation || data.reasoning)}</p>
            ${factorsHtml}
    `;
    
    if (data.recommendations && data.recommendations.length > 0) {
        html += '<p><strong>Recommendations:</strong></p><ul>';
        data.recommendations.forEach(rec => {
            html += `<li>${rec}</li>`;
        });
        html += '</ul>';
    }
    
    html += `
            <div class="mt-3">
                <button type="button" class="btn btn-sm btn-primary" onclick="applyPrioritySuggestion('${data.suggested_priority}')">
                    <i class="fas fa-check"></i> Apply Suggestion
                </button>
            </div>
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
    
    const assignedToSelect = document.getElementById('id_assigned_to');
    const assigneeHint = document.getElementById('predict-assignee-hint');
    
    // Function to check if assignee is selected and update button state
    function updatePredictButtonState() {
        if (!assignedToSelect) return;
        
        const selectedValue = assignedToSelect.value;
        const hasAssignee = selectedValue && selectedValue !== '';
        
        if (hasAssignee) {
            predictButton.disabled = false;
            predictButton.classList.remove('disabled');
            predictButton.title = 'AI-powered deadline prediction';
            // Hide the helper hint when assignee is selected
            if (assigneeHint) {
                assigneeHint.classList.add('d-none');
            }
        } else {
            predictButton.disabled = true;
            predictButton.classList.add('disabled');
            predictButton.title = 'Please select an assignee first. The AI needs to analyze their historical velocity and workload to predict an accurate deadline.';
            // Show the helper hint when no assignee is selected
            if (assigneeHint) {
                assigneeHint.classList.remove('d-none');
            }
        }
    }
    
    // Update button state on assignee change
    if (assignedToSelect) {
        assignedToSelect.addEventListener('change', updatePredictButtonState);
        // Initial state check
        updatePredictButtonState();
    }
    
    predictButton.addEventListener('click', function() {
        const titleInput = document.getElementById('id_title');
        const descriptionInput = document.getElementById('id_description');
        const prioritySelect = document.getElementById('id_priority');
        const boardId = this.dataset.boardId;
        const taskId = this.dataset.taskId;
        
        if (!titleInput || !titleInput.value.trim()) {
            alert('Please enter a task title first.');
            return;
        }
        
        // Double-check assignee is selected
        if (!assignedToSelect || !assignedToSelect.value || assignedToSelect.value === '') {
            alert('Please select an assignee first. The AI needs to analyze their historical velocity and current workload to make an accurate prediction.');
            return;
        }
        
        // Collect enhanced prediction fields from form
        const complexityScoreInput = document.getElementById('id_complexity_score');
        const workloadImpactSelect = document.getElementById('id_workload_impact');
        const skillMatchScoreInput = document.getElementById('id_skill_match_score');
        const collaborationRequiredCheckbox = document.getElementById('id_collaboration_required');
        const dependenciesSelect = document.getElementById('id_dependencies');
        const riskLevelSelect = document.getElementById('id_risk_level');
        const riskLikelihoodSelect = document.getElementById('id_risk_likelihood');
        const riskImpactSelect = document.getElementById('id_risk_impact');
        
        // Calculate risk score from likelihood and impact if available
        let riskScore = null;
        if (riskLikelihoodSelect && riskImpactSelect && 
            riskLikelihoodSelect.value && riskImpactSelect.value) {
            riskScore = parseInt(riskLikelihoodSelect.value) * parseInt(riskImpactSelect.value);
        }
        
        // Count selected dependencies
        let dependenciesCount = 0;
        if (dependenciesSelect) {
            dependenciesCount = Array.from(dependenciesSelect.selectedOptions).length;
        }
        
        const taskData = {
            title: titleInput.value.trim(),
            description: descriptionInput ? descriptionInput.value : '',
            priority: prioritySelect ? prioritySelect.value : 'medium',
            assigned_to: assignedToSelect ? assignedToSelect.options[assignedToSelect.selectedIndex].text : 'Unassigned',
            board_id: boardId,
            task_id: taskId,
            // Enhanced prediction fields
            complexity_score: complexityScoreInput ? parseInt(complexityScoreInput.value) || 5 : 5,
            workload_impact: workloadImpactSelect ? workloadImpactSelect.value || 'medium' : 'medium',
            skill_match_score: skillMatchScoreInput && skillMatchScoreInput.value ? parseInt(skillMatchScoreInput.value) : null,
            collaboration_required: collaborationRequiredCheckbox ? collaborationRequiredCheckbox.checked : false,
            dependencies_count: dependenciesCount,
            risk_score: riskScore,
            risk_level: riskLevelSelect ? riskLevelSelect.value || null : null
        };
        
        predictTaskDeadline(taskData, function(error, data) {
            if (error) {
                // Check if error is due to missing assignee
                if (error.assignee_required) {
                    alert(error.message || 'Please select an assignee first. The AI needs to analyze their historical velocity and current workload to make an accurate prediction.');
                } else {
                    alert('Failed to predict deadline. Please try again.');
                }
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
    // Use stripMarkdown to clean up AI-generated text
    const stripMarkdown = window.AIExplainability?.stripMarkdown || ((text) => text);
    
    html += `
        <div class="card mb-3">
            <div class="card-header bg-light">
                <h6 class="mb-0"><i class="bi bi-info-circle"></i> Why This Deadline?</h6>
            </div>
            <div class="card-body">
                <div class="reasoning-section mb-3">
                    <h6 class="small fw-bold text-muted">REASONING</h6>
                    <p>${stripMarkdown(data.reasoning)}</p>
                </div>
    `;
    
    // Velocity analysis
    if (data.velocity_analysis) {
        const velocity = data.velocity_analysis;
        
        // Determine trend styling and icon based on value
        let trendClass = '';
        let trendIcon = '';
        let trendDisplay = velocity.velocity_trend;
        
        if (velocity.velocity_trend === 'Pending' || velocity.velocity_trend === 'N/A') {
            trendClass = 'text-muted';
            trendIcon = '<i class="fas fa-clock"></i>';
            trendDisplay = 'Pending';
        } else if (velocity.velocity_trend === 'accelerating') {
            trendClass = 'text-success';
            trendIcon = '<i class="fas fa-arrow-up"></i>';
            trendDisplay = '<span class="d-none d-sm-inline">Accelerating</span>';
        } else if (velocity.velocity_trend === 'declining') {
            trendClass = 'text-danger';
            trendIcon = '<i class="fas fa-arrow-down"></i>';
            trendDisplay = '<span class="d-none d-sm-inline">Declining</span>';
        } else {
            trendClass = 'text-primary';
            trendIcon = '<i class="fas fa-arrows-alt-h"></i>';
            trendDisplay = '<span class="d-none d-sm-inline">Steady</span>';
        }
        
        html += `
            <div class="velocity-section mb-3">
                <h6 class="small fw-bold text-muted">VELOCITY ANALYSIS</h6>
                <div class="row text-center g-2">
                    <div class="col-6 col-sm-3">
                        <div class="metric-box p-2">
                            <div class="small text-muted text-nowrap">Current</div>
                            <div class="fw-bold">${velocity.current_velocity}</div>
                        </div>
                    </div>
                    <div class="col-6 col-sm-3">
                        <div class="metric-box p-2">
                            <div class="small text-muted text-nowrap">Expected</div>
                            <div class="fw-bold">${velocity.expected_velocity}</div>
                        </div>
                    </div>
                    <div class="col-6 col-sm-3">
                        <div class="metric-box p-2">
                            <div class="small text-muted text-nowrap">Trend</div>
                            <div class="fw-bold ${trendClass}">
                                ${trendIcon} ${trendDisplay}
                            </div>
                        </div>
                    </div>
                    <div class="col-6 col-sm-3">
                        <div class="metric-box p-2">
                            <div class="small text-muted text-nowrap">Remaining</div>
                            <div class="fw-bold text-nowrap">${velocity.remaining_effort_hours}h</div>
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
 * Highlight due date field for user review after high complexity detection
 */
function highlightDueDateForReview() {
    const dueDateInput = document.getElementById('id_due_date');
    const dueDateSection = dueDateInput ? dueDateInput.closest('.col-md-6') : null;
    
    if (dueDateSection) {
        // Add pulsing highlight effect
        dueDateSection.style.backgroundColor = '#fff3cd';
        dueDateSection.style.border = '2px solid #ffc107';
        dueDateSection.style.borderRadius = '8px';
        dueDateSection.style.padding = '10px';
        dueDateSection.style.transition = 'all 0.3s ease';
        
        // Scroll to due date field
        dueDateSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // Focus the input
        if (dueDateInput) {
            dueDateInput.focus();
        }
        
        // Remove highlight after 5 seconds
        setTimeout(() => {
            dueDateSection.style.backgroundColor = '';
            dueDateSection.style.border = '';
            dueDateSection.style.padding = '';
        }, 5000);
    }
}

/**
 * Re-trigger deadline prediction button after complexity analysis
 */
function repredictDeadlineWithComplexity(complexityScore) {
    const predictButton = document.getElementById('predict-deadline-btn');
    if (predictButton) {
        // Store complexity score for context (optional for future backend integration)
        window.lastComplexityScore = complexityScore;
        
        // Show user feedback
        const toast = document.createElement('div');
        toast.className = 'alert alert-info position-fixed top-0 start-50 translate-middle-x mt-3';
        toast.style.zIndex = '9999';
        toast.innerHTML = `<i class="fas fa-info-circle"></i> Re-calculating deadline with complexity score of ${complexityScore}/10...`;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 2000);
        
        // Trigger the predict deadline button
        predictButton.click();
    } else {
        alert('Please use the "Predict" button next to the Due Date field to calculate an optimal deadline.');
    }
}

/**
 * Utility function to get priority badge class
 * Supports accessibility mode with colorblind-friendly colors
 */
function getPriorityBadgeClass(priority) {
    // Standard mapping works for both modes since CSS handles the color transformation
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
    
    // Get the user's manual complexity score
    const userComplexityInput = document.querySelector('input[name="complexity_score"]');
    const userComplexityScore = userComplexityInput ? parseInt(userComplexityInput.value) : null;
    const aiComplexityScore = data.complexity_score;
    
    // Determine if there's a discrepancy
    const hasDiscrepancy = userComplexityScore && userComplexityScore !== aiComplexityScore;
    const scoreDifference = hasDiscrepancy ? Math.abs(userComplexityScore - aiComplexityScore) : 0;
    
    let html = `
        <div class="alert alert-${data.is_breakdown_recommended ? 'warning' : 'info'}">
            <h6><i class="fas fa-sitemap"></i> Task Complexity Analysis</h6>
            
            <!-- Complexity Score Comparison -->
            <div class="mb-3">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span><strong>AI Complexity Score:</strong></span>
                    <div class="d-flex align-items-center gap-2">
                        <span class="badge bg-${getComplexityBadgeClass(aiComplexityScore)} fs-6">${aiComplexityScore}/10</span>
                        ${hasDiscrepancy ? `
                            <button type="button" class="btn btn-sm btn-success" onclick="applyAIComplexityScore(${aiComplexityScore})" title="Apply AI score to your manual estimate">
                                <i class="fas fa-check me-1"></i>Apply this Score
                            </button>
                        ` : ''}
                    </div>
                </div>
                
                ${hasDiscrepancy ? `
                    <div class="complexity-comparison mt-3 p-3 bg-light border rounded">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <small class="text-muted"><i class="fas fa-info-circle me-1"></i> Score Comparison:</small>
                            <small class="text-muted">Difference: ${scoreDifference} point${scoreDifference !== 1 ? 's' : ''}</small>
                        </div>
                        
                        <!-- User Score (Solid Bar) -->
                        <div class="mb-2">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <small><strong>Your Estimate:</strong> ${userComplexityScore}/10</small>
                                <span class="badge bg-secondary">${userComplexityScore > aiComplexityScore ? 'Higher' : 'Lower'}</span>
                            </div>
                            <div class="progress" style="height: 20px;">
                                <div class="progress-bar bg-primary" role="progressbar" 
                                     style="width: ${userComplexityScore * 10}%" 
                                     aria-valuenow="${userComplexityScore}" aria-valuemin="0" aria-valuemax="10">
                                    ${userComplexityScore}
                                </div>
                            </div>
                        </div>
                        
                        <!-- AI Score (Outlined/Ghost Bar) -->
                        <div>
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <small><strong>AI Suggestion:</strong> ${aiComplexityScore}/10</small>
                                <span class="badge bg-info">AI</span>
                            </div>
                            <div class="progress" style="height: 20px; background-color: transparent; border: 2px dashed #0dcaf0;">
                                <div class="progress-bar" role="progressbar" 
                                     style="width: ${aiComplexityScore * 10}%; background-color: rgba(13, 202, 240, 0.3); border-right: 3px solid #0dcaf0;" 
                                     aria-valuenow="${aiComplexityScore}" aria-valuemin="0" aria-valuemax="10">
                                    ${aiComplexityScore}
                                </div>
                            </div>
                        </div>
                        
                        <div class="alert alert-info mt-3 mb-0 py-2">
                            <small>
                                <i class="fas fa-lightbulb me-1"></i>
                                <strong>You're the Captain:</strong> ${userComplexityScore > aiComplexityScore ? 
                                    'Your estimate is higher. You might know factors the AI doesn\'t (e.g., team constraints, hidden complexity).' : 
                                    'Your estimate is lower. The AI detected factors you might want to reconsider.'}
                                The AI provides a <em>second opinion</em>—review the analysis below and decide.
                            </small>
                        </div>
                    </div>
                ` : ''}
            </div>
            
            <p><strong>Breakdown Recommended:</strong> ${data.is_breakdown_recommended ? 'Yes' : 'No'}</p>
            <p><strong>Analysis:</strong> ${data.reasoning}</p>
    `;
    
    // High Complexity Warning - nudge user about due date
    if (data.complexity_score > 7) {
        html += `
            <div class="alert alert-danger mt-3 mb-0" role="alert">
                <h6 class="alert-heading"><i class="fas fa-exclamation-triangle"></i> High Complexity Detected!</h6>
                <p class="mb-2">This task has a complexity score of <strong>${data.complexity_score}/10</strong>. 
                The current due date might be too aggressive.</p>
                <p class="mb-2"><strong>Recommendation:</strong> Consider extending the deadline by <strong>2-3 days</strong> 
                to account for the task complexity.</p>
                <button type="button" class="btn btn-sm btn-warning mt-2" onclick="highlightDueDateForReview()">
                    <i class="fas fa-calendar-check me-1"></i> Review Due Date
                </button>
                <button type="button" class="btn btn-sm btn-info mt-2 ms-2" onclick="repredictDeadlineWithComplexity(${data.complexity_score})">
                    <i class="fas fa-brain me-1"></i> Re-predict Deadline
                </button>
            </div>
        `;
    }
    
    html += `
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
                    ${subtask.dependencies && subtask.dependencies.length > 0 ? 
                        `<small class="ms-3 text-info">Depends on: ${subtask.dependencies.map(d => parseInt(d) + 1).join(', ')}</small>` : 
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
                // Handle both string and object formats
                if (typeof risk === 'string') {
                    html += `<li class="text-warning">${risk}</li>`;
                } else if (typeof risk === 'object' && risk.risk) {
                    html += `<li class="text-warning">`;
                    html += `<strong>${risk.risk}</strong>`;
                    if (risk.affected_subtasks && risk.affected_subtasks.length > 0) {
                        html += `<br><small>Affects: ${risk.affected_subtasks.join(', ')}</small>`;
                    }
                    if (risk.mitigation) {
                        html += `<br><small class="text-muted">Mitigation: ${risk.mitigation}</small>`;
                    }
                    html += `</li>`;
                }
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
 * Apply AI-suggested complexity score to the manual input
 */
function applyAIComplexityScore(aiScore) {
    const complexityInput = document.querySelector('input[name="complexity_score"]');
    const complexityOutput = document.getElementById('complexity-output');
    
    if (!complexityInput) {
        console.error('Complexity input not found');
        return;
    }
    
    // Update the input value
    complexityInput.value = aiScore;
    
    // Trigger input event to update the visual indicator
    complexityInput.dispatchEvent(new Event('input', { bubbles: true }));
    
    // Update the output badge if it exists
    if (complexityOutput) {
        complexityOutput.value = aiScore;
        complexityOutput.textContent = aiScore;
        
        // Update badge color based on complexity
        complexityOutput.className = 'badge ';
        if (aiScore >= 8) {
            complexityOutput.className += 'bg-danger';
        } else if (aiScore >= 5) {
            complexityOutput.className += 'bg-warning';
        } else {
            complexityOutput.className += 'bg-success';
        }
    }
    
    // Scroll to the complexity input to show the update
    complexityInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Highlight the input briefly
    complexityInput.parentElement.style.transition = 'background-color 0.3s ease';
    complexityInput.parentElement.style.backgroundColor = '#d1ecf1';
    setTimeout(() => {
        complexityInput.parentElement.style.backgroundColor = '';
    }, 1500);
    
    // Show a subtle success message
    const resultDiv = document.getElementById('task-breakdown-result');
    if (resultDiv) {
        const successMsg = document.createElement('div');
        successMsg.className = 'alert alert-success alert-dismissible fade show mt-2';
        successMsg.innerHTML = `
            <i class="fas fa-check-circle me-1"></i>
            <strong>Score Applied!</strong> Your complexity estimate has been updated to ${aiScore}/10.
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        resultDiv.insertBefore(successMsg, resultDiv.firstChild);
        
        // Auto-dismiss after 3 seconds
        setTimeout(() => {
            successMsg.remove();
        }, 3000);
    }
}

/**
 * Helper function to get complexity badge class
 */
function getComplexityBadgeClass(score) {
    if (score >= 8) return 'danger';
    if (score >= 6) return 'warning';
    if (score >= 4) return 'info';
    return 'success';
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
 * Accept LSS classification suggestion
 */
function acceptLssClassification(value) {
    const radioButton = document.getElementById(`lss_${value}`);
    if (radioButton) {
        radioButton.checked = true;
        // Hide the suggestion after accepting
        const container = document.getElementById('lss-suggestion-container');
        if (container) {
            container.classList.add('d-none');
        }
        // Show success message
        if (typeof showToast === 'function') {
            showToast('LSS classification applied!', 'success');
        }
    }
}

/**
 * Toggle LSS classification explainability section
 */
function toggleLssExplain() {
    const explainSection = document.getElementById('lss-explainability');
    if (explainSection) {
        if (explainSection.style.display === 'none') {
            explainSection.style.display = 'block';
        } else {
            explainSection.style.display = 'none';
        }
    }
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

/**
 * Toggle LSS classification explainability section
 */
function toggleLssExplain() {
    const section = document.getElementById('lss-explainability');
    if (section) {
        section.style.display = section.style.display === 'none' ? 'block' : 'none';
    }
}

/**
 * Toggle analytics summary explainability section
 */
function toggleAnalyticsExplain() {
    const section = document.getElementById('analytics-explainability');
    if (section) {
        section.style.display = section.style.display === 'none' ? 'block' : 'none';
    }
}

/**
 * Show AI explainability modal with full details
 */
function showAIExplainabilityModal(data, title) {
    if (typeof AIExplainability !== 'undefined' && AIExplainability.showExplainabilityModal) {
        AIExplainability.showExplainabilityModal(data, title);
    } else {
        // Fallback modal
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header bg-primary text-white">
                        <h5 class="modal-title"><i class="bi bi-robot me-2"></i>${title || 'AI Explainability'}</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        ${data.confidence_score !== undefined ? `
                            <div class="mb-3">
                                <h6>Confidence Score</h6>
                                <div class="progress" style="height: 25px;">
                                    <div class="progress-bar ${data.confidence_score >= 0.75 ? 'bg-success' : data.confidence_score >= 0.5 ? 'bg-warning' : 'bg-danger'}" 
                                         style="width: ${Math.round(data.confidence_score * 100)}%">
                                        ${Math.round(data.confidence_score * 100)}%
                                    </div>
                                </div>
                            </div>
                        ` : ''}
                        ${data.reasoning ? `
                            <div class="mb-3">
                                <h6>Reasoning</h6>
                                <p>${data.reasoning}</p>
                            </div>
                        ` : ''}
                        ${data.contributing_factors && data.contributing_factors.length > 0 ? `
                            <div class="mb-3">
                                <h6>Contributing Factors</h6>
                                <ul>
                                    ${data.contributing_factors.map(f => `<li>${f.factor || f}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                        ${data.assumptions && data.assumptions.length > 0 ? `
                            <div class="mb-3">
                                <h6>Assumptions</h6>
                                <ul class="text-warning">
                                    ${data.assumptions.map(a => `<li>${a}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        modal.addEventListener('hidden.bs.modal', () => modal.remove());
    }
}

// Export functions for global access
window.toggleLssExplain = toggleLssExplain;
window.toggleAnalyticsExplain = toggleAnalyticsExplain;
window.showAIExplainabilityModal = showAIExplainabilityModal;


