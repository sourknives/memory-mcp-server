.PHONY: help install install-dev test lint format clean build run docker-build docker-run docker-stop

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install the package
	pip install -e .

install-dev: ## Install development dependencies
	pip install -e ".[dev,test]"

test: ## Run tests
	pytest

test-cov: ## Run tests with coverage
	pytest --cov=cortex_mcp --cov-report=html --cov-report=term

lint: ## Run linting
	flake8 src/ tests/
	mypy src/

format: ## Format code
	black src/ tests/
	isort src/ tests/

format-check: ## Check code formatting
	black --check src/ tests/
	isort --check-only src/ tests/

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

build: ## Build the package
	python -m build

run: ## Run the server locally
	python -m cortex_mcp.main

docker-build: ## Build Docker image
	docker-compose build

docker-run: ## Run with Docker Compose
	docker-compose up -d

docker-stop: ## Stop Docker containers
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

setup-dev: install-dev ## Set up development environment
	pre-commit install
	mkdir -p data logs models
# De
ployment and Packaging Commands

install-system: ## Install system-wide using installation script
	sudo ./scripts/install.sh

uninstall: ## Uninstall the system
	./scripts/uninstall.sh

deploy-dev: ## Deploy development environment
	docker-compose -f docker-compose.dev.yml up -d

deploy-prod: ## Deploy production environment
	docker-compose -f docker-compose.prod.yml up -d

package: ## Create deployment package
	@echo "Creating deployment package..."
	mkdir -p dist/cross-tool-memory-mcp
	cp -r src/ dist/cross-tool-memory-mcp/
	cp docker-compose.yml dist/cross-tool-memory-mcp/
	cp Dockerfile dist/cross-tool-memory-mcp/
	cp config.yml dist/cross-tool-memory-mcp/
	cp .env.example dist/cross-tool-memory-mcp/
	cp nginx.conf dist/cross-tool-memory-mcp/
	cp pyproject.toml dist/cross-tool-memory-mcp/
	cp README.md dist/cross-tool-memory-mcp/
	cp INSTALL.md dist/cross-tool-memory-mcp/
	cp DEPLOYMENT.md dist/cross-tool-memory-mcp/
	cp -r scripts/ dist/cross-tool-memory-mcp/
	cd dist && tar -czf cross-tool-memory-mcp-$(shell date +%Y%m%d).tar.gz cross-tool-memory-mcp/
	@echo "Package created: dist/cross-tool-memory-mcp-$(shell date +%Y%m%d).tar.gz"

backup: ## Create backup using backup script
	python scripts/backup_restore.py backup

backup-full: ## Create full backup including models and logs
	python scripts/backup_restore.py backup --include-logs

restore: ## Restore from backup (requires BACKUP_FILE variable)
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "Usage: make restore BACKUP_FILE=path/to/backup.tar.gz"; \
		exit 1; \
	fi
	python scripts/backup_restore.py restore $(BACKUP_FILE)

list-backups: ## List available backups
	python scripts/backup_restore.py list

cleanup-backups: ## Clean up old backups (keep last 10)
	python scripts/backup_restore.py cleanup --keep 10

health-check: ## Check server health
	@curl -f http://localhost:8000/health || echo "Server is not responding"

docker-build-prod: ## Build optimized production Docker image
	docker build --target production -t cross-tool-memory-mcp:latest .

docker-build-dev: ## Build development Docker image
	docker build --target builder -t cross-tool-memory-mcp:dev .

docker-push: ## Push Docker image to registry (requires REGISTRY variable)
	@if [ -z "$(REGISTRY)" ]; then \
		echo "Usage: make docker-push REGISTRY=your-registry.com/cross-tool-memory"; \
		exit 1; \
	fi
	docker tag cross-tool-memory-mcp:latest $(REGISTRY):latest
	docker push $(REGISTRY):latest

docker-clean: ## Clean up Docker resources
	docker-compose down -v
	docker rmi -f cross-tool-memory-mcp || true
	docker system prune -f

ssl-cert: ## Generate self-signed SSL certificate
	mkdir -p ssl
	openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
		-keyout ssl/server.key \
		-out ssl/server.crt \
		-subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

setup-prod: ssl-cert ## Set up production environment
	mkdir -p data models logs backups
	cp .env.example .env
	@echo "Production setup complete. Edit .env file and run 'make deploy-prod'"