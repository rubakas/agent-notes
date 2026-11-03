# ViewComponent

> Added by the owner, not from Fizzy/37signals. Fizzy's default is partials plus helpers (see views.md).

## Contents

- [Philosophy](#philosophy)
- [File Structure](#file-structure)
- [Basic Component Structure](#basic-component-structure)
- [Slots](#slots)
- [Slot Types](#slot-types)
- [Testing ViewComponents](#testing-viewcomponents)
- [Previews](#previews)
- [Best Practices](#best-practices)
- [Lifecycle Methods](#lifecycle-methods)
- [Advanced Patterns](#advanced-patterns)
- [Sources](#sources)

## Philosophy

ViewComponent encapsulates view logic, markup and styling in reusable, testable Ruby objects. Use it when:

- A partial is complex enough to benefit from instance methods and a clear interface.
- The component is rendered in several contexts and needs consistent behavior.
- You want to unit-test the component's logic in isolation.

Fizzy does not use ViewComponent; this guidance is for projects that do. Follow the project's RuboCop configuration for formatting.

Why: components are plain Ruby objects, so they can be tested without a request (ViewComponent docs: https://viewcomponent.org).

## File Structure

```
app/components/
├── button_component.rb
├── button_component.html.erb
├── card_component.rb
├── card_component.html.erb
└── card_component/
    ├── header_component.rb
    └── header_component.html.erb
test/components/
├── button_component_test.rb
└── previews/
    └── button_component_preview.rb
```

Each component is a `.rb` file paired with a template of the same name. Nested components go in a directory named after the parent. Previews live in `test/components/previews` by default.

Why: pairing the class and the template by name is how ViewComponent finds the template (ViewComponent docs: https://viewcomponent.org).

## Basic Component Structure

A component (`button_component.rb`) takes its data in `initialize` and exposes helper methods to its template (`button_component.html.erb`).

```ruby
# Illustrative (not from Fizzy)
class ButtonComponent < ViewComponent::Base
  def initialize(label:, variant: "primary", disabled: false, **html_attrs)
    @label = label
    @variant = variant
    @disabled = disabled
    @html_attrs = html_attrs
  end

  private
    def css_classes
      ["button", "button-#{@variant}", ("button-disabled" if @disabled)].compact.join(" ")
    end
end
```

```erb
<%# Illustrative (not from Fizzy) %>
<button class="<%= css_classes %>" <%= tag.attributes(@html_attrs) %>>
  <%= @label %>
</button>
```

Why: constructor arguments make the component's inputs explicit (ViewComponent docs: https://viewcomponent.org).

## Slots

Slots let a component accept blocks of content or sub-components. Declare them with `renders_one` and `renders_many`, and fill them with the generated `with_*` methods. The component's template renders `header` and `actions`.

```ruby
# Illustrative (not from Fizzy)
class CardComponent < ViewComponent::Base
  renders_one :header
  renders_many :actions
end
```

```erb
<%# Illustrative (not from Fizzy) %>
<%= render(CardComponent.new) do |card| %>
  <% card.with_header do %>
    <h2>Card Title</h2>
  <% end %>
  <% card.with_action do %>Edit<% end %>
  <% card.with_action do %>Delete<% end %>
<% end %>
```

Why: slots keep the component's layout in its template while callers supply the content (ViewComponent docs: https://viewcomponent.org/guide/slots.html).

## Slot Types

- `renders_one :slot_name` for a single optional slot.
- `renders_many :slot_name` for zero or more slots.
- `renders_one :slot_name, OtherComponent` to render a child component in the slot.

Why: the slot type decides whether the generated accessor returns one slot or a list (ViewComponent docs: https://viewcomponent.org/guide/slots.html).

## Testing ViewComponents

Test components with `ViewComponent::TestCase` and `render_inline`, then assert on the rendered HTML.

```ruby
# Illustrative (not from Fizzy)
class ButtonComponentTest < ViewComponent::TestCase
  test "renders button with label" do
    render_inline(ButtonComponent.new(label: "Click me"))
    assert_text "Click me"
    assert_selector "button"
  end

  test "applies variant class" do
    render_inline(ButtonComponent.new(label: "Delete", variant: "danger"))
    assert_selector "button.button-danger"
  end
end
```

Why: `render_inline` renders without a controller or request, so tests stay fast (ViewComponent docs: https://viewcomponent.org/guide/testing.html).

## Previews

Previews render components in isolation for manual review during development.

```ruby
# Illustrative (not from Fizzy)
class ButtonComponentPreview < ViewComponent::Preview
  def default
    render(ButtonComponent.new(label: "Click me"))
  end

  def danger
    render(ButtonComponent.new(label: "Delete", variant: "danger"))
  end
end
```

Each public method is one preview. Browse them at `/rails/view_components` in development.

Why: previews give every component state a stable URL for review (ViewComponent docs: https://viewcomponent.org/guide/previews.html).

## Best Practices

1. **Single responsibility.** One component per concept.
2. **Testable interface.** Take constructor parameters, not hidden instance variables.
3. **Keep domain logic out.** Put it in a model or helper and pass the result in.
4. **Shallow trees.** Avoid deep chains of nested components.

Why: small components with explicit inputs are the easiest to test and reuse (ViewComponent docs: https://viewcomponent.org).

## Lifecycle Methods

- `before_render` is a hook that runs before the template renders.
- `initialize` is the constructor, called once per render.
- `render?` decides whether to render at all (returns a boolean).

Why: these are the extension points ViewComponent provides around rendering (ViewComponent docs: https://viewcomponent.org).

## Advanced Patterns

**Conditional rendering.** Return `false` from `render?` to skip all output.

```ruby
# Illustrative (not from Fizzy)
def render?
  @items.any?
end
```

**Polymorphic components.** Accept a data object and choose the markup from its type.

**Collections.** Render the same component for each item.

```erb
<%# Illustrative (not from Fizzy) %>
<%= render CardComponent.with_collection(@cards) %>
```

Why: `render?` and `with_collection` are built-in, so they avoid conditionals and loops in the calling view (ViewComponent docs: https://viewcomponent.org/guide/collections.html).

## Sources

- [ViewComponent documentation](https://viewcomponent.org/)
