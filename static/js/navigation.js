/**
 * PrizmAI Navigation Utilities
 * Provides consistent back navigation across the application
 */

(function() {
    'use strict';

    // Global navigation utility
    window.PrizmAI = window.PrizmAI || {};
    
    /**
     * Navigate to the previous page in browser history
     * Falls back to a specified URL if no history is available
     * @param {string} fallbackUrl - URL to navigate to if no history exists
     */
    window.PrizmAI.goBack = function(fallbackUrl) {
        // Get the fallback URL from the data attribute or parameter
        fallbackUrl = fallbackUrl || getDashboardUrl();
        
        // Check if there's a valid previous page in history
        if (document.referrer && 
            document.referrer !== window.location.href && 
            isSameDomain(document.referrer)) {
            window.history.back();
        } else {
            // Navigate to the fallback URL
            window.location.href = fallbackUrl;
        }
    };

    /**
     * Get the appropriate dashboard URL based on demo mode
     * @returns {string} Dashboard URL
     */
    function getDashboardUrl() {
        // Check for demo mode from multiple sources
        const isDemoMode = document.body.dataset.demoMode === 'true' || 
                          window.location.pathname.includes('/demo/') ||
                          document.querySelector('[data-demo-mode="true"]') !== null;
        
        if (isDemoMode) {
            return '/demo/';
        }
        return '/dashboard/';
    }

    /**
     * Check if a URL is from the same domain
     * @param {string} url - URL to check
     * @returns {boolean} True if same domain
     */
    function isSameDomain(url) {
        try {
            const referrerUrl = new URL(url);
            return referrerUrl.host === window.location.host;
        } catch (e) {
            return false;
        }
    }

    /**
     * Legacy goBack function for backwards compatibility
     * Uses history.back() with intelligent fallback
     */
    window.goBack = function() {
        // Try to find a fallback URL from a data attribute on the page
        const backBtn = document.querySelector('[data-fallback-url]');
        const fallbackUrl = backBtn ? backBtn.dataset.fallbackUrl : null;
        
        window.PrizmAI.goBack(fallbackUrl);
    };

    // Initialize back buttons with data-fallback-url on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        // Auto-attach click handlers to back buttons without onclick
        const backButtons = document.querySelectorAll('[data-action="go-back"]');
        backButtons.forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const fallbackUrl = this.dataset.fallbackUrl || null;
                window.PrizmAI.goBack(fallbackUrl);
            });
        });
    });

})();
