# Model Structure and Associations

## Contents

- [File Structure](#file-structure)
- [Model Template](#model-template)
- [Associations](#associations)
- [Scopes](#scopes)
- [Sources](#sources)

## File Structure

Abridged layout of `app/models/` in Fizzy:

```
app/models/
├── application_record.rb
├── card.rb                    # Main model; one include list of concerns
├── card/
│   ├── closeable.rb           # Feature concern (capability)
│   ├── golden.rb              # Feature concern
│   ├── pinnable.rb            # Feature concern
│   ├── goldness.rb            # Associated model (Card::Goldness)
│   └── not_now.rb             # Associated model (Card::NotNow)
├── concerns/
│   ├── attachments.rb         # Shared concern (used by several models)
│   ├── eventable.rb           # Shared concern
│   └── mentions.rb            # Shared concern
└── closure.rb                 # Separate model (one-to-one child of Card)
```

A **concern** is one capability, named for what it does (`Closeable`, `Pinnable`). A **feature concern** belongs to one model and sits in that model's subfolder; a **shared concern** sits in `concerns/`. Associated records such as `Closure` live at model level, or nested under their parent as `Card::Goldness` does. The include list in `Card` is alphabetical.

Why: each file names one capability, and the alphabetical include list shows the model's whole surface at a glance (Fizzy: `app/models/card.rb`).

## Model Template

```ruby
# app/models/card.rb
class Card < ApplicationRecord
  include Accessible, Assignable, Attachments, Broadcastable, Closeable, Colored, Commentable,
    Entropic, Eventable, Exportable, Golden, Mentions, Multistep, Pinnable, Postponable, Promptable,
    Readable, Stallable, Statuses, Storage::Tracked, Taggable, Triageable, Watchable

  belongs_to :account, default: -> { board.account }
  belongs_to :board
  belongs_to :creator, class_name: "User", default: -> { Current.user }

  has_many :reactions, -> { order(:created_at) }, as: :reactable, dependent: :delete_all
  has_one_attached :image, dependent: :purge_later

  has_rich_text :description
# ...
end
```

The class body holds the includes and the associations. Most scopes, callbacks and feature associations live in the included concerns (for example `Card::Closeable` declares `has_one :closure`), though `Card` keeps a few of its own.

**Order is loose, not strict.** Associations, callbacks and scopes are often split across concerns. Method ordering follows STYLE.md: class methods first, then public methods (with `initialize` at the top), then `private`. Within the private section, order methods by invocation order, not alphabetically.

Why: "We order methods vertically based on their invocation order. This helps us to understand the flow of the code." (STYLE.md)

## Associations

### Belongs-to with defaults

```ruby
# app/models/card.rb
belongs_to :account, default: -> { board.account }
belongs_to :board
belongs_to :creator, class_name: "User", default: -> { Current.user }
```

Defaults are lambdas that read a parent association or `Current`, so call sites do not pass `account` or `creator` explicitly.

Why: the default derives the value from context the record already has, so the foreign key is never repeated at call sites (Fizzy: `app/models/card.rb`).

### Has-many with scoping

```ruby
# app/models/card.rb
has_many :reactions, -> { order(:created_at) }, as: :reactable, dependent: :delete_all
has_one_attached :image, dependent: :purge_later
```

`dependent: :delete_all` skips callbacks and deletes the rows in one statement. Use it for child rows that have no destroy-time side effects (`Reaction` only declares an `after_create`). Use `dependent: :destroy` when destroying the child must run callbacks, as for `has_many :pins, dependent: :destroy` in `Card::Pinnable`.

Why: `delete_all` is one query, and it is safe only when no destroy callbacks would be skipped (Fizzy: `app/models/reaction.rb`).

### Touch parent on child update

```ruby
# app/models/closure.rb
class Closure < ApplicationRecord
  belongs_to :account, default: -> { card.account }
  belongs_to :card, touch: true
  belongs_to :user, optional: true
end
```

`touch: true` updates the parent's `updated_at` whenever the child is saved, so closing a card moves `Card#updated_at`. `Comment` and `Reaction` do the same for their parents.

Why: anything keyed on the card's `updated_at` sees the child change (Fizzy: `app/models/closure.rb`).

### Polymorphic associations (no delegated_type)

Fizzy does not use `delegated_type`. It uses plain polymorphic `belongs_to`:

```ruby
# app/models/reaction.rb
class Reaction < ApplicationRecord
  belongs_to :account, default: -> { reactable.account }
  belongs_to :reactable, polymorphic: true, touch: true
  belongs_to :reacter, class_name: "User", default: -> { Current.user }
```

`Event#eventable`, `Notification#source` and `Mention#source` follow the same shape.

Why: a plain polymorphic `belongs_to` covers these cases without extra machinery, in line with the vanilla Rails approach (STYLE.md "Controller and model interactions").

### Delegated types (not used by Fizzy)

In the delegated-type pattern, a concrete "superclass" table holds the metadata every kind of record shares, and each kind keeps its own columns in its own table. The superclass row stores `<role>_type` and `<role>_id` and delegates to the concrete record. Compared with the two usual alternatives:

- Single-table inheritance puts every kind's columns in one table, so the table grows wider with each new kind and gets slower to migrate. Adding a kind to a delegated type is a new table, and the superclass table does not change.
- A plain polymorphic `belongs_to` lets many things point at one target, but it gives no shared table to query, paginate or hang common behaviour on. Basecamp still uses a polymorphic association for boosts, because a boost can target things that are not recordings.

Rails adds the helpers: `entry.message` (nil unless the entry is a message), `entry.message?`, `entry.entryable_name`, and a scope per type (`Entry.messages`).

```ruby
# Illustrative (not from Fizzy)
class Entry < ApplicationRecord
  belongs_to :account
  belongs_to :creator
  delegated_type :entryable, types: %w[ Message Comment ]
end

module Entryable
  extend ActiveSupport::Concern

  included do
    has_one :entry, as: :entryable, touch: true
  end
end

class Message < ApplicationRecord
  include Entryable
end

class Comment < ApplicationRecord
  include Entryable
end

Entry.create! entryable: Comment.new(content: "Hello!"), creator: Current.user, account: Current.account
Entry.messages.order(created_at: :desc).limit(50)
```

Why: the superclass table can be queried and paginated across every kind, which separate per-kind tables cannot do, and a new kind needs no change to it (37signals dev blog, "The Rails Delegated Type Pattern": https://dev.37signals.com/the-rails-delegated-type-pattern/; Rails API `ActiveRecord::DelegatedType`).

## Scopes

### Composed scope lambdas

```ruby
# app/models/card.rb
scope :with_users,              -> { preload(creator: [ :avatar_attachment, :account ], assignees: [ :avatar_attachment, :account ]) }
scope :preloaded,               -> { with_users.preload(:column, :tags, :steps, :closure, :goldness, :activity_spike, :image_attachment, reactions: :reacter, board: [ :entropy, :columns ], not_now: [ :user ]).with_rich_text_description_and_embeds }
```

`preloaded` builds on the `with_users` scope and finishes with `with_rich_text_description_and_embeds`. Scopes that need to find rows with no child record use `where.missing`:

```ruby
# app/models/card/closeable.rb
scope :closed, -> { joins(:closure) }
scope :open, -> { where.missing(:closure) }
```

Why: composing small scopes keeps each query readable, and `where.missing(:closure)` reads as the absence of a record (Fizzy: `app/models/card/closeable.rb`).

### Conditional scopes

```ruby
# app/models/event.rb
scope :for_creators, ->(ids) { where(creator_id: ids) if ids.present? }
scope :for_boards, ->(ids) { where(board_id: ids) if ids.present? }
```

The lambda returns `nil` when `ids` is blank, and Rails treats a scope that returns `nil` as `all`. Callers can therefore chain the scope unconditionally.

Why: call sites need no `if ids.present?` wrapper (Fizzy: `app/models/event.rb`).

### Scope aliases via case statement

```ruby
# app/models/card.rb
scope :indexed_by, ->(index) do
  case index
  when "stalled" then stalled
  when "postponing_soon" then postponing_soon
  when "closed" then closed
  when "maybe" then awaiting_triage
  when "not_now" then postponed.latest
  when "golden" then golden
  when "draft" then drafted
  else all
  end
end
```

Use `case` when a filter value aliases to other scopes. The `else all` branch makes an unknown value a no-op.

Why: filter-name-to-scope mapping lives in one place, so a new filter is one more `when` (Fizzy: `app/models/card.rb`).

## Sources

- Fizzy: `app/models/card.rb`, `app/models/card/closeable.rb`, `app/models/closure.rb`
- Fizzy: `app/models/reaction.rb`, `app/models/event.rb`
- STYLE.md "Methods ordering", "Invocation order", "Controller and model interactions"
- Fizzy: `app/models/notification.rb`, `app/models/mention.rb`
- 37signals dev blog, "The Rails Delegated Type Pattern": https://dev.37signals.com/the-rails-delegated-type-pattern/
- Rails API `ActiveRecord::DelegatedType` (activerecord 8.1.3, `lib/active_record/delegated_type.rb`)
