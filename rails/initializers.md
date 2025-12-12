# Initializers Guide

Guide for Rails configuration and boot-time setup.

---

## File Structure

```
config/initializers/
├── extensions.rb          # Load lib/ extensions
├── assets.rb             # Asset pipeline config
├── filter_parameter_logging.rb
├── inflections.rb
└── cors.rb
```

---

## Common Initializers

### Load Extensions

```ruby
# config/initializers/extensions.rb
Dir["#{Rails.root}/lib/rails_ext/*"].each { |path|
  require "rails_ext/#{File.basename(path)}"
}
```

### Filter Parameters

```ruby
# config/initializers/filter_parameter_logging.rb
Rails.application.config.filter_parameters += [
  :passw, :secret, :token, :_key, :crypt, :salt, :certificate
]
```

### CORS

```ruby
# config/initializers/cors.rb
Rails.application.config.middleware.insert_before 0, Rack::Cors do
  allow do
    origins "example.com"
    resource "*", headers: :any, methods: [:get, :post, :put, :delete, :options]
  end
end
```

### Custom Configuration

```ruby
# config/initializers/app_config.rb
Rails.application.config.x.api_key = ENV["API_KEY"]
Rails.application.config.x.feature_flags = {
  new_dashboard: true,
  experimental_feature: false
}

# Usage
Rails.configuration.x.api_key
```

---

## Summary

- **Boot Time**: Code runs when app starts
- **Configuration**: Set up libraries, features
- **Load Order**: Matters for dependencies
- **Environment Specific**: Use ENV for secrets
