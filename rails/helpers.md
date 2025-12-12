# Helpers Guide

Comprehensive guide for Rails view helpers.

---

## Philosophy

1. **Helpers are for view logic only** - Not business logic
2. **Domain-specific helpers** - One helper per resource
3. **Keep helpers focused** - Single responsibility
4. **No database queries** - Pass data from controller
5. **Tag builders over string concatenation** - Use `tag` helpers

---

## File Structure

```
app/helpers/
├── application_helper.rb     # Global helpers
├── cards_helper.rb          # Card-specific helpers
├── boards_helper.rb         # Board-specific helpers
├── forms_helper.rb          # Form helpers
├── time_helper.rb           # Time/date helpers
└── html_helper.rb           # HTML processing
```

---

## Application Helper

### Global Helpers

```ruby
# app/helpers/application_helper.rb
module ApplicationHelper
  # Page title with cascading defaults
  def page_title_tag
    parts = [@page_title, Current.account&.name, "My App"].compact
    tag.title parts.join(" | ")
  end

  # Icon rendering
  def icon_tag(name, **options)
    tag.span(
      class: class_names("icon icon--#{name}", options.delete(:class)),
      "aria-hidden": true,
      **options
    )
  end

  # SVG inline
  def inline_svg(name, **options)
    file_path = Rails.root.join("app/assets/images/#{name}.svg")
    return "(not found)" unless File.exist?(file_path)

    svg = File.read(file_path)
    tag.div(svg.html_safe, **options)
  end

  # Flash message rendering
  def flash_messages
    flash.map do |type, message|
      tag.div(message, class: "alert alert-#{type}", role: "alert")
    end.join.html_safe
  end

  # Navigation helpers
  def nav_link_to(text, path, **options)
    active = current_page?(path)
    css_class = class_names(options.delete(:class), "active" => active)

    link_to text, path, class: css_class, **options
  end

  # Boolean to Yes/No
  def yes_no(boolean)
    boolean ? "Yes" : "No"
  end

  # Gravatar
  def gravatar_url(email, size: 80)
    hash = Digest::MD5.hexdigest(email.downcase)
    "https://www.gravatar.com/avatar/#{hash}?s=#{size}&d=identicon"
  end
end
```

---

## Domain-Specific Helpers

### Cards Helper

```ruby
# app/helpers/cards_helper.rb
module CardsHelper
  # Custom tag builders
  def card_article_tag(card, **options, &block)
    classes = [
      options.delete(:class),
      ("golden-effect" if card.golden?),
      ("card--postponed" if card.postponed?),
      ("card--active" if card.active?)
    ].compact.join(" ")

    data = options.delete(:data) || {}
    data[:card_id] = card.id
    data[:drag_and_drop] = true if card.golden?

    tag.article(
      id: dom_id(card),
      style: "--card-color: #{card.color}",
      class: classes,
      data: data,
      **options,
      &block
    )
  end

  # Status badge
  def card_status_badge(card)
    tag.span(
      card.status.humanize,
      class: "badge badge-#{card.status}"
    )
  end

  # Card title with metadata
  def card_title_tag(card)
    parts = [
      card.title,
      "added by #{card.creator.name}",
      "in #{card.board.name}"
    ]
    parts << "assigned to #{card.assignees.map(&:name).to_sentence}" if card.assignees.any?

    tag.title parts.join(" ")
  end

  # Social meta tags
  def card_social_tags(card)
    [
      tag.meta(property: "og:title", content: "#{card.title} | #{card.board.name}"),
      tag.meta(property: "og:description", content: excerpt_text(card.description, length: 200)),
      tag.meta(property: "og:image", content: card_image_url(card)),
      tag.meta(property: "og:url", content: card_url(card))
    ].join.html_safe
  end

  # Button helpers
  def button_to_close_card(card)
    button_to card_closure_path(card), method: :post, class: "btn btn-secondary" do
      icon_tag("close") + tag.span("Close")
    end
  end

  def button_to_remove_card_image(card)
    return unless card.image.attached?

    button_to card_image_path(card), method: :delete, class: "btn btn-danger",
      data: { confirm: "Remove image?" } do
      icon_tag("trash") + tag.span("Remove image", class: "sr-only")
    end
  end

  private
    def card_image_url(card)
      if card.image.attached?
        url_for(card.image)
      else
        asset_url("default-card.png")
      end
    end

    def excerpt_text(rich_text, length: 200)
      truncate(rich_text.to_plain_text, length: length)
    end
end
```

### Boards Helper

```ruby
# app/helpers/boards_helper.rb
module BoardsHelper
  def board_access_badge(board)
    text = board.all_access? ? "All Access" : "Restricted"
    css_class = board.all_access? ? "success" : "warning"

    tag.span text, class: "badge badge-#{css_class}"
  end

  def board_card_count(board)
    count = board.cards.published.count
    tag.span pluralize(count, "card"), class: "card-count"
  end

  def board_members_list(board, limit: 5)
    members = board.users.limit(limit)
    overflow = board.users.count - limit

    content_tag :div, class: "members-list" do
      members.map { |user| user_avatar(user, size: :small) }.join.html_safe +
        (overflow > 0 ? tag.span("+#{overflow}", class: "overflow") : "".html_safe)
    end
  end

  def user_avatar(user, size: :medium)
    size_class = "avatar-#{size}"

    if user.avatar.attached?
      image_tag user.avatar.variant(resize_to_fill: [40, 40]),
        alt: user.name,
        class: "avatar #{size_class}"
    else
      tag.div(
        user.initials,
        class: "avatar avatar-placeholder #{size_class}",
        style: "background-color: #{user.avatar_color}"
      )
    end
  end
end
```

---

## Form Helpers

```ruby
# app/helpers/forms_helper.rb
module FormsHelper
  # Auto-submit form
  def auto_submit_form_with(**attributes, &block)
    data = attributes.delete(:data) || {}
    data[:controller] = "auto-submit #{data[:controller]}".strip

    form_with(**attributes, data: data, &block)
  end

  # Error messages for form
  def form_errors_for(model)
    return unless model.errors.any?

    tag.div class: "error-messages" do
      tag.h3("#{pluralize(model.errors.count, "error")} prohibited this from being saved:") +
      tag.ul do
        model.errors.full_messages.map { |msg| tag.li(msg) }.join.html_safe
      end
    end
  end

  # Field with error
  def field_with_errors(model, attribute, &block)
    css_class = model.errors[attribute].any? ? "field field-with-errors" : "field"

    tag.div class: css_class do
      capture(&block) +
        (model.errors[attribute].any? ? tag.span(model.errors[attribute].join(", "), class: "error") : "".html_safe)
    end
  end

  # Required field marker
  def required_marker
    tag.span "*", class: "required", "aria-label": "required"
  end
end
```

---

## Time Helpers

```ruby
# app/helpers/time_helper.rb
module TimeHelper
  # Local datetime (converted via JS)
  def local_datetime_tag(datetime, style: :time, **attributes)
    tag.time(
      "&nbsp;".html_safe,  # Placeholder
      **attributes,
      datetime: datetime.to_i,
      data: {
        local_time_target: style,
        action: "turbo:morph-element->local-time#refreshTarget"
      }
    )
  end

  # Relative time
  def relative_time_tag(datetime, **options)
    tag.time time_ago_in_words(datetime) + " ago",
      datetime: datetime.iso8601,
      title: datetime.strftime("%B %d, %Y at %l:%M %p"),
      **options
  end

  # Business days ago
  def business_days_ago(date)
    days = (Date.current - date.to_date).to_i
    weekends = (date.to_date..Date.current).count { |d| d.saturday? || d.sunday? }
    business_days = days - weekends

    pluralize(business_days, "business day")
  end

  # Duration in words
  def duration_in_words(seconds)
    return "less than a minute" if seconds < 60

    hours = seconds / 3600
    minutes = (seconds % 3600) / 60

    parts = []
    parts << "#{hours} #{hours == 1 ? 'hour' : 'hours'}" if hours > 0
    parts << "#{minutes} #{minutes == 1 ? 'minute' : 'minutes'}" if minutes > 0

    parts.join(" and ")
  end
end
```

---

## HTML Processing Helpers

```ruby
# app/helpers/html_helper.rb
module HtmlHelper
  include ERB::Util

  EXCLUDE_PUNCTUATION = %(.?,:!;"'<>)
  EXCLUDE_PUNCTUATION_REGEX = /[#{Regexp.escape(EXCLUDE_PUNCTUATION)}]+\z/

  # Auto-link URLs and emails
  def format_html(html)
    fragment = Nokogiri::HTML5.fragment(html)
    auto_link(fragment)
    fragment.to_html.html_safe
  end

  # Excerpt with highlighting
  def smart_excerpt(text, query, radius: 50)
    return truncate(text, length: radius * 2) if query.blank?

    highlighted = highlight(text, query, highlighter: '<mark>\1</mark>')
    excerpt(highlighted, query, radius: radius).html_safe
  end

  # Markdown to HTML (if using markdown)
  def markdown(text)
    return "" if text.blank?

    markdown_renderer.render(text).html_safe
  end

  private
    EXCLUDED_ELEMENTS = %w[ a figcaption pre code ]
    EMAIL_REGEX = /\b[a-zA-Z0-9.!#$%&'*+\/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\b/
    URL_REGEXP = URI::DEFAULT_PARSER.make_regexp(%w[http https])

    def auto_link(fragment)
      fragment.traverse do |node|
        next unless auto_linkable_node?(node)

        content = h(node.text)
        linked_content = content.dup

        auto_link_urls(linked_content)
        auto_link_emails(linked_content)

        node.replace(Nokogiri::HTML5.fragment(linked_content)) if linked_content != content
      end
    end

    def auto_linkable_node?(node)
      node.text? && node.ancestors.none? { |ancestor|
        EXCLUDED_ELEMENTS.include?(ancestor.name)
      }
    end

    def auto_link_urls(text)
      text.gsub!(URL_REGEXP) do |match|
        url, punctuation = extract_url_and_punctuation(match)
        %(<a href="#{url}" rel="noreferrer">#{url}</a>#{punctuation})
      end
    end

    def extract_url_and_punctuation(url_match)
      url_match = CGI.unescapeHTML(url_match)
      if match = url_match.match(EXCLUDE_PUNCTUATION_REGEX)
        len = match[0].length
        [url_match[..-(len+1)], url_match[-len..]]
      else
        [url_match, ""]
      end
    end

    def auto_link_emails(text)
      text.gsub!(EMAIL_REGEX) do |match|
        %(<a href="mailto:#{match}">#{match}</a>)
      end
    end

    def markdown_renderer
      @markdown_renderer ||= Redcarpet::Markdown.new(
        Redcarpet::Render::HTML,
        autolink: true,
        tables: true,
        fenced_code_blocks: true
      )
    end
end
```

---

## Pagination Helpers

```ruby
# app/helpers/pagination_helper.rb
module PaginationHelper
  def pagination_links(collection, **options)
    return if collection.total_pages <= 1

    tag.nav class: "pagination", **options do
      [
        previous_page_link(collection),
        page_links(collection),
        next_page_link(collection)
      ].join.html_safe
    end
  end

  private
    def previous_page_link(collection)
      if collection.prev_page
        link_to "Previous", url_for(page: collection.prev_page), class: "pagination-link"
      else
        tag.span "Previous", class: "pagination-link disabled"
      end
    end

    def next_page_link(collection)
      if collection.next_page
        link_to "Next", url_for(page: collection.next_page), class: "pagination-link"
      else
        tag.span "Next", class: "pagination-link disabled"
      end
    end

    def page_links(collection)
      window = 2
      start_page = [collection.current_page - window, 1].max
      end_page = [collection.current_page + window, collection.total_pages].min

      (start_page..end_page).map do |page|
        if page == collection.current_page
          tag.span page, class: "pagination-link active"
        else
          link_to page, url_for(page: page), class: "pagination-link"
        end
      end.join.html_safe
    end
end
```

---

## Component Helpers

```ruby
# app/helpers/components_helper.rb
module ComponentsHelper
  def alert_box(type: :info, dismissible: true, &block)
    tag.div class: "alert alert-#{type} #{dismissible ? 'alert-dismissible' : ''}", role: "alert" do
      content = capture(&block)
      content += dismiss_button if dismissible
      content
    end
  end

  def badge(text, type: :primary, **options)
    tag.span text, class: class_names("badge badge-#{type}", options.delete(:class)), **options
  end

  def card(**options, &block)
    tag.div class: class_names("card", options.delete(:class)), **options do
      capture(&block)
    end
  end

  def modal(id, title: nil, size: :medium, &block)
    tag.div id: id, class: "modal modal-#{size}", data: { controller: "modal" } do
      tag.div class: "modal-content" do
        modal_header(title) +
        tag.div(class: "modal-body", &block) +
        modal_footer
      end
    end
  end

  private
    def dismiss_button
      tag.button type: "button", class: "close", data: { dismiss: "alert" } do
        tag.span("×", "aria-hidden": true)
      end
    end

    def modal_header(title)
      return "".html_safe unless title

      tag.div class: "modal-header" do
        tag.h5(title, class: "modal-title") +
        tag.button(type: "button", class: "close", data: { dismiss: "modal" }) do
          tag.span("×")
        end
      end
    end

    def modal_footer
      tag.div class: "modal-footer" do
        tag.button "Close", type: "button", class: "btn btn-secondary", data: { dismiss: "modal" }
      end
    end
end
```

---

## Best Practices

### ✅ DO

1. **Use tag builders**
```ruby
# Good
tag.div "Content", class: "card", id: "card-1"

# Bad
"<div class='card' id='card-1'>Content</div>".html_safe
```

2. **Domain-specific helpers**
```ruby
# app/helpers/cards_helper.rb
def card_status_badge(card)
  tag.span card.status, class: "badge badge-#{card.status}"
end
```

3. **Private helper methods**
```ruby
module CardsHelper
  def card_title(card)
    format_title(card.title)
  end

  private
    def format_title(title)
      title.titleize.truncate(50)
    end
end
```

4. **Extract complex logic**
```ruby
# Good - in helper
def user_display_name(user)
  user.name.presence || user.email.split("@").first
end

# Bad - in view
<%= user.name.presence || user.email.split("@").first %>
```

### ❌ DON'T

1. **Business logic**
```ruby
# Bad
def can_edit_card?(card)
  current_user.admin? || card.creator == current_user
end

# Good - put in model or policy
def can_edit_card?(card)
  card.editable_by?(current_user)
end
```

2. **Database queries**
```ruby
# Bad
def recent_cards
  Card.where(created_at: 1.week.ago..).limit(5)
end

# Good - query in controller, helper formats
def recent_cards_list(cards)
  cards.map { |card| card_link(card) }.join(", ").html_safe
end
```

3. **Complex conditionals**
```ruby
# Bad
def card_class(card)
  if card.published? && card.active? && !card.archived?
    "card-active"
  elsif card.draft?
    "card-draft"
  end
end

# Good - push to model
def card_class(card)
  "card-#{card.display_state}"
end
```

---

## Testing Helpers

```ruby
# test/helpers/cards_helper_test.rb
class CardsHelperTest < ActionView::TestCase
  test "card_status_badge returns correct badge" do
    card = cards(:published)

    badge = card_status_badge(card)

    assert_match /badge/, badge
    assert_match /published/, badge
  end

  test "card_article_tag includes golden effect for golden cards" do
    card = cards(:logo)
    card.stub(:golden?, true) do
      result = card_article_tag(card) { "Content" }

      assert_match /golden-effect/, result
    end
  end

  test "card_social_tags includes og meta tags" do
    card = cards(:logo)

    tags = card_social_tags(card)

    assert_match /og:title/, tags
    assert_match /og:description/, tags
    assert_match card.title, tags
  end
end
```

---

## Summary

- **Purpose**: View presentation logic only, no business logic
- **Organization**: Domain-specific helpers per resource
- **Tag Builders**: Use `tag` helpers over string concatenation
- **Focused**: Single responsibility per helper method
- **Private**: Use private methods for helper implementation details
- **Testing**: Test complex helpers, skip simple ones
- **No Queries**: Pass data from controller, don't query in helpers
