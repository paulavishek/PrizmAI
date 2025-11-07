# File Management Implementation - Complete Guide

## Overview
PrizmAI now includes comprehensive file management features for both chat rooms and task management, allowing users to upload, download, and manage documents in a centralized location.

## Features Implemented

### 1. Chat Room File Management
**Location:** Messaging module (`messaging/`)

#### Models (`messaging/models.py`)
- **FileAttachment Model:**
  - Stores file uploads for chat rooms
  - Supports: PDF, Word (doc/docx), Excel (xls/xlsx), PowerPoint (ppt/pptx), Images (jpg/jpeg/png)
  - Max file size: 10MB per file
  - Soft delete support (keeps historical records)
  - Fields:
    - `chat_room` (ForeignKey) - Reference to the chat room
    - `uploaded_by` (ForeignKey) - User who uploaded the file
    - `file` (FileField) - The actual file
    - `filename` - Original filename
    - `file_size` - Size in bytes
    - `file_type` - File extension
    - `description` - Optional description
    - `uploaded_at` - Upload timestamp
    - `deleted_at` - Soft delete timestamp (null if not deleted)

#### Views (`messaging/views.py`)
- **`upload_chat_room_file(request, room_id)`** - Upload file to chat room
- **`download_chat_room_file(request, file_id)`** - Download file from chat room
- **`delete_chat_room_file(request, file_id)`** - Soft delete file from chat room
- **`list_chat_room_files(request, room_id)`** - List all files in a chat room (JSON API)

#### URL Routes (`messaging/urls.py`)
```python
path('room/<int:room_id>/files/upload/', views.upload_chat_room_file, name='upload_chat_room_file'),
path('room/<int:room_id>/files/list/', views.list_chat_room_files, name='list_chat_room_files'),
path('file/<int:file_id>/download/', views.download_chat_room_file, name='download_chat_room_file'),
path('file/<int:file_id>/delete/', views.delete_chat_room_file, name='delete_chat_room_file'),
```

#### Forms (`messaging/forms.py`)
- **ChatRoomFileForm:**
  - Validates file type and size
  - Raises user-friendly error messages
  - Accepts optional description

#### Template (`templates/messaging/chat_room_detail.html`)
- File upload section with toggle button
- File list sidebar showing all attachments
- Download links for each file
- Delete buttons (for file owner, room creator, or staff)
- File icons based on type
- File metadata display (uploader, size, date)

---

### 2. Task File Management
**Location:** Kanban module (`kanban/`)

#### Models (`kanban/models.py`)
- **TaskFile Model:**
  - Stores file uploads for individual tasks
  - Same file type support and constraints as FileAttachment
  - Max file size: 10MB per file
  - Soft delete support
  - Fields:
    - `task` (ForeignKey) - Reference to the task
    - `uploaded_by` (ForeignKey) - User who uploaded the file
    - `file` (FileField) - The actual file
    - `filename` - Original filename
    - `file_size` - Size in bytes
    - `file_type` - File extension
    - `description` - Optional description
    - `uploaded_at` - Upload timestamp
    - `deleted_at` - Soft delete timestamp (null if not deleted)

#### Views (`kanban/views.py`)
- **`upload_task_file(request, task_id)`** - Upload file to task
- **`download_task_file(request, file_id)`** - Download file from task
- **`delete_task_file(request, file_id)`** - Soft delete file from task
- **`list_task_files(request, task_id)`** - List all files in a task (JSON API)

#### URL Routes (`kanban/urls.py`)
```python
path('tasks/<int:task_id>/files/upload/', views.upload_task_file, name='upload_task_file'),
path('tasks/<int:task_id>/files/list/', views.list_task_files, name='list_task_files'),
path('files/<int:file_id>/download/', views.download_task_file, name='download_task_file'),
path('files/<int:file_id>/delete/', views.delete_task_file, name='delete_task_file'),
```

#### Forms (`kanban/forms/__init__.py`)
- **TaskFileForm:**
  - Validates file type and size
  - Raises user-friendly error messages
  - Accepts optional description

#### Template (`templates/kanban/task_detail.html`)
- File upload card in the main content area
- Collapsible file upload form
- File list with all attachments
- Download links for each file
- Delete buttons (for file owner or staff)
- File icons based on type
- File metadata display (uploader, size, date, optional description)

---

## Supported File Types

| Type | Extensions |
|------|-----------|
| Documents | .pdf |
| Word | .doc, .docx |
| Excel | .xls, .xlsx |
| PowerPoint | .ppt, .pptx |
| Images | .jpg, .jpeg, .png |

## File Size Limits
- **Maximum file size:** 10MB per file
- **Enforced at form validation level**
- **Clear error messages for oversized files**

## Database Schema

### FileAttachment Table
```
ID | chat_room_id | uploaded_by_id | file | filename | file_size | file_type | description | uploaded_at | deleted_at | created_at | updated_at
```

### TaskFile Table
```
ID | task_id | uploaded_by_id | file | filename | file_size | file_type | description | uploaded_at | deleted_at | created_at | updated_at
```

## Migrations

### Applied Migrations
- `messaging/migrations/0002_fileattachment.py` - Created FileAttachment model
- `kanban/migrations/0027_taskfile.py` - Created TaskFile model

## Security Features

### Permission Checks
1. **Chat Room Files:**
   - Only room members can view/download files
   - Only file owner, room creator, or staff can delete
   - Room member check enforced on upload

2. **Task Files:**
   - Only board members can view/download files
   - Only file owner or staff can delete
   - Board member check enforced on upload

### File Handling
- Files stored in `media/chat_rooms/` and `media/tasks/` with date-based organization
- Soft delete preserves audit trail
- File type validation prevents malicious uploads
- File size validation prevents storage issues

## API Endpoints

### Chat Room Files
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/messaging/room/<id>/files/upload/` | Upload file to chat room |
| GET | `/messaging/room/<id>/files/list/` | List files in chat room (JSON) |
| GET | `/messaging/file/<id>/download/` | Download file from chat room |
| POST | `/messaging/file/<id>/delete/` | Delete file from chat room |

### Task Files
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tasks/<id>/files/upload/` | Upload file to task |
| GET | `/tasks/<id>/files/list/` | List files in task (JSON) |
| GET | `/files/<id>/download/` | Download file from task |
| POST | `/files/<id>/delete/` | Delete file from task |

## Usage Examples

### For Users

#### Uploading a File to a Chat Room
1. Open a chat room
2. Click the "Attach file" button (paperclip icon)
3. Select a file from your computer
4. Optionally add a description
5. Click "Upload"
6. File appears in the Files sidebar

#### Uploading a File to a Task
1. Open a task detail page
2. Click the "Upload" button in the Attachments card
3. Select a file from your computer
4. Optionally add a description
5. Click "Upload"
6. File appears in the Attachments list

#### Downloading a File
1. Click on the filename link in the file list
2. File downloads to your computer

#### Deleting a File
1. Click the trash icon next to the file
2. Confirm deletion
3. File is soft-deleted (marked as deleted but record kept)

### For Developers

#### Accessing Files in Templates
```django
{% for file in chat_room.file_attachments.all %}
    {% if not file.is_deleted %}
        <a href="{% url 'messaging:download_chat_room_file' file_id=file.id %}">
            {{ file.filename }}
        </a>
    {% endif %}
{% endfor %}
```

#### Getting File Icon
```python
icon_class = file.get_file_icon()  # Returns 'fa-file-pdf', 'fa-file-word', etc.
```

#### Checking if File is Deleted
```python
if file.is_deleted():
    print(f"File {file.filename} was deleted on {file.deleted_at}")
```

#### Validating File Type
```python
if TaskFile.is_valid_file_type('document.pdf'):
    print("Valid file type")
else:
    print("Invalid file type")
```

## Storage Configuration

### Settings (`kanban_board/settings.py`)
```python
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
```

### Upload Directory Structure
```
media/
├── chat_rooms/
│   └── YYYY/MM/DD/
│       └── uploaded_files...
└── tasks/
    └── YYYY/MM/DD/
        └── uploaded_files...
```

## Testing File Management

### Manual Testing Checklist
- [ ] Upload valid file to chat room
- [ ] Upload oversized file (should show error)
- [ ] Upload invalid file type (should show error)
- [ ] Download file from chat room
- [ ] Delete file from chat room (soft delete)
- [ ] Upload valid file to task
- [ ] Download file from task
- [ ] Delete file from task
- [ ] Verify permission checks (non-members can't access)
- [ ] Verify file list displays correctly
- [ ] Test file icons display correctly

### Unit Tests
Test coverage should include:
- File upload with valid files
- File upload validation (size, type)
- File download with proper permissions
- File deletion (soft delete)
- File permission checks
- JSON API responses

## Performance Considerations

### Database Queries
- File lists are optimized with `values()` queries
- Soft delete filters exclude deleted files by default
- Consider pagination for large file lists

### Storage
- Files organized by date to prevent directory bloat
- Consider implementing periodic cleanup of old files
- Monitor storage usage for 10MB+ file uploads

## Future Enhancements

### Potential Improvements
1. **File Preview:** Add inline preview for images and PDFs
2. **Bulk Upload:** Support uploading multiple files at once
3. **File Search:** Search files by name/content
4. **Version Control:** Track file updates/versions
5. **Virus Scanning:** Integrate antivirus scanning
6. **File Expiration:** Auto-delete files after X days
7. **Storage Quotas:** Limit storage per chat room/task
8. **File Sharing:** Share files outside the platform

## Troubleshooting

### Common Issues

**Issue:** File upload returns 403 Forbidden
- **Solution:** Ensure user is a member of the chat room/board

**Issue:** File download returns 404
- **Solution:** Check that file exists and is not deleted

**Issue:** Upload button not appearing
- **Solution:** Verify file permissions (check `form.is_valid()` in view)

**Issue:** File list empty despite uploaded files
- **Solution:** Files may be soft-deleted; check `deleted_at` field

## Related Documentation
- [Messaging Module Documentation](./messaging/README.md)
- [Kanban Module Documentation](./kanban/README.md)
- [Django File Upload Handling](https://docs.djangoproject.com/en/5.2/topics/files/)
