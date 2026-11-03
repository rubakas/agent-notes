# System Tests, Jobs, Mailers, and Helpers

## Contents

- [System Tests](#system-tests)
- [Helper Tests](#helper-tests)
- [Mailer Tests](#mailer-tests)
- [Job Tests](#job-tests)
- [Testing Tips](#testing-tips)
- [Sources](#sources)

## System Tests

### Setup with Capybara and headless Chrome

```ruby
# test/application_system_test_case.rb
class ApplicationSystemTestCase < ActionDispatch::SystemTestCase
# ...
  Capybara.register_driver :chrome_headless do |app|
    browser_options.add_argument("--headless")
    Capybara::Selenium::Driver.new(app, browser: :chrome, options: browser_options)
  end
# ...
  if ENV["SYSTEM_TESTS_BROWSER"]
    driven_by :chrome, screen_size: [ 1200, 1000 ]
  else
    driven_by :chrome_headless, screen_size: [ 1200, 1000 ]
  end
# ...
end
```

System tests run Capybara with Selenium and Chrome. Headless Chrome is the default driver, and setting `SYSTEM_TESTS_BROWSER` switches to a visible Chrome. The base class also defines `sign_in_as` for system tests (it visits a session-transfer URL) and a `fill_in_lexxy` helper for the rich-text editor.

Why: headless Chrome runs without a window, and the environment variable lets you watch a failing test (Fizzy: `test/application_system_test_case.rb`).

### System test example

```ruby
# test/system/smoke_test.rb
require "application_system_test_case"
# ...
class SmokeTest < ApplicationSystemTestCase
# ...
  test "create a card" do
    sign_in_as(users(:david))

    visit board_url(boards(:writebook))
    click_on "Add a card"
    fill_in "card_title", with: "Hello, world!"
    fill_in_lexxy with: "I am editing this thing"
    click_on "Create card"

    assert_selector "h3", text: "Hello, world!"
  end
# ...
end
```

System tests drive a real browser. Use `visit`, `fill_in` and `click_on` from the Capybara DSL, then assert on the page with `assert_selector` or `assert_text`.

Why: the test covers routing, controller, view and JavaScript together (Fizzy: `test/system/smoke_test.rb`).

### Wait for elements

```ruby
# test/system/card_refresh_test.rb
class CardRefreshTest < ApplicationSystemTestCase
# ...
  test "a broadcast refresh shows card changes made elsewhere" do
    visit card_url(@card)
    assert_selector "h1", text: @card.title

    update_card_elsewhere

    assert_selector "h1", text: "Retitled elsewhere", wait: 5
    assert_text "Description updated elsewhere"
  end
# ...
end
```

`assert_selector` and `assert_text` retry until Capybara's wait time passes. Pass `wait:` (seconds) to extend it for content that arrives later, such as a broadcast refresh.

Why: Capybara retries the assertion, so a test does not need `sleep` (Fizzy: `test/system/card_refresh_test.rb`).

### Run serially in CI

```ruby
# config/ci.rb
SYSTEM_TEST_ENV = "PARALLEL_WORKERS=1" # system tests can't run reliably in parallel
# ...
    step "Tests: SQLite System", "#{OSS_ENV} #{SYSTEM_TEST_ENV} bin/rails test:system"
```

System tests run with `PARALLEL_WORKERS=1` in CI. Unit and integration tests run in parallel.

Why: system tests cannot run reliably in parallel (Fizzy: the comment in `config/ci.rb`: "system tests can't run reliably in parallel").

## Helper Tests

### Testing view helpers

```ruby
# test/helpers/application_helper_test.rb
class ApplicationHelperTest < ActionView::TestCase
  def parse(html)
    Nokogiri::HTML::DocumentFragment.parse(html)
  end
# ...
  test "page_title_tag on untenanted page" do
    Current.account = nil

    assert_select parse(page_title_tag), "title", text: "Fizzy"
  end
# ...
end
```

Inherit from `ActionView::TestCase`. The helper returns HTML, so the test parses it into a fragment and uses `assert_select` on it.

Why: a helper that builds markup is checked through the markup it renders (Fizzy: `test/helpers/application_helper_test.rb`).

### Setting up test context

```ruby
# test/helpers/application_helper_test.rb
  test "page_title_tag on tenanted page when user has a single account" do
    Current.session = sessions(:david)

    assert_select parse(page_title_tag), "title", text: "Fizzy"
  end
```

Helpers can read `Current`, so the test sets it. Here `Current.session = sessions(:david)` is enough for `page_title_tag` to resolve the account and user, and `Current.account = nil` models an untenanted page.

Why: the helper's output depends on `Current`, so the test sets the state it reads (Fizzy: `test/helpers/application_helper_test.rb`).

## Mailer Tests

### Basic mailer test

```ruby
# test/mailers/magic_link_mailer_test.rb
require "test_helper"
# ...
class MagicLinkMailerTest < ActionMailer::TestCase
  test "sign_in_instructions" do
    magic_link = MagicLink.create!(identity: identities(:kevin))
    email = MagicLinkMailer.sign_in_instructions(magic_link)

    assert_emails 1 do
      email.deliver_now
    end

    assert_equal [ "kevin@37signals.com" ], email.to
    assert_equal "Your Fizzy code is #{ magic_link.code }", email.subject
    assert_match magic_link.code, email.body.encoded
  end
end
```

Inherit from `ActionMailer::TestCase`. Calling the mailer method returns a message. `assert_emails 1 do ... end` checks that delivering it sent one email, and `email.to`, `email.subject` and `email.body.encoded` expose the content.

Why: the test checks recipient, subject and the sign-in code in the body, the parts a user sees (Fizzy: `test/mailers/magic_link_mailer_test.rb`).

### Delivery errors

```ruby
# test/mailers/smtp_delivery_error_test.rb
  test "deliver_later ignores bad recipient addresses" do
    assert_nothing_raised do
      perform_enqueued_jobs only: ActionMailer::MailDeliveryJob do
        TestMailer.smtp_syntax_error("501 5.1.3 Bad recipient address syntax\n").deliver_later
      end
    end
  end
```

`deliver_later` goes through `ActionMailer::MailDeliveryJob`, so the test runs only that job with `perform_enqueued_jobs only:`. The same file asserts that other SMTP syntax errors are re-raised and that timeouts and a busy server are retried.

Why: the test runs the real job class that carries the error handling (Fizzy: `test/mailers/smtp_delivery_error_test.rb`).

## Job Tests

### Perform a job directly

```ruby
# test/jobs/delete_unused_tags_job_test.rb
require "test_helper"
# ...
class DeleteUnusedTagsJobTest < ActiveJob::TestCase
  test "deletes tags that are not used by any cards" do
    unused = Tag.create!(title: "unused")

    assert_changes -> { Tag.count }, -1 do
      DeleteUnusedTagsJob.perform_now
    end

    assert_not Tag.exists?(unused.id), "Unused tag should be deleted"
  end
end
```

Inherit from `ActiveJob::TestCase` and call `perform_now`. The job body is one call into the model, so the test asserts the model's effect.

Why: the job is thin, so the test exercises the behavior it triggers (Fizzy: `test/jobs/delete_unused_tags_job_test.rb`).

### Run only the jobs under test

```ruby
# test/integration/notifications_test.rb
class NotificationDeliveryTest < ActiveSupport::TestCase
# ...
  test "notifications for inactive users are created but do not trigger push" do
    @assignee.deactivate

    assert_difference -> { Notification.count }, 1 do
      perform_enqueued_jobs only: [ NotifyRecipientsJob, Notification::PushJob ] do
        @card.toggle_assignment(@assignee)
      end
    end

    assert_no_push_delivered
    assert_no_web_push_delivered
  end
# ...
end
```

`perform_enqueued_jobs only:` runs the listed job classes and leaves the rest enqueued. The action enqueues `NotifyRecipientsJob`, which creates the notification, and `Notification::PushJob` then runs `push`. For an inactive user the notification exists but nothing is pushed.

Why: a chain of jobs is followed only as far as the test needs (Fizzy: `test/integration/notifications_test.rb`).

### Job context and Current

Jobs get their account through `AccountTenanted`, not from the test's `Current`. The `perform_enqueued_jobs` override in `test/test_helper.rb` clears `Current.account` while jobs run (see the `testing-models-fixtures.md` reference), so an enqueue in a test must serialize its account and the job must restore it.

Why: a job that passes only because `Current.account` leaked from `setup` would fail in production (Fizzy: `test/test_helper.rb`, AGENTS.md: "Background jobs serialize and restore").

## Testing Tips

### Time travel

```ruby
# test/models/card/stallable_test.rb
class Card::StallableTest < ActiveSupport::TestCase
# ...
  test "a card with an old activity spike is stalled" do
    cards(:logo).create_activity_spike!

    travel_to 3.months.from_now

    assert cards(:logo).stalled?
    assert_includes Card.stalled, cards(:logo)
  end
# ...
end
```

`travel_to` moves the clock, and `freeze_time` stops it. Both come from `ActiveSupport::Testing::TimeHelpers`, and Rails restores the real time after each test. Pass a block to scope the change (as `test/models/webhook/delinquency_tracker_test.rb` does). Fizzy's tests use `travel_to` or `freeze_time` on 27 lines.

Why: the test controls the time the model sees, so time-based states are reproducible (Fizzy: `test/models/card/stallable_test.rb`).

### HTTP stubs: WebMock and VCR

```ruby
# test/test_helper.rb
WebMock.allow_net_connect!
# ...
VCR.configure do |config|
  config.allow_http_connections_when_no_cassette = true
  config.cassette_library_dir = "test/vcr_cassettes"
  config.hook_into :webmock
# ...
end
```

`test_helper.rb` requires WebMock and VCR and calls `WebMock.allow_net_connect!`, so unstubbed requests are not blocked. VCR is configured to record into `test/vcr_cassettes` and to match on method, URI and the body with timestamps ignored. `test/test_helpers/vcr_test_helper.rb` can insert a cassette named after the test.

Why: recorded cassettes keep tests that call external services fast and repeatable (Fizzy: `test/test_helper.rb`).

### Mocha for stubbing

```ruby
# test/jobs/account/incinerate_due_job_test.rb
class Account::IncinerateDueJobTest < ActiveJob::TestCase
# ...
  test "finds accounts up for incineration" do
    @account.cancel(initiated_by: @user)
    @account.cancellation.update!(created_at: 31.days.ago)

    Account.any_instance.expects(:incinerate).once

    Account::IncinerateDueJob.perform_now
  end
# ...
end
```

Fizzy requires `mocha/minitest` and uses `stubs`, `expects` and `any_instance` in about 23 test files. Prefer fixtures and real objects, and stub only what the test cannot reach (a payment service, a remote host, a single method whose call you want to count).

Why: `expects(:incinerate).once` checks that the job calls the model, whose own behavior has its own test (Fizzy: `test/jobs/account/incinerate_due_job_test.rb`).

## Sources

- Fizzy: `test/application_system_test_case.rb`, `test/system/smoke_test.rb`, `test/system/card_refresh_test.rb`, `config/ci.rb`
- Fizzy: `test/helpers/application_helper_test.rb`, `test/mailers/magic_link_mailer_test.rb`, `test/mailers/smtp_delivery_error_test.rb`
- Fizzy: `test/jobs/delete_unused_tags_job_test.rb`, `test/jobs/account/incinerate_due_job_test.rb`, `test/integration/notifications_test.rb`
- Fizzy: `test/models/card/stallable_test.rb`, `test/models/webhook/delinquency_tracker_test.rb`, `test/test_helper.rb`, `test/test_helpers/vcr_test_helper.rb`
- Fizzy: `AGENTS.md` ("Multi-tenancy is URL-based")
