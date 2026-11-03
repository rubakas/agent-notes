# Stimulus Controllers

## Contents

- [Philosophy](#philosophy)
- [File Structure](#file-structure)
- [Controller Template](#controller-template)
- [Stimulus Patterns](#stimulus-patterns)
- [Sources](#sources)

## Philosophy

- **One controller per behavior.** Each file handles one distinct interaction (`auto_submit`, `copy_to_clipboard`, `toggle_class`).
- **Small controllers.** The 61 top-level controllers average about 50 lines; push heavier logic into `helpers/` modules or the server.
- **Private members use `#`.** Internal methods and fields are real JavaScript private members (`#markAsBusy()`, `#isComposing`).
- **Events via `this.dispatch()`.** Controllers announce changes (`dialog:show`, `dialog:close`) and other controllers listen with `data-action`.
- **HTML over JavaScript.** The server sends HTML; Stimulus enhances it.

Why: small single-purpose controllers compose through `data-controller` and `data-action` in the markup (Fizzy: `app/javascript/controllers/dialog_controller.js`).

## File Structure

Controllers sit in `app/javascript/controllers/` and are loaded by `controllers/index.js` with `eagerLoadControllersFrom`. Helpers and initializers are siblings of `controllers/`, not children. Excerpt at the pinned commit:

```
app/javascript/
├── application.js
├── controllers/
│   ├── application.js
│   ├── index.js
│   ├── auto_submit_controller.js
│   ├── dialog_controller.js
│   ├── form_controller.js
│   └── bridge/
│       ├── form_controller.js
│       └── title_controller.js
├── helpers/
│   ├── timing_helpers.js
│   ├── platform_helpers.js
│   └── orientation_helpers.js
├── initializers/
│   ├── index.js
│   ├── current.js
│   └── offline.js
└── lib/
vendor/javascript/
└── @hotwired--hotwire-native-bridge.js
```

Controllers in a subdirectory get a namespaced identifier (`controllers/bridge/form_controller.js` is `bridge--form`). Helpers are plain modules imported by name (`import { debounce } from "helpers/timing_helpers"`). `initializers/offline.js` starts the offline cache, which comes from an unreleased turbo-rails offline-cache fork (`Gemfile` pins the `offline-cache` branch); do not depend on it in a normal app.

Why: the importmap pins each directory separately, so `helpers/` and `initializers/` need their own pins (Fizzy: `config/importmap.rb`).

## Controller Template

A controller declares its needs with `static targets`, `static values` and `static classes`, then defines public action methods and private helpers.

```javascript
// app/javascript/controllers/auto_submit_controller.js
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  connect() {
    this.element.addEventListener("turbo:submit-end", this.#handleSubmitEnd.bind(this), { once: true })
    this.submit()
  }

  submit() {
    this.#markAsBusy()
    this.#disableSubmit()
    this.element.requestSubmit()
  }
```

`form_controller.js` shows values, a private field and `initialize()` wiring a debounced method:

```javascript
// app/javascript/controllers/form_controller.js
import { Controller } from "@hotwired/stimulus"
import { debounce, nextFrame } from "helpers/timing_helpers";

export default class extends Controller {
  static targets = [ "cancel", "submit", "input" ]

  static values = {
    debounceTimeout: { type: Number, default: 300 }
  }

  #isComposing = false

  initialize() {
    this.debouncedSubmit = debounce(this.debouncedSubmit.bind(this), this.debounceTimeoutValue)
  }
```

Practices seen here:

- Declare targets, values and classes statically.
- Use `#` for private methods and fields.
- Add `disconnect()` only when something must be cleaned up (10 of the 61 top-level controllers define it).
- Use `.bind(this)` when a method is passed as a listener (14 of the 61 do).

Why: static declarations make a controller's inputs visible at the top of the file (Fizzy: `app/javascript/controllers/auto_submit_controller.js`).

## Stimulus Patterns

**Auto-submit form.** `auto_submit_form_with` adds the `auto-submit` controller, which submits the form on connect and removes it after a successful response.

```erb
<%# app/views/searches/show.html.erb %>
      <%= auto_submit_form_with url: card_path(@card), method: :get, data: { turbo_action: "advance", turbo_frame: "_top", search_redirect: true } %>
```

**Keyboard and outside-click actions.** `data-action` takes key filters (`keydown.esc`) and a global target (`click@document`). Modifiers such as `:prevent` and `:stop` appear in `app/views/cards/edit.html.erb`.

```erb
<%# app/views/boards/show/menu/_columns.html.erb %>
<div class="cards__new-column" data-controller="dialog" data-action="keydown.esc->dialog#close click@document->dialog#closeOnClickOutside" data-turbo-permanent>
```

**Dialog controller.** Wraps a native `<dialog>` and dispatches `show` and `close` events.

```javascript
// app/javascript/controllers/dialog_controller.js
  close() {
    this.dialogTarget.close()
    this.dialogTarget.setAttribute("aria-hidden", "true")
    this.dialogTarget.blur()
    orient({ target: this.dialogTarget, reset: true })
    this.dispatch("close")
  }

  closeOnClickOutside({ target }) {
    if (!this.element.contains(target)) this.close()
  }
```

**Clipboard controller.** Copies a value and marks the element with a CSS class.

```javascript
// app/javascript/controllers/copy_to_clipboard_controller.js
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static values = { content: String }
  static classes = [ "success" ]

  async copy(event) {
    event.preventDefault()
    this.reset()

    try {
      await navigator.clipboard.writeText(this.contentValue)
      this.element.classList.add(this.successClass)
    } catch {}
  }
```

**Toggle controller.** One controller toggles a CSS class passed in through `static classes`.

```javascript
// app/javascript/controllers/toggle_class_controller.js
export default class extends Controller {
  static classes = [ "toggle" ]
  static targets = [ "checkbox" ]

  toggle() {
    this.element.classList.toggle(this.toggleClass)
  }

  add() {
    this.element.classList.add(this.toggleClass)
  }

  remove() {
    this.element.classList.remove(this.toggleClass)
  }
```

Why: each pattern is a small controller driven entirely by `data-*` attributes (Fizzy: `app/javascript/controllers/`; Stimulus handbook: https://stimulus.hotwired.dev/handbook/introduction).

## Sources

- Fizzy at 6aebc0cea: `app/javascript`, `config/importmap.rb`, `Gemfile`
- [Stimulus handbook](https://stimulus.hotwired.dev/handbook/introduction)
