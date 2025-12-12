# Migrations Guide

Comprehensive guide for Rails database migrations.

---

## File Structure

```
db/migrate/
├── 20250101120000_create_cards.rb
├── 20250102130000_add_status_to_cards.rb
└── 20250103140000_create_index_on_cards_board_id.rb
```

---

## Basic Migration Patterns

### Create Table

```ruby
class CreateCards < ActiveRecord::Migration[8.0]
  def change
    create_table :cards, id: :uuid do |t|
      t.uuid :account_id, null: false
      t.uuid :board_id, null: false
      t.uuid :creator_id, null: false

      t.integer :number, null: false
      t.string :title
      t.text :description
      t.string :status, default: "draft", null: false
      t.string :color

      t.timestamps

      t.index ["account_id", "number"], unique: true
      t.index ["board_id"]
      t.index ["creator_id"]
      t.index ["status"]
    end
  end
end
```

### Add Column

```ruby
class AddPublishedAtToCards < ActiveRecord::Migration[8.0]
  def change
    add_column :cards, :published_at, :datetime
    add_index :cards, :published_at
  end
end
```

### Remove Column

```ruby
class RemoveDeprecatedFieldFromCards < ActiveRecord::Migration[8.0]
  def change
    remove_column :cards, :deprecated_field, :string
  end
end
```

### Change Column

```ruby
class ChangeCardsTitleToText < ActiveRecord::Migration[8.0]
  def change
    change_column :cards, :title, :text
  end
end

# Or with up/down for safety
class ChangeCardsTitleToText < ActiveRecord::Migration[8.0]
  def up
    change_column :cards, :title, :text
  end

  def down
    change_column :cards, :title, :string
  end
end
```

### Rename Column

```ruby
class RenameCardsDescToDescription < ActiveRecord::Migration[8.0]
  def change
    rename_column :cards, :desc, :description
  end
end
```

---

## Index Patterns

### Single Column Index

```ruby
add_index :cards, :board_id
add_index :cards, :status
```

### Composite Index

```ruby
add_index :cards, [:account_id, :number], unique: true
add_index :cards, [:board_id, :status]
```

### Named Index

```ruby
add_index :cards, :email, unique: true, name: "idx_cards_on_email"
```

### Partial Index (PostgreSQL)

```ruby
add_index :cards, :published_at, where: "status = 'published'"
```

### Remove Index

```ruby
remove_index :cards, :board_id
remove_index :cards, name: "idx_cards_on_email"
```

---

## Foreign Keys

```ruby
class AddForeignKeys < ActiveRecord::Migration[8.0]
  def change
    add_foreign_key :cards, :boards
    add_foreign_key :cards, :accounts
    add_foreign_key :cards, :users, column: :creator_id
  end
end
```

---

## Data Migrations

### Backfill Data

```ruby
class BackfillCardNumbers < ActiveRecord::Migration[8.0]
  def up
    Card.where(number: nil).find_each do |card|
      card.update!(number: card.account.increment!(:cards_count).cards_count)
    end
  end

  def down
    # Usually no rollback for data migrations
  end
end
```

---

## UUID Primary Keys

```ruby
class EnableUuidExtension < ActiveRecord::Migration[8.0]
  def change
    enable_extension "pgcrypto"  # PostgreSQL
  end
end

class CreateCardsWithUuid < ActiveRecord::Migration[8.0]
  def change
    create_table :cards, id: :uuid do |t|
      t.uuid :account_id, null: false
      t.timestamps
    end
  end
end
```

---

## Reversible Migrations

```ruby
class AddCheckConstraint < ActiveRecord::Migration[8.0]
  def change
    reversible do |dir|
      dir.up do
        execute <<-SQL
          ALTER TABLE cards
          ADD CONSTRAINT check_positive_number
          CHECK (number > 0)
        SQL
      end

      dir.down do
        execute <<-SQL
          ALTER TABLE cards
          DROP CONSTRAINT check_positive_number
        SQL
      end
    end
  end
end
```

---

## Best Practices

### ✅ DO

1. **Add indexes for foreign keys**
```ruby
t.uuid :board_id, null: false
t.index [:board_id]
```

2. **Use null constraints**
```ruby
t.string :title, null: false
```

3. **Add default values**
```ruby
t.string :status, default: "draft", null: false
```

4. **Use change when possible**
```ruby
def change
  add_column :cards, :color, :string
end
```

### ❌ DON'T

1. **Modify old migrations** - Create new ones
2. **Remove columns in production without deprecation**
3. **Change column types without considering data loss**

---

## Summary

- **Versioned**: Each migration is timestamped
- **Reversible**: Use `change` when possible
- **Indexes**: Add for foreign keys and frequently queried columns
- **Constraints**: Use null, default, unique appropriately
- **Data Migrations**: Separate from schema migrations
- **UUID Keys**: Use for distributed systems
