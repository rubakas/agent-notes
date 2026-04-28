---
name: rails-testing-controllers
description: "Rails testing: controller tests, system tests, and integration tests"
group: rails
---

# Testing Controllers & Integration

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
