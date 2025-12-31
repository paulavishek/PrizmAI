/**
 * Conversion Nudge System
 * Detects optimal timing and displays conversion nudges based on user behavior
 * Integrates with aha moment detection and session state
 */

// Nudge state
const nudgeState = {
    initialized: false,
    currentNudge: null,
    nudgesShown: [],
    nudgesDismissed: {},
    checkInterval: null,
    exitIntentBound: false,
    isMobile: /iPhone|iPad|iPod|Android/i.test(navigator.userAgent),
};

/**
 * Initialize nudge system
 */
function initNudgeSystem() {
    if (nudgeState.initialized) return;
    
    console.log('💡 Initializing conversion nudge system...');
    
    // Load state from session storage
    loadNudgeState();
    
    // Start periodic checks for time-based nudges
    startNudgeChecks();
    
    // Set up exit intent detection (desktop only)
    if (!nudgeState.isMobile) {
        setupExitIntentDetection();
    }
    
    // Set up event listeners for all nudges
    setupNudgeEventListeners();
    
    nudgeState.initialized = true;
    console.log('✅ Nudge system initialized');
}

/**
 * Load nudge state from session storage
 */
function loadNudgeState() {
    try {
        const stored = sessionStorage.getItem('nudgeState');
        if (stored) {
            const state = JSON.parse(stored);
            nudgeState.nudgesShown = state.nudgesShown || [];
            nudgeState.nudgesDismissed = state.nudgesDismissed || {};
        }
    } catch (e) {
        console.error('Error loading nudge state:', e);
    }
}

/**
 * Save nudge state to session storage
 */
function saveNudgeState() {
    try {
        const state = {
            nudgesShown: nudgeState.nudgesShown,
            nudgesDismissed: nudgeState.nudgesDismissed,
        };
        sessionStorage.setItem('nudgeState', JSON.stringify(state));
    } catch (e) {
        console.error('Error saving nudge state:', e);
    }
}

/**
 * Start periodic checks for time-based nudges
 */
function startNudgeChecks() {
    // Check every 15 seconds for time-based triggers (was 30 seconds)
    nudgeState.checkInterval = setInterval(() => {
        checkForNudges();
    }, 15000); // 15 seconds
    
    // Also check immediately after a short delay
    setTimeout(() => checkForNudges(), 3000); // After 3 seconds on page
}

/**
 * Check if any nudge should be shown now
 */
async function checkForNudges() {
    // Don't check if nudge is currently visible
    if (nudgeState.currentNudge) return;
    
    try {
        // Call server to check what nudge should show
        const response = await fetch('/demo/check-nudge/', {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin',
        });
        
        if (!response.ok) return;
        
        const data = await response.json();
        
        if (data.show_nudge && data.nudge_type) {
            showNudge(data.nudge_type, data.context);
        }
    } catch (e) {
        console.error('Error checking for nudges:', e);
    }
}

/**
 * Set up exit intent detection (desktop only)
 */
function setupExitIntentDetection() {
    if (nudgeState.exitIntentBound) return;
    
    let lastY = 0;
    let exitShown = false;
    
    document.addEventListener('mousemove', (e) => {
        const y = e.clientY;
        
        // Detect mouse moving towards top of screen
        if (y < 10 && lastY > 10 && !exitShown) {
            // Check if exit intent nudge should show
            checkExitIntentNudge();
            exitShown = true; // Only trigger once per page load
        }
        
        lastY = y;
    });
    
    nudgeState.exitIntentBound = true;
}

/**
 * Check if exit intent nudge should be shown
 */
async function checkExitIntentNudge() {
    // Don't show if already showing a nudge
    if (nudgeState.currentNudge) return;
    
    // Check if exit intent already shown
    if (nudgeState.nudgesShown.includes('exit_intent')) return;
    
    try {
        const response = await fetch('/demo/check-nudge/?type=exit_intent', {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin',
        });
        
        if (!response.ok) return;
        
        const data = await response.json();
        
        if (data.show_nudge) {
            showNudge('exit_intent', data.context);
        }
    } catch (e) {
        console.error('Error checking exit intent:', e);
    }
}

/**
 * Show a specific nudge
 */
function showNudge(nudgeType, context = {}) {
    console.log(`📢 Showing ${nudgeType} nudge`);
    
    // Don't show if frequency cap reached
    if (nudgeState.nudgesShown.length >= 3) {
        console.log('⚠️ Frequency cap reached (3 nudges max)');
        return;
    }
    
    // Don't show if already shown
    if (nudgeState.nudgesShown.includes(nudgeType)) {
        console.log(`⚠️ ${nudgeType} already shown`);
        return;
    }
    
    // Get nudge element
    const nudgeElement = document.getElementById(`${nudgeType}-nudge`);
    if (!nudgeElement) {
        console.error(`Nudge element not found: ${nudgeType}-nudge`);
        return;
    }
    
    // Update context if needed
    updateNudgeContext(nudgeElement, context);
    
    // Show nudge
    nudgeElement.style.display = '';
    nudgeState.currentNudge = nudgeType;
    
    // Track nudge shown
    trackNudgeEvent('shown', nudgeType);
    nudgeState.nudgesShown.push(nudgeType);
    saveNudgeState();
    
    // Auto-dismiss for soft nudge
    if (nudgeType === 'soft') {
        const autoDismissTime = nudgeState.isMobile ? 5000 : 10000;
        setTimeout(() => {
            if (nudgeState.currentNudge === 'soft') {
                dismissNudge(nudgeType, true);
            }
        }, autoDismissTime);
    }
}

/**
 * Update nudge content with context data
 */
function updateNudgeContext(nudgeElement, context) {
    // Update features count if present
    const featuresCount = nudgeElement.querySelector('.features-count');
    const featuresTried = nudgeElement.querySelector('#features-tried-text');
    const nudgeTitle = nudgeElement.querySelector('#medium-nudge-title');
    
    if (featuresCount && context.features_explored_count !== undefined) {
        const count = context.features_explored_count;
        featuresCount.textContent = count;
        
        // Update title text contextually for medium nudge
        if (nudgeTitle) {
            if (count === 0) {
                nudgeTitle.innerHTML = 'Enjoying the demo so far?';
            } else if (count === 1) {
                nudgeTitle.innerHTML = 'You\'ve explored <span class="features-count">' + count + '</span> feature!';
            } else {
                nudgeTitle.innerHTML = 'You\'ve explored <span class="features-count">' + count + '</span> features!';
            }
        }
        
        // Update "features tried" text contextually
        if (featuresTried) {
            if (count === 0) {
                featuresTried.textContent = 'All features available';
            } else if (count === 1) {
                featuresTried.textContent = 'The feature you tried + all others';
            } else {
                featuresTried.textContent = 'All ' + count + ' features you tried + more';
            }
        }
    }
    
    // Add any other dynamic context updates here
}

/**
 * Dismiss a nudge
 */
function dismissNudge(nudgeType, autoDismiss = false) {
    const nudgeElement = document.getElementById(`${nudgeType}-nudge`);
    if (!nudgeElement) return;
    
    // Add hiding animation
    nudgeElement.classList.add('nudge-hiding');
    
    // Hide after animation
    setTimeout(() => {
        nudgeElement.style.display = 'none';
        nudgeElement.classList.remove('nudge-hiding');
        nudgeState.currentNudge = null;
    }, 300);
    
    // Track dismissal if not auto-dismiss
    if (!autoDismiss) {
        trackNudgeEvent('dismissed', nudgeType);
        nudgeState.nudgesDismissed[nudgeType] = new Date().toISOString();
        saveNudgeState();
    }
}

/**
 * Set up event listeners for all nudges
 */
function setupNudgeEventListeners() {
    // Find all nudge elements
    const nudges = document.querySelectorAll('.demo-nudge');
    
    nudges.forEach(nudge => {
        const nudgeType = nudge.getAttribute('data-nudge-type');
        
        // Dismiss button clicks
        const dismissButtons = nudge.querySelectorAll('[data-action="dismiss"]');
        dismissButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                dismissNudge(nudgeType, false);
            });
        });
        
        // CTA button clicks
        const ctaButtons = nudge.querySelectorAll('[data-action="signup"]');
        ctaButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                trackNudgeEvent('clicked', nudgeType);
            });
        });
    });
}

/**
 * Track nudge event (shown, clicked, dismissed)
 */
async function trackNudgeEvent(eventType, nudgeType) {
    try {
        await fetch('/demo/track-nudge/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                event_type: eventType,
                nudge_type: nudgeType,
                timestamp: new Date().toISOString(),
            }),
        });
        
        console.log(`✅ Tracked nudge ${eventType}: ${nudgeType}`);
    } catch (e) {
        console.error('Error tracking nudge event:', e);
    }
}

/**
 * Show peak nudge after aha moment
 * Called by aha moment detection system
 */
function showPeakNudgeForAha(momentType) {
    console.log(`🎯 Aha moment detected: ${momentType}`);
    
    // Check if peak nudge already shown for this moment
    const peakNudgeId = `peak_${momentType}`;
    if (nudgeState.nudgesShown.includes(peakNudgeId)) {
        console.log('Peak nudge already shown for this aha moment');
        return;
    }
    
    // Wait a moment for aha celebration to show first
    setTimeout(() => {
        showNudge('peak', { aha_moment_type: momentType });
        
        // Mark as shown for this specific moment
        nudgeState.nudgesShown.push(peakNudgeId);
        saveNudgeState();
    }, 3000); // 3 seconds after aha
}

/**
 * Get CSRF token from cookie
 */
function getCsrfToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Clean up nudge system (called on page unload)
 */
function cleanupNudgeSystem() {
    if (nudgeState.checkInterval) {
        clearInterval(nudgeState.checkInterval);
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNudgeSystem);
} else {
    initNudgeSystem();
}

// Clean up on page unload
window.addEventListener('beforeunload', cleanupNudgeSystem);

// Export for use by other scripts
window.nudgeSystem = {
    showPeakNudgeForAha,
    showNudge,
    dismissNudge,
};
