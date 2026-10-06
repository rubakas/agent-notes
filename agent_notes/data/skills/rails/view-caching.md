# View Caching

## Contents

- [Fragment Caching](#fragment-caching)
- [Cache Invalidation with Touch](#cache-invalidation-with-touch)
- [HTTP Caching](#http-caching)
- [Jbuilder Caching](#jbuilder-caching)
- [Sources](#sources)

## Fragment Caching

Fragment caching stores rendered HTML keyed on the record's cache key and version (`updated_at`). Use `cache record do` for one record, an array for multi-part keys, and `cached: true` on a collection render.

```erb
<%# app/views/cards/_container.html.erb %>
  <% cache card do %>
```

```erb
<%# app/views/cards/_messages.html.erb %>
    <%= render partial: "cards/comments/comment", collection: card.comments.preloaded.chronologically, cached: true %>
```

Array keys combine several inputs, such as a collection and the time zone:

```erb
<%# app/views/events/day_timeline/_columns.html.erb %>
<% cache [ day_timeline.events, Time.zone.name ] do %>
  <%# Template Dependency Updated: _layout.html.erb 2026-01-26 %>
```

When a template change that Rails cannot see (a helper's output) should expire the fragment, edit a dated comment inside it. The comment changes the template digest.

```erb
<%# app/views/notifications/_notification.html.erb %>
<% cache notification do %>
  <%# Helper Dependency Updated: avatar_image_tag 2025-12-15 %>
```

Why: cached fragments are reused across requests, and Rails expires them from the record version and template digest (Fizzy: `app/views/cards/_container.html.erb`).

## Cache Invalidation with Touch

Use `belongs_to ..., touch: true` so a child change updates the parent's `updated_at` and expires the parent's fragment. Chain further with `after_touch`.

```ruby
# app/models/comment.rb
  belongs_to :card, touch: true
```

```ruby
# app/models/card.rb
  after_save   -> { board.touch }, if: :published?
  after_touch  -> { board.touch }, if: :published?
```

A comment save touches its card, and a published card touches its board, so board-level fragments expire as well. This is the Russian-doll pattern.

Why: touching up the tree lets outer fragments expire whenever anything inside them changes (Fizzy: `app/models/card.rb`).

## HTTP Caching

Use `fresh_when etag:` in a controller action to answer with 304 Not Modified when the ETag matches. A global `etag { "v1" }` in `ApplicationController` is mixed into every ETag; changing the string expires every client's cached response. `stale_when_importmap_changes` does the same when the importmap changes.

```ruby
# app/controllers/application_controller.rb
  etag { "v1" }
  stale_when_importmap_changes
```

```ruby
# app/controllers/cards/pins_controller.rb
  def show
    fresh_when etag: @card.pin_for(Current.user) || "none"
  end
```

Why: the browser revalidates with `If-None-Match` and skips re-rendering when nothing changed (Fizzy: `app/controllers/application_controller.rb`).

## Jbuilder Caching

Wrap a Jbuilder partial's body in `json.cache!`. Render collections with `partial:` and `as:`; add `cached: true` to fetch the fragments in one cache read.

```ruby
# app/views/cards/_card.json.jbuilder
json.cache! card do
  json.(card, :id, :number, :title, :status)
  json.description card.description.to_plain_text
  json.description_html card.description.to_s
# ...
end
```

```ruby
# app/views/notifications/index.json.jbuilder
json.array! (@unread || []) + @page.records, partial: "notifications/notification", as: :notification, cached: true
```

Why: the JSON API reuses the same per-record fragments as the HTML views (Fizzy: `app/views/cards/_card.json.jbuilder`).

## Sources

- Fizzy at 6aebc0cea: `app/views`, `app/models`, `app/controllers`
- Rails guides: caching with Rails (fragment caching, ETags, `fresh_when`)
