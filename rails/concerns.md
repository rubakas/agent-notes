# Concerns

Comprehensive patterns and best practices for Rails concerns (both model and controller).

---

## Philosophy

**Concerns extract shared or feature-specific behavior into reusable modules.**

Two types:
1. **Model Concerns** - Feature-specific (`Card::Closeable`) or shared (`Searchable`)
2. **Controller Concerns** - Shared behavior (`Authentication`, `CardScoped`)

---

## Model Concerns

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

  # included block runs when module is included
  included do
    # Associations for this feature
    has_one :closure, dependent: :destroy

    # Scopes
    scope :closed, -> { joins(:closure) }
    scope :open, -> { where.missing(:closure) }
    scope :recently_closed_first, -> {
      closed.order("closures.created_at": :desc)
    }

    # Callbacks (if needed for this feature)
    after_update_commit :broadcast_closure_change, if: :saved_change_to_closure?
  end

  # Class methods (optional)
  class_methods do
    def close_all_stale
      open.where(last_active_at: ..1.month.ago).find_each(&:close)
    end
  end

  # Instance methods - Query methods
  def closed?
    closure.present?
  end

  def closed_by
    closure&.user
  end

  def closed_at
    closure&.created_at
  end

  # Instance methods - Action methods (use transactions + events)
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

  # Private methods specific to this concern
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
      true  # Override in including class if needed
    end
end
```

### Production Examples

#### Card::Golden

```ruby
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
```

#### Card::Pinnable

```ruby
module Card::Pinnable
  extend ActiveSupport::Concern

  included do
    has_many :pins, dependent: :destroy

    after_update_commit :broadcast_pin_updates, if: :preview_changed?
  end

  def pinned_by?(user)
    pins.exists?(user: user)
  end

  def pin_for(user)
    pins.find_by(user: user)
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
```

#### Card::Taggable

```ruby
module Card::Taggable
  extend ActiveSupport::Concern

  included do
    has_many :taggings, dependent: :destroy
    has_many :tags, through: :taggings

    scope :tagged_with, ->(tags) {
      joins(:taggings).where(taggings: { tag: tags })
    }
  end

  def toggle_tag_with(title)
    tag = account.tags.find_or_create_by!(title: title)

    transaction do
      if tagged_with?(tag)
        taggings.destroy_by tag: tag
      else
        taggings.create tag: tag
      end
    end
  end

  def tagged_with?(tag)
    tags.include? tag
  end
end
```

#### Searchable (Shared)

```ruby
module Searchable
  extend ActiveSupport::Concern

  included do
    after_create_commit :create_in_search_index
    after_update_commit :update_in_search_index
    after_destroy_commit :remove_from_search_index
  end

  def reindex
    update_in_search_index
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

    def search_record_class
      Search::Record.for(account_id)
    end

  # Including models must implement:
  # - search_title
  # - search_content
  # - search_card_id
  # - search_board_id
end
```

#### Broadcastable

```ruby
module Card::Broadcastable
  extend ActiveSupport::Concern

  included do
    broadcasts_refreshes  # Turbo auto-refresh

    before_update :remember_if_preview_changed
  end

  private
    def remember_if_preview_changed
      @preview_changed ||= title_changed? || column_id_changed? || board_id_changed?
    end

    def preview_changed?
      @preview_changed
    end
end
```

---

## Controller Concerns

### File Structure

```
app/controllers/concerns/
├── authentication.rb      # Authentication/authorization
├── card_scoped.rb        # Scoping concern
├── board_scoped.rb       # Scoping concern
└── filter_scoped.rb      # Filter concern
```

### Authentication Concern

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
    # Allow unauthenticated access to specific actions
    def allow_unauthenticated_access(**options)
      skip_before_action :require_authentication, **options
      before_action :resume_session, **options
    end

    # Require unauthenticated (for login/signup pages)
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

    def current_identity
      Current.identity
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
```

### Scoping Concern

```ruby
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

    # Helper methods for this resource
    def render_card_replacement
      render turbo_stream: turbo_stream.replace(
        [ @card, :card_container ],
        partial: "cards/container",
        method: :morph,
        locals: { card: @card.reload }
      )
    end

    def render_card_preview_replacement
      render turbo_stream: turbo_stream.replace(
        [ @card, :preview ],
        partial: "cards/display/preview",
        locals: { card: @card.reload }
      )
    end
end
```

### Feature Toggle Concern

```ruby
module FeatureGuarded
  extend ActiveSupport::Concern

  included do
    before_action :ensure_feature_enabled
  end

  private
    def ensure_feature_enabled
      feature_name = controller_name.singularize

      unless Current.account.feature_enabled?(feature_name)
        respond_to do |format|
          format.html { redirect_to root_path, alert: "Feature not available" }
          format.json { head :forbidden }
        end
      end
    end
end
```

### Pagination Concern

```ruby
module Paginatable
  extend ActiveSupport::Concern

  private
    def paginate(collection, per_page: 25)
      page = params[:page].to_i.clamp(1..)
      offset = (page - 1) * per_page

      collection.limit(per_page).offset(offset)
    end

    def pagination_meta(collection, per_page: 25)
      total = collection.count
      page = params[:page].to_i.clamp(1..)

      {
        current_page: page,
        per_page: per_page,
        total_pages: (total.to_f / per_page).ceil,
        total_count: total
      }
    end
end
```

---

## Job Concerns

### SMTP Error Handling

```ruby
# app/jobs/concerns/smtp_delivery_error_handling.rb
module SmtpDeliveryErrorHandling
  extend ActiveSupport::Concern

  included do
    # Retry delivery to possibly-unavailable remote mailservers
    retry_on Net::OpenTimeout, Net::ReadTimeout, Socket::ResolutionError,
      wait: :polynomially_longer

    # Net::SMTPServerBusy is SMTP error code 4xx (temporary error)
    retry_on Net::SMTPServerBusy, wait: :polynomially_longer

    # SMTP syntax errors (50x)
    rescue_from Net::SMTPSyntaxError do |error|
      case error.message
      when /\A501 5\.1\.3/
        # Ignore undeliverable email addresses, but log for monitoring
        Sentry.capture_exception error, level: :info
      else
        raise
      end
    end

    # SMTP fatal errors (5xx)
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

---

## Concern Patterns

### Dependency Injection

```ruby
module Notifiable
  extend ActiveSupport::Concern

  # Including class must implement notify_users method
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
```

### Configuration

```ruby
module Configurable
  extend ActiveSupport::Concern

  included do
    class_attribute :config, default: {}
  end

  class_methods do
    def configure(&block)
      self.config = config.dup
      yield config
    end
  end
end

# Usage:
class Card < ApplicationRecord
  include Configurable

  configure do |config|
    config[:auto_close_after] = 30.days
    config[:max_attachments] = 10
  end
end
```

### State Machine (Simple)

```ruby
module Stateful
  extend ActiveSupport::Concern

  included do
    validates :state, inclusion: { in: states }
  end

  class_methods do
    def states
      @states ||= []
    end

    def state(name, &block)
      states << name.to_s

      define_method("#{name}?") do
        state == name.to_s
      end

      define_method("#{name}!") do
        update!(state: name.to_s)
      end
    end
  end
end

# Usage:
class Order < ApplicationRecord
  include Stateful

  state :pending
  state :processing
  state :shipped
  state :delivered
end

order.pending?      # => true
order.processing!   # => updates state to processing
```

---

## Best Practices

### ✅ DO

1. **Extract features to concerns**
```ruby
# app/models/card.rb
include Closeable, Pinnable, Taggable
```

2. **Use namespacing for model-specific concerns**
```ruby
# app/models/card/closeable.rb
module Card::Closeable
```

3. **Keep concerns focused**
   - One responsibility per concern
   - Clear, descriptive names

4. **Use class_methods block**
```ruby
class_methods do
  def find_stale
    # ...
  end
end
```

5. **Document required methods**
```ruby
# Including class must implement:
# - search_title
# - search_content
```

6. **Use transactions in action methods**
```ruby
def close
  transaction do
    create_closure!
    track_event :closed
  end
end
```

7. **Test concerns independently**

### ❌ DON'T

1. **God concerns** - Keep focused
2. **Complex dependencies** - Keep concerns independent
3. **Deep nesting** - Avoid concerns including concerns
4. **Mixing responsibilities** - One concern = one feature
5. **Skipping documentation** - Document required methods

---

## Testing Concerns

### Model Concern Test

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

  test "closed scope returns closed cards" do
    card = cards(:logo)
    card.close

    assert_includes Card.closed, card
    assert_not_includes Card.open, card
  end
end
```

### Controller Concern Test

```ruby
# test/controllers/concerns/authentication_test.rb
class AuthenticationTest < ActionDispatch::IntegrationTest
  class TestController < ApplicationController
    include Authentication

    def index
      head :ok
    end

    def public_action
      head :ok
    end

    allow_unauthenticated_access only: :public_action
  end

  setup do
    Rails.application.routes.draw do
      get "test/index" => "authentication_test/test#index"
      get "test/public_action" => "authentication_test/test#public_action"
    end
  end

  teardown do
    Rails.application.reload_routes!
  end

  test "requires authentication for protected actions" do
    get "/test/index"

    assert_redirected_to new_session_path
  end

  test "allows unauthenticated access to public actions" do
    get "/test/public_action"

    assert_response :success
  end

  test "authenticated user can access protected actions" do
    sign_in_as :david

    get "/test/index"

    assert_response :success
  end
end
```

---

## Summary

- **Model Concerns**: Extract features (`Card::Closeable`) or shared behavior (`Searchable`)
- **Controller Concerns**: Authentication, scoping, shared actions
- **Structure**: `included do`, `class_methods`, instance methods, private methods
- **Focused**: One responsibility per concern
- **Documented**: Document required methods for including classes
- **Tested**: Test concerns independently and in context
- **Organized**: Model-specific in `model/`, shared in `concerns/`
