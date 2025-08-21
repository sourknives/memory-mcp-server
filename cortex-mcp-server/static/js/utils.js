/**
 * Utility functions for the Cortex MCP Enhanced Web Interface
 * Provides common helper functions for data manipulation, validation, and formatting
 */

// Namespace for utility functions
window.CortexUtils = {
    
    /**
     * Debounce function to limit the rate of function calls
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @param {boolean} immediate - Whether to execute immediately
     * @returns {Function} Debounced function
     */
    debounce(func, wait, immediate = false) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func.apply(this, args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(this, args);
        };
    },

    /**
     * Enhanced debounce with cancellation support
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @param {Object} options - Options object
     * @returns {Function} Debounced function with cancel method
     */
    debouncedWithCancel(func, wait, options = {}) {
        const { leading = false, trailing = true, maxWait } = options;
        let timeout;
        let maxTimeout;
        let lastCallTime;
        let lastInvokeTime = 0;
        let lastArgs;
        let lastThis;
        let result;

        function invokeFunc(time) {
            const args = lastArgs;
            const thisArg = lastThis;
            lastArgs = lastThis = undefined;
            lastInvokeTime = time;
            result = func.apply(thisArg, args);
            return result;
        }

        function leadingEdge(time) {
            lastInvokeTime = time;
            timeout = setTimeout(timerExpired, wait);
            return leading ? invokeFunc(time) : result;
        }

        function remainingWait(time) {
            const timeSinceLastCall = time - lastCallTime;
            const timeSinceLastInvoke = time - lastInvokeTime;
            const timeWaiting = wait - timeSinceLastCall;
            return maxWait !== undefined
                ? Math.min(timeWaiting, maxWait - timeSinceLastInvoke)
                : timeWaiting;
        }

        function shouldInvoke(time) {
            const timeSinceLastCall = time - lastCallTime;
            const timeSinceLastInvoke = time - lastInvokeTime;
            return (lastCallTime === undefined || (timeSinceLastCall >= wait) ||
                    (timeSinceLastCall < 0) || (maxWait !== undefined && timeSinceLastInvoke >= maxWait));
        }

        function timerExpired() {
            const time = Date.now();
            if (shouldInvoke(time)) {
                return trailingEdge(time);
            }
            timeout = setTimeout(timerExpired, remainingWait(time));
        }

        function trailingEdge(time) {
            timeout = undefined;
            if (trailing && lastArgs) {
                return invokeFunc(time);
            }
            lastArgs = lastThis = undefined;
            return result;
        }

        function cancel() {
            if (timeout !== undefined) {
                clearTimeout(timeout);
            }
            if (maxTimeout !== undefined) {
                clearTimeout(maxTimeout);
            }
            lastInvokeTime = 0;
            lastArgs = lastCallTime = lastThis = timeout = maxTimeout = undefined;
        }

        function flush() {
            return timeout === undefined ? result : trailingEdge(Date.now());
        }

        function debounced(...args) {
            const time = Date.now();
            const isInvoking = shouldInvoke(time);

            lastArgs = args;
            lastThis = this;
            lastCallTime = time;

            if (isInvoking) {
                if (timeout === undefined) {
                    return leadingEdge(lastCallTime);
                }
                if (maxWait !== undefined) {
                    timeout = setTimeout(timerExpired, wait);
                    return invokeFunc(lastCallTime);
                }
            }
            if (timeout === undefined) {
                timeout = setTimeout(timerExpired, wait);
            }
            return result;
        }

        debounced.cancel = cancel;
        debounced.flush = flush;
        return debounced;
    },

    /**
     * Throttle function to limit function execution frequency
     * @param {Function} func - Function to throttle
     * @param {number} limit - Time limit in milliseconds
     * @returns {Function} Throttled function
     */
    throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    /**
     * Format date to human-readable string
     * @param {string|Date} date - Date to format
     * @param {Object} options - Formatting options
     * @returns {string} Formatted date string
     */
    formatDate(date, options = {}) {
        const dateObj = typeof date === 'string' ? new Date(date) : date;
        const defaultOptions = {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        };
        
        return dateObj.toLocaleDateString('en-US', { ...defaultOptions, ...options });
    },

    /**
     * Format relative time (e.g., "2 hours ago")
     * @param {string|Date} date - Date to format
     * @returns {string} Relative time string
     */
    formatRelativeTime(date) {
        const dateObj = typeof date === 'string' ? new Date(date) : date;
        const now = new Date();
        const diffInSeconds = Math.floor((now - dateObj) / 1000);

        if (diffInSeconds < 60) return 'Just now';
        if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} minutes ago`;
        if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`;
        if (diffInSeconds < 2592000) return `${Math.floor(diffInSeconds / 86400)} days ago`;
        
        return this.formatDate(dateObj);
    },

    /**
     * Truncate text to specified length with ellipsis
     * @param {string} text - Text to truncate
     * @param {number} maxLength - Maximum length
     * @param {string} suffix - Suffix to add (default: '...')
     * @returns {string} Truncated text
     */
    truncateText(text, maxLength, suffix = '...') {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength - suffix.length) + suffix;
    },

    /**
     * Escape HTML to prevent XSS attacks
     * @param {string} text - Text to escape
     * @returns {string} Escaped HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Generate a unique ID
     * @param {string} prefix - Optional prefix
     * @returns {string} Unique ID
     */
    generateId(prefix = 'id') {
        return `${prefix}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    },

    /**
     * Deep clone an object
     * @param {Object} obj - Object to clone
     * @returns {Object} Cloned object
     */
    deepClone(obj) {
        if (obj === null || typeof obj !== 'object') return obj;
        if (obj instanceof Date) return new Date(obj.getTime());
        if (obj instanceof Array) return obj.map(item => this.deepClone(item));
        if (typeof obj === 'object') {
            const clonedObj = {};
            for (const key in obj) {
                if (obj.hasOwnProperty(key)) {
                    clonedObj[key] = this.deepClone(obj[key]);
                }
            }
            return clonedObj;
        }
    },

    /**
     * Validate email format
     * @param {string} email - Email to validate
     * @returns {boolean} Whether email is valid
     */
    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    },

    /**
     * Validate JSON string
     * @param {string} jsonString - JSON string to validate
     * @returns {boolean} Whether JSON is valid
     */
    isValidJson(jsonString) {
        try {
            JSON.parse(jsonString);
            return true;
        } catch {
            return false;
        }
    },

    /**
     * Format file size in human-readable format
     * @param {number} bytes - Size in bytes
     * @param {number} decimals - Number of decimal places
     * @returns {string} Formatted size
     */
    formatFileSize(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    },

    /**
     * Format number with thousands separators
     * @param {number} num - Number to format
     * @returns {string} Formatted number
     */
    formatNumber(num) {
        return new Intl.NumberFormat().format(num);
    },

    /**
     * Get query parameters from URL
     * @param {string} url - URL to parse (optional, defaults to current URL)
     * @returns {Object} Query parameters object
     */
    getQueryParams(url = window.location.href) {
        const params = {};
        const urlObj = new URL(url);
        
        for (const [key, value] of urlObj.searchParams) {
            params[key] = value;
        }
        
        return params;
    },

    /**
     * Set query parameters in URL
     * @param {Object} params - Parameters to set
     * @param {boolean} replace - Whether to replace current state
     */
    setQueryParams(params, replace = false) {
        const url = new URL(window.location);
        
        Object.keys(params).forEach(key => {
            if (params[key] !== null && params[key] !== undefined) {
                url.searchParams.set(key, params[key]);
            } else {
                url.searchParams.delete(key);
            }
        });
        
        if (replace) {
            window.history.replaceState({}, '', url);
        } else {
            window.history.pushState({}, '', url);
        }
    },

    /**
     * Copy text to clipboard
     * @param {string} text - Text to copy
     * @returns {Promise<boolean>} Success status
     */
    async copyToClipboard(text) {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
                return true;
            } else {
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                
                const success = document.execCommand('copy');
                textArea.remove();
                return success;
            }
        } catch (error) {
            console.error('Failed to copy text:', error);
            return false;
        }
    },

    /**
     * Download data as file
     * @param {string} data - Data to download
     * @param {string} filename - File name
     * @param {string} type - MIME type
     */
    downloadFile(data, filename, type = 'text/plain') {
        const blob = new Blob([data], { type });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        window.URL.revokeObjectURL(url);
    },

    /**
     * Check if element is in viewport
     * @param {Element} element - Element to check
     * @param {number} threshold - Threshold percentage (0-1)
     * @returns {boolean} Whether element is in viewport
     */
    isInViewport(element, threshold = 0) {
        const rect = element.getBoundingClientRect();
        const windowHeight = window.innerHeight || document.documentElement.clientHeight;
        const windowWidth = window.innerWidth || document.documentElement.clientWidth;
        
        const vertInView = (rect.top <= windowHeight * (1 - threshold)) && 
                          ((rect.top + rect.height) >= windowHeight * threshold);
        const horInView = (rect.left <= windowWidth * (1 - threshold)) && 
                         ((rect.left + rect.width) >= windowWidth * threshold);
        
        return vertInView && horInView;
    },

    /**
     * Smooth scroll to element
     * @param {Element|string} target - Element or selector to scroll to
     * @param {Object} options - Scroll options
     */
    scrollToElement(target, options = {}) {
        const element = typeof target === 'string' ? document.querySelector(target) : target;
        if (!element) return;
        
        const defaultOptions = {
            behavior: 'smooth',
            block: 'start',
            inline: 'nearest'
        };
        
        element.scrollIntoView({ ...defaultOptions, ...options });
    },

    /**
     * Local storage wrapper with error handling
     */
    storage: {
        /**
         * Get item from localStorage
         * @param {string} key - Storage key
         * @param {*} defaultValue - Default value if key doesn't exist
         * @returns {*} Stored value or default
         */
        get(key, defaultValue = null) {
            try {
                const item = localStorage.getItem(key);
                return item ? JSON.parse(item) : defaultValue;
            } catch (error) {
                console.error('Error reading from localStorage:', error);
                return defaultValue;
            }
        },

        /**
         * Set item in localStorage
         * @param {string} key - Storage key
         * @param {*} value - Value to store
         * @returns {boolean} Success status
         */
        set(key, value) {
            try {
                localStorage.setItem(key, JSON.stringify(value));
                return true;
            } catch (error) {
                console.error('Error writing to localStorage:', error);
                return false;
            }
        },

        /**
         * Remove item from localStorage
         * @param {string} key - Storage key
         * @returns {boolean} Success status
         */
        remove(key) {
            try {
                localStorage.removeItem(key);
                return true;
            } catch (error) {
                console.error('Error removing from localStorage:', error);
                return false;
            }
        },

        /**
         * Clear all localStorage
         * @returns {boolean} Success status
         */
        clear() {
            try {
                localStorage.clear();
                return true;
            } catch (error) {
                console.error('Error clearing localStorage:', error);
                return false;
            }
        }
    },

    /**
     * Performance monitoring utilities
     */
    performance: {
        /**
         * Measure function execution time
         * @param {Function} func - Function to measure
         * @param {string} name - Performance mark name
         * @returns {Function} Wrapped function
         */
        measure(func, name) {
            return function(...args) {
                const startMark = `${name}-start`;
                const endMark = `${name}-end`;
                const measureName = `${name}-duration`;
                
                performance.mark(startMark);
                const result = func.apply(this, args);
                
                if (result instanceof Promise) {
                    return result.finally(() => {
                        performance.mark(endMark);
                        performance.measure(measureName, startMark, endMark);
                    });
                } else {
                    performance.mark(endMark);
                    performance.measure(measureName, startMark, endMark);
                    return result;
                }
            };
        },

        /**
         * Get performance metrics
         * @param {string} name - Metric name
         * @returns {Array} Performance entries
         */
        getMetrics(name) {
            return performance.getEntriesByName(name);
        },

        /**
         * Clear performance metrics
         * @param {string} name - Metric name (optional)
         */
        clearMetrics(name) {
            if (name) {
                performance.clearMeasures(name);
                performance.clearMarks(`${name}-start`);
                performance.clearMarks(`${name}-end`);
            } else {
                performance.clearMeasures();
                performance.clearMarks();
            }
        }
    },

    /**
     * Virtual scrolling utilities for large datasets
     */
    virtualScroll: {
        /**
         * Create virtual scroll container
         * @param {Object} options - Configuration options
         * @returns {Object} Virtual scroll instance
         */
        create(options) {
            const {
                container,
                itemHeight,
                items,
                renderItem,
                overscan = 5
            } = options;

            let scrollTop = 0;
            let containerHeight = container.clientHeight;
            
            const totalHeight = items.length * itemHeight;
            const visibleCount = Math.ceil(containerHeight / itemHeight);
            
            function getVisibleRange() {
                const start = Math.floor(scrollTop / itemHeight);
                const end = Math.min(start + visibleCount + overscan, items.length);
                return { start: Math.max(0, start - overscan), end };
            }

            function render() {
                const { start, end } = getVisibleRange();
                const visibleItems = items.slice(start, end);
                
                container.innerHTML = '';
                container.style.height = `${totalHeight}px`;
                container.style.position = 'relative';
                
                visibleItems.forEach((item, index) => {
                    const element = renderItem(item, start + index);
                    element.style.position = 'absolute';
                    element.style.top = `${(start + index) * itemHeight}px`;
                    element.style.height = `${itemHeight}px`;
                    container.appendChild(element);
                });
            }

            function handleScroll() {
                scrollTop = container.scrollTop;
                render();
            }

            container.addEventListener('scroll', CortexUtils.throttle(handleScroll, 16));
            
            // Initial render
            render();

            return {
                update(newItems) {
                    items.splice(0, items.length, ...newItems);
                    render();
                },
                destroy() {
                    container.removeEventListener('scroll', handleScroll);
                }
            };
        }
    },

    /**
     * Lazy loading utilities
     */
    lazyLoad: {
        /**
         * Create intersection observer for lazy loading
         * @param {Object} options - Configuration options
         * @returns {IntersectionObserver} Observer instance
         */
        createObserver(options = {}) {
            const {
                threshold = 0.1,
                rootMargin = '50px',
                onIntersect
            } = options;

            return new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        onIntersect(entry.target);
                    }
                });
            }, { threshold, rootMargin });
        },

        /**
         * Lazy load images
         * @param {string} selector - Image selector
         */
        images(selector = 'img[data-src]') {
            const observer = this.createObserver({
                onIntersect: (img) => {
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                    observer.unobserve(img);
                }
            });

            document.querySelectorAll(selector).forEach(img => {
                observer.observe(img);
            });

            return observer;
        }
    },

    /**
     * Memory management utilities
     */
    memory: {
        /**
         * Clean up event listeners and references
         * @param {Object} component - Component to clean up
         */
        cleanup(component) {
            if (component.eventListeners) {
                component.eventListeners.forEach(({ element, event, handler }) => {
                    element.removeEventListener(event, handler);
                });
                component.eventListeners.clear();
            }
            
            if (component.intervals) {
                component.intervals.forEach(clearInterval);
                component.intervals.clear();
            }
            
            if (component.timeouts) {
                component.timeouts.forEach(clearTimeout);
                component.timeouts.clear();
            }
        },

        /**
         * Monitor memory usage
         * @returns {Object} Memory info
         */
        getUsage() {
            if (performance.memory) {
                return {
                    used: performance.memory.usedJSHeapSize,
                    total: performance.memory.totalJSHeapSize,
                    limit: performance.memory.jsHeapSizeLimit
                };
            }
            return null;
        }
    }
};

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CortexUtils;
}