# Routes

Comprehensive patterns and best practices for Rails routing.

---

## Core Philosophy

1. **RESTful resources** - Everything is a resource
2. **Actions as resources** - Model toggles/actions as singleton resources
3. **Zero custom actions** - No `post :custom_action`
4. **Nested resources** - Show relationships in URLs
5. **Clean URLs** - Use `scope module:` to organize without URL clutter

---

## Basic Resource Routing

### Standard CRUD Resources

```ruby
resources :boards
# Generates:
# GET    /boards          → boards#index
# GET    /boards/new      → boards#new
# POST   /boards          → boards#create
# GET    /boards/:id      → boards#show
# GET    /boards/:id/edit → boards#edit
# PATCH  /boards/:id      → boards#update
# DELETE /boards/:id      → boards#destroy
```

### Limit Actions

```ruby
resources :boards, only: %i[ index show create ]
resources :exports, only: %i[ create show ]
resources :tags, only: :index

resources :boards, except: %i[ destroy ]
```

### Singleton Resources

```ruby
resource :session  # No :id in URL
# Generates:
# GET    /session/new    → sessions#new
# POST   /session        → sessions#create
# GET    /session        → sessions#show
# GET    /session/edit   → sessions#edit
# PATCH  /session        → sessions#update
# DELETE /session        → sessions#destroy
```

---

## The Core Pattern: Actions as Resources

### ❌ Bad - Custom Actions

```ruby
resources :cards do
  post :close
  post :reopen
  post :gild
  post :ungild
  post :pin
  delete :unpin
end
```

### ✅ Good - Actions as Resources

```ruby
resources :cards do
  scope module: :cards do
    resource :closure   # POST = close, DELETE = reopen
    resource :goldness  # POST = gild, DELETE = ungild
    resource :pin       # POST = pin, DELETE = unpin
  end
end

# URLs:
# POST   /cards/:card_id/closure   → Cards::ClosuresController#create
# DELETE /cards/:card_id/closure   → Cards::ClosuresController#destroy
# POST   /cards/:card_id/goldness  → Cards::GoldnessesController#create
# DELETE /cards/:card_id/goldness  → Cards::GoldnessesController#destroy
```

---

## Nested Resources

### Basic Nesting

```ruby
resources :boards do
  resources :cards
end

# Generates:
# GET  /boards/:board_id/cards     → cards#index
# POST /boards/:board_id/cards     → cards#create
# GET  /boards/:board_id/cards/:id → cards#show
```

### Shallow Nesting

```ruby
resources :boards do
  resources :cards, shallow: true
end

# Generates:
# POST   /boards/:board_id/cards     → cards#create  (nested)
# GET    /cards/:id                  → cards#show    (shallow)
# PATCH  /cards/:id                  → cards#update  (shallow)
# DELETE /cards/:id                  → cards#destroy (shallow)

# Why? Because cards/:id is enough to identify the resource
```

### Multiple Levels

```ruby
resources :boards do
  resources :cards do
    resources :comments
  end
end

# But consider shallow nesting or limiting depth
resources :boards do
  resources :cards, shallow: true do
    resources :comments, shallow: true
  end
end
```

---

## Organization with scope module:

### Keep URLs Clean

```ruby
# Without scope module: (repetitive)
resources :cards do
  resource :closure, controller: "cards/closures"
  resource :goldness, controller: "cards/goldnesses"
  resource :pin, controller: "cards/pins"
end

# With scope module: (clean)
resources :cards do
  scope module: :cards do
    resource :closure
    resource :goldness
    resource :pin

    resources :comments
    resources :taggings
  end
end

# URLs: /cards/:card_id/closure
# Controllers: Cards::ClosuresController
```

### Nested Scope Modules

```ruby
resources :cards do
  scope module: :cards do
    resources :comments do
      # Reactions belong to comments
      resources :reactions, module: :comments
    end
  end
end

# URL: /cards/:card_id/comments/:comment_id/reactions
# Controller: Cards::Comments::ReactionsController
```

---

## Namespace vs Scope Module

### namespace (affects both URL and controller)

```ruby
namespace :admin do
  resources :users
end

# URL: /admin/users
# Controller: Admin::UsersController
```

### scope module (controller only)

```ruby
scope module: :cards do
  resource :closure
end

# URL: /closure
# Controller: Cards::ClosuresController
```

### scope path (URL only)

```ruby
scope path: :admin do
  resources :users
end

# URL: /admin/users
# Controller: UsersController
```

---

## Collection vs Member Routes

### Member Routes (act on specific resource)

```ruby
resources :boards do
  member do
    post :archive    # POST /boards/:id/archive
  end
end

# Better: Model as resource
resources :boards do
  resource :archive
end
```

### Collection Routes (act on collection)

```ruby
resources :cards do
  collection do
    get :search     # GET /cards/search
  end
end

# Or use namespace
namespace :cards do
  resources :searches
end
```

---

## Custom Routes

### Root Route

```ruby
root "events#index"
```

### Simple Routes

```ruby
get "about", to: "pages#about"
post "contact", to: "contacts#create"

# With constraints
get "signup", to: "signups#new", constraints: { subdomain: "www" }
```

### Direct Routes

```ruby
# Create helper method with custom URL
direct :published_board do |board, options|
  route_for :public_board, board.publication.key
end

# Usage in views/controllers:
published_board_url(@board)
# => /b/abc123xyz
```

### Resolve Routes (Polymorphic)

```ruby
# Map model to specific route
resolve "Event" do |event, options|
  polymorphic_url(event.eventable, options)
end

resolve "Comment" do |comment, options|
  options[:anchor] = ActionView::RecordIdentifier.dom_id(comment)
  route_for :card, comment.card, options
end

# Usage:
url_for(@event)
# => Routes to event.eventable (e.g., card_url(@event.eventable))

link_to "View", @comment
# => Routes to card with anchor #comment_123
```

---

## RESTful Route Patterns

### Resource Routes (Complete Example)

```ruby
resources :cards do
  scope module: :cards do
    # Singleton resources (toggles/state)
    resource :board        # Moving to different board
    resource :closure      # Closing/reopening
    resource :column       # Moving to column
    resource :goldness     # Gilding/ungilding
    resource :image        # Uploading/removing image
    resource :not_now      # Postponing
    resource :pin          # Pinning/unpinning
    resource :publish      # Publishing drafts
    resource :triage       # Moving to/from triage
    resource :watch        # Watching/unwatching

    # Collection resources (CRUD)
    resources :assignments
    resources :steps
    resources :taggings
    resources :comments do
      resources :reactions, module: :comments
    end
  end
end
```

### Boards Routes

```ruby
resources :boards do
  scope module: :boards do
    # Singleton resources
    resource :subscriptions
    resource :involvement
    resource :publication
    resource :entropy

    # Nested namespace
    namespace :columns do
      resource :not_now
      resource :stream
      resource :closed
    end

    resources :columns
  end

  # Only create action for cards (cards belong to boards)
  resources :cards, only: :create

  resources :webhooks do
    scope module: :webhooks do
      resource :activation, only: :create
    end
  end
end
```

---

## Route Constraints

### Parameter Constraints

```ruby
resources :boards, constraints: { id: /\d+/ }

get "/:username", to: "profiles#show",
  constraints: { username: /[a-zA-Z0-9_]+/ }
```

### Request Constraints

```ruby
get "mobile", to: "pages#mobile",
  constraints: { user_agent: /Mobile|Tablet/ }

namespace :admin, constraints: { subdomain: "admin" } do
  resources :users
end
```

### Custom Constraint Classes

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

## Route Concerns

### Define Reusable Route Patterns

```ruby
concern :commentable do
  resources :comments
end

concern :likeable do
  resource :like
end

# Use in resources
resources :posts, concerns: %i[ commentable likeable ]
resources :articles, concerns: %i[ commentable likeable ]

# Equivalent to:
resources :posts do
  resources :comments
  resource :like
end
```

---

## Scope and Path Helpers

### Custom Path Names

```ruby
resources :boards, path: "collections"
# URL: /collections
# Helpers: boards_path, board_path

resource :session, path: "login"
# URL: /login
# Helper: session_path
```

### Custom Helper Names

```ruby
resources :boards, as: :collections
# URL: /boards
# Helpers: collections_path, collection_path
```

---

## Route Helpers

### Path vs URL Helpers

```ruby
boards_path          # => "/boards"
boards_url           # => "http://example.com/boards"

board_path(@board)   # => "/boards/123"
board_url(@board)    # => "http://example.com/boards/123"

new_board_path       # => "/boards/new"
edit_board_path(@board)  # => "/boards/123/edit"
```

### Nested Resource Helpers

```ruby
board_cards_path(@board)        # => "/boards/123/cards"
board_card_path(@board, @card)  # => "/boards/123/cards/456"

# With shallow: true
card_path(@card)               # => "/cards/456"
```

### Custom Parameters

```ruby
board_path(@board, format: :json)        # => "/boards/123.json"
boards_path(page: 2, per: 25)           # => "/boards?page=2&per=25"
card_path(@card, anchor: "comments")    # => "/cards/123#comments"
```

---

## Multi-Tenancy with URL Path Scoping

### URL Structure

```ruby
# Middleware extracts account_id from URL
# /{account_id}/boards/...

# In routes.rb - routes are defined normally
resources :boards
# But URLs become: /{account_id}/boards

# How it works:
# 1. Middleware (AccountSlug::Extractor) extracts account_id
# 2. Moves slug from PATH_INFO to SCRIPT_NAME
# 3. Rails thinks it's "mounted" at /{account_id}
# 4. All URL helpers automatically include account_id
```

### Untenanted Routes

```ruby
# For routes outside account context (login, signup)
scope :untenanted do
  resource :session
  resource :signup
end

# Or in controller:
def new
  untenanted do
    redirect_to new_session_url
  end
end
```

---

## Redirect Routes

### Simple Redirects

```ruby
get "/old-path", to: redirect("/new-path")
get "/old-path", to: redirect("/new-path", status: 301)  # Permanent

# With parameters
get "/articles/:id", to: redirect("/posts/%{id}")
```

### Dynamic Redirects

```ruby
# Legacy URLs
get "/collections/:collection_id/cards/:id",
  to: redirect { |params, request|
    "#{request.script_name}/cards/#{params[:id]}"
  }

get "/collections/:id",
  to: redirect { |params, request|
    "#{request.script_name}/boards/#{params[:id]}"
  }
```

---

## API Versioning

### Namespace Versioning

```ruby
namespace :api do
  namespace :v1 do
    resources :boards
    resources :cards
  end

  namespace :v2 do
    resources :boards
    resources :cards
  end
end

# URLs: /api/v1/boards, /api/v2/boards
```

### Header-Based Versioning

```ruby
# Use constraints
scope module: :api do
  scope module: :v1, constraints: ApiVersionConstraint.new(1) do
    resources :boards
  end

  scope module: :v2, constraints: ApiVersionConstraint.new(2, default: true) do
    resources :boards
  end
end

# ApiVersionConstraint class
class ApiVersionConstraint
  def initialize(version, default: false)
    @version = version
    @default = default
  end

  def matches?(request)
    @default || request.headers["X-API-Version"] == "v#{@version}"
  end
end
```

---

## Testing Routes

### Route Tests

```ruby
# test/routing/cards_routing_test.rb
class CardsRoutingTest < ActionDispatch::IntegrationTest
  test "routes to cards#create" do
    assert_routing(
      { method: :post, path: "/boards/1/cards" },
      { controller: "cards", action: "create", board_id: "1" }
    )
  end

  test "routes to closure#create" do
    assert_routing(
      { method: :post, path: "/cards/1/closure" },
      { controller: "cards/closures", action: "create", card_id: "1" }
    )
  end
end
```

### Route Helper Tests

```ruby
test "board_path generates correct path" do
  board = boards(:writebook)
  assert_equal "/boards/#{board.id}", board_path(board)
end

test "card_closure_path generates correct path" do
  card = cards(:logo)
  assert_equal "/cards/#{card.number}/closure", card_closure_path(card)
end
```

---

## Debugging Routes

### Rails Console

```ruby
# List all routes
Rails.application.routes.routes.map(&:path).map(&:spec).sort.uniq

# Find route by helper
Rails.application.routes.url_helpers.boards_path
# => "/boards"

# Find routes matching pattern
Rails.application.routes.routes.select { |r| r.path.spec.to_s =~ /cards/ }

# Route recognition
Rails.application.routes.recognize_path("/boards/123")
# => { controller: "boards", action: "show", id: "123" }
```

### bin/rails routes

```bash
# All routes
bin/rails routes

# Filter by controller
bin/rails routes -c boards

# Filter by pattern
bin/rails routes -g closure

# Expanded format
bin/rails routes --expanded
```

---

## Best Practices

### ✅ DO

1. **Use RESTful resources** - Standard CRUD actions
2. **Model actions as resources** - Singleton resources for toggles
3. **Use scope module:** - Keep URLs clean, controllers namespaced
4. **Shallow nesting** - Avoid deep nesting
5. **Limit actions** - Only include needed actions
6. **Use concerns** - DRY up repeated patterns
7. **Test routes** - Ensure correct routing

### ❌ DON'T

1. **Custom actions** - Use resources instead
2. **Deep nesting** - More than 2 levels
3. **Generic member/collection** - Use resources
4. **Mixing namespace and scope module** - Confusing
5. **Too many routes** - Keep focused

---

## Complete Example: Production Routes

```ruby
Rails.application.routes.draw do
  root "events#index"

  # Account settings
  namespace :account do
    resource :join_code
    resource :settings
    resource :entropy
    resources :exports, only: %i[ create show ]
  end

  # Boards
  resources :boards do
    scope module: :boards do
      resource :publication
      resource :entropy

      namespace :columns do
        resource :not_now
        resource :stream
        resource :closed
      end

      resources :columns
    end

    resources :cards, only: :create
    resources :webhooks
  end

  # Cards (main resource)
  resources :cards do
    scope module: :cards do
      # Singleton resources (state toggles)
      resource :closure
      resource :goldness
      resource :pin
      resource :publish

      # Collections
      resources :comments do
        resources :reactions, module: :comments
      end
      resources :assignments
      resources :taggings
    end
  end

  # Session
  resource :session do
    scope module: :sessions do
      resource :magic_link
      resource :menu
    end
  end

  # Direct routes
  direct :published_board do |board|
    route_for :public_board, board.publication.key
  end

  # Polymorphic resolution
  resolve "Event" do |event, options|
    polymorphic_url(event.eventable, options)
  end
end
```

---

## Summary

- **RESTful Resources**: Everything is a resource
- **Actions as Resources**: Use singleton resources, not custom actions
- **Organization**: Use `scope module:` to keep URLs clean
- **Nesting**: Shallow nesting for deep relationships
- **Zero Custom Actions**: Model everything as resources
- **Clean URLs**: Predictable, standard REST patterns
