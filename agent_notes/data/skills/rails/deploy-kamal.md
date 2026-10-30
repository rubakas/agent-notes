# Kamal Deployment

## Contents

- [Overview](#overview)
- [Installation & Setup](#installation--setup)
- [Configuration](#configuration)
- [Dockerfile](#dockerfile)
- [Accessories](#accessories)
- [Commands](#commands)
- [Destinations](#destinations)
- [Secrets Management](#secrets-management)
- [Hooks](#hooks)
- [Best Practices](#best-practices)
- [Sources](#sources)

## Overview

Kamal deploys Docker containers to servers over SSH. It builds and pushes the image, boots the new container on each host, and swaps traffic over without downtime. Kamal 2 fronts the app with kamal-proxy instead of Traefik; the proxy terminates SSL, routes requests and health-checks the new container.

Fizzy's self-hosted deploy is a single `config/deploy.yml`. 37signals runs the hosted product from a second set of files under `saas/config/`.

Why: Fizzy's own docs recommend it for self-hosting: "Kamal makes it easy to set up a bare server, copy the application to it, and manage the configuration settings that it uses." (Fizzy: `docs/kamal-deployment.md`)

## Installation & Setup

Kamal is a Gemfile entry that is never required at runtime:

```ruby
# Gemfile
gem "kamal", require: false
```

`bin/kamal` is a Bundler binstub. In SaaS mode it also inserts `-c` with the path of the `fizzy-saas` deploy file, so the same command works for both setups. Fizzy's docs run `kamal init` once to create `.kamal/`, then use `bin/kamal setup` for the first deploy and `bin/kamal deploy` afterwards:

```bash
# Illustrative (not from Fizzy)
bundle exec kamal init
bin/kamal setup
bin/kamal deploy
```

Why: a `require: false` gem keeps the deploy tool out of the running app (Fizzy: `Gemfile`, `bin/kamal`, `docs/kamal-deployment.md`).

## Configuration

`config/deploy.yml` is a starter file; its top section, "About your deployment", holds everything an operator must change. These ranges are copied from it, with the original comments dropped between them:

```yaml
# config/deploy.yml
servers:
  web:
    - fizzy.example.com  # Set your server name here
# ...
proxy:
  ssl: true                # Set this to false if you *don't* want SSL
  host: fizzy.example.com  # Set your server name here to use automatic SSL
# ...
env:
  secret:
    - SECRET_KEY_BASE
    - VAPID_PUBLIC_KEY
    - VAPID_PRIVATE_KEY
    - SMTP_USERNAME
    - SMTP_PASSWORD
  clear:
    BASE_URL: https://fizzy.example.com # The public URL of your Fizzy instance
    MAILER_FROM_ADDRESS: support@example.com # The email "from" address that Fizzy sends email from
    SMTP_ADDRESS: mail.example.com # The SMTP server you'll use to send email
    MULTI_TENANT: false # Set to true to allow multiple accounts to sign up
    SOLID_QUEUE_IN_PUMA: true # Run background jobs in the app container
```

Secret values are listed by name only. Kamal reads them from `.kamal/secrets` (see Secrets Management). The rest of the file sets the registry, a persistent volume for SQLite and local Active Storage files, asset bridging and the builder:

```yaml
# config/deploy.yml
registry:
  server: localhost:5555
# ...
volumes:
  - "fizzy_storage:/rails/storage"
# ...
asset_path: /rails/public/assets
# ...
builder:
  arch: amd64
```

`asset_path` keeps fingerprinted JS and CSS from the old release available while the new one boots, so in-flight requests do not 404 (Fizzy's comment on that setting). Fizzy also defines shortcuts in the same file, so `bin/kamal console` opens a Rails console in production:

```yaml
# config/deploy.yml
aliases:
  console: app exec --interactive --reuse "bin/rails console"
  shell: app exec --interactive --reuse "bash"
  logs: app logs -f
  dbc: app exec --interactive --reuse "bin/rails dbconsole --include-password"
```

Kamal's proxy health check defaults to `/up`, which Fizzy serves from the stock Rails health controller:

```ruby
# config/routes.rb
  get "up", to: "rails/health#show", as: :rails_health_check
```

Why: one commented file lets a self-hoster edit a handful of values and nothing else (Fizzy: `docs/kamal-deployment.md`, "The config/deploy.yml has been mostly set up for you").

## Dockerfile

Fizzy's `Dockerfile` is multi-stage: a `base` stage with runtime packages and production environment variables, a throw-away `build` stage that installs gems and precompiles bootsnap and assets, and a final stage that copies only the gems and the app and runs as a non-root user. These are the structural lines, copied from it. The Ruby version `3.4.8` is an example as of 2026-10; use your project's Ruby version.

```dockerfile
# Dockerfile
ARG RUBY_VERSION=3.4.8
FROM docker.io/library/ruby:$RUBY_VERSION-slim AS base
# ...
# Throw-away build stage to reduce size of final image
FROM base AS build
# ...
# Final stage for app image
FROM base
# ...
# Entrypoint prepares the database.
ENTRYPOINT ["/rails/bin/docker-entrypoint"]

# Start server via Thruster by default, this can be overwritten at runtime
EXPOSE 80
CMD ["./bin/thrust", "./bin/rails", "server"]
```

Thruster fronts Puma, so the container listens on port 80. The entrypoint prepares the database only when the container is about to start the server, then `exec`s whatever command it was given:

```bash
# bin/docker-entrypoint
#!/bin/bash -e

# If running the rails server then create or migrate existing database
if [ "${1}" == "./bin/thrust" ] && [ "${2}" == "./bin/rails" ] && [ "${3}" == "server" ]; then
  MIGRATE=1 ./bin/rails db:prepare
fi

exec "${@}"
```

Why: the build stage's compilers and caches never reach the final image, which keeps it small (Fizzy: `Dockerfile`, comment "Throw-away build stage to reduce size of final image").

## Accessories

Fizzy's OSS `config/deploy.yml` declares no accessories, and the Gemfile has no Redis gem. The SaaS deploy declares one, `hotcell`, for attachment processing in a container with no network:

```yaml
# saas/config/deploy.yml
accessories:
  hotcell:
# ...
    network: none
```

`network: none` is an accessory key rather than a raw Docker flag, so it cannot go under `options:`. The file's own comment explains why this is an accessory and not an app role: "Kamal hard-codes --network kamal for roles". A deploy never touches an accessory, and booting one is an explicit command. `saas/config/deploy.production.yml` adds a `load-balancer` accessory the same way.

Why: accessories sit outside the app's rolling deploy, so they suit services that need their own lifecycle or network rules (Fizzy: `saas/config/deploy.yml`, comment above `accessories:`).

## Commands

The commands used day to day, all through the binstub:

```bash
# Illustrative (not from Fizzy)
bin/kamal deploy
bin/kamal app containers
bin/kamal app logs -f
bin/kamal app exec 'bin/rails db:migrate'
bin/kamal prune all
```

Fizzy's `config/deploy.yml` also defines the aliases `console`, `shell`, `logs` and `dbc`, so `bin/kamal console` and `bin/kamal logs` replace the longer `app exec` and `app logs` forms (the aliases block is shown under Configuration).

Why: the aliases turn the interactive `app exec` incantations into one word (Fizzy: `config/deploy.yml`).

## Destinations

A destination is an extra config file merged over the base one and selected with `-d`. Fizzy's SaaS files are `saas/config/deploy.production.yml`, `deploy.staging.yml`, `deploy.beta.yml` and `deploy.beta1.yml`. The production file assigns each host a tag, and the `tags:` map then gives every tag its own environment value, here the Solid Cache database host:

```yaml
# saas/config/deploy.production.yml
servers:
  web:
    hosts:
      - fizzy-app-01.sc-chi-int.37signals.com: sc_chi
      - fizzy-app-02.sc-chi-int.37signals.com: sc_chi
      - fizzy-app-101.df-iad-int.37signals.com: df_iad
      - fizzy-app-102.df-iad-int.37signals.com: df_iad
# ...
  tags:
    sc_chi:
      MYSQL_SOLID_CACHE_HOST: fizzy-solidcache-db-01.sc-chi-int.37signals.com
```

```bash
# Illustrative (not from Fizzy)
bin/kamal deploy -d production
```

Why: per-datacenter values live in the destination file, so the base file stays the same for every environment (Fizzy: `saas/config/deploy.production.yml`).

## Secrets Management

`config/deploy.yml` lists secret names under `env: secret:`, and the values come from a secrets file that stays out of the deploy config. Fizzy's self-hosting docs have you create `.kamal/secrets` with real values and warn: "it's important that you DON'T CHECK THIS FILE INTO YOUR REPO!" (Fizzy: `docs/kamal-deployment.md`).

The SaaS deploy points Kamal at per-destination files shipped inside the `fizzy-saas` gem. These two lines are copied from `saas/config/deploy.yml`:

```yaml
# saas/config/deploy.yml
hooks_path: <%= File.join(Gem::Specification.find_by_name("fizzy-saas").gem_dir, ".kamal", "hooks") %>
secrets_path: <%= File.join(Gem::Specification.find_by_name("fizzy-saas").gem_dir, ".kamal/secrets") %>
```

The files in `saas/.kamal/` are named `secrets.beta`, `secrets.beta1` to `secrets.beta4`, `secrets.production` and `secrets.staging`. Kamal also accepts a `.kamal/secrets-common` file shared by all destinations. A secrets file can hold references instead of raw values:

```bash
# Illustrative (not from Fizzy)
SECRET_KEY_BASE=$SECRET_KEY_BASE
SMTP_PASSWORD=$(pass smtp/password)
```

Never paste a raw credential into a file that is committed.

Why: Kamal expands environment variables and shell commands in the secrets file, so a password manager can supply values at deploy time (Kamal docs: https://kamal-deploy.org/docs/configuration/environment-variables/#secrets).

## Hooks

Kamal runs executables from the hooks directory at fixed points. The names Kamal ships samples for are `docker-setup`, `pre-connect`, `pre-build`, `pre-deploy`, `post-deploy`, `pre-app-boot`, `post-app-boot`, `pre-proxy-reboot` and `post-proxy-reboot`. Fizzy's SaaS deploy sets a custom `hooks_path` and defines four of them in `saas/.kamal/hooks/`: `pre-connect`, `pre-build`, `pre-deploy` and `post-deploy`. It raises the log level for two of them:

```yaml
# saas/config/deploy.yml
hooks_path: <%= File.join(Gem::Specification.find_by_name("fizzy-saas").gem_dir, ".kamal", "hooks") %>
# ...
# Kamal logs a hook's output at DEBUG, so the cell build, push, and reboot the hooks do would otherwise
# only show under -v.
hooks_output:
  pre-build: verbose
  pre-deploy: verbose
```

Database preparation is not a hook. It happens in `bin/docker-entrypoint` (shown under Dockerfile), which runs `db:prepare` when a container starts the server.

Why: Kamal logs hook output only at DEBUG, so Fizzy sets `hooks_output` to `verbose` for the build and deploy hooks (Fizzy: `saas/config/deploy.yml`, comment above `hooks_output`).

## Best Practices

1. **Serve a health endpoint.** Fizzy routes `up` to `rails/health#show` (shown under Configuration) and kamal-proxy checks it before sending traffic.
2. **Retain a few old containers.** Fizzy sets `retain_containers: 2` in `saas/config/deploy.production.yml` and `1` for staging and beta. Kamal's default is 5.
3. **Bridge assets across releases.** Keep `asset_path` set, as Fizzy does.
4. **Assume old and new code overlap.** Kamal starts the new container, routes traffic to it once it answers the health check, and only then stops the old one, so the two versions run side by side for a while. A migration must therefore work for both. The last step is general practice, not something Kamal or Fizzy states.

Why: items 1 to 3 are things Fizzy sets or relies on in its deploy files (Fizzy: `config/deploy.yml`, `saas/config/deploy.production.yml`); item 4 follows from the deploy sequence in the Kamal docs (https://kamal-deploy.org/docs/commands/deploy/).

## Sources

- Kamal documentation: https://kamal-deploy.org/
- Kamal repository: https://github.com/basecamp/kamal
- Kamal `deploy` command: https://kamal-deploy.org/docs/commands/deploy/
- Fizzy `docs/kamal-deployment.md`, `config/deploy.yml`, `saas/config/` and `Dockerfile`, at commit 6aebc0cea
