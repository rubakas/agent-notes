# Error Handling, Performance, and Security

## Contents

- [Error Handling](#error-handling)
- [Before, After, and Around Actions](#before-after-and-around-actions)
- [Flash Messages](#flash-messages)
- [Performance Patterns](#performance-patterns)
- [API Patterns](#api-patterns)
- [Security Patterns](#security-patterns)
- [Sources](#sources)

## Error Handling

Fizzy controllers have no `rescue_from`. They call bang methods and let Rails map the exceptions to HTTP statuses, with a few local `rescue` clauses for specific failures.

### Bang methods raise, Rails maps to status

```ruby
# app/controllers/cards/comments_controller.rb
  def update
    @comment.update! comment_params

    respond_to do |format|
      format.turbo_stream
      format.json { render :show }
    end
  end
```

Rails maps `ActiveRecord::RecordNotFound` to 404 and `ActiveRecord::RecordInvalid` to 422, so the action needs no handler.

Why: the `!` pairs with a non-bang counterpart and an invalid record fails loudly (STYLE.md: "we only use `!` for methods that have a correspondent counterpart without `!`").

### Non-bang methods when the controller handles failure

```ruby
# app/controllers/users_controller.rb
  def update
    if @user.update(user_params)
      respond_to do |format|
        format.html { redirect_to @user }
        format.json { render :show }
      end
    else
      respond_to do |format|
        format.html { render :edit, status: :unprocessable_entity }
        format.json { render json: @user.errors, status: :unprocessable_entity }
      end
    end
  end
```

Use `update` or `save` without `!` when the action renders its own failure response, as here with `:edit` for HTML and `@user.errors` for JSON, both with status 422.

Why: an expected validation failure is part of the normal flow, so the action branches on it (Fizzy: `app/controllers/users_controller.rb`).

### Local rescues for edge cases

```ruby
# app/controllers/boards/entropies_controller.rb
  def update
    @board.update!(entropy_params)

    respond_to do |format|
      format.turbo_stream
      format.json { render "boards/show", status: :ok }
    end
  rescue ActiveRecord::RecordInvalid
    head :unprocessable_entity
  end
```

A handful of controllers rescue locally, for one named exception, and answer with a status.

Why: the rescue covers one expected failure and the rest of the action stays unguarded (Fizzy: `app/controllers/boards/entropies_controller.rb`).

## Before, After, and Around Actions

### Before actions for setup

```ruby
# app/controllers/boards_controller.rb
  before_action :set_board, except: %i[ index new create ]
  before_action :ensure_permission_to_admin_board, only: %i[ update destroy ]
```

List the actions explicitly with `only:` or `except:`. Name guards after what they ensure (`ensure_permission_to_admin_board`, not `authorize`).

Why: an explicit action list shows at a glance which actions a guard covers (Fizzy: `app/controllers/boards_controller.rb`).

### After actions for response headers

```ruby
# app/controllers/concerns/block_search_engine_indexing.rb
module BlockSearchEngineIndexing
  extend ActiveSupport::Concern

  included do
    after_action :block_search_engine_indexing
  end

  private
    def block_search_engine_indexing
      headers["X-Robots-Tag"] = "none"
    end
end
```

Why: the header is set after the action runs, so action code is untouched (Fizzy: `app/controllers/concerns/block_search_engine_indexing.rb`).

### Around actions for request-scoped state

```ruby
# app/controllers/concerns/current_timezone.rb
module CurrentTimezone
# ...
  included do
    around_action :set_current_timezone
# ...
    etag { timezone_from_cookie }
  end
# ...
  private
    def set_current_timezone(&)
      Time.use_zone(timezone_from_cookie, &)
    end

    def timezone_from_cookie
      @timezone_from_cookie ||= begin
        timezone = cookies[:timezone]
        ActiveSupport::TimeZone[timezone] if timezone.present?
      end
    end
end
```

The zone comes from the `timezone` cookie, and the concern adds it to the controller's `etag` so a cached page is revalidated when the zone changes.

Why: `Time.use_zone` needs a block, and only an around action can wrap the whole action in one (Fizzy: `app/controllers/concerns/current_timezone.rb`).

### Opting out of authentication

```ruby
# app/controllers/users/avatars_controller.rb
class Users::AvatarsController < ApplicationController
  allow_unauthenticated_access only: :show
# ...
end
```

`allow_unauthenticated_access` skips `require_authentication`, resumes a session if there is one, and skips the account-access check. `require_unauthenticated_access` additionally redirects signed-in users away (`app/controllers/sessions_controller.rb`).

Why: one named class method replaces separate `skip_before_action` calls (Fizzy: `app/controllers/concerns/authentication.rb`).

## Flash Messages

### Basic flash usage

```ruby
# app/controllers/boards_controller.rb
      format.html do
        if @board.accessible_to?(Current.user)
          redirect_to edit_board_path(@board), notice: "Saved"
        else
          redirect_to root_path, notice: "Saved (you were removed from the board)"
        end
      end
```

HTML redirects pass `notice:` or `alert:`. JSON responses carry no flash.

Why: flash is for the next page load, which only a redirect has (Fizzy: `app/controllers/boards_controller.rb`).

### Turbo flash helper

`TurboFlash` is a controller concern. It exposes a private helper, `turbo_stream_flash`, that returns a Turbo Stream tag replacing the `flash` element:

```ruby
# app/controllers/concerns/turbo_flash.rb
module TurboFlash
  extend ActiveSupport::Concern

  included do
    helper_method :turbo_stream_flash
  end

  private
    def turbo_stream_flash(**flash_options)
      turbo_stream.replace(:flash, partial: "layouts/shared/flash", locals: { flash: flash_options })
    end
end
```

Turbo Stream views call it to show a message without a redirect:

```erb
<%# app/views/boards/entropies/update.turbo_stream.erb %>
<%= turbo_stream_flash(notice: "Saved") %>
```

Why: a Turbo Stream response cannot redirect, so the flash partial is replaced in the page instead (Fizzy: `app/controllers/concerns/turbo_flash.rb`).

## Performance Patterns

### ETags for conditional GET

```ruby
# app/controllers/boards_controller.rb
    def show_columns
      cards = @board.cards.awaiting_triage.latest.with_golden_first.preloaded
      set_page_and_extract_portion_from cards
      fresh_when etag: [ @board, @page.records, @user_filtering, Current.account ]
    end
```

`fresh_when etag:` takes everything the page depends on, here the board, the page of cards, the filtering state and the account. Concerns also add controller-wide ETags with `etag { ... }`: `Authentication` adds the identity id and `CurrentTimezone` adds the zone.

Why: a matching `If-None-Match` returns 304 and skips rendering (Fizzy: `app/controllers/boards_controller.rb`).

### Preloading with scopes

```ruby
# app/models/card.rb
  scope :preloaded,               -> { with_users.preload(:column, :tags, :steps, :closure, :goldness, :activity_spike, :image_attachment, reactions: :reacter, board: [ :entropy, :columns ], not_now: [ :user ]).with_rich_text_description_and_embeds }
```

The model owns the preload list and the controller calls `.preloaded` (`@board.cards.awaiting_triage.latest.with_golden_first.preloaded` in `BoardsController`).

Why: the associations a card view renders are loaded in one query each, which avoids N+1 queries (Fizzy: `app/models/card.rb`).

### Pagination

`set_page_and_extract_portion_from` is not part of Rails. It comes from the `geared_pagination` gem (`gem "geared_pagination", "~> 1.2"` in the Gemfile) and sets `@page`:

```ruby
# app/controllers/users_controller.rb
  def index
    set_page_and_extract_portion_from Current.account.users.active.alphabetically.includes(:identity)
  end
```

Why: the gem provides the controller helper and the `@page` object, so the controller does not build pagination by hand (Fizzy: `Gemfile`).

## API Patterns

### JSON is a format of the same controller

Fizzy has no `/api/v1` namespace in `config/routes.rb`. Each controller answers HTML, Turbo Stream or JSON through `respond_to`, and jbuilder templates render the JSON:

```ruby
# app/controllers/sessions_controller.rb
  def destroy
    terminate_session

    respond_to do |format|
      format.html { redirect_to_logout_url }
      format.json { head :no_content }
    end
  end
```

Why: one controller per resource serves every client format (STYLE.md: "We model web endpoints as CRUD operations on resources (REST)").

### Bearer tokens for API authentication

`require_authentication` tries the session cookie first, then a bearer token. Bearer tokens are accepted only for JSON requests:

```ruby
# app/controllers/concerns/authentication.rb
    def authenticate_by_bearer_token
      if request.authorization.to_s.include?("Bearer")
        if bearer_token_authenticatable_request?
          authenticate_or_request_with_http_token do |token|
            if identity = Identity.find_by_permissable_access_token(token, method: request.method)
              Current.identity = identity
            end
          end
        else
          request_http_token_authentication
        end
      end
    end
```

The token lookup is on `Identity`, and an access token must allow the request's HTTP method:

```ruby
# app/models/identity.rb
  def self.find_by_permissable_access_token(token, method:)
    if (access_token = AccessToken.find_by(token: token)) && access_token.allows?(method)
      access_token.identity
    end
  end
```

Why: scripts send a token, browsers keep the session cookie, and one concern handles both (Fizzy: `app/controllers/concerns/authentication.rb`).

## Security Patterns

### CSRF protection

```ruby
# app/controllers/concerns/request_forgery_protection.rb
module RequestForgeryProtection
  extend ActiveSupport::Concern

  included do
    protect_from_forgery using: :header_only, with: :exception
  end

  private
    def verified_via_header_only?
      super || allowed_api_request?
    end

    def allowed_api_request?
      sec_fetch_site_value.nil? && request.format.json?
    end
end
```

Fizzy tracks Rails `main` (`gem "rails", github: "rails/rails", branch: "main"` in the Gemfile), and `using: :header_only` is a `main`-only option. On released Rails 8.1 use the stock `protect_from_forgery with: :exception`. The concern also lets JSON requests that carry no `Sec-Fetch-Site` header (API clients) through.

Why: API clients cannot send a browser CSRF token, so the check has a narrow JSON exception (Fizzy: `app/controllers/concerns/request_forgery_protection.rb`).

### Skip CSRF for token-based endpoints

```ruby
# app/controllers/notifications/unsubscribes_controller.rb
class Notifications::UnsubscribesController < ApplicationController
  allow_unauthenticated_access
  skip_forgery_protection
# ...
end
```

Skip CSRF only where the request is intentionally unauthenticated. This endpoint is reached from an email link and identifies the user by an `access_token` param.

Why: a mail client has no session or CSRF token to send (Fizzy: `app/mailers/concerns/mailers/unsubscribable.rb`).

### Rate limiting

```ruby
# app/controllers/sessions_controller.rb
class SessionsController < ApplicationController
# ...
  rate_limit to: 10, within: 3.minutes, only: :create, with: :rate_limit_exceeded
# ...
  private
# ...
    def rate_limit_exceeded
      rate_limit_exceeded_message = "Try again later."

      respond_to do |format|
        format.html { redirect_to new_session_path, alert: rate_limit_exceeded_message }
        format.json { render json: { message: rate_limit_exceeded_message }, status: :too_many_requests }
      end
    end
# ...
end
```

`rate_limit` is Action Controller's class method (Rails 7.2+). `to:` is the request count, `within:` the window, `only:` the actions, and `with:` the response, here a private method answering HTML and JSON. The default key is `request.remote_ip`.

Why: sign-in attempts are limited per client IP to slow brute-force attacks (Fizzy: `app/controllers/sessions_controller.rb`).

### Authorization checks

```ruby
# app/controllers/concerns/authorization.rb
    def ensure_can_access_account
      unless Current.account.active? && Current.user&.active?
        respond_to do |format|
          format.html { redirect_to session_menu_path(script_name: nil) }
          format.json { head :forbidden }
        end
      end
    end
```

Role predicates live on the user model (`can_administer_board?` in `app/models/user/role.rb`). There is no policy gem.

Why: plain methods on the user are enough and answer HTML and JSON differently where needed (Fizzy: `app/controllers/concerns/authorization.rb`).

## Sources

- Fizzy: `app/controllers/boards_controller.rb`, `app/controllers/users_controller.rb`, `app/controllers/sessions_controller.rb`, `app/controllers/boards/entropies_controller.rb`, `app/controllers/cards/comments_controller.rb`
- Fizzy: `app/controllers/concerns/authentication.rb`, `app/controllers/concerns/authorization.rb`, `app/controllers/concerns/turbo_flash.rb`, `app/controllers/concerns/current_timezone.rb`
- Fizzy: `app/controllers/concerns/request_forgery_protection.rb`, `app/controllers/concerns/block_search_engine_indexing.rb`, `app/controllers/notifications/unsubscribes_controller.rb`
- Fizzy: `app/models/identity.rb`, `app/models/card.rb`, `app/models/user/role.rb`, `app/mailers/concerns/mailers/unsubscribable.rb`, `Gemfile`
- Fizzy: `STYLE.md` ("To bang or not to bang", "CRUD controllers")
