# JavaScript & Stimulus

Frontend patterns with Stimulus, Turbo, and Importmap (Rails 8 defaults).

---

## Philosophy

1. **HTML over the wire** - Server renders HTML, not JSON
2. **Progressive enhancement** - Works without JavaScript
3. **Sprinkles of interactivity** - Stimulus for behavior
4. **One controller per behavior** - Focused, reusable
5. **Turbo for speed** - Fast navigation without SPAs

---

## File Structure

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

## Stimulus Controller Template

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

  // Private methods with #
  #cleanup() {
    // Implementation
  }
}
```

---

## Stimulus Patterns

### Auto-Submit Form

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

### Keyboard Navigation

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

---

## Turbo Patterns

### Turbo Frames

```erb
<%# Lazy loading %>
<turbo-frame id="stats" src="<%= stats_path %>" loading="lazy">
  <p>Loading stats...</p>
</turbo-frame>

<%# Navigation within frame %>
<turbo-frame id="modal">
  <%= link_to "Edit", edit_card_path(@card) %>
</turbo-frame>

<%# Break out of frame %>
<%= link_to "View All", cards_path, data: { turbo_frame: "_top" } %>
```

### Turbo Streams

```ruby
# Controller
def create
  @card = Card.create!(card_params)

  respond_to do |format|
    format.turbo_stream
  end
end
```

```erb
<%# create.turbo_stream.erb %>
<%= turbo_stream.prepend "cards", @card %>
<%= turbo_stream.update "flash", partial: "shared/flash" %>
```

### Turbo Drive

```erb
<%# Disable Turbo for link %>
<%= link_to "External", external_path, data: { turbo: false } %>

<%# Confirm before navigation %>
<%= link_to "Delete", @card, method: :delete, data: { turbo_confirm: "Are you sure?" } %>
```

---

## Testing JavaScript

### System Tests with JavaScript

```ruby
class DialogTest < ApplicationSystemTestCase
  test "opening and closing dialog", js: true do
    visit cards_path

    click_on "New Card"
    assert_selector "dialog[open]"

    click_on "Cancel"
    assert_no_selector "dialog[open]"
  end
end
```

---

## Importmap (Rails 8 Default)

Rails 8 defaults to importmap for JavaScript management - no build step required.

### Configuration

```ruby
# config/importmap.rb
pin "application"
pin "@hotwired/turbo-rails", to: "turbo.min.js"
pin "@hotwired/stimulus", to: "stimulus.min.js"
pin "@hotwired/stimulus-loading", to: "stimulus-loading.js"

# Pin your controllers
pin_all_from "app/javascript/controllers", under: "controllers"

# Add third-party libraries
pin "local-time" # from jspm.io
pin "sortablejs" # from unpkg.com
```

### Adding JavaScript Libraries

```bash
# Import from CDN
bin/importmap pin local-time

# Pin specific version
bin/importmap pin sortablejs@1.15.0

# Check current pins
bin/importmap json
```

### Application Setup

```javascript
// app/javascript/application.js
import "@hotwired/turbo-rails"
import "./controllers"

// Optional: Import libraries
import LocalTime from "local-time"
LocalTime.start()
```

**When to use alternatives:**
- **esbuild/webpack**: Need npm packages not available via importmap
- **propshaft**: Simpler asset pipeline (no import maps)
- **vite**: Modern bundler with HMR

---

## Turbo 8 Features

### Page Refresh (Morphing)

Turbo 8 can morph entire pages while preserving scroll position and form state.

```erb
<%# Enable for entire app %>
<%# app/views/layouts/application.html.erb %>
<meta name="turbo-refresh-method" content="morph">
<meta name="turbo-refresh-scroll" content="preserve">
```

```ruby
# Enable for specific actions
class CardsController < ApplicationController
  def index
    # Will use morphing for page updates
    @cards = Card.all
  end
end

# Force refresh after form submit
def create
  @card = Card.create!(card_params)
  redirect_to cards_path, status: :see_other  # Triggers refresh
end
```

### Turbo Permanent Elements

Preserve elements across page navigations:

```erb
<div id="player" data-turbo-permanent>
  <%# Audio player persists across navigation %>
  <audio controls src="<%= @podcast.audio_url %>"></audio>
</div>

<div id="flash" data-turbo-permanent>
  <%# Flash messages persist during loading %>
  <%= render "shared/flash" %>
</div>
```

### Prefetching

Speed up navigation by prefetching links:

```erb
<%# Prefetch on hover %>
<%= link_to "View Card", @card, data: { turbo_prefetch: true } %>

<%# Instant navigation - prefetch on mousedown %>
<%= link_to "Dashboard", dashboard_path, data: { turbo_preload: "instant" } %>
```

---

## View Transitions (CSS)

Smooth page transitions using CSS View Transitions API with Turbo.

### Enable View Transitions

```erb
<%# app/views/layouts/application.html.erb %>
<meta name="view-transition" content="same-origin">
```

### CSS Animations

```css
/* app/assets/stylesheets/application.css */

/* Fade transition */
::view-transition-old(root),
::view-transition-new(root) {
  animation-duration: 0.3s;
}

/* Slide transition */
::view-transition-old(root) {
  animation-name: slide-out;
}

::view-transition-new(root) {
  animation-name: slide-in;
}

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

## Production-Ready Stimulus Controllers

### Clipboard Controller

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

### Dropdown Controller

```javascript
// controllers/dropdown_controller.js
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

```erb
<div data-controller="dropdown" class="dropdown">
  <button data-action="click->dropdown#toggle">
    Options ▾
  </button>

  <div data-dropdown-target="menu" data-dropdown-open-class="open" class="dropdown-menu">
    <%= link_to "Edit", edit_card_path(@card) %>
    <%= link_to "Delete", @card, method: :delete %>
  </div>
</div>
```

### Toggle Controller

```javascript
// controllers/toggle_controller.js
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

```erb
<div data-controller="toggle">
  <button data-action="click->toggle#toggle">
    Show/Hide Details
  </button>

  <div data-toggle-target="toggleable" data-toggle-hidden-class="hidden" class="hidden">
    <p>Additional details...</p>
  </div>
</div>
```

---

## Summary

- **Importmap**: Rails 8 default, no build step required
- **Stimulus**: One controller per behavior, focused and reusable
- **Targets**: Reference DOM elements
- **Values**: Pass data from HTML to JavaScript
- **Actions**: Respond to events
- **Turbo 8**: Page refresh with morphing, prefetching
- **View Transitions**: Smooth CSS animations between pages
- **Turbo Frames**: Lazy loading, scoped navigation
- **Turbo Streams**: Real-time updates
- **Progressive Enhancement**: Works without JavaScript
