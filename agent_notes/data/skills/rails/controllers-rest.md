# Controllers, REST, and Parameter Handling

## Contents

- [Core Philosophy](#core-philosophy)
- [File Structure](#file-structure)
- [CRUD Controller](#crud-controller)
- [Resource-Action Controller](#resource-action-controller)
- [Nested Resource Controller](#nested-resource-controller)
- [Parameter Handling](#parameter-handling)
- [Response Patterns](#response-patterns)
- [Controller Concerns](#controller-concerns)
- [Authorization](#authorization)
- [Sources](#sources)

## Core Philosophy

Fizzy follows the "vanilla Rails" approach in STYLE.md: thin controllers that call a rich domain model directly, with no service layer between them.

1. **Thin controllers**: delegate business logic to models.
2. **REST as the rule**: standard CRUD verbs (index, show, new, create, edit, update, destroy).
3. **Actions as resources**: a custom action becomes its own singular or nested resource.
4. **Model methods, not services**: controllers call intention-revealing model methods (`@card.gild`). Form objects such as `Signup` are used only where justified.

Why: controllers stay short because the behavior lives on the model (STYLE.md: "thin controllers directly invoking a rich domain model").

## File Structure

```
app/controllers/
├── application_controller.rb
├── boards_controller.rb            # standard CRUD
├── cards/
│   ├── closures_controller.rb      # resource-action: create closes, destroy reopens
│   ├── goldnesses_controller.rb
│   ├── pins_controller.rb
│   └── comments_controller.rb      # nested resource
└── concerns/
    ├── authentication.rb
    ├── authorization.rb
    ├── board_scoped.rb
    └── card_scoped.rb
```

Controller names follow the routes: `resources :boards` maps to `BoardsController`, and `resource :closure` inside `scope module: :cards` maps to `Cards::ClosuresController`.

Why: the file layout mirrors the route tree, so a URL leads straight to its controller (Fizzy: `config/routes.rb`).

## CRUD Controller

A standard REST controller. Authorization is a `before_action` plus scoping through the current user.

```ruby
# app/controllers/boards_controller.rb
class BoardsController < ApplicationController
  wrap_parameters :board, include: %i[ name all_access auto_postpone_period_in_days public_description ]

  include FilterScoped

  before_action :set_board, except: %i[ index new create ]
  before_action :ensure_permission_to_admin_board, only: %i[ update destroy ]
# ...
  def create
    @board = Board.create! board_params.with_defaults(all_access: true)

    respond_to do |format|
      format.html { redirect_to board_path(@board) }
      format.json { render :show, status: :created, location: board_path(@board, format: :json) }
    end
  end
# ...
end
```

```ruby
# app/controllers/boards_controller.rb
class BoardsController < ApplicationController
# ...
  private
    def set_board
      @board = Current.user.boards.find params[:id]
    end

    def ensure_permission_to_admin_board
      unless Current.user.can_administer_board?(@board)
        head :forbidden
      end
    end
# ...
end
```

**Key patterns:**
- `wrap_parameters` accepts flat JSON bodies. It names the keys to wrap, so it can be left out when clients send `{ board: { ... } }`.
- `Current.user.boards.find` scopes the lookup to boards the user can see, so a board they cannot see raises `RecordNotFound` (404).
- `ensure_permission_to_admin_board` answers `head :forbidden` for users who can see the board but cannot administer it.
- `respond_to` serves HTML and JSON from the same action: HTML redirects, JSON renders the resource or returns a status.

Why: the action calls `create!` and lets Rails turn `RecordInvalid` and `RecordNotFound` into 422 and 404 (Fizzy: `app/controllers/boards_controller.rb`).

## Resource-Action Controller

When an action does not fit a standard CRUD verb, STYLE.md introduces a new resource instead of a custom route:

```ruby
# STYLE.md
# Good
resources :cards do
  resource :closure
end
```

The closure controller is that pattern. `create` closes the card and `destroy` reopens it:

```ruby
# app/controllers/cards/closures_controller.rb
class Cards::ClosuresController < ApplicationController
  include CardScoped

  def create
    capture_card_location
    @card.close
    refresh_stream_if_needed

    respond_to do |format|
      format.turbo_stream
      format.json { head :no_content }
    end
  end
# ...
end
```

`destroy` calls `@card.reopen` the same way. The model API reads as intent (`close`, `reopen`), and the controller only chooses the response format.

Why: a new resource keeps every controller on the seven CRUD verbs (STYLE.md: "we introduce a new resource rather than adding custom actions").

## Nested Resource Controller

Children are created through the parent's association, and the child controller loads the parent with a shared concern (`CardScoped`, below).

```ruby
# config/routes.rb
      resources :comments do
        resources :reactions, module: :comments
      end
```

```ruby
# app/controllers/cards/comments_controller.rb
class Cards::CommentsController < ApplicationController
  wrap_parameters :comment, include: %i[ body created_at ]
  include CardScoped
# ...
  def create
    @comment = @card.comments.create!(comment_params)

    respond_to do |format|
      format.turbo_stream
      format.json { render :show, status: :created, location: card_comment_path(@card, @comment, format: :json) }
    end
  end
# ...
end
```

Why: plain Active Record through the association is enough (STYLE.md: "Invoking plain Active Record operations is totally fine").

## Parameter Handling

### params.expect (Rails 8.0+)

```ruby
# app/controllers/boards_controller.rb
    def board_params
      params.expect(board: [ :name, :all_access, :auto_postpone_period_in_days, :public_description ])
    end
```

`params.expect` exists since Rails 8.0. It requires the `board` key and permits the listed attributes in one call, and it raises `ActionController::ParameterMissing` (rendered as 400) when the key is missing or has the wrong shape, such as a string where a hash is expected. For a scalar, pass the key as a symbol:

```ruby
# app/controllers/sessions_controller.rb
    def email_address
      params.expect(:email_address)
    end
```

`expect!` also exists in Rails; Fizzy does not use it.

Why: one call replaces the `require(...).permit(...)` chain and rejects a malformed payload (Fizzy: `app/controllers/boards_controller.rb`).

### wrap_parameters for flat JSON

```ruby
# app/controllers/boards_controller.rb
  wrap_parameters :board, include: %i[ name all_access auto_postpone_period_in_days public_description ]
```

A client that sends `{ "name": "...", "all_access": true }` has those keys wrapped under `board`, so the same `params.expect(board: [...])` serves JSON and form posts. About 20 Fizzy controllers declare it.

Why: JSON clients do not have to nest their payload (Fizzy: `app/controllers/boards_controller.rb`).

## Response Patterns

### Turbo Stream responses

```ruby
# app/controllers/cards/closures_controller.rb
    respond_to do |format|
      format.turbo_stream
      format.json { head :no_content }
    end
```

`format.turbo_stream` renders the action's `.turbo_stream.erb` view, here `app/views/cards/closures/create.turbo_stream.erb`. Its last line replaces the card container:

```erb
<%# app/views/cards/closures/create.turbo_stream.erb %>
<%= turbo_stream.replace([ @card, :card_container ], partial: "cards/container", method: :morph, locals: { card: @card.reload }) %>
```

Why: the page updates in place without custom JavaScript (Fizzy: `app/views/cards/closures/create.turbo_stream.erb`).

### JSON responses

```ruby
# app/controllers/boards_controller.rb
    respond_to do |format|
      format.html { redirect_to board_path(@board) }
      format.json { render :show, status: :created, location: board_path(@board, format: :json) }
    end
```

JSON bodies come from jbuilder templates next to the HTML views. `render :show` reuses `app/views/boards/show.json.jbuilder`:

```ruby
# app/views/boards/show.json.jbuilder
json.partial! "boards/board", board: @board
json.user_ids @board.users.ids unless @board.all_access?
```

Why: serialization lives in views, so the controller only picks the status and `Location` header (Fizzy: `app/views/boards/show.json.jbuilder`).

### Fresh when for caching

```ruby
# app/controllers/boards_controller.rb
  def index
    set_page_and_extract_portion_from Current.user.boards.ordered_by_recently_accessed.includes(creator: :identity)
    fresh_when etag: @page.records
  end
```

`fresh_when etag:` builds an ETag from the records. When the client's `If-None-Match` matches, Rails answers 304 Not Modified. `set_page_and_extract_portion_from` comes from the `geared_pagination` gem (Gemfile), not from Rails.

Why: a 304 skips rendering and saves bandwidth (Fizzy: `app/controllers/boards_controller.rb`).

## Controller Concerns

### CardScoped concern

Card sub-controllers include `CardScoped`. It finds the card by `number` among the cards the current user can access, and sets `@board` from the card:

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
# ...
end
```

The concern also defines `render_card_replacement`, `capture_card_location` and `refresh_stream_if_needed`, which the card controllers use. A card the user cannot access is not found, so the request 404s. `CardScoped` has no 403 path.

Why: every card sub-controller shares one access-scoped lookup (Fizzy: `app/controllers/concerns/card_scoped.rb`).

### Authentication concern

`Authentication` runs `require_account` and `require_authentication` before every action. A controller opts out with the class method `allow_unauthenticated_access`:

```ruby
# app/controllers/concerns/authentication.rb
  class_methods do
# ...
    def allow_unauthenticated_access(**options)
      skip_before_action :require_authentication, **options
      before_action :resume_session, **options
      allow_unauthorized_access **options
    end
# ...
  end
```

```ruby
# app/controllers/concerns/authentication.rb
    def require_authentication
      resume_session || authenticate_by_bearer_token || request_authentication
    end
```

The private `require_authentication` tries the session cookie, then a bearer token, and otherwise redirects to login. See the `controllers-errors-auth.md` reference for the bearer-token path. See the `models-current-tenancy.md` reference for how `Current` is set.

Why: authentication is the default and each opt-out is declared in the controller that needs it (Fizzy: `app/controllers/concerns/authentication.rb`).

## Authorization

Fizzy has no policy gem. Access is expressed by scoping lookups through the user, plus small `ensure_*` before actions that answer `head :forbidden`:

```ruby
# app/controllers/concerns/authorization.rb
module Authorization
# ...
  private
    def ensure_admin
      head :forbidden unless Current.user.admin?
    end

    def ensure_staff
      head :forbidden unless Current.identity.staff?
    end
# ...
end
```

Permission predicates such as `can_administer_board?` live on the user (`app/models/user/role.rb`), and `ensure_permission_to_admin_board` (shown in the CRUD section) calls them directly. `BoardScoped` defines the same check for board sub-controllers.

Why: plain method calls on the user are simpler than a policy DSL (STYLE.md: "vanilla Rails").

## Sources

- Fizzy: `app/controllers/boards_controller.rb`, `app/controllers/cards/closures_controller.rb`, `app/controllers/cards/comments_controller.rb`, `app/controllers/sessions_controller.rb`
- Fizzy: `app/controllers/concerns/card_scoped.rb`, `app/controllers/concerns/board_scoped.rb`, `app/controllers/concerns/authentication.rb`, `app/controllers/concerns/authorization.rb`
- Fizzy: `app/views/cards/closures/create.turbo_stream.erb`, `app/views/boards/show.json.jbuilder`, `config/routes.rb`, `app/models/user/role.rb`
- Fizzy: `STYLE.md` ("CRUD controllers", "Controller and model interactions")
