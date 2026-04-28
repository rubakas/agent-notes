---
name: rails-testing-models
description: "Rails testing: model tests for associations, validations, scopes, callbacks, and methods"
group: rails
---

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
