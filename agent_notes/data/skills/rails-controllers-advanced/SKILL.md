---
name: rails-controllers-advanced
description: "Rails controllers advanced: error handling, filters, streaming, API patterns, security, and testing"
group: rails
---

# Controllers (Advanced)

## Error Handling

### Rescue from Exceptions

```ruby
class ApplicationController < ActionController::Base
  # Rescue specific errors
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
```

### Handling Validation Errors

```ruby
def create
  @board = Board.new(board_params)

  if @board.save
    redirect_to @board, notice: "Created!"
  else
    render :new, status: :unprocessable_entity
  end
end

# With create! (raises exception)
def create
  @board = Board.create!(board_params)
  redirect_to @board, notice: "Created!"
rescue ActiveRecord::RecordInvalid
  render :new, status: :unprocessable_entity
end
```

---

## Before/After/Around Actions

### Before Actions

```ruby
# Run before specific actions
before_action :set_board, only: %i[ show edit update destroy ]
before_action :set_board, except: %i[ index new create ]

# Run for all actions
before_action :require_authentication

# Conditional
before_action :check_admin, if: :admin_required?

# With Proc
before_action -> { redirect_to root_path unless admin? }, only: :admin_dashboard
```

### After Actions

```ruby
after_action :log_action
after_action :set_cache_headers, only: :show

private
  def log_action
    Rails.logger.info "Action: #{action_name} by #{Current.user&.email}"
  end

  def set_cache_headers
    expires_in 5.minutes, public: true
  end
```

### Around Actions

```ruby
around_action :wrap_in_transaction, only: :complex_operation

private
  def wrap_in_transaction
    ActiveRecord::Base.transaction do
      yield
    end
  end
```

### Skip Actions

```ruby
skip_before_action :require_authentication, only: :public_page
skip_after_action :log_action, only: :health_check
```

---

## Flash Messages

```ruby
# Set flash
redirect_to @board, notice: "Board created"
redirect_to @board, alert: "Something went wrong"

# Custom flash keys
redirect_to @board, flash: { warning: "Please verify your email" }

# Flash.now (doesn't persist to next request)
def create
  @board = Board.new(board_params)
  if @board.save
    redirect_to @board
  else
    flash.now[:alert] = "Could not create board"
    render :new
  end
end

# Keep flash for another request
flash.keep(:notice)
```

---

## Streaming & Live Updates

### Turbo Streams

```ruby
# In controller
def create
  @comment = @card.comments.create!(comment_params)

  respond_to do |format|
    format.turbo_stream  # Renders create.turbo_stream.erb
  end
end
```

### Server-Sent Events

```ruby
def stream
  response.headers["Content-Type"] = "text/event-stream"

  sse = SSE.new(response.stream)

  begin
    loop do
      sse.write({ message: "Hello" })
      sleep 1
    end
  rescue IOError
    # Client disconnected
  ensure
    sse.close
  end
end
```

---

## Performance Patterns

### Eager Loading

```ruby
def index
  @cards = Card.includes(:creator, :tags, :assignees)
    .preload(board: :columns)
    .where(board: Current.user.boards)
end
```

### Caching

```ruby
# Fragment caching (in view)
<% cache @board do %>
  <%= render @board %>
<% end %>

# HTTP caching
def show
  fresh_when etag: @board, last_modified: @board.updated_at, public: true
end

# Stale check
def show
  if stale?(@board)
    # Render view
  end
end
```

### Pagination

```ruby
def index
  @cards = Card.page(params[:page]).per(25)
end
```

---

## API Patterns

### JSON API Responses

```ruby
def show
  render json: @board
end

def create
  @board = Board.create!(board_params)
  render json: @board, status: :created, location: @board
end

# With serializer/Jbuilder
render json: @board, serializer: BoardSerializer
# or
render :show  # Uses show.json.jbuilder
```

### API Error Responses

```ruby
rescue_from ActiveRecord::RecordInvalid do |exception|
  render json: {
    error: "Validation failed",
    details: exception.record.errors.full_messages
  }, status: :unprocessable_entity
end

rescue_from ActiveRecord::RecordNotFound do
  render json: { error: "Not found" }, status: :not_found
end
```

### API Versioning

```ruby
# Namespace approach
namespace :api do
  namespace :v1 do
    resources :boards
  end
end

# Or header-based (in ApplicationController)
before_action :set_api_version

private
  def set_api_version
    @api_version = request.headers["X-API-Version"] || "v1"
  end
```

---

## Security Patterns

### CSRF Protection

```ruby
# Enabled by default
class ApplicationController < ActionController::Base
  protect_from_forgery with: :exception
end

# Skip for API endpoints
class ApiController < ApplicationController
  skip_before_action :verify_authenticity_token
end
```

### Strong Parameters

```ruby
# Only permitted params get through
def board_params
  params.expect(board: [ :name, :description ])
end

# Attempting to pass other params will raise ActionController::ParameterMissing
```

### Authorization Checks

```ruby
before_action :ensure_owner, only: %i[ destroy ]

private
  def ensure_owner
    unless @board.owner?(Current.user)
      head :forbidden
    end
  end
```

---

## Testing Controllers

```ruby
class BoardsControllerTest < ActionDispatch::IntegrationTest
  setup do
    sign_in_as :kevin
  end

  test "index shows user's boards" do
    get boards_path

    assert_response :success
    assert_select "h1", "Boards"
  end

  test "create creates board" do
    assert_difference -> { Board.count }, +1 do
      post boards_path, params: { board: { name: "New Board" } }
    end

    assert_redirected_to board_path(Board.last)
    assert_equal "New Board", Board.last.name
  end

  test "update updates board" do
    board = boards(:writebook)

    patch board_path(board), params: { board: { name: "Updated" } }

    assert_redirected_to board_path(board)
    assert_equal "Updated", board.reload.name
  end

  test "destroy removes board" do
    board = boards(:writebook)

    assert_difference -> { Board.count }, -1 do
      delete board_path(board)
    end

    assert_redirected_to boards_path
  end

  test "non-admin cannot update board" do
    logout_and_sign_in_as :member

    board = boards(:writebook)
    original_name = board.name

    patch board_path(board), params: { board: { name: "Hacked" } }

    assert_response :forbidden
    assert_equal original_name, board.reload.name
  end

  test "turbo stream response on create" do
    post boards_path,
      params: { board: { name: "Test" } },
      as: :turbo_stream

    assert_response :success
    assert_match "turbo-stream", response.body
  end

  test "json response includes board data" do
    board = boards(:writebook)

    get board_path(board), as: :json

    assert_response :success
    json = JSON.parse(response.body)
    assert_equal board.name, json["name"]
  end
end
```

---

## Best Practices

### DO

1. **Keep controllers thin** - Delegate to models
2. **Use concerns for shared behavior**
3. **Respond to multiple formats**
4. **Use strong parameters**
5. **Test permissions thoroughly**
6. **Return appropriate status codes**
7. **Use before_action for setup**

### DON'T

1. **Business logic in controllers** - Belongs in models
2. **Multiple responsibilities** - One resource per controller
3. **Complex queries** - Use model scopes
4. **Rescue exceptions broadly** - Be specific
5. **Skip CSRF protection** - Unless API
6. **Fat controllers** - Extract to concerns/models

---

## Summary

- **Structure**: Concerns, before_actions, REST actions, private methods
- **Delegation**: Controllers delegate to models
- **Responses**: Multi-format with appropriate status codes
- **Security**: Strong parameters, CSRF, authorization
- **Testing**: Test happy path, edge cases, and permissions
- **Performance**: Eager loading, caching, pagination
