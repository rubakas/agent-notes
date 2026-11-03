# Base Images and Structure

Version tags are examples as of 2026-10; use current releases.

## Contents

- [Dockerfile Structure Template](#dockerfile-structure-template)
- [Base Image Selection](#base-image-selection)

---

## Dockerfile Structure Template

```dockerfile
# syntax=docker/dockerfile:1

# Build stage
FROM node:24-alpine AS builder

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
FROM node:24-alpine AS production

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

# Health check - only when no orchestrator or proxy already checks health
# (Kubernetes probes, Kamal proxy, ECS, Compose healthcheck)
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
# Smallest size, minimal attack surface (musl libc: avoid for Ruby, native gems break)
FROM node:24-alpine
FROM python:3.12-alpine

# Install common dependencies on Alpine
RUN apk add --no-cache \
    bash \
    curl \
    git \
    postgresql-dev
```

### Pin to Specific Digests for Supply Chain Security

```dockerfile
# Pin to specific digest for guaranteed immutability (get the real digest from your registry)
FROM node:24-alpine@sha256:<digest>

# Note: Requires active maintenance for security updates
# Use Docker Scout for automated remediation workflows
```

**Source**: [Docker Best Practices - Supply Chain Security](https://docs.docker.com/build/building/best-practices/)

### Debian Slim (Balanced)

```dockerfile
# Good balance of size and compatibility
FROM node:24-slim
FROM python:3.12-slim
FROM ruby:3.4-slim

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
FROM gcr.io/distroless/nodejs24-debian12
FROM gcr.io/distroless/python3-debian12
FROM gcr.io/distroless/java17-debian12

# Note: No shell available, debugging is harder
# Best for production security
```
