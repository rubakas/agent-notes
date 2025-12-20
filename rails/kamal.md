# Kamal

Deploy web apps anywhere with zero-downtime deployments using Docker.

> **Source**: [Kamal Official Documentation](https://kamal-deploy.org/) | [GitHub](https://github.com/basecamp/kamal)

---

## Overview

**Kamal** = "Capistrano for Containers" by 37signals. Default deployment tool for Rails 8.

**Key Features:**
- Zero-downtime deployments via Traefik proxy
- Deploy anywhere (VPS, bare metal, cloud)
- Remote builds, asset bridging
- Accessory management (databases, Redis)
- Automatic provisioning
- Docker layer caching

**Source**: [Kamal Documentation](https://kamal-deploy.org/)

---

## Installation

### Rails 8+ (Pre-installed)

```bash
rails new myapp
cd myapp
# config/deploy.yml already exists
```

### Manual Installation

```bash
gem install kamal
kamal init  # Creates config/deploy.yml and .kamal/secrets
```

---

## Configuration

### Minimal deploy.yml

```yaml
# config/deploy.yml
service: myapp
image: username/myapp

servers:
  web:
    hosts:
      - 192.168.0.1

registry:
  username: your-username
  password:
    - KAMAL_REGISTRY_PASSWORD

env:
  secret:
    - RAILS_MASTER_KEY
```

### Production Configuration

```yaml
service: myapp
image: username/myapp

servers:
  web:
    hosts:
      - 192.168.0.1
      - 192.168.0.2
    labels:
      traefik.http.routers.myapp.rule: Host(`myapp.com`)

  workers:
    hosts:
      - 192.168.0.3
    cmd: bundle exec sidekiq

registry:
  server: ghcr.io
  username: github-username
  password:
    - KAMAL_REGISTRY_PASSWORD

proxy:
  ssl: true
  host: myapp.com

env:
  clear:
    RAILS_ENV: production
  secret:
    - RAILS_MASTER_KEY
    - DATABASE_URL

asset_path: /app/public/assets

volumes:
  - "storage:/app/storage"

retain_containers: 5
retain_images: 5

healthcheck:
  path: /up
  port: 3000
  interval: 10s

ssh:
  user: deploy
```

**Source**: [Kamal Configuration](https://kamal-deploy.org/docs/configuration/overview/)

---

## Accessories (Databases, Redis)

**Important**: Accessories **do not have zero-downtime deployments**. Managed separately from main app.

### PostgreSQL

```yaml
accessories:
  db:
    image: postgres:16
    host: 192.168.0.10
    port: "5432:5432"
    env:
      clear:
        POSTGRES_USER: myapp
      secret:
        - POSTGRES_PASSWORD
    directories:
      - data:/var/lib/postgresql/data
```

### Redis

```yaml
accessories:
  redis:
    image: redis:7-alpine
    host: 192.168.0.11
    port: "6379:6379"
    cmd: redis-server --appendonly yes
    directories:
      - data:/data
```

### MySQL

```yaml
accessories:
  mysql:
    image: mysql:8.0
    host: 192.168.0.12
    port: "3306:3306"
    env:
      clear:
        MYSQL_DATABASE: myapp_production
      secret:
        - MYSQL_ROOT_PASSWORD
    directories:
      - data:/var/lib/mysql
```

**Source**: [Kamal Accessories](https://kamal-deploy.org/docs/configuration/accessories/)

---

## Commands

### Deployment

```bash
# Initial setup
kamal setup

# Deploy
kamal deploy
kamal deploy -d staging
kamal deploy -d production

# App management
kamal app restart
kamal app logs -f
kamal app exec 'bin/rails console'
kamal app exec 'bin/rails db:migrate'

# Accessories
kamal accessory boot all
kamal accessory boot db
kamal accessory reboot redis
kamal accessory logs db

# Cleanup
kamal prune -y
```

---

## Destinations (Staging/Production)

### Base Config

```yaml
# config/deploy.yml
service: myapp
image: username/myapp
registry:
  username: username
  password:
    - KAMAL_REGISTRY_PASSWORD
```

### Staging

```yaml
# config/deploy.staging.yml
servers:
  web:
    hosts:
      - staging.example.com

env:
  clear:
    RAILS_ENV: staging

proxy:
  host: staging.myapp.com
```

### Production

```yaml
# config/deploy.production.yml
servers:
  web:
    hosts:
      - prod1.example.com
      - prod2.example.com

env:
  clear:
    RAILS_ENV: production

proxy:
  ssl: true
  host: myapp.com

require_destination: true  # Prevent accidental deploys
```

---

## Secrets Management

```bash
# .kamal/secrets
KAMAL_REGISTRY_PASSWORD=your-password
RAILS_MASTER_KEY=your-key
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://host:6379
```

```yaml
# config/deploy.yml
registry:
  password:
    - KAMAL_REGISTRY_PASSWORD

env:
  secret:
    - RAILS_MASTER_KEY
    - DATABASE_URL
```

**Important**: Add `.kamal/secrets*` to `.gitignore`!

---

## Hooks

```bash
.kamal/hooks/
├── pre-deploy          # Before deploy
├── post-deploy         # After deploy
└── pre-traefik-reboot  # Before proxy restart
```

### Example: Pre-deploy Hook

```bash
#!/bin/bash
# .kamal/hooks/pre-deploy
kamal app exec 'bin/rails db:migrate'
```

Make executable: `chmod +x .kamal/hooks/*`

---

## Zero-Downtime Flow

1. Health check old version (proxy routes traffic)
2. Build new image
3. Push to registry
4. Pull on servers
5. Start new container alongside old
6. Health check new version
7. Proxy gradually shifts traffic
8. Stop old container
9. Cleanup based on retention settings

**Proxy (Traefik) is key** to zero-downtime.

---

## Rails Patterns

### Database Migrations

```bash
# Via hook (recommended)
# .kamal/hooks/pre-deploy
kamal app exec 'bin/rails db:migrate'

# Or manually
kamal app exec 'bin/rails db:migrate'
kamal deploy
```

### Sidekiq Workers

```yaml
servers:
  web:
    hosts:
      - web1.example.com

  workers:
    hosts:
      - worker1.example.com
    cmd: bundle exec sidekiq
```

### Console Access

```bash
kamal app exec 'bin/rails console'
kamal app exec 'bin/rails dbconsole'
```

---

## Best Practices

### ✅ DO

1. **Use destinations** for staging/production
```yaml
require_destination: true
```

2. **Configure health checks**
```yaml
healthcheck:
  path: /up
  interval: 10s
```

3. **Set retention limits**
```yaml
retain_containers: 5
retain_images: 5
```

4. **Use secrets file**, add to `.gitignore`

5. **Run accessories on separate hosts**

6. **Use pre-deploy hooks** for migrations

7. **Specific image tags** in production
```yaml
image: username/myapp:v1.2.3  # Not :latest
```

### ❌ DON'T

1. **Don't commit secrets** to git
2. **Don't expect zero-downtime for accessories**
3. **Don't skip health checks**
4. **Don't use :latest tag** in production
5. **Don't deploy to production without testing staging first**

---

## Workflow

```bash
# 1. Initial setup
kamal setup
kamal accessory boot all

# 2. Development cycle
git commit -am "Update"
git push
kamal deploy -d staging
# Test staging
kamal deploy -d production

# 3. Monitoring
kamal app logs -f
kamal accessory logs db -f

# 4. Troubleshooting
kamal server containers
kamal app logs --tail 100
kamal prune -y
```

---

## Troubleshooting

```bash
# Check status
kamal server containers

# View logs
kamal app logs --tail 100
kamal accessory logs db

# Health check
curl https://myapp.com/up

# Increase timeouts
# In config/deploy.yml:
deploy_timeout: 60
readiness_delay: 10

# Cleanup
kamal prune -y
```

---

## Summary

- **Kamal** = Zero-downtime Docker deployments
- **Default in Rails 8**
- **Zero-downtime** via Traefik proxy
- **Accessories** = No zero-downtime (plan maintenance)
- **Destinations** = Staging/production separation
- **Secrets** = `.kamal/secrets` (never commit!)

---

## References

- [Kamal Official Documentation](https://kamal-deploy.org/)
- [Kamal GitHub](https://github.com/basecamp/kamal)
- [Configuration](https://kamal-deploy.org/docs/configuration/overview/)
- [Accessories](https://kamal-deploy.org/docs/configuration/accessories/)
- [Commands](https://kamal-deploy.org/docs/commands/deploy/)

Last updated: December 2025
