# Multi-Tenancy

## Contents

- [URL-Based Tenancy](#url-based-tenancy)
- [Routing & Script Name](#routing--script-name)
- [Current Context](#current-context)
- [Broadcasting & Jobs](#broadcasting--jobs)
- [Mailers & Action Cable](#mailers--action-cable)
- [Sources](#sources)

## URL-Based Tenancy

Fizzy identifies the account by a decimal `external_account_id` prefix in the URL: `/{account_id}/boards/...`. A Rack middleware, `AccountSlug::Extractor`, takes the prefix off `PATH_INFO`, puts it on `SCRIPT_NAME`, finds the account and runs the rest of the request inside `Current.with_account`. Requests with no prefix run inside `Current.without_account`. The middleware is inserted after `Rack::TempfileReaper`:

```ruby
# config/initializers/tenanting/account_slug.rb
      if request.script_name && request.script_name =~ PATH_INFO_MATCH
        # Likely due to restarting the action cable connection after upgrade
        env["fizzy.external_account_id"] = AccountSlug.decode($2)
      elsif request.path_info =~ PATH_INFO_MATCH
        # Yanks the prefix off PATH_INFO and move it to SCRIPT_NAME
        request.engine_script_name = request.script_name = $1
        request.path_info   = $'.empty? ? "/" : $'

        # Stash the account's Queenbee ID.
        env["fizzy.external_account_id"] = AccountSlug.decode($2)
      end
# ...
      if env["fizzy.external_account_id"]
        account = Account.find_by(external_account_id: env["fizzy.external_account_id"])
        Current.with_account(account) do
          @app.call env
        end
      else
        Current.without_account do
          @app.call env
        end
      end
    end
# ...
Rails.application.config.middleware.insert_after Rack::TempfileReaper, AccountSlug::Extractor
```

Why: moving the prefix to `SCRIPT_NAME` leaves the routes untouched. The code comment says: "Rather than namespace all our routes, we're "mounting" the Rails app at this URL prefix." (Fizzy: `config/initializers/tenanting/account_slug.rb`)

## Routing & Script Name

Because the prefix lives in `SCRIPT_NAME`, every route helper includes it without any change to `config/routes.rb`. `Account#slug` is the same prefix, and mailers and Turbo renders use it to build URLs outside a request:

```ruby
# app/models/account.rb
  def slug
    "/#{AccountSlug.encode(external_account_id)}"
  end
```

Tests and specs need care here. AGENTS.md warns that "route helpers and request specs that assume a bare root will mislead you".

Why: a helper that ignores `SCRIPT_NAME` would generate URLs that leave the tenant (AGENTS.md).

## Current Context

`Current` holds the tenant and the signed-in user for the length of a request or job. `with_account` and `without_account` are the two ways the middleware and jobs switch tenant. Assigning a session also assigns its identity, and assigning an identity looks up that identity's user in the current account:

```ruby
# app/models/current.rb
class Current < ActiveSupport::CurrentAttributes
  attribute :session, :user, :identity, :account
  attribute :http_method, :request_id, :user_agent, :ip_address, :referrer
# ...
  def with_account(value, &)
    with(account: value, &)
  end

  def without_account(&)
    with(account: nil, &)
  end
```

There is no controller `before_action` that reads an account id from params; the middleware has already set `Current.account` before the controller runs.

Why: AGENTS.md describes the same split: "`AccountSlug::Extractor` middleware sets `Current.account`" and a global `Identity` can hold users in several accounts, which is why the user is looked up per account.

## Broadcasting & Jobs

Jobs do not inherit the request's `Current`, so Fizzy prepends a module that carries the account with the job. `AccountTenanted` stores `Current.account` when the job is built, adds its GlobalID to the serialized data, and wraps `perform` in `Current.with_account`. It resolves the account inside an `around_perform` callback so that a missing account raises `ActiveJob::DeserializationError` where `discard_on` can handle it. Three excerpts from the module:

```ruby
# app/jobs/concerns/account_tenanted.rb
module AccountTenanted
  extend ActiveSupport::Concern

  prepended do
    attr_reader :account
    around_perform :with_account_context
  end
# ...
  def initialize(...)
    super
    @account = Current.account
  end

  def serialize
    super.merge({ "account" => @account&.to_gid })
  end
# ...
  private
    def with_account_context(&block)
      resolve_account!

      if account.present?
        Current.with_account(account, &block)
      else
        yield
      end
    end
```

`ApplicationJob` prepends it, so every app job is tenant-aware:

```ruby
# app/jobs/application_job.rb
class ApplicationJob < ActiveJob::Base
  prepend AccountTenanted
```

Jobs that Rails and Turbo define are covered the same way, in an initializer:

```ruby
# config/initializers/active_job.rb
ActiveSupport.on_load(:action_mailer) do
  ActionMailer::MailDeliveryJob.prepend AccountTenanted
end

Rails.application.config.after_initialize do
  Turbo::Streams::ActionBroadcastJob.prepend AccountTenanted
  Turbo::Streams::BroadcastJob.prepend AccountTenanted
  Turbo::Streams::BroadcastStreamJob.prepend AccountTenanted
end
```

Turbo broadcasts render partials outside a request, so `tenanting/turbo.rb` prepends a module onto `Turbo::StreamsChannel` that renders with the account's `script_name`:

```ruby
# config/initializers/tenanting/turbo.rb
module TurboStreamsJobExtensions
  extend ActiveSupport::Concern

  class_methods do
    def render_format(format, **rendering)
      if Current.account.present?
        ApplicationController.renderer.new(script_name: Current.account.slug).render(formats: [ format ], **rendering)
      else
        super
      end
    end
  end
end

Rails.application.config.after_initialize do
  Turbo::StreamsChannel.prepend TurboStreamsJobExtensions
end
```

Why: AGENTS.md says "Background jobs serialize and restore `Current.account` themselves."

## Mailers & Action Cable

`ApplicationMailer` adds the account slug as `script_name` whenever a `Current.account` exists, so links in emails carry the prefix. `MailDeliveryJob` gets `AccountTenanted` in the initializer shown above.

```ruby
# app/mailers/application_mailer.rb
  private
    def default_url_options
      if Current.account
        super.merge(script_name: Current.account.slug)
      else
        super
      end
    end
```

For Action Cable, the browser must connect under the same prefix. A helper builds the meta tag from `request.script_name` plus the cable mount path:

```ruby
# app/helpers/tenanting_helper.rb
module TenantingHelper
  def tenanted_action_cable_meta_tag
    tag "meta",
        name: "action-cable-url",
        content: "#{request.script_name}#{ActionCable.server.config.mount_path}"
  end
end
```

It is rendered from the shared head partial:

```erb
<%# app/views/layouts/shared/_head.html.erb %>
  <%= tenanted_action_cable_meta_tag %>
```

For an account whose slug is `/123` and a cable mount path of `/cable`, the tag has `content="/123/cable"`.

Why: without the prefix, the cable connection would be made at the bare root and lose the tenant (Fizzy: `app/helpers/tenanting_helper.rb`).

## Sources

- Fizzy `AGENTS.md`, section "Multi-tenancy is URL-based"
- Fizzy files shown above, at commit 6aebc0cea
