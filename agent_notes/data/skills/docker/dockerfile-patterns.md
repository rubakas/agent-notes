# Language-Specific Patterns

Version tags are examples as of 2026-10; use current releases.

## Contents

- [Node.js with Multi-Stage Build](#nodejs-with-multi-stage-build)
- [Python with Virtual Environment](#python-with-virtual-environment)
- [Ruby/Rails Application](#rubyrails-application)
- [Build Arguments and Environment](#build-arguments-and-environment)
- [Development vs Production Targets](#development-vs-production-targets)

---

## Node.js with Multi-Stage Build

```dockerfile
FROM node:24-alpine AS builder

WORKDIR /app

# Install all dependencies (including devDependencies)
COPY package*.json ./
RUN npm ci

# Build the application
COPY . .
RUN npm run build

# Production stage - only production dependencies
FROM node:24-alpine AS production

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

Keep the `HEALTHCHECK` only when no orchestrator or proxy already checks health (Kubernetes probes, Kamal proxy, ECS, Compose healthcheck).

## Python with Virtual Environment

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

## Ruby/Rails Application

Source: the Dockerfile `rails new` generates (railties 8.1.3.1, Ruby 3.4.4), unmodified.

```dockerfile
# syntax=docker/dockerfile:1
# check=error=true

# This Dockerfile is designed for production, not development. Use with Kamal or build'n'run by hand:
# docker build -t demo .
# docker run -d -p 80:80 -e RAILS_MASTER_KEY=<value from config/master.key> --name demo demo

# For a containerized dev environment, see Dev Containers: https://guides.rubyonrails.org/getting_started_with_devcontainer.html

# Make sure RUBY_VERSION matches the Ruby version in .ruby-version
ARG RUBY_VERSION=3.4.4
FROM docker.io/library/ruby:$RUBY_VERSION-slim AS base

# Rails app lives here
WORKDIR /rails

# Install base packages
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y curl libjemalloc2 libvips sqlite3 && \
    ln -s /usr/lib/$(uname -m)-linux-gnu/libjemalloc.so.2 /usr/local/lib/libjemalloc.so && \
    rm -rf /var/lib/apt/lists /var/cache/apt/archives

# Set production environment variables and enable jemalloc for reduced memory usage and latency.
ENV RAILS_ENV="production" \
    BUNDLE_DEPLOYMENT="1" \
    BUNDLE_PATH="/usr/local/bundle" \
    BUNDLE_WITHOUT="development" \
    LD_PRELOAD="/usr/local/lib/libjemalloc.so"

# Throw-away build stage to reduce size of final image
FROM base AS build

# Install packages needed to build gems
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y build-essential git libvips libyaml-dev pkg-config && \
    rm -rf /var/lib/apt/lists /var/cache/apt/archives

# Install application gems
COPY vendor/* ./vendor/
COPY Gemfile Gemfile.lock ./

RUN bundle install && \
    rm -rf ~/.bundle/ "${BUNDLE_PATH}"/ruby/*/cache "${BUNDLE_PATH}"/ruby/*/bundler/gems/*/.git && \
    # -j 1 disable parallel compilation to avoid a QEMU bug: https://github.com/rails/bootsnap/issues/495
    bundle exec bootsnap precompile -j 1 --gemfile

# Copy application code
COPY . .

# Precompile bootsnap code for faster boot times.
# -j 1 disable parallel compilation to avoid a QEMU bug: https://github.com/rails/bootsnap/issues/495
RUN bundle exec bootsnap precompile -j 1 app/ lib/

# Precompiling assets for production without requiring secret RAILS_MASTER_KEY
RUN SECRET_KEY_BASE_DUMMY=1 ./bin/rails assets:precompile




# Final stage for app image
FROM base

# Run and own only the runtime files as a non-root user for security
RUN groupadd --system --gid 1000 rails && \
    useradd rails --uid 1000 --gid 1000 --create-home --shell /bin/bash
USER 1000:1000

# Copy built artifacts: gems, application
COPY --chown=rails:rails --from=build "${BUNDLE_PATH}" "${BUNDLE_PATH}"
COPY --chown=rails:rails --from=build /rails /rails

# Entrypoint prepares the database.
ENTRYPOINT ["/rails/bin/docker-entrypoint"]

# Start server via Thruster by default, this can be overwritten at runtime
EXPOSE 80
CMD ["./bin/thrust", "./bin/rails", "server"]
```

The `bin/docker-entrypoint` that Dockerfile points at, also unmodified:

```bash
#!/bin/bash -e

# If running the rails server then create or migrate existing database
if [ "${@: -2:1}" == "./bin/rails" ] && [ "${@: -1:1}" == "server" ]; then
  ./bin/rails db:prepare
fi

exec "${@}"
```

The base is Debian slim (not Alpine, whose musl libc breaks many native gems). The app is served by Thruster on port 80, and `bin/docker-entrypoint` runs `db:prepare` before the server starts. There is no `HEALTHCHECK` because Kamal's proxy health-checks Rails' built-in `/up` route. When versions move, regenerate with your own `rails new` rather than copying this one.

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

Build args are for non-secret settings; their values persist in image metadata and history (use BuildKit secret mounts instead; see the Dockerfile security reference).

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
FROM node:24-alpine AS development

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

CMD ["npm", "run", "dev"]

# Production stage
FROM node:24-alpine AS production

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
