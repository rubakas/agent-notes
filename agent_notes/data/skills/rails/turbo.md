# Turbo: Frames, Streams & Morphing

## Contents

- [Frames](#frames)
- [Streams](#streams)
- [Morphing & Page Refresh](#morphing--page-refresh)
- [Prefetching](#prefetching)
- [View Transitions](#view-transitions)
- [Sources](#sources)

## Frames

Turbo Frames split a page into independent regions. Give a frame a `src` and `loading: :lazy` to fetch its content when it scrolls into view, and `refresh: :morph` so a page refresh morphs it instead of replacing it. Pass a record plus a symbol (`turbo_frame_tag card, :tagging`) to build a unique id with `dom_id`.

```erb
<%# app/views/cards/display/perma/_tags.html.erb %>
      <%= turbo_frame_tag card, :tagging, src: new_card_tagging_path(card), loading: :lazy, refresh: :morph %>
```

Links inside a frame navigate the frame unless they target `_top`:

```erb
<%# app/views/cards/comments/_comment.html.erb %>
              <%= link_to comment.creator.name, comment.creator, class: "txt-ink btn btn--plain fill-transparent", data: { turbo_frame: "_top" } %>
```

Why: lazy frames keep the initial page small, and `_top` is how a link inside a frame navigates the whole page (Turbo docs: https://turbo.hotwired.dev/handbook/frames).

## Streams

Turbo Streams update the page from a form response or a broadcast. A stream template sits next to the action as `.turbo_stream.erb`. Each `turbo_stream.<action>` names a DOM target (a string, a record, or an array that goes through `dom_id`).

```erb
<%# app/views/cards/comments/create.turbo_stream.erb %>
<%= turbo_stream.before [ @card, :new_comment ], partial: "cards/comments/comment", locals: { comment: @comment } %>

<%= turbo_stream.update [ @card, :new_comment ], partial: "cards/comments/new", locals: { card: @card } %>
```

`method: :morph` on `replace` or `update` morphs the target instead of swapping its HTML:

```erb
<%# app/views/cards/update.turbo_stream.erb %>
<% container_partial = @card.drafted? ? "cards/drafts/container" : "cards/container" %>
<%= turbo_stream.replace dom_id(@card, :card_container), partial: container_partial, method: :morph, locals: { card: @card.reload } %>
```

Fizzy uses `replace`, `update`, `before`, `after`, `append`, `prepend` and `remove`. `replace` is by far the most common. `prepend` puts a notification at the top of the read or unread list in `app/views/notifications/readings/create.turbo_stream.erb` and `destroy.turbo_stream.erb`, and `after` places a column next to its neighbour in `app/views/columns/right_positions/create.turbo_stream.erb`.

Why: a stream updates several parts of a page in one response, and morphing keeps focus and scroll position (Turbo docs: https://turbo.hotwired.dev/handbook/streams).

## Morphing & Page Refresh

Declare morphing once in the head partial; every page then morphs on refresh. Fizzy calls it with `<% %>` rather than `<%= %>`.

```erb
<%# app/views/layouts/shared/_head.html.erb %>
  <% turbo_refreshes_with method: :morph, scroll: :preserve %>
```

Models send refresh broadcasts with `broadcasts_refreshes` and `broadcasts_refreshes_to`. Fizzy's `Board::Broadcastable` concern declares both: one for the board's own stream and one for every board in the account.

```ruby
# app/models/board/broadcastable.rb
module Board::Broadcastable
  extend ActiveSupport::Concern

  included do
    broadcasts_refreshes
    broadcasts_refreshes_to ->(board) { [ board.account, :all_boards ] }
  end
end
```

Protect client state that a morph would overwrite. `data-turbo-permanent` keeps an element as is, and `turbo:morph-element` or `turbo:before-morph-attribute` listeners adjust or veto changes:

```erb
<%# app/views/cards/comments/_comment.html.erb %>
        <div class="comment__body lexxy-content" data-controller="syntax-highlight retarget-links" data-turbo-permanent>
```

```ruby
# app/helpers/time_helper.rb
  def local_datetime_tag(datetime, style: :time, **attributes)
    # Render empty space to ensure it takes height until the local time is loaded via JS
    tag.time "&nbsp;".html_safe, **attributes, datetime: datetime.to_i, data: { local_time_target: style, action: "turbo:morph-element->local-time#refreshTarget" }
  end
```

```erb
<%# app/views/cards/display/perma/_tags.html.erb %>
    <dialog class="popup panel flex-column align-start justify-start fill-white shadow txt-small"
        data-dialog-target="dialog"
        data-action="turbo:before-morph-attribute->dialog#preventCloseOnMorphing turbo:submit-end->dialog#close">
      <%= turbo_frame_tag card, :tagging, src: new_card_tagging_path(card), loading: :lazy, refresh: :morph %>
    </dialog>
```

Why: morphing lets a broadcast refresh the page without losing scroll, focus or open dialogs (Turbo docs: https://turbo.hotwired.dev/handbook/page_refreshes).

## Prefetching

Turbo prefetches a link on hover by default. Opt a link out with `data-turbo-prefetch="false"`; in Rails, `data: { turbo_prefetch: false }`.

```erb
<%# app/views/sessions/menus/show.html.erb %>
    <%= link_to new_signup_path, class: "btn center txt-small margin-block-start", data: { turbo_prefetch: false } do %>
```

Why: prefetching speeds up navigation, but it sends a GET that the server must be able to answer cheaply (Turbo docs: https://turbo.hotwired.dev/handbook/drive).

## View Transitions

The head partial emits the `view-transition` meta tag unless `@disable_view_transition` is set. Elements opt in to named transitions with `view-transition-name`, and CSS tunes the transition group.

```erb
<%# app/views/layouts/shared/_head.html.erb %>
  <% unless @disable_view_transition %>
    <meta name="view-transition" content="same-origin">
  <% end %>
```

```css
/* app/assets/stylesheets/trays.css */
  .tray--pins {
    inset-inline: var(--tray-margin) auto;
    view-transition-name: tray-pins;
```

```css
/* app/assets/stylesheets/trays.css */
  ::view-transition-group(tray-pins) {
    z-index: 100;
  }
```

Fizzy turns transitions off on a page refresh (the referrer equals the current URL) so a morph does not also animate:

```ruby
# app/controllers/concerns/view_transitions.rb
  included do
    before_action :disable_view_transitions, if: :page_refresh?
  end

  private
    def disable_view_transitions
      @disable_view_transition = true
    end

    def page_refresh?
      request.referrer.present? && request.referrer == request.url
    end
```

Why: the transition is skipped where it would fight with morphing (Fizzy: `app/controllers/concerns/view_transitions.rb`, which carries a FIXME to upstream the fix to turbo-rails).

## Sources

- [Turbo handbook](https://turbo.hotwired.dev/handbook/introduction)
- Fizzy at 6aebc0cea: `app/views`, `app/models/board/broadcastable.rb`, `app/assets/stylesheets/trays.css`
