# File Management Quick Reference

## What's New ✨

PrizmAI now supports file uploads and downloads in both **Chat Rooms** and **Tasks**!

### Chat Room Files
Upload documents to share with your team in real-time conversations.

### Task Files  
Attach documents, spreadsheets, and images directly to tasks for better organization and tracking.

---

## Supported File Types

✅ **Documents:** PDF  
✅ **Office:** Word (.doc, .docx), Excel (.xls, .xlsx), PowerPoint (.ppt, .pptx)  
✅ **Images:** JPG, JPEG, PNG  

⚠️ **Maximum file size: 10 MB per file**

---

## How to Use

### Upload to Chat Room

1. Open a chat room
2. Click the **📎 Attach** button next to the Send button
3. Choose file from your computer
4. (Optional) Add a description
5. Click **Upload**
6. File appears in the Files sidebar

### Upload to Task

1. Open a task detail page
2. Scroll to **Attachments** section
3. Click **📤 Upload** button
4. Choose file from your computer
5. (Optional) Add a description
6. Click **Upload**
7. File appears in the Attachments list

### Download a File

Click on the **filename** link to download  
or  
Click on any file name in the file list

### Delete a File

1. Find the file in the list
2. Click the **🗑️ trash icon**
3. Confirm deletion
4. File is removed (soft-deleted)

---

## Features

### File Organization
- Files automatically organized by date
- File type icons for quick identification
- File size shown for each attachment
- Upload timestamp and uploader info displayed

### File Metadata
- **Uploader:** Shows who uploaded the file
- **Size:** File size in bytes/KB/MB format
- **Date:** When the file was uploaded
- **Description:** Optional notes about the file

### Security
- Only room members can access chat room files
- Only board members can access task files
- Only file owner, creator, or staff can delete
- Soft delete preserves audit trail

### Error Handling
- Clear error messages for oversized files
- Validation for unsupported file types
- User-friendly error dialogs
- Automatic reload on successful upload

---

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Attach file (Chat) | Click 📎 button |
| Upload file (Task) | Click 📤 button |
| Download file | Click filename |
| Delete file | Click 🗑️ icon |

---

## API Endpoints

### Chat Room File APIs
```
POST   /messaging/room/{id}/files/upload/    Upload file
GET    /messaging/room/{id}/files/list/      List files (JSON)
GET    /messaging/file/{id}/download/        Download file
POST   /messaging/file/{id}/delete/          Delete file
```

### Task File APIs
```
POST   /tasks/{id}/files/upload/             Upload file
GET    /tasks/{id}/files/list/               List files (JSON)
GET    /files/{id}/download/                 Download file
POST   /files/{id}/delete/                   Delete file
```

---

## Common Questions

**Q: Can I upload multiple files at once?**  
A: Not currently - upload files one at a time.

**Q: What's the maximum file size?**  
A: 10MB per file.

**Q: Can I edit a file after uploading?**  
A: No, but you can delete and re-upload an updated version.

**Q: Are deleted files permanently removed?**  
A: Files are soft-deleted (marked as deleted) for audit purposes, but their records are kept in the database.

**Q: Who can see my files?**  
A: In chat rooms - only room members. In tasks - only board members.

**Q: Can I download files in bulk?**  
A: Not currently - download files individually.

**Q: What if a file fails to upload?**  
A: You'll see an error message. Check file size and type, then try again.

---

## File Icons

| Icon | File Type |
|------|-----------|
| 📄 | PDF |
| 📝 | Word |
| 📊 | Excel |
| 🎯 | PowerPoint |
| 🖼️ | Images |

---

## Troubleshooting

### Upload Button Not Showing
- Check you're a room member or board member
- Refresh the page
- Clear browser cache

### File Won't Upload
- Check file size (max 10MB)
- Verify file type is supported
- Check network connection

### Can't Download File
- Verify you have access to the room/board
- Try a different browser
- Check file still exists

### File Appears Twice
- Page may need refresh
- Check if original upload was successful

---

## Tips & Best Practices

### Organization
- Use descriptive filenames
- Add descriptions for important files
- Keep task attachments relevant to the task

### Performance
- Upload smaller files when possible
- Avoid uploading duplicate files
- Regularly clean up old files

### Security
- Don't share sensitive data via files
- Use descriptions to explain file purpose
- Review file access permissions

---

## What's Coming Soon

🔄 **File versioning** - Track file updates  
🔍 **File search** - Find files by name  
🖼️ **File preview** - View images/PDFs inline  
📦 **Bulk upload** - Upload multiple files at once  

---

## Need Help?

📖 Read the full documentation: `FILE_MANAGEMENT_IMPLEMENTATION.md`  
💬 Ask in chat or leave a comment on the task  
🐛 Report bugs to your admin  

---

**Last Updated:** October 31, 2025  
**Version:** 1.0
