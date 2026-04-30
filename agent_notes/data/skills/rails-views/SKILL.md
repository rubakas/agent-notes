---
name: rails-views
description: "Rails views: templates, partials, layouts, caching, and forms. Use when user is writing ERB templates, partials, or form helpers in Rails views."
group: rails
---

# Views Guide

Comprehensive guide for Rails views, partials, and templates.

---

## Philosophy

1. **Views are for presentation only** - No business logic
2. **Keep views dumb** - Complex logic goes in helpers or models
3. **DRY with partials** - Extract reusable view fragments
4. **Explicit locals** - Always pass data explicitly to partials
5. **Fragment caching** - Cache expensive view fragments

---

## File Structure

```
app/views/
├── layouts/
│   ├── application.html.erb      # Main layout
│   ├── mailer.html.erb           # Email layout
│   └── admin.html.erb            # Admin layout
├── cards/
│   ├── index.html.erb            # Template
│   ├── show.html.erb
│   ├── _card.html.erb            # Partial (starts with _)
│   ├── _form.html.erb
│   └── display/                   # Nested partials
│       ├── _preview.html.erb
│       └── _details.html.erb
└── shared/
    ├── _header.html.erb          # Shared partials
    └── _footer.html.erb
```

---

## Basic Template Structure

### Standard View Template

```erb
<%# app/views/cards/show.html.erb %>

<%# Set page title %>
<% content_for :title, @card.title %>

<%# Set meta tags %>
<% content_for :head do %>
  <%= card_social_tags(@card) %>
<% end %>

<div class="card-container">
  <header class="card-header">
    <h1><%= @card.title %></h1>
    <%= render "cards/metadata", card: @card %>
  </header>

  <div class="card-body">
    <%= render "cards/description", card: @card %>
  </div>

  <footer class="card-footer">
    <%= render "cards/actions", card: @card %>
  </footer>
</div>

<%# Render comments %>
<section id="comments">
  <%= render @card.comments %>
</section>
```

### Index Template

```erb
<%# app/views/cards/index.html.erb %>

<div class="cards-header">
  <h1>Cards</h1>
  <%= link_to "New Card", new_card_path, class: "btn btn-primary" %>
</div>

<div class="cards-grid">
  <%= render @cards %>
</div>

<%# Pagination %>
<%= paginate @cards %>
```

### Form Template

```erb
<%# app/views/cards/new.html.erb %>

<h1>New Card</h1>

<%= render "form", card: @card %>

<%= link_to "Back", cards_path %>
```

---

## Partials

### Basic Partial

```erb
<%# app/views/cards/_card.html.erb %>

<article class="card" id="<%= dom_id(card) %>">
  <h3><%= link_to card.title, card %></h3>

  <div class="card-meta">
    <span class="author">by <%= card.creator.name %></span>
    <time datetime="<%= card.created_at.iso8601 %>">
      <%= time_ago_in_words(card.created_at) %> ago
    </time>
  </div>

  <% if card.description.present? %>
    <div class="card-description">
      <%= truncate(card.description.to_plain_text, length: 200) %>
    </div>
  <% end %>
</article>
```

### Partial with Explicit Locals

```erb
<%# app/views/cards/_metadata.html.erb %>

<div class="metadata">
  <span class="status">
    <%= content_tag :span, card.status.humanize, class: "badge badge-#{card.status}" %>
  </span>

  <% if show_board %>
    <span class="board">
      <%= link_to card.board.name, card.board %>
    </span>
  <% end %>

  <% if card.tags.any? %>
    <div class="tags">
      <%= render card.tags %>
    </div>
  <% end %>
</div>

<%# Usage with explicit locals: %>
<%# <%= render "cards/metadata", card: @card, show_board: true %> %>
```

### Partial Collection

```erb
<%# Renders cards/_card.html.erb for each card %>
<%= render @cards %>

<%# Same as: %>
<%= render partial: "cards/card", collection: @cards %>

<%# With custom local name: %>
<%= render partial: "cards/card", collection: @cards, as: :item %>

<%# With spacer: %>
<%= render partial: "cards/card", collection: @cards, spacer_template: "cards/spacer" %>
```

### Partial with Counter

```erb
<%# app/views/cards/_card.html.erb %>

<article class="card" data-index="<%= card_counter %>">
  <h3>#<%= card_counter + 1 %> - <%= card.title %></h3>
</article>

<%# When rendering collection, card_counter is automatically available %>
```

### Conditional Partials

```erb
<% if user_signed_in? %>
  <%= render "cards/actions", card: @card %>
<% end %>

<% if @card.published? %>
  <%= render "cards/public_info", card: @card %>
<% else %>
  <%= render "cards/draft_notice", card: @card %>
<% end %>
```

---

## Layouts

### Application Layout

```erb
<%# app/views/layouts/application.html.erb %>

<!DOCTYPE html>
<html>
  <head>
    <title><%= content_for?(:title) ? yield(:title) : "My App" %></title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <%= csrf_meta_tags %>
    <%= csp_meta_tag %>

    <%= stylesheet_link_tag "application", "data-turbo-track": "reload" %>
    <%= javascript_importmap_tags %>

    <%= yield :head %>
  </head>

  <body>
    <%= render "shared/header" %>

    <main>
      <% if notice.present? %>
        <div class="alert alert-notice"><%= notice %></div>
      <% end %>

      <% if alert.present? %>
        <div class="alert alert-alert"><%= alert %></div>
      <% end %>

      <%= yield %>
    </main>

    <%= render "shared/footer" %>
  </body>
</html>
```

### Custom Layout

```erb
<%# app/views/layouts/admin.html.erb %>

<!DOCTYPE html>
<html>
  <head>
    <title>Admin - <%= content_for?(:title) ? yield(:title) : "Dashboard" %></title>
    <%= csrf_meta_tags %>
    <%= stylesheet_link_tag "admin", "data-turbo-track": "reload" %>
  </head>

  <body class="admin-layout">
    <%= render "admin/sidebar" %>

    <main class="admin-content">
      <%= yield %>
    </main>
  </body>
</html>
```

### Content For

```erb
<%# In view: %>
<% content_for :title, "Custom Page Title" %>

<% content_for :head do %>
  <meta name="description" content="Page description">
<% end %>

<% content_for :sidebar do %>
  <nav>
    <%= link_to "Link 1", path1 %>
    <%= link_to "Link 2", path2 %>
  </nav>
<% end %>

<%# In layout: %>
<title><%= yield :title %></title>
<%= yield :head %>
<aside><%= yield :sidebar %></aside>
```

---

## Caching

### Fragment Caching

```erb
<%# Cache a partial %>
<% cache @card do %>
  <%= render @card %>
<% end %>

<%# Cache with custom key %>
<% cache ["card", @card.id, @card.updated_at] do %>
  <%= render @card %>
<% end %>

<%# Cache with multiple dependencies %>
<% cache [@card, @card.tags.maximum(:updated_at)] do %>
  <%= render "cards/card_with_tags", card: @card %>
<% end %>
```

### Collection Caching

```erb
<%# Automatically caches each item %>
<%= render partial: "cards/card", collection: @cards, cached: true %>

<%# With custom cache key %>
<%= render partial: "cards/card", collection: @cards, cached: -> card { [card, "v2"] } %>
```

### Conditional Caching

```erb
<% cache_if user_signed_in?, @card do %>
  <%= render @card %>
<% end %>

<% cache_unless @card.draft?, @card do %>
  <%= render @card %>
<% end %>
```

---

## Forms

### Form Builder

```erb
<%# app/views/cards/_form.html.erb %>

<%= form_with model: card do |form| %>
  <% if card.errors.any? %>
    <div class="error-messages">
      <h3><%= pluralize(card.errors.count, "error") %> prohibited this card from being saved:</h3>
      <ul>
        <% card.errors.full_messages.each do |message| %>
          <li><%= message %></li>
        <% end %>
      </ul>
    </div>
  <% end %>

  <div class="field">
    <%= form.label :title %>
    <%= form.text_field :title, autofocus: true, class: "form-control" %>
  </div>

  <div class="field">
    <%= form.label :description %>
    <%= form.rich_text_area :description %>
  </div>

  <div class="field">
    <%= form.label :status %>
    <%= form.select :status, Card.statuses.keys, {}, class: "form-control" %>
  </div>

  <div class="field">
    <%= form.label :board_id %>
    <%= form.collection_select :board_id, current_user.boards, :id, :name, {}, class: "form-control" %>
  </div>

  <div class="actions">
    <%= form.submit class: "btn btn-primary" %>
  </div>
<% end %>
```

### Nested Forms

```erb
<%= form_with model: @card do |card_form| %>
  <%= card_form.text_field :title %>

  <h3>Steps</h3>
  <%= card_form.fields_for :steps do |step_form| %>
    <%= render "step_fields", form: step_form %>
  <% end %>

  <%= link_to "Add Step", "#", data: { action: "nested-form#add" } %>

  <%= card_form.submit %>
<% end %>

<%# _step_fields.html.erb %>
<div class="nested-fields">
  <%= form.text_field :title %>
  <%= form.check_box :completed %>
  <%= link_to "Remove", "#", data: { action: "nested-form#remove" } %>
</div>
```

---
