# Initializers & Lib

## Contents

- [Initializers](#initializers)
- [Rails Extensions](#rails-extensions)
- [Custom Libraries](#custom-libraries)
- [Sources](#sources)

## Initializers

Fizzy's `config/initializers/` holds one small file per concern: `active_job.rb`, `multi_tenant.rb`, `uuid_primary_keys.rb`, `vapid.rb`, `inflections.rb`, `filter_parameter_logging.rb`, `extensions.rb` and a `tenanting/` directory, among others. Fizzy has no `cors.rb`; add one only if your app needs CORS.

App-wide settings that come from the environment go on `config.x`. This is the whole of `vapid.rb`:

```ruby
# config/initializers/vapid.rb
Rails.application.configure do
  config.x.vapid.private_key = ENV["VAPID_PRIVATE_KEY"]
  config.x.vapid.public_key = ENV["VAPID_PUBLIC_KEY"]
end
```

Code reads them back through `Rails.configuration.x`:

```ruby
# lib/web_push/notification.rb
        Rails.configuration.x.vapid.symbolize_keys
```

Parameter filtering uses partial matches, so `passw` covers `password`:

```ruby
# config/initializers/filter_parameter_logging.rb
Rails.application.config.filter_parameters += %i[
  passw secret token _key crypt salt certificate otp ssn
]
```

Inflection rules go in `inflections.rb`:

```ruby
# config/initializers/inflections.rb
ActiveSupport::Inflector.inflections(:en) do |inflect|
  inflect.acronym "SQLite"
  inflect.acronym "IO"

  inflect.singular "quotas", "quota"
  inflect.plural "quota", "quotas"
end
```

Why: `config.x` gives environment-driven settings one namespace instead of scattered `ENV` reads (Fizzy: `config/initializers/vapid.rb`, `lib/web_push/notification.rb`).

## Rails Extensions

Patches to Rails internals live in `lib/rails_ext/`, one concern per file. `config/application.rb` tells Zeitwerk to skip that directory:

```ruby
# config/application.rb
    # Include the `lib` directory in autoload paths. Use the `ignore:` option
    # to list subdirectories that don't contain `.rb` files or that shouldn't
    # be reloaded or eager loaded.
    config.autoload_lib ignore: %w[ assets tasks rails_ext ]
```

A one-line initializer then requires every file in it:

```ruby
# config/initializers/extensions.rb
Dir["#{Rails.root}/lib/rails_ext/*"].each { |path| require "rails_ext/#{File.basename(path)}" }
```

A typical extension is a module that is included into a Rails class at load time. This one adds `prepend_order` to relations:

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

Why: the extension files do not define constants named after their files (`prepend_order.rb` defines `ActiveRecordRelationPrependOrder`), so Zeitwerk must not manage them and one initializer requires them instead (Fizzy: `config/application.rb`, `config/initializers/extensions.rb`).

## Custom Libraries

Shared code that is not a model goes in `lib/`, and the main module is named after the app. Fizzy's `lib/fizzy.rb` holds boot-time switches that must work before Rails has loaded:

```ruby
# lib/fizzy.rb
module Fizzy
  class << self
    def saas?
      return @saas if defined?(@saas)
      @saas = !!(((ENV["SAAS"] || File.exist?(File.expand_path("../tmp/saas.txt", __dir__))) && ENV["SAAS"] != "false"))
    end

    def db_adapter
      @db_adapter ||= DbAdapter.new ENV.fetch("DATABASE_ADAPTER", saas? ? "mysql" : "sqlite")
    end

    def configure_bundle
      if saas?
        ENV["BUNDLE_GEMFILE"] = "Gemfile.saas"
      end
    end
  end
```

`config/application.rb` requires the file, and `bin/kamal`, `config/puma.rb`, `config/ci.rb` and `config/database.yml` call `Fizzy.saas?` or `Fizzy.db_adapter`. `DbAdapter` is a small class rather than an inquirer; its comment says why: "Not using inquiry so that it works before Rails env loads."

The rest of `lib/` is grouped by subject: `action_pack/` (passkey and WebAuthn support), `active_search/` (the MySQL sharded search adapter), `web_push/`, `deployment/`, `assets/` and `tasks/` (Rake tasks), plus `rails_ext/` from above. `assets` and `tasks` are also on the `autoload_lib` ignore list.

Why: a plain module required from `config/application.rb` is available to the boot files and binstubs that run before the app loads (Fizzy: `lib/fizzy.rb`).

## Sources

- Fizzy `config/initializers/`, `lib/` and `config/application.rb`, at commit 6aebc0cea
- Rails guide on initialization and configuration: https://guides.rubyonrails.org/configuring.html
