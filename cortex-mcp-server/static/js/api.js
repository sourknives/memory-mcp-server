/**
 * API communication layer for Cortex MCP Enhanced Web Interface
 * Handles all HTTP requests with error handling, retry logic, and state management
 */

// Namespace for API functions
window.CortexAPI = {
    
    // Configuration
    config: {
        baseURL: '',
        timeout: 30000,
        retryAttempts: 3,
        retryDelay: 1000,
        headers: {
            'Content-Type': 'application/json'
        }
    },

    // Request interceptors
    requestInterceptors: [],
    responseInterceptors: [],

    // Intelligent caching system
    cache: {
        store: new Map(),
        maxSize: 100,
        defaultTTL: 5 * 60 * 1000, // 5 minutes
        
        /**
         * Generate cache key from request
         * @param {string} method - HTTP method
         * @param {string} endpoint - API endpoint
         * @param {Object} data - Request data
         * @returns {string} Cache key
         */
        generateKey(method, endpoint, data = null) {
            const key = `${method}:${endpoint}`;
            if (data && method !== 'GET') {
                return `${key}:${JSON.stringify(data)}`;
            }
            return key;
        },

        /**
         * Get cached response
         * @param {string} key - Cache key
         * @returns {Object|null} Cached response or null
         */
        get(key) {
            const entry = this.store.get(key);
            if (!entry) return null;
            
            if (Date.now() > entry.expires) {
                this.store.delete(key);
                return null;
            }
            
            return entry.data;
        },

        /**
         * Set cached response
         * @param {string} key - Cache key
         * @param {Object} data - Response data
         * @param {number} ttl - Time to live in milliseconds
         */
        set(key, data, ttl = this.defaultTTL) {
            // Implement LRU eviction if cache is full
            if (this.store.size >= this.maxSize) {
                const firstKey = this.store.keys().next().value;
                this.store.delete(firstKey);
            }
            
            this.store.set(key, {
                data: CortexUtils.deepClone(data),
                expires: Date.now() + ttl,
                timestamp: Date.now()
            });
        },

        /**
         * Clear cache entries
         * @param {string} pattern - Pattern to match (optional)
         */
        clear(pattern = null) {
            if (!pattern) {
                this.store.clear();
                return;
            }
            
            const regex = new RegExp(pattern);
            for (const key of this.store.keys()) {
                if (regex.test(key)) {
                    this.store.delete(key);
                }
            }
        },

        /**
         * Get cache statistics
         * @returns {Object} Cache stats
         */
        getStats() {
            const entries = Array.from(this.store.values());
            const now = Date.now();
            const expired = entries.filter(entry => now > entry.expires).length;
            
            return {
                size: this.store.size,
                maxSize: this.maxSize,
                expired,
                hitRate: this.hitCount / (this.hitCount + this.missCount) || 0
            };
        },

        hitCount: 0,
        missCount: 0
    },

    /**
     * Add request interceptor
     * @param {Function} interceptor - Function to modify request
     */
    addRequestInterceptor(interceptor) {
        this.requestInterceptors.push(interceptor);
    },

    /**
     * Add response interceptor
     * @param {Function} interceptor - Function to modify response
     */
    addResponseInterceptor(interceptor) {
        this.responseInterceptors.push(interceptor);
    },

    /**
     * Create AbortController for request cancellation
     * @returns {AbortController} Abort controller
     */
    createAbortController() {
        return new AbortController();
    },

    /**
     * Make HTTP request with comprehensive error handling and caching
     * @param {string} method - HTTP method
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Request options
     * @returns {Promise<Object>} API response
     */
    async request(method, endpoint, options = {}) {
        const {
            data = null,
            headers = {},
            timeout = this.config.timeout,
            retryAttempts = this.config.retryAttempts,
            retryDelay = this.config.retryDelay,
            abortController = null,
            useCache = true,
            cacheTTL = this.cache.defaultTTL
        } = options;

        // Check cache for GET requests
        if (method.toUpperCase() === 'GET' && useCache) {
            const cacheKey = this.cache.generateKey(method, endpoint, data);
            const cachedResponse = this.cache.get(cacheKey);
            
            if (cachedResponse) {
                this.cache.hitCount++;
                return cachedResponse;
            }
            this.cache.missCount++;
        }

        // Prepare request configuration
        const requestConfig = {
            method: method.toUpperCase(),
            headers: {
                ...this.config.headers,
                ...headers
            },
            signal: abortController?.signal
        };

        // Add body for non-GET requests
        if (data && method.toUpperCase() !== 'GET') {
            requestConfig.body = typeof data === 'string' ? data : JSON.stringify(data);
        }

        // Apply request interceptors
        let finalConfig = requestConfig;
        for (const interceptor of this.requestInterceptors) {
            finalConfig = await interceptor(finalConfig, endpoint);
        }

        // Retry logic
        let lastError;
        for (let attempt = 0; attempt <= retryAttempts; attempt++) {
            try {
                // Set timeout
                const timeoutPromise = new Promise((_, reject) => {
                    setTimeout(() => reject(new Error('Request timeout')), timeout);
                });

                // Make request
                const requestPromise = fetch(this.config.baseURL + endpoint, finalConfig);
                const response = await Promise.race([requestPromise, timeoutPromise]);

                // Check if request was aborted
                if (abortController?.signal.aborted) {
                    throw new Error('Request was cancelled');
                }

                // Parse response
                let responseData;
                const contentType = response.headers.get('content-type');
                
                if (contentType && contentType.includes('application/json')) {
                    responseData = await response.json();
                } else {
                    responseData = await response.text();
                }

                // Create response object
                const apiResponse = {
                    success: response.ok,
                    status: response.status,
                    statusText: response.statusText,
                    data: responseData,
                    headers: Object.fromEntries(response.headers.entries()),
                    url: response.url
                };

                // Apply response interceptors
                let finalResponse = apiResponse;
                for (const interceptor of this.responseInterceptors) {
                    finalResponse = await interceptor(finalResponse);
                }

                // Handle HTTP errors
                if (!response.ok) {
                    const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
                    error.response = finalResponse;
                    error.status = response.status;
                    throw error;
                }

                // Cache successful GET responses
                if (method.toUpperCase() === 'GET' && useCache && response.ok) {
                    const cacheKey = this.cache.generateKey(method, endpoint, data);
                    this.cache.set(cacheKey, finalResponse, cacheTTL);
                }

                return finalResponse;

            } catch (error) {
                lastError = error;
                
                // Don't retry on certain errors
                if (error.name === 'AbortError' || 
                    error.message === 'Request was cancelled' ||
                    (error.status && error.status < 500)) {
                    break;
                }

                // Wait before retry (except on last attempt)
                if (attempt < retryAttempts) {
                    await new Promise(resolve => setTimeout(resolve, retryDelay * (attempt + 1)));
                }
            }
        }

        // All attempts failed
        throw lastError;
    },

    /**
     * GET request
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Request options
     * @returns {Promise<Object>} API response
     */
    async get(endpoint, options = {}) {
        return this.request('GET', endpoint, options);
    },

    /**
     * POST request
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request data
     * @param {Object} options - Request options
     * @returns {Promise<Object>} API response
     */
    async post(endpoint, data = null, options = {}) {
        return this.request('POST', endpoint, { ...options, data });
    },

    /**
     * PUT request
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request data
     * @param {Object} options - Request options
     * @returns {Promise<Object>} API response
     */
    async put(endpoint, data = null, options = {}) {
        return this.request('PUT', endpoint, { ...options, data });
    },

    /**
     * DELETE request
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Request options
     * @returns {Promise<Object>} API response
     */
    async delete(endpoint, options = {}) {
        return this.request('DELETE', endpoint, options);
    },

    /**
     * PATCH request
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request data
     * @param {Object} options - Request options
     * @returns {Promise<Object>} API response
     */
    async patch(endpoint, data = null, options = {}) {
        return this.request('PATCH', endpoint, { ...options, data });
    },

    // Specific API endpoints for Cortex MCP

    /**
     * Health check
     * @returns {Promise<Object>} Health status
     */
    async getHealth() {
        return this.get('/health');
    },

    /**
     * Get database statistics
     * @returns {Promise<Object>} Database stats
     */
    async getStats() {
        return this.get('/stats');
    },

    /**
     * Get all projects
     * @param {Object} params - Query parameters
     * @returns {Promise<Object>} Projects list
     */
    async getProjects(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = queryString ? `/projects?${queryString}` : '/projects';
        return this.get(endpoint);
    },

    /**
     * Create new project
     * @param {Object} projectData - Project data
     * @returns {Promise<Object>} Created project
     */
    async createProject(projectData) {
        return this.post('/projects', projectData);
    },

    /**
     * Get project by ID
     * @param {string} projectId - Project ID
     * @returns {Promise<Object>} Project details
     */
    async getProject(projectId) {
        return this.get(`/projects/${projectId}`);
    },

    /**
     * Update project
     * @param {string} projectId - Project ID
     * @param {Object} updateData - Update data
     * @returns {Promise<Object>} Updated project
     */
    async updateProject(projectId, updateData) {
        return this.put(`/projects/${projectId}`, updateData);
    },

    /**
     * Delete project
     * @param {string} projectId - Project ID
     * @returns {Promise<Object>} Deletion result
     */
    async deleteProject(projectId) {
        return this.delete(`/projects/${projectId}`);
    },

    /**
     * Get conversations/memories
     * @param {Object} params - Query parameters
     * @returns {Promise<Object>} Conversations list
     */
    async getConversations(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = queryString ? `/conversations?${queryString}` : '/conversations';
        return this.get(endpoint);
    },

    /**
     * Create new conversation/memory
     * @param {Object} conversationData - Conversation data
     * @returns {Promise<Object>} Created conversation
     */
    async createConversation(conversationData) {
        return this.post('/conversations', conversationData);
    },

    /**
     * Get conversation by ID
     * @param {string} conversationId - Conversation ID
     * @returns {Promise<Object>} Conversation details
     */
    async getConversation(conversationId) {
        return this.get(`/conversations/${conversationId}`);
    },

    /**
     * Update conversation
     * @param {string} conversationId - Conversation ID
     * @param {Object} updateData - Update data
     * @returns {Promise<Object>} Updated conversation
     */
    async updateConversation(conversationId, updateData) {
        return this.put(`/conversations/${conversationId}`, updateData);
    },

    /**
     * Delete conversation
     * @param {string} conversationId - Conversation ID
     * @returns {Promise<Object>} Deletion result
     */
    async deleteConversation(conversationId) {
        return this.delete(`/conversations/${conversationId}`);
    },

    /**
     * Search memories using context search endpoint
     * @param {Object} searchParams - Search parameters
     * @returns {Promise<Object>} Search results
     */
    async searchMemories(searchParams) {
        return this.post('/context/search', searchParams);
    },

    /**
     * Get preferences
     * @returns {Promise<Object>} Preferences list
     */
    async getPreferences() {
        return this.get('/preferences');
    },

    /**
     * Set preference
     * @param {Object} preferenceData - Preference data
     * @returns {Promise<Object>} Set preference result
     */
    async setPreference(preferenceData) {
        return this.post('/preferences', preferenceData);
    },

    /**
     * Delete preference
     * @param {string} key - Preference key
     * @returns {Promise<Object>} Deletion result
     */
    async deletePreference(key) {
        return this.delete(`/preferences/${encodeURIComponent(key)}`);
    },

    /**
     * Get monitoring data
     * @param {string} type - Monitoring type (optional)
     * @returns {Promise<Object>} Monitoring data
     */
    async getMonitoring(type = '') {
        const endpoint = type ? `/monitoring/${type}` : '/monitoring';
        return this.get(endpoint);
    },

    /**
     * Get project context
     * @param {string} projectId - Project ID
     * @param {Object} params - Query parameters
     * @returns {Promise<Object>} Project context
     */
    async getProjectContext(projectId, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const endpoint = queryString ? 
            `/projects/${projectId}/context?${queryString}` : 
            `/projects/${projectId}/context`;
        return this.get(endpoint);
    },

    /**
     * Get conversation history
     * @param {Object} historyParams - History parameters
     * @returns {Promise<Object>} Conversation history
     */
    async getConversationHistory(historyParams) {
        return this.post('/conversations/history', historyParams);
    },

    /**
     * Get monitoring data
     * @param {string} endpoint - Specific monitoring endpoint
     * @returns {Promise<Object>} Monitoring data
     */
    async getMonitoringData(endpoint = '') {
        const path = endpoint ? `/monitoring/${endpoint}` : '/monitoring/health';
        return this.get(path);
    },

    /**
     * Get storage information
     * @returns {Promise<Object>} Storage information
     */
    async getStorageInfo() {
        return this.get('/monitoring/storage');
    },

    /**
     * Get performance metrics
     * @param {number} hours - Hours to analyze
     * @returns {Promise<Object>} Performance metrics
     */
    async getPerformanceMetrics(hours = 24) {
        return this.get(`/monitoring/performance?hours=${hours}`);
    },

    // Database Maintenance API Methods

    /**
     * Run database integrity check
     * @param {boolean} autoFix - Whether to automatically fix issues
     * @returns {Promise<Object>} Integrity check results
     */
    async runIntegrityCheck(autoFix = false) {
        return this.post('/database/integrity-check', { auto_fix: autoFix });
    },

    /**
     * Run database cleanup
     * @param {boolean} dryRun - Whether to run in dry-run mode
     * @returns {Promise<Object>} Cleanup results
     */
    async runDatabaseCleanup(dryRun = false) {
        return this.post('/database/cleanup', { dry_run: dryRun });
    },

    /**
     * Export database data
     * @param {boolean} includeEmbeddings - Whether to include embeddings
     * @param {boolean} compress - Whether to compress the export
     * @returns {Promise<Object>} Export results
     */
    async exportDatabase(includeEmbeddings = false, compress = true) {
        return this.post('/database/export', { 
            include_embeddings: includeEmbeddings,
            compress: compress
        });
    },

    /**
     * Import database data
     * @param {string} importFile - Path to import file
     * @param {boolean} overwriteExisting - Whether to overwrite existing data
     * @param {Object} selectiveImport - What data types to import
     * @returns {Promise<Object>} Import results
     */
    async importDatabase(importFile, overwriteExisting = false, selectiveImport = null) {
        return this.post('/database/import', {
            import_file: importFile,
            overwrite_existing: overwriteExisting,
            selective_import: selectiveImport
        });
    },

    /**
     * Get maintenance operation history
     * @param {number} limit - Number of operations to retrieve
     * @returns {Promise<Object>} Maintenance history
     */
    async getMaintenanceHistory(limit = 50) {
        return this.get(`/database/maintenance-history?limit=${limit}`);
    },

    /**
     * Download export file
     * @param {string} filename - Name of the file to download
     * @returns {Promise<Blob>} File blob for download
     */
    async downloadExportFile(filename) {
        const response = await fetch(`${this.config.baseURL}/database/download/${filename}`, {
            method: 'GET',
            headers: {
                ...this.config.headers
            }
        });

        if (!response.ok) {
            throw new Error(`Download failed: ${response.statusText}`);
        }

        return response.blob();
    },

    // API Key Management Methods

    /**
     * Get all API keys
     * @returns {Promise<Object>} List of API keys
     */
    async getApiKeys() {
        return this.get('/api-keys');
    },

    /**
     * Create new API key
     * @param {Object} keyData - API key creation data
     * @returns {Promise<Object>} Created API key with actual key value
     */
    async createApiKey(keyData) {
        return this.post('/api-keys', keyData);
    },

    /**
     * Get specific API key by ID
     * @param {string} keyId - API key ID
     * @returns {Promise<Object>} API key details
     */
    async getApiKey(keyId) {
        return this.get(`/api-keys/${keyId}`);
    },

    /**
     * Update API key
     * @param {string} keyId - API key ID
     * @param {Object} updateData - Update data
     * @returns {Promise<Object>} Updated API key
     */
    async updateApiKey(keyId, updateData) {
        return this.put(`/api-keys/${keyId}`, updateData);
    },

    /**
     * Delete API key
     * @param {string} keyId - API key ID
     * @returns {Promise<Object>} Deletion result
     */
    async deleteApiKey(keyId) {
        return this.delete(`/api-keys/${keyId}`);
    },

    /**
     * Deactivate API key (soft delete)
     * @param {string} keyId - API key ID
     * @returns {Promise<Object>} Deactivation result
     */
    async deactivateApiKey(keyId) {
        return this.post(`/api-keys/${keyId}/deactivate`);
    },

    /**
     * Rotate API key (generate new key)
     * @param {string} keyId - API key ID
     * @returns {Promise<Object>} New API key with actual key value
     */
    async rotateApiKey(keyId) {
        return this.post(`/api-keys/${keyId}/rotate`);
    },

    // Request batching and optimization
    batch: {
        queue: [],
        processing: false,
        batchSize: 10,
        batchDelay: 100,

        /**
         * Add request to batch queue
         * @param {Object} requestConfig - Request configuration
         * @returns {Promise} Request promise
         */
        add(requestConfig) {
            return new Promise((resolve, reject) => {
                this.queue.push({
                    ...requestConfig,
                    resolve,
                    reject
                });

                if (!this.processing) {
                    this.process();
                }
            });
        },

        /**
         * Process batch queue
         */
        async process() {
            if (this.processing || this.queue.length === 0) return;
            
            this.processing = true;
            
            while (this.queue.length > 0) {
                const batch = this.queue.splice(0, this.batchSize);
                
                try {
                    await Promise.all(
                        batch.map(async (request) => {
                            try {
                                const response = await CortexAPI.request(
                                    request.method,
                                    request.endpoint,
                                    request.options
                                );
                                request.resolve(response);
                            } catch (error) {
                                request.reject(error);
                            }
                        })
                    );
                } catch (error) {
                    console.error('Batch processing error:', error);
                }
                
                // Small delay between batches
                if (this.queue.length > 0) {
                    await new Promise(resolve => setTimeout(resolve, this.batchDelay));
                }
            }
            
            this.processing = false;
        }
    },

    // Performance monitoring
    performance: {
        metrics: new Map(),
        
        /**
         * Record request performance
         * @param {string} endpoint - API endpoint
         * @param {number} duration - Request duration
         * @param {boolean} success - Whether request was successful
         */
        record(endpoint, duration, success) {
            const key = endpoint;
            const existing = this.metrics.get(key) || {
                count: 0,
                totalDuration: 0,
                successCount: 0,
                errorCount: 0,
                averageDuration: 0
            };
            
            existing.count++;
            existing.totalDuration += duration;
            existing.averageDuration = existing.totalDuration / existing.count;
            
            if (success) {
                existing.successCount++;
            } else {
                existing.errorCount++;
            }
            
            this.metrics.set(key, existing);
        },

        /**
         * Get performance metrics
         * @param {string} endpoint - Specific endpoint (optional)
         * @returns {Object} Performance metrics
         */
        getMetrics(endpoint = null) {
            if (endpoint) {
                return this.metrics.get(endpoint) || null;
            }
            
            const allMetrics = {};
            for (const [key, value] of this.metrics) {
                allMetrics[key] = value;
            }
            return allMetrics;
        },

        /**
         * Clear performance metrics
         */
        clear() {
            this.metrics.clear();
        }
    }
};

// Add default error handling interceptor
CortexAPI.addResponseInterceptor(async (response) => {
    // Log errors for debugging
    if (!response.success) {
        console.error('API Error:', {
            status: response.status,
            statusText: response.statusText,
            url: response.url,
            data: response.data
        });
    }
    
    return response;
});

// Add authentication interceptor if API key is available
CortexAPI.addRequestInterceptor(async (config, endpoint) => {
    // Check for stored API key
    const apiKey = CortexUtils.storage.get('cortex_api_key');
    if (apiKey) {
        config.headers['Authorization'] = `Bearer ${apiKey}`;
    }
    
    return config;
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CortexAPI;
}