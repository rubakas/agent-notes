# Tests Guide

Comprehensive guide for Rails testing patterns.

---

## Testing Philosophy

1. **Test behavior, not implementation**
2. **Test happy path and edge cases**
3. **Test permissions thoroughly**
4. **Use fixtures for consistent data**
5. **Keep tests independent**
6. **Fast tests = tests that get run**

---

## Test Structure

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

## Model Tests

### Test File Structure

```ruby
class CardTest < ActiveSupport::TestCase
  # Setup runs before each test
  setup do
    @card = cards(:logo)
  end

  # Teardown runs after each test (optional)
  teardown do
    # Cleanup if needed
  end

  # Test naming: "test description"
  test "belongs to board" do
    assert_equal boards(:writebook), @card.board
  end

  test "validates title presence when published" do
    card = Card.new(status: :published)

    assert_not card.valid?
    assert_includes card.errors[:title], "can't be blank"
  end
end
```

### Testing Associations

```ruby
test "belongs to board" do
  card = cards(:logo)
  assert_equal boards(:writebook), card.board
end

test "has many comments" do
  card = cards(:logo)
  assert_respond_to card, :comments
  assert_instance_of ActiveRecord::Associations::CollectionProxy, card.comments
end

test "has many tags through taggings" do
  card = cards(:logo)
  tag = tags(:bug)

  card.taggings.create!(tag: tag)

  assert_includes card.tags, tag
end

test "destroys dependent comments" do
  card = cards(:logo)
  comment = card.comments.create!(body: "Test", creator: users(:david))

  assert_difference -> { Comment.count }, -1 do
    card.destroy
  end
end
```

### Testing Validations

```ruby
test "validates presence of title" do
  card = Card.new
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

test "validates email format" do
  user = User.new(email: "invalid")

  assert_not user.valid?
  assert_includes user.errors[:email], "is invalid"
end

test "validates conditional presence" do
  card = Card.new(status: :draft)
  assert card.valid?  # title not required for draft

  card.status = :published
  assert_not card.valid?
  assert_includes card.errors[:title], "can't be blank"
end
```

### Testing Scopes

```ruby
test "published scope returns published cards" do
  published_card = cards(:logo)
  draft_card = cards(:draft)

  assert_includes Card.published, published_card
  assert_not_includes Card.published, draft_card
end

test "closed scope returns cards with closure" do
  card = cards(:logo)
  card.close

  assert_includes Card.closed, card
  assert_not_includes Card.open, card
end

test "parameterized scope filters correctly" do
  user = users(:david)
  card = cards(:logo)
  card.assignments.create!(user: user)

  assert_includes Card.assigned_to(user), card
end
```

### Testing Callbacks

```ruby
test "sets default title before save" do
  card = Card.new(board: boards(:writebook), status: :published)
  card.save!

  assert_equal "Untitled", card.title
end

test "assigns number on create" do
  card = Card.create!(board: boards(:writebook), title: "Test")

  assert_not_nil card.number
  assert card.number > 0
end

test "touches board after save" do
  card = cards(:logo)
  board = card.board

  assert_changes -> { board.reload.updated_at } do
    card.update!(title: "New Title")
  end
end

test "callback only runs under condition" do
  card = cards(:draft)

  assert_no_changes -> { card.board.reload.updated_at } do
    card.update!(title: "New Title")  # Draft cards don't touch board
  end
end
```

### Testing Instance Methods

```ruby
test "closed? returns true when closure exists" do
  card = cards(:logo)
  assert_not card.closed?

  card.close
  assert card.closed?
end

test "move_to changes board and updates events" do
  card = cards(:logo)
  new_board = boards(:other_board)

  card.move_to(new_board)

  assert_equal new_board, card.reload.board
  assert_equal new_board.id, card.events.pluck(:board_id).uniq.first
end

test "archive sets archived_at" do
  card = cards(:logo)

  freeze_time do
    card.archive
    assert_equal Time.current, card.archived_at
  end
end
```

### Testing Transactions

```ruby
test "transaction rolls back on error" do
  card = cards(:logo)

  assert_no_difference "Card::Closure.count" do
    assert_raises(ActiveRecord::RecordInvalid) do
      card.transaction do
        card.create_closure!
        raise ActiveRecord::RecordInvalid  # Force rollback
      end
    end
  end

  assert_not card.closed?
end

test "transaction commits on success" do
  card = cards(:logo)

  assert_difference -> { card.events.count }, +1 do
    card.close
  end

  assert card.closed?
end
```

### Testing Class Methods

```ruby
test "close_all_stale closes inactive cards" do
  old_card = cards(:logo)
  old_card.update!(last_active_at: 2.months.ago)

  recent_card = cards(:other)
  recent_card.update!(last_active_at: 1.day.ago)

  Card.close_all_stale

  assert old_card.reload.closed?
  assert_not recent_card.reload.closed?
end
```

---

## Controller Tests

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

  test "show displays board" do
    board = boards(:writebook)

    get board_path(board)

    assert_response :success
    assert_select "h1", board.name
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

test "non-member cannot access board" do
  logout_and_sign_in_as :other_user

  get board_path(boards(:writebook))

  assert_response :forbidden
end

test "unauthenticated user redirected to login" do
  logout

  get boards_path

  assert_redirected_to new_session_path
end

test "owner can destroy board" do
  sign_in_as boards(:writebook).owner

  assert_difference -> { Board.count }, -1 do
    delete board_path(boards(:writebook))
  end

  assert_response :redirect
end
```

### Testing Response Formats

```ruby
test "responds with HTML" do
  get boards_path

  assert_response :success
  assert_match "text/html", response.content_type
end

test "responds with JSON" do
  board = boards(:writebook)

  get board_path(board), as: :json

  assert_response :success
  assert_match "application/json", response.content_type

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

### Testing Flash Messages

```ruby
test "success flash on create" do
  post boards_path, params: { board: { name: "Test" } }

  assert_equal "Board created", flash[:notice]
end

test "error flash on invalid create" do
  post boards_path, params: { board: { name: "" } }

  assert_match /error/, flash[:alert].downcase
end
```

### Testing Redirects

```ruby
test "redirects to board after create" do
  post boards_path, params: { board: { name: "Test" } }

  assert_redirected_to board_path(Board.last)
end

test "redirects back with fallback" do
  board = boards(:writebook)

  patch board_path(board),
    params: { board: { name: "Updated" } },
    headers: { "HTTP_REFERER" => boards_path }

  assert_redirected_to boards_path
end
```

### Testing Parameters

```ruby
test "permits valid parameters" do
  post boards_path, params: {
    board: {
      name: "Test",
      description: "Test description"
    }
  }

  board = Board.last
  assert_equal "Test", board.name
  assert_equal "Test description", board.description
end

test "filters unpermitted parameters" do
  post boards_path, params: {
    board: {
      name: "Test",
      admin: true  # Unpermitted
    }
  }

  board = Board.last
  assert_equal "Test", board.name
  assert_not board.respond_to?(:admin)
end
```

---

## System Tests

System tests use a real browser (Selenium) to test the full stack.

### Basic System Test

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

  test "closing a card" do
    sign_in_as users(:david)
    card = cards(:logo)

    visit card_url(card)
    click_on "Close"

    assert_selector ".badge", text: "Closed"
  end

  test "adding a comment" do
    sign_in_as users(:david)
    card = cards(:logo)

    visit card_url(card)

    fill_in "Comment", with: "Great work!"
    click_on "Post comment"

    assert_text "Great work!"
  end
end
```

### Testing JavaScript Interactions

```ruby
test "opening and closing modal", js: true do
  sign_in_as users(:david)

  visit boards_path
  click_on "New Board"

  # Modal should appear
  assert_selector "#new-board-modal", visible: true

  click_on "Cancel"

  # Modal should disappear
  assert_no_selector "#new-board-modal", visible: true
end

test "auto-save works", js: true do
  sign_in_as users(:david)
  card = cards(:logo)

  visit edit_card_path(card)

  fill_in "Title", with: "Auto-saved title"

  # Wait for auto-save
  assert_text "Saved", wait: 3

  visit card_path(card)
  assert_text "Auto-saved title"
end
```

### Testing Turbo Frames

```ruby
test "navigating within turbo frame" do
  sign_in_as users(:david)

  visit boards_path

  within("#boards-frame") do
    click_on "Show archived"
    assert_text "Archived Boards"
  end

  # Page didn't fully reload
  assert_current_path boards_path
end
```

---

## Integration Tests

Test complete user workflows across multiple requests.

```ruby
class UserFlowTest < ActionDispatch::IntegrationTest
  test "complete card workflow" do
    # Sign in
    sign_in_as :david

    # Create board
    post boards_path, params: { board: { name: "My Board" } }
    board = Board.last

    # Create card
    post board_cards_path(board), params: {
      card: { title: "My Card" }
    }
    card = Card.last

    # Add comment
    post card_comments_path(card), params: {
      comment: { body: "First comment" }
    }

    # Close card
    post card_closure_path(card)

    # Verify final state
    assert card.reload.closed?
    assert_equal 1, card.comments.count
  end
end
```

---

## Helper Tests

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

## Mailer Tests

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

  test "email includes correct links" do
    user = users(:david)
    card = cards(:logo)

    email = NotificationMailer.card_assigned(user, card)

    assert_match card_url(card), email.body.encoded
  end
end
```

---

## Job Tests

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

    # Assert side effects
    assert_equal 1, user.notifications.count
  end

  test "job retries on error" do
    NotificationJob.stub(:notify, -> { raise Net::HTTPServerError }) do
      assert_enqueued_jobs 2 do  # Original + 1 retry
        perform_enqueued_jobs(only: NotificationJob) do
          NotificationJob.perform_later(users(:david), "test")
        rescue Net::HTTPServerError
          # Expected
        end
      end
    end
  end
end
```

---

## Fixtures

### Creating Fixtures

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

### Using Fixtures

```ruby
test "fixture data is loaded" do
  card = cards(:logo)

  assert_equal "The logo isn't big enough", card.title
  assert_equal boards(:writebook), card.board
  assert card.published?
end

test "fixture associations work" do
  card = cards(:logo)

  assert_equal users(:david), card.creator
  assert_equal accounts(:company), card.account
end
```

---

## Test Helpers

### Session Helper

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
```

### Custom Assertions

```ruby
# test/test_helpers/custom_assertions.rb
module CustomAssertions
  def assert_card_closed(card)
    assert card.closed?, "Expected card to be closed"
  end

  def assert_redirected_with_notice(path, notice)
    assert_redirected_to path
    assert_equal notice, flash[:notice]
  end

  def assert_turbo_stream_action(action, target)
    assert_match action.to_s, response.body
    assert_match target.to_s, response.body
  end
end
```

---

## Test Database

### Setup

```ruby
# test/test_helper.rb
ENV["RAILS_ENV"] ||= "test"
require_relative "../config/environment"
require "rails/test_help"

class ActiveSupport::TestCase
  # Run tests in parallel
  parallelize(workers: :number_of_processors)

  # Setup all fixtures
  fixtures :all

  # Add custom helpers
  include SessionTestHelper
  include CustomAssertions
end

class ActionDispatch::IntegrationTest
  include SessionTestHelper
end
```

### Database Cleaning

```ruby
# Between tests, Rails automatically:
# - Wraps each test in a transaction
# - Rolls back after each test
# - Ensures clean state

# For system tests (JavaScript), use truncation:
class ApplicationSystemTestCase < ActionDispatch::SystemTestCase
  driven_by :selenium, using: :headless_chrome

  setup do
    # Custom setup if needed
  end

  teardown do
    # Cleanup if needed
  end
end
```

---

## Testing Tips

### Time Travel

```ruby
test "event expires after time" do
  event = events(:notification)

  travel 2.days do
    assert event.expired?
  end
end

test "scheduled job runs at correct time" do
  freeze_time do
    ScheduledJob.perform_later(Time.current + 1.hour)

    travel 1.hour do
      perform_enqueued_jobs
      assert_job_ran
    end
  end
end
```

### Stubbing Methods

```ruby
test "uses stubbed method" do
  user = users(:david)

  user.stub(:premium?, true) do
    assert user.can_access_premium_features?
  end
end
```

### Testing Errors

```ruby
test "raises error on invalid input" do
  assert_raises(ActiveRecord::RecordInvalid) do
    Card.create!(title: nil, status: :published)
  end
end

test "rescues error and handles gracefully" do
  card = cards(:logo)

  card.stub(:close, -> { raise StandardError }) do
    assert_nothing_raised do
      card.safe_close  # Method that rescues errors
    end
  end
end
```

---

## Best Practices

### ✅ DO

1. **Test behavior, not implementation**
2. **Use descriptive test names**
3. **Test permissions thoroughly**
4. **Use fixtures for consistent data**
5. **Keep tests independent**
6. **Test happy path and edge cases**
7. **Use helper methods to DRY up tests**
8. **Run tests frequently**

### ❌ DON'T

1. **Test private methods directly**
2. **Test framework code**
3. **Create brittle tests**
4. **Test implementation details**
5. **Skip setup/teardown when needed**
6. **Write slow tests**
7. **Leave failing tests**

---

## Running Tests

```bash
# All tests
bin/rails test

# Specific file
bin/rails test test/models/card_test.rb

# Specific test
bin/rails test test/models/card_test.rb:10

# System tests
bin/rails test:system

# With coverage
COVERAGE=true bin/rails test

# Parallel
PARALLEL_WORKERS=4 bin/rails test

# Seed for reproducibility
bin/rails test TESTOPTS="--seed=12345"
```

---

## Summary

- **Model Tests**: Associations, validations, scopes, callbacks, methods
- **Controller Tests**: CRUD, permissions, formats, parameters
- **System Tests**: Full-stack browser testing with Selenium
- **Integration Tests**: Multi-request workflows
- **Fixtures**: Consistent test data
- **Helpers**: DRY up common test patterns
- **Coverage**: Aim for high coverage of critical paths
