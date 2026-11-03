# Common Service Patterns

Version tags are examples as of 2026-10; use current releases.

## Contents

- [Node.js Application](#nodejs-application)
- [Rails with Solid Queue Background Jobs](#rails-with-solid-queue-background-jobs)
- [Python/Django with Celery](#pythondjango-with-celery)

---

## Node.js Application

```yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: ${BUILD_TARGET:-production}
    image: ${APP_NAME}:${VERSION:-latest}
    restart: unless-stopped
    ports:
      - "${APP_PORT:-3000}:3000"
    environment:
      NODE_ENV: ${NODE_ENV:-production}
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: redis://redis:6379
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
    volumes:
      # Development: mount source code
      - ./src:/app/src:ro
      # Production: named volumes for data
      - uploads:/app/uploads
      - logs:/app/logs
    networks:
      - app_network
    healthcheck:
      test: ["CMD", "node", "healthcheck.js"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

## Rails with Solid Queue Background Jobs

Rails 8 defaults to Solid Queue (jobs), Solid Cache and Solid Cable, all backed by the database, so a Rails stack needs no Redis and no separate job backend. The Dockerfile `rails new` generates (see the Ruby/Rails section of the Dockerfile patterns reference) serves through Thruster on port 80, and its default production `database.yml` keeps the primary, cache, queue and cable databases as SQLite files under `storage/`.

```yaml
services:
  web:
    build: .
    command: ["./bin/thrust", "./bin/rails", "server"]
    restart: unless-stopped
    ports:
      - "3000:80"
    environment:
      RAILS_MASTER_KEY: ${RAILS_MASTER_KEY}
    volumes:
      - rails_storage:/rails/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/up"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s

  jobs:
    build: .
    command: ./bin/jobs
    restart: unless-stopped
    environment:
      RAILS_MASTER_KEY: ${RAILS_MASTER_KEY}
    volumes:
      - rails_storage:/rails/storage
    depends_on:
      web:
        condition: service_healthy

volumes:
  rails_storage:
```

- `./bin/jobs` runs the Solid Queue supervisor. `bin/rails solid_queue:install` creates it (plus `config/queue.yml`), and `rails new` runs that installer when it bundles.
- `bin/docker-entrypoint` runs `db:prepare` only when the command is `./bin/rails server`, so `jobs` waits for `web` to be healthy instead of preparing the database itself.
- `/up` is Rails' built-in health route; the `web` check is a Compose healthcheck, which is why the Dockerfile itself carries no `HEALTHCHECK`.
- Single-server shortcut: drop the `jobs` service and set `SOLID_QUEUE_IN_PUMA: "true"` on `web`; `config/puma.rb` then runs the supervisor inside Puma.
- SQLite files on a volume only work on a single host; for several app hosts use a networked database (PostgreSQL or MySQL) for all four databases.

## Python/Django with Celery

```yaml
services:
  web:
    build:
      context: .
      dockerfile: Dockerfile
    command: gunicorn myapp.wsgi:application --bind 0.0.0.0:8000 --workers 4
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      DJANGO_SETTINGS_MODULE: myapp.settings.production
      DATABASE_URL: postgresql://postgres:password@db:5432/myapp
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./media:/app/media
      - ./static:/app/static
    networks:
      - app_network

  celery_worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A myapp worker -l info
    restart: unless-stopped
    environment:
      DJANGO_SETTINGS_MODULE: myapp.settings.production
      DATABASE_URL: postgresql://postgres:password@db:5432/myapp
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - db
      - redis
    networks:
      - app_network

  celery_beat:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A myapp beat -l info
    restart: unless-stopped
    environment:
      DJANGO_SETTINGS_MODULE: myapp.settings.production
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - redis
    networks:
      - app_network
```
