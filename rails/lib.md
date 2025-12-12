# Lib Guide

Guide for custom libraries and Rails extensions.

---

## File Structure

```
lib/
├── my_app.rb               # Main library
├── rails_ext/              # Rails extensions
│   ├── string.rb
│   ├── prepend_order.rb
│   └── active_record_date_arithmetic.rb
├── services/               # Custom services (if used)
│   └── payment_processor.rb
└── tasks/                  # Rake tasks
    └── maintenance.rake
```

---

## Rails Extensions

### Extend ActiveRecord

```ruby
# lib/rails_ext/prepend_order.rb
module ActiveRecordRelationPrependOrder
  extend ActiveSupport::Concern

  included do
    def prepend_order(*args)
      new_orders = args.flatten.map { |arg| arg.is_a?(String) ? arg : arg.to_sql }

      spawn.tap do |relation|
        relation.order_values = new_orders + order_values
      end
    end
  end
end

ActiveRecord::Relation.include(ActiveRecordRelationPrependOrder)
ActiveRecord::AssociationRelation.include(ActiveRecordRelationPrependOrder)
```

### Load Extensions

```ruby
# config/initializers/extensions.rb
Dir["#{Rails.root}/lib/rails_ext/*"].each { |path|
  require "rails_ext/#{File.basename(path)}"
}
```

---

## Custom Libraries

```ruby
# lib/my_app.rb
module MyApp
  class << self
    def version
      @version ||= File.read(Rails.root.join("VERSION")).strip
    end

    def config
      @config ||= Config.new
    end
  end

  class Config
    attr_accessor :feature_flag

    def initialize
      @feature_flag = false
    end
  end
end

# Usage
MyApp.version
MyApp.config.feature_flag = true
```

---

## Summary

- **Rails Extensions**: Extend framework carefully
- **Custom Libraries**: Reusable code outside app/
- **Autoload**: Configure in config/application.rb
- **Load**: Use initializers to require lib files
