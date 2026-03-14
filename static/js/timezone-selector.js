// Timezone Selector — topbar panel for per-user timezone preference
// Uses manual getBoundingClientRect() positioning so the panel is never
// clipped by the fixed topbar's stacking context.
(function () {
    'use strict';

    // Grouped timezone list (region → timezones)
    var TIMEZONE_GROUPS = {
        'Americas': [
            'America/New_York', 'America/Chicago', 'America/Denver',
            'America/Los_Angeles', 'America/Anchorage', 'Pacific/Honolulu',
            'America/Phoenix', 'America/Toronto', 'America/Vancouver',
            'America/Sao_Paulo', 'America/Argentina/Buenos_Aires',
            'America/Mexico_City', 'America/Bogota', 'America/Lima',
            'America/Santiago', 'America/Halifax', 'America/St_Johns'
        ],
        'Europe': [
            'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Madrid',
            'Europe/Rome', 'Europe/Amsterdam', 'Europe/Brussels',
            'Europe/Zurich', 'Europe/Vienna', 'Europe/Stockholm',
            'Europe/Oslo', 'Europe/Helsinki', 'Europe/Warsaw',
            'Europe/Prague', 'Europe/Budapest', 'Europe/Bucharest',
            'Europe/Athens', 'Europe/Istanbul', 'Europe/Moscow',
            'Europe/Kiev', 'Europe/Lisbon', 'Europe/Dublin'
        ],
        'Asia & Pacific': [
            'Asia/Kolkata', 'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Hong_Kong',
            'Asia/Singapore', 'Asia/Seoul', 'Asia/Taipei', 'Asia/Bangkok',
            'Asia/Jakarta', 'Asia/Manila', 'Asia/Karachi', 'Asia/Dhaka',
            'Asia/Colombo', 'Asia/Kathmandu', 'Asia/Almaty', 'Asia/Tashkent',
            'Asia/Vladivostok', 'Asia/Kamchatka',
            'Australia/Sydney', 'Australia/Melbourne', 'Australia/Perth',
            'Australia/Brisbane', 'Australia/Adelaide',
            'Pacific/Auckland', 'Pacific/Fiji', 'Pacific/Guam'
        ],
        'Middle East & Africa': [
            'Asia/Dubai', 'Asia/Riyadh', 'Asia/Qatar', 'Asia/Bahrain',
            'Asia/Kuwait', 'Asia/Muscat', 'Asia/Tehran', 'Asia/Baghdad',
            'Asia/Jerusalem', 'Asia/Beirut', 'Asia/Amman',
            'Africa/Cairo', 'Africa/Lagos', 'Africa/Nairobi',
            'Africa/Johannesburg', 'Africa/Casablanca', 'Africa/Accra',
            'Africa/Addis_Ababa', 'Africa/Dar_es_Salaam'
        ]
    };

    // Compute a short abbreviation for a timezone (e.g. "EST", "IST")
    function getTimezoneAbbr(tzName) {
        try {
            var parts = new Intl.DateTimeFormat('en-US', {
                timeZone: tzName,
                timeZoneName: 'short'
            }).formatToParts(new Date());
            for (var i = 0; i < parts.length; i++) {
                if (parts[i].type === 'timeZoneName') return parts[i].value;
            }
        } catch (e) { /* fallback */ }
        return tzName.split('/').pop().replace(/_/g, ' ');
    }

    // Compute a human-friendly label: "America/New_York → New York (EST)"
    function formatTzLabel(tzName) {
        var city = tzName.split('/').pop().replace(/_/g, ' ');
        var abbr = getTimezoneAbbr(tzName);
        // Get current UTC offset
        try {
            var now = new Date();
            var fmt = new Intl.DateTimeFormat('en-US', {
                timeZone: tzName,
                timeZoneName: 'longOffset'
            });
            var parts = fmt.formatToParts(now);
            var offset = '';
            for (var i = 0; i < parts.length; i++) {
                if (parts[i].type === 'timeZoneName') { offset = parts[i].value; break; }
            }
            return city + ' (' + abbr + ', ' + offset + ')';
        } catch (e) {
            return city + ' (' + abbr + ')';
        }
    }

    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function saveTimezone(tzName) {
        fetch('/accounts/api/set-timezone/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ timezone: tzName })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.status === 'ok') {
                document.body.setAttribute('data-user-timezone', tzName);
                localStorage.setItem('prizmTimezone', tzName);
                // Reload so all server-rendered dates re-render in the new timezone
                location.reload();
            }
        })
        .catch(function (err) { console.error('Error saving timezone:', err); });
    }

    function buildList(filterText) {
        var list = document.getElementById('timezone-list');
        if (!list) return;
        list.innerHTML = '';
        var currentTz = document.body.getAttribute('data-user-timezone') || 'Asia/Kolkata';
        var filter = (filterText || '').toLowerCase();
        var anyVisible = false;

        var groups = Object.keys(TIMEZONE_GROUPS);
        for (var g = 0; g < groups.length; g++) {
            var groupName = groups[g];
            var tzList = TIMEZONE_GROUPS[groupName];

            // Filter timezones in this group
            var filtered = [];
            for (var t = 0; t < tzList.length; t++) {
                var tz = tzList[t];
                var label = formatTzLabel(tz);
                if (!filter || tz.toLowerCase().indexOf(filter) !== -1 || label.toLowerCase().indexOf(filter) !== -1) {
                    filtered.push({ tz: tz, label: label });
                }
            }
            if (filtered.length === 0) continue;
            anyVisible = true;

            // Group header
            var header = document.createElement('h6');
            header.className = 'dropdown-header timezone-group-header';
            header.textContent = groupName;
            list.appendChild(header);

            for (var f = 0; f < filtered.length; f++) {
                var item = filtered[f];
                var a = document.createElement('a');
                a.className = 'dropdown-item timezone-item' + (item.tz === currentTz ? ' active' : '');
                a.href = '#';
                a.setAttribute('data-tz', item.tz);
                a.textContent = item.label;
                a.addEventListener('click', (function (tzVal) {
                    return function (e) {
                        e.preventDefault();
                        saveTimezone(tzVal);
                    };
                })(item.tz));
                list.appendChild(a);
            }
        }

        if (!anyVisible) {
            var noMatch = document.createElement('div');
            noMatch.className = 'px-3 py-2 text-muted small';
            noMatch.textContent = 'No matching timezone found';
            list.appendChild(noMatch);
        }
    }

    var panel = null;
    var toggleBtn = null;
    var isOpen = false;

    function openPanel() {
        if (!panel || !toggleBtn) return;
        // Calculate position from the button's viewport rectangle
        var rect = toggleBtn.getBoundingClientRect();
        panel.style.top  = (rect.bottom + 4) + 'px';
        // Align right edge of panel with right edge of button
        panel.style.right = (window.innerWidth - rect.right) + 'px';
        panel.style.left  = 'auto';
        panel.removeAttribute('hidden');
        toggleBtn.setAttribute('aria-expanded', 'true');
        isOpen = true;
        // Reset and focus search
        var searchInput = document.getElementById('timezone-search-input');
        if (searchInput) {
            searchInput.value = '';
            buildList('');
            searchInput.focus();
        }
    }

    function closePanel() {
        if (!panel) return;
        panel.setAttribute('hidden', '');
        if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'false');
        isOpen = false;
    }

    function initTimezoneSelector() {
        var currentTz = document.body.getAttribute('data-user-timezone') || 'Asia/Kolkata';
        panel     = document.getElementById('tz-panel');
        toggleBtn = document.getElementById('tz-toggle-btn');

        if (!panel || !toggleBtn) return;

        // Set abbreviation label in button
        var abbrLabel = document.getElementById('tz-abbr-label');
        if (abbrLabel) {
            abbrLabel.textContent = getTimezoneAbbr(currentTz);
        }

        // Build initial list
        buildList('');

        // Toggle open/close on button click
        toggleBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            if (isOpen) { closePanel(); } else { openPanel(); }
        });

        // Close when clicking outside the panel or button
        document.addEventListener('click', function (e) {
            if (isOpen && !panel.contains(e.target) && e.target !== toggleBtn) {
                closePanel();
            }
        });

        // Close on Escape
        document.addEventListener('keydown', function (e) {
            if (isOpen && e.key === 'Escape') { closePanel(); }
        });

        // Reposition on window resize
        window.addEventListener('resize', function () {
            if (isOpen) { openPanel(); }
        });

        // Search filtering
        var searchInput = document.getElementById('timezone-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', function () {
                buildList(this.value);
            });
            // Prevent panel close when typing inside it
            panel.addEventListener('click', function (e) {
                e.stopPropagation();
            });
        }

        // Auto-detect browser timezone on first visit and show a suggestion
        var browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        var hasSeenTzSuggestion = localStorage.getItem('prizmTzSuggestionSeen');
        if (browserTz && browserTz !== currentTz && !hasSeenTzSuggestion) {
            localStorage.setItem('prizmTzSuggestionSeen', 'true');
            // Show a subtle toast suggesting the browser timezone
            showTzSuggestionToast(browserTz);
        }
    }

    function showTzSuggestionToast(browserTz) {
        var abbr = getTimezoneAbbr(browserTz);
        var city = browserTz.split('/').pop().replace(/_/g, ' ');
        var container = document.getElementById('django-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'tz-toast-container';
            container.className = 'position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '1100';
            document.body.appendChild(container);
        }

        var toast = document.createElement('div');
        toast.className = 'toast align-items-center text-white bg-info border-0 show mb-2';
        toast.setAttribute('role', 'alert');
        toast.innerHTML =
            '<div class="d-flex">' +
            '  <div class="toast-body">' +
            '    <i class="fas fa-globe me-2"></i>' +
            '    Your browser timezone is <strong>' + city + ' (' + abbr + ')</strong>.' +
            '    <a href="#" id="tz-suggestion-apply" class="text-white text-decoration-underline ms-1">Switch now</a>' +
            '  </div>' +
            '  <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>' +
            '</div>';
        container.appendChild(toast);

        var applyBtn = document.getElementById('tz-suggestion-apply');
        if (applyBtn) {
            applyBtn.addEventListener('click', function (e) {
                e.preventDefault();
                saveTimezone(browserTz);
            });
        }

        // Auto-hide after 10 seconds
        setTimeout(function () {
            try { toast.remove(); } catch (e) { /* ignore */ }
        }, 10000);
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTimezoneSelector);
    } else {
        initTimezoneSelector();
    }
})();
