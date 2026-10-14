# Testing Models, Fixtures, and Setup

## Contents

- [Testing Philosophy](#testing-philosophy)
- [Test Structure](#test-structure)
- [Model Tests](#model-tests)
- [Fixtures](#fixtures)
- [Test Database Setup](#test-database-setup)
- [Test Helpers](#test-helpers)
- [Running Tests](#running-tests)
- [Sources](#sources)

## Testing Philosophy

Fizzy uses Minitest (the Rails default), not RSpec, and its Gemfile has no factory gem.

1. **Fixtures over factories**: deterministic data loaded once, with `fixtures :all`.
2. **Behavior tests**: assert what the model does (state, events), not how.
3. **Tests mirror `app/`**: `test/models/card/closeable_test.rb` tests `app/models/card/closeable.rb`.
4. **One test class per model or concern.**
5. **Assert state changes** with `assert_difference` and `assert_changes`.

Why: fixture ids are built to sort older than any runtime record, which keeps `.first` and `.last` deterministic (AGENTS.md: "generated to sort older than any runtime record").

## Test Structure

```
test/
├── application_system_test_case.rb
├── models/
│   ├── card_test.rb
│   └── card/
│       ├── closeable_test.rb
│       ├── pinnable_test.rb
│       └── golden_test.rb
├── controllers/
│   ├── boards_controller_test.rb
│   └── cards/
│       ├── closures_controller_test.rb
│       └── pins_controller_test.rb
├── integration/
│   └── notifications_test.rb
├── helpers/
│   └── application_helper_test.rb
├── mailers/
│   └── magic_link_mailer_test.rb
├── jobs/
│   └── delete_unused_tags_job_test.rb
├── system/
│   └── smoke_test.rb
├── test_helpers/
│   ├── session_test_helper.rb
│   ├── card_test_helper.rb
│   └── change_test_helper.rb
├── fixtures/
│   ├── cards.yml
│   ├── boards.yml
│   └── users.yml
└── test_helper.rb
```

Controller tests live in `controllers/`, model tests in `models/`, and so on. Reusable assertions live in `test_helpers/` as modules.

Why: the layout mirrors the source tree, so the test for a file is where you expect it (Fizzy: `test/`).

## Model Tests

### Testing a concern in isolation

```ruby
# test/models/card/closeable_test.rb
require "test_helper"
# ...
class Card::CloseableTest < ActiveSupport::TestCase
  setup do
    Current.session = sessions(:david)
  end
# ...
  test "close cards" do
    assert_not cards(:logo).closed?

    assert_difference -> { cards(:logo).events.count }, +1 do
      cards(:logo).close(user: users(:kevin))
    end

    assert cards(:logo).closed?
    assert cards(:logo).events.last.action.card_closed?
    assert_equal users(:kevin), cards(:logo).closed_by
  end
# ...
end
```

**Key patterns:**
- `setup { Current.session = sessions(:david) }` gives the test a session, and through it an account and user.
- Fixtures are read by label: `cards(:logo)`, `users(:kevin)`.
- `assert_difference -> { ... }, +1` checks a state change.
- The test asserts the recorded event (`events.last.action.card_closed?`) and `closed_by`, not callbacks.

Why: the test names the behavior a caller sees, so a refactor of the concern does not break it (Fizzy: `test/models/card/closeable_test.rb`).

### Assert changes with from and to

```ruby
# test/models/notification_test.rb
class NotificationTest < ActiveSupport::TestCase
# ...
  test "read marks notification as read" do
    notification = notifications(:logo_assignment_kevin)
    notification.update!(read_at: nil, unread_count: 2)

    assert_changes -> { notification.reload.read? }, from: false, to: true do
      notification.read
    end

    assert_equal 0, notification.unread_count
  end
# ...
end
```

`assert_changes` checks that an expression moves from one value to another. Pass `reload` inside the lambda when the change is persisted.

Why: `from:` and `to:` assert the starting value as well as the result (Fizzy: `test/models/notification_test.rb`).

### Assert enqueued jobs

```ruby
# test/models/notification/pushable_test.rb
class Notification::PushableTest < ActiveSupport::TestCase
# ...
  test "push_later enqueues Notification::PushJob" do
    assert_enqueued_with(job: Notification::PushJob, args: [ @notification ]) do
      @notification.push_later
    end
  end
# ...
end
```

`assert_enqueued_with job:, args:` proves that a model method enqueued a job with the expected arguments, without running it.

Why: the model test checks the enqueue and the job test checks the work (Fizzy: `test/models/notification/pushable_test.rb`).

## Fixtures

### YAML format with labels

```yaml
# test/fixtures/cards.yml
logo:
  id: <%= ActiveRecord::FixtureSet.identify("logo", :uuid) %>
  number: 1
  board: writebook_uuid
  creator: david_uuid
  column: writebook_triage_uuid
  title: The logo isn't big enough
  due_on: <%= 3.days.from_now %>
  created_at: <%= 1.week.ago %>
  status: published
  last_active_at: <%= 1.week.ago %>
```

**Key patterns:**
- ERB runs when the fixture loads.
- `ActiveRecord::FixtureSet.identify("logo", :uuid)` generates a deterministic UUID for the `id`.
- The label `logo:` becomes the fixture accessor `cards(:logo)`.
- Foreign keys use `<label>_uuid`: `board: writebook_uuid` points at `boards(:writebook)`.

Why: Fizzy's own `identify` override turns a label ending in `_uuid` into the same id the referenced fixture gets (Fizzy: `test/test_helper.rb`).

### UUID fixture ids

```ruby
# test/test_helper.rb
module FixturesTestHelper
# ...
  class_methods do
    def identify(label, column_type = :integer)
      if label.to_s.end_with?("_uuid")
        column_type = :uuid
        label = label.to_s.delete_suffix("_uuid")
      end

      # Rails passes :string for varchar columns, so handle both :uuid and :string
      return super(label, column_type) unless column_type.in?([ :uuid, :string ])
      generate_fixture_uuid(label)
    end
# ...
  end
end
```

For string primary keys the override returns a UUIDv7-based id whose timestamp is in the past, so fixtures sort older than records created during a test run.

Why: ordering by id stays predictable (AGENTS.md: "generated to sort older than any runtime record").

### Fixture references

```yaml
# test/fixtures/closures.yml
shipping:
  id: <%= ActiveRecord::FixtureSet.identify("shipping_closure", :uuid) %>
  account: 37s_uuid
  card: shipping_uuid
  user: kevin_uuid
```

Reference another fixture by its label plus `_uuid` (`card: shipping_uuid`, `user: kevin_uuid`), and the account the same way (`account: 37s_uuid`).

Why: labels are readable and survive id changes (Fizzy: `test/fixtures/closures.yml`).

## Test Database Setup

### Test helper

```ruby
# test/test_helper.rb
module ActiveSupport
  class TestCase
    parallelize workers: :number_of_processors, work_stealing: ENV["WORK_STEALING"] != "false"
# ...
    fixtures :all
# ...
    include ActiveJob::TestHelper
    include ActionTextTestHelper, CachingTestHelper, CardTestHelper, ChangeTestHelper, DnsTestHelper,
      SearchIndexTestHelper, SessionTestHelper
    include Turbo::Broadcastable::TestHelper
# ...
  end
end
```

`parallelize` runs test processes in parallel (`work_stealing` can be turned off with `WORK_STEALING=false`), and `fixtures :all` loads every fixture file. Helper modules are included once for all tests.

In the same file, `setup` puts the fixture account in `Current`, and `teardown` calls `Current.clear_all`. The `perform_enqueued_jobs` override clears `Current.account` while jobs run, so a job that depends on a leaked account fails in the test instead of in production. multi-tenancy.md ("Testing Tenancy") shows that excerpt.

Why: jobs carry their own account through `AccountTenanted` (Fizzy: the comment in `test/test_helper.rb`: "Jobs must carry their own account context").

## Test Helpers

### Session test helper

```ruby
# test/test_helpers/session_test_helper.rb
module SessionTestHelper
# ...
  def sign_in_as(identity)
# ...
    identity.send_magic_link
    magic_link = identity.magic_links.order(id: :desc).first

    untenanted do
      post session_path, params: { email_address: identity.email_address }
      post session_magic_link_url, params: { code: magic_link.code }
    end
# ...
  end
# ...
end
```

`sign_in_as` takes an identity label, an `Identity` or a `User`. It signs in through the real magic-link flow (`post session_path`, then `post session_magic_link_url` with the code), inside `untenanted` so the request has no account prefix. System tests use their own `sign_in_as` in `test/application_system_test_case.rb`.

Why: the same code path as production proves sign-in, and every integration test gets a real session cookie (Fizzy: `test/test_helpers/session_test_helper.rb`).

### Card test helper

```ruby
# test/test_helpers/card_test_helper.rb
module CardTestHelper
  def assert_card_container_rerendered(card)
    assert_turbo_stream action: :replace, target: dom_id(card, :card_container)
  end
end
```

A domain assertion wraps `assert_turbo_stream`, which comes from turbo-rails. `ChangeTestHelper#capture_change` is another small helper in the same directory.

Why: a named assertion keeps controller tests short and consistent (Fizzy: `test/test_helpers/card_test_helper.rb`).

## Running Tests

```ruby
# config/ci.rb
OSS_ENV = "SAAS=false BUNDLE_GEMFILE=Gemfile"
SAAS_ENV = "SAAS=true BUNDLE_GEMFILE=Gemfile.saas"
SYSTEM_TEST_ENV = "PARALLEL_WORKERS=1" # system tests can't run reliably in parallel
# ...
    step "Tests: SQLite",        "#{OSS_ENV} bin/rails test"
    step "Tests: SQLite System", "#{OSS_ENV} #{SYSTEM_TEST_ENV} bin/rails test:system"
```

`bin/rails test` runs the unit and integration tests. `bin/rails test:system` runs the system tests, which CI runs with `PARALLEL_WORKERS=1`. `bin/ci` runs the whole pipeline: setup, RuboCop, bundler-audit, importmap audit, Brakeman, gitleaks and the test suites.

Why: system tests cannot run reliably in parallel (Fizzy: the comment in `config/ci.rb`: "system tests can't run reliably in parallel").

## Sources

- Fizzy: `test/test_helper.rb`, `test/models/card/closeable_test.rb`, `test/models/notification_test.rb`, `test/models/notification/pushable_test.rb`
- Fizzy: `test/test_helpers/session_test_helper.rb`, `test/test_helpers/card_test_helper.rb`
- Fizzy: `test/fixtures/cards.yml`, `test/fixtures/closures.yml`, `config/ci.rb`, `docs/development.md`
- Fizzy: `AGENTS.md` ("UUID primary keys")
