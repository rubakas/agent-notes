# Frontend

## JavaScript & Stimulus

Frontend patterns with Stimulus, Turbo, and Importmap (Rails 8 defaults).

---

### Philosophy

1. **HTML over the wire** - Server renders HTML, not JSON
2. **Progressive enhancement** - Works without JavaScript
3. **Sprinkles of interactivity** - Stimulus for behavior
4. **One controller per behavior** - Focused, reusable
5. **Turbo for speed** - Fast navigation without SPAs

---

### File Structure

```
app/javascript/
├── application.js
└── controllers/
    ├── index.js
    ├── dialog_controller.js
    ├── auto_submit_controller.js
    ├── navigable_list_controller.js
    └── drag_drop_controller.js
```

---

### Stimulus Controller Template

```javascript
// app/javascript/controllers/dialog_controller.js
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = [ "dialog", "content" ]
  static values = { open: Boolean, dismissable: { type: Boolean, default: true } }
  static classes = [ "open", "closing" ]

  connect() {
    this.boundHandleEscape = this.handleEscape.bind(this)
    document.addEventListener("keydown", this.boundHandleEscape)
  }

  disconnect() {
    document.removeEventListener("keydown", this.boundHandleEscape)
  }

  open() {
    this.openValue = true
    this.dialogTarget.showModal()
    this.dialogTarget.classList.add(this.openClass)
  }

  close() {
    if (!this.dismissableValue) return

    this.openValue = false
    this.dialogTarget.classList.add(this.closingClass)

    setTimeout(() => {
      this.dialogTarget.close()
      this.dialogTarget.classList.remove(this.openClass, this.closingClass)
    }, 200)
  }

  handleEscape(event) {
    if (event.key === "Escape" && this.openValue) {
      this.close()
    }
  }
}
```

---

### Stimulus Patterns

#### Auto-Submit Form

```javascript
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = [ "form" ]
  static values = { delay: { type: Number, default: 300 } }

  submit() {
    clearTimeout(this.timeout)

    this.timeout = setTimeout(() => {
      this.formTarget.requestSubmit()
    }, this.delayValue)
  }
}
```

```erb
<%= form_with model: @filter, data: { controller: "auto-submit", action: "input->auto-submit#submit" } do |f| %>
  <%= f.text_field :query, data: { auto_submit_target: "form" } %>
<% end %>
```

#### Keyboard Navigation

```javascript
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = [ "item" ]

  connect() {
    this.index = 0
    this.highlight(0)
  }

  navigate(event) {
    switch(event.key) {
      case "ArrowDown":
        event.preventDefault()
        this.next()
        break
      case "ArrowUp":
        event.preventDefault()
        this.previous()
        break
      case "Enter":
        event.preventDefault()
        this.select()
        break
    }
  }

  next() {
    this.index = Math.min(this.index + 1, this.itemTargets.length - 1)
    this.highlight(this.index)
  }

  previous() {
    this.index = Math.max(this.index - 1, 0)
    this.highlight(this.index)
  }

  select() {
    this.itemTargets[this.index]?.click()
  }

  highlight(index) {
    this.itemTargets.forEach((item, i) => {
      item.classList.toggle("highlighted", i === index)
    })
    this.itemTargets[index]?.scrollIntoView({ block: "nearest" })
  }
}
```

#### Clipboard Controller

```javascript
// controllers/clipboard_controller.js
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = [ "source", "button" ]
  static values = {
    successMessage: { type: String, default: "Copied!" },
    successDuration: { type: Number, default: 2000 }
  }

  copy(event) {
    event.preventDefault()

    navigator.clipboard.writeText(this.sourceTarget.value || this.sourceTarget.textContent)
      .then(() => this.showSuccess())
      .catch(() => this.showError())
  }

  showSuccess() {
    const originalText = this.buttonTarget.textContent
    this.buttonTarget.textContent = this.successMessageValue

    setTimeout(() => {
      this.buttonTarget.textContent = originalText
    }, this.successDurationValue)
  }

  showError() {
    this.buttonTarget.textContent = "Failed to copy"
  }
}
```

```erb
<div data-controller="clipboard">
  <input data-clipboard-target="source" value="<%= @share_url %>" readonly>
  <button data-action="click->clipboard#copy" data-clipboard-target="button">
    Copy URL
  </button>
</div>
```

#### Dropdown Controller

```javascript
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = [ "menu" ]
  static classes = [ "open" ]

  connect() {
    this.boundHandleClickOutside = this.handleClickOutside.bind(this)
  }

  toggle(event) {
    event.stopPropagation()

    if (this.menuTarget.classList.contains(this.openClass)) {
      this.close()
    } else {
      this.open()
    }
  }

  open() {
    this.menuTarget.classList.add(this.openClass)
    document.addEventListener("click", this.boundHandleClickOutside)
  }

  close() {
    this.menuTarget.classList.remove(this.openClass)
    document.removeEventListener("click", this.boundHandleClickOutside)
  }

  handleClickOutside(event) {
    if (!this.element.contains(event.target)) {
      this.close()
    }
  }

  disconnect() {
    document.removeEventListener("click", this.boundHandleClickOutside)
  }
}
```

#### Toggle Controller

```javascript
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = [ "toggleable" ]
  static classes = [ "hidden" ]

  toggle() {
    this.toggleableTargets.forEach(target => {
      target.classList.toggle(this.hiddenClass)
    })
  }

  show() {
    this.toggleableTargets.forEach(target => {
      target.classList.remove(this.hiddenClass)
    })
  }

  hide() {
    this.toggleableTargets.forEach(target => {
      target.classList.add(this.hiddenClass)
    })
  }
}
```

---

### Turbo Patterns

#### Turbo Frames

```erb
<%# Lazy loading %>
<turbo-frame id="stats" src="<%= stats_path %>" loading="lazy">
  <p>Loading stats...</p>
</turbo-frame>

<%# Break out of frame %>
<%= link_to "View All", cards_path, data: { turbo_frame: "_top" } %>
```

#### Turbo Drive

```erb
<%# Disable Turbo for link %>
<%= link_to "External", external_path, data: { turbo: false } %>

<%# Confirm before navigation %>
<%= link_to "Delete", @card, method: :delete, data: { turbo_confirm: "Are you sure?" } %>
```

---

### Importmap (Rails 8 Default)

```ruby
# config/importmap.rb
pin "application"
pin "@hotwired/turbo-rails", to: "turbo.min.js"
pin "@hotwired/stimulus", to: "stimulus.min.js"
pin "@hotwired/stimulus-loading", to: "stimulus-loading.js"
pin_all_from "app/javascript/controllers", under: "controllers"

# Third-party libraries
pin "local-time"
pin "sortablejs"
```

```bash
# Add from CDN
bin/importmap pin local-time
bin/importmap pin sortablejs@1.15.0
bin/importmap json
```

```javascript
// app/javascript/application.js
import "@hotwired/turbo-rails"
import "./controllers"

import LocalTime from "local-time"
LocalTime.start()
```

---

### Turbo 8 Features

#### Page Refresh (Morphing)

```erb
<%# Enable for entire app %>
<meta name="turbo-refresh-method" content="morph">
<meta name="turbo-refresh-scroll" content="preserve">
```

```ruby
# Force refresh after form submit
def create
  @card = Card.create!(card_params)
  redirect_to cards_path, status: :see_other
end
```

#### Turbo Permanent Elements

```erb
<div id="player" data-turbo-permanent>
  <audio controls src="<%= @podcast.audio_url %>"></audio>
</div>
```

#### Prefetching

```erb
<%= link_to "View Card", @card, data: { turbo_prefetch: true } %>
<%= link_to "Dashboard", dashboard_path, data: { turbo_preload: "instant" } %>
```

---

### View Transitions (CSS)

```erb
<%# Enable %>
<meta name="view-transition" content="same-origin">
```

```css
/* Fade transition */
::view-transition-old(root),
::view-transition-new(root) {
  animation-duration: 0.3s;
}

/* Slide transition */
::view-transition-old(root) { animation-name: slide-out; }
::view-transition-new(root) { animation-name: slide-in; }

@keyframes slide-out {
  from { transform: translateX(0); }
  to { transform: translateX(-100%); }
}

@keyframes slide-in {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

/* Named transitions for specific elements */
.card-detail {
  view-transition-name: card-detail;
}
```

**Browser Support:** Chrome/Edge 111+, Safari 18+. Gracefully degrades in older browsers.

---

## Broadcasting (Turbo Streams)

Real-time updates with Turbo Streams and Action Cable.

---

### Model Broadcasting

```ruby
class Card < ApplicationRecord
  # Automatic broadcasts refresh on changes
  broadcasts_refreshes
end

# Custom Broadcasting
class Card < ApplicationRecord
  after_create_commit -> { broadcast_prepend_to "cards", partial: "cards/card", target: "cards-list" }
  after_update_commit -> { broadcast_replace_to "cards", partial: "cards/card" }
  after_destroy_commit -> { broadcast_remove_to "cards" }
end

# Conditional Broadcasting
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

### Manual Broadcasting

```ruby
# From Controllers
def create
  @card = Card.create!(card_params)

  @card.broadcast_prepend_to "cards",
    partial: "cards/card",
    target: "cards-list"
end

# From Jobs
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

### Subscribing to Streams

```erb
<%= turbo_stream_from "cards" %>

<div id="cards-list">
  <%= render @cards %>
</div>

<%# User-Specific Streams %>
<%= turbo_stream_from "user:#{current_user.id}:notifications" %>
<%= turbo_stream_from current_user, "notifications" %>

<%# Nested/Scoped Streams %>
<%= turbo_stream_from @board, "cards" %>
<%= turbo_stream_from [@board, @card] %>
```

---

### All Broadcast Methods

```ruby
broadcast_append_to "stream", target: "id", partial: "path"
broadcast_prepend_to "stream", target: "id", partial: "path"
broadcast_replace_to "stream", target: "id", partial: "path"
broadcast_update_to "stream", target: "id", partial: "path"
broadcast_remove_to "stream", target: "id"
broadcast_before_to "stream", target: "id", partial: "path"
broadcast_after_to "stream", target: "id", partial: "path"
broadcast_morph_to "stream", target: "id", partial: "path"  # Turbo 8+
broadcast_refresh_to "stream"
```

---

### Morphing (Turbo 8+)

```ruby
def update
  @card.update!(card_params)

  @card.broadcast_morph_to "cards",
    partial: "cards/card",
    target: dom_id(@card)
end
```

```erb
<%# app/views/cards/update.turbo_stream.erb %>
<%= turbo_stream.morph dom_id(@card) do %>
  <%= render @card %>
<% end %>
```

Use morph when: updating forms with user input, preserving scroll, maintaining focus state.
Use replace when: simple content updates, no user interaction in the element.

---

### Performance

```ruby
# Conditional broadcasting
class Card < ApplicationRecord
  after_update_commit :broadcast_if_changed, if: :saved_changes?

  private
    def broadcast_if_changed
      return unless saved_change_to_title? || saved_change_to_status?
      broadcast_replace_to "cards"
    end
end

# Debounce rapid updates
class Card < ApplicationRecord
  after_update_commit :broadcast_later

  private
    def broadcast_later
      BroadcastCardJob.set(wait: 100.milliseconds).perform_later(self)
    end
end
```

---

### Action Cable Config

```yaml
# config/cable.yml
development:
  adapter: async

production:
  adapter: redis
  url: <%= ENV.fetch("REDIS_URL") { "redis://localhost:6379/1" } %>
```

---

## Active Storage

File upload and attachment patterns with Active Storage.

---

### Setup

```ruby
# Single Attachment
class User < ApplicationRecord
  has_one_attached :avatar, dependent: :purge_later
end

# Multiple Attachments
class Card < ApplicationRecord
  has_many_attached :documents, dependent: :purge_later
end

# Dependent options:
# :purge         - Deletes attachment immediately when record is destroyed
# :purge_later   - Queues job to delete attachment (recommended for production)
# false          - Keeps attachment files orphaned (not recommended)
```

---

### Uploading & Displaying

```erb
<%# In Forms %>
<%= form_with model: @user do |f| %>
  <%= f.file_field :avatar %>
  <%= f.file_field :avatar, direct_upload: true %>
  <%= f.submit %>
<% end %>

<%# Displaying Images %>
<% if @user.avatar.attached? %>
  <%= image_tag @user.avatar %>
  <%= image_tag @user.avatar.variant(resize_to_limit: [200, 200]) %>
<% end %>
```

---

### Variants

```ruby
@user.avatar.variant(resize_to_limit: [300, 300])
@user.avatar.variant(resize_to_fill: [300, 300])
@user.avatar.variant(resize_to_limit: [300, 300], format: :jpg)
```

---

### Validations

```ruby
class User < ApplicationRecord
  has_one_attached :avatar
  has_many_attached :documents, dependent: :purge_later

  validate :avatar_validation
  validate :documents_validation

  private
    def avatar_validation
      return unless avatar.attached?

      acceptable_types = %w[image/png image/jpg image/jpeg image/gif]
      unless avatar.content_type.in?(acceptable_types)
        errors.add(:avatar, "must be a PNG, JPG, or GIF")
      end

      if avatar.byte_size > 5.megabytes
        errors.add(:avatar, "must be less than 5MB")
      end
    end

    def documents_validation
      return unless documents.attached?

      if documents.count > 10
        errors.add(:documents, "cannot exceed 10 files")
      end

      documents.each do |document|
        if document.byte_size > 10.megabytes
          errors.add(:documents, "#{document.filename} must be less than 10MB")
        end

        acceptable_types = %w[application/pdf image/png image/jpg]
        unless document.content_type.in?(acceptable_types)
          errors.add(:documents, "#{document.filename} must be a PDF or image")
        end
      end
    end
end
```

---

### Downloading & Managing

```ruby
# Small Files
def download
  send_data @user.avatar.download,
    filename: @user.avatar.filename.to_s,
    type: @user.avatar.content_type,
    disposition: "attachment"
end

# Large Files (Streaming)
def download
  redirect_to rails_blob_url(@document), allow_other_host: true
end

# Managing
@user.avatar.purge        # Synchronous
@user.avatar.purge_later  # Background job (recommended)
@card.documents.purge_all
@user.avatar.attached?    # => true/false
```

---

### Service Configuration

```yaml
# config/storage.yml
amazon:
  service: S3
  access_key_id: <%= Rails.application.credentials.dig(:aws, :access_key_id) %>
  secret_access_key: <%= Rails.application.credentials.dig(:aws, :secret_access_key) %>
  region: us-east-1
  bucket: my-app-<%= Rails.env %>

google:
  service: GCS
  project: my-project
  credentials: <%= Rails.application.credentials.dig(:gcs, :keyfile) %>
  bucket: my-app-<%= Rails.env %>

local:
  service: Disk
  root: <%= Rails.root.join("storage") %>
```

```ruby
# config/environments/development.rb
config.active_storage.service = :local

# config/environments/production.rb
config.active_storage.service = :amazon
```
