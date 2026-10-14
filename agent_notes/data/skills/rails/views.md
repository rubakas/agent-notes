# Views

## Contents

- [Philosophy](#philosophy)
- [File Structure](#file-structure)
- [Standard View Template](#standard-view-template)
- [Partials](#partials)
- [Optional Locals](#optional-locals)
- [Layouts](#layouts)
- [Forms](#forms)
- [Destructive Buttons](#destructive-buttons)
- [Helpers in Views](#helpers-in-views)
- [JSON Views (Jbuilder)](#json-views-jbuilder)
- [Sources](#sources)

## Philosophy

1. **Keep views presentational.** Pass data in explicitly, and move attribute-building logic into helpers (`card_article_tag`, `local_datetime_tag`) rather than inline Ruby.
2. **Partials take explicit locals.** Render collections with `render partial:, collection:, cached: true`.
3. **Optional locals use `local_assigns.fetch(:key, default)`.**
4. **Per-page layout slots use `content_for`** (`:head`, `:header`, `:footer`), and per-page state uses instance variables (`@page_title`).

Why: views stay readable and cacheable when the logic lives in helpers and models (Fizzy: `app/views/cards/display/_preview.html.erb`, `app/helpers/cards_helper.rb`).

## File Structure

Fizzy nests partials by resource and then by role (`cards/display/preview/`, `cards/container/`). There is no top-level `shared/` directory; the only one is `layouts/shared/`. Excerpt of `app/views/` at the pinned commit:

```
app/views/
├── layouts/
│   ├── application.html.erb
│   ├── mailer.html.erb
│   ├── public.html.erb
│   └── shared/
│       ├── _head.html.erb
│       └── _flash.html.erb
├── cards/
│   ├── show.html.erb
│   ├── edit.html.erb
│   ├── update.turbo_stream.erb
│   ├── _container.html.erb
│   ├── _card.json.jbuilder
│   ├── display/
│   │   ├── _preview.html.erb
│   │   └── preview/_meta.html.erb
│   └── comments/
│       ├── _comment.html.erb
│       └── create.turbo_stream.erb
└── boards/
    ├── show.html.erb
    └── show/
        ├── _column.html.erb
        └── _columns.html.erb
```

Turbo stream templates (`.turbo_stream.erb`) and JSON views (`.json.jbuilder`) sit next to the HTML template for the same action.

Why: a resource-then-role hierarchy keeps related partials together (Fizzy: `app/views/cards`).

## Standard View Template

A view sets `@page_title` for the layout, fills layout slots with `content_for`, subscribes to broadcasts with `turbo_stream_from`, and renders partials.

```erb
<%# app/views/cards/show.html.erb %>
<% @page_title = @card.title %>
<% @header_class = "header--card" %>

<% content_for :head do %>
  <%= card_social_tags(@card) %>
<% end %>
<%# ... %>
<%= turbo_stream_from @card %>
<%= turbo_stream_from @card, :activity %>
```

Why: the layout reads these slots and variables, so each page declares its own head, header and subscriptions in one place (Fizzy: `app/views/cards/show.html.erb`).

## Partials

Fragment-cache the record inside the partial, and render collections with `cached: true`. Fizzy leaves a dated ERB comment inside a cached partial (`Helper Dependency Updated: ...`, `Cache bump ...`) when a helper or rendering change should invalidate it.

```erb
<%# app/views/cards/comments/_comment.html.erb %>
<% cache comment do %>
  <%# Helper Dependency Updated: avatar_image_tag 2025-12-15 %>
```

Collections pass `cached: true` so each record's fragment is cached separately:

```erb
<%# app/views/cards/_messages.html.erb %>
    <%= render partial: "cards/comments/comment", collection: card.comments.preloaded.chronologically, cached: true %>
```

Why: per-record fragments are reused across pages, and the dated comment changes the template digest so stale fragments expire (Fizzy: `app/views/cards/comments/_comment.html.erb`).

## Optional Locals

Use `local_assigns.fetch` to give an optional local a default. Fizzy does not use strict-locals magic comments.

```erb
<%# app/views/cards/display/_preview.html.erb %>
<% draggable = local_assigns.fetch(:draggable, false) && card.published? %>
```

Why: a plain `fetch` works in every Rails version and keeps the default next to the use (Fizzy: `app/views/cards/display/_preview.html.erb`).

## Layouts

The layout delegates `<head>` to a partial and exposes slots such as `yield :header`. Page refreshes are morphed by declaring `turbo_refreshes_with` once in the head partial.

```erb
<%# app/views/layouts/application.html.erb %>
<!DOCTYPE html>
<html lang="en">
  <%= render "layouts/shared/head" %>
<%# ... %>
        <%= yield :header %>
```

```erb
<%# app/views/layouts/shared/_head.html.erb %>
<head>
  <%= page_title_tag %>
<%# ... %>
  <% turbo_refreshes_with method: :morph, scroll: :preserve %>
```

`page_title_tag` (`app/helpers/application_helper.rb`) builds the `<title>` from `@page_title`, the account name when the identity has several accounts, and "Fizzy". The flash partial wraps itself in `turbo_frame_tag :flash` so a Turbo Stream can replace it.

```erb
<%# app/views/layouts/shared/_flash.html.erb %>
<%= turbo_frame_tag :flash do %>
  <% if notice = flash[:notice] || flash[:alert] %>
```

Why: one place declares morphing for every page, and the flash frame is a stable target for streams (Fizzy: `app/views/layouts/shared/_head.html.erb`).

## Forms

Forms use `form_with model:` plus Fizzy's Stimulus controllers on the form element, and `rich_textarea` for Action Text fields. `auto_submit_form_with` and `bridged_form_with` prepend a Stimulus controller to `data[:controller]`.

```erb
<%# app/views/cards/edit.html.erb %>
  <%= form_with model: @card, id: dom_id(@card, :edit_form),
        data: { controller: "autoresize form local-save morph-guard", local_save_key_value: "card-#{@card.id}", action: "turbo:submit-end->local-save#submit" } do |form| %>
<%# ... %>
    <%= form.rich_textarea :description, class: "card__description lexxy-content",
          placeholder: "Add some notes, context, pictures, or video about this…",
          data: { local_save_target: "input", action: "lexxy:change->local-save#save turbo:morph-element->local-save#restoreContent keydown.ctrl+enter->form#submit:prevent keydown.meta+enter->form#submit:prevent keydown.esc->form#cancel:stop" } do %>
      <%= general_prompts(@card.board) %>
    <% end %>
```

The two form helpers are excerpted in helpers.md.

Why: form behavior is declared with `data-controller` instead of per-form JavaScript (Fizzy: `app/helpers/forms_helper.rb`).

## Destructive Buttons

Delete with `button_to ..., method: :delete`, which renders a one-button form. Add a confirmation through the form's `data` (`form: { data: { turbo_confirm: ... } }`).

```erb
<%# app/views/boards/show/menu/_column.html.erb %>
        <%= button_to board_column_path(column.board, column),
              method: :delete,
              class: "popup__btn btn txt-negative",
                form_class: "display-contents",
              form: { data: { turbo_confirm: "Are you sure you want to delete this column? This will move the cards back to Maybe." } } do %>
          <%= icon_tag "trash" %>
          <span>Delete column</span>
        <% end %>
```

When the delete form lives elsewhere on the page, a plain submit button that points at it with `form:` carries `turbo_confirm` in its own `data`:

```erb
<%# app/views/cards/comments/edit.html.erb %>
            <%= tag.button type: :submit, class: "btn btn--negative flex-item-justify-end", form: dom_id(@comment, :delete_form),
                  data: { turbo_confirm: "Are you sure you want to delete this comment?" } do %>
```

Why: Turbo shows its confirm prompt before submitting the form (Fizzy: `app/views/boards/show/menu/_column.html.erb`).

## Helpers in Views

Helpers build tag attributes. `card_article_tag` computes CSS classes from card state, and `local_datetime_tag` emits a `<time>` that a Stimulus controller formats in the browser, so the markup stays cacheable across time zones. Both helpers are excerpted in helpers.md.

Why: the same markup serves every user while the browser localizes it (Fizzy: `app/helpers/time_helper.rb`).

## JSON Views (Jbuilder)

A `show.json.jbuilder` renders the partial and adds extras. The partial wraps its body in `json.cache!`, and collections are rendered with `partial:` and `as:` (optionally `cached: true`).

```ruby
# app/views/cards/show.json.jbuilder
json.partial! "cards/card", card: @card
json.steps @card.steps, partial: "cards/steps/step", as: :step
```

The `_card.json.jbuilder` partial and the cached collection render for notifications are excerpted in view-caching.md.

Why: JSON responses reuse the same fragment cache and partials as the HTML views (Fizzy: `app/views/cards/_card.json.jbuilder`).

## Sources

- Fizzy at 6aebc0cea: `app/views`, `app/helpers`
- Rails guides: layouts and rendering, caching with Rails, Jbuilder
