# Testing Controllers and Integrations

## Contents

- [CRUD Controller Tests](#crud-controller-tests)
- [Testing Permissions](#testing-permissions)
- [Response Formats](#response-formats)
- [Integration Tests](#integration-tests)
- [Sources](#sources)

## CRUD Controller Tests

### One test per action

Fizzy controller tests inherit from `ActionDispatch::IntegrationTest`. They send real requests through the routes with path helpers (`get board_path(...)`), and assert on the response, the redirect and the changed records. They do not use the Rails functional-test style that names an action by symbol and reads controller instance variables.

```ruby
# test/controllers/boards_controller_test.rb
class BoardsControllerTest < ActionDispatch::IntegrationTest
  setup do
    sign_in_as :kevin
  end
# ...
  test "create" do
    assert_difference -> { Board.count }, +1 do
      post boards_path, params: { board: { name: "Remodel Punch List" } }
    end

    board = Board.last
    assert_redirected_to board_path(board)
    assert_includes board.users, users(:kevin)
    assert_equal "Remodel Punch List", board.name
  end
# ...
end
```

- `sign_in_as :kevin` signs in an identity from the fixtures (see the `testing-models-fixtures.md` reference).
- One test per action, named after it: `"new"`, `"show"`, `"create"`, `"edit"`, `"update"`, `"destroy"`.
- Assert the redirect, then the changed records. `Board.last` works because fixture ids sort older than runtime ids.
- Every integration test carries the account's URL prefix, which `test/test_helper.rb` adds once:

```ruby
# test/test_helper.rb
class ActionDispatch::IntegrationTest
  setup do
    integration_session.default_url_options = integration_session.default_url_options.merge(script_name: "/#{ActiveRecord::FixtureSet.identify("37signals")}")
  end
# ...
end
```

Why: a failing test names the action, and path helpers exercise the same routes a client uses (Fizzy: `test/controllers/boards_controller_test.rb`).

### JSON requests and responses

```ruby
# test/controllers/boards_controller_test.rb
  test "create as JSON" do
    assert_difference -> { Board.count }, +1 do
      post boards_path, params: { board: { name: "My new board" } }, as: :json
    end

    assert_response :created
    assert_equal board_path(Board.last, format: :json), @response.headers["Location"]
    assert_equal "My new board", @response.parsed_body["name"]
  end
```

Pass `as: :json` to send and accept JSON. Read the body with `@response.parsed_body`, and check headers such as `Location` on `@response.headers`. A JSON `destroy` returns `:no_content`.

Why: `as: :json` sets the request and accept headers for the JSON format (Fizzy: `test/controllers/boards_controller_test.rb`).

### Turbo Stream requests

```ruby
# test/controllers/cards/closures_controller_test.rb
  test "create" do
    card = cards(:logo)

    assert_changes -> { card.reload.closed? }, from: false, to: true do
      post card_closure_path(card), as: :turbo_stream
      assert_card_container_rerendered(card)
    end
  end
```

Pass `as: :turbo_stream` to request the stream format, then assert on the result. `assert_card_container_rerendered` is a helper from `test/test_helpers/card_test_helper.rb`.

Why: the test fails if the action renders the wrong format or forgets the stream (Fizzy: `test/controllers/cards/closures_controller_test.rb`).

## Testing Permissions

### Forbidden response

```ruby
# test/controllers/boards_controller_test.rb
  test "non-admin cannot change all_access on board they don't own" do
    logout_and_sign_in_as :jz

    board = boards(:writebook)
    original_all_access = board.all_access

    patch board_path(board), params: { board: { all_access: !original_all_access } }

    assert_response :forbidden
    assert_equal original_all_access, board.reload.all_access
  end
```

Sign in as a user without the permission, send the request, then assert the status and that the record did not change. `assert_response :forbidden` appears 46 times in Fizzy's tests.

Why: the test proves the guard blocks the change, not just that the page renders (Fizzy: `app/controllers/boards_controller.rb`).

### Not found for inaccessible records

```ruby
# test/controllers/cards_controller_test.rb
  test "users can only see cards in boards they have access to" do
    get card_path(cards(:logo))
    assert_response :success

    boards(:writebook).update! all_access: false
    boards(:writebook).accesses.revoke_from users(:kevin)

    get card_path(cards(:logo))
    assert_response :not_found
  end
```

Lookups are scoped through the user, so a card on a board the user lost access to is not found. The test removes the access in the middle of the test and checks the second request.

Why: the scoped lookup raises `RecordNotFound`, which Rails renders as 404 (Fizzy: `app/controllers/concerns/card_scoped.rb`).

### Switching users

```ruby
# test/test_helpers/session_test_helper.rb
  def logout_and_sign_in_as(identity)
    Session.delete_all
    sign_in_as identity
  end
```

Use `logout_and_sign_in_as :jz` to change the signed-in user inside one test. It deletes every session, then signs in again.

Why: with all earlier sessions gone, the next request can only authenticate as the new user (Fizzy: `test/test_helpers/session_test_helper.rb`).

## Response Formats

### Assert Turbo Stream changes

`assert_turbo_stream action:, target:` checks that the response contains a turbo-stream tag with that action and target. It comes from turbo-rails, and Fizzy wraps it in a named helper:

```ruby
# test/test_helpers/card_test_helper.rb
module CardTestHelper
  def assert_card_container_rerendered(card)
    assert_turbo_stream action: :replace, target: dom_id(card, :card_container)
  end
end
```

Why: the helper names the intent, and the closure tests call it with the card (Fizzy: `test/test_helpers/card_test_helper.rb`).

### Assert broadcasts

```ruby
# test/controllers/cards/pins_controller_test.rb
class Cards::PinsControllerTest < ActionDispatch::IntegrationTest
  setup do
    sign_in_as :kevin
  end
# ...
  test "create" do
    assert_changes -> { cards(:layout).pinned_by?(users(:kevin)) }, from: false, to: true do
      perform_enqueued_jobs do
        assert_turbo_stream_broadcasts([ users(:kevin), :pins_tray ], count: 1) do
          post card_pin_path(cards(:layout)), as: :turbo_stream
        end
      end
    end

    assert_response :success
  end
# ...
end
```

`assert_turbo_stream_broadcasts` takes a stream name (`[ users(:kevin), :pins_tray ]`) and a `count:`, and wraps the request. The broadcast runs in a job, so the request sits inside `perform_enqueued_jobs`. `test/test_helper.rb` includes `Turbo::Broadcastable::TestHelper`.

Why: a broadcast is a side effect the response does not show (Fizzy: `test/controllers/cards/pins_controller_test.rb`).

### JSON response parsing

```ruby
# test/controllers/boards_controller_test.rb
  test "index as JSON" do
    get boards_path, as: :json
    assert_response :success
    assert_equal users(:kevin).boards.count, @response.parsed_body.count
  end
```

`@response.parsed_body` parses a JSON response, so `JSON.parse(response.body)` is not needed.

Why: the helper picks the parser from the response's content type (Rails: `ActionDispatch::TestResponse#parsed_body`).

## Integration Tests

Tests under `test/integration/` also inherit from `ActionDispatch::IntegrationTest`. They cover behavior that cuts across controllers, such as authorization of Active Storage blobs, and they can use another credential than the session cookie. This one authenticates with a bearer token:

```ruby
# test/integration/active_storage_authorization_test.rb
class ActiveStorageAuthorizationTest < ActionDispatch::IntegrationTest
# ...
  test "bearer token with board access can view blob" do
    bearer_token = { "HTTP_AUTHORIZATION" => "Bearer #{identity_access_tokens(:davids_api_token).token}" }

    get rails_blob_path(@blob, disposition: :inline), env: bearer_token

    assert_response :redirect
    assert_match %r{rails/active_storage}, response.location
  end

# ...
end
```

Why: a cross-cutting rule is easiest to test at the request level (Fizzy: `test/integration/active_storage_authorization_test.rb`).

## Sources

- Fizzy: `test/controllers/boards_controller_test.rb`, `test/controllers/cards_controller_test.rb`, `test/controllers/cards/closures_controller_test.rb`, `test/controllers/cards/pins_controller_test.rb`
- Fizzy: `test/integration/active_storage_authorization_test.rb`, `test/test_helper.rb`, `test/test_helpers/session_test_helper.rb`, `test/test_helpers/card_test_helper.rb`
- Rails: `ActionDispatch::IntegrationTest`, `ActionDispatch::TestResponse#parsed_body`
