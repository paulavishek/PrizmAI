/**
 * Enhanced Browser Fingerprinting for Demo Abuse Prevention
 * 
 * Collects multiple browser attributes to create a unique fingerprint
 * that persists even when users clear cookies or use incognito mode.
 * 
 * Fingerprint Components:
 * - Canvas fingerprint (unique rendering patterns)
 * - WebGL fingerprint (GPU info)
 * - Audio fingerprint (audio processing patterns)
 * - Font detection (installed fonts)
 * - Screen/hardware info
 * - Timezone and locale
 */

(function() {
    'use strict';

    window.DemoFingerprint = window.DemoFingerprint || {};

    /**
     * Generate a comprehensive browser fingerprint
     * @returns {Promise<object>} Fingerprint data
     */
    DemoFingerprint.generate = async function() {
        const components = {};
        
        try {
            // Basic browser info
            components.userAgent = navigator.userAgent;
            components.language = navigator.language;
            components.languages = navigator.languages ? navigator.languages.join(',') : '';
            components.platform = navigator.platform;
            components.hardwareConcurrency = navigator.hardwareConcurrency || 0;
            components.deviceMemory = navigator.deviceMemory || 0;
            components.cookieEnabled = navigator.cookieEnabled;
            components.doNotTrack = navigator.doNotTrack;
            
            // Screen info
            components.screenWidth = screen.width;
            components.screenHeight = screen.height;
            components.screenDepth = screen.colorDepth;
            components.screenAvailWidth = screen.availWidth;
            components.screenAvailHeight = screen.availHeight;
            components.devicePixelRatio = window.devicePixelRatio || 1;
            
            // Timezone
            components.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            components.timezoneOffset = new Date().getTimezoneOffset();
            
            // Canvas fingerprint
            components.canvas = await DemoFingerprint.getCanvasFingerprint();
            
            // WebGL fingerprint
            components.webgl = await DemoFingerprint.getWebGLFingerprint();
            
            // Audio fingerprint
            components.audio = await DemoFingerprint.getAudioFingerprint();
            
            // Font detection
            components.fonts = await DemoFingerprint.getInstalledFonts();
            
            // Touch support
            components.touchSupport = {
                maxTouchPoints: navigator.maxTouchPoints || 0,
                touchEvent: 'ontouchstart' in window,
                touchStart: 'createTouch' in document
            };
            
            // Generate hash
            const fingerprintString = JSON.stringify(components);
            components.hash = await DemoFingerprint.hashString(fingerprintString);
            
        } catch (e) {
            console.warn('Fingerprint generation error:', e);
            components.error = e.message;
        }
        
        return components;
    };

    /**
     * Canvas fingerprinting - unique rendering patterns
     */
    DemoFingerprint.getCanvasFingerprint = async function() {
        try {
            const canvas = document.createElement('canvas');
            canvas.width = 280;
            canvas.height = 60;
            const ctx = canvas.getContext('2d');
            
            // Draw complex shapes and text
            ctx.textBaseline = 'alphabetic';
            ctx.fillStyle = '#f60';
            ctx.fillRect(125, 1, 62, 20);
            
            ctx.fillStyle = '#069';
            ctx.font = '11pt Arial';
            ctx.fillText('PrizmAI Demo 🎨', 2, 15);
            
            ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
            ctx.font = '18pt Arial';
            ctx.fillText('Canvas FP', 4, 45);
            
            // Add gradient
            const gradient = ctx.createLinearGradient(0, 0, 280, 0);
            gradient.addColorStop(0, 'red');
            gradient.addColorStop(0.5, 'green');
            gradient.addColorStop(1, 'blue');
            ctx.fillStyle = gradient;
            ctx.fillRect(0, 50, 280, 10);
            
            // Get data URL and hash it
            const dataUrl = canvas.toDataURL();
            return await DemoFingerprint.hashString(dataUrl);
        } catch (e) {
            return 'canvas_not_supported';
        }
    };

    /**
     * WebGL fingerprinting - GPU and driver info
     */
    DemoFingerprint.getWebGLFingerprint = async function() {
        try {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            
            if (!gl) {
                return 'webgl_not_supported';
            }
            
            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            const vendor = debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : 'unknown';
            const renderer = debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : 'unknown';
            
            const info = {
                vendor: vendor,
                renderer: renderer,
                version: gl.getParameter(gl.VERSION),
                shadingLanguageVersion: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
                maxTextureSize: gl.getParameter(gl.MAX_TEXTURE_SIZE),
                maxViewportDims: gl.getParameter(gl.MAX_VIEWPORT_DIMS),
                extensions: gl.getSupportedExtensions() ? gl.getSupportedExtensions().length : 0
            };
            
            return await DemoFingerprint.hashString(JSON.stringify(info));
        } catch (e) {
            return 'webgl_error';
        }
    };

    /**
     * Audio fingerprinting - audio processing patterns
     */
    DemoFingerprint.getAudioFingerprint = async function() {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!AudioContext) {
                return 'audio_not_supported';
            }
            
            const context = new AudioContext();
            const oscillator = context.createOscillator();
            const analyser = context.createAnalyser();
            const gain = context.createGain();
            const processor = context.createScriptProcessor(4096, 1, 1);
            
            gain.gain.value = 0; // Mute
            oscillator.type = 'triangle';
            oscillator.frequency.value = 10000;
            
            oscillator.connect(analyser);
            analyser.connect(gain);
            gain.connect(context.destination);
            
            // Get frequency data
            const frequencyData = new Uint8Array(analyser.frequencyBinCount);
            analyser.getByteFrequencyData(frequencyData);
            
            context.close();
            
            // Hash the frequency data
            const sum = frequencyData.reduce((a, b) => a + b, 0);
            return 'audio_' + sum;
        } catch (e) {
            return 'audio_error';
        }
    };

    /**
     * Font detection - check for installed fonts
     */
    DemoFingerprint.getInstalledFonts = async function() {
        const baseFonts = ['monospace', 'sans-serif', 'serif'];
        const testFonts = [
            'Arial', 'Arial Black', 'Arial Narrow', 'Calibri', 'Cambria',
            'Comic Sans MS', 'Consolas', 'Courier', 'Courier New', 'Georgia',
            'Helvetica', 'Impact', 'Lucida Console', 'Lucida Sans Unicode',
            'Microsoft Sans Serif', 'Palatino Linotype', 'Segoe UI', 'Tahoma',
            'Times', 'Times New Roman', 'Trebuchet MS', 'Verdana',
            'Monaco', 'Menlo', 'Ubuntu', 'DejaVu Sans', 'Liberation Sans'
        ];
        
        const detectedFonts = [];
        
        try {
            const testString = 'mmmmmmmmmmlli';
            const testSize = '72px';
            
            const span = document.createElement('span');
            span.style.position = 'absolute';
            span.style.left = '-9999px';
            span.style.fontSize = testSize;
            span.innerHTML = testString;
            document.body.appendChild(span);
            
            // Get base widths
            const baseWidths = {};
            for (const baseFont of baseFonts) {
                span.style.fontFamily = baseFont;
                baseWidths[baseFont] = span.offsetWidth;
            }
            
            // Test each font
            for (const font of testFonts) {
                for (const baseFont of baseFonts) {
                    span.style.fontFamily = `'${font}', ${baseFont}`;
                    if (span.offsetWidth !== baseWidths[baseFont]) {
                        detectedFonts.push(font);
                        break;
                    }
                }
            }
            
            document.body.removeChild(span);
        } catch (e) {
            // Font detection failed
        }
        
        return detectedFonts.sort().join(',');
    };

    /**
     * Hash a string using SHA-256
     */
    DemoFingerprint.hashString = async function(str) {
        try {
            const encoder = new TextEncoder();
            const data = encoder.encode(str);
            const hashBuffer = await crypto.subtle.digest('SHA-256', data);
            const hashArray = Array.from(new Uint8Array(hashBuffer));
            return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        } catch (e) {
            // Fallback to simple hash
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
                const char = str.charCodeAt(i);
                hash = ((hash << 5) - hash) + char;
                hash = hash & hash;
            }
            return 'fallback_' + Math.abs(hash).toString(16);
        }
    };

    /**
     * Store fingerprint in localStorage (persists beyond cookies)
     */
    DemoFingerprint.store = function(fingerprint) {
        try {
            const data = {
                fingerprint: fingerprint.hash,
                timestamp: Date.now(),
                components: {
                    canvas: fingerprint.canvas,
                    webgl: fingerprint.webgl,
                    audio: fingerprint.audio
                }
            };
            localStorage.setItem('_pfp', JSON.stringify(data));
            
            // Also store in sessionStorage as backup
            sessionStorage.setItem('_pfp', JSON.stringify(data));
            
            // Store in IndexedDB for maximum persistence
            DemoFingerprint.storeInIndexedDB(data);
            
        } catch (e) {
            console.warn('Could not store fingerprint:', e);
        }
    };

    /**
     * Store in IndexedDB (most persistent)
     */
    DemoFingerprint.storeInIndexedDB = function(data) {
        try {
            const request = indexedDB.open('PrizmDemo', 1);
            
            request.onupgradeneeded = function(event) {
                const db = event.target.result;
                if (!db.objectStoreNames.contains('fingerprint')) {
                    db.createObjectStore('fingerprint', { keyPath: 'id' });
                }
            };
            
            request.onsuccess = function(event) {
                const db = event.target.result;
                const transaction = db.transaction(['fingerprint'], 'readwrite');
                const store = transaction.objectStore('fingerprint');
                store.put({ id: 'main', ...data });
            };
        } catch (e) {
            // IndexedDB not available
        }
    };

    /**
     * Retrieve stored fingerprint
     */
    DemoFingerprint.retrieve = function() {
        try {
            // Try localStorage first
            let data = localStorage.getItem('_pfp');
            if (data) {
                return JSON.parse(data);
            }
            
            // Try sessionStorage
            data = sessionStorage.getItem('_pfp');
            if (data) {
                return JSON.parse(data);
            }
            
            return null;
        } catch (e) {
            return null;
        }
    };

    /**
     * Initialize and send fingerprint to server
     */
    DemoFingerprint.init = async function() {
        // Check if we already have a stored fingerprint
        let storedFp = DemoFingerprint.retrieve();
        
        // Generate new fingerprint
        const fingerprint = await DemoFingerprint.generate();
        
        // Store it
        DemoFingerprint.store(fingerprint);
        
        // Track demo usage in localStorage (persists beyond session)
        DemoFingerprint.trackUsage();
        
        // Send to server
        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                              document.querySelector('meta[name="csrf-token"]')?.content;
            
            if (csrfToken) {
                fetch('/demo/fingerprint/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({
                        fingerprint: fingerprint.hash,
                        canvas: fingerprint.canvas,
                        webgl: fingerprint.webgl,
                        audio: fingerprint.audio,
                        storedFingerprint: storedFp?.fingerprint || null,
                        localUsage: DemoFingerprint.getLocalUsage()
                    })
                }).catch(e => console.warn('Could not send fingerprint:', e));
            }
        } catch (e) {
            console.warn('Fingerprint send error:', e);
        }
        
        return fingerprint;
    };

    /**
     * Track demo usage in localStorage (persists beyond cookies)
     */
    DemoFingerprint.trackUsage = function() {
        try {
            const usage = JSON.parse(localStorage.getItem('_pdemo') || '{}');
            
            if (!usage.firstVisit) {
                usage.firstVisit = Date.now();
            }
            usage.lastVisit = Date.now();
            usage.visitCount = (usage.visitCount || 0) + 1;
            usage.aiUsed = usage.aiUsed || 0;
            usage.projectsCreated = usage.projectsCreated || 0;
            usage.sessionsStarted = (usage.sessionsStarted || 0) + 1;
            
            localStorage.setItem('_pdemo', JSON.stringify(usage));
        } catch (e) {
            // localStorage not available
        }
    };

    /**
     * Increment AI usage counter
     */
    DemoFingerprint.incrementAIUsage = function() {
        try {
            const usage = JSON.parse(localStorage.getItem('_pdemo') || '{}');
            usage.aiUsed = (usage.aiUsed || 0) + 1;
            localStorage.setItem('_pdemo', JSON.stringify(usage));
            return usage.aiUsed;
        } catch (e) {
            return 0;
        }
    };

    /**
     * Increment project creation counter
     */
    DemoFingerprint.incrementProjectCount = function() {
        try {
            const usage = JSON.parse(localStorage.getItem('_pdemo') || '{}');
            usage.projectsCreated = (usage.projectsCreated || 0) + 1;
            localStorage.setItem('_pdemo', JSON.stringify(usage));
            return usage.projectsCreated;
        } catch (e) {
            return 0;
        }
    };

    /**
     * Get local usage stats
     */
    DemoFingerprint.getLocalUsage = function() {
        try {
            return JSON.parse(localStorage.getItem('_pdemo') || '{}');
        } catch (e) {
            return {};
        }
    };

    /**
     * Check if user has exceeded local limits
     * This is a client-side check (can be bypassed but adds friction)
     */
    DemoFingerprint.checkLocalLimits = function() {
        const usage = DemoFingerprint.getLocalUsage();
        
        const limits = {
            aiUsed: { current: usage.aiUsed || 0, max: 50, exceeded: false },
            projectsCreated: { current: usage.projectsCreated || 0, max: 5, exceeded: false },
            sessionsStarted: { current: usage.sessionsStarted || 0, max: 20, exceeded: false }
        };
        
        limits.aiUsed.exceeded = limits.aiUsed.current >= limits.aiUsed.max;
        limits.projectsCreated.exceeded = limits.projectsCreated.current >= limits.projectsCreated.max;
        limits.sessionsStarted.exceeded = limits.sessionsStarted.current >= limits.sessionsStarted.max;
        
        limits.anyExceeded = limits.aiUsed.exceeded || 
                             limits.projectsCreated.exceeded || 
                             limits.sessionsStarted.exceeded;
        
        return limits;
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => DemoFingerprint.init());
    } else {
        DemoFingerprint.init();
    }

})();
