/**
 * Skill Gap Analysis UI Components
 * Provides visualization and interaction for skill matching and gap analysis
 */

class SkillGapAnalyzer {
    constructor(boardId) {
        this.boardId = boardId;
        this.gaps = [];
        this.teamProfile = null;
        this.developmentPlans = [];
    }

    /**
     * Initialize the skill gap analyzer
     */
    async init() {
        await this.loadTeamProfile();
        await this.loadSkillGaps();
        await this.loadDevelopmentPlans();
        this.renderDashboard();
    }

    /**
     * Analyze skill gaps for the board
     */
    async analyzeGaps(sprintDays = 14) {
        try {
            const response = await fetch(`/api/skill-gaps/analyze/${this.boardId}/?sprint_days=${sprintDays}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                }
            });

            if (!response.ok) {
                throw new Error('Failed to analyze skill gaps');
            }

            const data = await response.json();
            this.gaps = data.gaps;
            this.renderGapsSection();
            
            // Check if recommendations are pending
            const pendingCount = data.gaps.filter(g => g.recommendations_pending).length;
            if (pendingCount > 0) {
                this.showNotification(`Analysis complete! ${pendingCount} gap(s) pending AI recommendations...`, 'info');
            } else {
                this.showNotification('Skill gap analysis completed', 'success');
            }
            
            return data;
        } catch (error) {
            console.error('Error analyzing gaps:', error);
            this.showNotification('Failed to analyze skill gaps', 'error');
            throw error;
        }
    }

    /**
     * Load team skill profile
     */
    async loadTeamProfile() {
        try {
            const response = await fetch(`/api/team-skill-profile/${this.boardId}/`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.teamProfile = data;
            }
        } catch (error) {
            console.error('Error loading team profile:', error);
        }
    }

    /**
     * Load existing skill gaps
     */
    async loadSkillGaps() {
        try {
            const response = await fetch(`/api/skill-gaps/list/${this.boardId}/`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.gaps = data.gaps;
            }
        } catch (error) {
            console.error('Error loading skill gaps:', error);
        }
    }

    /**
     * Load development plans
     */
    async loadDevelopmentPlans() {
        try {
            const response = await fetch(`/api/development-plans/${this.boardId}/`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.developmentPlans = data.plans;
            }
        } catch (error) {
            console.error('Error loading development plans:', error);
        }
    }

    /**
     * Extract skills from task description
     */
    async extractTaskSkills(taskId) {
        try {
            const response = await fetch(`/api/task/${taskId}/extract-skills/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                }
            });

            if (!response.ok) {
                throw new Error('Failed to extract skills');
            }

            const data = await response.json();
            this.showNotification(`Extracted ${data.skills.length} skills from task`, 'success');
            
            return data.skills;
        } catch (error) {
            console.error('Error extracting skills:', error);
            this.showNotification('Failed to extract skills', 'error');
            throw error;
        }
    }

    /**
     * Find best team members for a task
     */
    async matchTeamToTask(taskId) {
        try {
            const response = await fetch(`/api/task/${taskId}/match-team/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                }
            });

            if (!response.ok) {
                throw new Error('Failed to match team members');
            }

            const data = await response.json();
            return data.matches;
        } catch (error) {
            console.error('Error matching team:', error);
            this.showNotification('Failed to match team members', 'error');
            throw error;
        }
    }

    /**
     * Create a skill development plan
     */
    async createDevelopmentPlan(gapId, planData) {
        try {
            const response = await fetch('/api/development-plans/create/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    skill_gap_id: gapId,
                    ...planData
                })
            });

            if (!response.ok) {
                throw new Error('Failed to create development plan');
            }

            const data = await response.json();
            this.showNotification('Development plan created successfully', 'success');
            await this.loadDevelopmentPlans();
            this.renderPlansSection();
            
            return data;
        } catch (error) {
            console.error('Error creating plan:', error);
            this.showNotification('Failed to create development plan', 'error');
            throw error;
        }
    }

    /**
     * Render the main dashboard
     */
    renderDashboard() {
        const container = document.getElementById('skill-gap-dashboard');
        if (!container) return;

        container.innerHTML = `
            <div class="skill-gap-dashboard">
                <div class="row mb-4">
                    <div class="col-md-12">
                        <div class="d-flex justify-content-between align-items-center">
                            <h3><i class="fas fa-brain me-2"></i>Skill Gap Analysis</h3>
                            <button class="btn btn-primary" onclick="skillGapAnalyzer.analyzeGaps()">
                                <i class="fas fa-sync-alt me-1"></i>Run Analysis
                            </button>
                        </div>
                    </div>
                </div>

                <div class="row mb-4">
                    <div class="col-md-12">
                        <div id="team-profile-summary"></div>
                    </div>
                </div>

                <div class="row mb-4">
                    <div class="col-md-6">
                        <div id="skill-gaps-section"></div>
                    </div>
                    <div class="col-md-6">
                        <div id="development-plans-section"></div>
                    </div>
                </div>

                <div class="row">
                    <div class="col-md-12">
                        <div id="skill-matrix-section"></div>
                    </div>
                </div>
            </div>
        `;

        this.renderTeamProfileSummary();
        this.renderGapsSection();
        this.renderPlansSection();
        this.renderSkillMatrix();
    }

    /**
     * Render team profile summary
     */
    renderTeamProfileSummary() {
        const container = document.getElementById('team-profile-summary');
        if (!container || !this.teamProfile) return;

        const utilization = this.teamProfile.utilization_percentage || 0;
        const utilizationClass = utilization > 90 ? 'danger' : utilization > 75 ? 'warning' : 'success';

        container.innerHTML = `
            <div class="card shadow-sm">
                <div class="card-body">
                    <h5 class="card-title"><i class="fas fa-users me-2"></i>Team Overview</h5>
                    <div class="row">
                        <div class="col-md-3">
                            <div class="stat-box">
                                <h3>${this.teamProfile.team_size}</h3>
                                <p class="text-muted">Team Members</p>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="stat-box">
                                <h3>${this.teamProfile.total_unique_skills}</h3>
                                <p class="text-muted">Unique Skills</p>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="stat-box">
                                <h3>${this.teamProfile.total_capacity_hours}h</h3>
                                <p class="text-muted">Total Capacity</p>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="stat-box">
                                <h3 class="text-${utilizationClass}">${utilization.toFixed(1)}%</h3>
                                <p class="text-muted">Utilization</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render skill gaps section
     */
    renderGapsSection() {
        const container = document.getElementById('skill-gaps-section');
        if (!container) return;

        const criticalGaps = this.gaps.filter(g => g.severity === 'critical' || g.severity === 'high');
        const otherGaps = this.gaps.filter(g => g.severity !== 'critical' && g.severity !== 'high');

        container.innerHTML = `
            <div class="card shadow-sm">
                <div class="card-header bg-warning text-white">
                    <h5 class="mb-0"><i class="fas fa-exclamation-triangle me-2"></i>Skill Gaps (${this.gaps.length})</h5>
                </div>
                <div class="card-body">
                    ${this.gaps.length === 0 ? 
                        '<p class="text-muted text-center py-4">No skill gaps identified. Run analysis to check.</p>' :
                        this.renderGapsList(criticalGaps, otherGaps)
                    }
                </div>
            </div>
        `;
    }

    /**
     * Render gaps list
     */
    renderGapsList(criticalGaps, otherGaps) {
        let html = '';

        if (criticalGaps.length > 0) {
            html += '<h6 class="text-danger"><i class="fas fa-fire me-1"></i>Critical & High Priority</h6>';
            html += '<div class="gaps-list mb-3">';
            criticalGaps.forEach(gap => {
                html += this.renderGapCard(gap);
            });
            html += '</div>';
        }

        if (otherGaps.length > 0) {
            html += '<h6 class="text-muted">Medium & Low Priority</h6>';
            html += '<div class="gaps-list">';
            otherGaps.forEach(gap => {
                html += this.renderGapCard(gap);
            });
            html += '</div>';
        }

        return html;
    }

    /**
     * Render individual gap card
     */
    renderGapCard(gap) {
        const severityBadge = this.getSeverityBadge(gap.severity);
        const statusBadge = this.getStatusBadge(gap.status);

        return `
            <div class="gap-card mb-2 p-3 border rounded">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div>
                        <h6 class="mb-1">${gap.skill_name} <span class="badge bg-secondary">${gap.proficiency_level}</span></h6>
                        <small class="text-muted">Need ${gap.gap_count} more • ${gap.affected_tasks_count} tasks affected</small>
                    </div>
                    <div>
                        ${severityBadge}
                        ${statusBadge}
                    </div>
                </div>
                ${gap.recommendations_pending ? `
                    <div class="mt-2">
                        <small class="text-warning"><i class="fas fa-spinner fa-spin me-1"></i>AI recommendations generating...</small>
                    </div>
                ` : gap.recommendations && gap.recommendations.length > 0 ? `
                    <div class="mt-2">
                        <small class="text-muted"><i class="fas fa-lightbulb me-1"></i>${gap.recommendations_count} recommendations</small>
                        <button class="btn btn-sm btn-outline-primary ms-2" onclick="skillGapAnalyzer.showGapDetails(${gap.id})">
                            View Details
                        </button>
                    </div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Render development plans section
     */
    renderPlansSection() {
        const container = document.getElementById('development-plans-section');
        if (!container) return;

        const activePlans = this.developmentPlans.filter(p => p.status === 'in_progress' || p.status === 'approved');
        const proposedPlans = this.developmentPlans.filter(p => p.status === 'proposed');

        container.innerHTML = `
            <div class="card shadow-sm">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0"><i class="fas fa-graduation-cap me-2"></i>Development Plans (${this.developmentPlans.length})</h5>
                </div>
                <div class="card-body">
                    ${this.developmentPlans.length === 0 ? 
                        '<p class="text-muted text-center py-4">No development plans yet.</p>' :
                        this.renderPlansList(activePlans, proposedPlans)
                    }
                </div>
            </div>
        `;
    }

    /**
     * Render plans list
     */
    renderPlansList(activePlans, proposedPlans) {
        let html = '';

        if (activePlans.length > 0) {
            html += '<h6 class="text-primary"><i class="fas fa-play-circle me-1"></i>Active Plans</h6>';
            html += '<div class="plans-list mb-3">';
            activePlans.forEach(plan => {
                html += this.renderPlanCard(plan);
            });
            html += '</div>';
        }

        if (proposedPlans.length > 0) {
            html += '<h6 class="text-muted">Proposed Plans</h6>';
            html += '<div class="plans-list">';
            proposedPlans.forEach(plan => {
                html += this.renderPlanCard(plan);
            });
            html += '</div>';
        }

        return html;
    }

    /**
     * Render individual plan card
     */
    renderPlanCard(plan) {
        const typeBadge = this.getPlanTypeBadge(plan.plan_type);
        const statusBadge = this.getStatusBadge(plan.status);
        const progressBar = this.renderProgressBar(plan.progress_percentage);

        return `
            <div class="plan-card mb-2 p-3 border rounded">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div>
                        <h6 class="mb-1">${plan.title}</h6>
                        <small class="text-muted">${plan.target_skill} (${plan.target_proficiency})</small>
                    </div>
                    <div>
                        ${typeBadge}
                        ${statusBadge}
                    </div>
                </div>
                ${progressBar}
                <div class="mt-2">
                    <small class="text-muted">
                        ${plan.target_users.length} team member(s) • 
                        ${plan.estimated_hours ? plan.estimated_hours + 'h' : 'No time estimate'}
                    </small>
                </div>
            </div>
        `;
    }

    /**
     * Render skill matrix (heatmap)
     */
    renderSkillMatrix() {
        const container = document.getElementById('skill-matrix-section');
        if (!container || !this.teamProfile || !this.teamProfile.skills) return;

        // Take top 10 skills
        const topSkills = this.teamProfile.skills.slice(0, 10);

        let html = `
            <div class="card shadow-sm">
                <div class="card-header">
                    <h5 class="mb-0"><i class="fas fa-th me-2"></i>Team Skill Matrix</h5>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-bordered skill-matrix-table">
                            <thead>
                                <tr>
                                    <th>Skill</th>
                                    <th class="text-center">Expert</th>
                                    <th class="text-center">Advanced</th>
                                    <th class="text-center">Intermediate</th>
                                    <th class="text-center">Beginner</th>
                                    <th class="text-center">Total</th>
                                </tr>
                            </thead>
                            <tbody>
        `;

        topSkills.forEach(skill => {
            html += `
                <tr>
                    <td><strong>${skill.skill_name}</strong></td>
                    <td class="text-center">${this.renderSkillCell(skill.expert)}</td>
                    <td class="text-center">${this.renderSkillCell(skill.advanced)}</td>
                    <td class="text-center">${this.renderSkillCell(skill.intermediate)}</td>
                    <td class="text-center">${this.renderSkillCell(skill.beginner)}</td>
                    <td class="text-center"><strong>${skill.total_members}</strong></td>
                </tr>
            `;
        });

        html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = html;
    }

    /**
     * Render skill cell with color coding
     */
    renderSkillCell(count) {
        if (count === 0) {
            return '<span class="text-muted">-</span>';
        }
        
        const colorClass = count >= 3 ? 'success' : count >= 2 ? 'primary' : 'secondary';
        return `<span class="badge bg-${colorClass}">${count}</span>`;
    }

    /**
     * Render progress bar
     */
    renderProgressBar(percentage) {
        const colorClass = percentage >= 75 ? 'success' : percentage >= 50 ? 'primary' : 'warning';
        return `
            <div class="progress" style="height: 6px;">
                <div class="progress-bar bg-${colorClass}" role="progressbar" 
                     style="width: ${percentage}%" aria-valuenow="${percentage}" 
                     aria-valuemin="0" aria-valuemax="100"></div>
            </div>
        `;
    }

    /**
     * Get severity badge HTML
     */
    getSeverityBadge(severity) {
        const badges = {
            'critical': '<span class="badge bg-danger">Critical</span>',
            'high': '<span class="badge bg-warning text-dark">High</span>',
            'medium': '<span class="badge bg-info">Medium</span>',
            'low': '<span class="badge bg-secondary">Low</span>'
        };
        return badges[severity] || '';
    }

    /**
     * Get status badge HTML
     */
    getStatusBadge(status) {
        const badges = {
            'identified': '<span class="badge bg-warning">Identified</span>',
            'acknowledged': '<span class="badge bg-info">Acknowledged</span>',
            'in_progress': '<span class="badge bg-primary">In Progress</span>',
            'resolved': '<span class="badge bg-success">Resolved</span>',
            'proposed': '<span class="badge bg-secondary">Proposed</span>',
            'approved': '<span class="badge bg-success">Approved</span>',
            'completed': '<span class="badge bg-success">Completed</span>'
        };
        return badges[status] || '';
    }

    /**
     * Get plan type badge HTML
     */
    getPlanTypeBadge(type) {
        const badges = {
            'training': '<span class="badge bg-primary"><i class="fas fa-book me-1"></i>Training</span>',
            'hiring': '<span class="badge bg-success"><i class="fas fa-user-plus me-1"></i>Hiring</span>',
            'contractor': '<span class="badge bg-info"><i class="fas fa-handshake me-1"></i>Contractor</span>',
            'redistribute': '<span class="badge bg-warning"><i class="fas fa-exchange-alt me-1"></i>Redistribute</span>',
            'mentorship': '<span class="badge bg-purple"><i class="fas fa-user-graduate me-1"></i>Mentorship</span>',
            'cross_training': '<span class="badge bg-secondary"><i class="fas fa-users me-1"></i>Cross-training</span>'
        };
        return badges[type] || '';
    }

    /**
     * Show gap details modal
     */
    showGapDetails(gapId) {
        const gap = this.gaps.find(g => g.id === gapId);
        if (!gap) return;

        // Create modal HTML
        const modalHtml = `
            <div class="modal fade" id="gapDetailsModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                ${gap.skill_name} (${gap.proficiency_level}) - Gap Details
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <strong>Gap Size:</strong> Need ${gap.gap_count} more team member(s)<br>
                                <strong>Currently Available:</strong> ${gap.available_count}<br>
                                <strong>Severity:</strong> ${this.getSeverityBadge(gap.severity)}<br>
                                <strong>Status:</strong> ${this.getStatusBadge(gap.status)}
                            </div>

                            ${gap.affected_tasks && gap.affected_tasks.length > 0 ? `
                                <div class="mb-3">
                                    <h6>Affected Tasks (${gap.affected_tasks.length})</h6>
                                    <ul class="list-group">
                                        ${gap.affected_tasks.map(t => `
                                            <li class="list-group-item">${t.title}</li>
                                        `).join('')}
                                    </ul>
                                </div>
                            ` : ''}

                            ${gap.recommendations && gap.recommendations.length > 0 ? `
                                <div class="mb-3">
                                    <h6>AI Recommendations</h6>
                                    ${gap.recommendations.map(rec => `
                                        <div class="card mb-2">
                                            <div class="card-body">
                                                <h6>${rec.title} ${this.getPlanTypeBadge(rec.type)}</h6>
                                                <p class="mb-2">${rec.description}</p>
                                                <small class="text-muted">
                                                    Timeframe: ${rec.timeframe_days} days • 
                                                    Cost: ${rec.cost_estimate} • 
                                                    Priority: ${rec.priority}/10
                                                </small>
                                                <div class="mt-2">
                                                    <button class="btn btn-sm btn-primary" 
                                                            onclick="skillGapAnalyzer.createPlanFromRecommendation(${gap.id}, ${JSON.stringify(rec).replace(/"/g, '&quot;')})">
                                                        <i class="fas fa-plus me-1"></i>Create Plan
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            ` : ''}
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal if any
        const existingModal = document.getElementById('gapDetailsModal');
        if (existingModal) {
            existingModal.remove();
        }

        // Add modal to body
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('gapDetailsModal'));
        modal.show();
    }

    /**
     * Create plan from recommendation
     */
    async createPlanFromRecommendation(gapId, recommendation) {
        const planData = {
            plan_type: recommendation.type,
            title: recommendation.title,
            description: recommendation.description,
            estimated_hours: recommendation.timeframe_days * 8, // Convert days to hours
            ai_suggested: true
        };

        await this.createDevelopmentPlan(gapId, planData);

        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('gapDetailsModal'));
        if (modal) {
            modal.hide();
        }
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Use existing notification system if available
        if (typeof showNotification === 'function') {
            showNotification(message, type);
        } else {
            console.log(`[${type}] ${message}`);
        }
    }

    /**
     * Get CSRF token
     */
    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
}

// Global instance - make it a window property to avoid conflicts
window.skillGapAnalyzer = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const dashboardElement = document.getElementById('skill-gap-dashboard');
    if (dashboardElement) {
        const boardId = dashboardElement.dataset.boardId;
        if (boardId) {
            window.skillGapAnalyzer = new SkillGapAnalyzer(boardId);
            window.skillGapAnalyzer.init();
        }
    }
});
