# Current Attributes, Multi-Tenancy, and Keys

## Contents

- [Current Attributes](#current-attributes)
- [Multi-Tenancy via URL](#multi-tenancy-via-url)
- [UUID Primary Keys (Fizzy-Specific)](#uuid-primary-keys-fizzy-specific)
- [Delegated Types](#delegated-types)
- [Sources](#sources)

## Current Attributes

`Current` is an `ActiveSupport::CurrentAttributes` class that holds the per-request context: the session, user, identity and account, plus request metadata.

```ruby
# app/models/current.rb
class Current < ActiveSupport::CurrentAttributes
  attribute :session, :user, :identity, :account
# ...
  def identity=(identity)
    super(identity)

    if identity.present?
      self.user = identity.users.find_by(account: account)
    end
  end
# ...
  def with_account(value, &)
    with(account: value, &)
  end
# ...
end
```

Setting `session` also sets `identity`, and setting `identity` looks up the `User` of that identity in the current account. `with_account` (and its counterpart `without_account`) runs a block under a given tenant.

Why: the identity-to-user step lives in one place, so `Current.user` always matches `Current.account` (Fizzy: `app/models/current.rb`).

### Setting and clearing Current

Three things set `Current` for a request. The `AccountSlug::Extractor` middleware sets the account (see Multi-Tenancy below). The `Authentication` concern sets the session:

```ruby
# app/controllers/concerns/authentication.rb
def set_current_session(session)
  Current.session = session
  cookies.signed.permanent[:session_token] = { value: session.signed_id, httponly: true, same_site: :lax }
end
```

The `CurrentRequest` concern copies the request's method, id, user agent, IP and referrer into `Current` in a `before_action`.

In tests, the global setup sets the account and the global teardown clears everything:

```ruby
# test/test_helper.rb
# Jobs must carry their own account context via AccountTenanted,
# not rely on Current.account leaking from the test setup.
def perform_enqueued_jobs(...)
  saved_account = Current.account
  Current.account = nil
  super
ensure
  Current.account = saved_account
end

setup do
  Current.account = accounts("37s")
end

teardown do
  Current.clear_all
end
```

Add `Current.session = sessions(:david)` in a test that needs a signed-in user, as `test/models/card/closeable_test.rb` does.

Why: `Current` is reset between requests by Rails, and tests must reset it themselves so state does not leak between them (Fizzy: `test/test_helper.rb`).

### Defaults via Current

```ruby
# app/models/comment.rb
belongs_to :account, default: -> { card.account }
belongs_to :card, touch: true
belongs_to :creator, class_name: "User", default: -> { Current.user }
```

Defaults are lambdas that read a parent association or `Current`. `Card::Closeable#close(user: Current.user)` uses the same default for a method argument.

Why: a web request always has a current user, so call sites need not pass it (Fizzy: `app/models/comment.rb`).

## Multi-Tenancy via URL

"Accounts get a decimal `external_account_id` URL prefix (`/{account_id}/boards/...`)." (AGENTS.md "Multi-tenancy is URL-based")

### Middleware extraction

`AccountSlug::Extractor` reads the prefix, moves it from `PATH_INFO` to `SCRIPT_NAME`, finds the `Account`, and runs the rest of the stack inside `Current.with_account`. Requests without a prefix run inside `Current.without_account`. It is inserted after `Rack::TempfileReaper`.

```ruby
# config/initializers/tenanting/account_slug.rb
        # Yanks the prefix off PATH_INFO and move it to SCRIPT_NAME
        request.engine_script_name = request.script_name = $1
        request.path_info   = $'.empty? ? "/" : $'
# ...
      if env["fizzy.external_account_id"]
        account = Account.find_by(external_account_id: env["fizzy.external_account_id"])
        Current.with_account(account) do
          @app.call env
        end
      else
        Current.without_account do
          @app.call env
        end
      end
    end
# ...
Rails.application.config.middleware.insert_after Rack::TempfileReaper, AccountSlug::Extractor
```

Why: the app is "mounted" at the prefix rather than namespacing every route, so route helpers and request tests behave as if it were mounted there (Fizzy: `config/initializers/tenanting/account_slug.rb`; AGENTS.md "Multi-tenancy is URL-based").

### Account-scoped associations

Domain records carry an `account_id` and default it from a parent. Queries go through relationships that are already scoped:

```ruby
# app/controllers/concerns/card_scoped.rb
@card = Current.user.accessible_cards.find_by!(number: params[:card_id])
```

`Current.user.accessible_cards` is a `has_many :accessible_cards, through: :boards` on `User::Accessor`. Fizzy defines no `default_scope`; scoping is explicit.

Why: going through `Current.user`'s relationships keeps the tenant and access rules visible at each query (Fizzy: `app/models/user/accessor.rb`).

### Global records (exceptions)

`Identity`, session and authentication records are not account-scoped. One `Identity` can have a `User` in several accounts:

```ruby
# app/models/identity.rb
has_many :access_tokens, dependent: :destroy
has_many :magic_links, dependent: :destroy
has_many :sessions, dependent: :destroy
has_many :users, dependent: :nullify
has_many :accounts, through: :users
```

```ruby
# app/models/user.rb
belongs_to :account
belongs_to :identity, optional: true
```

Why: "A global `Identity` (email-based) can hold `Users` in multiple accounts" (AGENTS.md "Multi-tenancy is URL-based")

### Jobs and Current

`AccountTenanted` is a module prepended into `ApplicationJob`. A job never sets `Current.account` by hand. At enqueue time the module records `Current.account` and adds the account's GlobalID to the serialized job data:

```ruby
# app/jobs/concerns/account_tenanted.rb
prepended do
  attr_reader :account
  around_perform :with_account_context
end

def initialize(...)
  super
  @account = Current.account
end

def serialize
  super.merge({ "account" => @account&.to_gid })
end
```

Before `perform` runs, `around_perform` resolves the account and wraps the job in `Current.with_account`. A missing account raises `ActiveJob::DeserializationError`, which `discard_on` can handle:

```ruby
# app/jobs/concerns/account_tenanted.rb
private
  def with_account_context(&block)
    resolve_account!

    if account.present?
      Current.with_account(account, &block)
    else
      yield
    end
  end
```

`ApplicationJob` prepends the module, and the initializer prepends it onto the framework jobs that Fizzy uses:

```ruby
# app/jobs/application_job.rb
class ApplicationJob < ActiveJob::Base
  prepend AccountTenanted
# ...
end
```

```ruby
# config/initializers/active_job.rb
ActiveSupport.on_load(:action_mailer) do
  ActionMailer::MailDeliveryJob.prepend AccountTenanted
end

Rails.application.config.after_initialize do
  Turbo::Streams::ActionBroadcastJob.prepend AccountTenanted
  Turbo::Streams::BroadcastJob.prepend AccountTenanted
  Turbo::Streams::BroadcastStreamJob.prepend AccountTenanted
end
```

A job therefore stays shallow: `Card::BroadcastPinUpdatesJob#perform(card)` is `card.broadcast_pin_updates`. See the `models-callbacks-jobs.md` reference.

Why: the account travels with the job, so a worker never needs ambient state (Fizzy: `app/jobs/concerns/account_tenanted.rb`; AGENTS.md "Multi-tenancy is URL-based").

## UUID Primary Keys (Fizzy-Specific)

"All tables use UUIDv7 keys, base36-encoded to 25 characters." (AGENTS.md "UUID primary keys") This is not a Rails default. Fizzy registers a custom `ActiveRecord::Type::Uuid`, stores it as `binary(16)` on MySQL and `blob(16)` on SQLite, and teaches the adapters and the table definition about a `:uuid` column type:

```ruby
# lib/rails_ext/active_record_uuid_type.rb
BASE36_LENGTH = 25 # 36^25 > 2^128
# ...
  def generate
    uuid = SecureRandom.uuid_v7
    hex = uuid.delete("-")
    hex_to_base36(hex)
  end
```

```ruby
# config/initializers/uuid_primary_keys.rb
  class_methods do
    def native_database_types
      @native_database_types_with_uuid ||= super.merge(uuid: { name: "binary", limit: 16 })
    end
  end
# ...
module TableDefinitionUuidSupport
  def uuid(name, **options)
    column(name, :uuid, **options)
  end
end
```

In migrations, declare the table with `id: :uuid` and foreign keys with `t.uuid`. The migration below says `Migration[8.2]` because Fizzy runs Rails from the `rails/rails` main branch; on released Rails 8.1 write `[8.1]`.

```ruby
# db/migrate/20260828120000_create_identity_transfers.rb
class CreateIdentityTransfers < ActiveRecord::Migration[8.2]
  def change
    create_table :identity_transfers, id: :uuid do |t|
      t.uuid :identity_id, null: false
      t.string :token, null: false

      t.timestamps

      t.index :identity_id
      t.index :token, unique: true
    end
  end
end
```

### Fixture UUIDs

Fixture ids are generated so that they sort older than any record created at runtime, which keeps `.first` and `.last` deterministic in tests. A fixture label ending in `_uuid` resolves to the same generated id:

```yaml
# test/fixtures/cards.yml
logo:
  id: <%= ActiveRecord::FixtureSet.identify("logo", :uuid) %>
  number: 1
  board: writebook_uuid
```

Why: ordering in tests stays stable without comparing insertion order to id order (AGENTS.md "UUID primary keys").

## Delegated Types

Fizzy does not use Rails' `delegated_type`. `Event`, `Reaction`, `Notification` and `Mention` use a plain `belongs_to ..., polymorphic: true`.

In the delegated-type pattern, a concrete "superclass" table holds the metadata every kind of record shares, and each kind keeps its own columns in its own table. The superclass row stores `<role>_type` and `<role>_id` and delegates to the concrete record. Compared with the two usual alternatives:

- Single-table inheritance puts every kind's columns in one table, so the table grows wider with each new kind and gets slower to migrate. Adding a kind to a delegated type is a new table, and the superclass table does not change.
- A plain polymorphic `belongs_to` lets many things point at one target, but it gives no shared table to query, paginate or hang common behaviour on. Basecamp still uses a polymorphic association for boosts, because a boost can target things that are not recordings.

Rails adds the helpers: `entry.message` (nil unless the entry is a message), `entry.message?`, `entry.entryable_name`, and a scope per type (`Entry.messages`).

```ruby
# Illustrative (not from Fizzy)
class Entry < ApplicationRecord
  belongs_to :account
  belongs_to :creator
  delegated_type :entryable, types: %w[ Message Comment ]
end

module Entryable
  extend ActiveSupport::Concern

  included do
    has_one :entry, as: :entryable, touch: true
  end
end

class Message < ApplicationRecord
  include Entryable
end

class Comment < ApplicationRecord
  include Entryable
end

Entry.create! entryable: Comment.new(content: "Hello!"), creator: Current.user, account: Current.account
Entry.messages.order(created_at: :desc).limit(50)
```

Why: the superclass table can be queried and paginated across every kind, which separate per-kind tables cannot do, and a new kind needs no change to it (37signals dev blog, "The Rails Delegated Type Pattern": https://dev.37signals.com/the-rails-delegated-type-pattern/; Rails API `ActiveRecord::DelegatedType`).

## Sources

- Fizzy: `app/models/current.rb`, `app/controllers/concerns/authentication.rb`, `app/controllers/concerns/current_request.rb`, `app/controllers/concerns/card_scoped.rb`
- Fizzy: `app/jobs/concerns/account_tenanted.rb`, `app/jobs/application_job.rb`, `config/initializers/active_job.rb`
- Fizzy: `config/initializers/tenanting/account_slug.rb`, `config/initializers/uuid_primary_keys.rb`, `lib/rails_ext/active_record_uuid_type.rb`
- Fizzy: `app/models/identity.rb`, `app/models/user.rb`, `app/models/user/accessor.rb`, `app/models/comment.rb`
- Fizzy: `test/test_helper.rb`, `test/fixtures/cards.yml`, `db/migrate/20260828120000_create_identity_transfers.rb`
- AGENTS.md "Multi-tenancy is URL-based", "UUID primary keys"
- Fizzy: `app/models/event.rb`, `app/models/reaction.rb`, `app/models/notification.rb`, `app/models/mention.rb`
- 37signals dev blog, "The Rails Delegated Type Pattern": https://dev.37signals.com/the-rails-delegated-type-pattern/
- Rails API `ActiveRecord::DelegatedType` (activerecord 8.1.3, `lib/active_record/delegated_type.rb`)
