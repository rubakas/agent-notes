---
name: docker-compose
description: "Docker Compose: file structure, health checks, depends_on, and common service patterns. Use when user is writing or editing a docker-compose.yml."
group: docker
---

# Docker Compose Patterns

Production-ready Docker Compose configurations for multi-container applications based on official Docker Compose Specification and current best practices.

> **Sources**: This guide is based on [Docker Compose Specification](https://docs.docker.com/reference/compose-file/), [Docker Compose Services Reference](https://docs.docker.com/reference/compose-file/services/), and Docker Compose v2 (2022+) best practices.

---

## Important: Version Field is Obsolete

**The `version:` field is obsolete** as of Docker Compose v2 (2022). Docker Compose now ignores this field entirely. Modern compose files should **NOT include** a `version:` field.

**Why**: Docker Compose v1.27.0+ (2020) introduced the Compose Specification, making the version field optional. The Compose Specification is now the recommended version.

**Source**: [Docker Compose Specification](https://docs.docker.com/reference/compose-file/)

---

## Compose File Structure Template

```yaml
services:
  # Application service
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
      args:
        NODE_ENV: production
    image: myapp:latest
    container_name: myapp
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://postgres:password@db:5432/myapp
      - REDIS_URL=redis://redis:6379
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./uploads:/app/uploads
      - app_logs:/app/logs
    networks:
      - app_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # Database service
  db:
    image: postgres:16-alpine
    container_name: myapp_db
    restart: unless-stopped
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=myapp
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    networks:
      - app_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis service
  redis:
    image: redis:7-alpine
    container_name: myapp_redis
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - app_network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  app_logs:
    driver: local

networks:
  app_network:
    driver: bridge
```

---

## Health Checks in Compose

Health checks work the same way as Dockerfile HEALTHCHECK and use the same default values. Your Compose file can override values set in the Dockerfile.

```yaml
services:
  web:
    image: myapp:latest
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

**Health check attributes**:
- `test`: Command to run (can be string or array)
- `interval`: Time between checks (default: 30s)
- `timeout`: Maximum time for check to complete (default: 30s)
- `retries`: Consecutive failures before marking unhealthy (default: 3)
- `start_period`: Grace period for container initialization (default: 0s)

**Source**: [Docker Compose Health Checks](https://docs.docker.com/reference/compose-file/services/#healthcheck)

---

## Depends_on with Conditions

Use `condition` to wait for services to be healthy before starting dependent services.

```yaml
services:
  app:
    depends_on:
      db:
        condition: service_healthy  # Wait for health check to pass
      redis:
        condition: service_started  # Just wait for container to start
```

**Available conditions**:
- `service_started`: Default, just waits for container to start
- `service_healthy`: Waits for health check to pass
- `service_completed_successfully`: Waits for one-time task to complete

**Source**: [Docker Compose depends_on](https://docs.docker.com/reference/compose-file/services/#depends_on)

---

## Common Service Patterns

### Node.js Application

```yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: ${BUILD_TARGET:-production}
    image: ${APP_NAME}:${VERSION:-latest}
    restart: unless-stopped
    ports:
      - "${APP_PORT:-3000}:3000"
    environment:
      NODE_ENV: ${NODE_ENV:-production}
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: redis://redis:6379
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
    volumes:
      # Development: mount source code
      - ./src:/app/src:ro
      # Production: named volumes for data
      - uploads:/app/uploads
      - logs:/app/logs
    networks:
      - app_network
    healthcheck:
      test: ["CMD", "node", "healthcheck.js"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### Rails with Background Workers

```yaml
services:
  web:
    build:
      context: .
      dockerfile: Dockerfile
    command: bundle exec rails server -b 0.0.0.0
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      RAILS_ENV: ${RAILS_ENV:-production}
      DATABASE_URL: postgresql://postgres:password@db:5432/myapp
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY_BASE: ${SECRET_KEY_BASE}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - ./storage:/app/storage
      - ./log:/app/log
    networks:
      - app_network

  sidekiq:
    build:
      context: .
      dockerfile: Dockerfile
    command: bundle exec sidekiq
    restart: unless-stopped
    environment:
      RAILS_ENV: ${RAILS_ENV:-production}
      DATABASE_URL: postgresql://postgres:password@db:5432/myapp
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ./storage:/app/storage
      - ./log:/app/log
    networks:
      - app_network
```

### Python/Django with Celery

```yaml
services:
  web:
    build:
      context: .
      dockerfile: Dockerfile
    command: gunicorn myapp.wsgi:application --bind 0.0.0.0:8000 --workers 4
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      DJANGO_SETTINGS_MODULE: myapp.settings.production
      DATABASE_URL: postgresql://postgres:password@db:5432/myapp
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./media:/app/media
      - ./static:/app/static
    networks:
      - app_network

  celery_worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A myapp worker -l info
    restart: unless-stopped
    environment:
      DJANGO_SETTINGS_MODULE: myapp.settings.production
      DATABASE_URL: postgresql://postgres:password@db:5432/myapp
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - db
      - redis
    networks:
      - app_network

  celery_beat:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A myapp beat -l info
    restart: unless-stopped
    environment:
      DJANGO_SETTINGS_MODULE: myapp.settings.production
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - redis
    networks:
      - app_network
```

---
