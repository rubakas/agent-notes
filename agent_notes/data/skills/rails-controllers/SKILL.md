---
name: rails-controllers
description: "Rails controllers: structure template, concerns, parameter handling, and response patterns. Use when user is writing or editing Rails controllers."
group: rails
---

# Controllers

Comprehensive patterns and best practices for Rails controllers.

---

## Core Philosophy

1. **Thin controllers** - Delegate business logic to models
2. **Standard REST** - Use index, show, new, create, edit, update, destroy
3. **Resource actions as resources** - Not custom actions
4. **Concerns for shared behavior** - Authentication, scoping, etc.
5. **Respond to multiple formats** - HTML, JSON, Turbo Stream

---

## File Structure

```
app/controllers/
├── application_controller.rb
├── boards_controller.rb          # CRUD controller
├── cards/
│   ├── closures_controller.rb    # Resource-action controller
│   ├── goldnesses_controller.rb  # Resource-action controller
│   ├── pins_controller.rb
│   └── comments_controller.rb
└── concerns/
    ├── authentication.rb          # Shared concern
    ├── card_scoped.rb            # Scoping concern
    └── filter_scoped.rb
```

---

## Controller Structure Template

### CRUD Controller

```ruby
class BoardsController < ApplicationController
  # 1. CONCERNS (at top)
  include FilterScoped

  # 2. BEFORE ACTIONS (explicit conditions)
  before_action :set_board, except: %i[ index new create ]
  before_action :ensure_permission_to_admin_board, only: %i[ update destroy ]
  before_action :ensure_user_has_access, only: %i[ show ]

  # 3. ACTIONS (in REST order: index, show, new, create, edit, update, destroy)

  def index
    @boards = Current.user.boards.ordered
  end

  def show
    @cards = @board.cards.published.preloaded
  end

  def new
    @board = Board.new
  end

  def create
    @board = Current.user.boards.create!(board_params)

    respond_to do |format|
      format.html { redirect_to board_path(@board), notice: "Board created" }
      format.json { head :created, location: board_path(@board, format: :json) }
      format.turbo_stream { render turbo_stream: turbo_stream.prepend(:boards, @board) }
    end
  end

  def edit
    # Renders edit form
  end

  def update
    @board.update!(board_params)

    respond_to do |format|
      format.html { redirect_to board_path(@board), notice: "Board updated" }
      format.json { head :no_content }
      format.turbo_stream { render turbo_stream: turbo_stream.replace(@board, @board) }
    end
  end

  def destroy
    @board.destroy!

    respond_to do |format|
      format.html { redirect_to boards_path, notice: "Board deleted" }
      format.json { head :no_content }
      format.turbo_stream { render turbo_stream: turbo_stream.remove(@board) }
    end
  end

  # 4. PRIVATE METHODS (ordered by invocation)
  private
    def set_board
      @board = Current.user.boards.find params[:id]
    end

    def ensure_permission_to_admin_board
      unless Current.user.can_administer_board?(@board)
        head :forbidden
      end
    end

    def ensure_user_has_access
      unless @board.accessible_to?(Current.user)
        head :forbidden
      end
    end

    def board_params
      params.expect(board: [ :name, :all_access, :auto_postpone_period, :public_description ])
    end
end
```

### Resource-Action Controller (Singleton)

```ruby
# Route: resource :closure
# POST /cards/:card_id/closure     → create (close)
# DELETE /cards/:card_id/closure   → destroy (reopen)

class Cards::ClosuresController < ApplicationController
  include CardScoped  # Sets @card and @board

  def create
    @card.close(user: Current.user)  # Delegate to model

    respond_to do |format|
      format.html { redirect_back fallback_location: @card }
      format.json { head :no_content }
      format.turbo_stream { render_card_replacement }
    end
  end

  def destroy
    @card.reopen(user: Current.user)

    respond_to do |format|
      format.html { redirect_back fallback_location: @card }
      format.json { head :no_content }
      format.turbo_stream { render_card_replacement }
    end
  end
end
```

### Nested Resource Controller

```ruby
class Cards::CommentsController < ApplicationController
  include CardScoped  # Sets @card

  before_action :set_comment, only: %i[ show edit update destroy ]

  def index
    @comments = @card.comments.chronologically
  end

  def show
  end

  def create
    @comment = @card.comments.create!(comment_params.merge(creator: Current.user))

    respond_to do |format|
      format.turbo_stream
      format.json { render json: @comment, status: :created }
    end
  end

  def update
    @comment.update!(comment_params)

    respond_to do |format|
      format.turbo_stream
      format.json { head :no_content }
    end
  end

  def destroy
    @comment.destroy!

    respond_to do |format|
      format.turbo_stream { render turbo_stream: turbo_stream.remove(@comment) }
      format.json { head :no_content }
    end
  end

  private
    def set_comment
      @comment = @card.comments.find(params[:id])
    end

    def comment_params
      params.expect(comment: [ :body ])
    end
end
```

---

## Controller Concerns

### Authentication Concern

```ruby
# app/controllers/concerns/authentication.rb
module Authentication
  extend ActiveSupport::Concern

  included do
    before_action :require_account
    before_action :require_authentication

    helper_method :authenticated?, :current_user
  end

  class_methods do
    # Allow specific actions without authentication
    def allow_unauthenticated_access(**options)
      skip_before_action :require_authentication, **options
      before_action :resume_session, **options
    end

    # Require unauthenticated (for login pages)
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
      unless authenticated?
        redirect_to new_session_path
      end
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
      if authenticated?
        redirect_to root_path
      end
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
      unless Current.account.feature_enabled?(controller_name)
        head :forbidden
      end
    end
end
```

---

## Parameter Handling

### Rails 8+ params.expect

Rails 8 introduced `params.expect` as the modern, safer alternative to `params.require().permit()`.

**Key difference:** `expect` renders a 400 Bad Request response for malformed params (production-friendly), while `expect!` raises an exception (for debugging/internal APIs).

```ruby
# Simple parameters
def board_params
  params.expect(board: [ :name, :description ])
end

# Nested parameters
def card_params
  params.expect(card: [ :title, :status, { tag_ids: [] } ])
end

# Multiple nested levels
def user_params
  params.expect(user: [
    :name,
    :email,
    :role,
    {
      avatar: [:image],
      preferences: [:theme, :notifications]
    }
  ])
end
```

**expect vs expect!**

```ruby
# expect - Production use (returns 400 response for malformed params)
def create
  @board = Board.create!(board_params)
end

private
  def board_params
    params.expect(board: [ :name, :description ])
  end
  # Missing or malformed params → renders 400 Bad Request

# expect! - Debugging/Internal APIs (raises exception)
def board_params
  params.expect!(board: [ :name, :description ])
end
# Missing or malformed params → raises ActionController::ParameterMissing
```

**Legacy pattern (Rails 7 and earlier)**

```ruby
# Still works in Rails 8, but expect is preferred
def board_params
  params.require(:board).permit(:name, :description, :all_access)
end
```

### Parameter Sanitization

```ruby
private
  def sanitized_tag_title_param
    params.required(:tag_title).strip.gsub(/\A#/, "")
  end

  def sanitized_email_param
    params.required(:email).downcase.strip
  end

  def normalized_url_param
    url = params.required(:url)
    url = "https://#{url}" unless url.start_with?("http")
    url
  end
```

---

## Response Patterns

### Multi-Format Responses

```ruby
def create
  @board = Board.create!(board_params)

  respond_to do |format|
    format.html { redirect_to board_path(@board), notice: "Created!" }
    format.json { render json: @board, status: :created }
    format.turbo_stream { render turbo_stream: turbo_stream.prepend(:boards, @board) }
  end
end
```

### Redirect Patterns

```ruby
# Basic redirect
redirect_to board_path(@board)

# With notice/alert
redirect_to @board, notice: "Board created"
redirect_to @board, alert: "Something went wrong"

# Redirect back with fallback
redirect_back fallback_location: @board

# Conditional redirect
if @board.accessible_to?(Current.user)
  redirect_to @board
else
  redirect_to boards_path
end

# Turbo-aware redirect
redirect_to @board, status: :see_other  # Forces GET request in Turbo
```

### Status Codes

```ruby
# Success
head :ok                    # 200
head :created              # 201
head :no_content           # 204

# Client errors
head :bad_request          # 400
head :unauthorized         # 401
head :forbidden            # 403
head :not_found            # 404
head :unprocessable_entity # 422

# Server errors
head :internal_server_error # 500

# With location
head :created, location: board_path(@board)
```

### Turbo Stream Responses

```ruby
# Replace element
render turbo_stream: turbo_stream.replace(@card, partial: "cards/card")

# Update element
render turbo_stream: turbo_stream.update(@card, partial: "cards/card")

# Append/Prepend
render turbo_stream: turbo_stream.append(:cards, @card)
render turbo_stream: turbo_stream.prepend(:cards, @card)

# Remove
render turbo_stream: turbo_stream.remove(@card)

# Multiple actions
render turbo_stream: [
  turbo_stream.replace(@card, @card),
  turbo_stream.update(:sidebar, partial: "cards/sidebar")
]
```

---
