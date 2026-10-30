# Security and Health Checks

Version tags are examples as of 2026-10; use current releases.

## Contents

- [Security Best Practices](#security-best-practices)
- [Health Checks](#health-checks)
- [Build, Rebuild and Test](#build-rebuild-and-test)

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
FROM node:24-alpine

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

# ❌ BAD - ARG values persist in image metadata and `docker history`,
# even if a later layer deletes the file that used them
ARG NPM_TOKEN

# ✅ GOOD - BuildKit secret mount: available only during this RUN, never stored in a layer
RUN --mount=type=secret,id=npm_token,env=NPM_TOKEN npm ci

# ✅ Runtime secrets - pass at runtime
# docker run -e API_KEY=$API_KEY my-image
```

```bash
docker build --secret id=npm_token,env=NPM_TOKEN .
```

---

## Health Checks

A HEALTHCHECK lets Docker detect an unhealthy container. Add one only when no orchestrator or proxy already checks health (Kubernetes probes, Kamal proxy, ECS, Compose healthcheck); a Rails app deployed with Kamal, for example, relies on the proxy hitting `/up` and needs none.

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

## Build, Rebuild and Test

Rebuild images regularly with `--no-cache` so base-image security patches are picked up, and fail the pipeline on findings:

```bash
docker build --no-cache -t my-app:latest .
docker scout cves my-app:latest --exit-code
```

Check the hardening claims instead of assuming them:

```bash
# Runs as an arbitrary non-root UID
docker run --user 10001:10001 my-app:latest

# Works with a read-only root filesystem
docker run --read-only --tmpfs /tmp my-app:latest

# Inspect layers for leaked secrets and bloat
docker history my-app:latest
```
