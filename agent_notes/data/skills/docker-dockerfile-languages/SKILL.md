---
name: docker-dockerfile-languages
description: "Dockerfile language patterns: Node.js, Python, Ruby builds, dev/prod targets, and CI/CD integration"
group: docker
---

# Dockerfile Language Patterns

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
