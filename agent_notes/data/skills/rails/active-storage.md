# Active Storage

## Contents

- [Setup](#setup)
- [Uploading & Displaying](#uploading--displaying)
- [Named Variants](#named-variants)
- [Validations](#validations)
- [Downloading & Managing](#downloading--managing)
- [Service Configuration](#service-configuration)
- [Sources](#sources)

## Setup

Attach files with `has_one_attached` or `has_many_attached`; the files live in the storage service, not the database. Fizzy passes `dependent: :purge_later` so the files are removed in a background job when the record is destroyed. `has_rich_text` (Action Text) stores embedded uploads through the same system.

```ruby
# app/models/card.rb
  has_one_attached :image, dependent: :purge_later

  has_rich_text :description
```

Detaching goes through `purge_later` as well:

```ruby
# app/controllers/cards/images_controller.rb
  def destroy
    @card.image.purge_later

    respond_to do |format|
      format.html { redirect_to @card }
      format.json { head :no_content }
    end
  end
```

Fizzy also overrides Active Storage's purge path (`config/initializers/active_storage_purge_on_last_attachment.rb`) so that a blob shared by several rich-text embeds is purged only when its last attachment goes. That is a Fizzy-specific decision, not a Rails default.

Why: purging in a job keeps destroys fast and keeps blob deletion out of the request (Rails Active Storage guide: https://guides.rubyonrails.org/active_storage_overview.html).

## Uploading & Displaying

Add a file field to a form built with `form_with model:`. Fizzy restricts the picker with the model's content-type constant:

```erb
<%# app/views/users/edit.html.erb %>
          <%= form.file_field :avatar, id: "file", class: "input", accept: User::Avatar::ALLOWED_AVATAR_CONTENT_TYPES.join(","),
                data: { upload_preview_target: "input", action: "upload-preview#previewImage" } %>
```

Show an image through a variant URL, and offer downloads with `rails_blob_path`. Fizzy's attachment partial renders a variable blob as a link and image of the same variant:

```erb
<%# app/views/active_storage/blobs/web/_representation.html.erb %>
<% elsif blob.variable? %>
  <%= link_to rails_representation_path(blob.variant(variant)), data: { lightbox_target: "image", lightbox_caption_value: blob.filename.to_s } do %>
    <%= image_tag rails_representation_path(blob.variant(variant)), width: width, height: height %>
  <% end %>
```

```erb
<%# app/views/active_storage/blobs/_blob.html.erb %>
      <%= link_to rails_blob_path(blob, disposition: :attachment), class: "attachment__link", download: blob.filename, title: "Download #{blob.filename}" do %>
```

The avatar endpoint redirects to the blob's thumbnail variant, or renders initials when no avatar is attached:

```ruby
# app/controllers/users/avatars_controller.rb
  def show
    if @user.system?
      redirect_to view_context.image_path("system_user.png")
    elsif @user.avatar.attached?
      redirect_to rails_blob_path(@user.avatar_thumbnail, disposition: "inline")
    elsif stale? @user, cache_control: cache_control
      render_initials
    end
  end
```

Direct uploads (browser to storage service) go through `ActiveStorage::DirectUploadsController`. Fizzy extends that controller so direct-upload requests go through its authentication, authorization and CSRF protection:

```ruby
# config/initializers/active_storage.rb
module ActiveStorageDirectUploadsControllerExtensions
  extend ActiveSupport::Concern

  included do
    include Authentication
    include Authorization
    include RequestForgeryProtection
  end
end
```

For a plain form field, pass `direct_upload: true` and start the Active Storage JavaScript:

```erb
<%# Illustrative (not from Fizzy) %>
<%= form.file_field :document, direct_upload: true %>
```

```javascript
// Illustrative (not from Fizzy)
import * as ActiveStorage from "@rails/activestorage"
ActiveStorage.start()
```

Why: variants and `rails_blob_path` generate signed, expiring URLs, and direct uploads keep large files off the app server (Rails Active Storage guide: https://guides.rubyonrails.org/active_storage_overview.html).

## Named Variants

Declare variants in the attachment block. `process: :immediately` creates the variant when the file is attached instead of on the first request.

```ruby
# app/models/user/avatar.rb
    has_one_attached :avatar, dependent: :purge_later do |attachable|
      attachable.variant :thumb, resize_to_fill: [ 256, 256 ], process: :immediately
    end
```

Pick the variant when it can be generated, and fall back to the original otherwise:

```ruby
# app/models/user/avatar.rb
  def avatar_thumbnail
    avatar.variable? ? avatar.variant(:thumb) : avatar
  end
```

Fizzy defines shared variant options for Action Text embeds and notes why they are processed immediately:

```ruby
# app/models/concerns/attachments.rb
  # Variants used by ActionText embeds. Processed immediately on attachment to avoid
  # read replica issues (lazy variants would attempt writes on read replicas).
  #
  # Patched into ActionText::RichText in config/initializers/action_text.rb
  VARIANTS = {
# ...
    small: { loader: { n: -1 }, resize_to_limit: [ 800, 600 ] },
    large: { loader: { n: -1 }, resize_to_limit: [ 1024, 768 ] }
  }
```

Why: lazy variants would write to the database on a read, which breaks read replicas (Fizzy: `app/models/concerns/attachments.rb`).

## Validations

Validate content type and dimensions with constants, and run the validations only when a file is attached. Fizzy keeps the constants and the validation in the `User::Avatar` concern.

```ruby
# app/models/user/avatar.rb
  ALLOWED_AVATAR_CONTENT_TYPES = %w[ image/jpeg image/png image/gif image/webp ].freeze
  MAX_AVATAR_DIMENSIONS = { width: 4096, height: 4096 }.freeze
# ...
    validate :avatar_content_type_allowed, :avatar_dimensions_allowed, if: :avatar_attached?
```

```ruby
# app/models/user/avatar.rb
  private
    def avatar_content_type_allowed
      unless ALLOWED_AVATAR_CONTENT_TYPES.include?(avatar.content_type)
        errors.add(:avatar, "must be a JPEG, PNG, GIF, or WebP image")
      end
    end
```

Dimensions come from the blob's analyzed metadata. Fizzy analyzes the blob on demand when it has not been analyzed yet:

```ruby
# app/models/user/avatar.rb
    def avatar_dimensions_allowed
      return unless avatar.blob.analyzed? || avatar.blob.analyze

      width = avatar.blob.metadata[:width]
      height = avatar.blob.metadata[:height]

      if width && width > MAX_AVATAR_DIMENSIONS[:width]
        errors.add(:avatar, "width must be less than #{MAX_AVATAR_DIMENSIONS[:width]}px")
      end

      if height && height > MAX_AVATAR_DIMENSIONS[:height]
        errors.add(:avatar, "height must be less than #{MAX_AVATAR_DIMENSIONS[:height]}px")
      end
    end
```

Use `image/jpeg`; `image/jpg` is not a registered MIME type.

Why: validating on the server is the only check a client cannot skip (Fizzy: `app/models/user/avatar.rb`).

## Downloading & Managing

Active Storage's disk controller serves local files. Fizzy adds a short public cache header to its `show` action, and lengthens the expiry of direct-upload URLs separately from download URLs:

```ruby
# config/initializers/active_storage.rb
ActiveSupport.on_load(:active_storage_blob) do
  ActiveStorage::DiskController.after_action only: :show do
    expires_in 5.minutes, public: true
  end
end
```

```ruby
# lib/rails_ext/active_storage_blob_service_url_for_direct_upload_expiry.rb
  mattr_accessor :service_urls_for_direct_uploads_expire_in, default: 48.hours
end

module ActiveStorageBlobServiceUrlForDirectUploadExpiry
  # Override default expires_in to accommodate long upload URL expiry
  # without having to lengthen download URL expiry.
  #
  # Accounts for Cloudflare only proxying slow client uploads once they're
  # fully buffered, long after the URL expired.
  #
  # 48 hours covers a 10GB upload at 0.5Mbps.
  def service_url_for_direct_upload(expires_in: ActiveStorage.service_urls_for_direct_uploads_expire_in)
    super
  end
```

Why: slow uploads of large files outlive a short URL expiry, so uploads get 48 hours (Fizzy: `lib/rails_ext/active_storage_blob_service_url_for_direct_upload_expiry.rb`).

## Service Configuration

Services are declared in `config/storage.yml`, and each environment selects one with `config.active_storage.service`. Fizzy's `storage.yml` is a small ERB file that loads either the open-source config or the SaaS gem's config, and `storage.oss.yml` holds the open-source services:

```yaml
# config/storage.yml
<%
  config_path = if Fizzy.saas?
    gem_path = Gem::Specification.find_by_name("fizzy-saas").gem_dir
    File.join(gem_path, "config", "storage.yml")
  else
    File.join(__dir__, "storage.oss.yml")
  end
%>
<%= ERB.new(File.read(config_path)).result %>
```

```yaml
# config/storage.oss.yml
test:
  service: Disk
  root: <%= Rails.root.join("tmp/storage/files") %>

local:
  service: Disk
  root: <%= Rails.root.join("storage", Rails.env, "files") %>
```

```yaml
# config/storage.oss.yml
s3:
  service: S3
  access_key_id: <%= ENV["S3_ACCESS_KEY_ID"] %>
  bucket: <%= ENV["S3_BUCKET"] || "fizzy-#{Rails.env}-activestorage" %>
  endpoint: <%= ENV["S3_ENDPOINT"] %>
  force_path_style: <%= ENV["S3_FORCE_PATH_STYLE"] == "true" %>
  region: <%= ENV.fetch("S3_REGION", "us-east-1") %>
  request_checksum_calculation: <%= ENV.fetch("S3_REQUEST_CHECKSUM_CALCULATION", "when_supported") %>
  response_checksum_validation: <%= ENV.fetch("S3_RESPONSE_CHECKSUM_VALIDATION", "when_supported") %>
  secret_access_key: <%= ENV["S3_SECRET_ACCESS_KEY"] %>
```

Production picks the service from an environment variable and defaults to local disk, unless something else (the SaaS gem) already set it:

```ruby
# config/environments/production.rb
  # Select Active Storage service via env var; default to local disk.
  # Don't overwrite if it's already been set (e.g. by fizzy-saas)
  if config.active_storage.service.blank?
    config.active_storage.service = ENV.fetch("ACTIVE_STORAGE_SERVICE", "local").to_sym
  end
```

Why: the environment decides where files live, so the same image runs against local disk or object storage (Fizzy: `config/environments/production.rb`).

## Sources

- [Active Storage guide](https://guides.rubyonrails.org/active_storage_overview.html)
- Fizzy at 6aebc0cea: `app/models/user/avatar.rb`, `app/models/concerns/attachments.rb`, `config/storage.oss.yml`, `config/initializers/active_storage.rb`
