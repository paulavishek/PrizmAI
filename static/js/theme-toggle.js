// Theme Toggle Functionality
(function() {
    'use strict';

    // Initialize theme on page load
    function initializeTheme() {
        // Check for saved theme preference from database (passed from template)
        const dbTheme = document.body.getAttribute('data-user-theme');
        // Check localStorage or default to system preference
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        // Priority: database preference > localStorage > system preference
        let theme;
        if (dbTheme && dbTheme !== 'auto') {
            theme = dbTheme;
        } else if (dbTheme === 'auto') {
            theme = prefersDark ? 'dark' : 'light';
        } else if (savedTheme) {
            theme = savedTheme;
        } else {
            theme = prefersDark ? 'dark' : 'light';
        }

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
        
        // Sync with database if user is authenticated
        syncThemeToDatabase(newTheme);
    }
    
    // Sync theme preference to database
    function syncThemeToDatabase(theme) {
        fetch('/assistant/api/preferences/save/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ theme: theme })
        }).catch(error => console.error('Error syncing theme:', error));
    }
    
    // Get CSRF token from cookies
    function getCookie(name) {
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

    // Listen for system theme changes
    function listenForSystemThemeChanges() {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', (e) => {
            // Only apply system preference if user has "auto" theme
            const dbTheme = document.body.getAttribute('data-user-theme');
            if (dbTheme === 'auto') {
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
