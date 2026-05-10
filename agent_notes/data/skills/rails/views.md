# Views

## Views — Templates, Partials, Layouts, Forms

Comprehensive guide for Rails views, partials, and templates.

---

### Philosophy

1. **Views are for presentation only** - No business logic
2. **Keep views dumb** - Complex logic goes in helpers or models
3. **DRY with partials** - Extract reusable view fragments
4. **Explicit locals** - Always pass data explicitly to partials
5. **Fragment caching** - Cache expensive view fragments

---

### File Structure

```
app/views/
├── layouts/
│   ├── application.html.erb
│   └── mailer.html.erb
├── cards/
│   ├── index.html.erb
│   ├── show.html.erb
│   ├── _card.html.erb            # Partial (starts with _)
│   ├── _form.html.erb
│   └── display/
│       ├── _preview.html.erb
│       └── _details.html.erb
└── shared/
    ├── _header.html.erb
    └── _footer.html.erb
```

---

### Standard View Template

```erb
<%# app/views/cards/show.html.erb %>

<% content_for :title, @card.title %>

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

<section id="comments">
  <%= render @card.comments %>
</section>
```

---

### Partials

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

<%# Collection rendering %>
<%= render @cards %>
<%= render partial: "cards/card", collection: @cards %>
<%= render partial: "cards/card", collection: @cards, cached: true %>

<%# With counter (card_counter auto-available) %>
<article data-index="<%= card_counter %>">
```

---

### Layouts

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

```erb
<%# content_for in views %>
<% content_for :title, "Custom Page Title" %>

<% content_for :head do %>
  <meta name="description" content="Page description">
<% end %>

<% content_for :sidebar do %>
  <nav>
    <%= link_to "Link 1", path1 %>
  </nav>
<% end %>
```

---

### Caching

```erb
<%# Fragment caching %>
<% cache @card do %>
  <%= render @card %>
<% end %>

<% cache ["card", @card.id, @card.updated_at] do %>
  <%= render @card %>
<% end %>

<% cache [@card, @card.tags.maximum(:updated_at)] do %>
  <%= render "cards/card_with_tags", card: @card %>
<% end %>

<%# Collection caching %>
<%= render partial: "cards/card", collection: @cards, cached: true %>

<%# Conditional caching %>
<% cache_if user_signed_in?, @card do %>
  <%= render @card %>
<% end %>
```

---

### Forms

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

---

## Views — Advanced (Turbo Streams, JSON, Helpers)

### Turbo Stream Templates

```erb
<%# app/views/cards/create.turbo_stream.erb %>

<%= turbo_stream.prepend "cards", @card %>

<% if @card.persisted? %>
  <%= turbo_stream.update "new_card_form", "" %>
<% else %>
  <%= turbo_stream.replace "new_card_form" do %>
    <%= render "form", card: @card %>
  <% end %>
<% end %>

<%= turbo_stream.update "flash" do %>
  <div class="alert alert-success">Card created!</div>
<% end %>
```

```erb
<%# All Turbo Stream actions %>
<%= turbo_stream.replace dom_id(@card), @card %>
<%= turbo_stream.update dom_id(@card), partial: "cards/card" %>
<%= turbo_stream.append "cards", @card %>
<%= turbo_stream.prepend "cards", @card %>
<%= turbo_stream.remove @card %>
<%= turbo_stream.before dom_id(@card), partial: "cards/notice" %>
<%= turbo_stream.after dom_id(@card), partial: "cards/metadata" %>
```

---

### JSON Views (Jbuilder)

```ruby
# app/views/cards/show.json.jbuilder
json.id @card.id
json.title @card.title
json.description @card.description.to_plain_text
json.status @card.status
json.created_at @card.created_at
json.url card_url(@card)

json.creator do
  json.id @card.creator.id
  json.name @card.creator.name
end

json.tags @card.tags, :id, :title
```

```ruby
# app/views/cards/_card.json.jbuilder
json.cache! card do
  json.(card, :id, :number, :title, :status)
  json.description card.description.to_plain_text
  json.url card_url(card)
  json.created_at card.created_at.iso8601

  json.creator do
    json.partial! "users/user", user: card.creator
  end
end
```

---

### Helpers in Views

```erb
<%# Link helpers %>
<%= link_to "View Card", @card %>
<%= link_to "Edit", edit_card_path(@card), class: "btn" %>
<%= link_to "Delete", @card, method: :delete, data: { confirm: "Are you sure?" } %>
<%= link_to "View", @card, data: { turbo_frame: "modal" } %>

<%# Button helpers %>
<%= button_to "Delete", @card, method: :delete, class: "btn btn-danger" %>

<%# Image helpers %>
<%= image_tag @user.avatar.variant(resize_to_limit: [200, 200]) %>

<%# Content tag helpers %>
<%= tag.article class: "card", id: dom_id(@card) do %>
  <h3><%= @card.title %></h3>
<% end %>

<%# Text helpers %>
<%= truncate(@card.description, length: 100) %>
<%= pluralize(@card.comments.count, "comment") %>
<%= number_to_currency(100.50) %>

<%# Date/time helpers %>
<%= time_ago_in_words(@card.created_at) %> ago
<time datetime="<%= @card.created_at.iso8601 %>">
  <%= @card.created_at.strftime("%b %d, %Y") %>
</time>
```

---

## ViewComponent

A framework for building reusable, testable & encapsulated view components in Ruby on Rails.

### Philosophy

**"ViewComponent is to UI what ActiveRecord is to SQL"**

- **Over 100x faster** than similar controller tests
- **Reusable** - Build once, use anywhere
- **Testable** - Unit test with `render_inline`
- **Encapsulated** - Self-contained logic and templates

---

### File Structure

```
app/components/
├── application_component.rb
├── button_component.rb
├── button_component.html.erb
├── card_component.rb
└── card_component/
    ├── card_component.html.erb
    └── header_component.rb
```

---

### Basic Component Structure

```ruby
# app/components/button_component.rb
class ButtonComponent < ViewComponent::Base
  def initialize(type: :primary, size: :medium, **html_options)
    @type = type
    @size = size
    @html_options = html_options
  end

  private
    attr_reader :type, :size, :html_options

    def button_classes
      ["btn", "btn-#{type}", "btn-#{size}", html_options[:class]].compact.join(" ")
    end
end
```

```erb
<%# app/components/button_component.html.erb %>
<button class="<%= button_classes %>" <%= tag.attributes(html_options.except(:class)) %>>
  <%= content %>
</button>
```

```erb
<%# Usage %>
<%= render ButtonComponent.new(type: :primary, size: :large) do %>
  Submit Form
<% end %>
```

---

### Slots

```ruby
# Component with Slots
class CardComponent < ViewComponent::Base
  renders_one :header, HeaderComponent
  renders_many :actions, ActionComponent

  def initialize(variant: :default)
    @variant = variant
  end
end
```

```erb
<%# card_component.html.erb %>
<div class="card card-<%= variant %>">
  <% if header? %>
    <div class="card-header"><%= header %></div>
  <% end %>

  <div class="card-body"><%= content %></div>

  <% if actions? %>
    <div class="card-actions">
      <% actions.each do |action| %><%= action %><% end %>
    </div>
  <% end %>
</div>
```

```erb
<%# Usage %>
<%= render CardComponent.new(variant: :primary) do |card| %>
  <% card.with_header(title: "User Profile") %>
  <p>Card body content.</p>
  <% card.with_action(label: "Edit", url: edit_user_path(@user)) %>
<% end %>
```

---

### Slot Types

```ruby
# renders_one variants
renders_one :title                        # Simple passthrough
renders_one :icon, IconComponent          # Component slot
renders_one :footer, ->(text:, classes: nil) do  # Lambda slot
  content_tag :div, text, class: classes
end

# renders_many
renders_many :items, NavItemComponent
renders_many :links, ->(title:, url:, **options) do
  link_to title, url, options
end

# Polymorphic slots
renders_one :body, types: {
  text: ->(content:) { content_tag :p, content },
  form: FormComponent,
  custom: ->(&block) { capture(&block) }
}
```

---

### Testing ViewComponents

```ruby
class ButtonComponentTest < ViewComponent::TestCase
  def test_renders_button
    render_inline ButtonComponent.new(type: :primary) do
      "Click me"
    end

    assert_selector "button.btn.btn-primary", text: "Click me"
  end
end

class CardComponentTest < ViewComponent::TestCase
  def test_renders_with_header
    render_inline CardComponent.new do |card|
      card.with_header(title: "Test Card")
      "Card content"
    end

    assert_selector ".card-header", text: "Test Card"
    assert_selector ".card-body", text: "Card content"
  end
end
```

---

### Previews

```ruby
# test/components/previews/button_component_preview.rb
class ButtonComponentPreview < ViewComponent::Preview
  def default
    render ButtonComponent.new(type: :primary) do
      "Default Button"
    end
  end

  def secondary
    render ButtonComponent.new(type: :secondary) do
      "Secondary Button"
    end
  end
end

# Access at: /rails/view_components
```

---

## ViewComponent — Advanced

### Best Practices

```ruby
# DO: Composition over inheritance
class PanelComponent < ViewComponent::Base
  renders_one :card, CardComponent
end

# DO: Pass global state explicitly
render UserCardComponent.new(user: current_user, signed_in: user_signed_in?)

# DO: Use instance methods instead of inline Ruby in templates
class ButtonComponent < ViewComponent::Base
  private
    def button_classes
      ["btn", "btn-#{type}", size_class].compact.join(" ")
    end
end

# DO: Most instance methods private
class ButtonComponent < ViewComponent::Base
  def initialize(type:)
    @type = type
  end

  private
    attr_reader :type

    def button_classes
      "btn btn-#{type}"
    end
end

# DON'T: Inline Ruby in templates
# BAD: <button class="btn <%= type == :primary ? 'btn-primary' : 'btn-secondary' %>">
# GOOD: <button class="<%= button_classes %>">

# DON'T: Pass HTML-safe markup as arguments
# BAD: render CardComponent.new(title: "<h3>#{user_input}</h3>".html_safe)
# GOOD: Use slots instead
```

---

### Lifecycle Methods

```ruby
class Component < ViewComponent::Base
  def initialize(*args)
    super
  end

  def before_render
    # Called before rendering - slots are available here
    @computed_value = expensive_calculation if header?
  end

  def render?
    # Return false to skip rendering entirely
    user.present? && user.active?
  end

  def call
    # Custom render logic
    content_tag :div, class: "wrapper" do
      super
    end
  end
end
```

---

### Advanced Patterns

```ruby
# Collections
class UserComponent < ViewComponent::Base
  def initialize(user:)
    @user = user
  end

  with_collection_parameter :user
end

# Usage: <%= render UserComponent.with_collection(@users) %>

# Helpers
class Component < ViewComponent::Base
  def formatted_date
    helpers.time_ago_in_words(created_at)
  end

  delegate :link_to, :content_tag, to: :helpers
end
```
