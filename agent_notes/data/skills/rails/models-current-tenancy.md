# Current Attributes and Account Scoping

## Contents

- [Current Attributes](#current-attributes)
- [Setting and clearing Current](#setting-and-clearing-current)
- [Defaults via Current](#defaults-via-current)
- [Account-scoped associations](#account-scoped-associations)
- [Global records (exceptions)](#global-records-exceptions)
- [Sources](#sources)

## Current Attributes

`Current` is an `ActiveSupport::CurrentAttributes` class that holds the per-request context: the session, user, identity and account, plus request metadata. Setting `session` also sets `identity`, and setting `identity` looks up the `User` of that identity in the current account.

Tenancy: see multi-tenancy.md for the `Current` class excerpt, the `AccountSlug::Extractor` middleware, `with_account` and `without_account`, `AccountTenanted` jobs and the test setup.

## Setting and clearing Current

Three things set `Current` for a request. The `AccountSlug::Extractor` middleware sets the account (see multi-tenancy.md). The `Authentication` concern sets the session:

```ruby
# app/controllers/concerns/authentication.rb
def set_current_session(session)
  Current.session = session
  cookies.signed.permanent[:session_token] = { value: session.signed_id, httponly: true, same_site: :lax }
end
```

The `CurrentRequest` concern copies the request's method, id, user agent, IP and referrer into `Current` in a `before_action`.

In tests, the global setup sets the account and the global teardown clears everything; that excerpt is in multi-tenancy.md. Add `Current.session = sessions(:david)` in a test that needs a signed-in user, as `test/models/card/closeable_test.rb` does.

Why: `Current` is reset between requests by Rails, and tests must reset it themselves so state does not leak between them (Fizzy: `test/test_helper.rb`).

## Defaults via Current

```ruby
# app/models/comment.rb
belongs_to :account, default: -> { card.account }
belongs_to :card, touch: true
belongs_to :creator, class_name: "User", default: -> { Current.user }
```

Defaults are lambdas that read a parent association or `Current`. `Card::Closeable#close(user: Current.user)` uses the same default for a method argument.

Why: a web request always has a current user, so call sites need not pass it (Fizzy: `app/models/comment.rb`).

## Account-scoped associations

Domain records carry an `account_id` and default it from a parent. Queries go through relationships that are already scoped:

```ruby
# app/controllers/concerns/card_scoped.rb
@card = Current.user.accessible_cards.find_by!(number: params[:card_id])
```

`Current.user.accessible_cards` is a `has_many :accessible_cards, through: :boards` on `User::Accessor`. Fizzy defines no `default_scope`; scoping is explicit.

Why: going through `Current.user`'s relationships keeps the tenant and access rules visible at each query (Fizzy: `app/models/user/accessor.rb`).

## Global records (exceptions)

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

## Sources

- Fizzy: `app/models/current.rb`, `app/controllers/concerns/authentication.rb`, `app/controllers/concerns/current_request.rb`, `app/controllers/concerns/card_scoped.rb`
- Fizzy: `app/models/identity.rb`, `app/models/user.rb`, `app/models/user/accessor.rb`, `app/models/comment.rb`
- Fizzy: `test/test_helper.rb`
- AGENTS.md "Multi-tenancy is URL-based"
