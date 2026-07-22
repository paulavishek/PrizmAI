/*
 * Task Aging / Stalling Detection — badge rendering + live per-column aging alerts.
 *
 * The day-count is computed CLIENT-SIDE from each card's data-column-entered-at attribute and the
 * effective thresholds carried on its parent .kanban-column (data-aging-enabled / -warning /
 * -critical / -show). This keeps the badge correct after a drag-drop move (which does not reload)
 * and as days roll over, with zero extra server work per task.
 *
 * Beyond the badge, each aging card gets:
 *   - A subtle tier-colored outline/glow ring (.aging-ring-warning / .aging-ring-critical) —
 *     doesn't touch the left border, which is already used for task priority.
 *   - Its column shows a single header banner ("N tasks aging — View") the moment it has ANY
 *     aging cards (one rule, not a per-count individual-vs-banner split), which filters the
 *     column down to just its aging cards.
 * Both recompute live as cards move/complete (recalc/recalcAll re-derive tiers, then
 * updateAllColumnAgingSummaries() re-renders the banner layer) — no page reload needed.
 *
 * Exposes window.PrizmAging.{recalc, recalcAll, updateAllColumnAgingSummaries} so kanban.js can
 * refresh a card's badge (and the column alert layer) on move.
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

    // Render (or hide) the aging badge + ring cue for one card element.
    function recalc(cardEl) {
        const badge = cardEl.querySelector('.card-aging-badge');
        if (!badge) return;
        const column = cardEl.closest('.kanban-column');
        if (!column || column.dataset.agingEnabled !== '1') {
            hide(cardEl, badge);
            return;
        }
        const days = daysSince(cardEl.dataset.columnEnteredAt);
        if (days === null) { hide(cardEl, badge); return; }

        const show = parseInt(column.dataset.agingShow, 10) || 1;
        const warning = parseInt(column.dataset.agingWarning, 10) || 0;
        const critical = parseInt(column.dataset.agingCritical, 10) || 0;

        if (days < show) { hide(cardEl, badge); return; }

        let state = 'aging-neutral';
        if (critical && days >= critical) state = 'aging-critical';
        else if (warning && days >= warning) state = 'aging-warning';

        badge.classList.remove('aging-neutral', 'aging-warning', 'aging-critical', 'd-none');
        badge.hidden = false;
        badge.classList.add(state);
        badge.innerHTML = '<i class="far fa-clock"></i>' + days + 'd';
        badge.title = 'In this column for ' + days + ' day' + (days === 1 ? '' : 's');

        cardEl.classList.toggle('aging-ring-warning', state === 'aging-warning');
        cardEl.classList.toggle('aging-ring-critical', state === 'aging-critical');
    }

    function hide(cardEl, badge) {
        badge.hidden = true;
        badge.classList.add('d-none');
        cardEl.classList.remove('aging-ring-warning', 'aging-ring-critical');
    }

    function recalcAll() {
        document.querySelectorAll('.kanban-task-v2').forEach(recalc);
        updateAllColumnAgingSummaries();
    }

    /* ---- Live per-column aging banner ---- */

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
        const agingCards = currentAgingCards(columnEl);
        if (agingCards.length === 0) {
            removeBanner(columnEl);
        } else {
            showBanner(columnEl, agingCards);
        }
    }

    // ---- Column-header banner ----

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
