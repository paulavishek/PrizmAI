/**
 * Feature Guide — Click-only popovers + detail modals for AI feature pages.
 *
 * Initialises Bootstrap 5 popovers on `.feature-guide-badge` buttons and
 * delegates "Learn more" clicks inside popovers to open the corresponding
 * detail modal.  Re-initialises after HTMX content swaps.
 */
(function () {
    'use strict';

    /** Track active popover so we can dismiss it on outside click. */
    let activePopover = null;

    /**
     * Initialise popovers on all feature-guide badges within a root element.
     */
    function initFeatureGuides(root) {
        const badges = (root || document).querySelectorAll('.feature-guide-badge');
        badges.forEach(function (badge) {
            // Avoid double-init
            if (badge._featureGuideInit) return;
            badge._featureGuideInit = true;

            const popover = new bootstrap.Popover(badge, {
                trigger: 'manual',   // we handle click ourselves
                html: true,
                sanitize: false,     // content is admin-authored, not user-input
                customClass: 'feature-guide-popover',
            });

            badge.addEventListener('click', function (e) {
                e.stopPropagation();

                // If clicking the same badge, toggle off
                if (activePopover && activePopover._element === badge) {
                    activePopover.hide();
                    activePopover = null;
                    return;
                }

                // Dismiss any other open popover first
                if (activePopover) {
                    activePopover.hide();
                    activePopover = null;
                }

                popover.show();
                activePopover = popover;
            });
        });
    }

    /**
     * Dismiss popover on outside click.
     */
    document.addEventListener('click', function (e) {
        if (!activePopover) return;

        // If the click is inside the popover tip, don't dismiss
        var tip = activePopover.getTipElement ? activePopover.getTipElement() : activePopover.tip;
        if (tip && tip.contains(e.target)) return;

        // If the click is on the badge itself, the badge handler deals with it
        if (activePopover._element && activePopover._element.contains(e.target)) return;

        activePopover.hide();
        activePopover = null;
    });

    /**
     * Dismiss popover on Escape key.
     */
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && activePopover) {
            activePopover.hide();
            activePopover = null;
        }
    });

    /**
     * Delegate "Learn more" clicks inside popovers → open the modal.
     */
    document.addEventListener('click', function (e) {
        var link = e.target.closest('.feature-guide-learn-more');
        if (!link) return;

        e.preventDefault();
        e.stopPropagation();

        var modalId = link.getAttribute('data-modal-target');
        if (!modalId) return;

        var modalEl = document.getElementById(modalId);
        if (!modalEl) return;

        // Dismiss popover first
        if (activePopover) {
            activePopover.hide();
            activePopover = null;
        }

        // Open modal
        var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    });

    // ── Init on DOM ready ────────────────────────────────────────────
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initFeatureGuides();
        });
    } else {
        initFeatureGuides();
    }

    // ── Re-init after HTMX content swaps ─────────────────────────────
    document.addEventListener('htmx:afterSwap', function (e) {
        initFeatureGuides(e.detail.target);
    });
})();
