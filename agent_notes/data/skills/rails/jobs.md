# Active Job & Solid Queue

## Contents

- [Philosophy](#philosophy)
- [File Structure](#file-structure)
- [Basic Job Structure](#basic-job-structure)
- [Model Integration Pattern](#model-integration-pattern)
- [Queue Configuration](#queue-configuration)
- [Error Handling](#error-handling)
- [Recurring Jobs](#recurring-jobs)
- [Job Tenancy](#job-tenancy)
- [Advanced Patterns](#advanced-patterns)
- [Testing Jobs](#testing-jobs)
- [Sources](#sources)

## Philosophy

1. **Thin jobs**: a job receives a record and calls one model method.
2. **`_later` flags enqueueing**: a model method ending in `_later` enqueues the job (`push_later`, `build_later`). The synchronous counterpart carries the plain name (`push`, `build`).
3. **Purpose-named queues**: queues describe the kind of work (`backend`, `webhooks`, `incineration`), not a priority.
4. **Discard jobs whose record is gone**: a job declares `discard_on ActiveJob::DeserializationError`.
5. **Tenancy rides on the job**: `AccountTenanted` serializes the account and restores it around `perform`.

STYLE.md describes the `_later` and `_now` convention:

```ruby
# STYLE.md
  def relay_later
    Event::RelayJob.perform_later(self)
  end

  def relay_now
    # ...
  end
```

STYLE.md suffixes the synchronous method with `_now`. The Fizzy code uses plain names for it: `Notification#push` and `Export#build`.

Why: the job class stays shallow and the logic is testable on the model (STYLE.md: "we write shallow job classes that delegate the logic itself to domain models").

## File Structure

```
app/jobs/
├── application_job.rb
├── data_export_job.rb
├── delete_unused_tags_job.rb
├── notify_recipients_job.rb
├── push_notification_job.rb
├── search_reindex_job.rb
├── account/        # data_import_job.rb, incinerate_due_job.rb
├── board/          # clean_inaccessible_data_job.rb
├── card/           # broadcast_pin_updates_job.rb, reindex_comments_job.rb, activity_spike/ ...
├── event/          # webhook_dispatch_job.rb
├── mention/        # create_job.rb
├── notification/   # push_job.rb, bundle/
├── storage/        # materialize_job.rb, reconcile_job.rb
├── webhook/        # delivery_job.rb
└── concerns/
    ├── account_tenanted.rb
    └── smtp_delivery_error_handling.rb
```

A job lives in the namespace of the model it works on (`Card::BroadcastPinUpdatesJob`, `Webhook::DeliveryJob`). Shared behavior goes in `app/jobs/concerns/`.

Why: the namespace shows which model owns the job (Fizzy: `app/jobs/`).

## Basic Job Structure

A job calls one method on the record it receives:

```ruby
# app/jobs/notification/push_job.rb
class Notification::PushJob < ApplicationJob
  def perform(notification)
    notification.push
  end
end
```

The model owns both the enqueue and the work. `push_later` is triggered from an `after_save_commit` callback, and `push` does the work:

```ruby
# app/models/notification/pushable.rb
module Notification::Pushable
# ...
  included do
    class_attribute :push_targets, default: []

    after_save_commit :push_later, if: :source_id_previously_changed?
  end
# ...
  def push_later
    Notification::PushJob.perform_later(self)
  end

  def push
    return unless pushable?

    self.class.push_targets.each { |target| push_to(target) }
  end
# ...
end
```

Call `perform_later` to enqueue and `perform_now` to run inline (tests, console).

Why: the callback enqueues after the commit and the job holds no logic (Fizzy: `app/models/notification/pushable.rb`).

## Model Integration Pattern

The model holds the `_later` method and the work method:

```ruby
# app/models/export.rb
class Export < ApplicationRecord
# ...
  def build_later
    DataExportJob.perform_later(self)
  end
# ...
end
```

```ruby
# app/jobs/data_export_job.rb
class DataExportJob < ApplicationJob
  queue_as :backend

  discard_on ActiveJob::DeserializationError

  def perform(export)
    export.build
  end
end
```

`build_later` enqueues `DataExportJob`, which runs `Export#build` (the work method) on the `backend` queue. Fizzy turns on enqueue-after-commit for every job class:

```ruby
# config/initializers/active_job.rb
ActiveSupport.on_load(:active_job) do
  self.enqueue_after_transaction_commit = true
end
```

Rails does not enable `enqueue_after_transaction_commit` by default in 8.1, so Fizzy sets it explicitly through `ActiveSupport.on_load(:active_job)`.

Why: a job enqueued inside a transaction can run before the commit and miss the record (Fizzy: `config/initializers/active_job.rb`).

## Queue Configuration

Production uses Solid Queue, with its tables in a separate queue database. `config/environments/production.rb` sets `queue_adapter = :solid_queue` and `connects_to`, and `config/queue.yml` configures workers and dispatchers through one `default` anchor that every environment reuses. Jobs run inside Puma through the Solid Queue plugin, except on SaaS, in local environments, or when `SOLID_QUEUE_IN_PUMA=false`; `bin/jobs` starts a separate supervisor (`SolidQueue::Cli.start(ARGV)`). The excerpts of all three files are in solid-stack.md.

Mission Control Jobs uses the app's `AdminController` as its base controller (`config/initializers/mission_control.rb`).

Why: the Puma plugin runs the Solid Queue supervisor inside the web process, so a small install needs only one process (Fizzy: `config/puma.rb`).

## Error Handling

Retry transient failures with backoff, and swallow errors that cannot succeed. The SMTP concern shows both. It retries timeouts and a busy server with `wait: :polynomially_longer`:

```ruby
# app/jobs/concerns/smtp_delivery_error_handling.rb
module SmtpDeliveryErrorHandling
# ...
  included do
    # Retry delivery to possibly-unavailable remote mailservers.
    retry_on Net::OpenTimeout, Net::ReadTimeout, Socket::ResolutionError, wait: :polynomially_longer

    # Net::SMTPServerBusy is SMTP error code 4xx, a temporary error.
    # Common one we've seen is 452 4.3.1 Insufficient system storage.
    # Patiently retry.
    retry_on Net::SMTPServerBusy, wait: :polynomially_longer
# ...
  end
end
```

A bad recipient address is not retried. The same concern rescues `Net::SMTPSyntaxError` (`501 5.1.3`) and `Net::SMTPFatalError` (`550 5.1.1`, `552 5.6.0`, `555 5.5.4`), reports them to Sentry only when `Fizzy.saas?`, and re-raises every other message.

The concern is included into Rails' mail delivery job in a `to_prepare` hook. It does not re-open the class or change its superclass:

```ruby
# lib/rails_ext/action_mailer_mail_delivery_job.rb
Rails.application.config.to_prepare do
  ActionMailer::MailDeliveryJob.include SmtpDeliveryErrorHandling
end
```

Discarding is declared per job, because `ApplicationJob` only prepends `AccountTenanted` and keeps its `retry_on` and `discard_on` suggestions commented out:

```ruby
# app/jobs/notify_recipients_job.rb
class NotifyRecipientsJob < ApplicationJob
  discard_on ActiveJob::DeserializationError

  def perform(notifiable)
    notifiable.notify_recipients
  end
end
```

Why: transient SMTP errors succeed on a later attempt, and a rejected address never will (Fizzy: `app/jobs/concerns/smtp_delivery_error_handling.rb`, `lib/rails_ext/action_mailer_mail_delivery_job.rb`).

## Recurring Jobs

Solid Queue reads `config/recurring.yml`: a mapping of task names to either a `command:` (Ruby run in the job) or a `class:` (a job class), each with a `schedule:`.

```yaml
# config/recurring.yml
production: &production
# ...
  # Application cleanup
  auto_postpone_all_due:
    command: "Card.auto_postpone_all_due"
    schedule: every hour at minute 50
  delete_unused_tags:
    class: DeleteUnusedTagsJob
    schedule: every day at 04:02
# ...
  incineration:
    class: "Account::IncinerateDueJob"
    schedule: every 8 hours at minute 16
# ...
development: *production
```

A command calls a class method on a model, such as `Card.auto_postpone_all_due` (`app/models/card/entropic.rb`). Environments share a task list through YAML anchors: `production: &production` and `development: *production`.

Why: the schedule lives in one file, and the work lives on the model (Fizzy: `config/recurring.yml`).

## Job Tenancy

`ApplicationJob` prepends `AccountTenanted`. It stores `Current.account` when the job is built, serializes the account's GlobalID into the job data, and wraps `perform` in `Current.with_account`. Jobs never set `Current.account` by hand. A job whose account no longer exists raises `ActiveJob::DeserializationError` inside `perform`, where `discard_on` can handle it (the comment in `account_tenanted.rb` says so). Jobs from gems (`ActionMailer::MailDeliveryJob`, the Turbo broadcast jobs) get the same behavior by prepending the concern in `config/initializers/active_job.rb`.

Tenancy: see multi-tenancy.md for the `AccountTenanted` excerpts and the initializer.

Why: a job runs in the account that enqueued it, whatever `Current` holds in the worker (AGENTS.md: "Background jobs serialize and restore `Current.account` themselves").

## Advanced Patterns

**Resumable jobs.** `ActiveJob::Continuable` (Rails 8.1) splits a job into steps with a cursor, so a retry resumes where the last attempt stopped:

```ruby
# app/jobs/event/webhook_dispatch_job.rb
require "active_job/continuable"
# ...
class Event::WebhookDispatchJob < ApplicationJob
  include ActiveJob::Continuable
# ...
  def perform(event)
    step :dispatch do |step|
      Webhook.active.triggered_by(event).find_each(start: step.cursor) do |webhook|
        webhook.trigger(event)
        step.advance! from: webhook.id
      end
    end
  end
end
```

Why: a retry skips the webhooks already triggered instead of starting over (Fizzy: `app/jobs/event/webhook_dispatch_job.rb`).

## Testing Jobs

Assert the enqueue on the model with `assert_enqueued_with` and `assert_enqueued_jobs`:

```ruby
# test/models/user/data_export_test.rb
class User::DataExportTest < ActiveSupport::TestCase
# ...
  test "build sends email when completed" do
    export = User::DataExport.create!(account: Current.account, user: users(:david))

    assert_enqueued_jobs 1, only: ActionMailer::MailDeliveryJob do
      export.build
    end
  end
# ...
  test "build_later enqueues DataExportJob" do
    export = User::DataExport.create!(account: Current.account, user: users(:david))

    assert_enqueued_with(job: DataExportJob, args: [ export ]) do
      export.build_later
    end
  end
# ...
end
```

Run the enqueued jobs with `perform_enqueued_jobs`, optionally limited with `only:`. `test/test_helper.rb` overrides it to clear `Current.account` while the jobs run, and its `teardown` calls `Current.clear_all`. The `testing-system-jobs-mailers.md` reference covers job tests in more detail.

Why: the enqueue test and the work test fail separately (Fizzy: `test/models/user/data_export_test.rb`).

## Sources

- Fizzy: `STYLE.md` ("Run async operations in jobs"), `AGENTS.md` ("Multi-tenancy is URL-based")
- Fizzy: `app/jobs/application_job.rb`, `app/jobs/concerns/account_tenanted.rb`, `app/jobs/concerns/smtp_delivery_error_handling.rb`, `app/jobs/notification/push_job.rb`, `app/jobs/data_export_job.rb`, `app/jobs/event/webhook_dispatch_job.rb`, `app/jobs/notify_recipients_job.rb`
- Fizzy: `app/models/notification/pushable.rb`, `app/models/export.rb`, `app/models/card/entropic.rb`
- Fizzy: `config/initializers/active_job.rb`, `config/initializers/mission_control.rb`, `config/queue.yml`, `config/recurring.yml`, `config/puma.rb`, `config/environments/production.rb`, `lib/rails_ext/action_mailer_mail_delivery_job.rb`
- Fizzy: `test/models/user/data_export_test.rb`, `test/test_helper.rb`
