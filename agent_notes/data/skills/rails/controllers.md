# Controllers

## Controllers — Structure

Comprehensive patterns and best practices for Rails controllers.

---

### Core Philosophy

1. **Thin controllers** - Delegate business logic to models
2. **Standard REST** - Use index, show, new, create, edit, update, destroy
3. **Resource actions as resources** - Not custom actions
4. **Concerns for shared behavior** - Authentication, scoping, etc.
5. **Respond to multiple formats** - HTML, JSON, Turbo Stream

---

### File Structure

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

### Controller Structure Template

#### CRUD Controller

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

#### Resource-Action Controller (Singleton)

```ruby
# Route: resource :closure
# POST /cards/:card_id/closure     → create (close)
# DELETE /cards/:card_id/closure   → destroy (reopen)

class Cards::ClosuresController < ApplicationController
  include CardScoped  # Sets @card and @board

  def create
    @card.close(user: Current.user)

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

#### Nested Resource Controller

```ruby
class Cards::CommentsController < ApplicationController
  include CardScoped

  before_action :set_comment, only: %i[ show edit update destroy ]

  def create
    @comment = @card.comments.create!(comment_params.merge(creator: Current.user))

    respond_to do |format|
      format.turbo_stream
      format.json { render json: @comment, status: :created }
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

### Parameter Handling

#### Rails 8+ params.expect

```ruby
# Simple parameters
def board_params
  params.expect(board: [ :name, :description ])
end

# Nested parameters
def card_params
  params.expect(card: [ :title, :status, { tag_ids: [] } ])
end

# expect - Production use (returns 400 response for malformed params)
# expect! - Debugging/Internal APIs (raises exception)

# Legacy pattern (Rails 7 and earlier)
def board_params
  params.require(:board).permit(:name, :description, :all_access)
end
```

#### Parameter Sanitization

```ruby
private
  def sanitized_tag_title_param
    params.required(:tag_title).strip.gsub(/\A#/, "")
  end

  def sanitized_email_param
    params.required(:email).downcase.strip
  end
```

---

### Response Patterns

```ruby
# Multi-format responses
respond_to do |format|
  format.html { redirect_to board_path(@board), notice: "Created!" }
  format.json { render json: @board, status: :created }
  format.turbo_stream { render turbo_stream: turbo_stream.prepend(:boards, @board) }
end

# Turbo Stream responses
render turbo_stream: turbo_stream.replace(@card, partial: "cards/card")
render turbo_stream: turbo_stream.append(:cards, @card)
render turbo_stream: turbo_stream.remove(@card)
render turbo_stream: [
  turbo_stream.replace(@card, @card),
  turbo_stream.update(:sidebar, partial: "cards/sidebar")
]

# Status codes
head :ok           # 200
head :created      # 201
head :no_content   # 204
head :forbidden    # 403
head :not_found    # 404

# Redirect patterns
redirect_to @board, notice: "Board created"
redirect_back fallback_location: @board
redirect_to @board, status: :see_other  # Forces GET request in Turbo
```

---

## Controllers — Advanced

### Error Handling

```ruby
class ApplicationController < ActionController::Base
  rescue_from ActiveRecord::RecordNotFound, with: :record_not_found
  rescue_from ActiveRecord::RecordInvalid, with: :record_invalid
  rescue_from ActionController::ParameterMissing, with: :parameter_missing

  private
    def record_not_found
      respond_to do |format|
        format.html { redirect_to root_path, alert: "Not found" }
        format.json { head :not_found }
      end
    end

    def record_invalid(exception)
      @errors = exception.record.errors

      respond_to do |format|
        format.html { render :edit, status: :unprocessable_entity }
        format.json { render json: { errors: @errors }, status: :unprocessable_entity }
      end
    end

    def parameter_missing(exception)
      respond_to do |format|
        format.html { redirect_back fallback_location: root_path, alert: "Invalid request" }
        format.json { render json: { error: exception.message }, status: :bad_request }
      end
    end
end

# Handling validation errors inline
def create
  @board = Board.new(board_params)

  if @board.save
    redirect_to @board, notice: "Created!"
  else
    render :new, status: :unprocessable_entity
  end
end
```

---

### Before/After/Around Actions

```ruby
before_action :set_board, only: %i[ show edit update destroy ]
before_action :require_authentication
before_action :check_admin, if: :admin_required?

after_action :log_action
after_action :set_cache_headers, only: :show

around_action :wrap_in_transaction, only: :complex_operation

skip_before_action :require_authentication, only: :public_page

private
  def wrap_in_transaction
    ActiveRecord::Base.transaction do
      yield
    end
  end
```

---

### Flash Messages

```ruby
redirect_to @board, notice: "Board created"
redirect_to @board, alert: "Something went wrong"
redirect_to @board, flash: { warning: "Please verify your email" }

# flash.now (doesn't persist to next request)
flash.now[:alert] = "Could not create board"
render :new

flash.keep(:notice)  # Keep for another request
```

---

### Performance Patterns

```ruby
# Eager Loading
def index
  @cards = Card.includes(:creator, :tags, :assignees)
    .preload(board: :columns)
    .where(board: Current.user.boards)
end

# HTTP caching
def show
  fresh_when etag: @board, last_modified: @board.updated_at, public: true
end

# Pagination
def index
  @cards = Card.page(params[:page]).per(25)
end
```

---

### API Patterns

```ruby
# JSON API Responses
def show
  render json: @board
end

def create
  @board = Board.create!(board_params)
  render json: @board, status: :created, location: @board
end

# API Error Responses
rescue_from ActiveRecord::RecordInvalid do |exception|
  render json: {
    error: "Validation failed",
    details: exception.record.errors.full_messages
  }, status: :unprocessable_entity
end

# API Versioning
namespace :api do
  namespace :v1 do
    resources :boards
  end
end
```

---

### Security Patterns

```ruby
# CSRF Protection
class ApplicationController < ActionController::Base
  protect_from_forgery with: :exception
end

# Skip for API endpoints
class ApiController < ApplicationController
  skip_before_action :verify_authenticity_token
end

# Authorization checks
before_action :ensure_owner, only: %i[ destroy ]

private
  def ensure_owner
    unless @board.owner?(Current.user)
      head :forbidden
    end
  end
```

---

## Routes

Comprehensive patterns and best practices for Rails routing.

### Core Philosophy

1. **RESTful resources** - Everything is a resource
2. **Actions as resources** - Model toggles/actions as singleton resources
3. **Zero custom actions** - No `post :custom_action`
4. **Nested resources** - Show relationships in URLs
5. **Clean URLs** - Use `scope module:` to organize without URL clutter

---

### Basic Resource Routing

```ruby
# Standard CRUD Resources
resources :boards
# GET /boards, GET /boards/new, POST /boards, GET /boards/:id,
# GET /boards/:id/edit, PATCH /boards/:id, DELETE /boards/:id

# Limit Actions
resources :boards, only: %i[ index show create ]
resources :boards, except: %i[ destroy ]

# Singleton Resources
resource :session  # No :id in URL
```

---

### The Core Pattern: Actions as Resources

```ruby
# BAD - Custom Actions
resources :cards do
  post :close
  post :reopen
  post :gild
end

# GOOD - Actions as Resources
resources :cards do
  scope module: :cards do
    resource :closure   # POST = close, DELETE = reopen
    resource :goldness  # POST = gild, DELETE = ungild
    resource :pin       # POST = pin, DELETE = unpin
  end
end

# URLs: /cards/:card_id/closure
# Controllers: Cards::ClosuresController
```

---

### Nested Resources

```ruby
# Basic Nesting
resources :boards do
  resources :cards
end

# Shallow Nesting
resources :boards do
  resources :cards, shallow: true
end

# scope module: keeps URLs clean, controllers namespaced
resources :cards do
  scope module: :cards do
    resource :closure
    resource :goldness
    resource :pin
    resources :comments
    resources :taggings
  end
end
```

---

### Namespace vs Scope Module

```ruby
namespace :admin do
  resources :users
end
# URL: /admin/users, Controller: Admin::UsersController

scope module: :cards do
  resource :closure
end
# URL: /closure, Controller: Cards::ClosuresController

scope path: :admin do
  resources :users
end
# URL: /admin/users, Controller: UsersController
```

---

### Custom Routes

```ruby
root "events#index"
get "about", to: "pages#about"

# Direct routes
direct :published_board do |board, options|
  route_for :public_board, board.publication.key
end

# Resolve routes (polymorphic)
resolve "Event" do |event, options|
  polymorphic_url(event.eventable, options)
end

resolve "Comment" do |comment, options|
  options[:anchor] = ActionView::RecordIdentifier.dom_id(comment)
  route_for :card, comment.card, options
end

# Redirects
get "/old-path", to: redirect("/new-path")
get "/collections/:collection_id/cards/:id",
  to: redirect { |params, request|
    "#{request.script_name}/cards/#{params[:id]}"
  }
```

---

### Route Constraints

```ruby
class AdminConstraint
  def matches?(request)
    user_id = request.session[:user_id]
    user = User.find_by(id: user_id)
    user && user.admin?
  end
end

namespace :admin, constraints: AdminConstraint.new do
  resources :users
end
```

---

### Route Concerns

```ruby
concern :commentable do
  resources :comments
end

resources :posts, concerns: %i[ commentable ]
resources :articles, concerns: %i[ commentable ]
```

---

### Debugging Routes

```bash
bin/rails routes
bin/rails routes -c boards
bin/rails routes -g closure
bin/rails routes --expanded
```

---

## Helpers

Comprehensive guide for Rails view helpers.

### Philosophy

1. **Helpers are for view logic only** - Not business logic
2. **Domain-specific helpers** - One helper per resource
3. **Tag builders over string concatenation** - Use `tag` helpers
4. **No database queries** - Pass data from controller

---

### Application Helper

```ruby
module ApplicationHelper
  def page_title_tag
    parts = [@page_title, Current.account&.name, "My App"].compact
    tag.title parts.join(" | ")
  end

  def icon_tag(name, **options)
    tag.span(
      class: class_names("icon icon--#{name}", options.delete(:class)),
      "aria-hidden": true,
      **options
    )
  end

  def flash_messages
    flash.map do |type, message|
      tag.div(message, class: "alert alert-#{type}", role: "alert")
    end.join.html_safe
  end

  def nav_link_to(text, path, **options)
    active = current_page?(path)
    css_class = class_names(options.delete(:class), "active" => active)
    link_to text, path, class: css_class, **options
  end
end
```

---

### Domain-Specific Helpers

```ruby
# app/helpers/cards_helper.rb
module CardsHelper
  def card_article_tag(card, **options, &block)
    classes = [
      options.delete(:class),
      ("golden-effect" if card.golden?),
      ("card--postponed" if card.postponed?)
    ].compact.join(" ")

    tag.article(
      id: dom_id(card),
      style: "--card-color: #{card.color}",
      class: classes,
      **options,
      &block
    )
  end

  def card_status_badge(card)
    tag.span(
      card.status.humanize,
      class: "badge badge-#{card.status}"
    )
  end
end
```

---

### Form Helpers

```ruby
module FormsHelper
  def form_errors_for(model)
    return unless model.errors.any?

    tag.div class: "error-messages" do
      tag.h3("#{pluralize(model.errors.count, "error")} prohibited this from being saved:") +
      tag.ul do
        model.errors.full_messages.map { |msg| tag.li(msg) }.join.html_safe
      end
    end
  end

  def field_with_errors(model, attribute, &block)
    css_class = model.errors[attribute].any? ? "field field-with-errors" : "field"

    tag.div class: css_class do
      capture(&block) +
        (model.errors[attribute].any? ? tag.span(model.errors[attribute].join(", "), class: "error") : "".html_safe)
    end
  end
end
```

---

### Time Helpers

```ruby
module TimeHelper
  def local_datetime_tag(datetime, style: :time, **attributes)
    tag.time(
      "&nbsp;".html_safe,
      **attributes,
      datetime: datetime.to_i,
      data: {
        local_time_target: style,
        action: "turbo:morph-element->local-time#refreshTarget"
      }
    )
  end

  def relative_time_tag(datetime, **options)
    tag.time time_ago_in_words(datetime) + " ago",
      datetime: datetime.iso8601,
      title: datetime.strftime("%B %d, %Y at %l:%M %p"),
      **options
  end
end
```

---

### Best Practices

```ruby
# DO: Use tag builders
tag.div "Content", class: "card", id: "card-1"

# DO: Domain-specific helpers
def card_status_badge(card)
  tag.span card.status, class: "badge badge-#{card.status}"
end

# DON'T: Business logic
# Bad - put in model or policy
def can_edit_card?(card)
  card.editable_by?(current_user)
end

# DON'T: Database queries in helpers
# Good - query in controller, helper formats
def recent_cards_list(cards)
  cards.map { |card| card_link(card) }.join(", ").html_safe
end
```
