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

## Turbo Streams

### Turbo Stream Template

```erb
<%# app/views/cards/create.turbo_stream.erb %>

<%# Prepend new card to list %>
<%= turbo_stream.prepend "cards", @card %>

<%# Update form with errors or clear it %>
<% if @card.persisted? %>
  <%= turbo_stream.update "new_card_form", "" %>
<% else %>
  <%= turbo_stream.replace "new_card_form" do %>
    <%= render "form", card: @card %>
  <% end %>
<% end %>

<%# Show flash message %>
<%= turbo_stream.update "flash" do %>
  <div class="alert alert-success">Card created!</div>
<% end %>
```

### Multiple Turbo Stream Actions

```erb
<%# app/views/cards/update.turbo_stream.erb %>

<%= turbo_stream.replace @card, @card %>

<%= turbo_stream.update "card_count" do %>
  <%= pluralize(Card.count, "card") %>
<% end %>

<%= turbo_stream.append "recent_activity" do %>
  <%= render "activity", card: @card, action: "updated" %>
<% end %>
```

### Turbo Stream Actions

```erb
<%# Replace %>
<%= turbo_stream.replace dom_id(@card), @card %>

<%# Update (replace innerHTML) %>
<%= turbo_stream.update dom_id(@card), partial: "cards/card" %>

<%# Append %>
<%= turbo_stream.append "cards", @card %>

<%# Prepend %>
<%= turbo_stream.prepend "cards", @card %>

<%# Remove %>
<%= turbo_stream.remove @card %>

<%# Before %>
<%= turbo_stream.before dom_id(@card), partial: "cards/notice" %>

<%# After %>
<%= turbo_stream.after dom_id(@card), partial: "cards/metadata" %>
```

---

## JSON Views (Jbuilder)

### Basic JSON Template

```ruby
# app/views/cards/show.json.jbuilder

json.id @card.id
json.title @card.title
json.description @card.description.to_plain_text
json.status @card.status
json.created_at @card.created_at
json.updated_at @card.updated_at

json.url card_url(@card)

json.creator do
  json.id @card.creator.id
  json.name @card.creator.name
  json.email @card.creator.email
end

json.tags @card.tags, :id, :title
```

### JSON with Partials

```ruby
# app/views/cards/show.json.jbuilder

json.partial! "cards/card", card: @card

json.comments @card.comments do |comment|
  json.partial! "comments/comment", comment: comment
end
```

```ruby
# app/views/cards/_card.json.jbuilder

json.cache! card do
  json.(card, :id, :number, :title, :status)
  json.description card.description.to_plain_text
  json.description_html card.description.to_s

  json.url card_url(card)
  json.created_at card.created_at.iso8601

  json.creator do
    json.partial! "users/user", user: card.creator
  end
end
```

### JSON Collection

```ruby
# app/views/cards/index.json.jbuilder

json.cards @cards do |card|
  json.partial! "cards/card", card: card
end

json.meta do
  json.total_count @cards.total_count
  json.current_page @cards.current_page
  json.total_pages @cards.total_pages
end
```

---

## Helpers in Views

### Link Helpers

```erb
<%= link_to "View Card", @card %>
<%= link_to "Edit", edit_card_path(@card), class: "btn" %>
<%= link_to "Delete", @card, method: :delete, data: { confirm: "Are you sure?" } %>

<%# Turbo-specific %>
<%= link_to "View", @card, data: { turbo_frame: "modal" } %>
<%= link_to "Edit", edit_card_path(@card), data: { turbo: false } %>
```

### Button Helpers

```erb
<%= button_to "Delete", @card, method: :delete, class: "btn btn-danger" %>
<%= button_to "Archive", archive_card_path(@card), method: :post %>
```

### Image Helpers

```erb
<%= image_tag "logo.png", alt: "Logo", class: "logo" %>
<%= image_tag card.image, size: "300x200" if card.image.attached? %>

<%# With Active Storage %>
<%= image_tag url_for(card.image) if card.image.attached? %>
<%= image_tag card.image.variant(resize_to_limit: [300, 200]) %>
```

### Content Tag Helpers

```erb
<%= content_tag :div, class: "card" do %>
  <h3><%= @card.title %></h3>
<% end %>

<%= tag.article class: "card", id: dom_id(@card) do %>
  <h3><%= @card.title %></h3>
<% end %>

<%# Self-closing tags %>
<%= tag.br %>
<%= tag.hr %>
<%= tag.img src: "logo.png" %>
```

### Text Helpers

```erb
<%= truncate(@card.description, length: 100) %>
<%= excerpt(@card.description, "keyword", radius: 50) %>
<%= highlight(@card.title, "search term") %>
<%= pluralize(@card.comments.count, "comment") %>
<%= number_to_currency(100.50) %>
<%= number_to_percentage(85.5, precision: 1) %>
<%= number_with_delimiter(1000000) %>
```

### Date/Time Helpers

```erb
<%= time_ago_in_words(@card.created_at) %> ago
<%= distance_of_time_in_words(@card.created_at, Time.current) %>

<%# Formatted %>
<%= @card.created_at.strftime("%B %d, %Y") %>
<%= l(@card.created_at, format: :long) %>

<%# Time tag %>
<time datetime="<%= @card.created_at.iso8601 %>">
  <%= @card.created_at.strftime("%b %d, %Y") %>
</time>
```

---

## Conditional Rendering

### Simple Conditionals

```erb
<% if @card.published? %>
  <span class="badge badge-published">Published</span>
<% else %>
  <span class="badge badge-draft">Draft</span>
<% end %>

<% unless @card.closed? %>
  <%= link_to "Close", card_closure_path(@card), method: :post %>
<% end %>
```

### Guard Clauses

```erb
<% if @cards.empty? %>
  <p>No cards found.</p>
<% else %>
  <%= render @cards %>
<% end %>

<%# With present? %>
<% if @card.description.present? %>
  <div class="description">
    <%= @card.description %>
  </div>
<% end %>
```

### Ternary Operator

```erb
<span class="status <%= @card.published? ? "active" : "inactive" %>">
  <%= @card.status %>
</span>

<%= link_to(@card.closed? ? "Reopen" : "Close", card_closure_path(@card)) %>
```

---

## Iteration

### Each Loop

```erb
<% @cards.each do |card| %>
  <%= render card %>
<% end %>

<%# With index %>
<% @cards.each_with_index do |card, index| %>
  <div class="card" data-index="<%= index %>">
    <%= render card %>
  </div>
<% end %>
```

### Collection Rendering

```erb
<%# Preferred way - cleaner %>
<%= render @cards %>

<%# Same as: %>
<% @cards.each do |card| %>
  <%= render "cards/card", card: card %>
<% end %>
```

### Grouped Collections

```erb
<% @cards.group_by(&:status).each do |status, cards| %>
  <section class="status-group">
    <h2><%= status.humanize %></h2>
    <%= render cards %>
  </section>
<% end %>
```

---

## Best Practices

### ✅ DO

1. **Keep views simple** - No business logic
```erb
<%# Good %>
<%= render @card if @card.published? %>

<%# Bad %>
<% if @card.status == "published" && @card.visible_to?(current_user) && @card.approved? %>
  <%= render @card %>
<% end %>
```

2. **Use explicit locals in partials**
```erb
<%# Good %>
<%= render "card", card: @card, show_actions: true %>

<%# Bad - relies on instance variables %>
<%= render "card" %>
```

3. **Extract complex view logic to helpers**
```erb
<%# Good %>
<%= card_status_badge(@card) %>

<%# Bad %>
<span class="badge badge-<%= @card.status.dasherize %> <%= 'urgent' if @card.urgent? %>">
  <%= @card.status.humanize %>
</span>
```

4. **Use fragment caching**
```erb
<% cache @card do %>
  <%= render @card %>
<% end %>
```

5. **Use semantic HTML**
```erb
<article class="card">
  <header><h1><%= @card.title %></h1></header>
  <section><%= @card.description %></section>
  <footer><%= render "card/actions" %></footer>
</article>
```

### ❌ DON'T

1. **Database queries in views**
```erb
<%# Bad %>
<% Card.where(status: :published).each do |card| %>
  <%= render card %>
<% end %>

<%# Good - query in controller %>
<%= render @published_cards %>
```

2. **Complex Ruby logic**
```erb
<%# Bad %>
<% total = @cards.inject(0) { |sum, card| sum + card.value } %>

<%# Good - method in model/helper %>
<%= @cards.total_value %>
```

3. **Inline styles**
```erb
<%# Bad %>
<div style="color: red; font-size: 14px;">

<%# Good %>
<div class="error-message">
```

4. **Raw HTML without sanitization**
```erb
<%# Bad %>
<%= @card.description.html_safe %>

<%# Good %>
<%= sanitize @card.description %>
<%= @card.description %>  <%# If it's already safe from model %>
```

---

## Testing Views

### View Tests (Helper Tests)

```ruby
# test/helpers/cards_helper_test.rb
class CardsHelperTest < ActionView::TestCase
  test "card_status_badge returns correct badge" do
    card = cards(:published)

    badge = card_status_badge(card)

    assert_match /badge/, badge
    assert_match /published/, badge
  end
end
```

### Testing Partials

```ruby
# In controller tests, partials are rendered
test "index renders cards" do
  get cards_path

  assert_select ".card", count: Card.count
  assert_select "h3", text: cards(:logo).title
end
```

---

## Summary

- **Structure**: Layouts, templates, partials, shared
- **Partials**: Explicit locals, collection rendering, caching
- **Forms**: Form builders, nested forms, error handling
- **Turbo Streams**: Real-time updates without full page reload
- **JSON**: Jbuilder for API responses
- **Helpers**: Link, button, image, text, date helpers
- **Best Practices**: Keep views simple, no business logic, use helpers
- **Caching**: Fragment caching for performance
