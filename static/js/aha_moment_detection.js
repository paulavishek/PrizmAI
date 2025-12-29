/**
 * Aha Moment Detection System
 * Tracks user interactions and triggers aha moments at the right time
 */

// Detection state
const ahaDetectionState = {
    burndownViewStart: null,
    timeTrackingInteractions: 0,
    pageViews: {},
    initialized: false
};

/**
 * Initialize aha moment detection
 */
function initAhaMomentDetection() {
    if (ahaDetectionState.initialized) return;
    
    console.log('🎯 Initializing aha moment detection...');
    
    // Detect AI suggestion acceptance
    detectAISuggestionAcceptance();
    
    // Detect burndown chart viewing
    detectBurndownViewing();
    
    // Detect RBAC interactions
    detectRBACInteractions();
    
    // Detect time tracking usage
    detectTimeTrackingUsage();
    
    // Detect dependency creation
    detectDependencyCreation();
    
    // Detect Gantt chart viewing
    detectGanttViewing();
    
    // Detect skill gap viewing
    detectSkillGapViewing();
    
    // Detect conflict resolution
    detectConflictResolution();
    
    ahaDetectionState.initialized = true;
}

/**
 * Detect AI suggestion acceptance
 */
function detectAISuggestionAcceptance() {
    // Watch for AI suggestion acceptance buttons
    document.addEventListener('click', (e) => {
        if (e.target.matches('.accept-ai-suggestion, [data-action="accept-suggestion"]')) {
            console.log('✅ AI suggestion accepted!');
            showAhaMoment('ai_suggestion_accepted', {
                suggestion_type: e.target.dataset.suggestionType || 'general'
            });
        }
    });
    
    // Also watch for AI-generated content being saved
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const url = args[0];
        if (typeof url === 'string' && (url.includes('/ai/') || url.includes('/generate/'))) {
            return originalFetch.apply(this, args).then(response => {
                if (response.ok && args[1]?.method === 'POST') {
                    setTimeout(() => {
                        console.log('✅ AI content generated!');
                        showAhaMoment('ai_suggestion_accepted', {
                            action: 'ai_generation'
                        });
                    }, 1000);
                }
                return response;
            });
        }
        return originalFetch.apply(this, args);
    };
}

/**
 * Detect burndown chart viewing (>10 seconds)
 */
function detectBurndownViewing() {
    // Check if on burndown/analytics page
    const isBurndownPage = window.location.pathname.includes('/analytics') || 
                          window.location.pathname.includes('/burndown') ||
                          document.querySelector('.burndown-chart, [data-chart="burndown"]');
    
    if (isBurndownPage && !ahaDetectionState.burndownViewStart) {
        ahaDetectionState.burndownViewStart = Date.now();
        console.log('📊 Started viewing burndown chart...');
        
        // Check after 10 seconds
        setTimeout(() => {
            const viewDuration = Date.now() - ahaDetectionState.burndownViewStart;
            if (viewDuration >= 10000) {
                console.log('📊 Burndown chart viewed for 10+ seconds!');
                showAhaMoment('burndown_viewed', {
                    duration_seconds: Math.floor(viewDuration / 1000)
                });
            }
        }, 10000);
    }
}

/**
 * Detect RBAC workflow (role switching, permission changes)
 */
function detectRBACInteractions() {
    // Watch for role switching
    document.addEventListener('click', (e) => {
        if (e.target.matches('.switch-role, [data-role], .role-selector option')) {
            setTimeout(() => {
                console.log('🔐 RBAC role switched!');
                showAhaMoment('rbac_workflow', {
                    action: 'role_switch',
                    new_role: e.target.value || e.target.dataset.role
                });
            }, 500);
        }
    });
    
    // Watch for permission-related pages
    if (window.location.pathname.includes('/permissions') || 
        window.location.pathname.includes('/members')) {
        // Track page interaction
        let interactionCount = 0;
        document.addEventListener('click', (e) => {
            if (e.target.closest('.permissions-panel, .member-list, .access-control')) {
                interactionCount++;
                if (interactionCount === 3) {
                    console.log('🔐 RBAC system explored!');
                    showAhaMoment('rbac_workflow', {
                        action: 'permissions_explored'
                    });
                }
            }
        });
    }
}

/**
 * Detect time tracking usage
 */
function detectTimeTrackingUsage() {
    // Watch for time tracking buttons
    document.addEventListener('click', (e) => {
        if (e.target.matches('.start-timer, .stop-timer, [data-action="track-time"]')) {
            ahaDetectionState.timeTrackingInteractions++;
            
            if (ahaDetectionState.timeTrackingInteractions === 2) {
                console.log('⏱️ Time tracking used!');
                showAhaMoment('time_tracking_used', {
                    action: 'timer_interaction'
                });
            }
        }
    });
    
    // Watch for time entry forms
    const timeInputs = document.querySelectorAll('input[name*="time"], input[type="time"], .time-entry');
    timeInputs.forEach(input => {
        input.addEventListener('change', () => {
            console.log('⏱️ Time logged manually!');
            showAhaMoment('time_tracking_used', {
                action: 'manual_time_entry'
            });
        });
    });
}

/**
 * Detect dependency creation
 */
function detectDependencyCreation() {
    // Watch for dependency creation buttons/forms
    document.addEventListener('click', (e) => {
        if (e.target.matches('.add-dependency, [data-action="add-dependency"]')) {
            setTimeout(() => {
                console.log('🔗 Task dependency created!');
                showAhaMoment('dependency_created', {
                    action: 'dependency_added'
                });
            }, 500);
        }
    });
    
    // Watch for AJAX dependency creation
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const url = args[0];
        if (typeof url === 'string' && url.includes('/dependency') && args[1]?.method === 'POST') {
            return originalFetch.apply(this, args).then(response => {
                if (response.ok) {
                    setTimeout(() => {
                        console.log('🔗 Dependency created via API!');
                        showAhaMoment('dependency_created', {
                            action: 'dependency_api'
                        });
                    }, 500);
                }
                return response;
            });
        }
        return originalFetch.apply(this, args);
    };
}

/**
 * Detect Gantt chart viewing
 */
function detectGanttViewing() {
    const isGanttPage = window.location.pathname.includes('/gantt') ||
                       document.querySelector('.gantt-chart, [data-chart="gantt"]');
    
    if (isGanttPage) {
        // Trigger after 3 seconds of viewing
        setTimeout(() => {
            console.log('📅 Gantt chart viewed!');
            showAhaMoment('gantt_viewed', {
                view_duration: 3
            });
        }, 3000);
    }
}

/**
 * Detect skill gap viewing
 */
function detectSkillGapViewing() {
    const isSkillGapPage = window.location.pathname.includes('/skill') ||
                          document.querySelector('.skill-gap, [data-view="skill-gaps"]');
    
    if (isSkillGapPage) {
        // Trigger after 5 seconds
        setTimeout(() => {
            console.log('🎯 Skill gap analysis viewed!');
            showAhaMoment('skill_gap_viewed', {
                view_duration: 5
            });
        }, 5000);
    }
}

/**
 * Detect conflict resolution interaction
 */
function detectConflictResolution() {
    // Watch for conflict-related interactions
    document.addEventListener('click', (e) => {
        if (e.target.matches('.resolve-conflict, .conflict-item, [data-conflict-id]')) {
            console.log('⚡ Conflict detection feature explored!');
            showAhaMoment('conflict_detected', {
                action: 'conflict_viewed'
            });
        }
    });
    
    // Check if conflicts badge exists and is visible
    const conflictBadge = document.querySelector('.conflict-badge, [data-conflicts]');
    if (conflictBadge && parseInt(conflictBadge.textContent) > 0) {
        setTimeout(() => {
            console.log('⚡ Active conflicts detected!');
            showAhaMoment('conflict_detected', {
                action: 'conflicts_present',
                count: parseInt(conflictBadge.textContent)
            });
        }, 5000);
    }
}

/**
 * Track page views for pattern detection
 */
function trackPageView() {
    const path = window.location.pathname;
    ahaDetectionState.pageViews[path] = (ahaDetectionState.pageViews[path] || 0) + 1;
    
    // Detect exploration patterns
    const uniquePages = Object.keys(ahaDetectionState.pageViews).length;
    if (uniquePages >= 5) {
        console.log('🎯 User exploring multiple features!');
        // Could trigger a general "power user" aha moment
    }
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAhaMomentDetection);
} else {
    initAhaMomentDetection();
}

// Track page views
trackPageView();
window.addEventListener('popstate', trackPageView);
