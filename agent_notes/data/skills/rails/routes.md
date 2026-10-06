# Routes and Resource Modeling

## Contents

- [Core Philosophy](#core-philosophy)
- [Basic Resource Routing](#basic-resource-routing)
- [Actions as Resources](#actions-as-resources)
- [Nested Resources](#nested-resources)
- [Namespaces and Scope Modules](#namespaces-and-scope-modules)
- [Custom Routes](#custom-routes)
- [Route Constraints](#route-constraints)
- [Debugging Routes](#debugging-routes)
- [Sources](#sources)

## Core Philosophy

Fizzy models web endpoints as CRUD operations on resources (REST). When an action does not fit a standard verb, add a resource for it instead of a custom member route:

```ruby
# Illustrative (not from Fizzy)
# Instead of custom member actions:
resources :articles do
  post :archive
  post :unarchive
end

# add a resource that represents the state:
resources :articles do
  resource :archival
end
```

Why: "When an action doesn't map cleanly to a standard CRUD verb, we introduce a new resource rather than adding custom actions." (STYLE.md "CRUD controllers")

## Basic Resource Routing

### Standard resource declaration

`resources :boards` (the first line of the boards block in `config/routes.rb`) generates the seven standard routes: `index`, `show`, `new`, `create`, `edit`, `update` and `destroy`. A singular `resource :settings` maps to one record with no `:id` in the URL and generates up to six routes: `show`, `new`, `create`, `edit`, `update` and `destroy`.

Why: a plural resource is a collection of records and a singular one is a thing that exists once in its context (https://guides.rubyonrails.org/routing.html).

### Limit routes with only

```ruby
# config/routes.rb
namespace :account do
  resource :cancellation, only: [ :create ]
  resource :entropy
  resource :join_code
  resource :settings
  resources :exports, only: [ :create, :show ]
  resources :imports, only: [ :new, :create, :show ]
end
```

Use `only:` to list the actions an endpoint really has, as `exports` and `imports` do. Fizzy omits it on many resources (`resource :entropy`, `resource :settings`).

Why: an `only:` list documents which actions exist and keeps unused routes out of `rails routes` (Fizzy: `config/routes.rb`).

## Actions as Resources

When a domain action does not fit a CRUD verb, make it a resource under the record it acts on:

```ruby
# config/routes.rb
resources :cards do
  scope module: :cards do
    resource :draft, only: :show
    resource :board
    resource :closure
    resource :column
    resource :goldness
    resource :image
    resource :not_now
    resource :pin
    resource :publish
    resource :reading
    resource :triage
    resource :watch
# ...
  end
end
```

`resource :closure` gives `POST /cards/:card_id/closure` and `DELETE /cards/:card_id/closure`, handled by `Cards::ClosuresController#create` (which calls `@card.close`) and `#destroy` (which calls `@card.reopen`). `resource :goldness`, `resource :pin` and `resource :watch` follow the same shape. Use `resources :x` (plural) when the thing has many items, such as `comments` and `reactions`.

Why: the controller keeps to the seven standard actions, and the model exposes intention-revealing methods (STYLE.md "CRUD controllers"; Fizzy: `config/routes.rb`).

## Nested Resources

### Nesting in the path

```ruby
# config/routes.rb
resources :cards, only: :create

resources :webhooks do
  scope module: :webhooks do
    resource :activation, only: :create
    resources :deliveries, only: :index, defaults: { format: :json }
  end
end
```

Paths: `POST /boards/:board_id/cards` and `GET /boards/:board_id/webhooks/:webhook_id/deliveries`. Nest when the child belongs to the parent (a board has webhooks), and limit the nested routes with `only:`.

Why: the URL carries the owner where the child cannot be found without it (Fizzy: `config/routes.rb`).

### Nest creation, address by own route

Fizzy does not use `shallow:`. A card is created under its board (`resources :cards, only: :create` inside `resources :boards`), and every later action uses the card's own top-level routes (`resources :cards` at the top of the file), so `/cards/:id` does not repeat the board.

Why: a card's number is unique per account (`index_cards_on_account_id_and_number`), so its URL does not need the board (Fizzy: `config/routes.rb`, `db/schema.rb`).

## Namespaces and Scope Modules

### Namespace (URL prefix and module)

```ruby
# config/routes.rb
namespace :notifications do
  resource :settings
  resource :unsubscribe
end
```

`namespace :notifications` generates `/notifications/settings` and routes it to `Notifications::SettingsController`. The path and the module both carry the prefix.

Why: the prefix groups a feature's endpoints in the URL and in the code (Fizzy: `config/routes.rb`).

### Scope module (module only)

```ruby
# config/routes.rb
resources :boards do
  scope module: :boards do
    resources :accesses, only: :index
    resource :subscriptions
    resource :involvement
    resource :publication
    resource :entropy
# ...
  end
# ...
end
```

Inside `scope module: :boards`, `resource :publication` generates `/boards/:board_id/publication` and routes it to `Boards::PublicationsController`. The path does not gain a `boards` segment, only the controller does.

Why: the URL stays short while the controllers live in a folder named for their parent (Fizzy: `config/routes.rb`).

### Nested modules within a namespace

```ruby
# config/routes.rb
namespace :columns do
  resources :cards, only: [] do
    scope module: :cards do
      namespace :drops do
        resource :not_now
        resource :stream
        resource :closure
        resource :column
      end
    end
  end
end
```

This yields `/columns/cards/:card_id/drops/not_now`, routed to `Columns::Cards::Drops::NotNowsController`. Use it sparingly, because every level adds a module.

Why: the four drop targets share one prefix in the URL and one folder in the code (Fizzy: `config/routes.rb`).

## Custom Routes

### Direct and resolve

```ruby
# config/routes.rb
direct :published_board do |board, options|
  route_for :public_board, board.publication.key
end

direct :published_card do |card, options|
  route_for :public_board_card, card.board.publication.key, card
end

resolve "Comment" do |comment, options|
  options[:anchor] = ActionView::RecordIdentifier.dom_id(comment)
  route_for :card, comment.card, options
end
```

`direct` defines a named URL helper that builds another route: `published_board_url(board)` is the public board URL built from the board's publication key, and views call it directly. `resolve` tells `polymorphic_url` and `link_to` where a model goes; a `Comment` resolves to its card with the comment's dom id as the anchor.

Why: callers use one helper or pass the model, and the URL shape lives in one place (Fizzy: `config/routes.rb`).

## Route Constraints

```ruby
# config/routes.rb
# Mobile clients
get "client_configurations/(:platform)_v(:version)" => "client_configurations#show",
  platform: /android|ios/, version: /\d+/
```

`platform:` and `version:` are segment constraints. The route matches only when the segment satisfies the regular expression.

Why: a non-matching request falls through to the next route instead of reaching the controller with a bad value (Fizzy: `config/routes.rb`).

## Debugging Routes

```bash
bin/rails routes                    # List all routes
bin/rails routes -g notifications   # Filter by path or name
bin/rails routes -c cards           # Filter by controller
bin/rails routes -E                 # Expanded format
```

Why: listing the routes is quicker than reading `config/routes.rb` when a nested module hides the controller name (https://guides.rubyonrails.org/routing.html#listing-existing-routes).

## Sources

- Fizzy: `config/routes.rb`, `app/controllers/cards/closures_controller.rb`, `app/controllers/boards/publications_controller.rb`
- Fizzy: `app/controllers/columns/cards/drops/not_nows_controller.rb`, `app/controllers/notifications/settings_controller.rb`, `db/schema.rb`
- STYLE.md "CRUD controllers"
- https://guides.rubyonrails.org/routing.html
