# Docker - Modular Reference

Production-ready Docker and Docker Compose patterns based on official Docker documentation. Each file can be independently included or excluded in CLAUDE.md.

---

## Available Modules

### Core Patterns
- **dockerfile.md** - Dockerfile patterns, multi-stage builds, security, health checks, layer optimization
- **compose.md** - Docker Compose configuration, service orchestration, health checks, dependencies

---

## Usage

### Include All Modules (Recommended)

Single line includes everything:

```markdown
## Docker Best Practices

@agent-notes/docker/index.md
```

This loads all 2 Docker pattern modules automatically.

### Include Specific Modules Only

For granular control, include individual files:

```markdown
## Docker Patterns

@agent-notes/docker/dockerfile.md
@agent-notes/docker/compose.md
```

### Disable Specific Modules

Comment out any you don't need:

```markdown
@agent-notes/docker/index.md  <!-- Includes all modules -->

<!-- OR selective loading: -->

@agent-notes/docker/dockerfile.md
<!-- @agent-notes/docker/compose.md -->  <!-- Disabled -->
```

---

## File Organization

```
docker/
├── README.md              # This file
├── index.md              # ⭐ Entry point (includes all modules)
├── dockerfile.md         # ✅ Complete
└── compose.md            # ✅ Complete
```

---

## Pattern Overview

Each file follows this structure:

1. **Overview** - Core principles and sources
2. **Structure Templates** - Copy-paste ready templates
3. **Patterns** - Real-world examples by language/use case
4. **Security** - Best practices and recommendations
5. **Best Practices** - Do's and don'ts
6. **Commands** - Common operations
7. **Sources** - Official Docker documentation links

---

## Quick Reference

### When to Use What?

```
Single Container App       → dockerfile.md (multi-stage build)
Multi-Container App        → compose.md (orchestration)
Development Environment    → compose.md (dev overrides)
Production Deployment      → compose.md + dockerfile.md (both)
Background Workers         → compose.md (separate services)
Database + Cache           → compose.md (service definitions)
Security Hardening         → dockerfile.md (non-root, scanning)
```

### Common Patterns

**Single Service Deployment:**
1. Dockerfile with multi-stage build (`dockerfile.md`)
2. Health check (`dockerfile.md`)
3. Non-root user UID > 10,000 (`dockerfile.md`)
4. Scan for vulnerabilities (`dockerfile.md`)

**Multi-Service Application:**
1. Dockerfiles for each service (`dockerfile.md`)
2. Compose file for orchestration (`compose.md`)
3. Health checks and dependencies (`compose.md`)
4. Development overrides (`compose.md`)

**Full Stack App (Frontend + Backend + DB):**
1. Frontend Dockerfile (`dockerfile.md`)
2. Backend Dockerfile (`dockerfile.md`)
3. Docker Compose orchestration (`compose.md`)
4. Database service with health check (`compose.md`)
5. Redis/cache service (`compose.md`)
6. Reverse proxy (Nginx/Traefik) (`compose.md`)

---

## Key Principles

### Security First
- **Run as non-root**: Use UID > 10,000 to avoid privilege escalation
- **Multi-stage builds**: Reduce attack surface by excluding build tools
- **Scan regularly**: Use Docker Scout or Trivy for vulnerability scanning
- **Pin versions**: Never use `:latest` in production
- **No secrets in images**: Use environment variables or secret management

### Optimization
- **Layer caching**: Order instructions by change frequency
- **Multi-stage builds**: Smaller final images, faster deployments
- **.dockerignore**: Essential for security and build performance
- **Combine RUN commands**: Fewer layers, smaller images

### Production Readiness
- **Health checks**: Not optional—required for orchestration
- **Resource limits**: Prevent resource exhaustion
- **Proper restart policies**: Automatic recovery
- **Network isolation**: Use custom networks
- **Version field obsolete**: Don't use `version:` in compose.yml (Compose v2)

---

## Important Notes

### Version Field is Obsolete

**Do not use** `version:` in compose.yml files. It's been obsolete since Docker Compose v2 (2022).

```yaml
# ❌ DON'T
version: '3.8'
services:
  app:
    ...

# ✅ DO
services:
  app:
    ...
```

**Source:** Docker Compose v2 ignores the version field entirely.

### UID Security

Always use **UID > 10,000** for non-root users. UIDs below 10,000 can overlap with privileged system users if container escape occurs.

```dockerfile
# ✅ SECURE
RUN addgroup -g 10001 -S appuser && \
    adduser -S appuser -u 10001

# ❌ LESS SECURE
RUN adduser -u 1001 appuser
```

**Source:** [Docker USER Instruction Best Practices](https://www.docker.com/blog/understanding-the-docker-user-instruction/)

### Health Checks are Required

According to Docker best practices, HEALTHCHECK is **production-necessary**, not optional. Without health checks, orchestration cannot detect failures.

**Source:** [Docker HEALTHCHECK Reference](https://docs.docker.com/reference/dockerfile/#healthcheck)

---

## Language-Specific Quick Start

### Node.js

```dockerfile
FROM node:20.11.0-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20.11.0-alpine
RUN addgroup -g 10001 -S nodejs && adduser -S nodejs -u 10001
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
USER nodejs
HEALTHCHECK CMD node healthcheck.js || exit 1
CMD ["node", "dist/server.js"]
```

### Python

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install -r requirements.txt

FROM python:3.12-slim
RUN useradd -m -u 10001 python
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=python:python . .
USER python
ENV PATH="/opt/venv/bin:$PATH"
CMD ["python", "app.py"]
```

### Ruby/Rails

```dockerfile
FROM ruby:3.3-alpine AS builder
RUN apk add --no-cache build-base postgresql-dev
WORKDIR /app
COPY Gemfile* ./
RUN bundle install

FROM ruby:3.3-alpine
RUN apk add --no-cache postgresql-client && \
    addgroup -g 10001 -S rails && \
    adduser -S rails -u 10001
WORKDIR /app
COPY --from=builder /usr/local/bundle /usr/local/bundle
COPY --chown=rails:rails . .
USER rails
CMD ["bundle", "exec", "rails", "server", "-b", "0.0.0.0"]
```

---

## Testing Your Docker Setup

```bash
# Build image
docker build -t myapp:latest .

# Scan for vulnerabilities
docker scout cves myapp:latest

# Test with compose
docker compose up -d

# View logs
docker compose logs -f

# Check health status
docker compose ps

# Inspect layers
docker history myapp:latest

# Test as non-root
docker run --user 10001:10001 myapp:latest
```

---

## Official Sources

All patterns in this module are based on official Docker documentation:

- [Docker Best Practices](https://docs.docker.com/build/building/best-practices/)
- [Docker Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker Compose Specification](https://docs.docker.com/reference/compose-file/)
- [Docker Security Documentation](https://docs.docker.com/engine/security/)
- [Dockerfile Reference](https://docs.docker.com/reference/dockerfile/)
- [Docker USER Instruction](https://www.docker.com/blog/understanding-the-docker-user-instruction/)

---

## Contributing

When adding Docker patterns from other projects:

1. **Verify with official docs** - Only use patterns from official Docker documentation
2. **Keep it generic** - Remove app-specific references
3. **Include sources** - Cite official Docker docs for all recommendations
4. **Show examples** - Include code samples with explanations
5. **Test patterns** - Ensure patterns work in production environments
6. **Security first** - Prioritize security over convenience
7. **Follow structure** - Match existing file format

---

## Summary

These are modular, comprehensive references for Docker development patterns based on official documentation. Include what you need, exclude what you don't. Each file is self-contained and can be used independently.

All patterns are sourced from official Docker documentation and verified for production use.
