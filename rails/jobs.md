# Jobs Guide

Comprehensive guide for Rails Active Job background processing.

---

## Philosophy

1. **Jobs delegate to models** - Keep jobs thin
2. **Use `_later` suffix** - Async method naming convention
3. **Idempotent when possible** - Jobs can be retried safely
4. **Error handling** - Retry on transient errors, discard on permanent
5. **Queue organization** - Different queues for different priorities

---

## File Structure

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

## Basic Job Structure

### Simple Job

```ruby
# app/jobs/notification_job.rb
class NotificationJob < ApplicationJob
  queue_as :default

  def perform(user, message)
    user.notifications.create!(message: message)
  end
end

# Enqueue
NotificationJob.perform_later(user, "Hello!")

# Enqueue with delay
NotificationJob.set(wait: 1.hour).perform_later(user, "Reminder")

# Enqueue at specific time
NotificationJob.set(wait_until: Time.current + 2.hours).perform_later(user, "Alert")
```

### Job with Options

```ruby
class DataExportJob < ApplicationJob
  queue_as :low_priority

  # Retry configuration
  retry_on Net::HTTPServerError, wait: :exponentially_longer, attempts: 5
  retry_on Timeout::Error, wait: 5.seconds, attempts: 3

  # Discard (don't retry)
  discard_on ActiveJob::DeserializationError
  discard_on ActiveRecord::RecordNotFound

  def perform(user, export_type)
    data = generate_export(user, export_type)
    user.send_export(data)
  end

  private
    def generate_export(user, type)
      # Implementation
    end
end
```

---

## Job Naming Conventions

### Model Integration Pattern

```ruby
# Model method
class Event < ApplicationRecord
  # Enqueue job
  def relay_later
    Event::RelayJob.perform_later(self)
  end

  # Synchronous version
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

# Usage
event.relay_later  # Async
event.relay_now    # Sync
```

### Callback Integration

```ruby
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

## Queue Configuration

### Define Queues

```ruby
# config/application.rb
config.active_job.queue_adapter = :solid_queue  # or :sidekiq, :resque, etc.

# Define queue priorities
config.active_job.queue_name_prefix = Rails.env
config.active_job.queue_name_delimiter = "_"
```

### Queue Organization

```ruby
class ApplicationJob < ActiveJob::Base
  # Default queue
  queue_as :default
end

class UrgentJob < ApplicationJob
  queue_as :urgent
end

class LowPriorityJob < ApplicationJob
  queue_as :low_priority
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

## Error Handling

### Retry Strategies

```ruby
class ExternalApiJob < ApplicationJob
  # Exponential backoff: 3s, 18s, 83s, 258s, ...
  retry_on Net::HTTPServerError, wait: :exponentially_longer, attempts: 5

  # Polynomial backoff: 4s, 16s, 36s, 64s, ...
  retry_on Timeout::Error, wait: :polynomially_longer, attempts: 4

  # Fixed delay
  retry_on SomeTransientError, wait: 30.seconds, attempts: 3

  # Custom wait calculation
  retry_on DatabaseError, wait: ->(executions) { executions * 10 }

  # Conditional retry
  retry_on SomeError, attempts: 3 do |job, exception|
    should_retry?(exception)
  end

  def perform(data)
    # Implementation
  end
end
```

### Discard (Don't Retry)

```ruby
class ProcessUserJob < ApplicationJob
  # Discard on permanent errors
  discard_on ActiveRecord::RecordNotFound
  discard_on ActiveJob::DeserializationError

  # Conditional discard
  discard_on CustomError do |job, exception|
    exception.message.include?("permanent")
  end

  def perform(user_id)
    user = User.find(user_id)
    process(user)
  end
end
```

### Rescue From

```ruby
class SmtpMailJob < ApplicationJob
  rescue_from Net::SMTPSyntaxError do |exception|
    case exception.message
    when /\A501 5\.1\.3/
      # Log and ignore invalid email addresses
      Rails.logger.info "Invalid email: #{exception.message}"
    else
      raise  # Re-raise for other SMTP syntax errors
    end
  end

  def perform(email_data)
    send_email(email_data)
  end
end
```

---

## Recurring Jobs

### Configuration (Solid Queue)

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

  weekly_digest:
    class: DigestJob
    schedule: "0 8 * * 1"  # Monday at 8 AM
```

### Recurring Job Pattern

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

## Job Concerns

### Error Handling Concern

```ruby
# app/jobs/concerns/smtp_delivery_error_handling.rb
module SmtpDeliveryErrorHandling
  extend ActiveSupport::Concern

  included do
    # Retry on network errors
    retry_on Net::OpenTimeout, Net::ReadTimeout, Socket::ResolutionError,
      wait: :polynomially_longer

    # Retry on temporary SMTP errors (4xx)
    retry_on Net::SMTPServerBusy, wait: :polynomially_longer

    # Handle specific SMTP errors
    rescue_from Net::SMTPSyntaxError do |error|
      case error.message
      when /\A501 5\.1\.3/
        # Ignore invalid email addresses
        Sentry.capture_exception(error, level: :info) if defined?(Sentry)
      else
        raise
      end
    end

    # Handle fatal SMTP errors (5xx)
    rescue_from Net::SMTPFatalError do |error|
      case error.message
      when /\A550 5\.1\.1/, /\A552 5\.6\.0/
        Sentry.capture_exception(error, level: :info) if defined?(Sentry)
      else
        raise
      end
    end
  end
end

# Usage
class WelcomeEmailJob < ApplicationJob
  include SmtpDeliveryErrorHandling

  def perform(user)
    UserMailer.welcome(user).deliver_now
  end
end
```

---

## Job Callbacks

### Lifecycle Callbacks

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

### Error Callbacks

```ruby
class ReportJob < ApplicationJob
  rescue_from StandardError do |exception|
    handle_error(exception)
  end

  def perform(report_id)
    generate_report(report_id)
  end

  private
    def handle_error(exception)
      ErrorNotifier.notify(exception, job: self)
      Report.find(arguments.first).mark_as_failed!
    end
end
```

---

## Testing Jobs

### Basic Job Test

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

### Testing Retry Logic

```ruby
test "retries on transient error" do
  user = users(:david)

  # Stub method to raise error
  UserMailer.stub(:welcome, -> { raise Net::HTTPServerError }) do
    assert_enqueued_jobs 2 do  # Original + 1 retry
      perform_enqueued_jobs do
        WelcomeEmailJob.perform_later(user)
      rescue Net::HTTPServerError
        # Expected to raise after retries
      end
    end
  end
end

test "discards on permanent error" do
  assert_no_enqueued_jobs do
    perform_enqueued_jobs do
      ProcessUserJob.perform_later(999999)  # Non-existent ID
    rescue ActiveRecord::RecordNotFound
      # Job should be discarded, not retried
    end
  end
end
```

### Testing Recurring Jobs

```ruby
test "auto postpone job postpones stale cards" do
  stale_card = cards(:old)
  stale_card.update!(last_active_at: 2.months.ago)

  recent_card = cards(:new)
  recent_card.update!(last_active_at: 1.day.ago)

  Card::AutoPostponeJob.perform_now

  assert stale_card.reload.postponed?
  assert_not recent_card.reload.postponed?
end
```

---

## Advanced Patterns

### Batch Processing

```ruby
class BatchImportJob < ApplicationJob
  def perform(file_path)
    CSV.foreach(file_path, headers: true).each_slice(100) do |batch|
      batch.each do |row|
        ImportRowJob.perform_later(row.to_h)
      end
    end
  end
end
```

### Progress Tracking

```ruby
class LongRunningJob < ApplicationJob
  def perform(total_items)
    total_items.times do |i|
      process_item(i)
      update_progress(i + 1, total_items)
    end
  end

  private
    def update_progress(current, total)
      percentage = (current.to_f / total * 100).round
      Rails.cache.write("job:#{job_id}:progress", percentage)
    end
end

# Check progress
progress = Rails.cache.read("job:#{job_id}:progress")
```

### Job Chaining

```ruby
class ProcessDataJob < ApplicationJob
  def perform(data_id)
    data = Data.find(data_id)
    data.process!

    # Enqueue next job after completion
    GenerateReportJob.set(wait: 5.minutes).perform_later(data_id)
  end
end
```

### Unique Jobs

```ruby
class UniqueProcessJob < ApplicationJob
  def perform(user_id)
    # Use lock to prevent duplicate jobs
    lock_key = "unique_job:#{user_id}"

    Rails.cache.fetch(lock_key, expires_in: 1.hour, race_condition_ttl: 10.seconds) do
      process_user(user_id)
      true
    end
  end
end
```

---

## Monitoring & Debugging

### Job Callbacks for Monitoring

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

### Job Inspection

```ruby
# In console
job = NotificationJob.new(user, "test")
job.serialize  # => Hash representation
job.queue_name # => "default"
job.priority   # => nil
job.scheduled_at # => Time
```

---

## Best Practices

### ✅ DO

1. **Keep jobs simple**
```ruby
# Good - delegates to model
class ProcessCardJob < ApplicationJob
  def perform(card)
    card.process
  end
end
```

2. **Use `_later` suffix**
```ruby
# Model
def send_notifications_later
  NotificationJob.perform_later(self)
end

def send_notifications_now
  # Implementation
end
```

3. **Make jobs idempotent**
```ruby
def perform(user_id)
  user = User.find(user_id)

  # Idempotent - can run multiple times safely
  user.update(processed: true) unless user.processed?
end
```

4. **Use appropriate queues**
```ruby
class UrgentJob < ApplicationJob
  queue_as :urgent
end

class ReportJob < ApplicationJob
  queue_as :low_priority
end
```

5. **Handle errors appropriately**
```ruby
retry_on TransientError, wait: :exponentially_longer
discard_on PermanentError
```

### ❌ DON'T

1. **Complex business logic in jobs**
```ruby
# Bad - too much logic
class ProcessJob < ApplicationJob
  def perform(data)
    # 100 lines of business logic
  end
end

# Good - delegate to model
class ProcessJob < ApplicationJob
  def perform(model)
    model.process
  end
end
```

2. **Long-running jobs without batching**
```ruby
# Bad - processes everything at once
def perform
  User.all.each { |user| process(user) }
end

# Good - batch processing
def perform
  User.find_in_batches(batch_size: 100) do |batch|
    batch.each { |user| ProcessUserJob.perform_later(user) }
  end
end
```

3. **Ignoring job failures**
```ruby
# Bad - swallows all errors
def perform(data)
  process(data)
rescue => e
  # Silent failure
end

# Good - let errors bubble up for retry logic
def perform(data)
  process(data)
end
```

---

## Summary

- **Purpose**: Background processing, async tasks
- **Delegation**: Jobs delegate to models, keep thin
- **Naming**: Use `_later` suffix for async methods
- **Queues**: Organize by priority and type
- **Error Handling**: Retry transient errors, discard permanent
- **Testing**: Test enqueuing, performing, and error handling
- **Monitoring**: Track job performance and failures
- **Idempotency**: Make jobs safe to retry
