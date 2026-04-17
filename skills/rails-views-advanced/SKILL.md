---
name: rails-views-advanced
description: "Rails views advanced: Turbo Streams, JSON/Jbuilder, helpers in views, conditional rendering, and best practices"
---

# Views (Advanced)

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

### DO

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

### DON'T

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
