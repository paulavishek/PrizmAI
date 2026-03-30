/**
 * AI Progressive Disclosure Library
 *
 * Provides a reusable helper for triggering AI tasks asynchronously,
 * streaming status updates over WebSocket, and rendering the final
 * result once complete.
 *
 * Usage:
 *   triggerAITask('/api/v1/boards/42/summarize/', {
 *     method: 'GET',
 *     containerSelector: '#ai-summary-result',
 *     loadingHTML: '<div class="ai-skeleton ai-skeleton--shimmer"></div>',
 *     onStatus(msg, pct)  { console.log(msg, pct); },
 *     onResult(data)       { renderSummary(data); },
 *     onError(msg)         { alert(msg); },
 *   });
 */

(function (window) {
  'use strict';

  /**
   * Build the WebSocket URL for an AI task.
   * @param {string} taskId  – Celery task ID returned by the server.
   * @returns {string} Full ws(s):// URL.
   */
  function _wsURL(taskId) {
    var proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return proto + '://' + window.location.host + '/ws/ai-task/' + taskId + '/';
  }

  /**
   * Get the CSRF token from the page cookie.
   * @returns {string|null}
   */
  function _getCSRFToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? match[1] : null;
  }

  /**
   * Trigger an AI task and stream progress updates via WebSocket.
   *
   * @param {string} url        – The Django endpoint URL.
   * @param {Object} opts       – Options bag.
   * @param {string}   [opts.method='POST']            – HTTP method.
   * @param {Object}   [opts.body]                     – JSON body (for POST).
   * @param {string}   [opts.containerSelector]        – CSS selector for result container.
   * @param {string}   [opts.statusSelector]           – CSS selector for status text element.
   * @param {string}   [opts.progressSelector]         – CSS selector for progress bar element.
   * @param {string}   [opts.loadingHTML]              – HTML snippet shown while waiting.
   * @param {Function} [opts.onStatus(message, pct)]   – Called on each status update.
   * @param {Function} [opts.onResult(data)]           – Called with the final AI result.
   * @param {Function} [opts.onError(message)]         – Called on failure.
   * @param {number}   [opts.timeoutMs=90000]          – WebSocket timeout (ms).
   */
  function triggerAITask(url, opts) {
    opts = opts || {};
    var method           = (opts.method || 'POST').toUpperCase();
    var container        = opts.containerSelector ? document.querySelector(opts.containerSelector) : null;
    var statusEl         = opts.statusSelector    ? document.querySelector(opts.statusSelector)    : null;
    var progressEl       = opts.progressSelector  ? document.querySelector(opts.progressSelector)  : null;
    var loadingHTML      = opts.loadingHTML || '<div class="ai-skeleton ai-skeleton--shimmer" style="height:120px"></div>';
    var onStatus         = opts.onStatus  || function () {};
    var onResult         = opts.onResult  || function () {};
    var onError          = opts.onError   || function (msg) { console.error('[AI Progressive]', msg); };
    var timeoutMs        = opts.timeoutMs || 90000;

    // Show loading skeleton
    if (container) {
      container.innerHTML = loadingHTML;
      container.style.display = '';
    }

    // 1. Fire the HTTP request with the async header
    var fetchOpts = {
      method: method,
      headers: {
        'X-Request-Async': 'true',
        'X-CSRFToken': _getCSRFToken(),
        'Content-Type': 'application/json',
      },
    };
    if (method !== 'GET' && method !== 'HEAD' && opts.body) {
      fetchOpts.body = JSON.stringify(opts.body);
    }

    fetch(url, fetchOpts)
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (err) {
            throw new Error(err.error || 'Request failed (' + res.status + ')');
          });
        }
        return res.json();
      })
      .then(function (data) {
        if (!data.task_id) {
          throw new Error('No task_id received from server');
        }
        _connectWebSocket(data.task_id);
      })
      .catch(function (err) {
        _handleError(err.message);
      });

    // 2. Connect to the WebSocket and listen for updates
    function _connectWebSocket(taskId) {
      var ws = new WebSocket(_wsURL(taskId));
      var timer = null;

      if (timeoutMs > 0) {
        timer = setTimeout(function () {
          ws.close();
          _handleError('AI task timed out. Please try again.');
        }, timeoutMs);
      }

      ws.onmessage = function (event) {
        var msg;
        try { msg = JSON.parse(event.data); } catch (e) { return; }

        switch (msg.type) {
          case 'ai_status_update':
            _handleStatus(msg.message, msg.progress || 0);
            break;
          case 'ai_result':
            clearTimeout(timer);
            ws.close();
            _handleResult(msg.data);
            break;
          case 'ai_error':
            clearTimeout(timer);
            ws.close();
            _handleError(msg.message);
            break;
        }
      };

      ws.onerror = function () {
        clearTimeout(timer);
        _handleError('WebSocket connection error. The AI task may still complete — please refresh.');
      };

      ws.onclose = function () {
        clearTimeout(timer);
      };
    }

    // Handlers
    function _handleStatus(message, progress) {
      if (statusEl) {
        statusEl.textContent = message;
      }
      if (progressEl) {
        progressEl.style.width = progress + '%';
        progressEl.setAttribute('aria-valuenow', progress);
      }
      onStatus(message, progress);
    }

    function _handleResult(data) {
      if (container) {
        // Clear loading skeleton — caller is responsible for rendering via onResult
        container.innerHTML = '';
      }
      onResult(data);
    }

    function _handleError(message) {
      if (container) {
        container.innerHTML =
          '<div class="alert alert-warning d-flex align-items-center" role="alert">' +
          '<i class="bi bi-exclamation-triangle-fill me-2"></i>' +
          '<span>' + message + '</span></div>';
      }
      onError(message);
    }
  }

  // Export
  window.triggerAITask = triggerAITask;

})(window);
