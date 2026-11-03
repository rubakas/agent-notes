# Solid Queue, Cache & Cable Configuration

## Contents

- [Solid Queue](#solid-queue)
- [Solid Cache](#solid-cache)
- [Solid Cable](#solid-cable)
- [Multi-Database Layout](#multi-database-layout)
- [Sources](#sources)

## Solid Queue

Solid Queue keeps job queues in a database instead of Redis. Fizzy turns it on in `config/environments/production.rb` and tunes it in `config/queue.yml`.

```ruby
# config/environments/production.rb
  # Use a real queuing backend for Active Job (and separate queues per environment).
  config.active_job.queue_adapter = :solid_queue
  config.solid_queue.connects_to = { database: { writing: :queue, reading: :queue } }
```

The queue file is one `default` anchor reused by every environment. `processes` defaults to `Concurrent.physical_processor_count` and `JOB_CONCURRENCY` overrides it:

```yaml
# config/queue.yml
default: &default
  dispatchers:
    - polling_interval: 1
      batch_size: 500
  workers:
    - queues: [ "default", "solid_queue_recurring", "backend", "webhooks", "*" ]
      threads: 3
      processes: <%= Integer(ENV.fetch("JOB_CONCURRENCY") { Concurrent.physical_processor_count }) %>
      polling_interval: 0.1

development: *default
test: *default
beta: *default
staging: *default
production: *default
```

Where the workers run is a deploy choice. `config/puma.rb` loads the Solid Queue Puma plugin for production deploys that are not SaaS, unless `SOLID_QUEUE_IN_PUMA` is `"false"`, so jobs run inside the web process:

```ruby
# config/puma.rb
# Only production configures a queue database, so a local supervisor dies on the missing
# solid_queue_recurring_tasks and takes Puma down with it.
unless Fizzy.saas? || Rails.env.local? || ENV["SOLID_QUEUE_IN_PUMA"] == "false"
  plugin :solid_queue
end
```

Fizzy's own `config/deploy.yml` also sets `SOLID_QUEUE_IN_PUMA: true` under `env: clear:` to make that explicit. The SaaS deploy (`saas/config/deploy.yml`) instead declares a separate `jobs` role that runs `bin/jobs`, a thin wrapper around `SolidQueue::Cli.start(ARGV)`:

```yaml
# saas/config/deploy.yml
  jobs:
    cmd: bin/jobs
```

Why: one process type fewer to run on a single box, and a dedicated role once web and jobs must scale apart (Fizzy: `config/puma.rb`, `saas/config/deploy.yml`).

## Solid Cache

Solid Cache stores Rails cache entries in a database. Fizzy selects it for production only; development uses `:memory_store` or `:null_store` and test uses `:null_store`.

```ruby
# config/environments/production.rb
  # Use a different cache store in production.
  config.cache_store = :solid_cache_store
```

`config/cache.yml` splits the options into two anchors. `default_connection` names the `cache` database from `database.yml`, and `default_options` sets `max_age` and a namespace built from `Rails.env` plus an optional `CACHE_NAMESPACE`. The `test` entry takes only the options, with no database:

```yaml
# config/cache.yml
default_options: &default_options
  store_options:
    max_age: <%= 60.days.to_i %>
    namespace: <%= "#{Rails.env}#{"-#{ENV["CACHE_NAMESPACE"]}" if ENV["CACHE_NAMESPACE"]}" %>

default_connection: &default_connection
  database: cache

default: &default
  <<: *default_connection
  <<: *default_options

development: *default
test: *default_options
beta: *default
staging: *default
production: *default
```

Why: `max_age` bounds how long an entry lives in the cache database (Solid Cache README: https://github.com/rails/solid_cache), and the env-based namespace keeps environments sharing one database from reading each other's entries (Fizzy: `config/cache.yml`).

## Solid Cable

Solid Cable carries Action Cable messages through a database, so no Redis pub/sub is needed. Fizzy uses a single `&cable` anchor for every environment except `test`, which uses the `test` adapter. The `database` is not repeated here; `connects_to` points both writing and reading at the `cable` database from `database.yml`:

```yaml
# config/cable.yml
cable: &cable
  adapter: solid_cable
  connects_to:
    database:
      writing: cable
      reading: cable
  polling_interval: 0.1.seconds
  message_retention: 1.day

development: *cable
test:
  adapter: test
beta: *cable
staging: *cable
production: *cable
```

Why: polling a database removes the Redis dependency while keeping the Action Cable API unchanged (Solid Cable README: https://github.com/rails/solid_cable; Fizzy: `config/cable.yml`).

## Multi-Database Layout

`config/database.yml` is a one-line ERB file that loads either `config/database.sqlite.yml` or `config/database.mysql.yml` depending on `Fizzy.db_adapter`, or `saas/config/database.yml` in SaaS mode:

```yaml
# config/database.yml
<%
  config_path = if Fizzy.saas?
    gem_path = Rails.root.join("saas").to_s
    File.join(gem_path, "config", "database.yml")
  else
    File.join("config", "database.#{Fizzy.db_adapter}.yml")
  end
%>
<%= ERB.new(File.read(config_path)).result %>
```

Fizzy supports both SQLite and MySQL (the `trilogy` adapter). Both files define the same split: a `primary` database plus separate `cable`, `cache` and `queue` databases. The SQLite file keeps one file per database under `storage/`. Development and test configure only `primary` and `cable`; production adds `cache` and `queue`. The test environment uses a file, not `:memory:`:

```yaml
# config/database.sqlite.yml
default: &default
  adapter: sqlite3
  pool: 5
  timeout: 5000

development:
  primary:
    <<: *default
    database: storage/development.sqlite3
    schema_dump: schema_sqlite.rb
  cable:
    <<: *default
    database: storage/development_cable.sqlite3
    migrations_paths: db/cable_migrate
# ...
  cache:
    <<: *default
    database: storage/production_cache.sqlite3
    migrations_paths: db/cache_migrate
  queue:
    <<: *default
    database: storage/production_queue.sqlite3
    migrations_paths: db/queue_migrate
```

The Solid databases ship schema files rather than migrations in this repo: `db/cable_schema.rb`, `db/cache_schema.rb` and `db/queue_schema.rb`, plus `db/queue_migrate/`. `migrations_paths` points each connection at its own directory.

Why: separate databases keep queue and cache write traffic off the primary and let each be backed up, sized or hosted on its own (Fizzy: `saas/config/database.yml` gives cable, queue and cache each its own host variable).

## Sources

- Solid Queue: https://github.com/rails/solid_queue
- Solid Cache: https://github.com/rails/solid_cache
- Solid Cable: https://github.com/rails/solid_cable
- Fizzy files shown above, at commit 6aebc0cea
