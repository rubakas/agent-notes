# Common Service Patterns

## Contents

- [Node.js Application](#nodejs-application)
- [Rails with Background Workers](#rails-with-background-workers)
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

## Rails with Background Workers

```yaml
services:
  web:
    build:
      context: .
      dockerfile: Dockerfile
    command: bundle exec rails server -b 0.0.0.0
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      RAILS_ENV: ${RAILS_ENV:-production}
      DATABASE_URL: postgresql://postgres:password@db:5432/myapp
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY_BASE: ${SECRET_KEY_BASE}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - ./storage:/app/storage
      - ./log:/app/log
    networks:
      - app_network

  sidekiq:
    build:
      context: .
      dockerfile: Dockerfile
    command: bundle exec sidekiq
    restart: unless-stopped
    environment:
      RAILS_ENV: ${RAILS_ENV:-production}
      DATABASE_URL: postgresql://postgres:password@db:5432/myapp
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ./storage:/app/storage
      - ./log:/app/log
    networks:
      - app_network
```

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
