---
name: rails-models-advanced
description: "Rails models advanced: transactions, enums, normalization, serialization, storage, and common patterns"
group: rails
---

# Models (Advanced)

## Transaction Safety

### Use Transactions for Multi-Step Changes

```ruby
def close(user: Current.user)
  transaction do
    create_closure! user: user
    track_event :closed, creator: user
    broadcast_refresh
  end
end

def move_to(new_board)
  transaction do
    old_board_name = board.name

    update!(board: new_board, column: nil)
    events.update_all(board_id: new_board.id)
    track_event :board_changed,
      particulars: { old_board: old_board_name, new_board: new_board.name }
  end
end
```

### Rollback on Exceptions

```ruby
# Automatically rolls back on exceptions
def complex_operation
  transaction do
    step_one!  # If this raises, transaction rolls back
    step_two!  # If this raises, transaction rolls back
  end
end

# Manual rollback
def conditional_save
  transaction do
    save!
    raise ActiveRecord::Rollback unless valid_state?
  end
end
```

---

## Enum Patterns

### Basic Enum

```ruby
# Symbol keys with integer values
enum :status, { draft: 0, published: 1, archived: 2 }

# String values (preferred for readability)
enum :status, %w[ draft published archived ].index_by(&:itself)

# With prefix/suffix
enum :color, %w[ red blue green ].index_by(&:itself), prefix: true
# Generates: color_red?, color_blue?, color_green?

enum :role, %w[ owner admin member ].index_by(&:itself), suffix: :role
# Generates: owner_role?, admin_role?, member_role?
```

### Enum Inquiry Methods

```ruby
card.status            # => "published"
card.published?        # => true
card.draft?            # => false

# Bang methods to update
card.published!        # => updates status to published
```

### Enum Scopes

```ruby
# Automatically generated
Card.published         # => cards where status = 'published'
Card.draft            # => cards where status = 'draft'

Card.not_published    # => cards where status != 'published'
```

---

## Normalization (Rails 7.1+)

```ruby
# Strip whitespace
normalizes :title, with: -> value { value.strip }

# Downcase
normalizes :email, with: -> value { value.downcase }

# Array normalization
normalizes :subscribed_actions,
  with: ->(value) { Array.wrap(value).map(&:to_s).uniq & PERMITTED_ACTIONS }

# Custom normalization
normalizes :phone,
  with: -> value { value.gsub(/\D/, '') }
```

---

## Serialization

```ruby
# JSON serialization
serialize :metadata, type: Hash, coder: JSON
serialize :tags, type: Array, coder: JSON

# Usage
card.metadata = { source: "api", version: 2 }
card.tags = ["bug", "urgent"]
```

---

## Secure Tokens

```ruby
class MagicLink < ApplicationRecord
  # Generates a unique token on create
  has_secure_token :code

  # Custom token
  has_secure_token :auth_token, length: 32
end

# Usage
magic_link = MagicLink.create
magic_link.code  # => "abc123xyz789"
```

---

## Active Storage Patterns

### Single Attachment

```ruby
has_one_attached :image, dependent: :purge_later

# Usage
card.image.attach(io: File.open('image.jpg'), filename: 'image.jpg')
card.image.attached?  # => true
card.image.purge      # Delete immediately
card.image.purge_later # Delete via background job

# In views
url_for(card.image) if card.image.attached?
```

### Multiple Attachments

```ruby
has_many_attached :documents, dependent: :purge_later

# Usage
card.documents.attach(io: file, filename: 'doc.pdf')
card.documents.each { |doc| url_for(doc) }
```

### Validations

```ruby
# Using validate callback
has_one_attached :avatar

validate :avatar_content_type_allowed

private
  def avatar_content_type_allowed
    return unless avatar.attached?

    unless avatar.content_type.in?(%w[image/png image/jpg image/jpeg])
      errors.add(:avatar, "must be a PNG or JPG")
    end
  end
```

---

## Action Text (Rich Text)

```ruby
has_rich_text :description

# Usage
card.description = "Hello <strong>world</strong>"
card.description.to_plain_text  # => "Hello world"
card.description.to_s           # => "<div>Hello <strong>world</strong></div>"

# In views
<%= card.description %>

# Searching
Card.with_rich_text_description
  .where("action_text_rich_texts.body LIKE ?", "%search%")
```

---

## Best Practices

### DO

1. **Use concerns for features** - One feature = one module
```ruby
include Closeable, Pinnable, Taggable
```

2. **Use transactions for state changes**
```ruby
def close
  transaction do
    create_closure!
    track_event :closed
  end
end
```

3. **Use scopes instead of class methods for queries**
```ruby
# Good
scope :published, -> { where(status: :published) }

# Avoid
def self.published
  where(status: :published)
end
```

4. **Default values with lambdas**
```ruby
belongs_to :account, default: -> { board.account }
```

5. **Validate at boundaries**
```ruby
validates :title, presence: true, if: :published?
```

6. **Use counter caches for counts**
```ruby
belongs_to :card, counter_cache: true
```

7. **Use dependent options**
```ruby
has_many :comments, dependent: :destroy
```

### DON'T

1. **Fat models** - Extract to concerns
2. **Business logic in callbacks** - Keep callbacks simple
3. **Complex queries in models** - Use scopes or query objects
4. **Skipping validations** - Use sparingly, only when intentional
5. **N+1 queries** - Use includes/preload
6. **Callbacks that call external services** - Use jobs

---

## Common Patterns

### Soft Delete

```ruby
scope :active, -> { where(deleted_at: nil) }
scope :deleted, -> { where.not(deleted_at: nil) }

def soft_delete
  update(deleted_at: Time.current)
end

def restore
  update(deleted_at: nil)
end
```

### Positioning

```ruby
acts_as_list scope: :board

# Or manual
before_create :set_position

def move_higher
  # Implementation
end

private
  def set_position
    self.position = board.cards.maximum(:position).to_i + 1
  end
```

### State Machine (Simple)

```ruby
def publish
  return if published?

  transaction do
    self.created_at = Time.current
    published!
    track_event :published
  end
end

def draft
  return if draft?

  transaction do
    draft!
    track_event :drafted
  end
end
```

### Touch Parent

```ruby
belongs_to :board, touch: true

# Or manual
after_save -> { board.touch }, if: :published?
```

---

## Testing Models

```ruby
class CardTest < ActiveSupport::TestCase
  test "belongs to board" do
    card = cards(:logo)
    assert_equal boards(:writebook), card.board
  end

  test "validates title presence when published" do
    card = Card.new(status: :published)
    assert_not card.valid?
    assert_includes card.errors[:title], "can't be blank"
  end

  test "assigns number on create" do
    account = accounts("37s")
    board = boards(:writebook)

    card = account.cards.create!(board: board, title: "Test")

    assert_not_nil card.number
    assert card.number > 0
  end

  test "transaction rolls back on error" do
    card = cards(:logo)

    assert_no_difference "Card::Closure.count" do
      assert_raises(ActiveRecord::RecordInvalid) do
        card.transaction do
          card.create_closure!
          raise ActiveRecord::RecordInvalid  # Simulates error
        end
      end
    end
  end
end
```

---

## Summary

- **Structure**: Concerns, associations, callbacks, validations, scopes, enums, methods
- **Concerns**: Extract features to modules
- **Associations**: Use defaults, extensions, and proper dependent options
- **Callbacks**: Keep simple, use transactions for state changes
- **Scopes**: Chainable, focused queries
- **Validations**: At boundaries, conditional when needed
- **Transactions**: Wrap multi-step state changes
- **Testing**: Test associations, validations, and business logic
