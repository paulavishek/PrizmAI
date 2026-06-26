/*
 * Task Aging / Stalling Detection — badge rendering + one-time onboarding tooltip.
 *
 * The day-count is computed CLIENT-SIDE from each card's data-column-entered-at attribute and the
 * effective thresholds carried on its parent .kanban-column (data-aging-enabled / -warning /
 * -critical / -show). This keeps the badge correct after a drag-drop move (which does not reload)
 * and as days roll over, with zero extra server work per task.
 *
 * Exposes window.PrizmAging.{recalc, recalcAll} so kanban.js can reset a card's badge on move.
 */
(function () {
    'use strict';

    // Whole calendar days elapsed between an ISO timestamp and now, floored.
    function daysSince(iso) {
        if (!iso) return null;
        const entered = new Date(iso);
        if (isNaN(entered.getTime())) return null;
        const ms = Date.now() - entered.getTime();
        if (ms < 0) return 0;
        return Math.floor(ms / 86400000);
    }

    // Render (or hide) the aging badge for one card element.
    function recalc(cardEl) {
        const badge = cardEl.querySelector('.card-aging-badge');
        if (!badge) return;
        const column = cardEl.closest('.kanban-column');
        if (!column || column.dataset.agingEnabled !== '1') {
            hide(badge);
            return;
        }
        const days = daysSince(cardEl.dataset.columnEnteredAt);
        if (days === null) { hide(badge); return; }

        const show = parseInt(column.dataset.agingShow, 10) || 1;
        const warning = parseInt(column.dataset.agingWarning, 10) || 0;
        const critical = parseInt(column.dataset.agingCritical, 10) || 0;

        if (days < show) { hide(badge); return; }

        let state = 'aging-neutral';
        if (critical && days >= critical) state = 'aging-critical';
        else if (warning && days >= warning) state = 'aging-warning';

        badge.classList.remove('aging-neutral', 'aging-warning', 'aging-critical', 'd-none');
        badge.hidden = false;
        badge.classList.add(state);
        badge.innerHTML = '<i class="far fa-clock"></i>' + days + 'd';
        badge.title = 'In this column for ' + days + ' day' + (days === 1 ? '' : 's');

        if (state === 'aging-warning' || state === 'aging-critical') {
            maybeShowOnboarding(badge);
        }
    }

    function hide(badge) {
        badge.hidden = true;
        badge.classList.add('d-none');
    }

    function recalcAll() {
        document.querySelectorAll('.kanban-task-v2').forEach(recalc);
    }

    /* ---- One-time onboarding tooltip ---- */
    let onboardingShown = false;

    function maybeShowOnboarding(badge) {
        if (onboardingShown) return;
        const board = document.getElementById('kanban-board');
        if (!board) return;
        // Only on boards that have NEVER been configured and the user hasn't dismissed it.
        if (board.dataset.agingConfigured === '1') return;
        if (board.dataset.agingOnboardingDismissed === '1') return;
        onboardingShown = true;

        const tip = document.createElement('div');
        tip.className = 'aging-onboarding-tip';
        tip.innerHTML =
            '<div class="aging-onboarding-tip-inner">' +
            '<i class="fas fa-hourglass-half text-warning me-1"></i>' +
            'This task has been sitting a while. Tune aging thresholds from a column’s ' +
            '<i class="fas fa-ellipsis-v"></i> menu → <strong>Aging Alerts</strong>.' +
            '<button type="button" class="btn-close btn-close-sm ms-2" aria-label="Dismiss"></button>' +
            '</div>';
        Object.assign(tip.style, {
            position: 'absolute', zIndex: 9998, maxWidth: '260px',
            background: 'var(--card-bg, #fff)', border: '1px solid var(--border-color, #ddd)',
            borderRadius: '8px', boxShadow: '0 6px 18px rgba(0,0,0,.18)',
            padding: '10px 12px', fontSize: '.78rem', lineHeight: '1.4',
        });
        document.body.appendChild(tip);
        const r = badge.getBoundingClientRect();
        tip.style.top = (window.scrollY + r.bottom + 8) + 'px';
        tip.style.left = (window.scrollX + r.left) + 'px';

        function dismiss() {
            tip.remove();
            board.dataset.agingOnboardingDismissed = '1';
            const csrf = document.cookie.match(/csrftoken=([^;]+)/);
            fetch('/boards/' + board.dataset.boardId + '/dismiss-aging-onboarding/', {
                method: 'POST',
                headers: { 'X-CSRFToken': csrf ? csrf[1] : '' },
            }).catch(function () { /* non-fatal */ });
        }
        tip.querySelector('.btn-close').addEventListener('click', dismiss);
        setTimeout(function () {
            document.addEventListener('click', function onDoc(e) {
                if (!tip.contains(e.target)) { dismiss(); document.removeEventListener('click', onDoc); }
            });
        }, 0);
    }

    window.PrizmAging = { recalc: recalc, recalcAll: recalcAll };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', recalcAll);
    } else {
        recalcAll();
    }
})();
