# Dockerfile Patterns

Best practices and patterns for writing production-ready Dockerfiles based on official Docker documentation and industry standards.

> **Sources**: This guide is based on [Docker Official Documentation](https://docs.docker.com/build/building/best-practices/), [Docker Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/), and current security best practices as of 2025.

---

## Dockerfile Structure Template

```dockerfile
# syntax=docker/dockerfile:1

# Build stage
FROM node:20.11.0-alpine AS builder

# Metadata
LABEL maintainer="team@example.com"
LABEL version="1.0"

# Set working directory
WORKDIR /app

# Install dependencies first (better caching)
COPY package*.json ./
RUN npm ci

# Copy application code
COPY . .

# Build application
RUN npm run build

# Production stage
FROM node:20.11.0-alpine AS production

# Install security updates
RUN apk update && apk upgrade && rm -rf /var/cache/apk/*

# Create non-root user (UID > 10000 for security)
RUN addgroup -g 10001 -S nodejs && \
    adduser -S nodejs -u 10001

WORKDIR /app

# Copy built assets from builder
COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules
COPY --chown=nodejs:nodejs package*.json ./

# Switch to non-root user
USER nodejs

# Expose port
EXPOSE 3000

# Health check (production-necessary, not optional)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD node healthcheck.js || exit 1

# Start application
CMD ["node", "dist/server.js"]
```

---

## Base Image Selection

### Choose from Trusted Sources

Docker recommends using images from:
- **Docker Official Images**: Curated collection with clear documentation
- **Verified Publisher images**: Authenticated by Docker
- **Docker-Sponsored Open Source**: Maintained projects

**Source**: [Docker Best Practices - Base Images](https://docs.docker.com/build/building/best-practices/)

### Alpine Linux (Minimal)

Alpine is recommended as a minimal starting point, currently **under 6 MB** while providing a full Linux distribution.

```dockerfile
# Smallest size, minimal attack surface
FROM node:20.11.0-alpine
FROM python:3.12-alpine
FROM ruby:3.3-alpine

# Install common dependencies on Alpine
RUN apk add --no-cache \
    bash \
    curl \
    git \
    postgresql-dev
```

### Pin to Specific Digests for Supply Chain Security

```dockerfile
# Pin to specific digest for guaranteed immutability
FROM node:20.11.0-alpine@sha256:c0a3badbd8a0a760de903e00cedbca94588e609299820557e72cba2a53dbaa2c

# Note: Requires active maintenance for security updates
# Use Docker Scout for automated remediation workflows
```

**Source**: [Docker Best Practices - Supply Chain Security](https://docs.docker.com/build/building/best-practices/)

### Debian Slim (Balanced)

```dockerfile
# Good balance of size and compatibility
FROM node:20-slim
FROM python:3.12-slim
FROM ruby:3.3-slim

# CRITICAL: Always combine apt-get update with install
# Prevents cache issues that could install outdated packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl \
      git \
      postgresql-client && \
    rm -rf /var/lib/apt/lists/*
```

### Distroless (Maximum Security)

```dockerfile
# Google's distroless images - no shell, minimal attack surface
FROM gcr.io/distroless/nodejs20-debian12
FROM gcr.io/distroless/python3-debian12
FROM gcr.io/distroless/java17-debian12

# Note: No shell available, debugging is harder
# Best for production security
```

---

## Multi-Stage Builds (Security Critical)

Multi-stage builds are **foundational for production security**. They allow you to "selectively copy artifacts from one stage to another, leaving behind everything you don't want in the final image."

### Security Benefits

1. **Reduced Attack Surface**: Excludes build tools, compilers, and development dependencies
2. **Smaller Image Size**: Final image contains only runtime necessities
3. **No Build Tools in Production**: Eliminates unnecessary security risks

**Source**: [Docker Multi-stage Builds Official Documentation](https://docs.docker.com/build/building/multi-stage/)

### Basic Multi-Stage Pattern

```dockerfile
# Build stage
FROM golang:1.24 AS build

WORKDIR /app
COPY . .
RUN go build -o /bin/hello ./main.go

# Production stage - minimal runtime
FROM scratch
COPY --from=build /bin/hello /bin/hello
CMD ["/bin/hello"]
```

### Copy from External Images

```dockerfile
# Copy from any image, not just previous stages
COPY --from=nginx:latest /etc/nginx/nginx.conf /nginx.conf
```

### Named Stages for Maintainability

```dockerfile
FROM node:20-alpine AS dependencies
RUN npm ci --only=production

FROM node:20-alpine AS builder
COPY --from=dependencies /app/node_modules ./node_modules
RUN npm run build

FROM node:20-alpine AS production
COPY --from=builder /app/dist ./dist
```

Use `AS <NAME>` to reference stages by name rather than numeric index—improves maintainability when reordering instructions.

---

## Layer Optimization

### Order by Change Frequency (Critical for Caching)

```dockerfile
# ❌ BAD - Changes frequently, invalidates cache
COPY . .
RUN npm install

# ✅ GOOD - Dependencies change less often
COPY package*.json ./
RUN npm ci
COPY . .
```

Understanding cache invalidation is critical for efficient builds.

### Combine RUN Commands

```dockerfile
# ❌ BAD - Creates multiple layers
RUN apt-get update
RUN apt-get install -y curl
RUN apt-get install -y git
RUN rm -rf /var/lib/apt/lists/*

# ✅ GOOD - Single layer, smaller image
# CRITICAL: Combine apt-get update with install in same RUN
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl \
      git && \
    rm -rf /var/lib/apt/lists/*
```

Sort arguments alphanumerically for maintainability.

### Use Pipefail for Error Detection

```dockerfile
# IMPORTANT: Prepend set -o pipefail to catch errors at any stage
RUN set -o pipefail && \
    curl -sL https://example.com/install.sh | bash
```

Without pipefail, errors in piped commands may be silently ignored.

**Source**: [Docker Best Practices - RUN Instructions](https://docs.docker.com/build/building/best-practices/)

### Use .dockerignore (Essential)

Including unnecessary files like `.git`, `node_modules`, and `.env` increases image size and exposes secrets. The `.dockerignore` file excludes files and directories from the build context.

```dockerignore
# .dockerignore
node_modules
npm-debug.log
.git
.env
.env.local
.env.*.local
*.md
.DS_Store
coverage
.next
dist
build
*.log
.vscode
.idea
Dockerfile
docker-compose*.yml
```

**Source**: [Docker Best Practices - Build Context](https://docs.docker.com/build/building/best-practices/)

---

## Security Best Practices

### Run as Non-Root User (Critical)

By default, Docker containers run as UID 0 (root). If the container is compromised, the attacker will have host-level root access to all resources allocated to the container.

**UIDs below 10,000 are a security risk** on several systems. If someone manages to escalate privileges outside the Docker container, their Docker container UID may overlap with a more privileged system user's UID, granting them additional permissions.

**Best Practice**: Always run processes as a **UID above 10,000**.

```dockerfile
# Alpine - Use UID > 10000 for security
RUN addgroup -g 10001 -S appuser && \
    adduser -S appuser -u 10001

# Debian/Ubuntu - Use UID > 10000
RUN useradd -m -u 10001 appuser

# Switch to non-root user
USER appuser

# Set proper ownership when copying
COPY --chown=appuser:appuser . .
```

**Source**: [Docker USER Instruction Best Practices](https://www.docker.com/blog/understanding-the-docker-user-instruction/)

### Scan for Vulnerabilities

```dockerfile
# Use specific versions, never :latest
FROM node:20.11.0-alpine

# Keep base image updated
RUN apk update && apk upgrade && rm -rf /var/cache/apk/*
```

Scan images regularly:
```bash
docker scout cves my-image:latest
# or
trivy image my-image:latest
```

### Secrets Management

```dockerfile
# ❌ BAD - Never hardcode secrets
ENV API_KEY=secret123

# ✅ GOOD - Use build args with cleanup
ARG NPM_TOKEN
RUN echo "//registry.npmjs.org/:_authToken=${NPM_TOKEN}" > .npmrc && \
    npm install && \
    rm -f .npmrc

# ✅ BETTER - Pass at runtime
# docker run -e API_KEY=$API_KEY my-image
```

---

## Health Checks (Production-Necessary)

According to Docker best practices, "adding a HEALTHCHECK to your Dockerfile is not a nice-to-have—**it's a production necessity**." Without health checks, Docker cannot detect if a containerized service is unhealthy, preventing automatic restarts or recovery.

### HEALTHCHECK Syntax

```dockerfile
HEALTHCHECK [OPTIONS] CMD command
```

**Options**:
- `--interval=DURATION` (default: 30s)
- `--timeout=DURATION` (default: 30s)
- `--start-period=DURATION` (default: 0s) - Grace period for slow-starting apps
- `--start-interval=DURATION` (default: 5s)
- `--retries=N` (default: 3)

**Exit Codes**:
- `0`: success - container is healthy
- `1`: unhealthy - container isn't working correctly

### Examples

```dockerfile
# Web server check
HEALTHCHECK --interval=5m --timeout=3s \
  CMD curl -f http://localhost/ || exit 1

# Database check
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD pg_isready -U postgres || exit 1

# With start-period for slow-starting apps
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
  CMD node healthcheck.js || exit 1
```

### Best Practices

1. **Use appropriate health checks** - Don't use shallow checks (e.g., ping when you need connection tests)
2. **Use `start-period` for slow apps** - Gives containers grace period before failures count
3. **Verify tool availability** - Tools like `curl` may not be in slim/alpine images
4. **Lightweight checks** - Use `wget --spider` or native commands when possible

**Source**: [Docker HEALTHCHECK Reference](https://docs.docker.com/reference/dockerfile/#healthcheck)

---

## Language-Specific Patterns

### Node.js with Multi-Stage Build

```dockerfile
FROM node:20.11.0-alpine AS builder

WORKDIR /app

# Install all dependencies (including devDependencies)
COPY package*.json ./
RUN npm ci

# Build the application
COPY . .
RUN npm run build

# Production stage - only production dependencies
FROM node:20.11.0-alpine AS production

RUN addgroup -g 10001 -S nodejs && \
    adduser -S nodejs -u 10001

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production && \
    npm cache clean --force

# Copy built assets
COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist

USER nodejs

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD node healthcheck.js || exit 1

CMD ["node", "dist/server.js"]
```

### Python with Virtual Environment

```dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Production
FROM python:3.12-slim

# Create non-root user (UID > 10000)
RUN useradd -m -u 10001 python

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application
COPY --chown=python:python . .

USER python

ENV PATH="/opt/venv/bin:$PATH"

CMD ["python", "app.py"]
```

### Ruby/Rails Application

```dockerfile
FROM ruby:3.3-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    build-base \
    postgresql-dev \
    nodejs \
    yarn

WORKDIR /app

# Install gems
COPY Gemfile Gemfile.lock ./
RUN bundle config set --local deployment 'true' && \
    bundle config set --local without 'development test' && \
    bundle install

# Install node packages and build assets
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .

# Precompile assets
RUN SECRET_KEY_BASE=dummy bundle exec rails assets:precompile

# Production
FROM ruby:3.3-alpine

# Install runtime dependencies only
RUN apk add --no-cache \
    postgresql-client \
    nodejs \
    tzdata

RUN addgroup -g 10001 -S rails && \
    adduser -S rails -u 10001

WORKDIR /app

# Copy gems and application
COPY --from=builder /usr/local/bundle /usr/local/bundle
COPY --from=builder --chown=rails:rails /app /app

USER rails

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["bundle", "exec", "rails", "server", "-b", "0.0.0.0"]
```

---

## Build Arguments and Environment

### Build Arguments

```dockerfile
ARG NODE_ENV=production
ARG BUILD_DATE
ARG VERSION

RUN if [ "$NODE_ENV" = "production" ]; then \
      npm ci --only=production; \
    else \
      npm ci; \
    fi

# Build with:
# docker build --build-arg NODE_ENV=development -t my-app .
```

### Environment Variables

```dockerfile
ENV NODE_ENV=production \
    PORT=3000 \
    LOG_LEVEL=info

# Can be overridden at runtime:
# docker run -e LOG_LEVEL=debug my-app
```

---

## Development vs Production Targets

```dockerfile
# Development stage
FROM node:20-alpine AS development

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

CMD ["npm", "run", "dev"]

# Production stage
FROM node:20-alpine AS production

RUN addgroup -g 10001 -S nodejs && \
    adduser -S nodejs -u 10001

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY --chown=nodejs:nodejs . .

USER nodejs

CMD ["npm", "start"]

# Build with: docker build --target development
# Or: docker build --target production (default)
```

BuildKit optimizes by only processing stages your target depends on.

---

## Best Practices Summary

### ✅ DO

1. **Use specific versions** - `FROM node:20.11.0-alpine`, never `:latest`
2. **Use multi-stage builds** - Reduces attack surface, smaller images
3. **Run as non-root user** - UID > 10,000 for security
4. **Order layers by change frequency** - Better caching
5. **Use .dockerignore** - Essential for security and size
6. **Combine apt-get update with install** - Prevents cache issues
7. **Use `set -o pipefail`** - Catch errors in piped commands
8. **Add HEALTHCHECK** - Production-necessary for orchestration
9. **Scan for vulnerabilities** - Use Docker Scout or Trivy
10. **Pin to digests for critical apps** - Supply chain security

### ❌ DON'T

1. **Use :latest tag** - Unpredictable, unreproducible builds
2. **Run as root** - Security risk, use UID > 10,000
3. **Store secrets in image** - Use runtime environment variables
4. **Install unnecessary packages** - Increases attack surface
5. **Use ADD when COPY works** - ADD has unexpected behaviors
6. **Forget .dockerignore** - 87% of images have vulnerabilities
7. **Skip HEALTHCHECK** - Orchestration cannot detect failures
8. **Separate apt-get update from install** - Cache inconsistency risk

---

## CI/CD Integration

Rebuild images frequently with `--no-cache` to obtain security patches. Integrate automated building and testing through GitHub Actions or equivalent pipelines.

```bash
# Build without cache for security updates
docker build --no-cache -t my-app:latest .

# Scan in CI pipeline
docker scout cves my-app:latest --exit-code
```

---

## Testing Dockerfiles

```bash
# Build
docker build -t my-app:latest .

# Run
docker run -p 3000:3000 my-app:latest

# Check size
docker images my-app:latest

# Scan for vulnerabilities
docker scout cves my-app:latest
trivy image my-app:latest

# Inspect layers
docker history my-app:latest

# Test as non-root (should work)
docker run --user 10001:10001 my-app:latest

# Test read-only filesystem
docker run --read-only --tmpfs /tmp my-app:latest
```

---

## References and Sources

This guide is based on official Docker documentation:

- [Docker Best Practices Official Documentation](https://docs.docker.com/build/building/best-practices/)
- [Docker Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker USER Instruction Best Practices](https://www.docker.com/blog/understanding-the-docker-user-instruction/)
- [Docker HEALTHCHECK Reference](https://docs.docker.com/reference/dockerfile/#healthcheck)
- [Dockerfile Reference](https://docs.docker.com/reference/dockerfile/)
- [Docker Security Documentation](https://docs.docker.com/engine/security/)

Last updated: December 2025
