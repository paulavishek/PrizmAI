/**
 * chart-theme.js — one shared source of truth for Chart.js (canvas) colors.
 *
 * Why this file exists:
 *   Chart.js draws on a <canvas>, so it NEVER responds to CSS variables or the
 *   data-bs-theme attribute. Every chart has to be told its colors explicitly
 *   in JS. Historically each page hand-rolled that (and most hardcoded
 *   light-mode greys), so charts were unreadable in dark mode. This centralizes
 *   it: every chart pulls axis/grid/title/legend colors from getChartTheme(),
 *   and registered charts re-color automatically when the theme is toggled.
 *
 * Color values here MIRROR the --chart-title-color token in css/theme.css and
 * the axis/grid values already used by the dashboard charts. Keep them in sync.
 *
 * Chart.js version note: the app ships a single bundled Chart.js v4.4.2
 * (static/js/chart.umd.min.js) on every page. To stay version-agnostic we do
 * NOT walk any Chart internal registry — charts opt in via
 * PrizmCharts.register(chart), so this works regardless of Chart.js version.
 */
(function () {
    'use strict';

    function isDark() {
        return document.documentElement.getAttribute('data-bs-theme') === 'dark';
    }

    /**
     * Theme palette for canvas chart chrome (NOT dataset/series colors — those
     * stay as the brand/data palette). Read this at chart-build time.
     * @returns {{isDark:boolean, textColor:string, gridColor:string, titleColor:string}}
     */
    window.getChartTheme = function getChartTheme() {
        var dark = isDark();
        return {
            isDark: dark,
            textColor:  dark ? '#c7ccdd' : '#444',                 // axis/tick/legend labels
            gridColor:  dark ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.05)',
            titleColor: dark ? '#8fb3ff' : '#1a3d7c'               // mirrors --chart-title-color
        };
    };

    // ── Chart registry + re-color-on-toggle ────────────────────────────────
    var registered = [];

    /**
     * Walk the standard Chart.js option slots and recolor the theme-driven
     * chrome (axis ticks, gridlines, axis titles, legend labels, chart title).
     * Leaves dataset colors untouched. Safe on any Chart.js v3/v4 config shape.
     */
    function applyThemeToChart(chart) {
        if (!chart || !chart.options) return;
        var t = window.getChartTheme();
        var o = chart.options;

        // Scales (v3/v4 both use options.scales as an object keyed by axis id)
        if (o.scales) {
            Object.keys(o.scales).forEach(function (key) {
                var sc = o.scales[key];
                if (!sc) return;
                if (sc.ticks)  sc.ticks.color = t.textColor;
                if (sc.grid)   sc.grid.color = t.gridColor;
                if (sc.title && sc.title.display) sc.title.color = t.titleColor;
            });
        }

        // Plugins: legend labels + chart title
        var p = o.plugins || {};
        if (p.legend && p.legend.labels) p.legend.labels.color = t.textColor;
        if (p.title && p.title.display)  p.title.color = t.titleColor;
    }

    /**
     * Apply theme-aware Chart.js GLOBAL defaults. This themes axis ticks,
     * legend labels, gridlines and title fallback for EVERY chart that doesn't
     * explicitly override them — no per-chart edits needed. Charts that do set
     * their own colors keep them. Safe no-op if Chart isn't loaded yet.
     */
    function applyChartDefaults() {
        if (typeof window.Chart === 'undefined') return;
        var t = window.getChartTheme();
        var C = window.Chart.defaults;
        C.color = t.textColor;                 // ticks + legend labels inherit this
        C.borderColor = t.gridColor;           // element/grid border fallback
        if (C.scale && C.scale.grid) C.scale.grid.color = t.gridColor;
        if (C.plugins) {
            if (C.plugins.legend && C.plugins.legend.labels) C.plugins.legend.labels.color = t.textColor;
            if (C.plugins.title) C.plugins.title.color = t.titleColor;
        }
    }
    // Chart.js is loaded per-page (in the body, before the page's chart script).
    // Apply defaults once the DOM is ready — this runs before page chart scripts'
    // own DOMContentLoaded handlers because this file is included earlier.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyChartDefaults);
    } else {
        applyChartDefaults();
    }

    window.PrizmCharts = {
        applyDefaults: applyChartDefaults,
        /**
         * Register a chart so it recolors when the display mode toggles.
         * Call this right after `new Chart(...)`. Returns the chart for chaining.
         */
        register: function (chart) {
            if (chart) registered.push(chart);
            return chart;
        },
        getTheme: window.getChartTheme,
        applyTheme: applyThemeToChart,
        _registered: registered
    };

    // Recolor all live registered charts when the user switches light/dark.
    // display-mode.js dispatches this on every mode change (see applyMode()).
    window.addEventListener('displayModeChanged', function () {
        applyChartDefaults();   // so any chart re-rendered later picks up the new theme
        for (var i = registered.length - 1; i >= 0; i--) {
            var chart = registered[i];
            // Drop destroyed charts (Chart.js nulls .ctx / .canvas on destroy).
            if (!chart || (!chart.ctx && !chart.canvas)) {
                registered.splice(i, 1);
                continue;
            }
            try {
                applyThemeToChart(chart);
                chart.update('none');   // 'none' = recolor without re-animating
            } catch (e) {
                registered.splice(i, 1);   // stale/broken instance — forget it
            }
        }
    });
})();
