/**
 * GA4 Demo Analytics Integration
 * 
 * Tracks demo mode limitations and conversion events for PrizmAI.
 * These events are designed for interview credibility - focusing on
 * behavioral signals rather than vanity metrics.
 * 
 * Key Events:
 * - limitation_encountered: When user hits a demo restriction
 * - demo_conversion_initiated: When user clicks upgrade
 * - demo_session_complete: Session summary on exit
 * - feature_first_use: First interaction with key features
 * - demo_engagement: Engagement quality metrics
 */

(function() {
    'use strict';

    // Demo Analytics namespace
    window.DemoAnalytics = window.DemoAnalytics || {};

    /**
     * Track when user encounters a demo limitation
     * @param {string} limitationType - 'project_limit', 'export_blocked', 'ai_limit', 'time_expired'
     * @param {object} context - Additional context data
     */
    DemoAnalytics.trackLimitationEncountered = function(limitationType, context = {}) {
        const eventData = {
            'limitation_type': limitationType,
            'demo_duration_minutes': context.duration || getDemoSessionDuration(),
            'projects_created': context.projects || getSessionValue('demo_projects_created', 0),
            'tasks_created': context.tasks || getSessionValue('demo_tasks_created', 0),
            'ai_uses': context.ai_uses || getSessionValue('demo_ai_uses', 0),
            'features_explored': context.features || getSessionValue('demo_features_count', 0)
        };

        // Send to GA4
        if (typeof gtag !== 'undefined') {
            gtag('event', 'limitation_encountered', eventData);
            console.log('📊 GA4: limitation_encountered', eventData);
        }

        // Also track server-side
        trackServerEvent('limitation_encountered', eventData);
    };

    /**
     * Track when user initiates conversion (clicks upgrade/signup)
     * @param {string} source - Where the conversion was initiated from
     */
    DemoAnalytics.trackConversionInitiated = function(source) {
        const eventData = {
            'conversion_source': source,
            'demo_duration_minutes': getDemoSessionDuration(),
            'projects_created': getSessionValue('demo_projects_created', 0),
            'tasks_created': getSessionValue('demo_tasks_created', 0),
            'limitations_hit': getSessionValue('demo_limitations_hit', []).join(','),
            'features_explored': getSessionValue('demo_features_count', 0)
        };

        if (typeof gtag !== 'undefined') {
            gtag('event', 'demo_conversion_initiated', eventData);
            console.log('📊 GA4: demo_conversion_initiated', eventData);
        }

        trackServerEvent('conversion_initiated', eventData);
    };

    /**
     * Track first use of a key feature
     * @param {string} featureName - Name of the feature
     */
    DemoAnalytics.trackFeatureFirstUse = function(featureName) {
        const trackedFeatures = getSessionValue('demo_tracked_features', []);
        
        // Only track first use
        if (trackedFeatures.includes(featureName)) {
            return;
        }

        // Mark as tracked
        trackedFeatures.push(featureName);
        setSessionValue('demo_tracked_features', trackedFeatures);

        const eventData = {
            'feature_name': featureName,
            'time_to_first_use_seconds': getDemoSessionDuration() * 60,
            'features_explored_count': trackedFeatures.length
        };

        if (typeof gtag !== 'undefined') {
            gtag('event', 'feature_first_use', eventData);
            console.log('📊 GA4: feature_first_use', eventData);
        }

        trackServerEvent('feature_first_use', eventData);
    };

    /**
     * Track demo session completion/quality
     * Called when user exits demo or session expires
     */
    DemoAnalytics.trackSessionComplete = function() {
        const eventData = {
            'duration_minutes': getDemoSessionDuration(),
            'projects_created': getSessionValue('demo_projects_created', 0),
            'tasks_created': getSessionValue('demo_tasks_created', 0),
            'ai_uses': getSessionValue('demo_ai_uses', 0),
            'features_explored': getSessionValue('demo_features_count', 0),
            'limitations_hit': getSessionValue('demo_limitations_hit', []).length,
            'quality_score': calculateEngagementQuality()
        };

        if (typeof gtag !== 'undefined') {
            gtag('event', 'demo_session_complete', eventData);
            console.log('📊 GA4: demo_session_complete', eventData);
        }

        trackServerEvent('session_complete', eventData);
    };

    /**
     * Track demo engagement quality
     * Called periodically or on key interactions
     */
    DemoAnalytics.trackEngagement = function() {
        const eventData = {
            'projects_created': getSessionValue('demo_projects_created', 0),
            'tasks_created': getSessionValue('demo_tasks_created', 0),
            'ai_generations_used': getSessionValue('demo_ai_uses', 0),
            'session_duration_minutes': getDemoSessionDuration(),
            'feature_exploration_breadth': getSessionValue('demo_tracked_features', []).length
        };

        if (typeof gtag !== 'undefined') {
            gtag('event', 'demo_engagement', eventData);
        }

        // No server tracking for periodic engagement - too noisy
    };

    /**
     * Track power user actions that indicate deep engagement
     * @param {string} actionType - Type of power user action
     */
    DemoAnalytics.trackPowerUserAction = function(actionType) {
        const eventData = {
            'action_type': actionType,
            'session_count': 1, // Could track across sessions with cookies
            'time_in_session_minutes': getDemoSessionDuration()
        };

        if (typeof gtag !== 'undefined') {
            gtag('event', 'power_user_action', eventData);
        }

        trackServerEvent('power_user_action', eventData);
    };

    /**
     * Track potential workaround attempts
     * Called when user tries to game the limitation system
     * @param {string} workaroundType - Type of workaround attempted
     * @param {object} context - Additional context data
     */
    DemoAnalytics.trackWorkaroundAttempt = function(workaroundType, context = {}) {
        const eventData = {
            'workaround_type': workaroundType,
            'boards_remaining': context.boards_remaining || 0,
            'total_created': context.total_created || 0,
            'success': context.success || false,
            'time_in_session_minutes': getDemoSessionDuration()
        };

        // Send to GA4
        if (typeof gtag !== 'undefined') {
            gtag('event', 'workaround_attempt', eventData);
            console.log('📊 GA4: workaround_attempt', eventData);
        }

        trackServerEvent('workaround_attempt', eventData);
    };

    /**
     * Track traffic source quality
     * Called on demo start
     */
    DemoAnalytics.trackSourceQuality = function() {
        const urlParams = new URLSearchParams(window.location.search);
        const utmSource = urlParams.get('utm_source') || 'direct';
        
        const eventData = {
            'utm_source': utmSource,
            'utm_medium': urlParams.get('utm_medium') || '',
            'utm_campaign': urlParams.get('utm_campaign') || '',
            'referrer': document.referrer || 'direct'
        };

        if (typeof gtag !== 'undefined') {
            gtag('event', 'demo_source', eventData);
        }

        trackServerEvent('demo_source', eventData);
    };

    // =====================
    // Helper Functions
    // =====================

    function getDemoSessionDuration() {
        const startTime = getSessionValue('demo_start_time');
        if (!startTime) return 0;
        
        const now = Date.now();
        const durationMs = now - startTime;
        return Math.round(durationMs / 60000); // Convert to minutes
    }

    function calculateEngagementQuality() {
        // Score 0-10 based on engagement signals
        let score = 0;
        
        const duration = getDemoSessionDuration();
        const projects = getSessionValue('demo_projects_created', 0);
        const tasks = getSessionValue('demo_tasks_created', 0);
        const aiUses = getSessionValue('demo_ai_uses', 0);
        const features = getSessionValue('demo_tracked_features', []).length;
        
        // Duration scoring (0-3)
        if (duration >= 15) score += 3;
        else if (duration >= 10) score += 2;
        else if (duration >= 5) score += 1;
        
        // Activity scoring (0-3)
        if (projects >= 2) score += 2;
        else if (projects >= 1) score += 1;
        if (tasks >= 3) score += 1;
        
        // AI usage scoring (0-2)
        if (aiUses >= 5) score += 2;
        else if (aiUses >= 1) score += 1;
        
        // Feature exploration (0-2)
        if (features >= 5) score += 2;
        else if (features >= 3) score += 1;
        
        return Math.min(10, score);
    }

    function getSessionValue(key, defaultValue = null) {
        try {
            const value = sessionStorage.getItem(key);
            if (value === null) return defaultValue;
            return JSON.parse(value);
        } catch (e) {
            return defaultValue;
        }
    }

    function setSessionValue(key, value) {
        try {
            sessionStorage.setItem(key, JSON.stringify(value));
        } catch (e) {
            console.error('Session storage error:', e);
        }
    }

    function trackServerEvent(eventType, eventData) {
        fetch('/demo/track-event/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({
                event_type: eventType,
                event_data: eventData
            })
        }).catch(e => console.error('Server tracking error:', e));
    }

    function getCsrfToken() {
        const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    }

    // =====================
    // Auto-initialization
    // =====================

    document.addEventListener('DOMContentLoaded', function() {
        // Check if in demo mode
        const isDemoMode = document.body.classList.contains('demo-mode') || 
                          document.querySelector('.demo-mode-banner');
        
        if (!isDemoMode) return;

        console.log('📊 Demo Analytics initialized');

        // Record demo start time if not set
        if (!getSessionValue('demo_start_time')) {
            setSessionValue('demo_start_time', Date.now());
            DemoAnalytics.trackSourceQuality();
        }

        // Track engagement periodically (every 2 minutes)
        setInterval(function() {
            DemoAnalytics.trackEngagement();
        }, 120000);

        // Track session complete on page unload
        window.addEventListener('beforeunload', function() {
            DemoAnalytics.trackSessionComplete();
        });
    });

})();
