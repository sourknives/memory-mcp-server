/**
 * Main application entry point for Cortex MCP Enhanced Web Interface
 * Initializes the application and coordinates all components
 */

// Main application namespace
window.CortexApp = {
    
    // Application configuration
    config: {
        version: '1.0.0',
        name: 'Cortex MCP Enhanced Web Interface',
        debug: false
    },

    // Application state
    initialized: false,
    startTime: null,

    /**
     * Initialize the application
     */
    async init() {
        if (this.initialized) {
            console.warn('Application already initialized');
            return;
        }

        this.startTime = performance.now();
        console.log(`Initializing ${this.config.name} v${this.config.version}...`);

        try {
            // Check browser compatibility
            this.checkBrowserCompatibility();

            // Initialize error handling
            this.setupErrorHandling();

            // Initialize API configuration
            this.initializeAPI();

            // Initialize UI
            await CortexUI.init();

            // Set up service worker (if available)
            this.setupServiceWorker();

            // Handle initial URL state
            this.handleInitialState();

            // Mark as initialized
            this.initialized = true;

            const initTime = performance.now() - this.startTime;
            console.log(`Application initialized successfully in ${initTime.toFixed(2)}ms`);

            // Show welcome message for first-time users
            this.showWelcomeMessage();

        } catch (error) {
            console.error('Failed to initialize application:', error);
            this.handleInitializationError(error);
        }
    },

    /**
     * Check browser compatibility
     */
    checkBrowserCompatibility() {
        const requiredFeatures = [
            'fetch',
            'Promise',
            'localStorage',
            'addEventListener',
            'querySelector'
        ];

        const missingFeatures = requiredFeatures.filter(feature => {
            return typeof window[feature] === 'undefined';
        });

        if (missingFeatures.length > 0) {
            throw new Error(`Browser missing required features: ${missingFeatures.join(', ')}`);
        }

        // Check for modern JavaScript features
        try {
            // Test arrow functions, const/let, template literals
            eval('const test = () => `test`; test();');
        } catch (error) {
            throw new Error('Browser does not support modern JavaScript features');
        }

        console.log('Browser compatibility check passed');
    },

    /**
     * Set up global error handling
     */
    setupErrorHandling() {
        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled promise rejection:', event.reason);
            
            if (CortexUI && CortexUI.showError) {
                CortexUI.showError('Unexpected Error', 'An unexpected error occurred. Please try refreshing the page.');
            }
            
            // Prevent the default browser error handling
            event.preventDefault();
        });

        // Handle JavaScript errors
        window.addEventListener('error', (event) => {
            console.error('JavaScript error:', {
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
                error: event.error
            });

            if (CortexUI && CortexUI.showError) {
                CortexUI.showError('Script Error', 'A script error occurred. Some features may not work correctly.');
            }
        });

        console.log('Error handling initialized');
    },

    /**
     * Initialize API configuration
     */
    initializeAPI() {
        // Set base URL based on current location
        const baseURL = window.location.origin;
        CortexAPI.config.baseURL = baseURL;

        // Add application-specific headers
        CortexAPI.config.headers['X-App-Version'] = this.config.version;
        CortexAPI.config.headers['X-App-Name'] = this.config.name;

        // Add request logging in debug mode
        if (this.config.debug) {
            CortexAPI.addRequestInterceptor(async (config, endpoint) => {
                console.log('API Request:', {
                    method: config.method,
                    endpoint: endpoint,
                    headers: config.headers
                });
                return config;
            });

            CortexAPI.addResponseInterceptor(async (response) => {
                console.log('API Response:', {
                    status: response.status,
                    success: response.success,
                    url: response.url
                });
                return response;
            });
        }

        console.log('API configuration initialized');
    },

    /**
     * Set up service worker for offline functionality
     */
    setupServiceWorker() {
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js')
                .then((registration) => {
                    console.log('Service Worker registered:', registration);
                })
                .catch((error) => {
                    console.log('Service Worker registration failed:', error);
                });
        }
    },

    /**
     * Handle initial application state from URL
     */
    handleInitialState() {
        const params = CortexUtils.getQueryParams();
        
        // Set initial tab from URL
        if (params.tab) {
            CortexUI.showTab(params.tab);
        }

        // Handle other URL parameters as needed
        if (params.debug === 'true') {
            this.config.debug = true;
            console.log('Debug mode enabled');
        }
    },

    /**
     * Show welcome message for new users
     */
    showWelcomeMessage() {
        const hasVisited = CortexUtils.storage.get('cortex_has_visited', false);
        
        if (!hasVisited) {
            setTimeout(() => {
                if (CortexUI && CortexUI.showToast) {
                    CortexUI.showToast(
                        'Welcome to Cortex MCP! Explore the tabs to manage your memories and projects.',
                        'info',
                        8000
                    );
                }
                CortexUtils.storage.set('cortex_has_visited', true);
            }, 1000);
        }
    },

    /**
     * Handle initialization errors
     * @param {Error} error - Initialization error
     */
    handleInitializationError(error) {
        // Show error message to user
        const errorContainer = document.createElement('div');
        errorContainer.className = 'init-error';
        errorContainer.innerHTML = `
            <div class="error-content">
                <h2>⚠️ Application Failed to Initialize</h2>
                <p>We're sorry, but the application failed to start properly.</p>
                <details>
                    <summary>Error Details</summary>
                    <pre>${error.message}</pre>
                </details>
                <div class="error-actions">
                    <button onclick="window.location.reload()" class="btn btn-primary">
                        Reload Page
                    </button>
                    <button onclick="this.clearStorage()" class="btn btn-secondary">
                        Clear Storage & Reload
                    </button>
                </div>
            </div>
        `;

        // Add error styles
        const style = document.createElement('style');
        style.textContent = `
            .init-error {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            .error-content {
                background: white;
                padding: 2rem;
                border-radius: 8px;
                max-width: 500px;
                text-align: center;
            }
            .error-content h2 {
                color: #dc3545;
                margin-bottom: 1rem;
            }
            .error-content details {
                text-align: left;
                margin: 1rem 0;
            }
            .error-content pre {
                background: #f8f9fa;
                padding: 1rem;
                border-radius: 4px;
                overflow: auto;
                font-size: 0.875rem;
            }
            .error-actions {
                display: flex;
                gap: 1rem;
                justify-content: center;
                margin-top: 1.5rem;
            }
            .btn {
                padding: 0.5rem 1rem;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: 500;
            }
            .btn-primary {
                background: #007bff;
                color: white;
            }
            .btn-secondary {
                background: #6c757d;
                color: white;
            }
        `;

        document.head.appendChild(style);
        document.body.appendChild(errorContainer);

        // Add clear storage function to window
        window.clearStorage = () => {
            try {
                localStorage.clear();
                sessionStorage.clear();
            } catch (e) {
                console.error('Failed to clear storage:', e);
            }
            window.location.reload();
        };
    },

    /**
     * Get application information
     * @returns {Object} Application info
     */
    getInfo() {
        return {
            name: this.config.name,
            version: this.config.version,
            initialized: this.initialized,
            startTime: this.startTime,
            uptime: this.startTime ? performance.now() - this.startTime : 0,
            userAgent: navigator.userAgent,
            url: window.location.href,
            timestamp: new Date().toISOString()
        };
    },

    /**
     * Enable debug mode
     */
    enableDebug() {
        this.config.debug = true;
        console.log('Debug mode enabled');
        CortexUtils.storage.set('cortex_debug', true);
    },

    /**
     * Disable debug mode
     */
    disableDebug() {
        this.config.debug = false;
        console.log('Debug mode disabled');
        CortexUtils.storage.remove('cortex_debug');
    },

    /**
     * Export application data for debugging
     * @returns {Object} Debug data
     */
    exportDebugData() {
        return {
            app: this.getInfo(),
            state: CortexUI.state,
            storage: {
                localStorage: { ...localStorage },
                sessionStorage: { ...sessionStorage }
            },
            performance: {
                navigation: performance.getEntriesByType('navigation')[0],
                memory: performance.memory
            }
        };
    }
};

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        CortexApp.init();
    });
} else {
    // DOM is already ready
    CortexApp.init();
}

// Make app available globally for debugging
window.CortexApp = CortexApp;

// Check for debug mode in storage
if (CortexUtils.storage.get('cortex_debug', false)) {
    CortexApp.config.debug = true;
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CortexApp;
}