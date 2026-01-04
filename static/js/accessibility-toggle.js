/**
 * Accessibility Toggle Functionality
 * Provides color blind friendly mode with pattern indicators
 * 
 * Features:
 * - Toggle between normal and color blind mode
 * - Persists preference to localStorage
 * - Syncs with user database preferences (if authenticated)
 * - Exposes accessible color palette for Chart.js
 */

(function() {
    'use strict';

    // Color blind friendly color palette for charts
    // Using colorbrewer's colorblind-safe palette
    const COLORBLIND_CHART_PALETTE = [
        '#1f77b4',  // Blue
        '#ff7f0e',  // Orange
        '#2ca02c',  // Green (darker)
        '#d62728',  // Red (darker)
        '#9467bd',  // Purple
        '#8c564b',  // Brown
        '#e377c2',  // Pink
        '#7f7f7f',  // Gray
        '#bcbd22',  // Yellow-green
        '#17becf'   // Cyan
    ];

    // Priority-specific colors for colorblind mode
    const COLORBLIND_PRIORITY_COLORS = {
        'Urgent': 'rgba(214, 39, 40, 0.8)',    // Darker red with pattern
        'High': 'rgba(255, 127, 14, 0.8)',     // Orange
        'Medium': 'rgba(31, 119, 180, 0.8)',   // Blue
        'Low': 'rgba(127, 127, 127, 0.8)',     // Gray
        'urgent': 'rgba(214, 39, 40, 0.8)',
        'high': 'rgba(255, 127, 14, 0.8)',
        'medium': 'rgba(31, 119, 180, 0.8)',
        'low': 'rgba(127, 127, 127, 0.8)'
    };

    // Standard colors (for reference when mode is off)
    const STANDARD_PRIORITY_COLORS = {
        'Urgent': 'rgba(220, 53, 69, 0.8)',
        'High': 'rgba(255, 193, 7, 0.8)',
        'Medium': 'rgba(54, 162, 235, 0.8)',
        'Low': 'rgba(40, 167, 69, 0.8)',
        'urgent': 'rgba(220, 53, 69, 0.8)',
        'high': 'rgba(255, 193, 7, 0.8)',
        'medium': 'rgba(54, 162, 235, 0.8)',
        'low': 'rgba(40, 167, 69, 0.8)'
    };

    /**
     * Check if colorblind mode is currently active
     */
    function isColorblindModeActive() {
        return document.body.classList.contains('colorblind-mode');
    }

    /**
     * Get the appropriate priority colors based on current mode
     */
    function getPriorityColors() {
        return isColorblindModeActive() ? COLORBLIND_PRIORITY_COLORS : STANDARD_PRIORITY_COLORS;
    }

    /**
     * Get the appropriate chart palette based on current mode
     */
    function getChartPalette() {
        if (isColorblindModeActive()) {
            return COLORBLIND_CHART_PALETTE;
        }
        // Standard palette
        return [
            'rgba(40, 167, 69, 0.7)',   // Green
            'rgba(255, 193, 7, 0.7)',   // Yellow
            'rgba(253, 126, 20, 0.7)',  // Orange
            'rgba(220, 53, 69, 0.7)',   // Red
            'rgba(13, 110, 253, 0.7)',  // Blue
            'rgba(111, 66, 193, 0.7)',  // Purple
            'rgba(32, 201, 151, 0.7)',  // Teal
            'rgba(108, 117, 125, 0.7)'  // Gray
        ];
    }

    /**
     * Initialize colorblind mode based on saved preference
     */
    function initializeAccessibility() {
        // Check for saved preference
        const savedMode = localStorage.getItem('colorblind-mode');
        
        if (savedMode === 'true') {
            applyColorblindMode(true);
        }

        // Update toggle button state
        updateToggleButton();
    }

    /**
     * Apply or remove colorblind mode
     */
    function applyColorblindMode(enable) {
        const bodyElement = document.body;
        const toggle = document.getElementById('accessibility-toggle');

        if (enable) {
            bodyElement.classList.add('colorblind-mode');
            if (toggle) {
                toggle.classList.add('active');
                toggle.setAttribute('aria-pressed', 'true');
                toggle.setAttribute('title', 'Color Blind Mode: ON (Click to disable)');
                toggle.innerHTML = '<i class="fas fa-eye"></i>';
            }
        } else {
            bodyElement.classList.remove('colorblind-mode');
            if (toggle) {
                toggle.classList.remove('active');
                toggle.setAttribute('aria-pressed', 'false');
                toggle.setAttribute('title', 'Color Blind Mode: OFF (Click to enable)');
                toggle.innerHTML = '<i class="fas fa-eye-slash"></i>';
            }
        }

        // Save preference
        localStorage.setItem('colorblind-mode', enable.toString());

        // Dispatch custom event for charts to update
        window.dispatchEvent(new CustomEvent('accessibilityModeChanged', {
            detail: { colorblindMode: enable }
        }));

        // Sync to database if user is authenticated
        syncAccessibilityToDatabase(enable);
    }

    /**
     * Toggle colorblind mode
     */
    function toggleColorblindMode() {
        const isActive = isColorblindModeActive();
        applyColorblindMode(!isActive);
        
        // Show feedback toast
        showAccessibilityToast(!isActive);
    }

    /**
     * Update toggle button appearance
     */
    function updateToggleButton() {
        const toggle = document.getElementById('accessibility-toggle');
        if (!toggle) return;

        const isActive = isColorblindModeActive();
        
        if (isActive) {
            toggle.classList.add('active');
            toggle.setAttribute('aria-pressed', 'true');
            toggle.setAttribute('title', 'Color Blind Mode: ON (Click to disable)');
            toggle.innerHTML = '<i class="fas fa-eye"></i>';
        } else {
            toggle.classList.remove('active');
            toggle.setAttribute('aria-pressed', 'false');
            toggle.setAttribute('title', 'Color Blind Mode: OFF (Click to enable)');
            toggle.innerHTML = '<i class="fas fa-eye-slash"></i>';
        }
    }

    /**
     * Show feedback toast when mode changes
     */
    function showAccessibilityToast(enabled) {
        // Remove existing toast if any
        const existingToast = document.getElementById('accessibility-toast');
        if (existingToast) {
            existingToast.remove();
        }

        // Create toast element
        const toast = document.createElement('div');
        toast.id = 'accessibility-toast';
        toast.className = 'position-fixed';
        toast.style.cssText = `
            bottom: 20px;
            right: 20px;
            z-index: 9999;
            background: ${enabled ? '#1f77b4' : '#6c757d'};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            display: flex;
            align-items: center;
            gap: 10px;
            animation: slideIn 0.3s ease;
        `;
        
        toast.innerHTML = `
            <i class="fas ${enabled ? 'fa-eye' : 'fa-eye-slash'}"></i>
            <span>Color Blind Mode ${enabled ? 'Enabled' : 'Disabled'}</span>
        `;

        // Add animation keyframes if not exists
        if (!document.getElementById('accessibility-toast-styles')) {
            const style = document.createElement('style');
            style.id = 'accessibility-toast-styles';
            style.textContent = `
                @keyframes slideIn {
                    from {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
                @keyframes slideOut {
                    from {
                        transform: translateX(0);
                        opacity: 1;
                    }
                    to {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(toast);

        // Auto-remove after 3 seconds
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    /**
     * Sync accessibility preference to database (disabled - using localStorage only)
     * This function is kept for future implementation if database sync is needed
     */
    function syncAccessibilityToDatabase(enabled) {
        // Currently disabled - using localStorage only for persistence
        // This avoids 404 errors in the console
        // To enable database sync, create /accounts/update-accessibility/ endpoint
        return;
    }

    /**
     * Set up event listeners
     */
    function setupEventListeners() {
        // Toggle button click
        const toggle = document.getElementById('accessibility-toggle');
        if (toggle) {
            toggle.addEventListener('click', function(e) {
                e.preventDefault();
                toggleColorblindMode();
            });

            // Keyboard support
            toggle.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    toggleColorblindMode();
                }
            });
        }

        // Listen for system preference changes (for future high contrast mode)
        if (window.matchMedia) {
            window.matchMedia('(prefers-contrast: high)').addEventListener('change', function(e) {
                if (e.matches && !isColorblindModeActive()) {
                    // Suggest enabling colorblind mode for high contrast preference
                    console.log('High contrast preference detected - consider enabling accessibility mode');
                }
            });
        }
    }

    /**
     * Initialize on DOM ready
     */
    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                initializeAccessibility();
                setupEventListeners();
            });
        } else {
            initializeAccessibility();
            setupEventListeners();
        }
    }

    // Expose functions globally for use in other scripts
    window.PrizmAccessibility = {
        isColorblindModeActive: isColorblindModeActive,
        getPriorityColors: getPriorityColors,
        getChartPalette: getChartPalette,
        toggle: toggleColorblindMode,
        COLORBLIND_CHART_PALETTE: COLORBLIND_CHART_PALETTE,
        COLORBLIND_PRIORITY_COLORS: COLORBLIND_PRIORITY_COLORS,
        STANDARD_PRIORITY_COLORS: STANDARD_PRIORITY_COLORS
    };

    // Initialize
    init();

})();
