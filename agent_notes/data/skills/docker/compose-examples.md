# Examples and Best Practices

## Contents

- [Development vs Production](#development-vs-production)
- [Full Stack Application Example](#full-stack-application-example)
- [Best Practices Summary](#best-practices-summary)
- [Common Commands](#common-commands)
- [References and Sources](#references-and-sources)

---

## Development vs Production

### Development Configuration

```yaml
# compose.dev.yml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: development
    volumes:
      # Mount source code for hot reload
      - ./src:/app/src
      - ./public:/app/public
      # Don't mount node_modules (use container's version)
      - /app/node_modules
    ports:
      # Expose debugger port
      - "9229:9229"
    environment:
      - NODE_ENV=development
      - DEBUG=app:*
    command: npm run dev

  db:
    ports:
      # Expose database port for local access in development
      - "5432:5432"

# Usage: docker compose -f compose.yml -f compose.dev.yml up
```

### Production Configuration

```yaml
# compose.prod.yml
services:
  app:
    build:
      target: production
    restart: always
    # Don't expose ports directly in production - use reverse proxy
    expose:
      - "3000"
    environment:
      - NODE_ENV=production
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

  db:
    # Don't expose database port in production
    expose:
      - "5432"
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G

# Usage: docker compose -f compose.yml -f compose.prod.yml up -d
```

---

## Full Stack Application Example

```yaml
services:
  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: production
    image: myapp-frontend:latest
    restart: unless-stopped
    depends_on:
      - backend
    networks:
      - app_network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`myapp.com`)"

  # Backend API
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    image: myapp-backend:latest
    restart: unless-stopped
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@db:5432/myapp
      - REDIS_URL=redis://redis:6379
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - uploads:/app/uploads
    networks:
      - app_network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.backend.rule=Host(`api.myapp.com`)"

  # Background Worker
  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: npm run worker
    restart: unless-stopped
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@db:5432/myapp
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    networks:
      - app_network

  # Database
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=myapp
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - app_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Cache
  redis:
    image: redis:7-alpine
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

  # Reverse Proxy
  traefik:
    image: traefik:v2.10
    restart: unless-stopped
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - app_network

volumes:
  postgres_data:
  redis_data:
  uploads:

networks:
  app_network:
    driver: bridge
```

---

## Best Practices Summary

### DO

1. **Remove version field** - It's obsolete in Compose v2
2. **Use health checks** - Essential for orchestration
3. **Use named volumes** - Data persistence
4. **Set resource limits** - Prevent resource exhaustion
5. **Use restart policies** - Automatic recovery
6. **Isolate with networks** - Security
7. **Pin image versions** - Use specific tags, not :latest
8. **Use .env files** - Centralized configuration
9. **Separate dev/prod configs** - Different requirements
10. **Use depends_on conditions** - Proper startup order

### DON'T

1. **Include version field** - Generates warnings in Compose v2
2. **Use :latest in production** - Unpredictable
3. **Expose database ports** - Security risk in production
4. **Hardcode secrets** - Use environment variables
5. **Use privileged mode** - Security risk
6. **Mount sensitive host directories** - Security risk
7. **Forget resource limits** - Can exhaust host
8. **Use bridge network for everything** - Proper isolation matters

---

## Common Commands

```bash
# Start services
docker compose up -d

# Start with specific file
docker compose -f compose.yml -f compose.prod.yml up -d

# View logs
docker compose logs -f app

# Restart service
docker compose restart app

# Stop services
docker compose down

# Stop and remove volumes (CAUTION: deletes data)
docker compose down -v

# Build and start
docker compose up --build

# Scale service
docker compose up -d --scale worker=3

# Execute command in running container
docker compose exec app sh

# Run one-off command
docker compose run --rm app npm test

# View service status
docker compose ps

# View resource usage
docker compose stats
```

---

## References and Sources

This guide is based on official Docker Compose documentation:

- [Docker Compose Specification](https://docs.docker.com/reference/compose-file/)
- [Docker Compose Services Reference](https://docs.docker.com/reference/compose-file/services/)
- [Docker Compose Health Checks](https://docs.docker.com/reference/compose-file/services/#healthcheck)
- [Docker Compose depends_on](https://docs.docker.com/reference/compose-file/services/#depends_on)
- [Docker Compose Legacy Versions](https://docs.docker.com/reference/compose-file/legacy-versions/)

Last updated: December 2025
