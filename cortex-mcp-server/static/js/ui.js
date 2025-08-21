/**
 * UI management and state handling for Cortex MCP Enhanced Web Interface
 * Handles DOM manipulation, component rendering, and user interactions
 */

// Namespace for UI functions
const CortexUI = {
    
    // Application state
    state: {
        currentTab: 'dashboard',
        loading: false,
        projects: [],
        memories: [],
        preferences: {},
        connectionStatus: 'connected',
        lastUpdate: null,
        autoRefreshEnabled: true,
        previousMetrics: {},
        apiKeys: [],
        showInactiveApiKeys: false
    },

    // API testing state
    apiTestingState: {
        requestHistory: [],
        currentRequest: {
            method: 'GET',
            endpoint: '',
            headers: {},
            body: ''
        },
        response: null,
        loading: false
    },

    // Event listeners registry
    eventListeners: new Map(),

    // Performance optimization settings
    performance: {
        enableVirtualScrolling: true,
        enableLazyLoading: true,
        enableDebouncing: true,
        debounceDelay: 300,
        virtualScrollItemHeight: 80,
        lazyLoadThreshold: 0.1,
        maxRenderItems: 50
    },

    // Component lazy loading registry
    lazyComponents: new Map(),

    /**
     * Initialize the UI
     */
    async init() {
        console.log('Initializing Cortex UI...');
        
        try {
            // Set up event listeners
            this.setupEventListeners();
            
            // Initialize components
            this.initializeComponents();
            
            // Load initial data
            await this.loadInitialData();
            
            // Set up periodic updates
            this.setupPeriodicUpdates();
            
            console.log('Cortex UI initialized successfully');
        } catch (error) {
            console.error('Failed to initialize UI:', error);
            this.showError('Failed to initialize application', error.message);
        }
    },

    /**
     * Set up event listeners with performance optimizations
     */
    setupEventListeners() {
        // Tab navigation with debouncing
        const debouncedTabSwitch = CortexUtils.debounce((tabName) => {
            this.showTab(tabName);
        }, 100);

        document.querySelectorAll('.nav-tab').forEach(tab => {
            const handler = (e) => {
                const tabName = e.currentTarget.dataset.tab;
                debouncedTabSwitch(tabName);
            };
            tab.addEventListener('click', handler);
            this.eventListeners.set(`tab-${tab.dataset.tab}`, { element: tab, event: 'click', handler });
        });

        // Refresh button with throttling
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            const throttledRefresh = CortexUtils.throttle(() => this.refreshData(), 2000);
            refreshBtn.addEventListener('click', throttledRefresh);
            this.eventListeners.set('refresh-btn', { element: refreshBtn, event: 'click', handler: throttledRefresh });
        }

        // Auto-refresh toggle
        const autoRefreshToggle = document.getElementById('auto-refresh-toggle');
        if (autoRefreshToggle) {
            const handler = (e) => this.toggleAutoRefresh(e.target.checked);
            autoRefreshToggle.addEventListener('change', handler);
            this.eventListeners.set('auto-refresh-toggle', { element: autoRefreshToggle, event: 'change', handler });
        }

        // Window events
        const onlineHandler = () => this.updateConnectionStatus('connected');
        const offlineHandler = () => this.updateConnectionStatus('disconnected');
        window.addEventListener('online', onlineHandler);
        window.addEventListener('offline', offlineHandler);
        this.eventListeners.set('window-online', { element: window, event: 'online', handler: onlineHandler });
        this.eventListeners.set('window-offline', { element: window, event: 'offline', handler: offlineHandler });
        
        // Keyboard shortcuts with debouncing
        const debouncedKeyHandler = CortexUtils.debounce((e) => this.handleKeyboardShortcuts(e), 50);
        document.addEventListener('keydown', debouncedKeyHandler);
        this.eventListeners.set('keydown', { element: document, event: 'keydown', handler: debouncedKeyHandler });
        
        // Form submissions with debouncing
        const debouncedFormHandler = CortexUtils.debounce((e) => this.handleFormSubmission(e), 200);
        document.addEventListener('submit', debouncedFormHandler);
        this.eventListeners.set('form-submit', { element: document, event: 'submit', handler: debouncedFormHandler });

        // Modal backdrop clicks
        const modalHandler = (e) => {
            if (e.target.classList.contains('modal-backdrop')) {
                const modal = e.target.closest('.modal');
                if (modal) {
                    modal.style.display = 'none';
                }
            }
        };
        document.addEventListener('click', modalHandler);
        this.eventListeners.set('modal-backdrop', { element: document, event: 'click', handler: modalHandler });

        // Intersection observer for lazy loading
        this.setupLazyLoading();

        // Performance monitoring
        this.setupPerformanceMonitoring();
    },

    /**
     * Initialize UI components
     */
    initializeComponents() {
        // Initialize tooltips
        this.initializeTooltips();
        
        // Initialize modals
        this.initializeModals();
        
        // Set initial tab
        this.showTab(this.state.currentTab);
    },

    /**
     * Load initial data
     */
    async loadInitialData() {
        this.setLoading(true);
        
        try {
            // Load dashboard data
            await this.loadDashboardData();
            
            // Load projects
            await this.loadProjects();
            
            this.state.lastUpdate = new Date();
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showError('Failed to load initial data', error.message);
        } finally {
            this.setLoading(false);
        }
    },

    /**
     * Set up periodic updates
     */
    setupPeriodicUpdates() {
        // Initialize auto-refresh state from storage
        this.state.autoRefreshEnabled = CortexUtils.storage.get('cortex_auto_refresh', true);
        const autoRefreshToggle = document.getElementById('auto-refresh-toggle');
        if (autoRefreshToggle) {
            autoRefreshToggle.checked = this.state.autoRefreshEnabled;
        }

        // Update dashboard every 30 seconds (if auto-refresh is enabled)
        this.dashboardUpdateInterval = setInterval(() => {
            if (this.state.currentTab === 'dashboard' && 
                !this.state.loading && 
                this.state.autoRefreshEnabled) {
                this.loadDashboardData();
            }
        }, 30000);

        // Check connection status every 10 seconds
        this.connectionCheckInterval = setInterval(() => {
            this.checkConnectionStatus();
        }, 10000);
    },

    /**
     * Show specific tab
     * @param {string} tabName - Tab name to show
     */
    async showTab(tabName) {
        if (this.state.currentTab === tabName) return;

        // Update state
        this.state.currentTab = tabName;

        // Update tab navigation
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.classList.remove('active');
            tab.setAttribute('aria-selected', 'false');
        });

        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.remove('active');
        });

        // Activate selected tab
        const activeTab = document.querySelector(`[data-tab="${tabName}"]`);
        const activePanel = document.getElementById(`${tabName}-panel`);

        if (activeTab && activePanel) {
            activeTab.classList.add('active');
            activeTab.setAttribute('aria-selected', 'true');
            activePanel.classList.add('active');

            // Load tab-specific data
            await this.loadTabData(tabName);
        }

        // Update URL
        CortexUtils.setQueryParams({ tab: tabName }, true);
    },

    /**
     * Load data for specific tab
     * @param {string} tabName - Tab name
     */
    async loadTabData(tabName) {
        try {
            switch (tabName) {
                case 'dashboard':
                    await this.loadDashboardData();
                    break;
                case 'memories':
                    await this.loadMemoriesTab();
                    break;
                case 'projects':
                    await this.loadProjectsTab();
                    break;
                case 'search':
                    await this.loadSearchTab();
                    break;
                case 'settings':
                    await this.loadSettingsTab();
                    break;
                case 'monitoring':
                    await this.loadMonitoringTab();
                    break;
                case 'api':
                    await this.loadApiTab();
                    break;
                case 'api-keys':
                    await this.loadApiKeysTab();
                    break;
                case 'database':
                    await this.loadDatabaseTab();
                    break;
            }
        } catch (error) {
            console.error(`Error loading ${tabName} tab:`, error);
            this.showError(`Failed to load ${tabName} data`, error.message);
        }
    },

    /**
     * Load dashboard data
     */
    async loadDashboardData() {
        try {
            // Load health status
            const healthResponse = await CortexAPI.getHealth();
            if (healthResponse.success) {
                const healthData = healthResponse.data;
                let healthIcon = '✅';
                let healthText = 'Healthy';
                
                if (healthData.status === 'degraded') {
                    healthIcon = '⚠️';
                    healthText = 'Degraded';
                } else if (healthData.status === 'unhealthy') {
                    healthIcon = '❌';
                    healthText = 'Unhealthy';
                }
                
                this.updateMetric('system-health', healthIcon);
                
                // Update connection status based on health
                this.updateConnectionStatus(healthData.status === 'healthy' ? 'connected' : 'disconnected');
            }

            // Load stats
            const statsResponse = await CortexAPI.getStats();
            if (statsResponse.success) {
                const statsData = statsResponse.data;
                
                // Track metrics for trend analysis
                const currentMetrics = {
                    memories: statsData.total_conversations || 0,
                    projects: statsData.total_projects || 0,
                    storage: statsData.database_size_mb || 0
                };
                
                this.updateMetric('total-memories', CortexUtils.formatNumber(currentMetrics.memories));
                this.updateMetric('total-projects', CortexUtils.formatNumber(currentMetrics.projects));
                
                // Format storage usage
                if (statsData.database_size_mb !== undefined) {
                    this.updateMetric('storage-usage', CortexUtils.formatFileSize(statsData.database_size_mb * 1024 * 1024));
                } else {
                    this.updateMetric('storage-usage', 'N/A');
                }
                
                // Store current metrics for next comparison
                this.state.previousMetrics = currentMetrics;
            }

            // Load recent memories
            await this.loadRecentMemories();

            // Update last refresh time
            this.state.lastUpdate = new Date();
            this.updateLastRefreshTime();

        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.updateConnectionStatus('disconnected');
            this.showError('Dashboard Error', 'Failed to load dashboard data');
        }
    },

    /**
     * Load recent memories for dashboard
     */
    async loadRecentMemories() {
        const container = document.getElementById('recent-memories');
        if (!container) return;

        try {
            // Show loading state
            container.innerHTML = `
                <div class="loading-state">
                    <div class="loading-spinner"></div>
                    <p>Loading recent memories...</p>
                </div>
            `;

            const response = await CortexAPI.getConversations({ limit: 5 });
            
            if (response.success && response.data && response.data.length > 0) {
                container.innerHTML = response.data.map(memory => `
                    <div class="memory-item" data-memory-id="${memory.id || ''}">
                        <div class="memory-meta">
                            <span class="memory-tool" title="Tool: ${CortexUtils.escapeHtml(memory.tool_name || 'Unknown')}">${CortexUtils.escapeHtml(memory.tool_name || 'Unknown')}</span>
                            <span class="memory-date" title="${CortexUtils.formatDate(memory.timestamp || memory.created_at)}">${CortexUtils.formatRelativeTime(memory.timestamp || memory.created_at)}</span>
                        </div>
                        <div class="memory-content" title="${CortexUtils.escapeHtml(memory.content || '')}">
                            ${CortexUtils.escapeHtml(CortexUtils.truncateText(memory.content || '', 100))}
                        </div>
                        ${memory.project_name ? `<div class="memory-project">📁 ${CortexUtils.escapeHtml(memory.project_name)}</div>` : ''}
                    </div>
                `).join('');
            } else {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>No recent memories found.</p>
                        <button class="btn btn-primary btn-sm" onclick="CortexUI.showTab('memories')">
                            Add First Memory
                        </button>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error loading recent memories:', error);
            container.innerHTML = `
                <div class="error-state">
                    <p>Failed to load recent memories.</p>
                    <button class="btn btn-secondary btn-sm" onclick="CortexUI.loadRecentMemories()">
                        Retry
                    </button>
                </div>
            `;
        }
    },

    /**
     * Load projects
     */
    async loadProjects() {
        try {
            const response = await CortexAPI.getProjects();
            if (response.success) {
                this.state.projects = response.data;
                this.updateProjectDropdowns();
            }
        } catch (error) {
            console.error('Error loading projects:', error);
        }
    },

    /**
     * Update metric display with animation
     * @param {string} metricId - Metric element ID
     * @param {string} value - New value
     */
    updateMetric(metricId, value) {
        const element = document.getElementById(metricId);
        if (element) {
            const oldValue = element.textContent;
            
            // Only animate if value actually changed
            if (oldValue !== value && oldValue !== '-') {
                element.classList.add('metric-updating');
                setTimeout(() => {
                    element.classList.remove('metric-updating');
                }, 300);
            }
            
            element.textContent = value;
        }
    },

    /**
     * Update project dropdowns
     */
    updateProjectDropdowns() {
        const dropdowns = document.querySelectorAll('select[id*="project"]');
        
        dropdowns.forEach(dropdown => {
            const currentValue = dropdown.value;
            const hasAllOption = dropdown.querySelector('option[value=""]');
            
            // Clear existing options except "All" option
            dropdown.innerHTML = hasAllOption ? '<option value="">All Projects</option>' : '';
            
            // Add project options
            this.state.projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project.id;
                option.textContent = project.name;
                if (option.value === currentValue) {
                    option.selected = true;
                }
                dropdown.appendChild(option);
            });
        });
    },

    /**
     * Set loading state
     * @param {boolean} loading - Loading state
     */
    setLoading(loading) {
        this.state.loading = loading;
        const overlay = document.getElementById('loading-overlay');
        
        if (overlay) {
            overlay.style.display = loading ? 'flex' : 'none';
        }
    },

    /**
     * Update connection status
     * @param {string} status - Connection status
     */
    updateConnectionStatus(status) {
        this.state.connectionStatus = status;
        const statusElement = document.getElementById('connection-status');
        
        if (statusElement) {
            const statusText = statusElement.querySelector('.status-text');
            const statusDot = statusElement.querySelector('.status-dot');
            
            if (statusText && statusDot) {
                statusText.textContent = status === 'connected' ? 'Connected' : 'Disconnected';
                statusDot.style.backgroundColor = status === 'connected' ? 'var(--success-color)' : 'var(--danger-color)';
            }
        }
    },

    /**
     * Check connection status
     */
    async checkConnectionStatus() {
        try {
            const response = await CortexAPI.getHealth();
            this.updateConnectionStatus(response.success ? 'connected' : 'disconnected');
        } catch (error) {
            this.updateConnectionStatus('disconnected');
        }
    },

    /**
     * Show toast notification
     * @param {string} message - Message to show
     * @param {string} type - Toast type (success, error, warning, info)
     * @param {number} duration - Duration in milliseconds
     */
    showToast(message, type = 'info', duration = 5000) {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <p>${CortexUtils.escapeHtml(message)}</p>
                <button class="toast-close" aria-label="Close notification">&times;</button>
            </div>
        `;

        // Add close functionality
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => {
            toast.remove();
        });

        // Auto-remove after duration
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, duration);

        container.appendChild(toast);
    },

    /**
     * Show error message
     * @param {string} title - Error title
     * @param {string} message - Error message
     */
    showError(title, message) {
        this.showToast(`${title}: ${message}`, 'error', 8000);
    },

    /**
     * Show success message
     * @param {string} message - Success message
     */
    showSuccess(message) {
        this.showToast(message, 'success', 3000);
    },

    /**
     * Show info message
     * @param {string} title - Info title
     * @param {string} message - Info message
     */
    showInfo(title, message) {
        this.showToast(`${title}: ${message}`, 'info', 5000);
    },

    /**
     * Close modal by ID
     * @param {string} modalId - Modal element ID
     */
    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
        }
    },

    /**
     * Refresh all data
     */
    async refreshData() {
        // Prevent multiple simultaneous refreshes
        if (this.state.loading) {
            return;
        }

        this.setLoading(true);
        
        try {
            await this.loadInitialData();
            await this.loadTabData(this.state.currentTab);
            this.showSuccess('Data refreshed successfully');
        } catch (error) {
            this.showError('Refresh failed', error.message);
        } finally {
            this.setLoading(false);
        }
    },

    /**
     * Toggle auto-refresh functionality
     * @param {boolean} enabled - Whether auto-refresh should be enabled
     */
    toggleAutoRefresh(enabled) {
        this.state.autoRefreshEnabled = enabled;
        
        if (enabled) {
            this.showToast('Auto-refresh enabled', 'info');
        } else {
            this.showToast('Auto-refresh disabled', 'info');
        }
        
        // Store preference
        CortexUtils.storage.set('cortex_auto_refresh', enabled);
    },

    /**
     * Update last refresh time display
     */
    updateLastRefreshTime() {
        const element = document.getElementById('last-refresh-time');
        if (element && this.state.lastUpdate) {
            element.textContent = `Last updated: ${CortexUtils.formatRelativeTime(this.state.lastUpdate)}`;
        }
    },

    /**
     * Set up lazy loading for components
     */
    setupLazyLoading() {
        if (!this.performance.enableLazyLoading) return;

        this.lazyLoadObserver = CortexUtils.lazyLoad.createObserver({
            threshold: this.performance.lazyLoadThreshold,
            onIntersect: (element) => {
                const componentName = element.dataset.lazyComponent;
                if (componentName && this.lazyComponents.has(componentName)) {
                    const loader = this.lazyComponents.get(componentName);
                    loader(element);
                    this.lazyLoadObserver.unobserve(element);
                }
            }
        });
    },

    /**
     * Set up performance monitoring
     */
    setupPerformanceMonitoring() {
        // Monitor long tasks
        if ('PerformanceObserver' in window) {
            try {
                const observer = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        if (entry.duration > 50) {
                            console.warn('Long task detected:', entry);
                        }
                    }
                });
                observer.observe({ entryTypes: ['longtask'] });
            } catch (e) {
                console.log('Long task monitoring not supported');
            }
        }

        // Monitor memory usage periodically
        if (performance.memory) {
            setInterval(() => {
                const usage = CortexUtils.memory.getUsage();
                if (usage && usage.used > usage.limit * 0.8) {
                    console.warn('High memory usage detected:', usage);
                }
            }, 30000);
        }
    },

    /**
     * Create virtual scroll for large datasets
     * @param {string} containerId - Container element ID
     * @param {Array} items - Items to render
     * @param {Function} renderItem - Item render function
     * @returns {Object} Virtual scroll instance
     */
    createVirtualScroll(containerId, items, renderItem) {
        const container = document.getElementById(containerId);
        if (!container || !this.performance.enableVirtualScrolling) {
            return null;
        }

        return CortexUtils.virtualScroll.create({
            container,
            itemHeight: this.performance.virtualScrollItemHeight,
            items,
            renderItem,
            overscan: 5
        });
    },

    /**
     * Render large list with performance optimizations
     * @param {string} containerId - Container element ID
     * @param {Array} items - Items to render
     * @param {Function} renderItem - Item render function
     * @param {Object} options - Rendering options
     */
    renderLargeList(containerId, items, renderItem, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const {
            useVirtualScroll = this.performance.enableVirtualScrolling,
            maxItems = this.performance.maxRenderItems,
            showLoadMore = true
        } = options;

        // Use virtual scrolling for very large datasets
        if (useVirtualScroll && items.length > 100) {
            return this.createVirtualScroll(containerId, items, renderItem);
        }

        // Render limited items with load more functionality
        const itemsToRender = items.slice(0, maxItems);
        const fragment = document.createDocumentFragment();

        itemsToRender.forEach((item, index) => {
            const element = renderItem(item, index);
            fragment.appendChild(element);
        });

        container.innerHTML = '';
        container.appendChild(fragment);

        // Add load more button if needed
        if (showLoadMore && items.length > maxItems) {
            const loadMoreBtn = document.createElement('button');
            loadMoreBtn.className = 'btn btn-secondary load-more-btn';
            loadMoreBtn.textContent = `Load More (${items.length - maxItems} remaining)`;
            loadMoreBtn.onclick = () => {
                this.renderLargeList(containerId, items, renderItem, {
                    ...options,
                    maxItems: maxItems + this.performance.maxRenderItems
                });
            };
            container.appendChild(loadMoreBtn);
        }
    },

    // Placeholder methods for other tabs with lazy loading
    async loadMemoriesTab() {
        const panel = document.getElementById('memories-panel');
        if (panel) {
            // Show loading state
            panel.innerHTML = `
                <div class="loading-state">
                    <div class="loading-spinner"></div>
                    <p>Loading memory management interface...</p>
                </div>
            `;

            // Lazy load the memories interface
            setTimeout(() => {
                panel.innerHTML = `
                    <div class="panel-header">
                        <h2>Memory Management Interface</h2>
                        <p>Advanced memory management with performance optimizations</p>
                    </div>
                    <div class="memories-interface">
                        <div class="memory-controls">
                            <div class="search-filters">
                                <input type="text" id="memory-search" class="form-control search-input" 
                                       placeholder="Search memories..." data-debounce="true">
                                <select id="memory-tool-filter" class="form-control">
                                    <option value="">All Tools</option>
                                </select>
                                <select id="memory-project-filter" class="form-control">
                                    <option value="">All Projects</option>
                                </select>
                            </div>
                        </div>
                        <div id="memories-list" class="memory-list-container" data-lazy-component="memories-list">
                            <div class="loading-state">
                                <div class="loading-spinner"></div>
                                <p>Loading memories...</p>
                            </div>
                        </div>
                    </div>
                `;

                // Set up debounced search
                const searchInput = document.getElementById('memory-search');
                if (searchInput) {
                    const debouncedSearch = CortexUtils.debouncedWithCancel(
                        (query) => this.searchMemories(query),
                        this.performance.debounceDelay
                    );
                    searchInput.addEventListener('input', (e) => debouncedSearch(e.target.value));
                }

                // Register lazy component loader
                this.lazyComponents.set('memories-list', (element) => {
                    this.loadMemoriesList(element);
                });

                // Observe the memories list for lazy loading
                const memoriesList = document.getElementById('memories-list');
                if (memoriesList && this.lazyLoadObserver) {
                    this.lazyLoadObserver.observe(memoriesList);
                }
            }, 100);
        }
    },

    async loadProjectsTab() {
        const panel = document.getElementById('projects-panel');
        if (panel) {
            panel.innerHTML = `
                <div class="panel-header">
                    <h2>Project Management Interface</h2>
                    <p>Efficient project management with lazy loading</p>
                </div>
                <div id="projects-list" data-lazy-component="projects-list">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>Loading projects...</p>
                    </div>
                </div>
            `;

            // Register lazy component loader
            this.lazyComponents.set('projects-list', (element) => {
                this.loadProjectsList(element);
            });

            // Observe for lazy loading
            const projectsList = document.getElementById('projects-list');
            if (projectsList && this.lazyLoadObserver) {
                this.lazyLoadObserver.observe(projectsList);
            }
        }
    },

    async loadSearchTab() {
        const panel = document.getElementById('search-panel');
        if (panel) {
            panel.innerHTML = `
                <div class="panel-header">
                    <h2>Advanced Search Interface</h2>
                    <p>Powerful search with debounced input and result caching</p>
                </div>
                <div class="search-interface">
                    <div class="search-controls">
                        <input type="text" id="search-query" class="form-control" 
                               placeholder="Enter search query..." data-debounce="true">
                        <select id="search-type" class="form-control">
                            <option value="semantic">Semantic Search</option>
                            <option value="keyword">Keyword Search</option>
                            <option value="hybrid">Hybrid Search</option>
                        </select>
                        <button id="search-btn" class="btn btn-primary">Search</button>
                    </div>
                    <div id="search-results" data-lazy-component="search-results">
                        <div class="empty-state">
                            <p>Enter a search query to get started</p>
                        </div>
                    </div>
                </div>
            `;

            // Set up debounced search
            const searchInput = document.getElementById('search-query');
            const searchBtn = document.getElementById('search-btn');
            
            if (searchInput && searchBtn) {
                const debouncedSearch = CortexUtils.debouncedWithCancel(
                    (query) => this.performSearch(query),
                    this.performance.debounceDelay
                );
                
                searchInput.addEventListener('input', (e) => {
                    if (e.target.value.length > 2) {
                        debouncedSearch(e.target.value);
                    }
                });
                
                searchBtn.addEventListener('click', () => {
                    const query = searchInput.value.trim();
                    if (query) {
                        this.performSearch(query);
                    }
                });
            }
        }
    },

    async loadSettingsTab() {
        const panel = document.getElementById('settings-panel');
        if (panel) {
            panel.innerHTML = `
                <div class="panel-header">
                    <h2>System Settings</h2>
                    <p>Configure system preferences with auto-save</p>
                </div>
                <div id="settings-content" data-lazy-component="settings-content">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>Loading settings...</p>
                    </div>
                </div>
            `;

            // Register lazy component loader
            this.lazyComponents.set('settings-content', (element) => {
                this.loadSettingsContent(element);
            });

            // Observe for lazy loading
            const settingsContent = document.getElementById('settings-content');
            if (settingsContent && this.lazyLoadObserver) {
                this.lazyLoadObserver.observe(settingsContent);
            }
        }
    },

    async loadMonitoringTab() {
        const panel = document.getElementById('monitoring-panel');
        if (panel) {
            panel.innerHTML = `
                <div class="panel-header">
                    <h2>System Monitoring</h2>
                    <p>Real-time performance metrics and health monitoring</p>
                </div>
                <div id="monitoring-content" data-lazy-component="monitoring-content">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>Loading monitoring dashboard...</p>
                    </div>
                </div>
            `;

            // Register lazy component loader
            this.lazyComponents.set('monitoring-content', (element) => {
                this.loadMonitoringContent(element);
            });

            // Observe for lazy loading
            const monitoringContent = document.getElementById('monitoring-content');
            if (monitoringContent && this.lazyLoadObserver) {
                this.lazyLoadObserver.observe(monitoringContent);
            }
        }
    },

    // API Key Management Interface Implementation
    async loadApiKeysTab() {
        const panel = document.getElementById('api-keys-panel');
        if (!panel) return;

        try {
            panel.innerHTML = this.renderApiKeyManagementInterface();
            this.setupApiKeyEventListeners();
            await this.loadApiKeys();
        } catch (error) {
            console.error('Error loading API keys tab:', error);
            panel.innerHTML = `
                <div class="error-state">
                    <h3>Error Loading API Key Interface</h3>
                    <p>Failed to load API key management interface: ${error.message}</p>
                    <button class="btn btn-primary" onclick="CortexUI.loadApiKeysTab()">Retry</button>
                </div>
            `;
        }
    },

    renderApiKeyManagementInterface() {
        return `
            <div class="panel-header">
                <h2>API Key Management</h2>
                <p>Create, manage, and monitor API keys for secure access to your Cortex MCP server</p>
            </div>

            <div class="dashboard-grid">
                <!-- API Key Creation Card -->
                <div class="card">
                    <div class="card-header">
                        <h3>🔑 Create New API Key</h3>
                    </div>
                    <div class="card-content">
                        <form id="create-api-key-form">
                            <div class="form-group">
                                <label for="api-key-name">Key Name</label>
                                <input type="text" id="api-key-name" class="form-control" 
                                       placeholder="Enter a descriptive name" required maxlength="100">
                                <div class="form-help">Choose a descriptive name to identify this API key</div>
                            </div>
                            <div class="form-group">
                                <label for="api-key-expires">Expires In (Days)</label>
                                <select id="api-key-expires" class="form-control">
                                    <option value="">Never expires</option>
                                    <option value="7">7 days</option>
                                    <option value="30">30 days</option>
                                    <option value="90">90 days</option>
                                    <option value="365">1 year</option>
                                </select>
                                <div class="form-help">Optional expiration period for enhanced security</div>
                            </div>
                            <button type="submit" class="btn btn-primary">
                                <span class="btn-icon">➕</span>
                                Generate API Key
                            </button>
                        </form>
                    </div>
                </div>

                <!-- API Key Statistics Card -->
                <div class="card">
                    <div class="card-header">
                        <h3>📊 Key Statistics</h3>
                        <button id="refresh-api-keys-btn" class="btn btn-text" title="Refresh API keys">
                            <span class="btn-icon">🔄</span>
                        </button>
                    </div>
                    <div class="card-content">
                        <div class="metrics-grid" style="grid-template-columns: 1fr 1fr;">
                            <div class="metric-card">
                                <div class="metric-icon">🔑</div>
                                <div class="metric-content">
                                    <div class="metric-value" id="total-api-keys">-</div>
                                    <div class="metric-label">Total Keys</div>
                                </div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-icon">✅</div>
                                <div class="metric-content">
                                    <div class="metric-value" id="active-api-keys">-</div>
                                    <div class="metric-label">Active Keys</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- API Keys List -->
            <div class="card">
                <div class="card-header">
                    <h3>🗂️ API Keys</h3>
                    <div class="card-actions">
                        <button id="show-inactive-keys-btn" class="btn btn-text">
                            <span class="btn-icon">👁️</span>
                            Show Inactive
                        </button>
                    </div>
                </div>
                <div class="card-content">
                    <div id="api-keys-list" class="api-keys-list">
                        <div class="loading-state">
                            <div class="loading-spinner"></div>
                            <p>Loading API keys...</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- API Key Display Modal -->
            <div id="api-key-display-modal" class="modal">
                <div class="modal-backdrop"></div>
                <div class="modal-content modal-sm">
                    <div class="modal-header">
                        <h3>🔑 New API Key Created</h3>
                        <button class="modal-close" onclick="CortexUI.closeModal('api-key-display-modal')">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="alert alert-warning">
                            <strong>⚠️ Important:</strong> This is the only time you'll see the full API key. 
                            Copy it now and store it securely.
                        </div>
                        <div class="form-group">
                            <label>API Key</label>
                            <div class="api-key-display">
                                <input type="text" id="new-api-key-value" class="form-control" readonly>
                                <button id="copy-api-key-btn" class="btn btn-secondary" title="Copy to clipboard">
                                    <span class="btn-icon">📋</span>
                                </button>
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Key Name</label>
                            <input type="text" id="new-api-key-name" class="form-control" readonly>
                        </div>
                        <div class="form-group">
                            <label>Key ID</label>
                            <input type="text" id="new-api-key-id" class="form-control" readonly>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-primary" onclick="CortexUI.closeModal('api-key-display-modal')">
                            I've Copied the Key
                        </button>
                    </div>
                </div>
            </div>

            <!-- Confirm Delete Modal -->
            <div id="confirm-delete-api-key-modal" class="modal">
                <div class="modal-backdrop"></div>
                <div class="modal-content modal-sm">
                    <div class="modal-header">
                        <h3>⚠️ Confirm Deletion</h3>
                        <button class="modal-close" onclick="CortexUI.closeModal('confirm-delete-api-key-modal')">&times;</button>
                    </div>
                    <div class="modal-body">
                        <p>Are you sure you want to delete this API key?</p>
                        <div class="alert alert-danger">
                            <strong>This action cannot be undone.</strong> Any applications using this key will lose access immediately.
                        </div>
                        <div class="form-group">
                            <label>Key Name</label>
                            <input type="text" id="delete-api-key-name" class="form-control" readonly>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="CortexUI.closeModal('confirm-delete-api-key-modal')">Cancel</button>
                        <button id="confirm-delete-api-key-btn" class="btn btn-danger">Delete Key</button>
                    </div>
                </div>
            </div>

            <!-- Rotate Key Modal -->
            <div id="rotate-api-key-modal" class="modal">
                <div class="modal-backdrop"></div>
                <div class="modal-content modal-sm">
                    <div class="modal-header">
                        <h3>🔄 Rotate API Key</h3>
                        <button class="modal-close" onclick="CortexUI.closeModal('rotate-api-key-modal')">&times;</button>
                    </div>
                    <div class="modal-body">
                        <p>Generate a new API key while keeping the same metadata and usage statistics.</p>
                        <div class="alert alert-warning">
                            <strong>⚠️ Warning:</strong> The old key will be invalidated immediately. 
                            Update any applications using this key.
                        </div>
                        <div class="form-group">
                            <label>Key Name</label>
                            <input type="text" id="rotate-api-key-name" class="form-control" readonly>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="CortexUI.closeModal('rotate-api-key-modal')">Cancel</button>
                        <button id="confirm-rotate-api-key-btn" class="btn btn-warning">Rotate Key</button>
                    </div>
                </div>
            </div>
        `;
    },

    setupApiKeyEventListeners() {
        // Create API key form
        const createForm = document.getElementById('create-api-key-form');
        if (createForm) {
            createForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.createApiKey();
            });
        }

        // Refresh API keys button
        const refreshBtn = document.getElementById('refresh-api-keys-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadApiKeys());
        }

        // Show/hide inactive keys
        const showInactiveBtn = document.getElementById('show-inactive-keys-btn');
        if (showInactiveBtn) {
            showInactiveBtn.addEventListener('click', () => this.toggleInactiveKeys());
        }

        // Copy API key button
        const copyBtn = document.getElementById('copy-api-key-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => this.copyApiKeyToClipboard());
        }

        // Confirm delete button
        const confirmDeleteBtn = document.getElementById('confirm-delete-api-key-btn');
        if (confirmDeleteBtn) {
            confirmDeleteBtn.addEventListener('click', () => this.confirmDeleteApiKey());
        }

        // Confirm rotate button
        const confirmRotateBtn = document.getElementById('confirm-rotate-api-key-btn');
        if (confirmRotateBtn) {
            confirmRotateBtn.addEventListener('click', () => this.confirmRotateApiKey());
        }
    },

    async loadApiKeys() {
        const container = document.getElementById('api-keys-list');
        if (!container) return;

        try {
            // Show loading state
            container.innerHTML = `
                <div class="loading-state">
                    <div class="loading-spinner"></div>
                    <p>Loading API keys...</p>
                </div>
            `;

            const response = await CortexAPI.getApiKeys();
            
            if (response.success && response.data) {
                const apiKeys = response.data;
                
                // Store in state
                this.state.apiKeys = apiKeys;
                
                // Update statistics
                this.updateApiKeyStats(apiKeys);
                
                if (apiKeys.length > 0) {
                    container.innerHTML = this.renderApiKeysList(apiKeys);
                    this.setupApiKeyItemEventListeners();
                } else {
                    container.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-icon">🔑</div>
                            <h3>No API Keys</h3>
                            <p>Create your first API key to start using the Cortex MCP server programmatically.</p>
                            <button class="btn btn-primary" onclick="document.getElementById('api-key-name').focus()">
                                Create First API Key
                            </button>
                        </div>
                    `;
                }
            } else {
                throw new Error(response.data?.message || 'Failed to load API keys');
            }
        } catch (error) {
            console.error('Error loading API keys:', error);
            container.innerHTML = `
                <div class="error-state">
                    <h3>Failed to Load API Keys</h3>
                    <p>${error.message}</p>
                    <button class="btn btn-secondary" onclick="CortexUI.loadApiKeys()">
                        Retry
                    </button>
                </div>
            `;
        }
    },

    updateApiKeyStats(apiKeys) {
        const totalKeys = apiKeys.length;
        const activeKeys = apiKeys.filter(key => key.active && !key.expired).length;
        
        this.updateMetric('total-api-keys', totalKeys);
        this.updateMetric('active-api-keys', activeKeys);
    },

    renderApiKeysList(apiKeys) {
        const showInactive = this.state.showInactiveApiKeys || false;
        const filteredKeys = showInactive ? apiKeys : apiKeys.filter(key => key.active && !key.expired);
        
        if (filteredKeys.length === 0) {
            return `
                <div class="empty-state">
                    <div class="empty-icon">🔍</div>
                    <h3>No ${showInactive ? '' : 'Active '}API Keys</h3>
                    <p>${showInactive ? 'No API keys found.' : 'No active API keys found. Create a new one or show inactive keys.'}</p>
                </div>
            `;
        }

        return `
            <div class="api-keys-grid">
                ${filteredKeys.map(key => this.renderApiKeyItem(key)).join('')}
            </div>
        `;
    },

    renderApiKeyItem(apiKey) {
        const isExpired = apiKey.expired;
        const isInactive = !apiKey.active;
        const statusClass = isExpired ? 'expired' : (isInactive ? 'inactive' : 'active');
        const statusIcon = isExpired ? '⏰' : (isInactive ? '🚫' : '✅');
        const statusText = isExpired ? 'Expired' : (isInactive ? 'Inactive' : 'Active');
        
        return `
            <div class="api-key-item ${statusClass}" data-key-id="${apiKey.id}">
                <div class="api-key-header">
                    <div class="api-key-info">
                        <h4 class="api-key-name">${CortexUtils.escapeHtml(apiKey.name)}</h4>
                        <div class="api-key-meta">
                            <span class="api-key-id">ID: ${CortexUtils.escapeHtml(apiKey.key_preview)}</span>
                            <span class="api-key-status ${statusClass}">
                                ${statusIcon} ${statusText}
                            </span>
                        </div>
                    </div>
                    <div class="api-key-actions">
                        ${!isExpired && isInactive ? `
                            <button class="btn btn-sm btn-success" onclick="CortexUI.activateApiKey('${apiKey.id}')" title="Activate key">
                                <span class="btn-icon">✅</span>
                            </button>
                        ` : ''}
                        ${!isExpired && !isInactive ? `
                            <button class="btn btn-sm btn-warning" onclick="CortexUI.showRotateApiKeyModal('${apiKey.id}', '${CortexUtils.escapeHtml(apiKey.name)}')" title="Rotate key">
                                <span class="btn-icon">🔄</span>
                            </button>
                            <button class="btn btn-sm btn-secondary" onclick="CortexUI.deactivateApiKey('${apiKey.id}')" title="Deactivate key">
                                <span class="btn-icon">⏸️</span>
                            </button>
                        ` : ''}
                        <button class="btn btn-sm btn-danger" onclick="CortexUI.showDeleteApiKeyModal('${apiKey.id}', '${CortexUtils.escapeHtml(apiKey.name)}')" title="Delete key">
                            <span class="btn-icon">🗑️</span>
                        </button>
                    </div>
                </div>
                <div class="api-key-details">
                    <div class="api-key-stats">
                        <div class="stat-item">
                            <span class="stat-label">Created:</span>
                            <span class="stat-value">${CortexUtils.formatDate(apiKey.created)}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Last Used:</span>
                            <span class="stat-value">${apiKey.last_used ? CortexUtils.formatRelativeTime(apiKey.last_used) : 'Never'}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Usage Count:</span>
                            <span class="stat-value">${CortexUtils.formatNumber(apiKey.usage_count)}</span>
                        </div>
                        ${apiKey.expires ? `
                            <div class="stat-item">
                                <span class="stat-label">Expires:</span>
                                <span class="stat-value ${isExpired ? 'expired' : ''}">${CortexUtils.formatDate(apiKey.expires)}</span>
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    },

    setupApiKeyItemEventListeners() {
        // Event listeners are set up via onclick attributes in the HTML
        // This method can be used for additional event listeners if needed
    },

    async createApiKey() {
        const nameInput = document.getElementById('api-key-name');
        const expiresInput = document.getElementById('api-key-expires');
        
        if (!nameInput || !nameInput.value.trim()) {
            this.showError('Validation Error', 'API key name is required');
            return;
        }

        const keyData = {
            name: nameInput.value.trim()
        };

        if (expiresInput.value) {
            keyData.expires_days = parseInt(expiresInput.value);
        }

        try {
            this.setLoading(true);
            const response = await CortexAPI.createApiKey(keyData);
            
            if (response.success && response.data) {
                // Show the new API key in modal
                this.showNewApiKeyModal(response.data);
                
                // Clear form
                nameInput.value = '';
                expiresInput.value = '';
                
                // Reload API keys list
                await this.loadApiKeys();
                
                this.showSuccess('API key created successfully');
            } else {
                throw new Error(response.data?.message || 'Failed to create API key');
            }
        } catch (error) {
            console.error('Error creating API key:', error);
            this.showError('Creation Failed', error.message);
        } finally {
            this.setLoading(false);
        }
    },

    showNewApiKeyModal(apiKeyData) {
        const modal = document.getElementById('api-key-display-modal');
        const keyValueInput = document.getElementById('new-api-key-value');
        const keyNameInput = document.getElementById('new-api-key-name');
        const keyIdInput = document.getElementById('new-api-key-id');
        
        if (modal && keyValueInput && keyNameInput && keyIdInput) {
            keyValueInput.value = apiKeyData.key;
            keyNameInput.value = apiKeyData.name;
            keyIdInput.value = apiKeyData.id;
            
            modal.style.display = 'flex';
        }
    },

    async copyApiKeyToClipboard() {
        const keyValueInput = document.getElementById('new-api-key-value');
        if (keyValueInput) {
            try {
                await navigator.clipboard.writeText(keyValueInput.value);
                this.showSuccess('API key copied to clipboard');
            } catch (error) {
                // Fallback for older browsers
                keyValueInput.select();
                document.execCommand('copy');
                this.showSuccess('API key copied to clipboard');
            }
        }
    },

    showDeleteApiKeyModal(keyId, keyName) {
        const modal = document.getElementById('confirm-delete-api-key-modal');
        const keyNameInput = document.getElementById('delete-api-key-name');
        const confirmBtn = document.getElementById('confirm-delete-api-key-btn');
        
        if (modal && keyNameInput && confirmBtn) {
            keyNameInput.value = keyName;
            confirmBtn.dataset.keyId = keyId;
            modal.style.display = 'flex';
        }
    },

    async confirmDeleteApiKey() {
        const confirmBtn = document.getElementById('confirm-delete-api-key-btn');
        const keyId = confirmBtn?.dataset.keyId;
        
        if (!keyId) return;

        try {
            this.setLoading(true);
            const response = await CortexAPI.deleteApiKey(keyId);
            
            if (response.success) {
                this.closeModal('confirm-delete-api-key-modal');
                await this.loadApiKeys();
                this.showSuccess('API key deleted successfully');
            } else {
                throw new Error(response.data?.message || 'Failed to delete API key');
            }
        } catch (error) {
            console.error('Error deleting API key:', error);
            this.showError('Deletion Failed', error.message);
        } finally {
            this.setLoading(false);
        }
    },

    showRotateApiKeyModal(keyId, keyName) {
        const modal = document.getElementById('rotate-api-key-modal');
        const keyNameInput = document.getElementById('rotate-api-key-name');
        const confirmBtn = document.getElementById('confirm-rotate-api-key-btn');
        
        if (modal && keyNameInput && confirmBtn) {
            keyNameInput.value = keyName;
            confirmBtn.dataset.keyId = keyId;
            modal.style.display = 'flex';
        }
    },

    async confirmRotateApiKey() {
        const confirmBtn = document.getElementById('confirm-rotate-api-key-btn');
        const keyId = confirmBtn?.dataset.keyId;
        
        if (!keyId) return;

        try {
            this.setLoading(true);
            const response = await CortexAPI.rotateApiKey(keyId);
            
            if (response.success && response.data) {
                this.closeModal('rotate-api-key-modal');
                
                // Show the new API key
                this.showNewApiKeyModal(response.data);
                
                await this.loadApiKeys();
                this.showSuccess('API key rotated successfully');
            } else {
                throw new Error(response.data?.message || 'Failed to rotate API key');
            }
        } catch (error) {
            console.error('Error rotating API key:', error);
            this.showError('Rotation Failed', error.message);
        } finally {
            this.setLoading(false);
        }
    },

    async deactivateApiKey(keyId) {
        if (!confirm('Are you sure you want to deactivate this API key? It will stop working immediately.')) {
            return;
        }

        try {
            this.setLoading(true);
            const response = await CortexAPI.deactivateApiKey(keyId);
            
            if (response.success) {
                await this.loadApiKeys();
                this.showSuccess('API key deactivated successfully');
            } else {
                throw new Error(response.data?.message || 'Failed to deactivate API key');
            }
        } catch (error) {
            console.error('Error deactivating API key:', error);
            this.showError('Deactivation Failed', error.message);
        } finally {
            this.setLoading(false);
        }
    },

    async activateApiKey(keyId) {
        try {
            this.setLoading(true);
            const response = await CortexAPI.updateApiKey(keyId, { active: true });
            
            if (response.success) {
                await this.loadApiKeys();
                this.showSuccess('API key activated successfully');
            } else {
                throw new Error(response.data?.message || 'Failed to activate API key');
            }
        } catch (error) {
            console.error('Error activating API key:', error);
            this.showError('Activation Failed', error.message);
        } finally {
            this.setLoading(false);
        }
    },

    toggleInactiveKeys() {
        this.state.showInactiveApiKeys = !this.state.showInactiveApiKeys;
        const btn = document.getElementById('show-inactive-keys-btn');
        
        if (btn) {
            const icon = btn.querySelector('.btn-icon');
            const text = btn.childNodes[btn.childNodes.length - 1];
            
            if (this.state.showInactiveApiKeys) {
                icon.textContent = '🙈';
                text.textContent = ' Hide Inactive';
            } else {
                icon.textContent = '👁️';
                text.textContent = ' Show Inactive';
            }
        }
        
        // Re-render the list with current data
        const container = document.getElementById('api-keys-list');
        if (container && this.state.apiKeys) {
            container.innerHTML = this.renderApiKeysList(this.state.apiKeys);
            this.setupApiKeyItemEventListeners();
        }
    },

    // Database Maintenance Interface Implementation
    async loadDatabaseTab() {
        const panel = document.getElementById('database-panel');
        if (!panel) return;

        try {
            panel.innerHTML = this.renderDatabaseMaintenanceInterface();
            this.setupDatabaseMaintenanceEventListeners();
            await this.loadMaintenanceHistory();
        } catch (error) {
            console.error('Error loading database tab:', error);
            panel.innerHTML = `
                <div class="error-state">
                    <h3>Error Loading Database Interface</h3>
                    <p>Failed to load database maintenance interface: ${error.message}</p>
                    <button class="btn btn-primary" onclick="CortexUI.loadDatabaseTab()">Retry</button>
                </div>
            `;
        }
    },

    renderDatabaseMaintenanceInterface() {
        return `
            <div class="panel-header">
                <h2>Database Maintenance</h2>
                <p>Manage database integrity, cleanup operations, and data export/import</p>
            </div>

            <div class="dashboard-grid">
                <!-- Database Operations Card -->
                <div class="card">
                    <div class="card-header">
                        <h3>🔍 Database Operations</h3>
                    </div>
                    <div class="card-content">
                        <div class="action-buttons">
                            <button id="integrity-check-btn" class="btn btn-primary">
                                <span class="btn-icon">🔍</span>
                                Run Integrity Check
                            </button>
                            <button id="cleanup-btn" class="btn btn-warning">
                                <span class="btn-icon">🧹</span>
                                Run Cleanup
                            </button>
                            <button id="dry-run-cleanup-btn" class="btn btn-secondary">
                                <span class="btn-icon">👁️</span>
                                Preview Cleanup
                            </button>
                        </div>
                        <div id="operation-status" class="operation-status" style="display: none;">
                            <div class="loading-spinner"></div>
                            <p id="operation-message">Processing...</p>
                        </div>
                        <div id="operation-results" class="operation-results" style="display: none;"></div>
                    </div>
                </div>

                <!-- Data Export/Import Card -->
                <div class="card">
                    <div class="card-header">
                        <h3>📦 Data Export/Import</h3>
                    </div>
                    <div class="card-content">
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="include-embeddings" />
                                Include embeddings (larger file size)
                            </label>
                        </div>
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="compress-export" checked />
                                Compress export file
                            </label>
                        </div>
                        <div class="action-buttons">
                            <button id="export-btn" class="btn btn-success">
                                <span class="btn-icon">📤</span>
                                Export Data
                            </button>
                            <button id="import-btn" class="btn btn-info">
                                <span class="btn-icon">📥</span>
                                Import Data
                            </button>
                        </div>
                        <div id="export-status" class="export-status" style="display: none;">
                            <div class="loading-spinner"></div>
                            <p id="export-message">Preparing export...</p>
                        </div>
                        <div id="export-results" class="export-results" style="display: none;"></div>
                    </div>
                </div>

                <!-- Maintenance History Card -->
                <div class="card">
                    <div class="card-header">
                        <h3>📋 Maintenance History</h3>
                        <button id="refresh-history-btn" class="btn btn-text">
                            <span class="btn-icon">🔄</span>
                        </button>
                    </div>
                    <div class="card-content">
                        <div id="maintenance-history" class="maintenance-history">
                            <div class="loading-state">
                                <div class="loading-spinner"></div>
                                <p>Loading maintenance history...</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Database Statistics Card -->
                <div class="card">
                    <div class="card-header">
                        <h3>📊 Database Statistics</h3>
                    </div>
                    <div class="card-content">
                        <div id="database-stats" class="database-stats">
                            <div class="loading-state">
                                <div class="loading-spinner"></div>
                                <p>Loading database statistics...</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Import Modal -->
            <div id="import-modal" class="modal">
                <div class="modal-backdrop"></div>
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>Import Database Data</h3>
                        <button class="modal-close" onclick="CortexUI.closeModal('import-modal')">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <label for="import-file-input">Select Import File</label>
                            <input type="file" id="import-file-input" accept=".json,.zip" class="form-control" />
                            <div class="form-help">Select a JSON or ZIP export file to import</div>
                        </div>
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="overwrite-existing" />
                                Overwrite existing data
                            </label>
                            <div class="form-help">If checked, existing records will be updated with imported data</div>
                        </div>
                        <div class="form-group">
                            <label>Import Options:</label>
                            <div class="checkbox-group">
                                <label><input type="checkbox" id="import-conversations" checked /> Conversations</label>
                                <label><input type="checkbox" id="import-projects" checked /> Projects</label>
                                <label><input type="checkbox" id="import-preferences" checked /> Preferences</label>
                                <label><input type="checkbox" id="import-context-links" checked /> Context Links</label>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="CortexUI.closeModal('import-modal')">Cancel</button>
                        <button id="confirm-import-btn" class="btn btn-primary">Import Data</button>
                    </div>
                </div>
            </div>
        `;
    },

    setupDatabaseMaintenanceEventListeners() {
        // Integrity check button
        const integrityBtn = document.getElementById('integrity-check-btn');
        if (integrityBtn) {
            integrityBtn.addEventListener('click', () => this.runIntegrityCheck());
        }

        // Cleanup buttons
        const cleanupBtn = document.getElementById('cleanup-btn');
        if (cleanupBtn) {
            cleanupBtn.addEventListener('click', () => this.runCleanup(false));
        }

        const dryRunBtn = document.getElementById('dry-run-cleanup-btn');
        if (dryRunBtn) {
            dryRunBtn.addEventListener('click', () => this.runCleanup(true));
        }

        // Export button
        const exportBtn = document.getElementById('export-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportData());
        }

        // Import button
        const importBtn = document.getElementById('import-btn');
        if (importBtn) {
            importBtn.addEventListener('click', () => this.showImportModal());
        }

        // Refresh history button
        const refreshHistoryBtn = document.getElementById('refresh-history-btn');
        if (refreshHistoryBtn) {
            refreshHistoryBtn.addEventListener('click', () => this.loadMaintenanceHistory());
        }

        // Import modal confirm button
        const confirmImportBtn = document.getElementById('confirm-import-btn');
        if (confirmImportBtn) {
            confirmImportBtn.addEventListener('click', () => this.importData());
        }

        // Load initial database statistics
        this.loadDatabaseStatistics();
    },

    async runIntegrityCheck(autoFix = false) {
        const statusDiv = document.getElementById('operation-status');
        const resultsDiv = document.getElementById('operation-results');
        const messageEl = document.getElementById('operation-message');
        const integrityBtn = document.getElementById('integrity-check-btn');

        try {
            // Show loading state
            statusDiv.style.display = 'block';
            resultsDiv.style.display = 'none';
            messageEl.textContent = 'Running database integrity check...';
            integrityBtn.disabled = true;

            const response = await CortexAPI.request('POST', '/database/integrity-check', {
                auto_fix: autoFix
            });

            if (response.success) {
                const data = response.data;
                statusDiv.style.display = 'none';
                resultsDiv.style.display = 'block';
                
                const statusIcon = data.is_healthy ? '✅' : '⚠️';
                const statusText = data.is_healthy ? 'Healthy' : 'Issues Found';
                
                resultsDiv.innerHTML = `
                    <div class="operation-result ${data.is_healthy ? 'success' : 'warning'}">
                        <h4>${statusIcon} Database Integrity Check Complete</h4>
                        <div class="result-details">
                            <div class="metric">
                                <span class="metric-label">Status:</span>
                                <span class="metric-value">${statusText}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Total Checks:</span>
                                <span class="metric-value">${data.total_checks}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Issues Found:</span>
                                <span class="metric-value">${data.issues_found}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Duration:</span>
                                <span class="metric-value">${data.duration_seconds.toFixed(2)}s</span>
                            </div>
                        </div>
                        ${data.issues && data.issues.length > 0 ? `
                            <div class="issues-list">
                                <h5>Issues Found:</h5>
                                ${data.issues.map(issue => `
                                    <div class="issue-item ${issue.severity}">
                                        <strong>${issue.type}</strong> in ${issue.table}: ${issue.description}
                                        ${issue.auto_fixable ? ' (Auto-fixable)' : ''}
                                    </div>
                                `).join('')}
                            </div>
                        ` : ''}
                    </div>
                `;

                this.showSuccess('Integrity Check Complete', `Found ${data.issues_found} issues`);
            } else {
                throw new Error(response.error || 'Integrity check failed');
            }
        } catch (error) {
            console.error('Integrity check failed:', error);
            statusDiv.style.display = 'none';
            resultsDiv.style.display = 'block';
            resultsDiv.innerHTML = `
                <div class="operation-result error">
                    <h4>❌ Integrity Check Failed</h4>
                    <p>${error.message}</p>
                </div>
            `;
            this.showError('Integrity Check Failed', error.message);
        } finally {
            integrityBtn.disabled = false;
        }
    },

    async runCleanup(dryRun = false) {
        const statusDiv = document.getElementById('operation-status');
        const resultsDiv = document.getElementById('operation-results');
        const messageEl = document.getElementById('operation-message');
        const cleanupBtn = document.getElementById('cleanup-btn');
        const dryRunBtn = document.getElementById('dry-run-cleanup-btn');

        if (!dryRun && !confirm('Are you sure you want to run database cleanup? This will permanently delete old data.')) {
            return;
        }

        try {
            // Show loading state
            statusDiv.style.display = 'block';
            resultsDiv.style.display = 'none';
            messageEl.textContent = dryRun ? 'Previewing cleanup operations...' : 'Running database cleanup...';
            cleanupBtn.disabled = true;
            dryRunBtn.disabled = true;

            const response = await CortexAPI.request('POST', '/database/cleanup', {
                dry_run: dryRun
            });

            if (response.success) {
                const data = response.data;
                statusDiv.style.display = 'none';
                resultsDiv.style.display = 'block';
                
                resultsDiv.innerHTML = `
                    <div class="operation-result success">
                        <h4>🧹 ${dryRun ? 'Cleanup Preview' : 'Cleanup Complete'}</h4>
                        <div class="result-details">
                            <div class="metric">
                                <span class="metric-label">Items Processed:</span>
                                <span class="metric-value">${data.total_items_processed}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Space ${dryRun ? 'Would Be' : ''} Freed:</span>
                                <span class="metric-value">${data.total_mb_freed.toFixed(2)} MB</span>
                            </div>
                        </div>
                        ${data.operations && data.operations.length > 0 ? `
                            <div class="operations-list">
                                <h5>Operations:</h5>
                                ${data.operations.map(op => `
                                    <div class="operation-item ${op.success ? 'success' : 'error'}">
                                        <strong>${op.action}</strong>: 
                                        ${op.items_processed} items, ${op.mb_freed.toFixed(2)} MB
                                        (${op.duration_seconds.toFixed(2)}s)
                                        ${op.error_message ? `<br><span class="error">${op.error_message}</span>` : ''}
                                    </div>
                                `).join('')}
                            </div>
                        ` : ''}
                    </div>
                `;

                this.showSuccess(
                    dryRun ? 'Cleanup Preview Complete' : 'Cleanup Complete', 
                    `${dryRun ? 'Would free' : 'Freed'} ${data.total_mb_freed.toFixed(2)} MB`
                );
            } else {
                throw new Error(response.error || 'Cleanup failed');
            }
        } catch (error) {
            console.error('Cleanup failed:', error);
            statusDiv.style.display = 'none';
            resultsDiv.style.display = 'block';
            resultsDiv.innerHTML = `
                <div class="operation-result error">
                    <h4>❌ Cleanup Failed</h4>
                    <p>${error.message}</p>
                </div>
            `;
            this.showError('Cleanup Failed', error.message);
        } finally {
            cleanupBtn.disabled = false;
            dryRunBtn.disabled = false;
        }
    },

    async exportData() {
        const statusDiv = document.getElementById('export-status');
        const resultsDiv = document.getElementById('export-results');
        const messageEl = document.getElementById('export-message');
        const exportBtn = document.getElementById('export-btn');
        const includeEmbeddings = document.getElementById('include-embeddings').checked;
        const compress = document.getElementById('compress-export').checked;

        try {
            // Show loading state
            statusDiv.style.display = 'block';
            resultsDiv.style.display = 'none';
            messageEl.textContent = 'Preparing data export...';
            exportBtn.disabled = true;

            const response = await CortexAPI.request('POST', '/database/export', {
                include_embeddings: includeEmbeddings,
                compress: compress
            });

            if (response.success) {
                const data = response.data;
                statusDiv.style.display = 'none';
                resultsDiv.style.display = 'block';
                
                resultsDiv.innerHTML = `
                    <div class="operation-result success">
                        <h4>📤 Export Complete</h4>
                        <div class="result-details">
                            <div class="metric">
                                <span class="metric-label">File Size:</span>
                                <span class="metric-value">${data.file_size_mb} MB</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Export Time:</span>
                                <span class="metric-value">${new Date(data.timestamp).toLocaleString()}</span>
                            </div>
                        </div>
                        <div class="export-actions">
                            <a href="${data.download_url}" class="btn btn-primary" download>
                                <span class="btn-icon">💾</span>
                                Download Export File
                            </a>
                        </div>
                    </div>
                `;

                this.showSuccess('Export Complete', `File ready for download (${data.file_size_mb} MB)`);
            } else {
                throw new Error(response.error || 'Export failed');
            }
        } catch (error) {
            console.error('Export failed:', error);
            statusDiv.style.display = 'none';
            resultsDiv.style.display = 'block';
            resultsDiv.innerHTML = `
                <div class="operation-result error">
                    <h4>❌ Export Failed</h4>
                    <p>${error.message}</p>
                </div>
            `;
            this.showError('Export Failed', error.message);
        } finally {
            exportBtn.disabled = false;
        }
    },

    showImportModal() {
        const modal = document.getElementById('import-modal');
        if (modal) {
            modal.style.display = 'flex';
        }
    },

    async importData() {
        const fileInput = document.getElementById('import-file-input');
        const overwriteExisting = document.getElementById('overwrite-existing').checked;
        const importConversations = document.getElementById('import-conversations').checked;
        const importProjects = document.getElementById('import-projects').checked;
        const importPreferences = document.getElementById('import-preferences').checked;
        const importContextLinks = document.getElementById('import-context-links').checked;

        if (!fileInput.files || fileInput.files.length === 0) {
            this.showError('Import Error', 'Please select a file to import');
            return;
        }

        const file = fileInput.files[0];
        
        try {
            // For now, show a placeholder message since file upload requires more complex implementation
            this.showInfo('Import Feature', 'File import functionality requires server-side file upload implementation. This will be completed in the next iteration.');
            this.closeModal('import-modal');
        } catch (error) {
            console.error('Import failed:', error);
            this.showError('Import Failed', error.message);
        }
    },

    async loadMaintenanceHistory() {
        const historyDiv = document.getElementById('maintenance-history');
        if (!historyDiv) return;

        try {
            historyDiv.innerHTML = `
                <div class="loading-state">
                    <div class="loading-spinner"></div>
                    <p>Loading maintenance history...</p>
                </div>
            `;

            const response = await CortexAPI.request('GET', '/database/maintenance-history');

            if (response.success && response.data.operations) {
                const operations = response.data.operations;
                
                if (operations.length === 0) {
                    historyDiv.innerHTML = `
                        <div class="empty-state">
                            <p>No maintenance operations recorded yet.</p>
                        </div>
                    `;
                } else {
                    historyDiv.innerHTML = `
                        <div class="history-list">
                            ${operations.map(op => `
                                <div class="history-item ${op.status}">
                                    <div class="history-header">
                                        <span class="operation-type">${this.formatOperationType(op.operation_type)}</span>
                                        <span class="operation-date">${new Date(op.timestamp).toLocaleString()}</span>
                                    </div>
                                    <div class="history-details">
                                        <span class="status-badge ${op.status}">${op.status}</span>
                                        <span class="duration">${op.duration_seconds.toFixed(2)}s</span>
                                        ${this.formatOperationDetails(op.operation_type, op.details)}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `;
                }
            } else {
                throw new Error(response.error || 'Failed to load maintenance history');
            }
        } catch (error) {
            console.error('Failed to load maintenance history:', error);
            historyDiv.innerHTML = `
                <div class="error-state">
                    <p>Failed to load maintenance history: ${error.message}</p>
                    <button class="btn btn-secondary" onclick="CortexUI.loadMaintenanceHistory()">Retry</button>
                </div>
            `;
        }
    },

    async loadDatabaseStatistics() {
        const statsDiv = document.getElementById('database-stats');
        if (!statsDiv) return;

        try {
            const response = await CortexAPI.getStats();

            if (response.success) {
                const stats = response.data;
                
                statsDiv.innerHTML = `
                    <div class="stats-grid">
                        <div class="stat-item">
                            <div class="stat-value">${CortexUtils.formatNumber(stats.total_conversations || 0)}</div>
                            <div class="stat-label">Total Conversations</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${CortexUtils.formatNumber(stats.total_projects || 0)}</div>
                            <div class="stat-label">Total Projects</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${stats.database_size_mb ? stats.database_size_mb.toFixed(1) + ' MB' : 'N/A'}</div>
                            <div class="stat-label">Database Size</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${stats.last_backup ? new Date(stats.last_backup).toLocaleDateString() : 'Never'}</div>
                            <div class="stat-label">Last Backup</div>
                        </div>
                    </div>
                `;
            } else {
                throw new Error(response.error || 'Failed to load database statistics');
            }
        } catch (error) {
            console.error('Failed to load database statistics:', error);
            statsDiv.innerHTML = `
                <div class="error-state">
                    <p>Failed to load statistics: ${error.message}</p>
                </div>
            `;
        }
    },

    formatOperationType(type) {
        const types = {
            'integrity_check': '🔍 Integrity Check',
            'cleanup': '🧹 Cleanup',
            'export': '📤 Export',
            'import': '📥 Import'
        };
        return types[type] || type;
    },

    formatOperationDetails(type, details) {
        if (!details) return '';
        
        switch (type) {
            case 'integrity_check':
                return `<span class="detail">${details.issues_found || 0} issues found</span>`;
            case 'cleanup':
                return `<span class="detail">${details.mb_freed || 0} MB freed, ${details.items_processed || 0} items</span>`;
            case 'export':
                return `<span class="detail">${details.file_size_mb || 0} MB exported</span>`;
            case 'import':
                return `<span class="detail">${details.items_imported || 0} items imported</span>`;
            default:
                return '';
        }
    },

    // API Testing Interface Implementation
    async loadApiTab() {
        const panel = document.getElementById('api-panel');
        if (!panel) return;

        try {
            // Initialize API testing state if not exists
            if (!this.apiTestingState) {
                this.apiTestingState = {
                    requestHistory: CortexUtils.storage.get('cortex_api_request_history', []),
                    currentRequest: {
                        method: 'GET',
                        endpoint: '',
                        headers: {},
                        body: ''
                    },
                    response: null,
                    loading: false
                };
            }

            panel.innerHTML = this.renderApiTestingInterface();
            this.setupApiTestingEventListeners();
            this.loadApiEndpoints();
        } catch (error) {
            console.error('Error loading API testing interface:', error);
            panel.innerHTML = `
                <div class="error-state">
                    <h3>Failed to load API testing interface</h3>
                    <p>${error.message}</p>
                    <button class="btn btn-primary" onclick="CortexUI.loadApiTab()">Retry</button>
                </div>
            `;
        }
    },

    renderApiTestingInterface() {
        return `
            <div class="panel-header">
                <div class="api-header">
                    <div>
                        <h2>API Testing Interface</h2>
                        <p>Test and explore all available API endpoints</p>
                    </div>
                    <div class="api-header-actions">
                        <button class="btn btn-secondary" onclick="CortexUI.clearApiHistory()">
                            <span class="btn-icon">🗑️</span>
                            Clear History
                        </button>
                        <button class="btn btn-primary" onclick="CortexUI.exportApiHistory()">
                            <span class="btn-icon">📥</span>
                            Export History
                        </button>
                    </div>
                </div>
            </div>

            <div class="api-testing-container">
                <div class="api-testing-grid">
                    <!-- Request Builder -->
                    <div class="api-request-section">
                        <div class="card">
                            <div class="card-header">
                                <h3>Request Builder</h3>
                                <div class="request-actions">
                                    <button class="btn btn-success" onclick="CortexUI.sendApiRequest()" id="send-request-btn">
                                        <span class="btn-icon">🚀</span>
                                        Send Request
                                    </button>
                                    <button class="btn btn-secondary" onclick="CortexUI.clearApiRequest()">
                                        <span class="btn-icon">🧹</span>
                                        Clear
                                    </button>
                                </div>
                            </div>
                            <div class="card-content">
                                <!-- HTTP Method and Endpoint -->
                                <div class="request-line">
                                    <div class="method-selector">
                                        <label for="api-method">Method:</label>
                                        <select id="api-method" class="form-control">
                                            <option value="GET">GET</option>
                                            <option value="POST">POST</option>
                                            <option value="PUT">PUT</option>
                                            <option value="DELETE">DELETE</option>
                                            <option value="PATCH">PATCH</option>
                                        </select>
                                    </div>
                                    <div class="endpoint-input">
                                        <label for="api-endpoint">Endpoint:</label>
                                        <input type="text" id="api-endpoint" class="form-control" 
                                               placeholder="/health" value="">
                                    </div>
                                </div>

                                <!-- Headers -->
                                <div class="request-section">
                                    <div class="section-header">
                                        <h4>Headers</h4>
                                        <button class="btn btn-text btn-sm" onclick="CortexUI.addApiHeader()">
                                            <span class="btn-icon">➕</span>
                                            Add Header
                                        </button>
                                    </div>
                                    <div id="api-headers-container" class="headers-container">
                                        <div class="header-row">
                                            <input type="text" placeholder="Header name" class="form-control header-key">
                                            <input type="text" placeholder="Header value" class="form-control header-value">
                                            <button class="btn btn-text btn-danger btn-sm" onclick="this.parentElement.remove()">
                                                <span class="btn-icon">❌</span>
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                <!-- Request Body -->
                                <div class="request-section">
                                    <div class="section-header">
                                        <h4>Request Body</h4>
                                        <div class="body-actions">
                                            <button class="btn btn-text btn-sm" onclick="CortexUI.formatApiRequestBody()">
                                                <span class="btn-icon">🎨</span>
                                                Format JSON
                                            </button>
                                            <button class="btn btn-text btn-sm" onclick="CortexUI.clearApiRequestBody()">
                                                <span class="btn-icon">🧹</span>
                                                Clear
                                            </button>
                                        </div>
                                    </div>
                                    <div class="body-editor">
                                        <textarea id="api-request-body" class="form-control code-editor" 
                                                  placeholder='{"key": "value"}' rows="8"></textarea>
                                        <div id="body-validation" class="validation-message"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Response Display -->
                    <div class="api-response-section">
                        <div class="card">
                            <div class="card-header">
                                <h3>Response</h3>
                                <div class="response-actions">
                                    <button class="btn btn-text btn-sm" onclick="CortexUI.copyApiResponse()" 
                                            id="copy-response-btn" style="display: none;">
                                        <span class="btn-icon">📋</span>
                                        Copy Response
                                    </button>
                                    <button class="btn btn-text btn-sm" onclick="CortexUI.downloadApiResponse()" 
                                            id="download-response-btn" style="display: none;">
                                        <span class="btn-icon">💾</span>
                                        Download
                                    </button>
                                </div>
                            </div>
                            <div class="card-content">
                                <div id="api-response-container" class="response-container">
                                    <div class="empty-response">
                                        <div class="empty-icon">📡</div>
                                        <p>No response yet</p>
                                        <p class="text-muted">Send a request to see the response here</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Endpoint Documentation -->
                <div class="api-endpoints-section">
                    <div class="card">
                        <div class="card-header">
                            <h3>Available Endpoints</h3>
                            <div class="endpoints-actions">
                                <input type="text" id="endpoints-search" class="form-control" 
                                       placeholder="Search endpoints..." style="width: 200px;">
                                <button class="btn btn-secondary" onclick="CortexUI.refreshApiEndpoints()">
                                    <span class="btn-icon">🔄</span>
                                    Refresh
                                </button>
                            </div>
                        </div>
                        <div class="card-content">
                            <div id="api-endpoints-container" class="endpoints-container">
                                <div class="loading-state">
                                    <div class="loading-spinner"></div>
                                    <p>Loading endpoints...</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Request History -->
                <div class="api-history-section">
                    <div class="card">
                        <div class="card-header">
                            <h3>Request History</h3>
                            <div class="history-actions">
                                <span class="history-count" id="history-count">0 requests</span>
                            </div>
                        </div>
                        <div class="card-content">
                            <div id="api-history-container" class="history-container">
                                <div class="empty-state">
                                    <div class="empty-icon">📜</div>
                                    <p>No request history</p>
                                    <p class="text-muted">Your API requests will appear here</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    setupApiTestingEventListeners() {
        // Method change handler
        const methodSelect = document.getElementById('api-method');
        if (methodSelect) {
            methodSelect.addEventListener('change', (e) => {
                this.apiTestingState.currentRequest.method = e.target.value;
                this.updateRequestBodyVisibility();
            });
        }

        // Endpoint input handler
        const endpointInput = document.getElementById('api-endpoint');
        if (endpointInput) {
            endpointInput.addEventListener('input', (e) => {
                this.apiTestingState.currentRequest.endpoint = e.target.value;
            });
        }

        // Request body validation
        const bodyTextarea = document.getElementById('api-request-body');
        if (bodyTextarea) {
            bodyTextarea.addEventListener('input', (e) => {
                this.apiTestingState.currentRequest.body = e.target.value;
                this.validateRequestBody();
            });
        }

        // Endpoints search
        const endpointsSearch = document.getElementById('endpoints-search');
        if (endpointsSearch) {
            endpointsSearch.addEventListener('input', (e) => {
                this.filterApiEndpoints(e.target.value);
            });
        }

        // Keyboard shortcuts for API testing
        document.addEventListener('keydown', (e) => {
            if (this.state.currentTab === 'api') {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                    e.preventDefault();
                    this.sendApiRequest();
                }
            }
        });
    },

    async loadApiEndpoints() {
        const container = document.getElementById('api-endpoints-container');
        if (!container) return;

        try {
            // Define available endpoints with descriptions
            const endpoints = [
                {
                    method: 'GET',
                    path: '/health',
                    description: 'Check system health status',
                    category: 'System',
                    example: null
                },
                {
                    method: 'GET',
                    path: '/stats',
                    description: 'Get database statistics',
                    category: 'System',
                    example: null
                },
                {
                    method: 'POST',
                    path: '/context',
                    description: 'Store conversation context',
                    category: 'Context',
                    example: {
                        content: 'Example conversation content',
                        tool_name: 'example-tool',
                        metadata: { key: 'value' },
                        project_id: 'optional-project-id'
                    }
                },
                {
                    method: 'POST',
                    path: '/context/search',
                    description: 'Search stored context',
                    category: 'Context',
                    example: {
                        query: 'search query',
                        search_type: 'hybrid',
                        limit: 10
                    }
                },
                {
                    method: 'GET',
                    path: '/projects/{project_id}/context',
                    description: 'Get project context',
                    category: 'Context',
                    example: null
                },
                {
                    method: 'POST',
                    path: '/conversations',
                    description: 'Create new conversation',
                    category: 'Conversations',
                    example: {
                        content: 'Conversation content',
                        tool_name: 'example-tool',
                        project_id: 'optional-project-id'
                    }
                },
                {
                    method: 'GET',
                    path: '/conversations',
                    description: 'List conversations',
                    category: 'Conversations',
                    example: null
                },
                {
                    method: 'GET',
                    path: '/conversations/{id}',
                    description: 'Get conversation by ID',
                    category: 'Conversations',
                    example: null
                },
                {
                    method: 'PUT',
                    path: '/conversations/{id}',
                    description: 'Update conversation',
                    category: 'Conversations',
                    example: {
                        content: 'Updated content',
                        metadata: { updated: true }
                    }
                },
                {
                    method: 'DELETE',
                    path: '/conversations/{id}',
                    description: 'Delete conversation',
                    category: 'Conversations',
                    example: null
                },
                {
                    method: 'POST',
                    path: '/projects',
                    description: 'Create new project',
                    category: 'Projects',
                    example: {
                        name: 'Project Name',
                        description: 'Project description',
                        path: '/path/to/project'
                    }
                },
                {
                    method: 'GET',
                    path: '/projects',
                    description: 'List projects',
                    category: 'Projects',
                    example: null
                },
                {
                    method: 'GET',
                    path: '/projects/{id}',
                    description: 'Get project by ID',
                    category: 'Projects',
                    example: null
                },
                {
                    method: 'PUT',
                    path: '/projects/{id}',
                    description: 'Update project',
                    category: 'Projects',
                    example: {
                        name: 'Updated Name',
                        description: 'Updated description'
                    }
                },
                {
                    method: 'DELETE',
                    path: '/projects/{id}',
                    description: 'Delete project',
                    category: 'Projects',
                    example: null
                },
                {
                    method: 'POST',
                    path: '/preferences',
                    description: 'Create/update preference',
                    category: 'Preferences',
                    example: {
                        key: 'preference_key',
                        value: 'preference_value',
                        category: 'general'
                    }
                },
                {
                    method: 'GET',
                    path: '/preferences',
                    description: 'List preferences',
                    category: 'Preferences',
                    example: null
                },
                {
                    method: 'GET',
                    path: '/preferences/{key}',
                    description: 'Get preference by key',
                    category: 'Preferences',
                    example: null
                },
                {
                    method: 'PUT',
                    path: '/preferences/{key}',
                    description: 'Update preference',
                    category: 'Preferences',
                    example: {
                        value: 'new_value'
                    }
                },
                {
                    method: 'DELETE',
                    path: '/preferences/{key}',
                    description: 'Delete preference',
                    category: 'Preferences',
                    example: null
                },
                {
                    method: 'POST',
                    path: '/api-keys',
                    description: 'Create new API key',
                    category: 'API Keys',
                    example: {
                        name: 'Key Name',
                        description: 'Key description'
                    }
                },
                {
                    method: 'GET',
                    path: '/api-keys',
                    description: 'List API keys',
                    category: 'API Keys',
                    example: null
                },
                {
                    method: 'GET',
                    path: '/api-keys/{id}',
                    description: 'Get API key by ID',
                    category: 'API Keys',
                    example: null
                },
                {
                    method: 'PUT',
                    path: '/api-keys/{id}',
                    description: 'Update API key',
                    category: 'API Keys',
                    example: {
                        name: 'Updated Name'
                    }
                },
                {
                    method: 'DELETE',
                    path: '/api-keys/{id}',
                    description: 'Delete API key',
                    category: 'API Keys',
                    example: null
                },
                {
                    method: 'POST',
                    path: '/api-keys/{id}/deactivate',
                    description: 'Deactivate API key',
                    category: 'API Keys',
                    example: null
                },
                {
                    method: 'POST',
                    path: '/api-keys/{id}/rotate',
                    description: 'Rotate API key',
                    category: 'API Keys',
                    example: null
                },
                {
                    method: 'GET',
                    path: '/monitoring/health',
                    description: 'Comprehensive health check',
                    category: 'Monitoring',
                    example: null
                },
                {
                    method: 'GET',
                    path: '/monitoring/storage',
                    description: 'Storage usage information',
                    category: 'Monitoring',
                    example: null
                },
                {
                    method: 'GET',
                    path: '/monitoring/performance',
                    description: 'Performance metrics',
                    category: 'Monitoring',
                    example: null
                }
            ];

            this.apiEndpoints = endpoints;
            this.renderApiEndpoints(endpoints);

        } catch (error) {
            console.error('Error loading API endpoints:', error);
            container.innerHTML = `
                <div class="error-state">
                    <p>Failed to load endpoints</p>
                    <button class="btn btn-secondary" onclick="CortexUI.loadApiEndpoints()">Retry</button>
                </div>
            `;
        }
    },

    renderApiEndpoints(endpoints) {
        const container = document.getElementById('api-endpoints-container');
        if (!container) return;

        // Group endpoints by category
        const groupedEndpoints = endpoints.reduce((groups, endpoint) => {
            const category = endpoint.category || 'Other';
            if (!groups[category]) {
                groups[category] = [];
            }
            groups[category].push(endpoint);
            return groups;
        }, {});

        const html = Object.entries(groupedEndpoints).map(([category, categoryEndpoints]) => `
            <div class="endpoint-category">
                <h4 class="category-title">${category}</h4>
                <div class="endpoints-list">
                    ${categoryEndpoints.map(endpoint => this.renderEndpointItem(endpoint)).join('')}
                </div>
            </div>
        `).join('');

        container.innerHTML = html;
    },

    renderEndpointItem(endpoint) {
        const methodClass = endpoint.method.toLowerCase();
        const hasExample = endpoint.example !== null;
        
        return `
            <div class="endpoint-item" data-method="${endpoint.method}" data-path="${endpoint.path}">
                <div class="endpoint-header" onclick="CortexUI.toggleEndpointDetails(this)">
                    <div class="endpoint-info">
                        <span class="method-badge ${methodClass}">${endpoint.method}</span>
                        <span class="endpoint-path">${endpoint.path}</span>
                    </div>
                    <div class="endpoint-actions">
                        <button class="btn btn-text btn-sm" onclick="event.stopPropagation(); CortexUI.useEndpoint('${endpoint.method}', '${endpoint.path}', ${hasExample ? 'true' : 'false'})">
                            <span class="btn-icon">📝</span>
                            Use
                        </button>
                        <span class="expand-icon">▼</span>
                    </div>
                </div>
                <div class="endpoint-details" style="display: none;">
                    <p class="endpoint-description">${endpoint.description}</p>
                    ${hasExample ? `
                        <div class="endpoint-example">
                            <h5>Example Request Body:</h5>
                            <pre class="code-block">${JSON.stringify(endpoint.example, null, 2)}</pre>
                            <button class="btn btn-text btn-sm" onclick="CortexUI.copyEndpointExample('${endpoint.method}', '${endpoint.path}')">
                                <span class="btn-icon">📋</span>
                                Copy Example
                            </button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    },

    toggleEndpointDetails(headerElement) {
        const details = headerElement.nextElementSibling;
        const expandIcon = headerElement.querySelector('.expand-icon');
        
        if (details.style.display === 'none') {
            details.style.display = 'block';
            expandIcon.textContent = '▲';
        } else {
            details.style.display = 'none';
            expandIcon.textContent = '▼';
        }
    },

    useEndpoint(method, path, hasExample = false) {
        // Set method and endpoint
        document.getElementById('api-method').value = method;
        document.getElementById('api-endpoint').value = path;
        
        this.apiTestingState.currentRequest.method = method;
        this.apiTestingState.currentRequest.endpoint = path;

        // If endpoint has example and method supports body, populate it
        if (hasExample && ['POST', 'PUT', 'PATCH'].includes(method)) {
            const endpoint = this.apiEndpoints.find(e => e.method === method && e.path === path);
            if (endpoint && endpoint.example) {
                document.getElementById('api-request-body').value = JSON.stringify(endpoint.example, null, 2);
                this.apiTestingState.currentRequest.body = JSON.stringify(endpoint.example, null, 2);
            }
        }

        this.updateRequestBodyVisibility();
        this.showToast(`Endpoint ${method} ${path} loaded into request builder`, 'success');
        
        // Scroll to request builder
        document.querySelector('.api-request-section').scrollIntoView({ behavior: 'smooth' });
    },

    copyEndpointExample(method, path) {
        const endpoint = this.apiEndpoints.find(e => e.method === method && e.path === path);
        if (endpoint && endpoint.example) {
            const exampleText = JSON.stringify(endpoint.example, null, 2);
            CortexUtils.copyToClipboard(exampleText);
            this.showToast('Example copied to clipboard', 'success');
        }
    },

    filterApiEndpoints(query) {
        if (!this.apiEndpoints) return;

        const filteredEndpoints = this.apiEndpoints.filter(endpoint => {
            const searchText = `${endpoint.method} ${endpoint.path} ${endpoint.description} ${endpoint.category}`.toLowerCase();
            return searchText.includes(query.toLowerCase());
        });

        this.renderApiEndpoints(filteredEndpoints);
    },

    refreshApiEndpoints() {
        this.loadApiEndpoints();
        this.showToast('Endpoints refreshed', 'success');
    },

    updateRequestBodyVisibility() {
        const method = this.apiTestingState.currentRequest.method;
        const bodySection = document.querySelector('.request-section:last-child');
        
        if (bodySection) {
            if (['POST', 'PUT', 'PATCH'].includes(method)) {
                bodySection.style.display = 'block';
            } else {
                bodySection.style.display = 'none';
            }
        }
    },

    addApiHeader() {
        const container = document.getElementById('api-headers-container');
        if (!container) return;

        const headerRow = document.createElement('div');
        headerRow.className = 'header-row';
        headerRow.innerHTML = `
            <input type="text" placeholder="Header name" class="form-control header-key">
            <input type="text" placeholder="Header value" class="form-control header-value">
            <button class="btn btn-text btn-danger btn-sm" onclick="this.parentElement.remove()">
                <span class="btn-icon">❌</span>
            </button>
        `;
        
        container.appendChild(headerRow);
    },

    validateRequestBody() {
        const bodyTextarea = document.getElementById('api-request-body');
        const validationDiv = document.getElementById('body-validation');
        
        if (!bodyTextarea || !validationDiv) return;

        const body = bodyTextarea.value.trim();
        
        if (!body) {
            validationDiv.innerHTML = '';
            bodyTextarea.classList.remove('error', 'success');
            return;
        }

        try {
            JSON.parse(body);
            validationDiv.innerHTML = '<span class="validation-success">✓ Valid JSON</span>';
            bodyTextarea.classList.remove('error');
            bodyTextarea.classList.add('success');
        } catch (error) {
            validationDiv.innerHTML = `<span class="validation-error">✗ Invalid JSON: ${error.message}</span>`;
            bodyTextarea.classList.remove('success');
            bodyTextarea.classList.add('error');
        }
    },

    formatApiRequestBody() {
        const bodyTextarea = document.getElementById('api-request-body');
        if (!bodyTextarea) return;

        const body = bodyTextarea.value.trim();
        if (!body) return;

        try {
            const parsed = JSON.parse(body);
            bodyTextarea.value = JSON.stringify(parsed, null, 2);
            this.apiTestingState.currentRequest.body = bodyTextarea.value;
            this.showToast('JSON formatted successfully', 'success');
        } catch (error) {
            this.showToast('Invalid JSON - cannot format', 'error');
        }
    },

    clearApiRequestBody() {
        const bodyTextarea = document.getElementById('api-request-body');
        if (bodyTextarea) {
            bodyTextarea.value = '';
            this.apiTestingState.currentRequest.body = '';
            this.validateRequestBody();
        }
    },

    clearApiRequest() {
        document.getElementById('api-method').value = 'GET';
        document.getElementById('api-endpoint').value = '';
        document.getElementById('api-request-body').value = '';
        
        // Clear headers except first one
        const headersContainer = document.getElementById('api-headers-container');
        if (headersContainer) {
            const headerRows = headersContainer.querySelectorAll('.header-row');
            headerRows.forEach((row, index) => {
                if (index === 0) {
                    row.querySelector('.header-key').value = '';
                    row.querySelector('.header-value').value = '';
                } else {
                    row.remove();
                }
            });
        }

        this.apiTestingState.currentRequest = {
            method: 'GET',
            endpoint: '',
            headers: {},
            body: ''
        };

        this.updateRequestBodyVisibility();
        this.validateRequestBody();
        this.showToast('Request cleared', 'success');
    },

    async sendApiRequest() {
        if (this.apiTestingState.loading) return;

        const sendBtn = document.getElementById('send-request-btn');
        const responseContainer = document.getElementById('api-response-container');
        
        if (!sendBtn || !responseContainer) return;

        let startTime;
        try {
            // Validate request
            const method = document.getElementById('api-method').value;
            const endpoint = document.getElementById('api-endpoint').value.trim();
            
            if (!endpoint) {
                this.showToast('Please enter an endpoint', 'error');
                return;
            }

            // Set loading state
            this.apiTestingState.loading = true;
            sendBtn.disabled = true;
            sendBtn.innerHTML = '<span class="loading-spinner small"></span> Sending...';

            // Collect headers
            const headers = {};
            const headerRows = document.querySelectorAll('#api-headers-container .header-row');
            headerRows.forEach(row => {
                const key = row.querySelector('.header-key').value.trim();
                const value = row.querySelector('.header-value').value.trim();
                if (key && value) {
                    headers[key] = value;
                }
            });

            // Collect request body
            let body = null;
            if (['POST', 'PUT', 'PATCH'].includes(method)) {
                const bodyText = document.getElementById('api-request-body').value.trim();
                if (bodyText) {
                    try {
                        body = JSON.parse(bodyText);
                    } catch (error) {
                        this.showToast('Invalid JSON in request body', 'error');
                        return;
                    }
                }
            }

            // Show loading in response container
            responseContainer.innerHTML = `
                <div class="loading-state">
                    <div class="loading-spinner"></div>
                    <p>Sending request...</p>
                </div>
            `;

            // Record request start time
            startTime = performance.now();

            // Make API request
            const response = await CortexAPI.request(method, endpoint, {
                data: body,
                headers: headers
            });

            const endTime = performance.now();
            const duration = Math.round(endTime - startTime);

            // Store response
            this.apiTestingState.response = response;

            // Display response
            this.displayApiResponse(response, duration);

            // Add to history
            this.addToApiHistory({
                method,
                endpoint,
                headers,
                body,
                response,
                duration,
                timestamp: new Date().toISOString()
            });

            this.showToast(`Request completed in ${duration}ms`, 'success');

        } catch (error) {
            console.error('API request failed:', error);
            
            const endTime = performance.now();
            const duration = startTime ? Math.round(endTime - startTime) : 0;

            // Display error response
            this.displayApiError(error, duration);

            // Add error to history
            this.addToApiHistory({
                method: document.getElementById('api-method').value,
                endpoint: document.getElementById('api-endpoint').value,
                headers: {},
                body: null,
                error: error.message,
                duration,
                timestamp: new Date().toISOString()
            });

            this.showToast('Request failed', 'error');

        } finally {
            // Reset loading state
            this.apiTestingState.loading = false;
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<span class="btn-icon">🚀</span> Send Request';
        }
    },

    displayApiResponse(response, duration) {
        const container = document.getElementById('api-response-container');
        if (!container) return;

        const statusClass = response.success ? 'success' : 'error';
        const statusIcon = response.success ? '✅' : '❌';

        container.innerHTML = `
            <div class="response-header">
                <div class="response-status ${statusClass}">
                    <span class="status-icon">${statusIcon}</span>
                    <span class="status-code">${response.status}</span>
                    <span class="status-text">${response.statusText}</span>
                </div>
                <div class="response-meta">
                    <span class="response-time">${duration}ms</span>
                    <span class="response-size">${this.getResponseSize(response.data)}</span>
                </div>
            </div>

            <div class="response-tabs">
                <button class="response-tab active" onclick="CortexUI.showResponseTab(this, 'body')">Response Body</button>
                <button class="response-tab" onclick="CortexUI.showResponseTab(this, 'headers')">Headers</button>
            </div>

            <div class="response-content">
                <div class="response-tab-content active" data-tab="body">
                    <div class="response-body">
                        <pre class="code-block">${this.formatResponseData(response.data)}</pre>
                    </div>
                </div>
                <div class="response-tab-content" data-tab="headers">
                    <div class="response-headers">
                        <pre class="code-block">${JSON.stringify(response.headers, null, 2)}</pre>
                    </div>
                </div>
            </div>
        `;

        // Show response actions
        document.getElementById('copy-response-btn').style.display = 'inline-block';
        document.getElementById('download-response-btn').style.display = 'inline-block';
    },

    displayApiError(error, duration) {
        const container = document.getElementById('api-response-container');
        if (!container) return;

        const response = error.response;
        const statusCode = response ? response.status : 'Network Error';
        const statusText = response ? response.statusText : error.message;

        container.innerHTML = `
            <div class="response-header">
                <div class="response-status error">
                    <span class="status-icon">❌</span>
                    <span class="status-code">${statusCode}</span>
                    <span class="status-text">${statusText}</span>
                </div>
                <div class="response-meta">
                    <span class="response-time">${duration}ms</span>
                </div>
            </div>

            <div class="response-content">
                <div class="error-details">
                    <h4>Error Details</h4>
                    <pre class="code-block error">${response ? this.formatResponseData(response.data) : error.message}</pre>
                    ${response && response.headers ? `
                        <h4>Response Headers</h4>
                        <pre class="code-block">${JSON.stringify(response.headers, null, 2)}</pre>
                    ` : ''}
                </div>
            </div>
        `;
    },

    showResponseTab(tabButton, tabName) {
        // Update tab buttons
        document.querySelectorAll('.response-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        tabButton.classList.add('active');

        // Update tab content
        document.querySelectorAll('.response-tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    },

    formatResponseData(data) {
        if (typeof data === 'string') {
            try {
                const parsed = JSON.parse(data);
                return JSON.stringify(parsed, null, 2);
            } catch {
                return data;
            }
        } else if (typeof data === 'object') {
            return JSON.stringify(data, null, 2);
        } else {
            return String(data);
        }
    },

    getResponseSize(data) {
        const size = new Blob([this.formatResponseData(data)]).size;
        return CortexUtils.formatFileSize(size);
    },

    copyApiResponse() {
        if (!this.apiTestingState.response) return;

        const responseText = this.formatResponseData(this.apiTestingState.response.data);
        CortexUtils.copyToClipboard(responseText);
        this.showToast('Response copied to clipboard', 'success');
    },

    downloadApiResponse() {
        if (!this.apiTestingState.response) return;

        const responseText = this.formatResponseData(this.apiTestingState.response.data);
        const filename = `api-response-${new Date().toISOString().split('T')[0]}.json`;
        CortexUtils.downloadFile(responseText, filename, 'application/json');
        this.showToast('Response downloaded', 'success');
    },

    addToApiHistory(requestData) {
        this.apiTestingState.requestHistory.unshift(requestData);
        
        // Limit history to 50 items
        if (this.apiTestingState.requestHistory.length > 50) {
            this.apiTestingState.requestHistory = this.apiTestingState.requestHistory.slice(0, 50);
        }

        // Save to storage
        CortexUtils.storage.set('cortex_api_request_history', this.apiTestingState.requestHistory);

        // Update history display
        this.renderApiHistory();
    },

    renderApiHistory() {
        const container = document.getElementById('api-history-container');
        const countElement = document.getElementById('history-count');
        
        if (!container) return;

        const history = this.apiTestingState.requestHistory;
        
        if (countElement) {
            countElement.textContent = `${history.length} request${history.length !== 1 ? 's' : ''}`;
        }

        if (history.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📜</div>
                    <p>No request history</p>
                    <p class="text-muted">Your API requests will appear here</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="history-list">
                ${history.map((request, index) => this.renderHistoryItem(request, index)).join('')}
            </div>
        `;
    },

    renderHistoryItem(request, index) {
        const statusClass = request.error ? 'error' : 'success';
        const statusIcon = request.error ? '❌' : '✅';
        const statusText = request.error ? 'Error' : 'Success';
        const timestamp = CortexUtils.formatRelativeTime(request.timestamp);

        return `
            <div class="history-item ${statusClass}" data-index="${index}">
                <div class="history-header" onclick="CortexUI.toggleHistoryDetails(${index})">
                    <div class="history-info">
                        <span class="method-badge ${request.method.toLowerCase()}">${request.method}</span>
                        <span class="history-endpoint">${request.endpoint}</span>
                        <span class="history-status ${statusClass}">
                            ${statusIcon} ${statusText}
                        </span>
                    </div>
                    <div class="history-meta">
                        <span class="history-time">${timestamp}</span>
                        <span class="history-duration">${request.duration}ms</span>
                        <button class="btn btn-text btn-sm" onclick="event.stopPropagation(); CortexUI.replayRequest(${index})">
                            <span class="btn-icon">🔄</span>
                            Replay
                        </button>
                        <span class="expand-icon">▼</span>
                    </div>
                </div>
                <div class="history-details" style="display: none;">
                    ${Object.keys(request.headers).length > 0 ? `
                        <div class="history-section">
                            <h5>Headers:</h5>
                            <pre class="code-block small">${JSON.stringify(request.headers, null, 2)}</pre>
                        </div>
                    ` : ''}
                    ${request.body ? `
                        <div class="history-section">
                            <h5>Request Body:</h5>
                            <pre class="code-block small">${JSON.stringify(request.body, null, 2)}</pre>
                        </div>
                    ` : ''}
                    ${request.response ? `
                        <div class="history-section">
                            <h5>Response:</h5>
                            <pre class="code-block small">${this.formatResponseData(request.response.data).substring(0, 500)}${this.formatResponseData(request.response.data).length > 500 ? '...' : ''}</pre>
                        </div>
                    ` : ''}
                    ${request.error ? `
                        <div class="history-section">
                            <h5>Error:</h5>
                            <pre class="code-block small error">${request.error}</pre>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    },

    toggleHistoryDetails(index) {
        const item = document.querySelector(`[data-index="${index}"]`);
        if (!item) return;

        const details = item.querySelector('.history-details');
        const expandIcon = item.querySelector('.expand-icon');
        
        if (details.style.display === 'none') {
            details.style.display = 'block';
            expandIcon.textContent = '▲';
        } else {
            details.style.display = 'none';
            expandIcon.textContent = '▼';
        }
    },

    replayRequest(index) {
        const request = this.apiTestingState.requestHistory[index];
        if (!request) return;

        // Set method and endpoint
        document.getElementById('api-method').value = request.method;
        document.getElementById('api-endpoint').value = request.endpoint;

        // Set headers
        const headersContainer = document.getElementById('api-headers-container');
        if (headersContainer) {
            // Clear existing headers
            headersContainer.innerHTML = '';
            
            // Add headers from history
            Object.entries(request.headers).forEach(([key, value]) => {
                const headerRow = document.createElement('div');
                headerRow.className = 'header-row';
                headerRow.innerHTML = `
                    <input type="text" placeholder="Header name" class="form-control header-key" value="${key}">
                    <input type="text" placeholder="Header value" class="form-control header-value" value="${value}">
                    <button class="btn btn-text btn-danger btn-sm" onclick="this.parentElement.remove()">
                        <span class="btn-icon">❌</span>
                    </button>
                `;
                headersContainer.appendChild(headerRow);
            });

            // Add empty header row if no headers
            if (Object.keys(request.headers).length === 0) {
                this.addApiHeader();
            }
        }

        // Set request body
        if (request.body) {
            document.getElementById('api-request-body').value = JSON.stringify(request.body, null, 2);
        }

        // Update state
        this.apiTestingState.currentRequest = {
            method: request.method,
            endpoint: request.endpoint,
            headers: request.headers,
            body: request.body ? JSON.stringify(request.body, null, 2) : ''
        };

        this.updateRequestBodyVisibility();
        this.showToast('Request replayed from history', 'success');
        
        // Scroll to request builder
        document.querySelector('.api-request-section').scrollIntoView({ behavior: 'smooth' });
    },

    clearApiHistory() {
        if (confirm('Are you sure you want to clear all request history?')) {
            this.apiTestingState.requestHistory = [];
            CortexUtils.storage.remove('cortex_api_request_history');
            this.renderApiHistory();
            this.showToast('Request history cleared', 'success');
        }
    },

    exportApiHistory() {
        if (this.apiTestingState.requestHistory.length === 0) {
            this.showToast('No history to export', 'warning');
            return;
        }

        const exportData = {
            exported_at: new Date().toISOString(),
            total_requests: this.apiTestingState.requestHistory.length,
            requests: this.apiTestingState.requestHistory
        };

        const filename = `cortex-api-history-${new Date().toISOString().split('T')[0]}.json`;
        CortexUtils.downloadFile(JSON.stringify(exportData, null, 2), filename, 'application/json');
        this.showToast('History exported successfully', 'success');
    },

    // Placeholder methods for other functionality
    initializeTooltips() {
        // Tooltip initialization will be implemented as needed
    },

    initializeModals() {
        // Modal initialization will be implemented as needed
    },

    handleKeyboardShortcuts(e) {
        // Keyboard shortcuts will be implemented as needed
    },

    handleFormSubmission(e) {
        // Form submission handling will be implemented as needed
    },

    /**
     * Lazy load memories list
     * @param {Element} element - Container element
     */
    async loadMemoriesList(element) {
        try {
            const response = await CortexAPI.getConversations({ limit: 100 });
            if (response.success && response.data) {
                this.renderLargeList('memories-list', response.data, (memory, index) => {
                    const div = document.createElement('div');
                    div.className = 'memory-item';
                    div.innerHTML = `
                        <div class="memory-header">
                            <div class="memory-meta">
                                <span class="memory-tool">${CortexUtils.escapeHtml(memory.tool_name || 'Unknown')}</span>
                                <span class="memory-date">${CortexUtils.formatRelativeTime(memory.timestamp || memory.created_at)}</span>
                            </div>
                        </div>
                        <div class="memory-content">${CortexUtils.escapeHtml(CortexUtils.truncateText(memory.content || '', 200))}</div>
                    `;
                    return div;
                });
            }
        } catch (error) {
            element.innerHTML = `
                <div class="error-state">
                    <p>Failed to load memories: ${error.message}</p>
                    <button class="btn btn-secondary" onclick="CortexUI.loadMemoriesList(this.parentElement)">Retry</button>
                </div>
            `;
        }
    },

    /**
     * Lazy load projects list
     * @param {Element} element - Container element
     */
    async loadProjectsList(element) {
        try {
            const response = await CortexAPI.getProjects();
            if (response.success && response.data) {
                this.renderLargeList('projects-list', response.data, (project, index) => {
                    const div = document.createElement('div');
                    div.className = 'project-item';
                    div.innerHTML = `
                        <div class="project-header">
                            <h4>${CortexUtils.escapeHtml(project.name)}</h4>
                            <span class="project-date">${CortexUtils.formatRelativeTime(project.created_at)}</span>
                        </div>
                        <div class="project-description">${CortexUtils.escapeHtml(project.description || 'No description')}</div>
                    `;
                    return div;
                });
            }
        } catch (error) {
            element.innerHTML = `
                <div class="error-state">
                    <p>Failed to load projects: ${error.message}</p>
                    <button class="btn btn-secondary" onclick="CortexUI.loadProjectsList(this.parentElement)">Retry</button>
                </div>
            `;
        }
    },

    /**
     * Lazy load settings content
     * @param {Element} element - Container element
     */
    async loadSettingsContent(element) {
        try {
            const response = await CortexAPI.getPreferences();
            if (response.success && response.data) {
                element.innerHTML = `
                    <div class="settings-grid">
                        <div class="card">
                            <div class="card-header">
                                <h3>Performance Settings</h3>
                            </div>
                            <div class="card-content">
                                <div class="form-group">
                                    <label>
                                        <input type="checkbox" ${this.performance.enableVirtualScrolling ? 'checked' : ''}
                                               onchange="CortexUI.toggleVirtualScrolling(this.checked)">
                                        Enable Virtual Scrolling
                                    </label>
                                </div>
                                <div class="form-group">
                                    <label>
                                        <input type="checkbox" ${this.performance.enableLazyLoading ? 'checked' : ''}
                                               onchange="CortexUI.toggleLazyLoading(this.checked)">
                                        Enable Lazy Loading
                                    </label>
                                </div>
                                <div class="form-group">
                                    <label>Debounce Delay (ms)</label>
                                    <input type="number" class="form-control" value="${this.performance.debounceDelay}"
                                           onchange="CortexUI.setDebounceDelay(this.value)">
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }
        } catch (error) {
            element.innerHTML = `
                <div class="error-state">
                    <p>Failed to load settings: ${error.message}</p>
                    <button class="btn btn-secondary" onclick="CortexUI.loadSettingsContent(this.parentElement)">Retry</button>
                </div>
            `;
        }
    },

    /**
     * Lazy load monitoring content
     * @param {Element} element - Container element
     */
    async loadMonitoringContent(element) {
        try {
            const [healthResponse, performanceMetrics] = await Promise.all([
                CortexAPI.getHealth(),
                Promise.resolve(CortexAPI.performance.getMetrics())
            ]);

            element.innerHTML = `
                <div class="monitoring-grid">
                    <div class="card">
                        <div class="card-header">
                            <h3>API Performance</h3>
                        </div>
                        <div class="card-content">
                            <div id="performance-metrics">
                                ${Object.entries(performanceMetrics).map(([endpoint, metrics]) => `
                                    <div class="metric-row">
                                        <span class="endpoint">${endpoint}</span>
                                        <span class="avg-duration">${metrics.averageDuration.toFixed(2)}ms</span>
                                        <span class="success-rate">${((metrics.successCount / metrics.count) * 100).toFixed(1)}%</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header">
                            <h3>Cache Statistics</h3>
                        </div>
                        <div class="card-content">
                            <div id="cache-stats">
                                ${(() => {
                                    const stats = CortexAPI.cache.getStats();
                                    return `
                                        <div class="stat-item">
                                            <span class="stat-label">Cache Size</span>
                                            <span class="stat-value">${stats.size}/${stats.maxSize}</span>
                                        </div>
                                        <div class="stat-item">
                                            <span class="stat-label">Hit Rate</span>
                                            <span class="stat-value">${(stats.hitRate * 100).toFixed(1)}%</span>
                                        </div>
                                        <div class="stat-item">
                                            <span class="stat-label">Expired Entries</span>
                                            <span class="stat-value">${stats.expired}</span>
                                        </div>
                                    `;
                                })()}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } catch (error) {
            element.innerHTML = `
                <div class="error-state">
                    <p>Failed to load monitoring data: ${error.message}</p>
                    <button class="btn btn-secondary" onclick="CortexUI.loadMonitoringContent(this.parentElement)">Retry</button>
                </div>
            `;
        }
    },

    /**
     * Perform search with caching
     * @param {string} query - Search query
     */
    async performSearch(query) {
        const resultsContainer = document.getElementById('search-results');
        if (!resultsContainer) return;

        try {
            resultsContainer.innerHTML = `
                <div class="loading-state">
                    <div class="loading-spinner"></div>
                    <p>Searching...</p>
                </div>
            `;

            const searchType = document.getElementById('search-type')?.value || 'semantic';
            const response = await CortexAPI.searchMemories({
                query,
                search_type: searchType,
                limit: 50
            });

            if (response.success && response.data) {
                this.renderLargeList('search-results', response.data, (result, index) => {
                    const div = document.createElement('div');
                    div.className = 'search-result-item';
                    div.innerHTML = `
                        <div class="result-header">
                            <span class="result-score">Score: ${(result.score || 0).toFixed(3)}</span>
                            <span class="result-tool">${CortexUtils.escapeHtml(result.tool_name || 'Unknown')}</span>
                        </div>
                        <div class="result-content">${CortexUtils.escapeHtml(CortexUtils.truncateText(result.content || '', 300))}</div>
                    `;
                    return div;
                });
            } else {
                resultsContainer.innerHTML = `
                    <div class="empty-state">
                        <p>No results found for "${CortexUtils.escapeHtml(query)}"</p>
                    </div>
                `;
            }
        } catch (error) {
            resultsContainer.innerHTML = `
                <div class="error-state">
                    <p>Search failed: ${error.message}</p>
                    <button class="btn btn-secondary" onclick="CortexUI.performSearch('${CortexUtils.escapeHtml(query)}')">Retry</button>
                </div>
            `;
        }
    },

    /**
     * Search memories with debouncing
     * @param {string} query - Search query
     */
    searchMemories: CortexUtils.debounce(async function(query) {
        // Implementation for memory search
        console.log('Searching memories:', query);
    }, 300),

    /**
     * Toggle virtual scrolling
     * @param {boolean} enabled - Whether to enable virtual scrolling
     */
    toggleVirtualScrolling(enabled) {
        this.performance.enableVirtualScrolling = enabled;
        CortexUtils.storage.set('cortex_virtual_scrolling', enabled);
        this.showToast(`Virtual scrolling ${enabled ? 'enabled' : 'disabled'}`, 'info');
    },

    /**
     * Toggle lazy loading
     * @param {boolean} enabled - Whether to enable lazy loading
     */
    toggleLazyLoading(enabled) {
        this.performance.enableLazyLoading = enabled;
        CortexUtils.storage.set('cortex_lazy_loading', enabled);
        this.showToast(`Lazy loading ${enabled ? 'enabled' : 'disabled'}`, 'info');
    },

    /**
     * Set debounce delay
     * @param {number} delay - Delay in milliseconds
     */
    setDebounceDelay(delay) {
        this.performance.debounceDelay = Math.max(100, parseInt(delay) || 300);
        CortexUtils.storage.set('cortex_debounce_delay', this.performance.debounceDelay);
        this.showToast(`Debounce delay set to ${this.performance.debounceDelay}ms`, 'info');
    },

    /**
     * Clean up resources and event listeners
     */
    cleanup() {
        // Clear intervals
        if (this.dashboardUpdateInterval) {
            clearInterval(this.dashboardUpdateInterval);
        }
        if (this.connectionCheckInterval) {
            clearInterval(this.connectionCheckInterval);
        }

        // Clean up event listeners
        CortexUtils.memory.cleanup(this);

        // Disconnect observers
        if (this.lazyLoadObserver) {
            this.lazyLoadObserver.disconnect();
        }

        // Clear caches
        CortexAPI.cache.clear();
        CortexAPI.performance.clear();

        console.log('UI cleanup completed');
    }
};

// Make UI available globally for debugging (browser environment)
if (typeof window !== 'undefined') {
    window.CortexUI = CortexUI;
    
    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            CortexUI.init();
        });
    } else {
        // DOM is already ready
        CortexUI.init();
    }
}

// Export for Node.js environment
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CortexUI;
}