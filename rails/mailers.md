# Mailers Guide

Comprehensive guide for Rails Action Mailer.

---

## Philosophy

1. **Mailers are like controllers** - Thin, delegate to models
2. **Preview mailers in development** - Use mailer previews
3. **Test email delivery** - Test content, not delivery mechanism
4. **Layouts for consistency** - DRY up email HTML
5. **Plain text + HTML** - Always provide both formats

---

## File Structure

```
app/mailers/
├── application_mailer.rb
├── user_mailer.rb
├── notification_mailer.rb
└── magic_link_mailer.rb

app/views/
├── layouts/
│   └── mailer.html.erb
└── user_mailer/
    ├── welcome.html.erb
    └── welcome.text.erb
```

---

## Basic Mailer

### Application Mailer

```ruby
# app/mailers/application_mailer.rb
class ApplicationMailer < ActionMailer::Base
  default from: ENV.fetch("MAILER_FROM_ADDRESS", "App <noreply@example.com>")

  layout "mailer"

  helper ApplicationHelper, UsersHelper

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

### Simple Mailer

```ruby
# app/mailers/user_mailer.rb
class UserMailer < ApplicationMailer
  def welcome(user)
    @user = user
    @login_url = new_session_url

    mail to: @user.email, subject: "Welcome to #{app_name}!"
  end

  def password_reset(user, token)
    @user = user
    @token = token
    @reset_url = edit_password_url(token: @token)

    mail to: @user.email, subject: "Reset your password"
  end

  private
    def app_name
      "My App"
    end
end
```

---

## Templates

### HTML Template

```erb
<%# app/views/user_mailer/welcome.html.erb %>

<h1>Welcome, <%= @user.name %>!</h1>

<p>Thanks for signing up. We're excited to have you on board.</p>

<p>
  <%= link_to "Get Started", @login_url, class: "button" %>
</p>

<p>
  If you have any questions, just reply to this email.
</p>

<p>
  Thanks,<br>
  The Team
</p>
```

### Plain Text Template

```erb
<%# app/views/user_mailer/welcome.text.erb %>

Welcome, <%= @user.name %>!

Thanks for signing up. We're excited to have you on board.

Get started: <%= @login_url %>

If you have any questions, just reply to this email.

Thanks,
The Team
```

### Mailer Layout

```erb
<%# app/views/layouts/mailer.html.erb %>

<!DOCTYPE html>
<html>
  <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <style>
      body { font-family: Arial, sans-serif; line-height: 1.6; }
      .button { background: #007bff; color: white; padding: 10px 20px; text-decoration: none; }
    </style>
  </head>
  <body>
    <%= yield %>

    <hr>
    <p style="font-size: 12px; color: #666;">
      You're receiving this email because you have an account at My App.
    </p>
  </body>
</html>
```

---

## Mailer Methods

### With Attachments

```ruby
def invoice(user, invoice)
  @user = user
  @invoice = invoice

  attachments["invoice-#{@invoice.id}.pdf"] = @invoice.to_pdf
  attachments.inline["logo.png"] = File.read(Rails.root.join("app/assets/images/logo.png"))

  mail to: @user.email, subject: "Invoice ##{@invoice.id}"
end
```

### With CC/BCC

```ruby
def notification(user, admin)
  @user = user

  mail(
    to: @user.email,
    cc: admin.email,
    bcc: "notifications@example.com",
    subject: "Important Update"
  )
end
```

### With Custom Headers

```ruby
def custom_email(user)
  @user = user

  headers["X-Priority"] = "1"
  headers["X-Mailer"] = "MyApp Mailer"

  mail to: @user.email, subject: "Custom Email"
end
```

---

## Sending Emails

### Immediate Delivery

```ruby
# Sends immediately
UserMailer.welcome(user).deliver_now
```

### Background Delivery

```ruby
# Enqueues job
UserMailer.welcome(user).deliver_later

# With delay
UserMailer.welcome(user).deliver_later(wait: 1.hour)

# At specific time
UserMailer.welcome(user).deliver_later(wait_until: Time.current + 2.hours)
```

### From Models

```ruby
class User < ApplicationRecord
  after_create :send_welcome_email

  private
    def send_welcome_email
      UserMailer.welcome(self).deliver_later
    end
end
```

---

## Mailer Previews

### Preview Class

```ruby
# test/mailers/previews/user_mailer_preview.rb
class UserMailerPreview < ActionMailer::Preview
  def welcome
    UserMailer.welcome(User.first)
  end

  def password_reset
    user = User.first
    token = "sample-token-123"
    UserMailer.password_reset(user, token)
  end
end

# Visit: http://localhost:3000/rails/mailers
```

---

## Testing Mailers

### Basic Mailer Test

```ruby
class UserMailerTest < ActionMailer::TestCase
  test "welcome email" do
    user = users(:david)

    email = UserMailer.welcome(user)

    assert_emails 1 do
      email.deliver_now
    end

    assert_equal [user.email], email.to
    assert_equal "Welcome to My App!", email.subject
    assert_match user.name, email.body.encoded
    assert_match "Get Started", email.body.encoded
  end

  test "welcome email includes login URL" do
    user = users(:david)

    email = UserMailer.welcome(user)

    assert_match new_session_url, email.body.encoded
  end

  test "email has both HTML and text parts" do
    user = users(:david)

    email = UserMailer.welcome(user)

    assert_equal 2, email.parts.size
    assert_equal "text/plain", email.text_part.content_type
    assert_equal "text/html", email.html_part.content_type
  end
end
```

---

## Summary

- **Structure**: Like controllers, thin and focused
- **Templates**: HTML + plain text versions
- **Layouts**: DRY up common email structure
- **Delivery**: Immediate or background (deliver_later)
- **Testing**: Test content, recipients, attachments
- **Previews**: Preview emails in development
