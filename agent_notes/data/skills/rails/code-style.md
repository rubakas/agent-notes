# Code Style

## Contents

- [RuboCop Configuration](#rubocop-configuration)
- [Conditional Returns](#conditional-returns)
- [Methods Ordering](#methods-ordering)
- [Bang Methods](#bang-methods)
- [Visibility Modifiers](#visibility-modifiers)
- [Sources](#sources)

## RuboCop Configuration

The project's own RuboCop config (`.rubocop.yml`) and its existing code come first. Every style default below is the 37signals preference from Fizzy's `STYLE.md`, and it applies only where the project has no rule of its own.

Fizzy inherits `rubocop-rails-omakase` and adds two cops:

```yaml
# .rubocop.yml
# Omakase Ruby styling for Rails
inherit_gem: { rubocop-rails-omakase: rubocop.yml }
# ...
Style/NegatedIf:
  Enabled: true
Style/NegatedUnless:
  Enabled: true
```

Omakase 1.1.0 switches every department off (`Layout`, `Lint`, `Metrics`, `Naming`, `Style` and others) and then enables individual cops. It enables 14 `Style` cops, and `Style/GuardClause` is not among them, so RuboCop does not enforce a conditional style. It also sets `Layout/IndentationConsistency` to `Enabled: false`, with the gem's comment: "We break this rule in context, though, e.g. for private-only concerns, so we leave it disabled." So RuboCop neither requires nor forbids indenting methods under `private`. Fizzy enables `Style/NegatedIf` and `Style/NegatedUnless` on top.

Why: omakase keeps a short enforced list and leaves the rest to the team, and Fizzy's AGENTS.md calls its own instructions "defaults with reasons, not law" (rubocop-rails-omakase 1.1.0 `rubocop.yml`; Fizzy: `AGENTS.md`).

## Conditional Returns

Prefer an expanded `if`/`else` to a guard clause. STYLE.md allows a guard clause as an exception when the return is at the very beginning of the method and the main body is not trivial. Both examples are copied from STYLE.md:

```ruby
# STYLE.md
# Bad
def todos_for_new_group
  ids = params.require(:todolist)[:todo_ids]
  return [] unless ids
  @bucket.recordings.todos.find(ids.split(","))
end

# Good
def todos_for_new_group
  if ids = params.require(:todolist)[:todo_ids]
    @bucket.recordings.todos.find(ids.split(","))
  else
    []
  end
end
# ...
def after_recorded_as_commit(recording)
  return if recording.parent.was_created?

  if recording.was_created?
    broadcast_new_column(recording)
  else
    broadcast_column_change(recording)
  end
end
```

Because omakase does not enable `Style/GuardClause`, this is a convention for reviewers, not a lint. If the project's RuboCop config enables the cop, follow it.

Why: "This is because guard clauses can be hard to read, especially when they are nested." (STYLE.md)

## Methods Ordering

Order the members of a class like this:

1. `class` methods
2. `public` methods, with `initialize` at the top
3. `private` methods

Within each group, order methods by invocation order: callers above the methods they call. This class from STYLE.md shows the ordering inside the `private` section:

```ruby
# STYLE.md
class SomeClass
  def some_method
    method_1
    method_2
  end

  private
    def method_1
      method_1_1
      method_1_2
    end

    def method_1_1
      # ...
    end

    def method_1_2
      # ...
    end
# ...
end
```

Why: "We order methods vertically based on their invocation order. This helps us to understand the flow of the code." (STYLE.md)

## Bang Methods

Use `!` only when a method has a non-bang counterpart, as `save` and `save!` do. Do not use `!` to mark a method as destructive:

```ruby
# Illustrative (not from Fizzy)
card.save    # returns true or false
card.save!   # same operation, raises on failure

items = [ 1, 2 ]
items.clear  # destructive, yet has no `!`
```

Why: "As a general rule, we only use `!` for methods that have a correspondent counterpart without `!`. In particular, we don’t use `!` to flag destructive actions." (STYLE.md)

## Visibility Modifiers

Write `private` with no blank line after it, and indent the methods under it:

```ruby
# STYLE.md
class SomeClass
  def some_method
    # ...
  end

  private
    def some_private_method_1
      # ...
    end

    def some_private_method_2
      # ...
    end
end
```

A module that has only private methods puts `private` at the top, adds a blank line after it, and does not indent:

```ruby
# STYLE.md
module SomeModule
  private

  def some_private_method
    # ...
  end
end
```

Omakase leaves indentation under `private` unenforced (`Layout/IndentationConsistency` is disabled), so follow the project's RuboCop config and the surrounding code.

Why: "We don't add a newline under visibility modifiers, and we indent the content under them." (STYLE.md)

## Sources

- Fizzy `STYLE.md`, `.rubocop.yml` and `AGENTS.md`, at commit 6aebc0cea
- rubocop-rails-omakase: https://github.com/rails/rubocop-rails-omakase
