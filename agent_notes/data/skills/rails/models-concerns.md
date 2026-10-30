# Model Concerns: Capabilities as Mixins

## Contents

- [Philosophy](#philosophy)
- [Feature Concern Template](#feature-concern-template)
- [Shared Concern Template](#shared-concern-template)
- [Production Examples](#production-examples)
- [Facade over Plain Objects](#facade-over-plain-objects)
- [Testing Concerns](#testing-concerns)
- [Sources](#sources)

## Philosophy

A **concern** is one capability of a model, implemented as an included module. Concerns are:

- **Named for what they do** (`Closeable`, `Pinnable`, `Eventable`), not what they touch.
- **Organized by scope**: feature concerns in `app/models/model_name/` (`Card::Closeable`), shared concerns in `app/models/concerns/` (`Eventable`).
- **Included alphabetically** in the model, so the list is easy to scan.
- **A facade over the domain model**: a concern exposes a public API, and internal logic can live in plain objects.

`Card` includes 23 concerns. Each one is a focused capability, which keeps the model readable despite its size.

Why: the model stays the one place where behaviour lives, with no service layer: "We don't use services or other artifacts to connect the two." (STYLE.md "Controller and model interactions")

## Feature Concern Template

A feature concern lives in `app/models/model_name/` and holds the associations, scopes and public methods for one capability:

```ruby
# app/models/card/closeable.rb
module Card::Closeable
  extend ActiveSupport::Concern

  included do
    has_one :closure, dependent: :destroy

    scope :closed, -> { joins(:closure) }
    scope :open, -> { where.missing(:closure) }

    scope :recently_closed_first, -> { closed.order(closures: { created_at: :desc }) }
    scope :closed_at_window, ->(window) { closed.where(closures: { created_at: window }) }
    scope :closed_by, ->(users) { closed.where(closures: { user_id: Array(users) }) }
  end
# ...
  def closed?
    closure.present?
  end
# ...
end
```

Follow the project's RuboCop config (`.rubocop.yml`). Fizzy uses `rubocop-rails-omakase`, which enforces neither style. When the project has no rule, the 37signals default is expanded conditionals with guards only at the very top; Fizzy's `close` and `reopen` use `unless closed?` and `if closed?` around a transaction.

**Structure:**
1. `included do`: associations, scopes, callbacks.
2. Public methods: the public API (predicates, actions).
3. `private`: helpers, callbacks, internal state.

Why: keeping the association, the scopes and the state-change methods in one module means one file answers "how does a card close?" (Fizzy: `app/models/card/closeable.rb`).

## Shared Concern Template

A shared concern is included by several models and defines a hook-method contract. `Eventable` is mixed into `Card` and `Comment` through their own `Eventable` concerns:

```ruby
# app/models/concerns/eventable.rb
included do
  has_many :events, as: :eventable, dependent: :destroy
end

def track_event(action, creator: Current.user, board: self.board, **particulars)
  if should_track_event?
    board.events.create!(action: "#{eventable_prefix}_#{action}", creator:, board:, eventable: self, particulars:)
  end
end
# ...
def event_was_created(event)
end
# ...
private
  def should_track_event?
    true
  end
```

A model-specific concern includes the shared one and overrides the hooks:

```ruby
# app/models/card/eventable.rb
module Card::Eventable
  extend ActiveSupport::Concern

  include ::Eventable
# ...
  def event_was_created(event)
    transaction do
      create_system_comment_for(event)
      touch_last_active_at unless was_just_published?
    end
  end
# ...
  private
    def should_track_event?
      published?
    end
# ...
end
```

`track_event` calls the private `should_track_event?`, which `Card::Eventable` overrides to return `published?`. `event_was_created(event)` is the public hook that `Event` calls from its `after_create`.

Why: default hook methods let each model customise shared behaviour without a service object (Fizzy: `app/models/concerns/eventable.rb`).

## Production Examples

### Card::Golden (intention-revealing API)

```ruby
# app/models/card/golden.rb
module Card::Golden
  extend ActiveSupport::Concern

  included do
    has_one :goldness, dependent: :destroy, class_name: "Card::Goldness"

    scope :golden, -> { joins(:goldness) }
    scope :with_golden_first, -> { left_outer_joins(:goldness).prepend_order("card_goldnesses.id IS NULL").preload(:goldness) }
  end
# ...
  def gild
    create_goldness! unless golden?
  end
# ...
end
```

`gild` creates the `Card::Goldness` record unless one exists, and `ungild` destroys it. `Cards::GoldnessesController#create` is `@card.gild`. Fizzy-specific: `with_golden_first` uses `prepend_order`, which `lib/rails_ext/prepend_order.rb` adds to `ActiveRecord::Relation`; it is not part of Rails.

Why: "we prefer clear, intention-revealing model APIs that controllers call directly" (STYLE.md "Controller and model interactions")

### Card::Pinnable (access-aware broadcast)

```ruby
# app/models/card/pinnable.rb
# Renders the board this run has loaded, so it picks its recipients from that same board:
# a card that moves again while the job runs cannot widen the audience, and access revoked
# before the job runs is already gone from board.users.
def broadcast_pin_updates
  pins.where(user: board.users).find_each do |pin|
    pin.broadcast_replace_to [ pin.user, :pins_tray ], partial: "my/pins/pin"
  end
end
```

The recipients come from `board.users` at the moment the job runs, not from the moment the job was enqueued. A card that moves again while the job runs cannot widen the audience, and a user whose access was revoked is already gone from `board.users`. The rest of the concern is `pinned_by?`, `pin_for`, `pin_by` and `unpin_by`.

Why: the broadcast decides who sees a card from the board it renders (Fizzy: `app/models/card/pinnable.rb`).

## Facade over Plain Objects

When a capability's logic grows, keep the public method in the concern and delegate to a plain object:

```ruby
# app/models/card/stallable.rb
def detect_activity_spikes
  Card::ActivitySpike::Detector.new(self).detect
end
```

```ruby
# app/models/card/activity_spike/detector.rb
class Card::ActivitySpike::Detector
  attr_reader :card

  def initialize(card)
    @card = card
  end

  def detect
    if has_activity_spike?
      register_activity_spike
      true
    else
      false
    end
  end
```

`Card::Eventable` does the same with `SystemCommenter.new(self, event).comment`. The concern exposes one method; the plain object holds the logic. This is not a "service object": it is a helper class owned by the model's namespace.

Why: the model stays the domain abstraction, and a plain object is used only when it earns its place (Fizzy: `app/models/card/stallable.rb`; STYLE.md "When justified, it is fine to use services or form objects, but don't treat those as special artifacts").

## Testing Concerns

Test a concern through the model it is mixed into. `Card::CloseableTest` sets `Current.session` in `setup`, closes a fixture card and asserts the recorded event and `closed_by`; testing-models-fixtures.md shows the test in full.

**Key patterns:**
- The global `setup` in `test/test_helper.rb` sets `Current.account`; add `Current.session = sessions(:david)` where the code reads `Current.user`.
- Use fixtures (`cards(:logo)`, `users(:kevin)`).
- Assert state changes with `assert_difference -> { ... }`.
- Check the events a change produces, not the callbacks that produced them.

Why: tests mirror the source layout, so `app/models/card/closeable.rb` is tested in `test/models/card/closeable_test.rb` (Fizzy: `test/models/card/closeable_test.rb`).

## Sources

- Fizzy: `app/models/card/closeable.rb`, `app/models/card/golden.rb`, `app/models/card/pinnable.rb`, `app/models/card/stallable.rb`
- Fizzy: `app/models/concerns/eventable.rb`, `app/models/card/eventable.rb`, `app/models/card/activity_spike/detector.rb`
- Fizzy: `lib/rails_ext/prepend_order.rb`, `test/models/card/closeable_test.rb`, `test/test_helper.rb`
- STYLE.md "Controller and model interactions"
