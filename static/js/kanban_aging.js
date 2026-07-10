/*
 * Task Aging / Stalling Detection — badge rendering + live per-column aging alerts.
 *
 * The day-count is computed CLIENT-SIDE from each card's data-column-entered-at attribute and the
 * effective thresholds carried on its parent .kanban-column (data-aging-enabled / -warning /
 * -critical / -show). This keeps the badge correct after a drag-drop move (which does not reload)
 * and as days roll over, with zero extra server work per task.
 *
 * Beyond the badge, each column gets a live aging-alert layer:
 *   - Up to MAX_INDIVIDUAL_AGING_ALERTS aging cards each get their own floating alert, anchored
 *     to that specific card.
 *   - Past that threshold, individual alerts are replaced by a single column-header banner
 *     ("N tasks aging — View") that filters the column down to just its aging cards.
 * Both recompute live as cards move/complete (recalc/recalcAll re-derive tiers, then
 * updateAllColumnAgingSummaries() re-renders the alert layer) — no page reload needed.
 *
 * Exposes window.PrizmAging.{recalc, recalcAll, updateAllColumnAgingSummaries} so kanban.js can
 * refresh a card's badge (and the column alert layer) on move.
 */
(function () {
    'use strict';

    const MAX_INDIVIDUAL_AGING_ALERTS = 2;

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
    }

    function hide(badge) {
        badge.hidden = true;
        badge.classList.add('d-none');
    }

    function recalcAll() {
        document.querySelectorAll('.kanban-task-v2').forEach(recalc);
        updateAllColumnAgingSummaries();
    }

    /* ---- Live per-column aging alerts (individual tips + overflow banner) ---- */

    // taskId -> open tip element, for cards currently showing their own floating alert.
    const openTips = new Map();
    // taskIds the user has closed (X or click-away) THIS page view. Not persisted —
    // the task is still genuinely aging, so it's expected back on the next load.
    const closedAlertTaskIds = new Set();

    function agingTierOf(cardEl) {
        const badge = cardEl.querySelector('.card-aging-badge');
        if (!badge || badge.hidden) return null;
        if (badge.classList.contains('aging-critical')) return 'critical';
        if (badge.classList.contains('aging-warning')) return 'warning';
        return null;
    }

    function updateAllColumnAgingSummaries() {
        document.querySelectorAll('.kanban-column').forEach(updateColumnAgingSummary);
    }

    function updateColumnAgingSummary(columnEl) {
        const cards = Array.from(columnEl.querySelectorAll('.kanban-task-v2'));
        const agingCards = cards.filter(function (c) { return agingTierOf(c) !== null; });

        if (agingCards.length === 0) {
            clearIndividualAlerts(columnEl);
            removeBanner(columnEl);
            return;
        }

        if (agingCards.length <= MAX_INDIVIDUAL_AGING_ALERTS) {
            removeBanner(columnEl);
            const keep = new Set(agingCards.map(function (c) { return c.dataset.taskId; }));
            clearIndividualAlerts(columnEl, keep);
            agingCards.forEach(showIndividualAlert);
        } else {
            clearIndividualAlerts(columnEl);
            showBanner(columnEl, agingCards);
        }
    }

    // ---- Individual floating alerts ----

    function showIndividualAlert(cardEl) {
        const taskId = cardEl.dataset.taskId;
        if (!taskId || openTips.has(taskId) || closedAlertTaskIds.has(taskId)) return;
        const badge = cardEl.querySelector('.card-aging-badge');
        if (!badge) return;
        const columnEl = cardEl.closest('.kanban-column');

        cardEl.classList.add('aging-alert-highlight');

        const tip = document.createElement('div');
        tip.className = 'aging-alert-tip';
        tip.dataset.taskId = taskId;
        tip.dataset.columnId = columnEl ? columnEl.dataset.columnId : '';
        tip.innerHTML =
            '<div class="aging-alert-tip-inner">' +
            '<i class="fas fa-hourglass-half text-warning me-1"></i>' +
            'This task has been sitting a while. Tune aging thresholds from a column’s ' +
            '<i class="fas fa-ellipsis-v"></i> menu → <strong>Aging Alerts</strong>.' +
            '<button type="button" class="btn-close btn-close-sm ms-2" aria-label="Dismiss"></button>' +
            '</div>';
        document.body.appendChild(tip);

        const r = badge.getBoundingClientRect();
        tip.style.top = (window.scrollY + r.bottom + 10) + 'px';
        tip.style.left = (window.scrollX + r.left) + 'px';
        // Arrow sits directly above the badge that triggered the tip, regardless
        // of where the tip box itself ends up horizontally.
        const arrowOffset = Math.max(8, Math.min(r.width / 2 + 4, tip.offsetWidth - 20));
        tip.style.setProperty('--aging-tip-arrow-left', arrowOffset + 'px');

        openTips.set(taskId, tip);

        // Only the X closes an individual alert. A "click outside" listener would
        // fire for every OTHER open tip too (closing tip A's X is itself a click
        // outside tip B), silently closing alerts the user never touched.
        tip.querySelector('.btn-close').addEventListener('click', function () {
            closedAlertTaskIds.add(taskId);
            closeIndividualAlert(taskId, tip);
        });
    }

    // Internal cleanup (card stopped aging, column moved to banner mode, etc.) —
    // does NOT count as a user dismissal, so it's not added to closedAlertTaskIds.
    function closeIndividualAlert(taskId, tip) {
        tip.remove();
        openTips.delete(taskId);
        const card = document.querySelector('.kanban-task-v2[data-task-id="' + taskId + '"]');
        if (card) card.classList.remove('aging-alert-highlight');
    }

    function clearIndividualAlerts(columnEl, keepTaskIds) {
        const columnId = columnEl.dataset.columnId;
        openTips.forEach(function (tip, taskId) {
            if (tip.dataset.columnId !== columnId) return;
            if (keepTaskIds && keepTaskIds.has(taskId)) return;
            closeIndividualAlert(taskId, tip);
        });
    }

    // ---- Overflow banner (column has more aging cards than the individual-alert threshold) ----

    function showBanner(columnEl, agingCards) {
        const slot = columnEl.querySelector('.column-aging-banner-slot');
        if (!slot) return;
        let banner = slot.querySelector('.column-aging-banner');
        const hasCritical = agingCards.some(function (c) { return agingTierOf(c) === 'critical'; });
        if (!banner) {
            banner = document.createElement('span');
            banner.className = 'column-aging-banner';
            banner.innerHTML =
                '<i class="fas fa-hourglass-half me-1"></i>' +
                '<span class="column-aging-banner-count"></span>' +
                '<button type="button" class="column-aging-banner-view">View</button>';
            banner.querySelector('.column-aging-banner-view').addEventListener('click', function (e) {
                e.stopPropagation();
                applyAgingFilter(columnEl, currentAgingCards(columnEl));
            });
            slot.appendChild(banner);
        }
        banner.classList.toggle('aging-banner-critical', hasCritical);
        banner.classList.toggle('aging-banner-warning', !hasCritical);
        banner.querySelector('.column-aging-banner-count').textContent =
            agingCards.length + (agingCards.length === 1 ? ' task aging' : ' tasks aging');

        // Keep an already-active filter in sync with the live aging set.
        if (columnEl.dataset.agingFilterActive === '1') {
            applyAgingFilter(columnEl, agingCards);
        }
    }

    function removeBanner(columnEl) {
        const slot = columnEl.querySelector('.column-aging-banner-slot');
        if (slot) slot.innerHTML = '';
        clearAgingFilter(columnEl);
    }

    function currentAgingCards(columnEl) {
        return Array.from(columnEl.querySelectorAll('.kanban-task-v2'))
            .filter(function (c) { return agingTierOf(c) !== null; });
    }

    // ---- "View" filter: hide non-aging cards in the column, with a Clear notice ----

    function applyAgingFilter(columnEl, agingCards) {
        const agingIds = new Set(agingCards.map(function (c) { return c.dataset.taskId; }));
        columnEl.querySelectorAll('.kanban-task-v2').forEach(function (card) {
            if (agingIds.has(card.dataset.taskId)) return;
            if (!card.classList.contains('filtered-out')) {
                card.classList.add('filtered-out');
                card.dataset.agingHiddenByFilter = '1';
            }
        });
        columnEl.dataset.agingFilterActive = '1';
        showFilterNotice(columnEl, agingCards.length);
    }

    function clearAgingFilter(columnEl) {
        columnEl.querySelectorAll('[data-aging-hidden-by-filter="1"]').forEach(function (card) {
            card.classList.remove('filtered-out');
            delete card.dataset.agingHiddenByFilter;
        });
        delete columnEl.dataset.agingFilterActive;
        const notice = columnEl.querySelector('.aging-filter-notice');
        if (notice) notice.remove();
    }

    function showFilterNotice(columnEl, count) {
        let notice = columnEl.querySelector('.aging-filter-notice');
        if (!notice) {
            notice = document.createElement('div');
            notice.className = 'aging-filter-notice';
            notice.innerHTML =
                '<span class="aging-filter-notice-label"></span>' +
                '<button type="button" class="aging-filter-notice-clear">Clear</button>';
            notice.querySelector('.aging-filter-notice-clear').addEventListener('click', function () {
                clearAgingFilter(columnEl);
            });
            const tasksEl = columnEl.querySelector('.kanban-column-tasks');
            if (!tasksEl) return;
            tasksEl.insertAdjacentElement('beforebegin', notice);
        }
        notice.querySelector('.aging-filter-notice-label').textContent =
            'Showing: ' + count + (count === 1 ? ' aging task' : ' aging tasks') + ' in this column';
    }

    window.PrizmAging = {
        recalc: recalc,
        recalcAll: recalcAll,
        updateAllColumnAgingSummaries: updateAllColumnAgingSummaries,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', recalcAll);
    } else {
        recalcAll();
    }
})();
