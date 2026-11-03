# Multi-Stage Builds and Layer Optimization

## Contents

- [Multi-Stage Builds](#multi-stage-builds-security-critical)
- [Layer Optimization](#layer-optimization)

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
FROM node:24-alpine AS dependencies
RUN npm ci --only=production

FROM node:24-alpine AS builder
COPY --from=dependencies /app/node_modules ./node_modules
RUN npm run build

FROM node:24-alpine AS production
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

Without pipefail, errors in piped commands may be silently ignored. Piping a script into a shell runs whatever the server returns: pin the version and verify a checksum or signature before executing, or install from a package instead.

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
