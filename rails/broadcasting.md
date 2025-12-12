# Broadcasting (Turbo Streams)

Real-time updates with Turbo Streams and Action Cable.

---

## Model Broadcasting

### broadcasts_refreshes

```ruby
class Card < ApplicationRecord
  # Automatically broadcasts refresh on changes
  broadcasts_refreshes
end
```

### Custom Broadcasting

```ruby
class Card < ApplicationRecord
  after_create_commit -> { broadcast_prepend_to "cards", partial: "cards/card", target: "cards-list" }
  after_update_commit -> { broadcast_replace_to "cards", partial: "cards/card" }
  after_destroy_commit -> { broadcast_remove_to "cards" }
end
```

### Conditional Broadcasting

```ruby
module Card::Broadcastable
  extend ActiveSupport::Concern

  included do
    broadcasts_refreshes

    before_update :remember_if_preview_changed
  end

  private
    def remember_if_preview_changed
      @preview_changed ||= title_changed? || column_id_changed?
    end

    def preview_changed?
      @preview_changed
    end
end
```

---

## Manual Broadcasting

### From Controllers

```ruby
def create
  @card = Card.create!(card_params)

  @card.broadcast_prepend_to "cards",
    partial: "cards/card",
    target: "cards-list"
end
```

### From Jobs

```ruby
class NotificationJob < ApplicationJob
  def perform(user, message)
    Turbo::StreamsChannel.broadcast_append_to(
      "user:#{user.id}:notifications",
      target: "notifications",
      partial: "notifications/notification",
      locals: { message: message }
    )
  end
end
```

---

## Subscribing to Streams

### In Views

```erb
<%= turbo_stream_from "cards" %>

<div id="cards-list">
  <%= render @cards %>
</div>
```

### User-Specific Streams

```erb
<%= turbo_stream_from "user:#{current_user.id}:notifications" %>

<div id="notifications">
  <!-- Notifications will appear here -->
</div>
```

---

## Turbo Stream Methods

### All Broadcast Methods

```ruby
# Append to target
broadcast_append_to "stream", target: "id", partial: "path"

# Prepend to target
broadcast_prepend_to "stream", target: "id", partial: "path"

# Replace target
broadcast_replace_to "stream", target: "id", partial: "path"

# Update target (replaces innerHTML only)
broadcast_update_to "stream", target: "id", partial: "path"

# Remove target
broadcast_remove_to "stream", target: "id"

# Before target
broadcast_before_to "stream", target: "id", partial: "path"

# After target
broadcast_after_to "stream", target: "id", partial: "path"

# Morph (Turbo 8+) - Preserves form state, focus, scroll position
broadcast_morph_to "stream", target: "id", partial: "path"

# Refresh entire page
broadcast_refresh_to "stream"
```

---

## Morphing (Turbo 8+)

Morphing updates the DOM while preserving form state, focus, and scroll position. Use for complex updates where you want smooth transitions without losing user context.

### In Controllers

```ruby
def update
  @card = Card.find(params[:id])
  @card.update!(card_params)

  # Morph instead of replace - preserves form state
  @card.broadcast_morph_to "cards",
    partial: "cards/card",
    target: dom_id(@card)
end
```

### In Views (Manual Turbo Streams)

```erb
<%# app/views/cards/update.turbo_stream.erb %>
<%= turbo_stream.morph dom_id(@card) do %>
  <%= render @card %>
<% end %>
```

### When to Use Morph vs Replace

**Use morph when:**
- Updating forms with user input
- Preserving scroll position
- Maintaining focus state
- Complex UI with nested interactive elements

**Use replace when:**
- Simple content updates
- No user interaction in the element
- Complete state refresh needed

---

## Stream Targeting Strategies

### Instance-Based (Single Record)

```erb
<%# Subscribe to specific card updates %>
<%= turbo_stream_from @card %>

<%# In model %>
class Card < ApplicationRecord
  after_update_commit -> {
    broadcast_replace_to self, partial: "cards/card"
  }
end
```

### Collection-Based (All Records)

```erb
<%# Subscribe to all cards %>
<%= turbo_stream_from "cards" %>

<%# In model %>
class Card < ApplicationRecord
  after_create_commit -> {
    broadcast_prepend_to "cards", target: "cards-list"
  }
end
```

### Nested/Scoped Streams

```erb
<%# Subscribe to cards within a board %>
<%= turbo_stream_from @board, "cards" %>
<%= turbo_stream_from [@board, @card] %>

<%# In model %>
class Card < ApplicationRecord
  after_update_commit -> {
    broadcast_replace_to [board, "cards"], partial: "cards/card"
  }
end
```

### User-Specific Streams

```erb
<%# Subscribe to current user's notifications %>
<%= turbo_stream_from current_user, "notifications" %>
<%= turbo_stream_from "user:#{current_user.id}:notifications" %>

<%# In job/model %>
Turbo::StreamsChannel.broadcast_append_to(
  [current_user, "notifications"],
  target: "notifications",
  partial: "notifications/notification"
)
```

### Multiple Targets

```ruby
# Broadcast to multiple streams
def after_update_commit
  # Update the card itself
  broadcast_replace_to self

  # Update the board's card list
  broadcast_replace_to [board, "cards"],
    target: "cards-list",
    partial: "boards/cards_list"

  # Update user's activity feed
  broadcast_prepend_to [creator, "activity"],
    target: "activity-feed",
    partial: "activity/card_updated"
end
```

---

## Performance Considerations

### When to Use Broadcasting

**✅ Good use cases:**
- Collaborative editing (multiple users)
- Real-time notifications
- Live dashboards
- Chat/messaging
- Status updates

**⚠️ Avoid when:**
- Single-user forms (use Turbo Frames instead)
- High-frequency updates (> 10/sec per user)
- Large data sets (paginate or batch)
- Non-interactive content

### Optimization Tips

```ruby
# ❌ Bad - Broadcasts on every save
class Card < ApplicationRecord
  broadcasts_refreshes
end

# ✅ Good - Conditional broadcasting
class Card < ApplicationRecord
  after_update_commit :broadcast_if_changed, if: :saved_changes?

  private
    def broadcast_if_changed
      return unless saved_change_to_title? || saved_change_to_status?
      broadcast_replace_to "cards"
    end
end

# ✅ Better - Debounce rapid updates
class Card < ApplicationRecord
  after_update_commit :broadcast_later

  private
    def broadcast_later
      BroadcastCardJob.set(wait: 100.milliseconds).perform_later(self)
    end
end
```

---

## Troubleshooting

### Broadcasts Not Appearing

**Check WebSocket connection:**
```javascript
// In browser console
Turbo.StreamActions
Turbo.session.adapter.visitStarted
```

**Verify stream subscription:**
```erb
<%# Make sure turbo_stream_from matches broadcast target %>
<%= turbo_stream_from "cards" %>  <%# Must match broadcast_*_to "cards" %>
```

**Check Action Cable:**
```ruby
# config/cable.yml should have correct adapter
development:
  adapter: async

production:
  adapter: redis
  url: <%= ENV.fetch("REDIS_URL") { "redis://localhost:6379/1" } %>
```

### Performance Issues

```ruby
# Limit broadcast frequency
class Card < ApplicationRecord
  # Throttle broadcasts
  after_update_commit :broadcast_changes, if: -> {
    (saved_changes.keys & %w[title status]).any?
  }
end

# Or use background jobs
after_update_commit -> { BroadcastJob.perform_later(self) }
```

---

## Summary

- **broadcasts_refreshes**: Automatic model broadcasting (simple)
- **broadcast_morph_to**: Preserves form state and scroll (Turbo 8+)
- **Targeting**: Instance, collection, nested, user-specific
- **Methods**: append, prepend, replace, update, remove, morph
- **Performance**: Conditional broadcasting, debouncing, background jobs
- **Action Cable**: WebSocket connection for real-time updates
