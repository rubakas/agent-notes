# Code Style Guide

Comprehensive guide for Rails code style and conventions.

> **Note**: This guide represents opinionated coding style based on Basecamp/37signals practices. While strongly aligned with Rails philosophy and conventions, some preferences (such as favoring expanded conditionals over guard clauses, and the `_later`/`_now` naming pattern) differ from broader Rails community norms. These are battle-tested patterns from production codebases, not universal standards. Adapt these guidelines to match your team's preferences and project needs.

---

## Philosophy

Write code that is a pleasure to read. Code style matters because:
- **Readability** - Code is read more often than written
- **Consistency** - Predictable patterns reduce cognitive load
- **Maintainability** - Clear code is easier to modify
- **Collaboration** - Shared conventions improve team velocity

---

## Conditional Returns

### Prefer Expanded Conditionals

**Prefer expanded if/else over guard clauses:**

```ruby
# ❌ Bad - Guard clause
def todos_for_new_group
  ids = params.require(:todolist)[:todo_ids]
  return [] unless ids
  @bucket.recordings.todos.find(ids.split(","))
end

# ✅ Good - Expanded conditional
def todos_for_new_group
  if ids = params.require(:todolist)[:todo_ids]
    @bucket.recordings.todos.find(ids.split(","))
  else
    []
  end
end
```

**Why:** Guard clauses can be hard to read, especially when nested.

### Exception: Early Returns

Guard clauses are acceptable when:
1. The return is right at the beginning of the method
2. The main method body is non-trivial (several lines)

```ruby
# ✅ Acceptable - Early return for clarity
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

## Methods Ordering

### Class-Level Organization

Order methods in classes:

1. **Class methods**
2. **Public methods** (with `initialize` first if present)
3. **Private methods**

```ruby
class Card < ApplicationRecord
  # 1. Class methods
  def self.find_stale
    where(last_active_at: ..1.month.ago)
  end

  # 2. Public methods
  def initialize(*args)
    super
    @initialized = true
  end

  def close
    create_closure!
  end

  def reopen
    closure.destroy
  end

  # 3. Private methods
  private
    def validate_state
      # ...
    end
end
```

### Invocation Order (Vertical Reading)

Order methods based on their invocation order. This helps understand code flow:

```ruby
class SomeClass
  def process
    step_one
    step_two
  end

  private
    # Step one and its sub-methods
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

    # Step two and its sub-methods
    def step_two
      step_two_a
      step_two_b
    end

    def step_two_a
      # Implementation
    end

    def step_two_b
      # Implementation
    end
end
```

**Why:** Reading top-to-bottom mirrors execution flow.

---

## Bang Methods (!)

### Only Use ! When Non-Bang Version Exists

**Rule:** Only use `!` for methods that have a corresponding version without `!`.

```ruby
# ✅ Good - Has save counterpart
def save!
  raise unless save
end

# ❌ Bad - No close counterpart
def close!
  create_closure!
end

# ✅ Good - Just use close
def close
  create_closure!
end
```

**Why:** We don't use `!` to flag destructive actions. Many destructive methods in Ruby and Rails don't end with `!` (`destroy`, `delete`, `update`, etc.).

**Examples of correct usage:**
- `save` / `save!`
- `create` / `create!`
- `update` / `update!`
- `destroy` / `destroy!`

---

## Visibility Modifiers

### No Newline Under Modifier, Indent Content

```ruby
# ✅ Good
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
```

```ruby
# ❌ Bad - Extra newline, no indentation
class SomeClass
  def public_method
  end

  private

  def private_method
  end
end
```

### Module with Only Private Methods

If a module has only private methods, mark `private` at the top with an extra newline but don't indent:

```ruby
# ✅ Good - Module with only private methods
module SomeModule
  private

  def some_private_method
    # Implementation
  end

  def another_private_method
    # Implementation
  end
end
```

---

## CRUD Controllers

### Model Actions as Resources

Model web endpoints as CRUD operations on resources (REST). When an action doesn't map to a standard CRUD verb, introduce a new resource:

```ruby
# ❌ Bad - Custom actions
resources :cards do
  post :close
  post :reopen
  post :gild
end

# ✅ Good - Actions as resources
resources :cards do
  resource :closure   # POST = close, DELETE = reopen
  resource :goldness  # POST = gild, DELETE = ungild
end
```

---

## Controller and Model Interactions

### Vanilla Rails Approach

Favor thin controllers directly invoking a rich domain model. Don't use services or other artifacts to connect the two unless necessary.

### Simple Operations

Invoking plain Active Record operations is totally fine:

```ruby
# ✅ Good - Direct Active Record
class Cards::CommentsController < ApplicationController
  def create
    @comment = @card.comments.create!(comment_params)
  end
end
```

### Complex Operations

For complex behavior, prefer clear, intention-revealing model APIs:

```ruby
# ✅ Good - Intention-revealing model method
class Cards::GoldnessesController < ApplicationController
  def create
    @card.gild
  end
end

# In model
class Card < ApplicationRecord
  def gild
    transaction do
      create_goldness!
      track_event :gilded
    end
  end
end
```

### Services (When Justified)

When justified, it's fine to use services or form objects, but don't treat them as special artifacts:

```ruby
# ✅ Acceptable when complexity warrants it
class SignupsController < ApplicationController
  def create
    Signup.new(email_address: params[:email]).create_identity
  end
end
```

---

## Async Operations in Jobs

### Shallow Jobs That Delegate

Write shallow job classes that delegate logic to domain models:

**Naming convention:**
- Use `_later` suffix for methods that enqueue a job
- Use `_now` suffix for the synchronous version

```ruby
# Model concern
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

# Job delegates to model
class Event::RelayJob < ApplicationJob
  def perform(event)
    event.relay_now
  end
end
```

**Why:** Keeps jobs thin and testable. Business logic stays in models.

---

## General Code Style

### Whitespace

```ruby
# ✅ Good - One space around operators
x = 1 + 2
hash = { key: value }
array = [1, 2, 3]

# ❌ Bad
x=1+2
hash={key:value}
```

### Line Length

- Keep lines under 120 characters when possible
- Break long lines logically

```ruby
# ✅ Good - Broken at logical points
User.where(active: true)
  .where(verified: true)
  .order(created_at: :desc)

# ❌ Bad - One long line
User.where(active: true).where(verified: true).order(created_at: :desc).limit(10).offset(20)
```

### String Literals

```ruby
# ✅ Prefer double quotes for strings
message = "Hello, world!"

# ✅ Single quotes for strings that don't need interpolation or escaping
sql = 'SELECT * FROM users WHERE id = ?'
```

### Hash Syntax

```ruby
# ✅ Good - New hash syntax for symbol keys
user = { name: "Alice", email: "alice@example.com" }

# ✅ Old syntax when keys are not symbols
config = { "Content-Type" => "application/json" }
```

---

## Code Organization Principles

### 1. Extract Complex Conditionals

```ruby
# ❌ Bad - Complex inline conditional
if user.admin? && (user.verified? || user.trusted?) && user.active?
  grant_access
end

# ✅ Good - Extracted to method
def can_access?
  user.admin? && (user.verified? || user.trusted?) && user.active?
end

if can_access?
  grant_access
end

# ✅ Even better - Method on user
if user.can_access?
  grant_access
end
```

### 2. Single Responsibility

Each method should have one clear purpose:

```ruby
# ❌ Bad - Multiple responsibilities
def process_user
  user.verify_email
  user.send_welcome_email
  user.subscribe_to_newsletter
  user.create_default_settings
end

# ✅ Good - Separate concerns
def process_user
  verify_user
  welcome_user
  setup_user_account
end

private
  def verify_user
    user.verify_email
  end

  def welcome_user
    user.send_welcome_email
  end

  def setup_user_account
    user.subscribe_to_newsletter
    user.create_default_settings
  end
```

### 3. Intention-Revealing Names

Use clear, descriptive names:

```ruby
# ❌ Bad - Unclear names
def process
  data = fetch
  x = transform(data)
  save(x)
end

# ✅ Good - Clear names
def import_users
  csv_data = fetch_csv_from_api
  user_records = parse_csv_to_users(csv_data)
  save_users_to_database(user_records)
end
```

---

## Best Practices Summary

### ✅ DO

1. **Expanded conditionals** over guard clauses (except early returns)
2. **Order methods** by invocation flow
3. **Indent under visibility modifiers** (no extra newline)
4. **Only use !** when non-bang version exists
5. **Model actions as resources** in routes
6. **Thin controllers** that delegate to models
7. **Shallow jobs** with `_later` / `_now` pattern
8. **Intention-revealing names** for methods and variables
9. **Extract complex conditionals** to methods
10. **One responsibility per method**

### ❌ DON'T

1. **Guard clauses everywhere** - Use expanded conditionals
2. **Random method order** - Follow invocation order
3. **Extra newlines after private** - Keep it clean
4. **Bang methods without counterparts** - Just use regular names
5. **Custom controller actions** - Use resources
6. **Fat controllers** - Delegate to models
7. **Business logic in jobs** - Keep jobs thin
8. **Cryptic variable names** - Be descriptive
9. **Complex inline conditionals** - Extract to methods
10. **Multiple responsibilities** - Keep focused

---

## Summary

- **Conditionals**: Expanded over guards (except early returns)
- **Methods**: Ordered by invocation, clear names
- **Visibility**: Indent under modifiers, no extra newlines
- **Bang**: Only when non-bang version exists
- **Controllers**: Thin, RESTful, resource-oriented
- **Jobs**: Shallow, delegate to models, use `_later`/`_now`
- **Organization**: Single responsibility, intention-revealing names
