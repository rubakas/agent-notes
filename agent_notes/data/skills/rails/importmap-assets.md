# Importmap, Propshaft & Thruster

## Contents

- [Importmap](#importmap)
- [Propshaft & CSS](#propshaft--css)
- [Thruster](#thruster)
- [Sources](#sources)

## Importmap

Importmap is Rails' default for JavaScript: no bundler, each module is pinned to a file the browser loads directly. `pin` names one module, and `pin_all_from` pins a whole directory under a prefix. Fizzy pins `controllers/`, `helpers/`, `lib/` and `initializers/` separately, so a new directory needs its own pin.

```ruby
# config/importmap.rb
pin "application"
pin "@hotwired/turbo-rails", to: "turbo.min.js"
pin "@hotwired/turbo/offline", to: "turbo-offline.min.js"
pin "@hotwired/stimulus", to: "stimulus.min.js"
pin "@hotwired/stimulus-loading", to: "stimulus-loading.js"
pin "@hotwired/hotwire-native-bridge", to: "@hotwired--hotwire-native-bridge.js"
pin "@rails/request.js", to: "@rails--request.js" # @0.0.13
# ...
pin_all_from "app/javascript/controllers", under: "controllers"
pin_all_from "app/javascript/helpers", under: "helpers"
pin_all_from "app/javascript/lib", under: "lib"
pin_all_from "app/javascript/initializers", under: "initializers"
```

The Active Storage and Action Text browser libraries come from the Rails gems; downloaded packages live in `vendor/javascript/` (for example `@rails--request.js`):

```ruby
# config/importmap.rb
pin "lexxy"
pin "@rails/activestorage", to: "activestorage.esm.js"
pin "@rails/actiontext", to: "actiontext.esm.js"
```

`bin/importmap audit` checks pinned packages for known vulnerabilities; Fizzy runs it as a CI step.

```ruby
# config/ci.rb
  step "Security: Importmap audit", "bin/importmap audit"
```

Why: pins keep dependencies explicit without a build step (Fizzy: `config/importmap.rb`, `config/ci.rb`).

## Propshaft & CSS

Propshaft serves the files in `app/assets/stylesheets/` with digested URLs and does no preprocessing. `stylesheet_link_tag :app` links every stylesheet under `app/assets` (not those from gems), so adding a file needs no manifest edit.

```erb
<%# app/views/layouts/shared/_head.html.erb %>
  <%= stylesheet_link_tag :app, "data-turbo-track": "reload" %>
  <%= javascript_importmap_tags %>
```

Fizzy writes plain CSS. Because Propshaft does not transform it, features like custom properties, native nesting and `@layer` work only because current browsers support them. `base.css` opens with `@layer base` and uses nesting. At the pinned commit there are 64 stylesheets.

```css
/* app/assets/stylesheets/base.css */
@layer base {
  html {
    font-size: 100%;

    @media (min-width: 100ch) {
      font-size: 1.1875rem;
    }
  }
```

```css
/* app/assets/stylesheets/base.css */
  a {
    text-decoration: none;

    &:not([class]) {
      color: var(--color-link);
      text-decoration: underline;
      text-decoration-skip-ink: auto;
    }
  }
```

Why: a no-build asset pipeline leaves the browser to do the work that Sass or PostCSS would do (Propshaft docs: https://github.com/rails/propshaft; Fizzy: `app/assets/stylesheets/base.css`).

## Thruster

Thruster is a small proxy in front of Puma. It adds HTTP/2, automatic TLS (when `TLS_DOMAIN` is set), caching of public assets, and X-Sendfile and compression for static files. Run Puma through it by prefixing the server command with `thrust`. Fizzy's Dockerfile exposes port 80 and starts the server through `bin/thrust`:

```dockerfile
# Dockerfile
# Start server via Thruster by default, this can be overwritten at runtime
EXPOSE 80
CMD ["./bin/thrust", "./bin/rails", "server"]
```

Thruster's settings are environment variables, optionally prefixed with `THRUSTER_`. Fizzy's deployment guide (`docs/docker-deployment.md`) tells operators importing very large exports to raise `THRUSTER_HTTP_READ_TIMEOUT` (seconds), because Thruster drops slow uploads after its read timeout.

Why: Thruster gives a single container a production-ready edge with no extra configuration (Thruster README: https://github.com/basecamp/thruster).

## Sources

- [Importmap Rails](https://github.com/rails/importmap-rails)
- [Propshaft](https://github.com/rails/propshaft)
- [Thruster README](https://github.com/basecamp/thruster)
- Fizzy at 6aebc0cea: `config/importmap.rb`, `config/ci.rb`, `Dockerfile`, `docs/docker-deployment.md`
