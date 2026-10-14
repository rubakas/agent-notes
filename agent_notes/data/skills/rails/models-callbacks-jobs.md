# Callbacks and Async Jobs

## Contents

- [Callback Policy](#callback-policy)
- [Callback Patterns](#callback-patterns)
- [Transaction Safety](#transaction-safety)
- [Async Jobs with `_later` Suffix](#async-jobs-with-_later-suffix)
- [Sources](#sources)

## Callback Policy

Rails callbacks run at fixed lifecycle points (before/after create, update, save, commit, destroy). Fizzy follows three rules:

1. **Same-database writes that belong with the parent**: use `after_create` (inside the transaction), so the sibling record is written atomically with the parent.
2. **Async or external work**: use `after_*_commit`, so the job or broadcast runs only once the data is committed.
3. **Conditional execution**: use `if:` with a method predicate or a lambda.

`Event` shows rules 1 and 2 side by side:

```ruby
# app/models/event.rb
after_create -> { eventable.event_was_created(self) }
after_create_commit :dispatch_webhooks
# ...
private
  def dispatch_webhooks
    Event::WebhookDispatchJob.perform_later(self)
  end
```

Why: an `after_create` write rolls back with the parent, while a job enqueued from `after_*_commit` can only run on committed rows (Fizzy: `app/models/event.rb`).

## Callback Patterns

### Conditional callbacks

```ruby
# app/models/card.rb
before_save :set_default_title, if: :published?
before_create :assign_number

after_save   -> { board.touch }, if: :published?
after_touch  -> { board.touch }, if: :published?
after_update :handle_board_change, if: :saved_change_to_board_id?
```

A condition can name a method (`if: :published?`) or be a lambda (`after_save -> { board.touch }`). Fizzy uses lambdas for one-line bodies and named methods when the body needs its own name.

Why: a named predicate reads as a sentence and can be reused (Fizzy: `app/models/card.rb`).

### Remember a change in `before_update`

```ruby
# app/models/card/broadcastable.rb
before_update :remember_if_preview_changed
# ...
private
  def remember_if_preview_changed
    @preview_changed ||= title_changed? || column_id_changed? || board_id_changed?
  end

  def preview_changed?
    @preview_changed
  end
```

`Card::Pinnable` then declares `after_update_commit :broadcast_pin_updates_later, if: :preview_changed?`. The flag is computed in `before_update`, where `title_changed?` and friends still answer, and read in the after-commit callback, where the changes have already been applied.

Why: the dirty-tracking predicates are reset once the save finishes, so the answer is recorded while it is still available (Fizzy: `app/models/card/broadcastable.rb`).

### No after_rollback

Fizzy has no `after_rollback` callbacks. A rolled-back transaction fires no `after_commit` callback, so nothing was broadcast or enqueued and there is nothing to undo.

Why: with work hung off `after_*_commit`, a rollback leaves no side effects to clean up (Fizzy: `app/models/card/pinnable.rb`).

## Transaction Safety

### Use `transaction` for multi-step operations

```ruby
# app/models/card/closeable.rb
def close(user: Current.user)
  unless closed?
    transaction do
      not_now&.destroy
      create_closure! user: user
      track_event :closed, creator: user
    end
  end
end
```

Wrap multi-step model changes in `transaction do ... end`. The not-now record is destroyed, the closure is created and the event is tracked together or not at all; `after_*_commit` callbacks fire only if the transaction succeeds.

Why: a failure part-way rolls back every step, so a card is never half closed (Fizzy: `app/models/card/closeable.rb`).

### Use with_lock for read-modify-write

```ruby
# app/models/card.rb
def assign_number
  self.number ||= account.with_lock { account.increment!(:cards_count).cards_count }
end
```

`with_lock` opens a transaction and takes a row lock on the account, so two concurrent saves cannot read the same `cards_count`. The unique index on `[account_id, number]` is the backstop.

Why: a counter that is read and then written back needs the lock to be race-free (Fizzy: `app/models/card.rb`).

### Conditional style

Follow the project's RuboCop config (`.rubocop.yml`). Fizzy uses `rubocop-rails-omakase`, which enforces neither style. When the project has no rule, the 37signals default (STYLE.md) is expanded conditionals, with a guard clause only at the very top of a method. See the `code-style.md` reference.

`Card::Closeable#close`, shown above, wraps its body in `unless closed?` rather than opening with `return if closed?`. STYLE.md allows a guard clause "right at the beginning of the method" when "the main method body is not trivial and involves several lines of code".

Why: "In general, we prefer to use expanded conditionals over guard clauses." (STYLE.md)

## Async Jobs with `_later` Suffix

### The _later pattern

A `x_later` method enqueues a job, and the job calls the unsuffixed method that does the work:

```ruby
# app/models/card/pinnable.rb
included do
  has_many :pins, dependent: :destroy

  after_update_commit :broadcast_pin_updates_later, if: :preview_changed?
end
# ...
private
  def broadcast_pin_updates_later
    Card::BroadcastPinUpdatesJob.perform_later(self)
  end
```

The job is shallow and delegates to the model:

```ruby
# app/jobs/card/broadcast_pin_updates_job.rb
class Card::BroadcastPinUpdatesJob < ApplicationJob
  discard_on ActiveJob::DeserializationError

  def perform(card)
    card.broadcast_pin_updates
  end
end
```

Here `broadcast_pin_updates_later` is private; `Webhook::Delivery#deliver_later` and `Export#build_later` are public. `discard_on ActiveJob::DeserializationError` drops the job when the record is gone before it runs. The account context is restored for every job by `AccountTenanted`; see multi-tenancy.md.

Why: "we write shallow job classes that delegate the logic itself to domain models" (STYLE.md "Run async operations in jobs")

### Fizzy leaves the synchronous method unsuffixed

STYLE.md says "we use the suffix `_now` for the regular synchronous method" (its example is `relay_now`). Fizzy's code does not: the synchronous methods are `broadcast_pin_updates`, `Webhook::Delivery#deliver` and `Export#build`. Follow the names the project already uses, and do not add `*_now` methods to a codebase that has none.

Why: STYLE.md and the code disagree, and the code is what a contributor will find next to the change (STYLE.md "Run async operations in jobs"; Fizzy: `app/models/webhook/delivery.rb`).

### Enqueue after transaction commit

`config/initializers/active_job.rb` sets `self.enqueue_after_transaction_commit = true` inside `ActiveSupport.on_load(:active_job)`; jobs.md shows the excerpt. Fizzy sets it explicitly for every Active Job class, so a job enqueued inside a transaction waits for the commit. Set it in the application's own initializer rather than assuming it is on.

Why: the job can then always read the row that triggered it (Fizzy: `config/initializers/active_job.rb`).

## Sources

- Fizzy: `app/models/event.rb`, `app/models/card.rb`, `app/models/card/broadcastable.rb`, `app/models/card/closeable.rb`
- Fizzy: `app/models/card/pinnable.rb`, `app/jobs/card/broadcast_pin_updates_job.rb`, `app/models/webhook/delivery.rb`, `app/models/export.rb`
- Fizzy: `config/initializers/active_job.rb`
- STYLE.md "Run async operations in jobs", "Conditional returns"
