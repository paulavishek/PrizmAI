/**
 * display-mode.js — Unified Display Mode System for PrizmAI
 *
 * Handles four exclusive modes:
 *   light        — default, always-light interface
 *   dark         — dark interface using Bootstrap 5 data-bs-theme + body.dark-mode
 *   auto         — follows the OS/browser prefers-color-scheme
 *   accessibility — colorblind-friendly palette (light base)
 *
 * The DB preference is already applied before first paint by the anti-flicker
 * inline script in base.html <head>. This file manages interactive switching,
 * topbar dropdown state, and AJAX persistence.
 *
 * Exposes window.PrizmDisplayMode for use by other modules (charts, etc.).
 * Also exposes window.AccessibilityMode for backward-compat with chart code
 * that previously used accessibility-toggle.js.
 */

(function () {
    'use strict';

    // ── Color palettes (preserved from accessibility-toggle.js) ──────────────

    var COLORBLIND_CHART_PALETTE = [
        '#1f77b4',  // Blue
        '#ff7f0e',  // Orange
        '#2ca02c',  // Green
        '#d62728',  // Red
        '#9467bd',  // Purple
        '#8c564b',  // Brown
        '#e377c2',  // Pink
        '#7f7f7f',  // Gray
        '#bcbd22',  // Yellow-green
        '#17becf',  // Cyan
    ];

    var STANDARD_CHART_PALETTE = [
        'rgba(40, 167, 69, 0.7)',
        'rgba(255, 193, 7, 0.7)',
        'rgba(253, 126, 20, 0.7)',
        'rgba(220, 53, 69, 0.7)',
        'rgba(13, 110, 253, 0.7)',
        'rgba(111, 66, 193, 0.7)',
        'rgba(32, 201, 151, 0.7)',
        'rgba(108, 117, 125, 0.7)',
    ];

    var COLORBLIND_PRIORITY_COLORS = {
        'Urgent': 'rgba(214, 39, 40, 0.8)',
        'High':   'rgba(255, 127, 14, 0.8)',
        'Medium': 'rgba(31, 119, 180, 0.8)',
        'Low':    'rgba(127, 127, 127, 0.8)',
        'urgent': 'rgba(214, 39, 40, 0.8)',
        'high':   'rgba(255, 127, 14, 0.8)',
        'medium': 'rgba(31, 119, 180, 0.8)',
        'low':    'rgba(127, 127, 127, 0.8)',
    };

    var STANDARD_PRIORITY_COLORS = {
        'Urgent': 'rgba(220, 53, 69, 0.8)',
        'High':   'rgba(255, 193, 7, 0.8)',
        'Medium': 'rgba(54, 162, 235, 0.8)',
        'Low':    'rgba(40, 167, 69, 0.8)',
        'urgent': 'rgba(220, 53, 69, 0.8)',
        'high':   'rgba(255, 193, 7, 0.8)',
        'medium': 'rgba(54, 162, 235, 0.8)',
        'low':    'rgba(40, 167, 69, 0.8)',
    };

    // ── Mode icons ────────────────────────────────────────────────────────────

    var MODE_ICON = {
        light:         'fas fa-sun',
        dark:          'fas fa-moon',
        auto:          'fas fa-desktop',
        accessibility: 'fas fa-eye',
    };

    // ── Core apply function ───────────────────────────────────────────────────

    /**
     * Apply a display mode to the document immediately.
     * @param {string} mode  one of: light | dark | auto | accessibility
     */
    function applyMode(mode) {
        var html  = document.documentElement;
        var body  = document.body;

        // Resolve 'auto' to actual light/dark
        var resolved = mode;
        if (mode === 'auto') {
            resolved = (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches)
                ? 'dark'
                : 'light';
        }

        // ── Toggle Bootstrap dark theme ──────────────────────────────────────
        if (resolved === 'dark') {
            html.setAttribute('data-bs-theme', 'dark');
        } else {
            html.setAttribute('data-bs-theme', 'light');
        }

        // ── Toggle custom CSS classes ────────────────────────────────────────
        if (resolved === 'dark') {
            body.classList.add('dark-mode');
            html.classList.add('prizm-dark-mode');
        } else {
            body.classList.remove('dark-mode');
            html.classList.remove('prizm-dark-mode');
        }

        if (mode === 'accessibility') {
            body.classList.add('colorblind-mode');
            html.classList.add('prizm-accessibility-mode');
        } else {
            body.classList.remove('colorblind-mode');
            html.classList.remove('prizm-accessibility-mode');
        }

        // ── Update topbar dropdown icon ──────────────────────────────────────
        var iconEl = document.getElementById('display-mode-icon');
        if (iconEl) {
            iconEl.className = MODE_ICON[mode] || 'fas fa-circle-half-stroke';
        }

        // ── Mark active item in dropdown ────────────────────────────────────
        document.querySelectorAll('.display-mode-option').forEach(function (btn) {
            if (btn.getAttribute('data-mode') === mode) {
                btn.classList.add('fw-bold');
                btn.setAttribute('aria-checked', 'true');
            } else {
                btn.classList.remove('fw-bold');
                btn.setAttribute('aria-checked', 'false');
            }
        });

        // ── Dispatch event so charts and other components can react ──────────
        window.dispatchEvent(new CustomEvent('displayModeChanged', {
            detail: { mode: mode, resolved: resolved }
        }));
        // Backward compat event from accessibility-toggle.js
        window.dispatchEvent(new CustomEvent('accessibilityModeChanged', {
            detail: { colorblindMode: (mode === 'accessibility') }
        }));

        // ── Persist to localStorage (snapshot, for non-auth fallback) ────────
        try { localStorage.setItem('prizmDisplayMode', mode); } catch (e) {}
    }

    // ── AJAX save ─────────────────────────────────────────────────────────────

    function getCsrfToken() {
        var name = 'csrftoken';
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var c = cookies[i].trim();
            if (c.indexOf(name + '=') === 0) {
                return decodeURIComponent(c.substring(name.length + 1));
            }
        }
        return '';
    }

    /**
     * Persist a mode choice to the database via AJAX.
     * @param {string} mode
     */
    function saveMode(mode) {
        fetch('/accounts/api/update-display-mode/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({ display_mode: mode }),
        }).catch(function (err) {
            console.warn('[display-mode] Could not save to DB:', err);
        });
    }

    // ── OS theme-change listener ──────────────────────────────────────────────

    var _autoMediaQuery = null;

    function listenForOsChanges(currentMode) {
        // Remove any previous listener
        if (_autoMediaQuery) {
            try { _autoMediaQuery.removeEventListener('change', _handleOsChange); } catch (e) {}
        }
        if (currentMode === 'auto' && window.matchMedia) {
            _autoMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            _autoMediaQuery.addEventListener('change', _handleOsChange);
        }
    }

    function _handleOsChange() {
        // Only re-apply if we're still in 'auto' mode
        try {
            if (localStorage.getItem('prizmDisplayMode') === 'auto') {
                applyMode('auto');
            }
        } catch (e) {}
    }

    // ── Initialise on page load ───────────────────────────────────────────────

    function init() {
        // DB preference is already baked into data-display-mode on <body>
        var dbMode = document.body && document.body.getAttribute('data-display-mode');
        var mode   = dbMode || 'light';

        // Apply (the <head> anti-flicker script already did the initial paint,
        // but we need to run applyMode() now to set all the class/icon state)
        applyMode(mode);
        listenForOsChanges(mode);

        // ── Wire topbar dropdown ──────────────────────────────────────────────
        document.querySelectorAll('.display-mode-option').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var chosen = btn.getAttribute('data-mode');
                applyMode(chosen);
                saveMode(chosen);
                listenForOsChanges(chosen);
                try { localStorage.setItem('prizmDisplayMode', chosen); } catch (e) {}

                // Close the Bootstrap dropdown
                var dropEl = document.getElementById('display-mode-dropdown');
                if (dropEl && window.bootstrap) {
                    var dd = window.bootstrap.Dropdown.getInstance(
                        dropEl.querySelector('[data-bs-toggle="dropdown"]')
                    );
                    if (dd) dd.hide();
                }

                // Show a brief toast
                showToast(chosen);
            });
        });
    }

    // ── Toast feedback ────────────────────────────────────────────────────────

    function showToast(mode) {
        var existing = document.getElementById('prizm-dm-toast');
        if (existing) existing.remove();

        var labels = {
            light:         'Light mode applied',
            dark:          'Dark mode applied',
            auto:          'Browser mode applied',
            accessibility: 'Accessibility mode applied',
        };

        var toast = document.createElement('div');
        toast.id = 'prizm-dm-toast';
        toast.style.cssText = [
            'position:fixed;bottom:20px;right:20px;z-index:9999;',
            'background:#0d6efd;color:#fff;padding:10px 18px;',
            'border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.15);',
            'display:flex;align-items:center;gap:8px;',
            'animation:prizm-slide-in .25s ease;',
        ].join('');
        toast.innerHTML = '<i class="' + (MODE_ICON[mode] || 'fas fa-check') + '"></i>'
                        + '<span>' + (labels[mode] || mode) + '</span>';

        // Inject keyframes once
        if (!document.getElementById('prizm-dm-keyframes')) {
            var style = document.createElement('style');
            style.id  = 'prizm-dm-keyframes';
            style.textContent = '@keyframes prizm-slide-in{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}';
            document.head.appendChild(style);
        }

        document.body.appendChild(toast);
        setTimeout(function () { if (toast.parentNode) toast.remove(); }, 2500);
    }

    // ── Public API ────────────────────────────────────────────────────────────

    var API = {
        applyMode: applyMode,
        saveMode:  saveMode,
        // Chart / priority helpers (backward compat with accessibility-toggle.js)
        isColorblindModeActive: function () {
            return document.body.classList.contains('colorblind-mode');
        },
        getChartPalette: function () {
            return API.isColorblindModeActive()
                ? COLORBLIND_CHART_PALETTE
                : STANDARD_CHART_PALETTE;
        },
        getPriorityColors: function () {
            return API.isColorblindModeActive()
                ? COLORBLIND_PRIORITY_COLORS
                : STANDARD_PRIORITY_COLORS;
        },
    };

    window.PrizmDisplayMode  = API;
    // Backward-compat alias so any existing code calling window.AccessibilityMode still works
    window.AccessibilityMode = API;

    // ── Boot ──────────────────────────────────────────────────────────────────

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
