---
name: rails-testing-system
description: "Rails testing: helper tests, mailer tests, job tests, fixtures, test helpers, and tips. Use when user is writing tests for helpers, mailers, jobs, or needs fixture/test-helper guidance."
group: rails
---

# Testing Helpers, Jobs & Configuration

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

### DO

1. **Test behavior, not implementation**
2. **Use descriptive test names**
3. **Test permissions thoroughly**
4. **Use fixtures for consistent data**
5. **Keep tests independent**
6. **Test happy path and edge cases**
7. **Use helper methods to DRY up tests**
8. **Run tests frequently**

### DON'T

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
