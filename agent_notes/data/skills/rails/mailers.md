# Action Mailer

## Contents

- [Philosophy](#philosophy)
- [File Structure](#file-structure)
- [Application Mailer](#application-mailer)
- [Simple Mailer](#simple-mailer)
- [Templates](#templates)
- [Mailer Layout](#mailer-layout)
- [Sending Emails](#sending-emails)
- [Mailer Previews](#mailer-previews)
- [Testing Mailers](#testing-mailers)
- [Sources](#sources)

## Philosophy

1. **Thin mailers**: a mailer method assigns instance variables and calls `mail`. The data comes from a model passed in (`magic_link`, `export`, `bundle`).
2. **Async delivery**: model code calls `deliver_later`.
3. **HTML and text**: each mail has an `.html.erb` and a `.text.erb` template.
4. **Previews**: `test/mailers/previews/` holds previews for the mailers.
5. **Environment-aware sender**: the `from` address reads `MAILER_FROM_ADDRESS`.

Why: a mailer that takes a model and formats it, as `MagicLinkMailer` does with a `MagicLink`, leaves the logic on the model (Fizzy: `app/mailers/magic_link_mailer.rb`).

## File Structure

```
app/mailers/
├── application_mailer.rb
├── account_mailer.rb
├── export_mailer.rb
├── import_mailer.rb
├── magic_link_mailer.rb
├── user_mailer.rb
├── notification/
│   └── bundle_mailer.rb
└── concerns/
    └── mailers/
        └── unsubscribable.rb

app/views/
├── layouts/
│   ├── mailer.html.erb
│   └── mailer.text.erb
└── mailers/
    ├── magic_link_mailer/
    │   ├── sign_in_instructions.html.erb
    │   └── sign_in_instructions.text.erb
    ├── export_mailer/
    ├── notification/bundle_mailer/
    └── ...
```

Mail templates live under `app/views/mailers/<mailer_name>/`, and the layouts live in `app/views/layouts/`.

Why: `ApplicationMailer` adds `app/views/mailers` to the view path, which keeps mail templates apart from the web views (Fizzy: `app/mailers/application_mailer.rb`).

## Application Mailer

```ruby
# app/mailers/application_mailer.rb
class ApplicationMailer < ActionMailer::Base
  default from: ENV.fetch("MAILER_FROM_ADDRESS", "Fizzy <support@fizzy.do>")

  layout "mailer"
  append_view_path Rails.root.join("app/views/mailers")
  helper AvatarsHelper, HtmlHelper

  private
    def default_url_options
      if Current.account
        super.merge(script_name: Current.account.slug)
      else
        super
      end
    end
end
```

- `default from:` reads `MAILER_FROM_ADDRESS` and falls back to a support address.
- `append_view_path` points mailers at `app/views/mailers`.
- `helper AvatarsHelper, HtmlHelper` makes view helpers available in mail templates.
- `default_url_options` adds `script_name: Current.account.slug` when an account is current, so URLs in the mail carry the account prefix.

Shared mailer behavior goes in a concern. `Mailers::Unsubscribable` adds the one-click unsubscribe headers after the action runs:

```ruby
# app/mailers/concerns/mailers/unsubscribable.rb
module Mailers::Unsubscribable
  extend ActiveSupport::Concern

  included do
    after_action :set_unsubscribe_headers
  end

  def set_unsubscribe_headers
    headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    headers["List-Unsubscribe"]      = "<#{notifications_unsubscribe_url(access_token: @unsubscribe_token)}>"
  end
end
```

`Notification::BundleMailer` includes it.

Why: URL helpers in a mail have no request, so the mailer supplies the account prefix itself (Fizzy: `app/mailers/application_mailer.rb`).

## Simple Mailer

```ruby
# app/mailers/magic_link_mailer.rb
class MagicLinkMailer < ApplicationMailer
  def sign_in_instructions(magic_link)
    @magic_link = magic_link
    @identity = @magic_link.identity

    mail to: @identity.email_address, subject: "Your Fizzy code is #{ @magic_link.code }"
  end
end
```

The mailer takes a `magic_link`, reads its identity, and sends the code in the subject and body. `mail` returns a message object. `deliver_now` sends it immediately and `deliver_later` enqueues it.

Why: the mailer formats, and the model made the `magic_link` and its code (Fizzy: `app/mailers/magic_link_mailer.rb`).

## Templates

Provide both formats. The HTML template:

```erb
<%# app/views/mailers/magic_link_mailer/sign_in_instructions.html.erb %>
<% if @magic_link.for_sign_in? %>
  <h1 class="title">Fizzy verification code</h1>
  <p class="subtitle">Please enter this 6-character verification code on the Fizzy sign-in page:</p>
<% else %>
  <h1 class="title">Welcome to Fizzy!</h1>
  <p class="subtitle">Please enter this 6-character verification code to finish creating your account:</p>
<% end %>

<strong class="txt-large"><%= @magic_link.code %></strong>

<p>This code will work for <%= distance_of_time_in_words(MagicLink::EXPIRATION_TIME) %>.</p>
```

and the text template:

```erb
<%# app/views/mailers/magic_link_mailer/sign_in_instructions.text.erb %>
<% if @magic_link.for_sign_in? %>
Please enter this 6-character verification code on the Fizzy sign-in page:
<% else %>
Please enter this 6-character verification code to finish creating your account:
<% end %>

<%= @magic_link.code %>

This code will work for <%= distance_of_time_in_words(MagicLink::EXPIRATION_TIME) %>.
```

Both show `@magic_link.code`, which the user types into the sign-in page, instead of a link.

Why: mail clients that cannot render HTML show the text part (Fizzy: `app/views/mailers/magic_link_mailer/`).

## Mailer Layout

The HTML layout wraps the message in a document with inline styles. The text layout only yields:

```erb
<%# app/views/layouts/mailer.html.erb %>
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <style>
<%# ... %>
    </style>
  </head>

  <body>
    <table id="body">
      <%= yield %>
    </table>
  </body>
</html>
```

```erb
<%# app/views/layouts/mailer.text.erb %>
<%= yield %>
```

Why: the CSS sits in the layout's `<style>` block, so every template shares one set of classes (Fizzy: `app/views/layouts/mailer.html.erb`).

## Sending Emails

Models call the mailer and `deliver_later`. `Identity#send_magic_link` creates the magic link and then enqueues the mail:

```ruby
# app/models/identity.rb
  def send_magic_link(**attributes)
    attributes[:purpose] = attributes.delete(:for) if attributes.key?(:for)

    magic_links.create!(attributes).tap do |magic_link|
      MagicLinkMailer.sign_in_instructions(magic_link).deliver_later
    end
  end
```

The delivery job needs the account, so `ActionMailer::MailDeliveryJob` is prepended with `AccountTenanted` when Action Mailer loads:

```ruby
# config/initializers/active_job.rb
ActiveSupport.on_load(:action_mailer) do
  ActionMailer::MailDeliveryJob.prepend AccountTenanted
end
```

SMTP error handling is added to the same job in a separate `to_prepare` hook (see the `jobs.md` reference).

Why: the job restores the account that enqueued the mail, so the URLs it builds are correct (Fizzy: `config/initializers/active_job.rb`).

## Mailer Previews

Previews display emails in development at `/rails/mailers`:

```ruby
# test/mailers/previews/magic_link_mailer_preview.rb
class MagicLinkMailerPreview < ActionMailer::Preview
  def magic_link
    identity = Identity.all.sample
    magic_link = MagicLink.new(identity: identity)
    magic_link.valid?

    MagicLinkMailer.sign_in_instructions(magic_link)
  end
end
```

A preview builds the arguments the mailer needs without sending anything. This one builds an unsaved `MagicLink` for a random identity.

Why: a preview shows the rendered mail without delivering one (Fizzy: `test/mailers/previews/magic_link_mailer_preview.rb`).

## Testing Mailers

```ruby
# test/mailers/export_mailer_test.rb
class ExportMailerTest < ActionMailer::TestCase
  test "completed for account export" do
    export = Account::Export.create!(account: Current.account, user: users(:david))
    email = ExportMailer.completed(export)

    assert_emails 1 do
      email.deliver_now
    end

    assert_equal [ "david@37signals.com" ], email.to
    assert_equal "Your Fizzy data export is ready for download", email.subject
    assert_match %r{/exports/#{export.id}}, email.body.encoded
  end
# ...
end
```

Inherit from `ActionMailer::TestCase`. Build the message, deliver it inside `assert_emails 1`, then assert on `email.to`, `email.subject` and `email.body.encoded`. The `testing-system-jobs-mailers.md` reference covers the SMTP error tests.

Why: the test checks what a recipient sees: the address, the subject and the link (Fizzy: `test/mailers/export_mailer_test.rb`).

## Sources

- Fizzy: `app/mailers/application_mailer.rb`, `app/mailers/magic_link_mailer.rb`, `app/mailers/concerns/mailers/unsubscribable.rb`, `app/mailers/notification/bundle_mailer.rb`
- Fizzy: `app/views/mailers/magic_link_mailer/`, `app/views/layouts/mailer.html.erb`, `app/views/layouts/mailer.text.erb`
- Fizzy: `app/models/identity.rb`, `config/initializers/active_job.rb`
- Fizzy: `test/mailers/export_mailer_test.rb`, `test/mailers/previews/magic_link_mailer_preview.rb`
