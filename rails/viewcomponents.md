# ViewComponent

A framework for building reusable, testable & encapsulated view components in Ruby on Rails.

> **Source**: This guide is based on [ViewComponent Official Documentation](https://viewcomponent.org/) and the [ViewComponent GitHub Repository](https://github.com/ViewComponent/view_component).

---

## Philosophy

**"ViewComponent is to UI what ActiveRecord is to SQL"** — brings conceptual compression to UI development.

ViewComponent was created to manage complexity in GitHub.com's view layer, providing abstraction for common UI patterns to improve quality and consistency. It exposes existing complexity, which aids refactoring and comprehension.

**Key Benefits:**
- **Over 100x faster** than similar controller tests (GitHub codebase)
- **Reusable** - Build once, use anywhere
- **Testable** - Unit test with `render_inline`
- **Encapsulated** - Self-contained logic and templates

**Source**: [ViewComponent Overview](https://viewcomponent.org/)

---

## File Structure

```
app/components/
├── application_component.rb           # Base component
├── button_component.rb                # Component class
├── button_component.html.erb          # Component template
├── card_component.rb
├── card_component/
│   ├── card_component.html.erb       # Sidecar template
│   ├── header_component.rb           # Nested component
│   └── header_component.html.erb
└── alert/
    ├── component.rb                   # Alternative structure
    └── component.html.erb
```

---

## Basic Component Structure

### Simple Component

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
      [
        "btn",
        "btn-#{type}",
        "btn-#{size}",
        html_options[:class]
      ].compact.join(" ")
    end
end
```

```erb
<%# app/components/button_component.html.erb %>
<button class="<%= button_classes %>" <%= tag.attributes(html_options.except(:class)) %>>
  <%= content %>
</button>
```

**Usage:**
```erb
<%= render ButtonComponent.new(type: :primary, size: :large, data: { action: "click->form#submit" }) do %>
  Submit Form
<% end %>
```

### Component with Slots

```ruby
# app/components/card_component.rb
class CardComponent < ViewComponent::Base
  # Single slot (rendered at most once)
  renders_one :header, HeaderComponent

  # Multiple slots (rendered multiple times)
  renders_many :actions, ActionComponent

  def initialize(variant: :default)
    @variant = variant
  end

  private
    attr_reader :variant
end
```

```erb
<%# app/components/card_component.html.erb %>
<div class="card card-<%= variant %>">
  <% if header? %>
    <div class="card-header">
      <%= header %>
    </div>
  <% end %>

  <div class="card-body">
    <%= content %>
  </div>

  <% if actions? %>
    <div class="card-actions">
      <% actions.each do |action| %>
        <%= action %>
      <% end %>
    </div>
  <% end %>
</div>
```

**Usage:**
```erb
<%= render CardComponent.new(variant: :primary) do |card| %>
  <% card.with_header(title: "User Profile") %>

  <p>This is the card body content.</p>

  <% card.with_action(label: "Edit", url: edit_user_path(@user)) %>
  <% card.with_action(label: "Delete", url: user_path(@user), method: :delete) %>
<% end %>
```

**Source**: [ViewComponent Slots Guide](https://viewcomponent.org/guide/slots.html)

---

## Slot Patterns

### renders_one (Single Slot)

```ruby
class AlertComponent < ViewComponent::Base
  # Simple passthrough slot
  renders_one :title

  # Component slot
  renders_one :icon, IconComponent

  # Lambda slot
  renders_one :footer, ->(text:, classes: nil) do
    content_tag :div, text, class: classes
  end
end
```

```erb
<div class="alert">
  <% if icon? %>
    <%= icon %>
  <% end %>

  <% if title? %>
    <h4><%= title %></h4>
  <% end %>

  <%= content %>

  <% if footer? %>
    <%= footer %>
  <% end %>
</div>
```

**Usage:**
```erb
<%= render AlertComponent.new do |alert| %>
  <% alert.with_icon(name: "warning") %>
  <% alert.with_title { "Warning" } %>

  This is an alert message.

  <% alert.with_footer(text: "Dismiss", classes: "text-sm") %>
<% end %>
```

### renders_many (Multiple Slots)

```ruby
class NavigationComponent < ViewComponent::Base
  # Multiple items
  renders_many :items, NavItemComponent

  # Or with lambda
  renders_many :links, ->(title:, url:, **options) do
    link_to title, url, options
  end
end
```

```erb
<nav>
  <ul>
    <% items.each do |item| %>
      <li><%= item %></li>
    <% end %>
  </ul>
</nav>
```

**Usage:**
```erb
<%= render NavigationComponent.new do |nav| %>
  <% nav.with_item(title: "Home", url: root_path, current: true) %>
  <% nav.with_item(title: "About", url: about_path) %>
  <% nav.with_item(title: "Contact", url: contact_path) %>
<% end %>
```

### Polymorphic Slots

```ruby
class ModalComponent < ViewComponent::Base
  renders_one :body, types: {
    text: ->(content:) { content_tag :p, content },
    form: FormComponent,
    custom: ->(&block) { capture(&block) }
  }
end
```

**Usage:**
```erb
<%# Text variant %>
<%= render ModalComponent.new do |modal| %>
  <% modal.with_body_text(content: "Simple text content") %>
<% end %>

<%# Form variant %>
<%= render ModalComponent.new do |modal| %>
  <% modal.with_body_form(url: users_path) %>
<% end %>

<%# Custom variant %>
<%= render ModalComponent.new do |modal| %>
  <% modal.with_body_custom do %>
    <div>Custom HTML content</div>
  <% end %>
<% end %>
```

**Source**: [ViewComponent Slots - Polymorphic Slots](https://viewcomponent.org/guide/slots.html)

---

## Slot Utilities

### Predicate Methods

```ruby
class CardComponent < ViewComponent::Base
  renders_one :header
  renders_many :actions
end
```

```erb
<% if header? %>
  <%= header %>
<% end %>

<% if actions? %>
  <% actions.each do |action| %>
    <%= action %>
  <% end %>
<% end %>
```

### Default Slots

```ruby
class PanelComponent < ViewComponent::Base
  renders_one :title

  private
    def default_title
      content_tag :h3, "Default Title"
    end
end
```

```erb
<%# Will use default if not provided %>
<%= title %>
```

### Collection Rendering

```ruby
class TableComponent < ViewComponent::Base
  renders_many :rows
end
```

**Usage:**
```erb
<%= render TableComponent.new do |table| %>
  <%# Pass array to plural setter %>
  <% table.with_rows(@users.map { |user| { name: user.name, email: user.email } }) %>
<% end %>
```

**Source**: [ViewComponent Slots Guide](https://viewcomponent.org/guide/slots.html)

---

## Testing

### Basic Component Test

```ruby
# test/components/button_component_test.rb
require "test_helper"

class ButtonComponentTest < ViewComponent::TestCase
  def test_renders_button
    render_inline ButtonComponent.new(type: :primary) do
      "Click me"
    end

    assert_selector "button.btn.btn-primary", text: "Click me"
  end

  def test_renders_with_custom_classes
    render_inline ButtonComponent.new(type: :secondary, class: "custom-class")

    assert_selector "button.btn.btn-secondary.custom-class"
  end

  def test_renders_with_data_attributes
    render_inline ButtonComponent.new(data: { action: "click->test#run" })

    assert_selector "button[data-action='click->test#run']"
  end
end
```

### Testing with Slots

```ruby
class CardComponentTest < ViewComponent::TestCase
  def test_renders_with_header
    render_inline CardComponent.new do |card|
      card.with_header(title: "Test Card")
      "Card content"
    end

    assert_selector ".card-header", text: "Test Card"
    assert_selector ".card-body", text: "Card content"
  end

  def test_renders_without_header
    render_inline CardComponent.new do
      "Card content"
    end

    assert_no_selector ".card-header"
    assert_selector ".card-body", text: "Card content"
  end

  def test_renders_multiple_actions
    render_inline CardComponent.new do |card|
      card.with_action(label: "Edit")
      card.with_action(label: "Delete")
    end

    assert_selector ".card-actions", count: 1
    assert_text "Edit"
    assert_text "Delete"
  end
end
```

### RSpec Setup

```ruby
# spec/rails_helper.rb
RSpec.configure do |config|
  config.include ViewComponent::TestHelpers, type: :component
  config.include Capybara::RSpecMatchers, type: :component
end
```

```ruby
# spec/components/button_component_spec.rb
require "rails_helper"

RSpec.describe ButtonComponent, type: :component do
  it "renders a primary button" do
    render_inline described_class.new(type: :primary) do
      "Submit"
    end

    expect(page).to have_css "button.btn.btn-primary", text: "Submit"
  end

  it "applies custom data attributes" do
    render_inline described_class.new(data: { controller: "form" })

    expect(page).to have_css "button[data-controller='form']"
  end
end
```

**Source**: [ViewComponent Testing Guide](https://viewcomponent.org/guide/testing.html)

---

## Previews

Previews provide a quick way to visualize components in isolation during development.

### Creating Previews

```ruby
# test/components/previews/button_component_preview.rb
class ButtonComponentPreview < ViewComponent::Preview
  # Default preview
  def default
    render ButtonComponent.new(type: :primary) do
      "Default Button"
    end
  end

  # Named preview
  def primary
    render ButtonComponent.new(type: :primary) do
      "Primary Button"
    end
  end

  def secondary
    render ButtonComponent.new(type: :secondary) do
      "Secondary Button"
    end
  end

  def large
    render ButtonComponent.new(type: :primary, size: :large) do
      "Large Button"
    end
  end

  # With description
  # @label Danger Button
  # @display bg_color "#fee"
  def danger
    render ButtonComponent.new(type: :danger) do
      "Danger Button"
    end
  end
end
```

### Preview with Slots

```ruby
class CardComponentPreview < ViewComponent::Preview
  def with_all_slots
    render CardComponent.new(variant: :primary) do |card|
      card.with_header(title: "Card Title")
      card.with_action(label: "Edit", url: "#")
      card.with_action(label: "Delete", url: "#")

      "This is the card body content with all slots populated."
    end
  end

  def minimal
    render CardComponent.new do
      "Minimal card with no slots."
    end
  end
end
```

### Configuration

```ruby
# config/application.rb
config.view_component.preview_paths << "#{Rails.root}/app/components/previews"
config.view_component.show_previews = Rails.env.development?
```

**Access previews:** Visit `/rails/view_components` in development.

**Source**: [ViewComponent Previews Guide](https://viewcomponent.org/guide/previews.html)

---

## Best Practices

### ✅ DO

1. **Use composition instead of inheritance**
```ruby
# ✅ GOOD - Composition
class PanelComponent < ViewComponent::Base
  renders_one :card, CardComponent
end

# ❌ BAD - Inheritance
class PanelComponent < CardComponent
end
```

2. **Extract components after proving pattern across multiple uses**
```ruby
# Good frameworks are extracted, not invented
# Develop single-use components first, extract when pattern repeats 3+ times
```

3. **Pass global state explicitly as arguments**
```ruby
# ✅ GOOD
render UserCardComponent.new(user: current_user, signed_in: user_signed_in?)

# ❌ BAD - Accessing global state
class UserCardComponent < ViewComponent::Base
  def call
    if user_signed_in?  # Don't access global state
      ...
    end
  end
end
```

4. **Use instance methods instead of inline Ruby in templates**
```ruby
# ✅ GOOD
class ButtonComponent < ViewComponent::Base
  private
    def button_classes
      ["btn", "btn-#{type}", size_class].compact.join(" ")
    end
end
```

```erb
<button class="<%= button_classes %>">
```

5. **Prefer slots for providing markup to components**
```ruby
# ✅ GOOD - Using slots
card.with_header do
  content_tag :h3, "Title"
end

# ❌ BAD - Passing HTML as argument
card.header = "<h3>Title</h3>".html_safe
```

6. **Test against rendered content**
```ruby
# ✅ GOOD
def test_renders_button
  render_inline ButtonComponent.new(type: :primary)
  assert_selector "button.btn-primary"
end

# ❌ BAD - Testing only instance methods
def test_button_classes
  component = ButtonComponent.new(type: :primary)
  assert_equal "btn btn-primary", component.send(:button_classes)
end
```

7. **Make most instance methods private**
```ruby
class ButtonComponent < ViewComponent::Base
  def initialize(type:)
    @type = type
  end

  # Public interface is minimal

  private
    attr_reader :type

    # Helper methods are private but accessible in templates
    def button_classes
      "btn btn-#{type}"
    end
end
```

8. **Replace partials and HTML-generating helpers**
```ruby
# ✅ GOOD - ViewComponent
render ButtonComponent.new(type: :primary, url: user_path(@user))

# ❌ OLD - Partial
render "shared/button", type: :primary, url: user_path(@user)

# ❌ OLD - Helper
button_tag type: :primary, url: user_path(@user)
```

### ❌ DON'T

1. **Don't use component inheritance with separate templates**
```ruby
# ❌ BAD - Confusing inheritance
class PanelComponent < CardComponent
  # Has its own template - which one renders?
end
```

2. **Don't write inline Ruby in templates**
```erb
<%# ❌ BAD %>
<button class="btn <%= type == :primary ? 'btn-primary' : 'btn-secondary' %>">

<%# ✅ GOOD - Use instance method %>
<button class="<%= button_classes %>">
```

3. **Don't pass HTML-safe markup as arguments**
```ruby
# ❌ BAD - Security risk
render CardComponent.new(title: "<h3>#{user_input}</h3>".html_safe)

# ✅ GOOD - Use slots
render CardComponent.new do |card|
  card.with_title { content_tag :h3, user_input }
end
```

4. **Don't rely on global state**
```ruby
# ❌ BAD
class UserComponent < ViewComponent::Base
  def call
    current_user  # Accessing global state
    params[:id]   # Accessing request params
  end
end

# ✅ GOOD - Explicit dependencies
class UserComponent < ViewComponent::Base
  def initialize(user:, id:)
    @user = user
    @id = id
  end
end
```

**Source**: [ViewComponent Best Practices](https://viewcomponent.org/best_practices.html)

---

## Component Organization

### Two Component Types

1. **General-purpose components** - Common UI patterns
   - Examples: buttons, forms, modals, alerts
   - Like Primer ViewComponents
   - Highly reusable across applications

2. **Application-specific components** - Domain-driven
   - Examples: UserCard, ProductListing, InvoiceHeader
   - Convert domain objects into general-purpose components
   - Encapsulate business logic presentation

### Naming Conventions

```ruby
# Use -Component suffix (Rails conventions)
ButtonComponent
UserCardComponent
NavigationComponent
```

### Extraction Strategy

```
1. Develop single-use components first
2. Extract to reusable component once pattern appears 3+ times
3. Consolidate similar patterns (DRY)
4. Minimize single-use view code
```

**Source**: [ViewComponent Best Practices](https://viewcomponent.org/best_practices.html)

---

## Lifecycle Methods

```ruby
class Component < ViewComponent::Base
  def initialize(*args)
    # Called when component is instantiated
    super
  end

  def before_render
    # Called before rendering
    # Access to slots here
    @computed_value = expensive_calculation if header?
  end

  def call
    # Optional: custom render logic
    # By default renders the template
    content_tag :div, class: "wrapper" do
      super
    end
  end
end
```

**Source**: [ViewComponent Lifecycle Guide](https://viewcomponent.org/guide/lifecycle.html)

---

## Advanced Patterns

### Collections

```ruby
class UserComponent < ViewComponent::Base
  def initialize(user:)
    @user = user
  end

  # Enable collection rendering
  with_collection_parameter :user
end
```

**Usage:**
```erb
<%# Renders UserComponent for each user %>
<%= render UserComponent.with_collection(@users) %>

<%# With counter %>
<%= render UserComponent.with_collection(@users, :user_counter) %>
```

### Conditional Rendering

```ruby
class Component < ViewComponent::Base
  def render?
    # Return false to skip rendering entirely
    user.present? && user.active?
  end
end
```

### Helpers

```ruby
class Component < ViewComponent::Base
  # Access Rails helpers
  def formatted_date
    helpers.time_ago_in_words(created_at)
  end

  # Or delegate
  delegate :link_to, :content_tag, to: :helpers
end
```

---

## Common Patterns

### Form Component

```ruby
class FormComponent < ViewComponent::Base
  renders_one :submit_button, ButtonComponent

  def initialize(url:, method: :post, **options)
    @url = url
    @method = method
    @options = options
  end

  private
    attr_reader :url, :method, :options
end
```

```erb
<%= form_with url: url, method: method, **options do |f| %>
  <%= content %>

  <% if submit_button? %>
    <%= submit_button %>
  <% else %>
    <%= f.submit "Submit", class: "btn btn-primary" %>
  <% end %>
<% end %>
```

### Modal Component

```ruby
class ModalComponent < ViewComponent::Base
  renders_one :title
  renders_one :body
  renders_many :actions, ActionComponent

  def initialize(id:, size: :medium)
    @id = id
    @size = size
  end

  private
    attr_reader :id, :size
end
```

### Table Component

```ruby
class TableComponent < ViewComponent::Base
  renders_many :columns, ColumnComponent
  renders_many :rows, RowComponent

  def initialize(data:, **options)
    @data = data
    @options = options
  end
end
```

---

## Summary

- **ViewComponent** = Reusable, testable, encapsulated view components
- **100x faster** tests than controller tests
- **Slots** = `renders_one` (single) and `renders_many` (multiple)
- **Testing** = Use `render_inline` with Capybara matchers
- **Previews** = Visualize components at `/rails/view_components`
- **Best Practices** = Composition over inheritance, explicit dependencies, slots over HTML args
- **Organization** = General-purpose vs application-specific components

---

## References and Sources

This guide is based on official ViewComponent documentation:

- [ViewComponent Official Documentation](https://viewcomponent.org/)
- [ViewComponent GitHub Repository](https://github.com/ViewComponent/view_component)
- [ViewComponent Guide](https://viewcomponent.org/guide/)
- [ViewComponent Slots](https://viewcomponent.org/guide/slots.html)
- [ViewComponent Testing](https://viewcomponent.org/guide/testing.html)
- [ViewComponent Previews](https://viewcomponent.org/guide/previews.html)
- [ViewComponent Best Practices](https://viewcomponent.org/best_practices.html)

Last updated: December 2025
