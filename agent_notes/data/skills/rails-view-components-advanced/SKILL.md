---
name: rails-view-components-advanced
description: "ViewComponent advanced: best practices, organization, lifecycle, and common patterns"
group: rails
---

# ViewComponent (Advanced)

## Best Practices

### DO

1. **Use composition instead of inheritance**
```ruby
# GOOD - Composition
class PanelComponent < ViewComponent::Base
  renders_one :card, CardComponent
end

# BAD - Inheritance
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
# GOOD
render UserCardComponent.new(user: current_user, signed_in: user_signed_in?)

# BAD - Accessing global state
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
# GOOD
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
# GOOD - Using slots
card.with_header do
  content_tag :h3, "Title"
end

# BAD - Passing HTML as argument
card.header = "<h3>Title</h3>".html_safe
```

6. **Test against rendered content**
```ruby
# GOOD
def test_renders_button
  render_inline ButtonComponent.new(type: :primary)
  assert_selector "button.btn-primary"
end

# BAD - Testing only instance methods
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
# GOOD - ViewComponent
render ButtonComponent.new(type: :primary, url: user_path(@user))

# OLD - Partial
render "shared/button", type: :primary, url: user_path(@user)

# OLD - Helper
button_tag type: :primary, url: user_path(@user)
```

### DON'T

1. **Don't use component inheritance with separate templates**
```ruby
# BAD - Confusing inheritance
class PanelComponent < CardComponent
  # Has its own template - which one renders?
end
```

2. **Don't write inline Ruby in templates**
```erb
<%# BAD %>
<button class="btn <%= type == :primary ? 'btn-primary' : 'btn-secondary' %>">

<%# GOOD - Use instance method %>
<button class="<%= button_classes %>">
```

3. **Don't pass HTML-safe markup as arguments**
```ruby
# BAD - Security risk
render CardComponent.new(title: "<h3>#{user_input}</h3>".html_safe)

# GOOD - Use slots
render CardComponent.new do |card|
  card.with_title { content_tag :h3, user_input }
end
```

4. **Don't rely on global state**
```ruby
# BAD
class UserComponent < ViewComponent::Base
  def call
    current_user  # Accessing global state
    params[:id]   # Accessing request params
  end
end

# GOOD - Explicit dependencies
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
