# Validations, Attributes, and Serialization

## Contents

- [Validations](#validations)
- [Enums](#enums)
- [Normalization](#normalization)
- [Serialization](#serialization)
- [Secure Tokens](#secure-tokens)
- [Action Text (Rich Text)](#action-text-rich-text)
- [Primary Keys: UUIDs (Fizzy-Specific)](#primary-keys-uuids-fizzy-specific)
- [Common Patterns](#common-patterns)
- [Sources](#sources)

## Validations

### Uniqueness in the database

Put a unique index on every column set that must be unique. `Card#number` has no uniqueness validation at all, only the index:

```ruby
# db/schema.rb
t.index ["account_id", "number"], name: "index_cards_on_account_id_and_number", unique: true
```

`validates :uniqueness` appears once in Fizzy's `app/`, on `MagicLink#code`, and that column also has a unique index.

Why: the index is checked atomically by the database, while a validation alone can pass twice under concurrency (Fizzy: `db/schema.rb`).

### Built-in validations

Keep validations concise. Fizzy uses few of them:

```ruby
# app/models/identity.rb
validates :email_address, format: { with: URI::MailTo::EMAIL_REGEXP }
```

Why: most constraints live in the schema, which has `null: false` and unique indexes on the columns that need them (Fizzy: `db/schema.rb`).

### Custom validations

Write a `validate` method that adds to `errors` when a built-in validator cannot express the rule:

```ruby
# app/models/webhook.rb
validate :validate_url
# ...
private
  def validate_url
    uri = URI.parse(url.presence)

    if PERMITTED_SCHEMES.exclude?(uri.scheme)
      errors.add :url, "must use #{PERMITTED_SCHEMES.to_choice_sentence}"
    end
  rescue URI::InvalidURIError
    errors.add :url, "not a URL"
  end
```

Why: a method can parse the value and report a precise message, which a regex format check cannot (Fizzy: `app/models/webhook.rb`).

### Conditional validations

```ruby
# app/models/signup.rb
validates :email_address, format: { with: URI::MailTo::EMAIL_REGEXP }, on: :identity_creation
validates :full_name, :identity, presence: true, on: :completion
```

Use `on: :context_name` to run validations at specific points. Pass the context explicitly: `signup.valid?(:identity_creation)` in the controllers, and `valid?(:completion)` inside `Signup#complete`.

Why: one object can enforce different rules at each step of a multi-step flow (Fizzy: `app/models/signup.rb`).

## Enums

### String-valued enums with index_by

```ruby
# app/models/card/statuses.rb
included do
  enum :status, %w[ drafted published ].index_by(&:itself)
# ...
end
```

`Export` and `Webhook::Delivery` use the same form:

```ruby
# app/models/export.rb
enum :status, %w[ pending processing completed failed ].index_by(&:itself), default: :pending
```

`%w[ ... ].index_by(&:itself)` builds a hash from each name to itself, so the values are stored as strings. A plain array such as `%w[ sign_in sign_up ]` (`MagicLink#purpose`) stores integers. Add `default:` when there is a sensible starting value.

Why: string values are readable in SQL and in the schema, while integer-backed values are opaque (Fizzy: `app/models/card/statuses.rb`).

### Enum options: scopes, prefix, default

```ruby
# app/models/account/import.rb
enum :status, %w[ pending processing completed failed ].index_by(&:itself), default: :pending
enum :failure_reason, %w[ conflict invalid_export insufficient_storage_space ].index_by(&:itself), prefix: :failed_due_to, scopes: false
```

- `scopes: false` skips the generated class scopes. `User::Role` does this because it defines its own `owner`, `admin`, `member` and `active` scopes, which also filter on `active: true`.
- `prefix:` prepends a prefix to the generated methods (`failed_due_to_conflict?`; `MagicLink` uses `prefix: :for` for `for_sign_in?`).
- `default:` sets the starting value.

Why: a generated scope would collide with, or be weaker than, a hand-written one of the same name (Fizzy: `app/models/user/role.rb`).

## Normalization

Rails 7.1+ provides `normalizes`, which cleans an attribute when it is assigned and also applies to values passed to finders such as `find_by`:

```ruby
# app/models/webhook.rb
normalizes :subscribed_actions, with: ->(value) { Array.wrap(value).map(&:to_s).uniq & PERMITTED_ACTIONS }
normalizes :url, with: -> { it.strip }
```

```ruby
# app/models/identity.rb
normalizes :email_address, with: ->(value) { value.strip.downcase.presence }
```

Use `it` (Ruby 3.4's implicit block parameter) or an explicit `->(value) { ... }`; Fizzy uses both.

Why: the database only ever holds the cleaned form, so lookups and uniqueness checks see one spelling (https://api.rubyonrails.org/classes/ActiveModel/Attributes/Normalization/ClassMethods.html).

## Serialization

### Serialize arrays as JSON

```ruby
# app/models/webhook.rb
serialize :subscribed_actions, type: Array, coder: JSON
```

`type: Array` with `coder: JSON` stores the list in one text column. `Webhook::Delivery` keeps its request and response in `store ..., coder: JSON` attributes.

Why: a short list that is always read and written whole needs no join table (Fizzy: `app/models/webhook.rb`).

## Secure Tokens

### has_secure_token for API keys and signing secrets

```ruby
# app/models/board/publication.rb
class Board::Publication < ApplicationRecord
  belongs_to :account, default: -> { board.account }
  belongs_to :board, touch: true

  has_secure_token :key
end
```

`Webhook` uses `has_secure_token :signing_secret`, and `Identity::AccessToken` uses a bare `has_secure_token`. `has_secure_token` only generates a random token on create. The value is stored as plain text and looked up by value (`AccessToken.find_by(token: token)` in `app/models/identity.rb`), so protect the column like any other secret.

`MagicLink` does not use it. Its short sign-in code comes from its own `generate_code` callback and `Code.generate`, and it expires after 15 minutes.

Why: use `has_secure_token` for unguessable identifiers and bearer tokens, not for hashed credentials (https://api.rubyonrails.org/classes/ActiveRecord/SecureToken/ClassMethods.html).

## Action Text (Rich Text)

### Declare rich text and preload

```ruby
# app/models/card.rb
has_rich_text :description
# ...
scope :preloaded,               -> { with_users.preload(:column, :tags, :steps, :closure, :goldness, :activity_spike, :image_attachment, reactions: :reacter, board: [ :entropy, :columns ], not_now: [ :user ]).with_rich_text_description_and_embeds }
```

`has_rich_text :description` stores the body in the `action_text_rich_texts` table. `Comment` declares `has_rich_text :body` the same way. In a preloading scope, `with_rich_text_description_and_embeds` loads the text and its embedded attachments in one go.

For search, Fizzy joins models to the index with `has_search` from ActiveSearch, and the store adapter owns every read and write (AGENTS.md "Search is sharded on MySQL, single-index on SQLite"). `Card` and `Comment` both declare it.

Why: rich text lives in a separate table, so a list view needs the preload to avoid one query per record (Fizzy: `app/models/card.rb`).

## Primary Keys: UUIDs (Fizzy-Specific)

"All tables use UUIDv7 keys, base36-encoded to 25 characters." (AGENTS.md "UUID primary keys") This is not a Rails default. Fizzy registers a custom `ActiveRecord::Type::Uuid`, stores it as `binary(16)` on MySQL and `blob(16)` on SQLite, and teaches the adapters and the table definition about a `:uuid` column type:

```ruby
# lib/rails_ext/active_record_uuid_type.rb
BASE36_LENGTH = 25 # 36^25 > 2^128
# ...
  def generate
    uuid = SecureRandom.uuid_v7
    hex = uuid.delete("-")
    hex_to_base36(hex)
  end
```

```ruby
# config/initializers/uuid_primary_keys.rb
  class_methods do
    def native_database_types
      @native_database_types_with_uuid ||= super.merge(uuid: { name: "binary", limit: 16 })
    end
  end
# ...
module TableDefinitionUuidSupport
  def uuid(name, **options)
    column(name, :uuid, **options)
  end
end
```

In migrations, declare the table with `id: :uuid` and foreign keys with `t.uuid`; models-migrations.md has a full example.

Fixture ids are generated so that they sort older than any record created at runtime, which keeps `.first` and `.last` deterministic in tests. A fixture label ending in `_uuid` resolves to the same generated id; testing-models-fixtures.md shows the YAML and the `identify` override.

Why: ordering in tests stays stable without comparing insertion order to id order (AGENTS.md "UUID primary keys").

## Common Patterns

### State as a record (one-to-one child)

A state such as "closed" or "golden" is a child record, not a boolean column:

```ruby
# app/models/card/closeable.rb
has_one :closure, dependent: :destroy
# ...
def closed?
  closure.present?
end
```

`Card::Closeable` (models-concerns.md) holds the full concern. The child stores the metadata (`Closure` has `user` and timestamps) and the parent reads its presence. `closures.card_id` has a unique index, so a card has at most one closure. `Closure` declares `belongs_to :card, touch: true`; see the `models-structure.md` reference.

Why: a record can be queried and carries who and when, which a boolean cannot (Fizzy: `app/models/card/closeable.rb`).

## Sources

- Fizzy: `app/models/card.rb`, `app/models/card/statuses.rb`, `app/models/card/closeable.rb`
- Fizzy: `app/models/identity.rb`, `app/models/identity/access_token.rb`, `app/models/magic_link.rb`
- Fizzy: `app/models/webhook.rb`, `app/models/signup.rb`, `app/models/export.rb`, `app/models/account/import.rb`
- Fizzy: `app/models/user/role.rb`, `app/models/board/publication.rb`, `db/schema.rb`
- Fizzy: `lib/rails_ext/active_record_uuid_type.rb`, `config/initializers/uuid_primary_keys.rb`
- AGENTS.md "Search is sharded on MySQL, single-index on SQLite", "UUID primary keys"
- https://api.rubyonrails.org/classes/ActiveModel/Attributes/Normalization/ClassMethods.html
- https://api.rubyonrails.org/classes/ActiveRecord/SecureToken/ClassMethods.html
