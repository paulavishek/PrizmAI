// Theme Toggle Functionality
(function() {
    'use strict';

    // Initialize theme on page load
    function initializeTheme() {
        // Check for saved theme preference or default to system preference
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = savedTheme || (prefersDark ? 'dark' : 'light');

        applyTheme(theme);
    }

    // Apply theme to the document
    function applyTheme(theme) {
        const htmlElement = document.documentElement;
        const bodyElement = document.body;
        const themeToggle = document.getElementById('theme-toggle');

        if (theme === 'dark') {
            bodyElement.classList.add('dark-mode');
            if (themeToggle) {
                themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
                themeToggle.title = 'Switch to Light Mode';
                themeToggle.setAttribute('aria-label', 'Switch to Light Mode');
            }
        } else {
            bodyElement.classList.remove('dark-mode');
            if (themeToggle) {
                themeToggle.innerHTML = '<i class="fas fa-moon"></i>';
                themeToggle.title = 'Switch to Dark Mode';
                themeToggle.setAttribute('aria-label', 'Switch to Dark Mode');
            }
        }

        localStorage.setItem('theme', theme);
    }

    // Toggle theme function
    function toggleTheme() {
        const currentTheme = localStorage.getItem('theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        applyTheme(newTheme);
    }

    // Listen for system theme changes
    function listenForSystemThemeChanges() {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', (e) => {
            // Only apply system preference if user hasn't set a preference
            if (!localStorage.getItem('theme')) {
                applyTheme(e.matches ? 'dark' : 'light');
            }
        });
    }

    // Expose toggle function globally
    window.toggleTheme = toggleTheme;

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initializeTheme();
            listenForSystemThemeChanges();

            // Add click listener to toggle button
            const themeToggle = document.getElementById('theme-toggle');
            if (themeToggle) {
                themeToggle.addEventListener('click', toggleTheme);
            }
        });
    } else {
        initializeTheme();
        listenForSystemThemeChanges();

        // Add click listener to toggle button
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', toggleTheme);
        }
    }
})();
