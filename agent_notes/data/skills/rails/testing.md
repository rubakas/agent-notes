# Testing

## Testing — Models

Comprehensive guide for Rails testing patterns.

---

### Testing Philosophy

1. **Test behavior, not implementation**
2. **Test happy path and edge cases**
3. **Test permissions thoroughly**
4. **Use fixtures for consistent data**
5. **Keep tests independent**
6. **Fast tests = tests that get run**

---

### Test Structure

```
test/
├── controllers/
│   ├── boards_controller_test.rb
│   └── cards/
│       └── closures_controller_test.rb
├── models/
│   ├── card_test.rb
│   └── card/
│       └── closeable_test.rb
├── system/
│   └── cards_test.rb
├── integration/
│   └── user_flow_test.rb
├── helpers/
│   └── cards_helper_test.rb
├── mailers/
│   └── notification_mailer_test.rb
├── jobs/
│   └── notification_job_test.rb
└── fixtures/
    ├── cards.yml
    ├── users.yml
    └── boards.yml
```

---

### Model Tests

```ruby
class CardTest < ActiveSupport::TestCase
  setup do
    @card = cards(:logo)
  end

  # Testing Associations
  test "belongs to board" do
    assert_equal boards(:writebook), @card.board
  end

  test "has many tags through taggings" do
    tag = tags(:bug)
    @card.taggings.create!(tag: tag)
    assert_includes @card.tags, tag
  end

  test "destroys dependent comments" do
    comment = @card.comments.create!(body: "Test", creator: users(:david))

    assert_difference -> { Comment.count }, -1 do
      @card.destroy
    end
  end

  # Testing Validations
  test "validates presence of title when published" do
    card = Card.new(status: :published)
    assert_not card.valid?
    assert_includes card.errors[:title], "can't be blank"
  end

  test "validates uniqueness of number scoped to account" do
    existing = cards(:logo)

    card = Card.new(
      account: existing.account,
      board: boards(:writebook),
      number: existing.number
    )

    assert_not card.valid?
    assert_includes card.errors[:number], "has already been taken"
  end

  # Testing Scopes
  test "published scope returns published cards" do
    published_card = cards(:logo)
    draft_card = cards(:draft)

    assert_includes Card.published, published_card
    assert_not_includes Card.published, draft_card
  end

  test "closed scope returns cards with closure" do
    @card.close

    assert_includes Card.closed, @card
    assert_not_includes Card.open, @card
  end

  # Testing Callbacks
  test "assigns number on create" do
    card = Card.create!(board: boards(:writebook), title: "Test")

    assert_not_nil card.number
    assert card.number > 0
  end

  test "touches board after save" do
    board = @card.board

    assert_changes -> { board.reload.updated_at } do
      @card.update!(title: "New Title")
    end
  end

  # Testing Instance Methods
  test "closed? returns true when closure exists" do
    assert_not @card.closed?

    @card.close
    assert @card.closed?
  end

  test "move_to changes board and updates events" do
    new_board = boards(:other_board)

    @card.move_to(new_board)

    assert_equal new_board, @card.reload.board
    assert_equal new_board.id, @card.events.pluck(:board_id).uniq.first
  end

  test "archive sets archived_at" do
    freeze_time do
      @card.archive
      assert_equal Time.current, @card.archived_at
    end
  end

  # Testing Transactions
  test "transaction rolls back on error" do
    assert_no_difference "Card::Closure.count" do
      assert_raises(ActiveRecord::RecordInvalid) do
        @card.transaction do
          @card.create_closure!
          raise ActiveRecord::RecordInvalid
        end
      end
    end

    assert_not @card.closed?
  end

  test "transaction commits on success" do
    assert_difference -> { @card.events.count }, +1 do
      @card.close
    end

    assert @card.closed?
  end

  # Testing Class Methods
  test "close_all_stale closes inactive cards" do
    old_card = cards(:logo)
    old_card.update!(last_active_at: 2.months.ago)

    recent_card = cards(:other)
    recent_card.update!(last_active_at: 1.day.ago)

    Card.close_all_stale

    assert old_card.reload.closed?
    assert_not recent_card.reload.closed?
  end
end
```

---

## Testing — Controllers & Integration

### Basic CRUD Tests

```ruby
class BoardsControllerTest < ActionDispatch::IntegrationTest
  setup do
    sign_in_as :kevin
  end

  test "index shows boards" do
    get boards_path

    assert_response :success
    assert_select "h1", "Boards"
  end

  test "create creates board" do
    assert_difference -> { Board.count }, +1 do
      post boards_path, params: { board: { name: "New Board" } }
    end

    assert_redirected_to board_path(Board.last)
    assert_equal "New Board", Board.last.name
  end

  test "update updates board" do
    board = boards(:writebook)

    patch board_path(board), params: { board: { name: "Updated" } }

    assert_redirected_to board_path(board)
    assert_equal "Updated", board.reload.name
  end

  test "destroy removes board" do
    board = boards(:writebook)

    assert_difference -> { Board.count }, -1 do
      delete board_path(board)
    end

    assert_redirected_to boards_path
  end
end
```

### Testing Permissions

```ruby
test "non-admin cannot update board" do
  logout_and_sign_in_as :member

  board = boards(:writebook)
  original_name = board.name

  patch board_path(board), params: { board: { name: "Hacked" } }

  assert_response :forbidden
  assert_equal original_name, board.reload.name
end

test "unauthenticated user redirected to login" do
  logout

  get boards_path

  assert_redirected_to new_session_path
end
```

### Testing Response Formats

```ruby
test "responds with JSON" do
  board = boards(:writebook)

  get board_path(board), as: :json

  assert_response :success
  json = JSON.parse(response.body)
  assert_equal board.name, json["name"]
end

test "responds with Turbo Stream" do
  post boards_path,
    params: { board: { name: "Test" } },
    as: :turbo_stream

  assert_response :success
  assert_match "text/vnd.turbo-stream.html", response.content_type
  assert_match "turbo-stream", response.body
end
```

### Integration Tests

```ruby
class UserFlowTest < ActionDispatch::IntegrationTest
  test "complete card workflow" do
    sign_in_as :david

    post boards_path, params: { board: { name: "My Board" } }
    board = Board.last

    post board_cards_path(board), params: {
      card: { title: "My Card" }
    }
    card = Card.last

    post card_closure_path(card)

    assert card.reload.closed?
  end
end
```

---

## Testing — System Tests, Helpers, Jobs, Fixtures

### System Tests

```ruby
class CardsTest < ApplicationSystemTestCase
  test "creating a card" do
    sign_in_as users(:david)

    visit board_url(boards(:writebook))
    click_on "Add a card"

    fill_in "Title", with: "New feature"
    fill_in "Description", with: "Build something awesome"
    click_on "Create card"

    assert_selector "h3", text: "New feature"
    assert_text "Build something awesome"
  end

  test "auto-save works", js: true do
    sign_in_as users(:david)
    card = cards(:logo)

    visit edit_card_path(card)
    fill_in "Title", with: "Auto-saved title"
    assert_text "Saved", wait: 3

    visit card_path(card)
    assert_text "Auto-saved title"
  end

  test "navigating within turbo frame" do
    sign_in_as users(:david)

    visit boards_path

    within("#boards-frame") do
      click_on "Show archived"
      assert_text "Archived Boards"
    end

    assert_current_path boards_path
  end
end
```

---

### Helper Tests

```ruby
class CardsHelperTest < ActionView::TestCase
  test "card_article_tag generates article with classes" do
    card = cards(:logo)
    card.stub(:golden?, true) do
      result = card_article_tag(card) { "Content" }

      assert_match /golden-effect/, result
      assert_match /article/, result
    end
  end

  test "card_status_badge returns correct badge" do
    card = cards(:logo)

    badge = card_status_badge(card)

    assert_match /badge/, badge
    assert_match /published/, badge
  end
end
```

---

### Mailer Tests

```ruby
class NotificationMailerTest < ActionMailer::TestCase
  test "notification email" do
    user = users(:david)
    card = cards(:logo)

    email = NotificationMailer.card_assigned(user, card)

    assert_emails 1 do
      email.deliver_now
    end

    assert_equal [user.email], email.to
    assert_equal "You've been assigned to a card", email.subject
    assert_match card.title, email.body.encoded
  end
end
```

---

### Job Tests

```ruby
class NotificationJobTest < ActiveJob::TestCase
  test "enqueues job" do
    assert_enqueued_with(job: NotificationJob) do
      NotificationJob.perform_later(users(:david), "test")
    end
  end

  test "job performs notification" do
    user = users(:david)

    perform_enqueued_jobs do
      NotificationJob.perform_later(user, "test")
    end

    assert_equal 1, user.notifications.count
  end
end
```

---

### Fixtures

```yaml
# test/fixtures/cards.yml
logo:
  id: <%= ActiveRecord::FixtureSet.identify("logo", :uuid) %>
  number: 1
  board: writebook
  creator: david
  title: The logo isn't big enough
  status: published
  created_at: <%= 1.week.ago %>
  account: company

draft:
  number: 2
  board: writebook
  creator: david
  title: Draft card
  status: draft
  created_at: <%= 1.day.ago %>
  account: company
```

---

### Test Helpers

```ruby
# test/test_helpers/session_test_helper.rb
module SessionTestHelper
  def sign_in_as(user_or_fixture_name)
    user = user_or_fixture_name.is_a?(User) ? user_or_fixture_name : users(user_or_fixture_name)

    post session_url, params: {
      email: user.email,
      password: "password"
    }

    assert_response :redirect
  end

  def logout
    delete session_url
    assert_response :redirect
  end

  def logout_and_sign_in_as(user)
    logout
    sign_in_as(user)
  end
end

# test/test_helpers/custom_assertions.rb
module CustomAssertions
  def assert_card_closed(card)
    assert card.closed?, "Expected card to be closed"
  end

  def assert_turbo_stream_action(action, target)
    assert_match action.to_s, response.body
    assert_match target.to_s, response.body
  end
end
```

---

### Test Database Setup

```ruby
# test/test_helper.rb
ENV["RAILS_ENV"] ||= "test"
require_relative "../config/environment"
require "rails/test_help"

class ActiveSupport::TestCase
  parallelize(workers: :number_of_processors)
  fixtures :all

  include SessionTestHelper
  include CustomAssertions
end

class ActionDispatch::IntegrationTest
  include SessionTestHelper
end
```

---

### Testing Tips

```ruby
# Time Travel
test "event expires after time" do
  event = events(:notification)

  travel 2.days do
    assert event.expired?
  end
end

# Stubbing Methods
test "uses stubbed method" do
  user = users(:david)

  user.stub(:premium?, true) do
    assert user.can_access_premium_features?
  end
end

# Testing Errors
test "raises error on invalid input" do
  assert_raises(ActiveRecord::RecordInvalid) do
    Card.create!(title: nil, status: :published)
  end
end
```

---

### Running Tests

```bash
bin/rails test
bin/rails test test/models/card_test.rb
bin/rails test test/models/card_test.rb:10
bin/rails test:system
PARALLEL_WORKERS=4 bin/rails test
bin/rails test TESTOPTS="--seed=12345"
```
