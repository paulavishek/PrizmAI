/* ==========================================================================
   PrizmLoading — Centralized loading spinner & rotating message utility
   ========================================================================== */

(function (root) {
    'use strict';

    var PrizmLoading = {};

    /* ── Default fallback messages ──────────────────────────────────────── */
    var DEFAULT_MESSAGES = [
        'Processing your request\u2026',
        'Analyzing relevant data\u2026',
        'Evaluating patterns and context\u2026',
        'Cross-referencing project information\u2026',
        'Synthesizing insights\u2026',
        'Running quality checks\u2026',
        'Refining results\u2026',
        'Applying finishing touches\u2026',
        'Almost there \u2014 finalizing output\u2026'
    ];

    var DEFAULT_DURATION = 55000; // 55 seconds — leaves 5s buffer before 60s max

    /* ── Core: rotate messages on an element ────────────────────────────── */
    /**
     * Rotate messages on a text element with smooth opacity fade.
     *
     * @param {HTMLElement} el        — the element whose textContent will cycle
     * @param {string[]}    messages  — array of messages (≥2 recommended)
     * @param {number}      [totalDuration=55000] — total time in ms to spread messages across
     * @returns {{ stop: Function }}  — call .stop() to cancel immediately
     */
    PrizmLoading.rotateMessages = function (el, messages, totalDuration) {
        messages = messages && messages.length ? messages : DEFAULT_MESSAGES;
        totalDuration = totalDuration || DEFAULT_DURATION;

        var idx = 0;
        var interval = messages.length > 1
            ? Math.floor(totalDuration / (messages.length - 1))
            : totalDuration;
        var timer = null;
        var stopped = false;

        // Set the first message immediately
        el.style.transition = 'opacity 0.3s ease';
        el.textContent = messages[0];
        el.style.opacity = '1';

        if (messages.length <= 1) {
            return { stop: function () {} };
        }

        timer = setInterval(function () {
            if (stopped) return;
            idx++;
            if (idx >= messages.length) {
                clearInterval(timer);
                timer = null;
                return;
            }
            // Fade out
            el.style.opacity = '0';
            setTimeout(function () {
                if (stopped) return;
                el.textContent = messages[idx];
                // Fade in
                el.style.opacity = '1';
                // If this is the last message, stop the interval
                if (idx >= messages.length - 1 && timer) {
                    clearInterval(timer);
                    timer = null;
                }
            }, 300);
        }, interval);

        return {
            stop: function () {
                stopped = true;
                if (timer) {
                    clearInterval(timer);
                    timer = null;
                }
            }
        };
    };

    /* ── Show overlay (full-screen or scoped to a container) ────────────── */
    /**
     * Show a loading overlay with spinner + rotating messages.
     *
     * @param {HTMLElement|null} container — if null, uses document.body (full-screen)
     * @param {Object}          opts
     * @param {string[]}        opts.messages      — rotating message strings
     * @param {number}          opts.totalDuration  — ms to spread messages across
     * @param {string}          opts.spinnerSize    — 'sm'|''|'lg' (default '')
     * @returns {{ stop: Function, remove: Function }}
     */
    PrizmLoading.showOverlay = function (container, opts) {
        opts = opts || {};
        container = container || document.body;

        var spinnerClass = 'prizm-spinner';
        if (opts.spinnerSize === 'sm') spinnerClass += ' prizm-spinner--sm';
        if (opts.spinnerSize === 'lg') spinnerClass += ' prizm-spinner--lg';

        var overlay = document.createElement('div');
        overlay.className = 'prizm-loading-overlay';
        overlay.innerHTML =
            '<div class="prizm-loading-container">' +
                '<div class="' + spinnerClass + '"></div>' +
                '<p class="prizm-loading-message"></p>' +
            '</div>';

        // If container is not body, make overlay absolute within it
        if (container !== document.body) {
            overlay.style.position = 'absolute';
            var pos = getComputedStyle(container).position;
            if (pos === 'static') container.style.position = 'relative';
        }

        container.appendChild(overlay);

        var msgEl = overlay.querySelector('.prizm-loading-message');
        var handle = PrizmLoading.rotateMessages(
            msgEl,
            opts.messages,
            opts.totalDuration
        );

        return {
            stop: function () { handle.stop(); },
            remove: function () {
                handle.stop();
                if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
            }
        };
    };

    /* ── Show inline (replaces section content) ─────────────────────────── */
    /**
     * Replace the content of a container with a spinner + rotating messages.
     *
     * @param {HTMLElement} container
     * @param {Object}      opts
     * @param {string[]}    opts.messages
     * @param {number}      opts.totalDuration
     * @param {string}      opts.spinnerSize — 'sm'|''|'lg' (default '')
     * @param {boolean}     opts.preserveContent — if true, hides original instead of clearing
     * @returns {{ stop: Function, remove: Function }}
     */
    PrizmLoading.showInline = function (container, opts) {
        opts = opts || {};

        var spinnerClass = 'prizm-spinner';
        if (opts.spinnerSize === 'sm') spinnerClass += ' prizm-spinner--sm';
        if (opts.spinnerSize === 'lg') spinnerClass += ' prizm-spinner--lg';

        var wrapper = document.createElement('div');
        wrapper.className = 'prizm-loading-inline';
        wrapper.innerHTML =
            '<div class="' + spinnerClass + '"></div>' +
            '<p class="prizm-loading-message"></p>';

        var savedContent = null;
        if (opts.preserveContent) {
            // Hide existing children
            savedContent = [];
            var children = container.children;
            for (var i = 0; i < children.length; i++) {
                savedContent.push({ el: children[i], display: children[i].style.display });
                children[i].style.display = 'none';
            }
        } else {
            savedContent = container.innerHTML;
            container.innerHTML = '';
        }

        container.appendChild(wrapper);

        var msgEl = wrapper.querySelector('.prizm-loading-message');
        var handle = PrizmLoading.rotateMessages(
            msgEl,
            opts.messages,
            opts.totalDuration
        );

        return {
            stop: function () { handle.stop(); },
            remove: function () {
                handle.stop();
                if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper);
                if (opts.preserveContent && Array.isArray(savedContent)) {
                    for (var i = 0; i < savedContent.length; i++) {
                        savedContent[i].el.style.display = savedContent[i].display;
                    }
                }
            }
        };
    };

    /* ── Helper: attach rotating messages to an existing spinner element ── */
    /**
     * Wire up rotating messages to an existing spinner message element.
     * Useful for spinners already in the DOM (Bootstrap spinner-border etc.)
     * that just need their static text replaced with cycling messages.
     *
     * @param {HTMLElement} messageEl  — existing <span> or <small> with static text
     * @param {string[]}    messages   — rotating message strings
     * @param {number}      [totalDuration]
     * @returns {{ stop: Function }}
     */
    PrizmLoading.attachMessages = function (messageEl, messages, totalDuration) {
        if (!messageEl) return { stop: function () {} };
        return PrizmLoading.rotateMessages(messageEl, messages, totalDuration);
    };

    /* ── Predefined message sets for common AI features ─────────────────── */
    PrizmLoading.messages = {
        aiDescription: [
            'Generating description with AI\u2026',
            'Analyzing task context and requirements\u2026',
            'Crafting a clear, structured description\u2026',
            'Refining language and formatting\u2026',
            'Applying project-specific terminology\u2026',
            'Polishing the final description\u2026'
        ],
        complexity: [
            'Analyzing task complexity\u2026',
            'Evaluating technical requirements\u2026',
            'Assessing effort and dependency factors\u2026',
            'Comparing with similar past tasks\u2026',
            'Calculating complexity score\u2026'
        ],
        aiAnalysis: [
            'Analyzing with AI\u2026',
            'Examining task attributes and history\u2026',
            'Evaluating patterns and context\u2026',
            'Cross-referencing project data\u2026',
            'Generating actionable insights\u2026'
        ],
        assignee: [
            'Analyzing team skills, workload & performance\u2026',
            'Matching task requirements to team capabilities\u2026',
            'Evaluating current workload distribution\u2026',
            'Considering availability and expertise\u2026',
            'Identifying the optimal assignment\u2026'
        ],
        priority: [
            'Analyzing optimal priority\u2026',
            'Evaluating urgency and business impact\u2026',
            'Comparing against backlog priorities\u2026',
            'Assessing dependencies and deadlines\u2026',
            'Determining recommended priority level\u2026'
        ],
        summary: [
            'Generating comprehensive summary\u2026',
            'Analyzing task history and context\u2026',
            'Synthesizing key information\u2026',
            'Highlighting critical updates\u2026',
            'Formatting summary output\u2026'
        ],
        stakeholder: [
            'Identifying relevant stakeholders\u2026',
            'Mapping organizational relationships\u2026',
            'Evaluating stakeholder influence and interest\u2026',
            'Assessing communication requirements\u2026',
            'Preparing stakeholder matrix\u2026'
        ],
        boardSummary: [
            'Generating board insights\u2026',
            'Analyzing task distribution patterns\u2026',
            'Evaluating team velocity trends\u2026',
            'Identifying bottlenecks and opportunities\u2026',
            'Preparing comprehensive summary\u2026'
        ],
        workflow: [
            'Analyzing workflow efficiency\u2026',
            'Identifying process bottlenecks\u2026',
            'Evaluating optimization opportunities\u2026',
            'Benchmarking against best practices\u2026',
            'Generating workflow recommendations\u2026'
        ],
        criticalPath: [
            'Analyzing critical path\u2026',
            'Mapping task dependencies\u2026',
            'Calculating schedule impact\u2026',
            'Identifying risk areas on the timeline\u2026',
            'Preparing critical path report\u2026'
        ],
        timeline: [
            'Generating timeline analysis\u2026',
            'Evaluating milestones and deadlines\u2026',
            'Calculating schedule projections\u2026',
            'Assessing resource constraints\u2026',
            'Preparing timeline insights\u2026'
        ],
        columnStructure: [
            'Analyzing optimal column structure\u2026',
            'Evaluating workflow stage patterns\u2026',
            'Mapping task lifecycle stages\u2026',
            'Benchmarking against industry standards\u2026',
            'Generating column recommendations\u2026'
        ],
        boardSetup: [
            'Analyzing your project and generating recommendations\u2026',
            'Evaluating project scope and goals\u2026',
            'Identifying key workflow stages\u2026',
            'Tailoring board configuration\u2026',
            'Preparing optimized board setup\u2026'
        ],
        whatif: [
            'Analyzing scenario impact\u2026',
            'Simulating resource and schedule changes\u2026',
            'Calculating projected outcomes\u2026',
            'Evaluating risk factors\u2026',
            'Comparing scenario trade-offs\u2026',
            'Generating scenario analysis\u2026'
        ],
        premortem: [
            'Analyzing project risks\u2026',
            'Identifying potential failure modes\u2026',
            'Evaluating probability and impact\u2026',
            'Developing mitigation strategies\u2026',
            'Preparing premortem report\u2026'
        ],
        scopeAutopsy: [
            'Analyzing scope history\u2026',
            'Identifying scope change patterns\u2026',
            'Evaluating root causes of scope drift\u2026',
            'Measuring impact on timeline and budget\u2026',
            'Preparing autopsy findings\u2026'
        ],
        stressTest: [
            'Running stress test scenarios\u2026',
            'Simulating peak workload conditions\u2026',
            'Evaluating system bottlenecks\u2026',
            'Calculating resilience metrics\u2026',
            'Preparing stress test report\u2026'
        ],
        meetingTranscript: [
            'AI is analyzing your meeting transcript\u2026',
            'Extracting key discussion points\u2026',
            'Identifying action items and decisions\u2026',
            'Categorizing topics and follow-ups\u2026',
            'Preparing structured analysis\u2026'
        ],
        recommendation: [
            'Analyzing recommendation\u2026',
            'Evaluating implementation impact\u2026',
            'Assessing resource requirements\u2026',
            'Checking alignment with project goals\u2026',
            'Preparing detailed analysis\u2026'
        ],
        dependency: [
            'Analyzing dependencies\u2026',
            'Mapping task relationships\u2026',
            'Identifying circular dependencies\u2026',
            'Calculating dependency depth and risk\u2026',
            'Preparing dependency report\u2026'
        ],
        statusReport: [
            'Generating status report\u2026',
            'Analyzing sprint progress\u2026',
            'Compiling team achievements\u2026',
            'Summarizing blockers and risks\u2026',
            'Formatting the final report\u2026'
        ],
        coach: [
            'Thinking\u2026',
            'Analyzing your question in context\u2026',
            'Researching relevant project data\u2026',
            'Formulating a personalized response\u2026',
            'Preparing actionable advice\u2026'
        ],
        coachDashboard: [
            'Generating coaching insights\u2026',
            'Analyzing team patterns and trends\u2026',
            'Identifying growth opportunities\u2026',
            'Crafting personalized recommendations\u2026',
            'Finalizing coaching report\u2026'
        ],
        burndown: [
            'Generating burndown analysis\u2026',
            'Calculating velocity trends\u2026',
            'Evaluating sprint health metrics\u2026',
            'Projecting completion trajectory\u2026',
            'Preparing burndown insights\u2026'
        ],
        resourceLeveling: [
            'Analyzing resource allocation\u2026',
            'Evaluating team workload distribution\u2026',
            'Identifying over- and under-allocation\u2026',
            'Calculating utilization rates\u2026',
            'Preparing leveling suggestions\u2026'
        ],
        conflicts: [
            'Scanning for resource conflicts\u2026',
            'Analyzing task dependencies and overlaps\u2026',
            'Checking team availability windows\u2026',
            'Evaluating schedule constraints\u2026',
            'Identifying resolution strategies\u2026',
            'Preparing conflict report\u2026'
        ],
        conflictResolution: [
            'Generating AI resolution suggestions\u2026',
            'Analyzing conflict patterns\u2026',
            'Evaluating resolution options\u2026',
            'Ranking strategies by effectiveness\u2026',
            'Preparing recommended actions\u2026'
        ],
        skillGap: [
            'Running skill gap analysis\u2026',
            'Mapping team competencies\u2026',
            'Identifying skill deficiencies\u2026',
            'Evaluating training opportunities\u2026',
            'Generating AI-powered recommendations\u2026',
            'Preparing development roadmap\u2026'
        ],
        chatSummarize: [
            'Summarizing conversation\u2026',
            'Extracting key discussion points\u2026',
            'Identifying decisions and action items\u2026',
            'Organizing topics chronologically\u2026',
            'Formatting summary\u2026'
        ],
        chatExtractThread: [
            'Extracting thread\u2026',
            'Analyzing message relationships\u2026',
            'Identifying thread boundaries\u2026',
            'Grouping related messages\u2026',
            'Preparing thread view\u2026'
        ],
        chatCompose: [
            'Composing message\u2026',
            'Analyzing conversation context\u2026',
            'Drafting an appropriate response\u2026',
            'Refining tone and clarity\u2026',
            'Finalizing message\u2026'
        ],
        wikiGenerate: [
            'Generating wiki content\u2026',
            'Researching relevant context\u2026',
            'Structuring content layout\u2026',
            'Writing section content\u2026',
            'Polishing and formatting\u2026',
            'Finalizing wiki page\u2026'
        ],
        wikiAnalysis: [
            'Analyzing wiki content\u2026',
            'Evaluating content quality and coverage\u2026',
            'Identifying improvement areas\u2026',
            'Checking for gaps and inconsistencies\u2026',
            'Preparing analysis results\u2026'
        ],
        riskAnalysis: [
            'Analyzing project risks\u2026',
            'Evaluating probability and impact\u2026',
            'Identifying risk dependencies\u2026',
            'Assessing risk velocity\u2026',
            'Preparing risk assessment\u2026'
        ],
        riskMitigation: [
            'Generating mitigation strategies\u2026',
            'Evaluating response options\u2026',
            'Assessing resource requirements\u2026',
            'Ranking strategies by effectiveness\u2026',
            'Preparing mitigation plan\u2026'
        ],
        requirementClarity: [
            'Analyzing requirement clarity\u2026',
            'Evaluating completeness and specificity\u2026',
            'Checking for ambiguous language\u2026',
            'Assessing testability criteria\u2026',
            'Preparing clarity report\u2026'
        ],
        requirementEdgeCases: [
            'Generating edge case scenarios\u2026',
            'Analyzing boundary conditions\u2026',
            'Identifying unusual input patterns\u2026',
            'Evaluating error handling needs\u2026',
            'Preparing edge case report\u2026'
        ],
        requirementImpact: [
            'Analyzing downstream requirement impact\u2026',
            'Mapping dependency relationships\u2026',
            'Evaluating affected components\u2026',
            'Assessing change propagation risk\u2026',
            'Generating impact report\u2026'
        ],
        requirementGap: [
            'Running AI gap analysis\u2026',
            'Scanning requirements coverage\u2026',
            'Identifying missing requirements\u2026',
            'Analyzing traceability gaps\u2026',
            'Preparing gap report\u2026'
        ],
        budget: [
            'Analyzing budget data\u2026',
            'Reviewing cost breakdowns and allocations\u2026',
            'Analyzing resource utilization rates\u2026',
            'Evaluating spending trends\u2026',
            'Identifying cost optimization opportunities\u2026',
            'Generating budget recommendations\u2026',
            'Preparing financial insights\u2026'
        ],
        prizmbrief: [
            'Generating project brief\u2026',
            'Analyzing project context and goals\u2026',
            'Structuring executive summary\u2026',
            'Compiling key metrics and milestones\u2026',
            'Formatting the final brief\u2026'
        ],
        onboarding: [
            'Spectra is reading your goal\u2026',
            'Identifying the right missions\u2026',
            'Breaking missions into actionable strategies\u2026',
            'Generating starter tasks tailored to your goal\u2026',
            'Setting up your workspace\u2026',
            'Almost ready \u2014 final touches\u2026'
        ],
        fileAnalysis: [
            'Analyzing file with AI\u2026',
            'Extracting file content and structure\u2026',
            'Identifying key information\u2026',
            'Generating insights from file data\u2026',
            'Preparing analysis results\u2026'
        ],
        taskBreakdown: [
            'Breaking down task\u2026',
            'Analyzing task scope and requirements\u2026',
            'Identifying logical sub-components\u2026',
            'Structuring subtask hierarchy\u2026',
            'Finalizing task breakdown\u2026'
        ],
        classification: [
            'Classifying task\u2026',
            'Analyzing task attributes\u2026',
            'Matching against known categories\u2026',
            'Evaluating classification confidence\u2026',
            'Applying classification labels\u2026'
        ],
        deadline: [
            'Predicting optimal deadline\u2026',
            'Analyzing task complexity and scope\u2026',
            'Evaluating team capacity\u2026',
            'Considering dependency timelines\u2026',
            'Calculating recommended deadline\u2026'
        ]
    };

    /* ── Auto-initialization via MutationObserver ──────────────────────── */
    /**
     * Automatically start/stop rotating messages when spinner containers
     * become visible/hidden. Works with:
     *   - Bootstrap `d-none` class toggle
     *   - `style.display` toggle
     *
     * Usage: add `data-prizm-messages="key"` to the message element inside
     * the spinner container. The key must match a PrizmLoading.messages entry.
     *
     * Optionally add `data-prizm-duration="45000"` to override the default
     * total duration (55 000 ms).
     */
    PrizmLoading.autoInit = function () {
        var activeHandles = {};
        var uid = 0;

        function getUid(el) {
            if (!el._prizmUid) el._prizmUid = 'pl_' + (++uid);
            return el._prizmUid;
        }

        function isHidden(el) {
            if (el.classList.contains('d-none')) return true;
            if (el.style.display === 'none') return true;
            return false;
        }

        function startRotation(msgEl, container) {
            var id = getUid(msgEl);
            if (activeHandles[id]) return; // already running
            var key = msgEl.getAttribute('data-prizm-messages');
            var msgs = PrizmLoading.messages[key];
            if (!msgs) return;
            var dur = parseInt(msgEl.getAttribute('data-prizm-duration'), 10) || DEFAULT_DURATION;
            activeHandles[id] = PrizmLoading.rotateMessages(msgEl, msgs, dur);
        }

        function stopRotation(msgEl) {
            var id = getUid(msgEl);
            if (!activeHandles[id]) return;
            activeHandles[id].stop();
            delete activeHandles[id];
            // Reset to first message for next trigger
            var key = msgEl.getAttribute('data-prizm-messages');
            var msgs = PrizmLoading.messages[key];
            if (msgs && msgs.length) {
                msgEl.textContent = msgs[0];
                msgEl.style.opacity = '1';
            }
        }

        function processContainer(container) {
            var msgEl = container.querySelector('[data-prizm-messages]');
            if (!msgEl && container.hasAttribute('data-prizm-messages')) {
                msgEl = container;
            }
            if (!msgEl) return;
            if (isHidden(container)) {
                stopRotation(msgEl);
            } else {
                startRotation(msgEl, container);
            }
        }

        var observer = new MutationObserver(function (mutations) {
            for (var i = 0; i < mutations.length; i++) {
                var m = mutations[i];
                if (m.attributeName === 'class' || m.attributeName === 'style') {
                    processContainer(m.target);
                }
            }
        });

        function setup() {
            var allMsg = document.querySelectorAll('[data-prizm-messages]');
            var observed = new Set();
            allMsg.forEach(function (span) {
                // Find the nearest toggled parent (with d-none or display:none)
                var container = span.parentElement;
                while (container && container !== document.body) {
                    if (container.classList.contains('d-none') ||
                        container.style.display === 'none' ||
                        container.hasAttribute('data-prizm-container')) {
                        break;
                    }
                    container = container.parentElement;
                }
                if (!container || container === document.body) {
                    container = span.parentElement;
                }
                if (!observed.has(container)) {
                    observed.add(container);
                    observer.observe(container, {
                        attributes: true,
                        attributeFilter: ['class', 'style']
                    });
                }
            });
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', setup);
        } else {
            setup();
        }

        // Re-initialize if new spinners are added dynamically
        PrizmLoading._reinit = setup;
    };

    // Auto-initialize on load
    PrizmLoading.autoInit();

    /* ── Expose globally ────────────────────────────────────────────────── */
    root.PrizmLoading = PrizmLoading;

})(window);
