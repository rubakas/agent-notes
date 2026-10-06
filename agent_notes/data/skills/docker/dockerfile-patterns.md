# Language-Specific Patterns

## Contents

- [Node.js with Multi-Stage Build](#nodejs-with-multi-stage-build)
- [Python with Virtual Environment](#python-with-virtual-environment)
- [Ruby/Rails Application](#rubyrails-application)
- [Build Arguments and Environment](#build-arguments-and-environment)
- [Development vs Production Targets](#development-vs-production-targets)

---

## Node.js with Multi-Stage Build

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
