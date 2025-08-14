# Cortex MCP Server Deployment Guide

This guide covers deployment strategies for different environments and use cases.

## Table of Contents

- [Deployment Overview](#deployment-overview)
- [Local Development](#local-development)
- [Production Deployment](#production-deployment)
- [Docker Deployment](#docker-deployment)
- [Cloud Deployment](#cloud-deployment)
- [High Availability Setup](#high-availability-setup)
- [Monitoring and Maintenance](#monitoring-and-maintenance)

## Deployment Overview

The Cortex MCP Server can be deployed in various configurations:

- **Single User Local**: Personal development machine
- **Multi-User Local**: Shared development server
- **Production**: High-availability production environment
- **Cloud**: Cloud-based deployment with scaling

## Local Development

### Quick Start

```bash
# Clone and start
git clone <repository-url>
cd cortex-mcp
docker-compose up -d
```

### Development Configuration

Create a `docker-compose.dev.yml` for development:

```yaml
version: '3.8'

services:
  cortex-mcp:
    build:
      context: .
      dockerfile: Dockerfile
      target: builder  # Use builder stage for development
    container_name: cortex-mcp-dev
    ports:
      - "8000:8000"
    volumes:
      # Mount source code for live reloading
      - ./src:/app/src
      - ./data:/app/data
      - ./models:/app/models
      - ./config.yml:/app/config.yml
    environment:
      - MEMORY_SERVER_HOST=0.0.0.0
      - MEMORY_SERVER_PORT=8000
      - LOG_LEVEL=DEBUG
      - RELOAD=true  # Enable auto-reload
    restart: "no"  # Don't restart automatically in dev
```

Start development environment:

```bash
docker-compose -f docker-compose.dev.yml up
```

## Production Deployment

### Production Configuration

Create a `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  cortex-mcp:
    image: cortex-mcp:latest
    container_name: cortex-mcp-prod
    ports:
      - "127.0.0.1:8000:8000"  # Bind to localhost only
    volumes:
      - memory-data:/app/data
      - memory-models:/app/models
      - ./config.prod.yml:/app/config.yml:ro
      - ./logs:/app/logs
    environment:
      - MEMORY_SERVER_HOST=127.0.0.1
      - MEMORY_SERVER_PORT=8000
      - LOG_LEVEL=INFO
      - ENABLE_ENCRYPTION=true
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'

  nginx:
    image: nginx:alpine
    container_name: memory-nginx-prod
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.prod.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./logs/nginx:/var/log/nginx
    depends_on:
      - cortex-mcp
    restart: unless-stopped

  # Log rotation service
  logrotate:
    image: linkyard/docker-logrotate
    container_name: memory-logrotate
    volumes:
      - ./logs:/logs
      - ./logrotate.conf:/etc/logrotate.conf:ro
    restart: unless-stopped

volumes:
  memory-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /opt/cross-tool-memory/data
  memory-models:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /opt/cross-tool-memory/models

networks:
  default:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### Production nginx Configuration

Create `nginx.prod.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream memory_backend {
        server cross-tool-memory:8000;
        keepalive 32;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=health:10m rate=1r/s;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    server {
        listen 80;
        server_name localhost;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name localhost;

        ssl_certificate /etc/nginx/ssl/server.crt;
        ssl_certificate_key /etc/nginx/ssl/server.key;

        # Health check endpoint (less restrictive)
        location /health {
            limit_req zone=health burst=5 nodelay;
            proxy_pass http://memory_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # API endpoints (rate limited)
        location / {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://memory_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeouts
            proxy_connect_timeout 5s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
            
            # Buffer settings
            proxy_buffering on;
            proxy_buffer_size 4k;
            proxy_buffers 8 4k;
        }
    }

    # Logging
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log warn;
}
```

### Production Deployment Steps

1. **Prepare the server**:
```bash
# Create production directory
sudo mkdir -p /opt/cross-tool-memory/{data,models,logs,ssl}
sudo chown -R $USER:$USER /opt/cross-tool-memory

# Copy configuration files
cp config.yml /opt/cross-tool-memory/config.prod.yml
cp nginx.prod.conf /opt/cross-tool-memory/
cp docker-compose.prod.yml /opt/cross-tool-memory/docker-compose.yml
```

2. **Generate SSL certificates**:
```bash
# For production, use Let's Encrypt or proper CA certificates
# For testing, generate self-signed:
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /opt/cross-tool-memory/ssl/server.key \
  -out /opt/cross-tool-memory/ssl/server.crt
```

3. **Deploy**:
```bash
cd /opt/cross-tool-memory
docker-compose up -d
```

4. **Set up systemd service**:
```bash
sudo tee /etc/systemd/system/cross-tool-memory.service > /dev/null <<EOF
[Unit]
Description=Cross-Tool Memory MCP Server
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/cross-tool-memory
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cross-tool-memory
sudo systemctl start cross-tool-memory
```

## Docker Deployment

### Multi-Stage Production Build

Optimize the Dockerfile for production:

```dockerfile
# Build stage
FROM python:3.11-slim as builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml /tmp/
RUN pip install --upgrade pip setuptools wheel && \
    pip install /tmp/

# Production stage
FROM python:3.11-slim as production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r memoryuser && useradd -r -g memoryuser memoryuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY src/ ./src/
COPY README.md ./

RUN mkdir -p /app/data /app/models /app/logs && \
    chown -R memoryuser:memoryuser /app

USER memoryuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "cortex_mcp.main"]
```

### Docker Swarm Deployment

For Docker Swarm clusters:

```yaml
version: '3.8'

services:
  cross-tool-memory:
    image: cross-tool-memory-mcp:latest
    ports:
      - "8000:8000"
    volumes:
      - memory-data:/app/data
      - memory-models:/app/models
    environment:
      - MEMORY_SERVER_HOST=0.0.0.0
      - MEMORY_SERVER_PORT=8000
    deploy:
      replicas: 2
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'
      placement:
        constraints:
          - node.role == worker
    networks:
      - memory-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.swarm.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
    networks:
      - memory-network

volumes:
  memory-data:
    driver: local
  memory-models:
    driver: local

networks:
  memory-network:
    driver: overlay
    attachable: true
```

Deploy to swarm:

```bash
docker stack deploy -c docker-compose.swarm.yml memory-stack
```

## Cloud Deployment

### AWS Deployment

#### Using ECS Fargate

1. **Create task definition**:
```json
{
  "family": "cross-tool-memory",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "memory-server",
      "image": "your-account.dkr.ecr.region.amazonaws.com/cross-tool-memory:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "MEMORY_SERVER_HOST",
          "value": "0.0.0.0"
        },
        {
          "name": "DATABASE_PATH",
          "value": "/app/data/memory.db"
        }
      ],
      "mountPoints": [
        {
          "sourceVolume": "memory-data",
          "containerPath": "/app/data"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/cross-tool-memory",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ],
  "volumes": [
    {
      "name": "memory-data",
      "efsVolumeConfiguration": {
        "fileSystemId": "fs-12345678",
        "transitEncryption": "ENABLED"
      }
    }
  ]
}
```

2. **Create ECS service**:
```bash
aws ecs create-service \
  --cluster memory-cluster \
  --service-name cross-tool-memory \
  --task-definition cross-tool-memory:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345,subnet-67890],securityGroups=[sg-12345],assignPublicIp=ENABLED}"
```

#### Using EC2 with Auto Scaling

Create a launch template:

```bash
#!/bin/bash
yum update -y
yum install -y docker
systemctl start docker
systemctl enable docker

# Install docker-compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Deploy application
mkdir -p /opt/cross-tool-memory
cd /opt/cross-tool-memory

# Download configuration from S3
aws s3 cp s3://your-bucket/cross-tool-memory/docker-compose.yml .
aws s3 cp s3://your-bucket/cross-tool-memory/config.yml .

# Start services
docker-compose up -d
```

### Google Cloud Platform

#### Using Cloud Run

1. **Build and push image**:
```bash
# Build for Cloud Run
docker build -t gcr.io/your-project/cross-tool-memory .
docker push gcr.io/your-project/cross-tool-memory
```

2. **Deploy to Cloud Run**:
```bash
gcloud run deploy cross-tool-memory \
  --image gcr.io/your-project/cross-tool-memory \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --port 8000 \
  --set-env-vars MEMORY_SERVER_HOST=0.0.0.0,MEMORY_SERVER_PORT=8000
```

#### Using GKE

Create Kubernetes manifests:

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cross-tool-memory
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cross-tool-memory
  template:
    metadata:
      labels:
        app: cross-tool-memory
    spec:
      containers:
      - name: memory-server
        image: gcr.io/your-project/cross-tool-memory:latest
        ports:
        - containerPort: 8000
        env:
        - name: MEMORY_SERVER_HOST
          value: "0.0.0.0"
        - name: DATABASE_PATH
          value: "/app/data/memory.db"
        volumeMounts:
        - name: memory-data
          mountPath: /app/data
        - name: memory-models
          mountPath: /app/models
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: memory-data
        persistentVolumeClaim:
          claimName: memory-data-pvc
      - name: memory-models
        persistentVolumeClaim:
          claimName: memory-models-pvc

---
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: cross-tool-memory-service
spec:
  selector:
    app: cross-tool-memory
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer

---
# pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: memory-data-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: memory-models-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
```

Deploy:

```bash
kubectl apply -f deployment.yaml
```

## High Availability Setup

### Database Replication

For high availability, consider using database replication:

```yaml
# docker-compose.ha.yml
version: '3.8'

services:
  memory-primary:
    image: cross-tool-memory-mcp:latest
    environment:
      - DATABASE_ROLE=primary
      - DATABASE_PATH=/app/data/memory.db
    volumes:
      - primary-data:/app/data
    ports:
      - "8000:8000"

  memory-replica:
    image: cross-tool-memory-mcp:latest
    environment:
      - DATABASE_ROLE=replica
      - PRIMARY_HOST=memory-primary
      - DATABASE_PATH=/app/data/memory.db
    volumes:
      - replica-data:/app/data
    ports:
      - "8001:8000"
    depends_on:
      - memory-primary

  haproxy:
    image: haproxy:alpine
    ports:
      - "80:80"
    volumes:
      - ./haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
    depends_on:
      - memory-primary
      - memory-replica

volumes:
  primary-data:
  replica-data:
```

### Load Balancer Configuration

HAProxy configuration (`haproxy.cfg`):

```
global
    daemon

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms

frontend memory_frontend
    bind *:80
    default_backend memory_backend

backend memory_backend
    balance roundrobin
    option httpchk GET /health
    server primary memory-primary:8000 check
    server replica memory-replica:8000 check backup
```

## Monitoring and Maintenance

### Prometheus Monitoring

Add monitoring to your deployment:

```yaml
# monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana

  node-exporter:
    image: prom/node-exporter
    ports:
      - "9100:9100"

volumes:
  prometheus-data:
  grafana-data:
```

### Backup Strategy

Implement automated backups:

```bash
#!/bin/bash
# backup-cron.sh

BACKUP_DIR="/opt/backups/cross-tool-memory"
RETENTION_DAYS=30

# Create backup
python3 /opt/cross-tool-memory/scripts/backup_restore.py backup \
  --name "scheduled_$(date +%Y%m%d_%H%M%S)"

# Upload to cloud storage (optional)
aws s3 sync $BACKUP_DIR s3://your-backup-bucket/cross-tool-memory/

# Clean up old backups
find $BACKUP_DIR -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
```

Add to crontab:

```bash
# Daily backup at 2 AM
0 2 * * * /opt/scripts/backup-cron.sh
```

### Log Management

Set up log rotation:

```bash
# /etc/logrotate.d/cross-tool-memory
/opt/cross-tool-memory/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
    postrotate
        docker-compose -f /opt/cross-tool-memory/docker-compose.yml restart cross-tool-memory
    endscript
}
```

### Health Monitoring

Create a monitoring script:

```bash
#!/bin/bash
# health-check.sh

HEALTH_URL="http://localhost:8000/health"
ALERT_EMAIL="admin@example.com"

if ! curl -f -s $HEALTH_URL > /dev/null; then
    echo "Cross-Tool Memory server is down!" | mail -s "Server Alert" $ALERT_EMAIL
    
    # Attempt restart
    cd /opt/cross-tool-memory
    docker-compose restart cross-tool-memory
fi
```

Run every 5 minutes:

```bash
*/5 * * * * /opt/scripts/health-check.sh
```

This deployment guide provides comprehensive coverage for various deployment scenarios, from local development to production cloud deployments with high availability and monitoring.