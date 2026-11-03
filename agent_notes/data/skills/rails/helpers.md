# View Helpers

## Contents

- [Philosophy](#philosophy)
- [Application Helpers](#application-helpers)
- [Domain-Specific Helpers](#domain-specific-helpers)
- [Form Helpers](#form-helpers)
- [Time Helpers](#time-helpers)
- [Best Practices](#best-practices)
- [Sources](#sources)

## Philosophy

Helpers are view-focused methods that wrap markup or view logic. Fizzy has 28 helper files in `app/helpers/`, plus a `my/` folder, each for one domain: cards, comments, forms, time, notifications and so on.

Why: one file per domain makes a helper easy to find from the view that calls it (Fizzy: `app/helpers`).

## Application Helpers

Global helpers used across views live in `ApplicationHelper`:

```ruby
# app/helpers/application_helper.rb
module ApplicationHelper
  def page_title_tag
    account_name = if Current.account && Current.session&.identity&.users&.many?
      Current.account&.name
    end
    tag.title [ @page_title, account_name, "Fizzy" ].compact.join(" | ")
  end

  def icon_tag(name, **options)
    tag.span class: class_names("icon icon--#{name}", options.delete(:class)), "aria-hidden": true, **options
  end
# ...
end
```

`page_title_tag` takes no argument. It reads `@page_title`, adds the account name when the signed-in identity belongs to more than one account, and appends "Fizzy". `icon_tag` returns a `span` with icon classes, and `back_link_to` builds the "Back to ..." link with its hotkey data attributes.

Why: markup that every page repeats is written once, with the tag helpers (`tag.title`, `tag.span`) doing the escaping (Fizzy: `app/helpers/application_helper.rb`).

## Domain-Specific Helpers

Helpers for one resource live in a file named for it. `CardsHelper` builds the card's `<article>`:

```ruby
# app/helpers/cards_helper.rb
def card_article_tag(card, id: dom_id(card, :article), data: {}, **options, &block)
  classes = [
    options.delete(:class),
    ("golden-effect" if card.golden?),
    ("card--postponed" if card.postponed?),
    ("card--active" if card.active?)
  ].compact.join(" ")
# ...
end
```

The class list comes from model predicates (`golden?`, `postponed?`, `active?`), and the rest of the method sets the `id`, the CSS custom property and the view-transition name. The same file holds `card_title_tag`, `card_social_tags` and `button_to_remove_card_image`:

```ruby
# app/helpers/cards_helper.rb
def button_to_remove_card_image(card)
  button_to(card_image_path(card), method: :delete, class: "btn", data: { controller: "tooltip", action: "dialog#close" }) do
    icon_tag("trash") + tag.span("Remove background image", class: "for-screen-reader")
  end
end
```

Why: the helper turns model state into markup, and the model keeps the logic (Fizzy: `app/helpers/cards_helper.rb`).

## Form Helpers

Form helpers wrap `form_with` and add a Stimulus controller through the `data` attributes:

```ruby
# app/helpers/forms_helper.rb
module FormsHelper
  def auto_submit_form_with(**attributes, &)
    data = attributes.delete(:data) || {}
    data[:controller] = "auto-submit #{data[:controller]}".strip

    if block_given?
      form_with **attributes, data: data, &
    else
      form_with(**attributes, data: data) { }
    end
  end
# ...
end
```

`bridged_form_with` does the same for the `bridge--form` controller and also adds two Turbo submit actions:

```ruby
# app/helpers/forms_helper.rb
def bridged_form_with(**attributes, &)
  data = attributes.delete(:data) || {}
  controllers = [ data[:controller], "bridge--form" ].compact.join(" ").strip
  actions = [
    data[:action],
    "turbo:submit-start->bridge--form#submitStart",
    "turbo:submit-end->bridge--form#submitEnd"
  ].compact.join(" ").strip

  data[:controller] = controllers
  data[:action] = actions
# ...
end
```

Both accept a block, or run `form_with` with an empty block when none is given.

Why: callers get the controller wiring by switching the helper name, not by repeating `data:` hashes (Fizzy: `app/helpers/forms_helper.rb`).

## Time Helpers

```ruby
# app/helpers/time_helper.rb
module TimeHelper
  def local_datetime_tag(datetime, style: :time, **attributes)
    # Render empty space to ensure it takes height until the local time is loaded via JS
    tag.time "&nbsp;".html_safe, **attributes, datetime: datetime.to_i, data: { local_time_target: style, action: "turbo:morph-element->local-time#refreshTarget" }
  end
end
```

`local_datetime_tag` renders a `<time>` element whose `datetime` is the timestamp in epoch seconds. The `local-time` Stimulus controller, attached to `<body>` in the layouts, formats it in the viewer's own timezone, and `data-local-time-target` selects the style. The `&nbsp;` placeholder reserves the line's height until the JavaScript has run, and the `turbo:morph-element` action refreshes the text after a morph.

Why: the server cannot know the viewer's timezone, so the browser formats the time (Fizzy: `app/helpers/time_helper.rb`).

## Best Practices

### Helpers may read Current

Only two helpers read `Current`: `ApplicationHelper#page_title_tag` (above) and this one:

```ruby
# app/helpers/comments_helper.rb
module CommentsHelper
  def new_comment_placeholder(card)
    if card.creator == Current.user && card.comments.empty?
      "Next, add some notes, context, pictures, or video about this…"
    else
      "Type your comment…"
    end
  end
```

Why: the signed-in user is request context, and a view helper is where request context turns into copy (Fizzy: `app/helpers/comments_helper.rb`).

### Keep helpers thin

A helper composes markup and calls the model's predicates, as `card_article_tag` calls `card.golden?`. Business rules belong in the model or a concern.

Why: models own the domain logic and helpers own presentation (https://guides.rubyonrails.org/action_view_helpers.html).

### Name helpers after what they return

Fizzy names a helper after the Rails helper it wraps: `*_tag` for an element (`page_title_tag`, `icon_tag`, `card_article_tag`, `local_datetime_tag`), `*_form_with` for form wrappers (`auto_submit_form_with`, `bridged_form_with`), `button_to_*` for buttons (`button_to_remove_card_image`) and `back_link_to` for links.

Why: the name tells the reader which Rails helper to compare it with (Fizzy: `app/helpers/forms_helper.rb`, `app/helpers/cards_helper.rb`).

## Sources

- Fizzy: `app/helpers/application_helper.rb`, `app/helpers/cards_helper.rb`, `app/helpers/forms_helper.rb`
- Fizzy: `app/helpers/time_helper.rb`, `app/helpers/comments_helper.rb`
- https://guides.rubyonrails.org/action_view_helpers.html
