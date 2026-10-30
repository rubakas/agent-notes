# Basic Configuration

## Contents

- [Version Field](#important-version-field-is-obsolete)
- [Compose File Structure](#compose-file-structure-template)
- [Health Checks](#health-checks-in-compose)
- [Depends On](#depends_on-with-conditions)
- [Environment Variables](#environment-variables)

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

## Environment Variables

### .env File

```bash
# .env
NODE_ENV=production
APP_PORT=3000

# Database
DB_USER=postgres
DB_PASSWORD=secure_password_here
DB_NAME=myapp
DB_PORT=5432

# Redis
REDIS_PASSWORD=redis_password_here

# Application
JWT_SECRET=your_jwt_secret_here
API_KEY=your_api_key_here

# Version
VERSION=1.0.0
```

### Using Environment Variables

```yaml
services:
  app:
    image: ${APP_NAME:-myapp}:${VERSION:-latest}
    ports:
      - "${APP_PORT:-3000}:3000"
    environment:
      # Use variables from .env
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:${DB_PORT}/${DB_NAME}
      - API_KEY=${API_KEY}
    env_file:
      # Load all variables from .env
      - .env
```
