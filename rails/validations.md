# Validations Guide

Guide for Rails model validations.

---

## Built-in Validations

### Presence

```ruby
validates :title, presence: true
validates :email, presence: true, on: :create
```

### Uniqueness

```ruby
validates :email, uniqueness: true
validates :number, uniqueness: { scope: :account_id }
validates :slug, uniqueness: { case_sensitive: false }
```

### Format

```ruby
validates :email, format: { with: URI::MailTo::EMAIL_REGEXP }
validates :url, format: { with: /\Ahttps?:\/\/.+\z/ }
```

### Length

```ruby
validates :title, length: { maximum: 200 }
validates :password, length: { minimum: 8, maximum: 128 }
validates :code, length: { is: 6 }
```

### Inclusion

```ruby
validates :status, inclusion: { in: %w[draft published archived] }
validates :role, inclusion: { in: ALLOWED_ROLES }
```

---

## Custom Validations

### Method Validation

```ruby
class Webhook < ApplicationRecord
  validate :validate_url

  private
    def validate_url
      return if url.blank?

      uri = URI.parse(url)
      unless PERMITTED_SCHEMES.include?(uri.scheme)
        errors.add(:url, "must use http or https")
      end
    rescue URI::InvalidURIError
      errors.add(:url, "is not a valid URL")
    end
end
```

### Validator Class

```ruby
class EmailValidator < ActiveModel::EachValidator
  def validate_each(record, attribute, value)
    unless value =~ URI::MailTo::EMAIL_REGEXP
      record.errors.add(attribute, "is not a valid email")
    end
  end
end

# Usage
validates :email, email: true
```

---

## Conditional Validations

```ruby
validates :title, presence: true, if: :published?
validates :description, presence: true, unless: :draft?
validates :api_key, presence: true, on: :create
```

---

## Summary

- **Built-in**: presence, uniqueness, format, length, inclusion
- **Custom**: validate method or validator class
- **Conditional**: if, unless, on
- **Scope**: Uniqueness with scope option
