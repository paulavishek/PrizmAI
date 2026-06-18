/* ============================================================
   Strategic Detail Pages – JS  (Goal / Mission / Strategy)
   ============================================================ */
(function () {
    'use strict';

    /* ---- Tab switching (Bootstrap 5 native or manual fallback) ---- */
    function activateTab(target) {
        if (!target) return;
        var link = document.querySelector('.strategic-tabs .nav-link[data-bs-target="' + target + '"], .strategic-tabs .nav-link[href="' + target + '"]');
        var pane = document.querySelector(target);
        if (!link || !pane) return;
        document.querySelectorAll('.strategic-tabs .nav-link').forEach(function (t) { t.classList.remove('active'); });
        var container = document.querySelector('.tab-content');
        if (container) {
            container.querySelectorAll('.tab-pane').forEach(function (p) { p.classList.remove('show', 'active'); });
        }
        link.classList.add('active');
        pane.classList.add('show', 'active');
    }

    document.querySelectorAll('.strategic-tabs .nav-link').forEach(function (tab) {
        tab.addEventListener('click', function (e) {
            e.preventDefault();
            var target = this.getAttribute('data-bs-target') || this.getAttribute('href');
            if (!target) return;
            activateTab(target);
            // Keep the URL hash in sync so a reload (e.g. after regenerating an
            // AI summary) returns to this tab instead of resetting to Overview.
            if (history.replaceState) { history.replaceState(null, '', target); }
        });
    });

    // On load, restore the tab named in the URL hash (#tab-ai, #tab-updates, …).
    if (window.location.hash) { activateTab(window.location.hash); }

    /* ---- AJAX: Post a Strategic Update ---- */
    var updateForm = document.getElementById('strategic-update-form');
    if (updateForm) {
        updateForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var form = this;
            var btn = form.querySelector('button[type="submit"]');
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Posting…';

            fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.success) {
                    // Prepend new entry to feed
                    var feed = document.getElementById('updates-feed');
                    if (feed && data.html) {
                        feed.insertAdjacentHTML('afterbegin', data.html);
                    }
                    // Hide "no updates" message
                    var noMsg = document.getElementById('no-updates-msg');
                    if (noMsg) noMsg.style.display = 'none';
                    form.reset();
                    // Update count badge if present
                    var badge = document.getElementById('updates-count');
                    if (badge && data.count !== undefined) {
                        badge.textContent = data.count;
                    }
                } else {
                    alert(data.error || 'Failed to post update.');
                }
            })
            .catch(function () { alert('Network error — please try again.'); })
            .finally(function () {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-paper-plane me-1"></i>Post';
            });
        });
    }

    /* ---- AJAX: Generate / Regenerate AI Summary ---- */
    document.querySelectorAll('.btn-regenerate-ai').forEach(function (regenBtn) {
        regenBtn.addEventListener('click', function () {
            var url = this.dataset.url;
            if (!url) return;
            var original = this.innerHTML;
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Generating…';

            var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
            var headers = { 'X-Requested-With': 'XMLHttpRequest' };
            if (csrfToken) headers['X-CSRFToken'] = csrfToken.value;

            var self = this;
            fetch(url, { method: 'POST', headers: headers })
            .then(function (res) {
                if (!res.ok) return res.json().then(function (d) { throw new Error(d.error || 'Server error (' + res.status + ')'); });
                return res.json();
            })
            .then(function (data) {
                if (data.success) {
                    // Summary is generated and saved server-side; reload to render
                    // it, returning to the AI Insights tab rather than Overview.
                    window.location.hash = 'tab-ai';
                    location.reload();
                } else {
                    throw new Error(data.error || 'Failed to generate summary.');
                }
            })
            .catch(function (err) {
                alert(err.message || 'Failed to generate summary.');
                self.disabled = false;
                self.innerHTML = original;
            });
        });
    });

    /* ---- AJAX: Follow / Unfollow ---- */
    var followBtn = document.getElementById('btn-follow');
    if (followBtn) {
        followBtn.addEventListener('click', function () {
            var url = this.dataset.url;
            if (!url) return;
            this.disabled = true;
            var isFollowing = this.dataset.following === 'true';

            var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
            var headers = { 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/json' };
            if (csrfToken) headers['X-CSRFToken'] = csrfToken.value;

            fetch(url, {
                method: isFollowing ? 'DELETE' : 'POST',
                headers: headers,
            })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.success) {
                    followBtn.dataset.following = String(!isFollowing);
                    followBtn.innerHTML = isFollowing
                        ? '<i class="fas fa-bell me-1"></i>Follow'
                        : '<i class="fas fa-bell-slash me-1"></i>Unfollow';
                    followBtn.classList.toggle('btn-outline-primary', isFollowing);
                    followBtn.classList.toggle('btn-primary', !isFollowing);
                    // Update follower count
                    var cnt = document.getElementById('follower-count');
                    if (cnt && data.count !== undefined) cnt.textContent = data.count;
                }
            })
            .catch(function () {})
            .finally(function () { followBtn.disabled = false; });
        });
    }

    /* ---- Stale banner dismiss ---- */
    var dismissStale = document.getElementById('dismiss-stale-banner');
    if (dismissStale) {
        dismissStale.addEventListener('click', function () {
            var banner = document.getElementById('stale-ai-banner');
            if (banner) banner.style.display = 'none';
        });
    }

})();
