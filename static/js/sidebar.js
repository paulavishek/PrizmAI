/**
 * PrizmAI Sidebar — Toggle, collapse, mobile drawer logic
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'prizmSidebarCollapsed';

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
        }
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
