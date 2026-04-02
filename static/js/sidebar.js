/**
 * PrizmAI Sidebar — Toggle, collapse, mobile drawer logic
 * Uses direct inline styles for layout to avoid CSS caching / specificity issues.
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'prizmSidebarCollapsed';
    var EXPANDED_W = '220px';
    var COLLAPSED_W = '60px';

    function applyLayout(collapsed) {
        var w = collapsed ? COLLAPSED_W : EXPANDED_W;
        var appShell = document.getElementById('appShell');
        var sidebar = document.getElementById('prizmSidebar');
        var topbar = document.querySelector('.prizm-topbar');

        // Single padding-left on the shell pushes all normal-flow children
        if (appShell) appShell.style.setProperty('padding-left', w, 'important');
        if (sidebar) sidebar.style.setProperty('width', w, 'important');
        if (topbar) topbar.style.setProperty('left', w, 'important');

        // Remove the init style tag injected by pre-paint script
        var initStyle = document.getElementById('sidebar-layout-init');
        if (initStyle) initStyle.remove();
    }

    function init() {
        var sidebar = document.getElementById('prizmSidebar');
        var appShell = document.getElementById('appShell');
        var toggleBtn = document.getElementById('sidebarToggleBtn');
        var mobileToggle = document.getElementById('mobileMenuToggle');
        var overlay = document.getElementById('sidebarOverlay');
        var moreToggle = document.getElementById('sidebarMoreToggle');
        var moreList = document.getElementById('sidebarMoreList');

        if (!sidebar || !appShell) return;

        // Restore collapsed state from localStorage
        var isCollapsed = localStorage.getItem(STORAGE_KEY) === 'true';
        if (isCollapsed) {
            sidebar.classList.add('collapsed');
            appShell.classList.add('sidebar-collapsed');
        } else {
            sidebar.classList.remove('collapsed');
            appShell.classList.remove('sidebar-collapsed');
        }

        // Apply layout with direct inline styles
        applyLayout(isCollapsed);

        // Remove the pre-paint class now that JS has hydrated
        document.documentElement.classList.remove('sidebar-pre-collapsed');

        // Desktop: toggle collapse
        if (toggleBtn) {
            toggleBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                var collapsed = sidebar.classList.toggle('collapsed');
                appShell.classList.toggle('sidebar-collapsed', collapsed);
                localStorage.setItem(STORAGE_KEY, collapsed);
                toggleBtn.title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
                applyLayout(collapsed);
            });
        }

        // Mobile: open sidebar as drawer
        if (mobileToggle) {
            mobileToggle.addEventListener('click', function () {
                sidebar.classList.add('mobile-open');
                if (overlay) overlay.classList.add('show');
                document.body.style.overflow = 'hidden';
            });
        }

        // Close mobile drawer on overlay click
        if (overlay) {
            overlay.addEventListener('click', function () {
                closeMobileDrawer(sidebar, overlay);
            });
        }

        // Close mobile drawer on Escape
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && sidebar.classList.contains('mobile-open')) {
                closeMobileDrawer(sidebar, overlay);
            }
        });

        // "More" section toggle
        if (moreToggle && moreList) {
            moreToggle.addEventListener('click', function () {
                var expanded = moreList.classList.toggle('show');
                moreToggle.setAttribute('aria-expanded', expanded);
            });
        }

        // Workspace Switcher dropdown toggle
        var wsToggle = document.getElementById('wsDropdownToggle');
        var wsMenu = document.getElementById('wsDropdownMenu');
        if (wsToggle && wsMenu) {
            wsToggle.addEventListener('click', function (e) {
                e.stopPropagation();
                var open = wsMenu.style.display !== 'block';
                wsMenu.style.display = open ? 'block' : 'none';
                wsToggle.setAttribute('aria-expanded', open);
            });
            // Close on outside click
            document.addEventListener('click', function (e) {
                if (!wsMenu.contains(e.target) && !wsToggle.contains(e.target)) {
                    wsMenu.style.display = 'none';
                    wsToggle.setAttribute('aria-expanded', 'false');
                }
            });
            // Close on Escape
            document.addEventListener('keydown', function (e) {
                if (e.key === 'Escape' && wsMenu.style.display === 'block') {
                    wsMenu.style.display = 'none';
                    wsToggle.setAttribute('aria-expanded', 'false');
                    wsToggle.focus();
                }
            });
        }
        }
    }

    function closeMobileDrawer(sidebar, overlay) {
        sidebar.classList.remove('mobile-open');
        if (overlay) overlay.classList.remove('show');
        document.body.style.overflow = '';
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
