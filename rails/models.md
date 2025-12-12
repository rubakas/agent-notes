# Models

Comprehensive patterns and best practices for Rails Active Record models.

---

## File Structure

```
app/models/
├── card.rb                    # Main model
├── card/
│   ├── closeable.rb          # Feature concern
│   ├── golden.rb             # Feature concern
│   ├── pinnable.rb           # Feature concern
│   └── goldness.rb           # Associated model (Card::Goldness)
├── concerns/
│   ├── eventable.rb          # Shared concern (multiple models)
│   └── searchable.rb         # Shared concern
└── application_record.rb      # Base model
```

---

## Model Structure Template

```ruby
class Card < ApplicationRecord
  # 1. CONCERNS (alphabetically for easy scanning)
  include Assignable, Attachments, Broadcastable, Closeable,
    Colored, Entropic, Eventable, Exportable, Golden, Mentions,
    Multistep, Pinnable, Postponable, Promptable, Readable,
    Searchable, Stallable, Statuses, Storage::Tracked,
    Taggable, Triageable, Watchable

  # 2. ASSOCIATIONS
  # Order: belongs_to, has_one, has_many, has_and_belongs_to_many,
  #        has_one_attached, has_many_attached, has_rich_text

  # belongs_to (with defaults if needed)
  belongs_to :account, default: -> { board.account }
  belongs_to :board
  belongs_to :creator, class_name: "User", default: -> { Current.user }

  # has_one
  has_one :closure, dependent: :destroy
  has_one :goldness, dependent: :destroy

  # has_many
  has_many :comments, dependent: :destroy
  has_many :events, as: :eventable, dependent: :destroy
  has_many :assignments, dependent: :destroy
  has_many :assignees, through: :assignments, source: :user

  # Active Storage attachments
  has_one_attached :image, dependent: :purge_later

  # Action Text
  has_rich_text :description

  # 3. CALLBACKS (in lifecycle order)
  # Lifecycle: before_validation, after_validation, before_save,
  #            around_save, before_create, around_create, after_create,
  #            before_update, around_update, after_update,
  #            before_destroy, around_destroy, after_destroy,
  #            after_save, after_commit, after_rollback

  before_validation :normalize_title
  before_save :set_default_title, if: :published?
  before_create :assign_number

  after_save -> { board.touch }, if: :published?
  after_touch -> { board.touch }, if: :published?
  after_update :handle_board_change, if: :saved_change_to_board_id?

  after_create_commit :broadcast_creation
  after_update_commit :broadcast_updates
  after_destroy_commit :broadcast_removal

  # 4. VALIDATIONS
  validates :title, presence: true, if: :published?
  validates :number, uniqueness: { scope: :account_id }
  validates :status, inclusion: { in: %w[draft published] }

  # Custom validations
  validate :ensure_board_accessible, if: :board_id_changed?

  # 5. NORMALIZATIONS (Rails 7.1+)
  normalizes :title, with: -> value { value.strip }

  # 6. SCOPES (grouped by purpose)
  # Ordering scopes
  scope :reverse_chronologically, -> { order created_at: :desc, id: :desc }
  scope :chronologically, -> { order created_at: :asc, id: :asc }
  scope :latest, -> { order last_active_at: :desc, id: :desc }

  # Filtering scopes
  scope :published, -> { where(status: :published) }
  scope :drafted, -> { where(status: :draft) }

  # Association scopes
  scope :assigned_to, ->(users) {
    joins(:assignees).where(assignees: { user: users })
  }
  scope :tagged_with, ->(tags) {
    joins(:taggings).where(taggings: { tag: tags })
  }

  # Complex query scopes
  scope :preloaded, -> {
    with_users.preload(:column, :tags, :steps, :closure, :goldness,
      board: [:columns]).with_rich_text_description_and_embeds
  }

  # Conditional scopes
  scope :indexed_by, ->(index) do
    case index
    when "stalled" then stalled
    when "active" then published.latest
    when "closed" then closed
    else all
    end
  end

  # 7. ENUMS
  enum :status, %w[ draft published ].index_by(&:itself)
  enum :color, %w[ red blue green ].index_by(&:itself), prefix: true

  # 8. DELEGATIONS
  delegate :accessible_to?, to: :board
  delegate :name, to: :creator, prefix: true

  # 9. PUBLIC METHODS
  # Action methods (change state, use transactions)
  def move_to(new_board)
    transaction do
      update!(board: new_board)
      events.update_all(board_id: new_board.id)
    end
  end

  def archive
    transaction do
      update!(archived_at: Time.current)
      track_event :archived
    end
  end

  # Query methods (return data/booleans)
  def archived?
    archived_at.present?
  end

  def filled?
    title.present? || description.present?
  end

  # 10. PRIVATE METHODS (ordered by invocation)
  private
    def normalize_title
      self.title = title&.strip
    end

    def set_default_title
      self.title = "Untitled" if title.blank?
    end

    def assign_number
      self.number ||= account.increment!(:cards_count).cards_count
    end

    def handle_board_change
      old_board = account.boards.find_by(id: board_id_before_last_save)

      transaction do
        update! column: nil
        track_board_change_event(old_board.name)
        grant_access_to_assignees unless board.all_access?
      end

      remove_inaccessible_notifications_later
    end

    def track_board_change_event(old_board_name)
      track_event "board_changed",
        particulars: { old_board: old_board_name, new_board: board.name }
    end

    def grant_access_to_assignees
      board.accesses.grant_to(assignees)
    end

    def ensure_board_accessible
      unless creator.boards.include?(board)
        errors.add(:board, "must be accessible to creator")
      end
    end
end
```

---

## Association Patterns

### belongs_to with Defaults

```ruby
# Default value from lambda
belongs_to :account, default: -> { board.account }
belongs_to :creator, class_name: "User", default: -> { Current.user }

# Optional association
belongs_to :parent, optional: true

# Polymorphic
belongs_to :eventable, polymorphic: true
```

### has_many with Extensions

```ruby
has_many :accesses, dependent: :delete_all do
  def revise(granted: [], revoked: [])
    transaction do
      grant_to granted
      revoke_from revoked
    end
  end

  def grant_to(user_ids)
    user_ids.each { |id| create(user_id: id) }
  end

  def revoke_from(user_ids)
    where(user_id: user_ids).delete_all
  end
end

# Usage:
board.accesses.revise(granted: [user1.id], revoked: [user2.id])
```

### Counter Caches

```ruby
# In parent model
has_many :comments, dependent: :destroy

# In child model
belongs_to :card, counter_cache: true

# Migration
add_column :cards, :comments_count, :integer, default: 0, null: false
```

### Dependent Options

```ruby
has_many :comments, dependent: :destroy        # Calls destroy on each
has_many :events, dependent: :delete_all      # SQL DELETE (faster, no callbacks)
has_one :closure, dependent: :destroy
has_one :avatar, dependent: :purge_later      # For Active Storage
```

---

## Callback Patterns

### Conditional Callbacks

```ruby
# With if/unless
before_save :set_defaults, if: :new_record?
after_save :notify_users, unless: :draft?

# With Proc
before_save :set_title, if: -> { title.blank? && published? }

# Multiple conditions
after_update :reindex,
  if: :saved_change_to_title?,
  unless: :draft?
```

### Lambda Callbacks

```ruby
# Inline logic
after_save -> { board.touch }, if: :published?

# With parameters (using stabby lambda)
after_create ->(record) { NotificationJob.perform_later(record) }
```

### Transaction Callbacks

```ruby
# After transaction commits
after_create_commit :send_notifications
after_update_commit :reindex_search
after_destroy_commit :cleanup_storage

# All commits
after_commit :broadcast_changes

# On rollback
after_rollback :log_failure
```

### Callback Methods Location

```ruby
class Card < ApplicationRecord
  after_save :do_something

  private
    # Callback methods in private section
    def do_something
      # Implementation
    end
end
```

---

## Scope Patterns

### Basic Scopes

```ruby
# Simple where
scope :published, -> { where(status: :published) }
scope :recent, -> { where(created_at: 1.week.ago..) }

# Ordering
scope :latest, -> { order(created_at: :desc) }
scope :alphabetical, -> { order(name: :asc) }

# Joins
scope :with_comments, -> { joins(:comments).distinct }
scope :closed, -> { joins(:closure) }

# Missing associations (Rails 7+)
scope :open, -> { where.missing(:closure) }
```

### Parameterized Scopes

```ruby
scope :created_after, ->(date) { where(created_at: date..) }
scope :assigned_to, ->(user) { where(assignee: user) }
scope :tagged_with, ->(tag_titles) {
  joins(:taggings).where(taggings: { tag: Tag.where(title: tag_titles) })
}
```

### Complex Scopes

```ruby
scope :preloaded, -> {
  includes(:creator, :assignees, :tags)
    .preload(board: :columns)
    .with_rich_text_description_and_embeds
}

scope :search_results, ->(query) do
  left_joins(:tags)
    .where("cards.title LIKE ? OR tags.title LIKE ?", "%#{query}%", "%#{query}%")
    .distinct
end

scope :indexed_by, ->(index) do
  case index
  when "stalled" then stalled.latest
  when "active" then published.latest
  when "closed" then closed.recently_closed_first
  else all
  end
end
```

### Scope Composition

```ruby
# Scopes are chainable
Card.published.tagged_with(["bug"]).assigned_to(current_user).latest

# Can be used in associations
has_many :published_cards, -> { published }, class_name: "Card"
```

---

## Validation Patterns

### Built-in Validations

```ruby
# Presence
validates :title, presence: true
validates :title, presence: true, if: :published?

# Uniqueness
validates :email, uniqueness: true
validates :number, uniqueness: { scope: :account_id }
validates :slug, uniqueness: { case_sensitive: false }

# Format
validates :email, format: { with: URI::MailTo::EMAIL_REGEXP }
validates :url, format: { with: /\Ahttps?:\/\// }

# Length
validates :title, length: { maximum: 200 }
validates :password, length: { minimum: 8 }
validates :code, length: { is: 6 }

# Inclusion/Exclusion
validates :status, inclusion: { in: %w[draft published] }
validates :role, exclusion: { in: %w[super_admin] }

# Numericality
validates :age, numericality: { only_integer: true }
validates :price, numericality: { greater_than: 0 }
```

### Custom Validations

```ruby
# Method validation
validate :url_must_be_valid

private
  def url_must_be_valid
    return if url.blank?

    uri = URI.parse(url)
    unless PERMITTED_SCHEMES.include?(uri.scheme)
      errors.add(:url, "must use http or https")
    end
  rescue URI::InvalidURIError
    errors.add(:url, "is not a valid URL")
  end
```

### Conditional Validations

```ruby
validates :title, presence: true, if: :published?
validates :description, presence: true, on: :update
validates :email, uniqueness: true, unless: :skip_email_validation?
```

---

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

### ✅ DO

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

### ❌ DON'T

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
