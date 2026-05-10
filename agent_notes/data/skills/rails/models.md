# Models

## Models — Structure

Comprehensive patterns and best practices for Rails Active Record models.

---

### File Structure

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

### Model Structure Template

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

    def ensure_board_accessible
      unless creator.boards.include?(board)
        errors.add(:board, "must be accessible to creator")
      end
    end
end
```

---

### Association Patterns

```ruby
# belongs_to with defaults
belongs_to :account, default: -> { board.account }
belongs_to :creator, class_name: "User", default: -> { Current.user }
belongs_to :parent, optional: true
belongs_to :eventable, polymorphic: true

# has_many with extensions
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

# Counter caches
belongs_to :card, counter_cache: true  # In child model
# add_column :cards, :comments_count, :integer, default: 0, null: false

# Dependent options
has_many :comments, dependent: :destroy        # Calls destroy on each
has_many :events, dependent: :delete_all      # SQL DELETE (faster, no callbacks)
has_one :closure, dependent: :destroy
has_one :avatar, dependent: :purge_later      # For Active Storage
```

---

### Callback Patterns

```ruby
# Conditional callbacks
before_save :set_defaults, if: :new_record?
after_save :notify_users, unless: :draft?
before_save :set_title, if: -> { title.blank? && published? }
after_update :reindex, if: :saved_change_to_title?, unless: :draft?

# Lambda callbacks
after_save -> { board.touch }, if: :published?
after_create ->(record) { NotificationJob.perform_later(record) }

# Transaction callbacks
after_create_commit :send_notifications
after_update_commit :reindex_search
after_destroy_commit :cleanup_storage
after_commit :broadcast_changes
after_rollback :log_failure
```

---

### Scope Patterns

```ruby
# Basic scopes
scope :published, -> { where(status: :published) }
scope :recent, -> { where(created_at: 1.week.ago..) }
scope :latest, -> { order(created_at: :desc) }
scope :with_comments, -> { joins(:comments).distinct }
scope :closed, -> { joins(:closure) }
scope :open, -> { where.missing(:closure) }  # Rails 7+

# Parameterized scopes
scope :created_after, ->(date) { where(created_at: date..) }
scope :assigned_to, ->(user) { where(assignee: user) }

# Complex scopes
scope :preloaded, -> {
  includes(:creator, :assignees, :tags)
    .preload(board: :columns)
    .with_rich_text_description_and_embeds
}

scope :indexed_by, ->(index) do
  case index
  when "stalled" then stalled.latest
  when "active" then published.latest
  when "closed" then closed.recently_closed_first
  else all
  end
end

# Scope composition
Card.published.tagged_with(["bug"]).assigned_to(current_user).latest
```

---

### Validation Patterns

```ruby
# Built-in
validates :title, presence: true, if: :published?
validates :email, uniqueness: true
validates :number, uniqueness: { scope: :account_id }
validates :email, format: { with: URI::MailTo::EMAIL_REGEXP }
validates :title, length: { maximum: 200 }
validates :status, inclusion: { in: %w[draft published] }

# Custom validations
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

---

## Models — Advanced

### Transaction Safety

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

# Manual rollback
def conditional_save
  transaction do
    save!
    raise ActiveRecord::Rollback unless valid_state?
  end
end
```

---

### Enum Patterns

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

# Inquiry/scope methods auto-generated:
card.status            # => "published"
card.published?        # => true
card.published!        # => updates status to published
Card.published         # => cards where status = 'published'
Card.not_published    # => cards where status != 'published'
```

---

### Normalization (Rails 7.1+)

```ruby
normalizes :title, with: -> value { value.strip }
normalizes :email, with: -> value { value.downcase }
normalizes :subscribed_actions,
  with: ->(value) { Array.wrap(value).map(&:to_s).uniq & PERMITTED_ACTIONS }
normalizes :phone, with: -> value { value.gsub(/\D/, '') }
```

---

### Serialization

```ruby
serialize :metadata, type: Hash, coder: JSON
serialize :tags, type: Array, coder: JSON
```

---

### Secure Tokens

```ruby
class MagicLink < ApplicationRecord
  has_secure_token :code
  has_secure_token :auth_token, length: 32
end

magic_link = MagicLink.create
magic_link.code  # => "abc123xyz789"
```

---

### Action Text (Rich Text)

```ruby
has_rich_text :description

card.description = "Hello <strong>world</strong>"
card.description.to_plain_text  # => "Hello world"
card.description.to_s           # => "<div>Hello <strong>world</strong></div>"

# Searching
Card.with_rich_text_description
  .where("action_text_rich_texts.body LIKE ?", "%search%")
```

---

### Common Patterns

```ruby
# Soft Delete
scope :active, -> { where(deleted_at: nil) }
scope :deleted, -> { where.not(deleted_at: nil) }

def soft_delete
  update(deleted_at: Time.current)
end

# Touch Parent
belongs_to :board, touch: true
# Or: after_save -> { board.touch }, if: :published?

# State Machine (Simple)
def publish
  return if published?

  transaction do
    self.created_at = Time.current
    published!
    track_event :published
  end
end
```

---

## Validations

Guide for Rails model validations.

### Built-in Validations

```ruby
# Presence
validates :title, presence: true
validates :email, presence: true, on: :create

# Uniqueness
validates :email, uniqueness: true
validates :number, uniqueness: { scope: :account_id }
validates :slug, uniqueness: { case_sensitive: false }

# Format
validates :email, format: { with: URI::MailTo::EMAIL_REGEXP }
validates :url, format: { with: /\Ahttps?:\/\/.+\z/ }

# Length
validates :title, length: { maximum: 200 }
validates :password, length: { minimum: 8, maximum: 128 }
validates :code, length: { is: 6 }

# Inclusion
validates :status, inclusion: { in: %w[draft published archived] }
validates :role, inclusion: { in: ALLOWED_ROLES }
```

### Custom Validations

```ruby
# Method validation
class Webhook < ApplicationRecord
  validate :validate_url

  private
    def validate_url
      return if url.blank?

      uri = URI.parse(url)
      unless PERMITTED_SCHEMES.include?(uri.scheme)
        errors.add(:url, "must use http or https")
      end
    rescue URI::InvalidURIError
      errors.add(:url, "is not a valid URL")
    end
end

# Validator class
class EmailValidator < ActiveModel::EachValidator
  def validate_each(record, attribute, value)
    unless value =~ URI::MailTo::EMAIL_REGEXP
      record.errors.add(attribute, "is not a valid email")
    end
  end
end

# Usage
validates :email, email: true
```

### Conditional Validations

```ruby
validates :title, presence: true, if: :published?
validates :description, presence: true, unless: :draft?
validates :api_key, presence: true, on: :create
```

---

## Concerns

Comprehensive patterns and best practices for Rails concerns (both model and controller).

### Philosophy

**Concerns extract shared or feature-specific behavior into reusable modules.**

Two types:
1. **Model Concerns** - Feature-specific (`Card::Closeable`) or shared (`Searchable`)
2. **Controller Concerns** - Shared behavior (`Authentication`, `CardScoped`)

### File Structure

```
app/models/
├── card/
│   ├── closeable.rb       # Feature concern (Card::Closeable)
│   ├── golden.rb          # Feature concern
│   └── pinnable.rb        # Feature concern
└── concerns/
    ├── eventable.rb       # Shared concern
    └── searchable.rb      # Shared concern
```

### Feature Concern Template (Model-Specific)

```ruby
# app/models/card/closeable.rb
module Card::Closeable
  extend ActiveSupport::Concern

  included do
    has_one :closure, dependent: :destroy

    scope :closed, -> { joins(:closure) }
    scope :open, -> { where.missing(:closure) }
    scope :recently_closed_first, -> {
      closed.order("closures.created_at": :desc)
    }

    after_update_commit :broadcast_closure_change, if: :saved_change_to_closure?
  end

  class_methods do
    def close_all_stale
      open.where(last_active_at: ..1.month.ago).find_each(&:close)
    end
  end

  def closed?
    closure.present?
  end

  def closed_by
    closure&.user
  end

  def close(user: Current.user)
    return if closed?

    transaction do
      create_closure! user: user
      track_event :closed, creator: user
    end
  end

  def reopen(user: Current.user)
    return unless closed?

    transaction do
      closure.destroy
      track_event :reopened, creator: user
    end
  end

  private
    def broadcast_closure_change
      broadcast_refresh_later
    end
end
```

### Shared Concern Template

```ruby
# app/models/concerns/eventable.rb
module Eventable
  extend ActiveSupport::Concern

  included do
    has_many :events, as: :eventable, dependent: :destroy
  end

  def track_event(action, creator: Current.user, board: self.board, **particulars)
    if should_track_event?
      board.events.create!(
        action: "#{eventable_prefix}_#{action}",
        creator: creator,
        board: board,
        eventable: self,
        particulars: particulars
      )
    end
  end

  private
    def eventable_prefix
      self.class.name.demodulize.underscore
    end

    def should_track_event?
      true
    end
end
```

### Production Examples

```ruby
# Card::Golden
module Card::Golden
  extend ActiveSupport::Concern

  included do
    has_one :goldness, dependent: :destroy, class_name: "Card::Goldness"

    scope :golden, -> { joins(:goldness) }
    scope :with_golden_first, -> {
      left_outer_joins(:goldness)
        .prepend_order("card_goldnesses.id IS NULL")
        .preload(:goldness)
    }
  end

  def golden?
    goldness.present?
  end

  def gild
    create_goldness! unless golden?
  end

  def ungild
    goldness&.destroy
  end
end

# Card::Pinnable
module Card::Pinnable
  extend ActiveSupport::Concern

  included do
    has_many :pins, dependent: :destroy
    after_update_commit :broadcast_pin_updates, if: :preview_changed?
  end

  def pinned_by?(user)
    pins.exists?(user: user)
  end

  def pin_by(user)
    pins.find_or_create_by!(user: user)
  end

  def unpin_by(user)
    pins.find_by(user: user)&.destroy
  end

  private
    def broadcast_pin_updates
      pins.find_each do |pin|
        pin.broadcast_replace_later_to [ pin.user, :pins_tray ],
          partial: "my/pins/pin"
      end
    end
end

# Searchable (Shared)
module Searchable
  extend ActiveSupport::Concern

  included do
    after_create_commit :create_in_search_index
    after_update_commit :update_in_search_index
    after_destroy_commit :remove_from_search_index
  end

  private
    def create_in_search_index
      search_record_class.create!(search_record_attributes)
    end

    def update_in_search_index
      search_record_class.upsert!(search_record_attributes)
    end

    def remove_from_search_index
      search_record_class
        .find_by(searchable_type: self.class.name, searchable_id: id)
        &.destroy
    end

    def search_record_attributes
      {
        account_id: account_id,
        searchable_type: self.class.name,
        searchable_id: id,
        card_id: search_card_id,
        board_id: search_board_id,
        title: search_title,
        content: search_content,
        created_at: created_at
      }
    end

  # Including models must implement:
  # - search_title
  # - search_content
  # - search_card_id
  # - search_board_id
end
```

### Controller Concerns

```ruby
# app/controllers/concerns/authentication.rb
module Authentication
  extend ActiveSupport::Concern

  included do
    before_action :require_account
    before_action :require_authentication

    helper_method :authenticated?, :current_user, :current_identity
  end

  class_methods do
    def allow_unauthenticated_access(**options)
      skip_before_action :require_authentication, **options
      before_action :resume_session, **options
    end

    def require_unauthenticated_access(**options)
      allow_unauthenticated_access **options
      before_action :redirect_authenticated_user, **options
    end
  end

  private
    def authenticated?
      Current.identity.present?
    end

    def current_user
      Current.user
    end

    def require_authentication
      redirect_to new_session_path unless authenticated?
    end

    def require_account
      unless Current.account
        redirect_to root_url(untenanted: true)
      end
    end

    def resume_session
      if session_cookie = cookies.signed[:session_id]
        Current.session = Session.find_by(id: session_cookie)
      end
    end

    def redirect_authenticated_user
      redirect_to root_path if authenticated?
    end
end

# app/controllers/concerns/card_scoped.rb
module CardScoped
  extend ActiveSupport::Concern

  included do
    before_action :set_card, :set_board
  end

  private
    def set_card
      @card = Current.user.accessible_cards.find_by!(number: params[:card_id])
    end

    def set_board
      @board = @card.board
    end

    def render_card_replacement
      render turbo_stream: turbo_stream.replace(
        [ @card, :card_container ],
        partial: "cards/container",
        method: :morph,
        locals: { card: @card.reload }
      )
    end
end
```

### Concern Patterns

```ruby
# Dependency Injection
module Notifiable
  extend ActiveSupport::Concern

  def send_notifications
    users_to_notify.each do |user|
      notify_user(user)
    end
  end

  private
    def users_to_notify
      raise NotImplementedError, "Include class must implement users_to_notify"
    end

    def notify_user(user)
      raise NotImplementedError, "Include class must implement notify_user"
    end
end

# SMTP Error Handling (Job Concern)
module SmtpDeliveryErrorHandling
  extend ActiveSupport::Concern

  included do
    retry_on Net::OpenTimeout, Net::ReadTimeout, Socket::ResolutionError,
      wait: :polynomially_longer

    retry_on Net::SMTPServerBusy, wait: :polynomially_longer

    rescue_from Net::SMTPSyntaxError do |error|
      case error.message
      when /\A501 5\.1\.3/
        Sentry.capture_exception error, level: :info
      else
        raise
      end
    end

    rescue_from Net::SMTPFatalError do |error|
      case error.message
      when /\A550 5\.1\.1/, /\A552 5\.6\.0/, /\A555 5\.5\.4/
        Sentry.capture_exception error, level: :info
      else
        raise
      end
    end
  end
end
```

### Testing Concerns

```ruby
# test/models/card/closeable_test.rb
class Card::CloseableTest < ActiveSupport::TestCase
  setup do
    Current.session = sessions(:david)
  end

  test "close creates closure" do
    card = cards(:logo)

    assert_not card.closed?

    assert_difference -> { Card::Closure.count }, +1 do
      card.close(user: users(:kevin))
    end

    assert card.closed?
    assert_equal users(:kevin), card.closed_by
  end

  test "reopen removes closure" do
    card = cards(:logo)
    card.close

    assert card.closed?

    assert_difference -> { Card::Closure.count }, -1 do
      card.reopen
    end

    assert_not card.closed?
  end
end
```

---

## Migrations

Comprehensive guide for Rails database migrations.

### File Structure

```
db/migrate/
├── 20250101120000_create_cards.rb
├── 20250102130000_add_status_to_cards.rb
└── 20250103140000_create_index_on_cards_board_id.rb
```

### Basic Migration Patterns

```ruby
# Create Table
class CreateCards < ActiveRecord::Migration[8.0]
  def change
    create_table :cards, id: :uuid do |t|
      t.uuid :account_id, null: false
      t.uuid :board_id, null: false
      t.uuid :creator_id, null: false

      t.integer :number, null: false
      t.string :title
      t.text :description
      t.string :status, default: "draft", null: false
      t.string :color

      t.timestamps

      t.index ["account_id", "number"], unique: true
      t.index ["board_id"]
      t.index ["creator_id"]
      t.index ["status"]
    end
  end
end

# Add Column
class AddPublishedAtToCards < ActiveRecord::Migration[8.0]
  def change
    add_column :cards, :published_at, :datetime
    add_index :cards, :published_at
  end
end

# Remove Column
class RemoveDeprecatedFieldFromCards < ActiveRecord::Migration[8.0]
  def change
    remove_column :cards, :deprecated_field, :string
  end
end

# Change Column
class ChangeCardsTitleToText < ActiveRecord::Migration[8.0]
  def up
    change_column :cards, :title, :text
  end

  def down
    change_column :cards, :title, :string
  end
end

# Rename Column
class RenameCardsDescToDescription < ActiveRecord::Migration[8.0]
  def change
    rename_column :cards, :desc, :description
  end
end
```

### Index Patterns

```ruby
# Single / Composite / Unique
add_index :cards, :board_id
add_index :cards, [:account_id, :number], unique: true
add_index :cards, :email, unique: true, name: "idx_cards_on_email"

# Partial Index (PostgreSQL)
add_index :cards, :published_at, where: "status = 'published'"

# Remove
remove_index :cards, :board_id
remove_index :cards, name: "idx_cards_on_email"
```

### Foreign Keys

```ruby
class AddForeignKeys < ActiveRecord::Migration[8.0]
  def change
    add_foreign_key :cards, :boards
    add_foreign_key :cards, :accounts
    add_foreign_key :cards, :users, column: :creator_id
  end
end
```

### Data Migrations

```ruby
class BackfillCardNumbers < ActiveRecord::Migration[8.0]
  def up
    Card.where(number: nil).find_each do |card|
      card.update!(number: card.account.increment!(:cards_count).cards_count)
    end
  end

  def down
    # Usually no rollback for data migrations
  end
end
```

### UUID Primary Keys

```ruby
class EnableUuidExtension < ActiveRecord::Migration[8.0]
  def change
    enable_extension "pgcrypto"  # PostgreSQL
  end
end

create_table :cards, id: :uuid do |t|
  t.uuid :account_id, null: false
  t.timestamps
end
```

### Reversible Migrations

```ruby
class AddCheckConstraint < ActiveRecord::Migration[8.0]
  def change
    reversible do |dir|
      dir.up do
        execute <<-SQL
          ALTER TABLE cards
          ADD CONSTRAINT check_positive_number
          CHECK (number > 0)
        SQL
      end

      dir.down do
        execute <<-SQL
          ALTER TABLE cards
          DROP CONSTRAINT check_positive_number
        SQL
      end
    end
  end
end
```

### Best Practices

- Add indexes for foreign keys and frequently queried columns
- Use null constraints and default values where appropriate
- Use `change` when possible (auto-reversible)
- Don't modify old migrations — create new ones
- Don't remove columns in production without a deprecation cycle
- Keep data migrations separate from schema migrations
