# Broadcasting & Solid Cable

## Contents

- [Model Broadcasting](#model-broadcasting)
- [Manual Broadcasting](#manual-broadcasting)
- [Subscribing to Streams](#subscribing-to-streams)
- [Broadcast Methods](#broadcast-methods)
- [Solid Cable Configuration](#solid-cable-configuration)
- [Multi-Tenant Broadcasting](#multi-tenant-broadcasting)
- [Sources](#sources)

## Model Broadcasting

A model broadcasts a page refresh when it changes with `broadcasts_refreshes` (to the model's own stream) and `broadcasts_refreshes_to` (to a stream you compute). Fizzy keeps these in concerns: `Board::Broadcastable` declares both, and `Card::Broadcastable` declares the first.

```ruby
# app/models/board/broadcastable.rb
module Board::Broadcastable
  extend ActiveSupport::Concern

  included do
    broadcasts_refreshes
    broadcasts_refreshes_to ->(board) { [ board.account, :all_boards ] }
  end
end
```

```ruby
# app/models/card/broadcastable.rb
module Card::Broadcastable
  extend ActiveSupport::Concern

  included do
    broadcasts_refreshes

    before_update :remember_if_preview_changed
  end
```

The broadcasts run from `after_commit` callbacks, so subscribers see committed data. In turbo-rails 2.0.23, `broadcasts_refreshes` enqueues a job for create and update (`broadcast_refresh_later_to`, `broadcast_refresh_later`) but broadcasts destroy inline (`broadcast_refresh`). Subscribers with morphing enabled refresh in place.

Why: a refresh broadcast keeps every open page in sync without hand-written stream templates (Turbo docs: https://turbo.hotwired.dev/handbook/page_refreshes).

## Manual Broadcasting

When a stream needs a custom partial or a specific recipient list, call `broadcast_*_to` yourself. Fizzy's `Card::Pinnable` enqueues a job after an update commit, and the job calls a model method that broadcasts to each pinned user's tray.

```ruby
# app/models/card/pinnable.rb
    after_update_commit :broadcast_pin_updates_later, if: :preview_changed?
```

```ruby
# app/models/card/pinnable.rb
  def broadcast_pin_updates
    pins.where(user: board.users).find_each do |pin|
      pin.broadcast_replace_to [ pin.user, :pins_tray ], partial: "my/pins/pin"
    end
  end
```

```ruby
# app/models/card/pinnable.rb
  private
    def broadcast_pin_updates_later
      Card::BroadcastPinUpdatesJob.perform_later(self)
    end
```

```ruby
# app/jobs/card/broadcast_pin_updates_job.rb
class Card::BroadcastPinUpdatesJob < ApplicationJob
  discard_on ActiveJob::DeserializationError

  def perform(card)
    card.broadcast_pin_updates
  end
end
```

Why: the job keeps rendering out of the request, and the model method decides who receives what (Fizzy: `app/models/card/pinnable.rb`).

## Subscribing to Streams

Views subscribe with `turbo_stream_from`, passing model objects and symbols. Turbo builds a signed stream name from them, so the name matches what the model broadcasts to.

```erb
<%# app/views/cards/show.html.erb %>
<%= turbo_stream_from @card %>
<%= turbo_stream_from @card, :activity %>
```

```erb
<%# app/views/cards/_broadcasts.html.erb %>
<% if filter.boards.any? %>
  <% filter.boards.each do |board| %>
    <%= turbo_stream_from board %>
  <% end %>
<% else %>
  <%= turbo_stream_from [ Current.account, :all_boards ] %>
<% end %>
```

```erb
<%# app/views/my/pins/_tray.html.erb %>
<%= turbo_stream_from Current.user, :pins_tray %>
```

The `[ Current.account, :all_boards ]` subscription pairs with the `broadcasts_refreshes_to` call in `Board::Broadcastable`.

Why: one array expression on each side keeps the subscription and the broadcast in agreement (Fizzy: `app/views/cards/_broadcasts.html.erb`).

## Broadcast Methods

These instance methods come from `Turbo::Broadcastable` (turbo-rails 2.0.23):

- `broadcast_replace_to`, `broadcast_update_to`, `broadcast_append_to`, `broadcast_prepend_to` take `partial:` and `locals:`.
- `broadcast_before_to`, `broadcast_after_to` and `broadcast_remove_to` act on a target element.
- `broadcast_refresh_to` sends a page refresh.
- `broadcast_replace_later_to`, `broadcast_update_later_to`, `broadcast_append_later_to`, `broadcast_prepend_later_to` and `broadcast_refresh_later_to` enqueue the broadcast as a job. There is no `_later` form of `broadcast_remove_to`, `broadcast_before_to` or `broadcast_after_to`.
- Each has a variant without `_to` that broadcasts to the model's own stream.
- Pass `attributes: { method: :morph }` to `broadcast_replace_to` or `broadcast_update_to` to morph instead of replace.
- Turbo debounces repeated page refreshes in a row so only the last one is broadcast.

Why: the `_later` variants move rendering out of the request or callback (Turbo docs: https://turbo.hotwired.dev/handbook/streams; source: turbo-rails `app/models/concerns/turbo/broadcastable.rb`).

## Solid Cable Configuration

Solid Cable stores Action Cable messages in the database, so Redis is not required. Fizzy defines one `cable` entry and reuses it for each environment:

```yaml
# config/cable.yml
cable: &cable
  adapter: solid_cable
  connects_to:
    database:
      writing: cable
      reading: cable
  polling_interval: 0.1.seconds
  message_retention: 1.day

development: *cable
test:
  adapter: test
beta: *cable
staging: *cable
production: *cable
```

The `cable` database is a separate connection with its own migrations path. In `config/database.sqlite.yml`:

```yaml
# config/database.sqlite.yml
  cable:
    <<: *default
    database: storage/development_cable.sqlite3
    migrations_paths: db/cable_migrate
```

If the app already runs Redis, Action Cable's Redis adapter also works. This is not from Fizzy:

```yaml
# Illustrative (not from Fizzy)
production:
  adapter: redis
  url: <%= ENV.fetch("REDIS_URL") %>
```

Why: a database-backed adapter removes a moving part from the stack (Solid Cable docs: https://github.com/rails/solid_cable; Fizzy: `config/cable.yml`).

## Multi-Tenant Broadcasting

Turbo renders broadcast partials in background jobs, outside a request. In a multi-tenant app those jobs must run with the right account. Fizzy prepends its `AccountTenanted` concern onto Turbo's broadcast jobs, and `render_format` renders with the account's `script_name` so generated URLs carry the account prefix.

```ruby
# config/initializers/active_job.rb
Rails.application.config.after_initialize do
  Turbo::Streams::ActionBroadcastJob.prepend AccountTenanted
  Turbo::Streams::BroadcastJob.prepend AccountTenanted
  Turbo::Streams::BroadcastStreamJob.prepend AccountTenanted
end
```

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

The layout adds the Action Cable URL, including the script name, as a meta tag:

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

Why: without the account context, the job cannot resolve tenant-scoped records or URLs (Fizzy: `config/initializers/active_job.rb`, `AGENTS.md`).

## Sources

- [Turbo handbook](https://turbo.hotwired.dev/handbook/introduction)
- [Action Cable guides](https://guides.rubyonrails.org/action_cable_overview.html)
- [Solid Cable](https://github.com/rails/solid_cable)
- Fizzy at 6aebc0cea: `app/models`, `app/jobs`, `config/cable.yml`, `config/initializers`
- turbo-rails 2.0.23: `app/models/concerns/turbo/broadcastable.rb` (`broadcasts_refreshes`)
