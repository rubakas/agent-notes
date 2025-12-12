# Active Storage

File upload and attachment patterns with Active Storage.

---

## Setup

### Single Attachment

```ruby
class User < ApplicationRecord
  has_one_attached :avatar, dependent: :purge_later
end
```

### Multiple Attachments

```ruby
class Card < ApplicationRecord
  has_many_attached :documents, dependent: :purge_later
end
```

**Dependent options:**
- `:purge` - Deletes attachment immediately when record is destroyed
- `:purge_later` - Queues job to delete attachment (recommended for production)
- `false` - Keeps attachment files orphaned (not recommended)

---

## Uploading Files

### In Forms

```erb
<%= form_with model: @user do |f| %>
  <%= f.file_field :avatar %>
  <%= f.submit %>
<% end %>
```

### Direct Uploads

```erb
<%= f.file_field :avatar, direct_upload: true %>
```

---

## Displaying Images

```erb
<% if @user.avatar.attached? %>
  <%= image_tag @user.avatar %>
<% end %>

<%# With variant %>
<%= image_tag @user.avatar.variant(resize_to_limit: [200, 200]) %>
```

---

## Variants

```ruby
# Resize
@user.avatar.variant(resize_to_limit: [300, 300])

# Crop
@user.avatar.variant(resize_to_fill: [300, 300])

# Format
@user.avatar.variant(resize_to_limit: [300, 300], format: :jpg)
```

---

## Validations

```ruby
class User < ApplicationRecord
  has_one_attached :avatar

  validate :avatar_validation

  private
    def avatar_validation
      return unless avatar.attached?

      unless avatar.content_type.in?(%w[image/png image/jpg image/jpeg])
        errors.add(:avatar, "must be a PNG or JPG")
      end

      if avatar.byte_size > 5.megabytes
        errors.add(:avatar, "must be less than 5MB")
      end
    end
end
```

---

## Downloading Files

### Small Files

```ruby
# In controller
def download
  send_data @user.avatar.download,
    filename: @user.avatar.filename.to_s,
    type: @user.avatar.content_type,
    disposition: "attachment"
end
```

### Large Files (Streaming)

```ruby
# Redirect to cloud storage URL (recommended for large files)
def download
  redirect_to rails_blob_url(@document), allow_other_host: true
end

# Or use X-Sendfile/X-Accel-Redirect
# Configure your web server (nginx/apache) for efficient file serving
send_file @user.avatar.service_url
```

---

## Removing Attachments

```ruby
# Remove single attachment
@user.avatar.purge        # Synchronous
@user.avatar.purge_later  # Background job (recommended)

# Remove all attachments from a collection
@card.documents.purge_all        # Synchronous
@card.documents.purge_later      # Background job (recommended)

# Check if attached
@user.avatar.attached?  # => true/false
```

---

## Service Configuration

### Amazon S3

```yaml
# config/storage.yml
amazon:
  service: S3
  access_key_id: <%= Rails.application.credentials.dig(:aws, :access_key_id) %>
  secret_access_key: <%= Rails.application.credentials.dig(:aws, :secret_access_key) %>
  region: us-east-1
  bucket: my-app-<%= Rails.env %>
```

### Google Cloud Storage

```yaml
# config/storage.yml
google:
  service: GCS
  project: my-project
  credentials: <%= Rails.application.credentials.dig(:gcs, :keyfile) %>
  bucket: my-app-<%= Rails.env %>
```

### Microsoft Azure

```yaml
# config/storage.yml
microsoft:
  service: AzureStorage
  storage_account_name: <%= Rails.application.credentials.dig(:azure, :storage_account_name) %>
  storage_access_key: <%= Rails.application.credentials.dig(:azure, :storage_access_key) %>
  container: my-app-<%= Rails.env %>
```

### Local (Development/Test)

```yaml
# config/storage.yml
local:
  service: Disk
  root: <%= Rails.root.join("storage") %>

# config/environments/development.rb
config.active_storage.service = :local

# config/environments/production.rb
config.active_storage.service = :amazon
```

---

## Advanced Validations

```ruby
class User < ApplicationRecord
  has_one_attached :avatar, dependent: :purge_later
  has_many_attached :documents, dependent: :purge_later

  validate :avatar_validation
  validate :documents_validation

  private
    def avatar_validation
      return unless avatar.attached?

      # Content type validation
      acceptable_types = %w[image/png image/jpg image/jpeg image/gif]
      unless avatar.content_type.in?(acceptable_types)
        errors.add(:avatar, "must be a PNG, JPG, or GIF")
      end

      # File size validation
      if avatar.byte_size > 5.megabytes
        errors.add(:avatar, "must be less than 5MB")
      end

      # Image dimensions (requires image_processing gem)
      image = MiniMagick::Image.read(avatar.download)
      if image.width < 100 || image.height < 100
        errors.add(:avatar, "must be at least 100x100 pixels")
      end
    end

    def documents_validation
      return unless documents.attached?

      # Validate total count
      if documents.count > 10
        errors.add(:documents, "cannot exceed 10 files")
      end

      # Validate each document
      documents.each do |document|
        # File size
        if document.byte_size > 10.megabytes
          errors.add(:documents, "#{document.filename} must be less than 10MB")
        end

        # Content type
        acceptable_types = %w[application/pdf image/png image/jpg]
        unless document.content_type.in?(acceptable_types)
          errors.add(:documents, "#{document.filename} must be a PDF or image")
        end
      end
    end
end
```

---

## Virus Scanning (Production Pattern)

```ruby
# app/models/concerns/virus_scannable.rb
module VirusScannable
  extend ActiveSupport::Concern

  included do
    before_save :scan_attachments
  end

  private
    def scan_attachments
      self.class.attachment_reflections.each_key do |name|
        attachment = public_send(name)
        next unless attachment.attached? && attachment.changed?

        if attachment.is_a?(ActiveStorage::Attached::Many)
          attachment.each { |file| scan_file(file, name) }
        else
          scan_file(attachment, name)
        end
      end
    end

    def scan_file(file, attribute_name)
      # Example using ClamAV or similar service
      scanner = VirusScanner.new(file)
      if scanner.infected?
        errors.add(attribute_name, "contains a virus")
        file.purge
      end
    end
end

# Usage
class User < ApplicationRecord
  include VirusScannable
  has_one_attached :avatar
end
```

---

## Summary

- **has_one_attached**: Single file with `dependent: :purge_later`
- **has_many_attached**: Multiple files with proper validations
- **Variants**: Image transformations (resize, crop, format)
- **Direct Upload**: Upload to cloud storage directly (faster)
- **Validations**: Content type, file size, dimensions, count
- **Service Config**: S3, GCS, Azure for production
- **Streaming**: Use redirects for large file downloads
- **Virus Scanning**: Add security layer for uploads
