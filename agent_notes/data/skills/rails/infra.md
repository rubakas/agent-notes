# Infrastructure

## Active Job

Comprehensive guide for Rails Active Job background processing.

---

### Philosophy

1. **Jobs delegate to models** - Keep jobs thin
2. **Use `_later` suffix** - Async method naming convention
3. **Idempotent when possible** - Jobs can be retried safely
4. **Error handling** - Retry on transient errors, discard on permanent
5. **Queue organization** - Different queues for different priorities

---

### File Structure

```
app/jobs/
├── application_job.rb
├── notification/
│   └── bundle/
│       └── deliver_job.rb
├── event/
│   ├── relay_job.rb
│   └── webhook_dispatch_job.rb
└── card/
    └── auto_postpone_job.rb
```

---

### Basic Job Structure

```ruby
# Simple Job
class NotificationJob < ApplicationJob
  queue_as :default

  def perform(user, message)
    user.notifications.create!(message: message)
  end
end

NotificationJob.perform_later(user, "Hello!")
NotificationJob.set(wait: 1.hour).perform_later(user, "Reminder")
NotificationJob.set(wait_until: Time.current + 2.hours).perform_later(user, "Alert")

# Job with Options
class DataExportJob < ApplicationJob
  queue_as :low_priority

  retry_on Net::HTTPServerError, wait: :exponentially_longer, attempts: 5
  retry_on Timeout::Error, wait: 5.seconds, attempts: 3

  discard_on ActiveJob::DeserializationError
  discard_on ActiveRecord::RecordNotFound

  def perform(user, export_type)
    data = generate_export(user, export_type)
    user.send_export(data)
  end
end
```

---

### Model Integration Pattern

```ruby
# Model method
class Event < ApplicationRecord
  def relay_later
    Event::RelayJob.perform_later(self)
  end

  def relay_now
    webhooks.active.each do |webhook|
      webhook.trigger(self)
    end
  end
end

# Job delegates to model
class Event::RelayJob < ApplicationJob
  queue_as :webhooks

  def perform(event)
    event.relay_now
  end
end

# Callback Integration
module Event::Relaying
  extend ActiveSupport::Concern

  included do
    after_create_commit :relay_later
  end

  def relay_later
    Event::RelayJob.perform_later(self)
  end

  def relay_now
    # Implementation
  end
end
```

---

### Queue Configuration

```ruby
# config/application.rb
config.active_job.queue_adapter = :solid_queue  # or :sidekiq, :resque

class ApplicationJob < ActiveJob::Base
  queue_as :default
end

class ReportJob < ApplicationJob
  # Dynamic queue based on user
  queue_as do
    user = arguments.first
    user.premium? ? :premium : :default
  end
end
```

---

### Error Handling

```ruby
class ExternalApiJob < ApplicationJob
  # Exponential backoff: 3s, 18s, 83s, 258s, ...
  retry_on Net::HTTPServerError, wait: :exponentially_longer, attempts: 5

  # Polynomial backoff
  retry_on Timeout::Error, wait: :polynomially_longer, attempts: 4

  # Fixed delay
  retry_on SomeTransientError, wait: 30.seconds, attempts: 3

  # Custom wait calculation
  retry_on DatabaseError, wait: ->(executions) { executions * 10 }

  # Discard (don't retry)
  discard_on ActiveRecord::RecordNotFound
  discard_on ActiveJob::DeserializationError

  # Conditional discard
  discard_on CustomError do |job, exception|
    exception.message.include?("permanent")
  end
end

# Rescue From
class SmtpMailJob < ApplicationJob
  rescue_from Net::SMTPSyntaxError do |exception|
    case exception.message
    when /\A501 5\.1\.3/
      Rails.logger.info "Invalid email: #{exception.message}"
    else
      raise
    end
  end
end
```

---

### Recurring Jobs (Solid Queue)

```yaml
# config/recurring.yml
production:
  deliver_notifications:
    class: Notification::Bundle::DeliverJob
    schedule: "*/30 * * * *"  # Every 30 minutes

  auto_postpone_cards:
    class: Card::AutoPostponeJob
    schedule: "0 * * * *"  # Every hour

  cleanup_old_sessions:
    class: Session::CleanupJob
    schedule: "0 2 * * *"  # Daily at 2 AM
```

```ruby
class Card::AutoPostponeJob < ApplicationJob
  queue_as :maintenance

  def perform
    Card.stale.find_each do |card|
      card.postpone
    end
  end
end
```

---

### Job Callbacks

```ruby
class DataProcessingJob < ApplicationJob
  before_perform :log_start
  around_perform :measure_time
  after_perform :log_completion

  def perform(data)
    process(data)
  end

  private
    def log_start
      Rails.logger.info "Starting job: #{job_id}"
    end

    def measure_time
      start_time = Time.current
      yield
      duration = Time.current - start_time
      Rails.logger.info "Job completed in #{duration}s"
    end

    def log_completion
      Rails.logger.info "Job completed: #{job_id}"
    end
end
```

---

### Advanced Patterns

```ruby
# Batch Processing
class BatchImportJob < ApplicationJob
  def perform(file_path)
    CSV.foreach(file_path, headers: true).each_slice(100) do |batch|
      batch.each do |row|
        ImportRowJob.perform_later(row.to_h)
      end
    end
  end
end

# Progress Tracking
class LongRunningJob < ApplicationJob
  def perform(total_items)
    total_items.times do |i|
      process_item(i)
      Rails.cache.write("job:#{job_id}:progress", ((i + 1).to_f / total_items * 100).round)
    end
  end
end

# Job Chaining
class ProcessDataJob < ApplicationJob
  def perform(data_id)
    data = Data.find(data_id)
    data.process!
    GenerateReportJob.set(wait: 5.minutes).perform_later(data_id)
  end
end

# Unique Jobs
class UniqueProcessJob < ApplicationJob
  def perform(user_id)
    lock_key = "unique_job:#{user_id}"

    Rails.cache.fetch(lock_key, expires_in: 1.hour, race_condition_ttl: 10.seconds) do
      process_user(user_id)
      true
    end
  end
end
```

---

### Monitoring

```ruby
class ApplicationJob < ActiveJob::Base
  around_perform do |job, block|
    start_time = Time.current
    block.call
    duration = Time.current - start_time
    Metrics.record("job.duration", duration, tags: { job: job.class.name })
  end

  rescue_from StandardError do |exception|
    Metrics.increment("job.error", tags: { job: self.class.name })
    ErrorTracker.notify(exception, job_id: job_id, arguments: arguments)
    raise
  end
end
```

---

### Testing Jobs

```ruby
class NotificationJobTest < ActiveJob::TestCase
  test "enqueues job" do
    assert_enqueued_with(job: NotificationJob, args: [users(:david), "test"]) do
      NotificationJob.perform_later(users(:david), "test")
    end
  end

  test "performs job" do
    user = users(:david)

    assert_difference -> { user.notifications.count }, +1 do
      NotificationJob.perform_now(user, "test message")
    end
  end

  test "job is enqueued on correct queue" do
    assert_enqueued_with(job: NotificationJob, queue: "default") do
      NotificationJob.perform_later(users(:david), "test")
    end
  end
end
```

---

## Action Mailer

Comprehensive guide for Rails Action Mailer.

---

### Philosophy

1. **Mailers are like controllers** - Thin, delegate to models
2. **Preview mailers in development** - Use mailer previews
3. **Test email delivery** - Test content, not delivery mechanism
4. **Layouts for consistency** - DRY up email HTML
5. **Plain text + HTML** - Always provide both formats

---

### File Structure

```
app/mailers/
├── application_mailer.rb
├── user_mailer.rb
└── notification_mailer.rb

app/views/
├── layouts/
│   └── mailer.html.erb
└── user_mailer/
    ├── welcome.html.erb
    └── welcome.text.erb
```

---

### Application Mailer

```ruby
class ApplicationMailer < ActionMailer::Base
  default from: ENV.fetch("MAILER_FROM_ADDRESS", "App <noreply@example.com>")

  layout "mailer"

  helper ApplicationHelper, UsersHelper

  private
    def default_url_options
      if Current.account
        super.merge(script_name: Current.account.slug)
      else
        super
      end
    end
end
```

---

### Simple Mailer

```ruby
class UserMailer < ApplicationMailer
  def welcome(user)
    @user = user
    @login_url = new_session_url

    mail to: @user.email, subject: "Welcome to #{app_name}!"
  end

  def password_reset(user, token)
    @user = user
    @token = token
    @reset_url = edit_password_url(token: @token)

    mail to: @user.email, subject: "Reset your password"
  end

  def invoice(user, invoice)
    @user = user
    @invoice = invoice

    attachments["invoice-#{@invoice.id}.pdf"] = @invoice.to_pdf
    attachments.inline["logo.png"] = File.read(Rails.root.join("app/assets/images/logo.png"))

    mail to: @user.email, subject: "Invoice ##{@invoice.id}"
  end
end
```

---

### Templates

```erb
<%# app/views/user_mailer/welcome.html.erb %>
<h1>Welcome, <%= @user.name %>!</h1>
<p>Thanks for signing up. We're excited to have you on board.</p>
<p><%= link_to "Get Started", @login_url, class: "button" %></p>
```

```erb
<%# app/views/user_mailer/welcome.text.erb %>
Welcome, <%= @user.name %>!

Thanks for signing up. We're excited to have you on board.

Get started: <%= @login_url %>
```

---

### Mailer Layout

```erb
<%# app/views/layouts/mailer.html.erb %>
<!DOCTYPE html>
<html>
  <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <style>
      body { font-family: Arial, sans-serif; line-height: 1.6; }
      .button { background: #007bff; color: white; padding: 10px 20px; text-decoration: none; }
    </style>
  </head>
  <body>
    <%= yield %>
    <hr>
    <p style="font-size: 12px; color: #666;">
      You're receiving this email because you have an account at My App.
    </p>
  </body>
</html>
```

---

### Sending Emails

```ruby
# Immediate
UserMailer.welcome(user).deliver_now

# Background
UserMailer.welcome(user).deliver_later
UserMailer.welcome(user).deliver_later(wait: 1.hour)
UserMailer.welcome(user).deliver_later(wait_until: Time.current + 2.hours)

# From Models
class User < ApplicationRecord
  after_create :send_welcome_email

  private
    def send_welcome_email
      UserMailer.welcome(self).deliver_later
    end
end
```

---

### Mailer Previews

```ruby
# test/mailers/previews/user_mailer_preview.rb
class UserMailerPreview < ActionMailer::Preview
  def welcome
    UserMailer.welcome(User.first)
  end

  def password_reset
    user = User.first
    token = "sample-token-123"
    UserMailer.password_reset(user, token)
  end
end

# Visit: http://localhost:3000/rails/mailers
```

---

### Testing Mailers

```ruby
class UserMailerTest < ActionMailer::TestCase
  test "welcome email" do
    user = users(:david)

    email = UserMailer.welcome(user)

    assert_emails 1 do
      email.deliver_now
    end

    assert_equal [user.email], email.to
    assert_equal "Welcome to My App!", email.subject
    assert_match user.name, email.body.encoded

    assert_equal 2, email.parts.size
    assert_equal "text/plain", email.text_part.content_type
    assert_equal "text/html", email.html_part.content_type
  end
end
```

---

## Kamal

Deploy web apps anywhere with zero-downtime deployments using Docker.

---

### Overview

**Kamal** = Default deployment tool for Rails 8.

- Zero-downtime deployments via Traefik proxy
- Deploy anywhere (VPS, bare metal, cloud)
- Remote builds, asset bridging
- Accessory management (databases, Redis)

**Source**: [Kamal Documentation](https://kamal-deploy.org/)

---

### Installation

```bash
# Rails 8+ (Pre-installed)
rails new myapp
cd myapp
# config/deploy.yml already exists

# Manual
gem install kamal
kamal init
```

---

### Configuration

```yaml
# config/deploy.yml (minimal)
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

```yaml
# Production configuration
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

---

### Accessories

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

  redis:
    image: redis:7-alpine
    host: 192.168.0.11
    port: "6379:6379"
    cmd: redis-server --appendonly yes
    directories:
      - data:/data
```

**Important**: Accessories do **not** have zero-downtime deployments. Managed separately.

---

### Commands

```bash
kamal setup
kamal deploy
kamal deploy -d staging
kamal deploy -d production

kamal app restart
kamal app logs -f
kamal app exec 'bin/rails console'
kamal app exec 'bin/rails db:migrate'

kamal accessory boot all
kamal accessory boot db
kamal accessory reboot redis
kamal accessory logs db

kamal prune -y
kamal server containers
```

---

### Destinations (Staging/Production)

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

### Secrets Management

```bash
# .kamal/secrets
KAMAL_REGISTRY_PASSWORD=your-password
RAILS_MASTER_KEY=your-key
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://host:6379
```

**Important**: Add `.kamal/secrets*` to `.gitignore`!

---

### Hooks

```bash
.kamal/hooks/
├── pre-deploy          # Before deploy
├── post-deploy         # After deploy
└── pre-traefik-reboot  # Before proxy restart
```

```bash
#!/bin/bash
# .kamal/hooks/pre-deploy
kamal app exec 'bin/rails db:migrate'
```

Make executable: `chmod +x .kamal/hooks/*`

---

### Best Practices

- Use destinations for staging/production separation
- Configure health checks (`/up`)
- Set retention limits for containers and images
- Run accessories on separate hosts
- Use pre-deploy hooks for migrations
- Never use `:latest` tag in production
- Never commit secrets to git

---

## Initializers

Guide for Rails configuration and boot-time setup.

---

### File Structure

```
config/initializers/
├── extensions.rb          # Load lib/ extensions
├── assets.rb
├── filter_parameter_logging.rb
├── inflections.rb
└── cors.rb
```

---

### Common Initializers

```ruby
# config/initializers/extensions.rb
Dir["#{Rails.root}/lib/rails_ext/*"].each { |path|
  require "rails_ext/#{File.basename(path)}"
}

# config/initializers/filter_parameter_logging.rb
Rails.application.config.filter_parameters += [
  :passw, :secret, :token, :_key, :crypt, :salt, :certificate
]

# config/initializers/cors.rb
Rails.application.config.middleware.insert_before 0, Rack::Cors do
  allow do
    origins "example.com"
    resource "*", headers: :any, methods: [:get, :post, :put, :delete, :options]
  end
end

# config/initializers/app_config.rb
Rails.application.config.x.api_key = ENV["API_KEY"]
Rails.application.config.x.feature_flags = {
  new_dashboard: true,
  experimental_feature: false
}

# Usage
Rails.configuration.x.api_key
```

---

## Lib (Custom Libraries & Extensions)

Guide for custom libraries and Rails extensions.

---

### File Structure

```
lib/
├── my_app.rb               # Main library
├── rails_ext/              # Rails extensions
│   ├── string.rb
│   ├── prepend_order.rb
│   └── active_record_date_arithmetic.rb
├── services/               # Custom services (if used)
│   └── payment_processor.rb
└── tasks/                  # Rake tasks
    └── maintenance.rake
```

---

### Rails Extensions

```ruby
# lib/rails_ext/prepend_order.rb
module ActiveRecordRelationPrependOrder
  extend ActiveSupport::Concern

  included do
    def prepend_order(*args)
      new_orders = args.flatten.map { |arg| arg.is_a?(String) ? arg : arg.to_sql }

      spawn.tap do |relation|
        relation.order_values = new_orders + order_values
      end
    end
  end
end

ActiveRecord::Relation.include(ActiveRecordRelationPrependOrder)
ActiveRecord::AssociationRelation.include(ActiveRecordRelationPrependOrder)
```

---

### Custom Libraries

```ruby
# lib/my_app.rb
module MyApp
  class << self
    def version
      @version ||= File.read(Rails.root.join("VERSION")).strip
    end

    def config
      @config ||= Config.new
    end
  end

  class Config
    attr_accessor :feature_flag

    def initialize
      @feature_flag = false
    end
  end
end
```

---

## Rails Code Style

Comprehensive guide for Rails code style and conventions.

> **Note**: This guide represents opinionated coding style based on Basecamp/37signals practices. Some preferences differ from broader Rails community norms. Adapt to match your team's preferences.

---

### Conditional Returns

```ruby
# Prefer expanded if/else over guard clauses

# BAD - Guard clause
def todos_for_new_group
  ids = params.require(:todolist)[:todo_ids]
  return [] unless ids
  @bucket.recordings.todos.find(ids.split(","))
end

# GOOD - Expanded conditional
def todos_for_new_group
  if ids = params.require(:todolist)[:todo_ids]
    @bucket.recordings.todos.find(ids.split(","))
  else
    []
  end
end

# Exception: Early returns at top of method
def after_recorded_as_commit(recording)
  return if recording.parent.was_created?

  if recording.was_created?
    broadcast_new_column(recording)
  else
    broadcast_column_change(recording)
  end
end
```

---

### Methods Ordering

Order methods by invocation flow (vertical reading helps understand code):

```ruby
class SomeClass
  def process
    step_one
    step_two
  end

  private
    def step_one
      step_one_a
      step_one_b
    end

    def step_one_a
      # Implementation
    end

    def step_one_b
      # Implementation
    end

    def step_two
      # Implementation
    end
end
```

---

### Bang Methods (!)

Only use `!` when non-bang version exists:

```ruby
# GOOD - Has save counterpart
def save!
  raise unless save
end

# BAD - No close counterpart
def close!   # Just use close
  create_closure!
end

# GOOD
def close
  create_closure!
end
```

---

### Visibility Modifiers

```ruby
# GOOD - no newline under modifier, indent content
class SomeClass
  def public_method
    # Implementation
  end

  private
    def private_method_1
      # Implementation
    end

    def private_method_2
      # Implementation
    end
end

# Module with only private methods: mark private at top with extra newline, no indent
module SomeModule
  private

  def some_private_method
    # Implementation
  end
end
```

---

### Async Operations in Jobs

```ruby
# Naming convention: _later for async, _now for synchronous

module Event::Relaying
  extend ActiveSupport::Concern

  included do
    after_create_commit :relay_later
  end

  def relay_later
    Event::RelayJob.perform_later(self)
  end

  def relay_now
    webhooks.active.each { |webhook| webhook.trigger(self) }
  end
end

class Event::RelayJob < ApplicationJob
  def perform(event)
    event.relay_now
  end
end
```

---

### Code Organization Principles

```ruby
# Extract complex conditionals
if user.can_access?
  grant_access
end

# Single responsibility
def process_user
  verify_user
  welcome_user
  setup_user_account
end

# Intention-revealing names
def import_users
  csv_data = fetch_csv_from_api
  user_records = parse_csv_to_users(csv_data)
  save_users_to_database(user_records)
end
```

---

### Best Practices Summary

**DO:**
- Expanded conditionals over guard clauses (except early returns)
- Order methods by invocation flow
- Indent under visibility modifiers (no extra newline)
- Only use `!` when non-bang version exists
- Model actions as resources in routes
- Thin controllers that delegate to models
- Shallow jobs with `_later` / `_now` pattern
- Intention-revealing names for methods and variables

**DON'T:**
- Guard clauses everywhere — use expanded conditionals
- Random method order — follow invocation order
- Extra newlines after `private` — keep it clean
- Bang methods without counterparts — just use regular names
- Custom controller actions — use resources
- Fat controllers — delegate to models
- Business logic in jobs — keep jobs thin
