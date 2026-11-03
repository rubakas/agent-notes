# CI, Linting & Pre-Commit Hooks

## Contents

- [Local CI](#local-ci)
- [GitHub Actions](#github-actions)
- [RuboCop Configuration](#rubocop-configuration)
- [Pre-Commit Hooks](#pre-commit-hooks)
- [Sources](#sources)

## Local CI

`bin/ci` runs the same checks as CI on your machine. It is a six-line Ruby script that loads Rails' `ActiveSupport::ContinuousIntegration` and then `config/ci.rb`:

```ruby
# bin/ci
#!/usr/bin/env ruby
require_relative "../config/boot"
require "active_support/continuous_integration"

CI = ActiveSupport::ContinuousIntegration
require_relative "../config/ci.rb"
```

The steps live in `config/ci.rb`. These ranges are copied from it:

```ruby
# config/ci.rb
CI.run do
  step "Setup", "bin/setup --skip-server"

  step "Docs: agent instructions", "script/check_agents_docs"

  step "Style: Ruby", "bin/rubocop -f simple"

  step "Gemfile: Drift check", "bin/bundle-drift check"
  step "Security: Gem audit", "bin/bundler-audit check --update"
  step "Security: Importmap audit", "bin/importmap audit"
  step "Security: Brakeman audit", "bin/brakeman --quiet --no-pager --exit-on-warn --exit-on-error"
  step "Security: Gitleaks audit", "bin/gitleaks-audit"
# ...
  if Fizzy.saas?
    step "Tests: SaaS",          "#{SAAS_ENV} bin/rails test"
    step "Tests: SaaS System",   "#{SAAS_ENV} #{SYSTEM_TEST_ENV} bin/rails test:system"
    step "Tests: OSS",           "#{OSS_ENV} bin/rails test"
    step "Tests: OSS System",    "#{OSS_ENV} #{SYSTEM_TEST_ENV} bin/rails test:system"
  else
    step "Tests: SQLite",        "#{OSS_ENV} bin/rails test"
    step "Tests: SQLite System", "#{OSS_ENV} #{SYSTEM_TEST_ENV} bin/rails test:system"
  end
```

In order: setup, a check of the agent docs, RuboCop, a drift check between `Gemfile.lock` and `Gemfile.saas.lock`, then four security audits (bundler-audit, importmap audit, Brakeman and gitleaks). After that come the tests. In SaaS mode it runs the SaaS and OSS suites; otherwise it runs the SQLite suite. System tests set `PARALLEL_WORKERS=1`, because, in the file's own words, "system tests can't run reliably in parallel". On success the last step runs `gh signoff`.

Why: one command reproduces the whole pipeline before a push (Fizzy: `config/ci.rb`).

## GitHub Actions

Fizzy pins every third-party action to a commit SHA and keeps the version in a trailing comment. The lint job in `ci-checks.yml` shows the pattern, with `ruby-version` read from `.ruby-version`. The action SHAs and versions are examples as of 2026-10; use your project's versions.

```yaml
# .github/workflows/ci-checks.yml
  lint:
    name: Lint
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: ruby/setup-ruby@95ef2b042f9d7a56d8268cba8559e2842e2ad01b # v1.321.0
        with:
          ruby-version: .ruby-version
          bundler-cache: true

      - name: Lint code for consistent style
        run: bin/rubocop

      - name: Agent docs
        run: script/check_agents_docs
```

The same file has a `zizmor` job that audits the workflows themselves. `test.yml` is a reusable workflow (`on: workflow_call` with a `saas` input) that `ci-oss.yml` and `ci-saas.yml` call. Its matrix runs every suite against both SQLite and MySQL:

```yaml
# .github/workflows/test.yml
    strategy:
      matrix:
        include:
          - mode: SQLite
            db_adapter: sqlite
          - mode: MySQL
            db_adapter: mysql
# ...
      - name: Run tests
        run: bin/rails db:setup test

      - name: Run system tests
        run: bin/rails test:system
```

Why: a commit SHA cannot be repointed the way a tag can, and the `zizmor` job checks the workflow files for unsafe patterns (Fizzy: `.github/workflows/ci-checks.yml`).

## RuboCop Configuration

CI runs `bin/rubocop`, and the pre-commit hook runs `bin/rubocop --force-exclusion`. Migrations and schema files are excluded in `.rubocop.yml`:

```yaml
# .rubocop.yml
AllCops:
  Exclude:
    - 'db/migrate/**/*'
    - 'db/schema*.rb'
    - 'saas/db/migrate/**/*'
    - 'saas/db/saas_schema.rb'
```

`--force-exclusion` makes RuboCop apply those exclusions even when files are named on the command line, which is how a hook calls it. Omakase 1.1.0 enables neither `Style/GuardClause` nor `Layout/IndentationConsistency`, so conditional style and `private` indentation are left to the project.

Why: without `--force-exclusion`, a file passed explicitly is linted even if it is excluded (RuboCop docs: https://docs.rubocop.org/rubocop/configuration.html).

## Pre-Commit Hooks

Fizzy keeps its hooks in `.githooks/` and registers the directory in `bin/setup`:

```bash
# bin/setup
step "Installing Git pre-commit hooks" git config core.hooksPath .githooks
```

The hook script is long because most of it finds a working `mise` and puts the project's toolchain on `PATH`; the line that does the work is the last one, which runs `prek` (a pre-commit runner):

```bash
# .githooks/pre-commit
exec "$mise" exec -- prek run
```

`prek.toml` says what runs. The local RuboCop hook runs on Ruby files, and the built-in hooks check for merge conflicts, case conflicts, large added files and private keys:

```yaml
# prek.toml
[[repos]]
repo = "local"
hooks = [
  { id = "rubocop", name = "rubocop", language = "system", entry = "bin/rubocop --force-exclusion", types = ["ruby"] },
]

[[repos]]
repo = "builtin"
hooks = [
  { id = "check-merge-conflict" },
  { id = "check-case-conflict" },
  { id = "check-added-large-files" },
  { id = "detect-private-key" },
]
```

Why: the hook's comment says the wrong toolchain is "the single outcome this hook exists to prevent", so the script resolves `mise` itself rather than trusting the caller's `PATH` (Fizzy: `.githooks/pre-commit`).

## Sources

- Fizzy `config/ci.rb`, `.github/workflows/`, `.rubocop.yml`, `.githooks/pre-commit`, `prek.toml` and `bin/setup`, at commit 6aebc0cea
- RuboCop: https://docs.rubocop.org/
- GitHub Actions: https://docs.github.com/en/actions
