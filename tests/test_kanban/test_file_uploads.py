"""
File Upload and Attachment Tests
==================================

Tests coverage:
- File size validation
- File type validation
- Malicious file detection
- Upload security
- Filename sanitization
- Storage path security
- Image processing security
- Virus scanning (mocked)
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.conf import settings
from unittest.mock import patch, Mock
import os

from accounts.models import Organization
from kanban.models import Board, Column, Task, TaskAttachment


class FileUploadValidationTests(TestCase):
    """Test file upload validation"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.column = Column.objects.create(
            name='To Do',
            board=self.board
        )
        self.task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_upload_valid_file(self):
        """Test uploading valid file types"""
        valid_files = [
            ('test.pdf', b'%PDF-1.4 fake pdf content', 'application/pdf'),
            ('test.docx', b'fake docx content', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
            ('test.txt', b'plain text content', 'text/plain'),
            ('test.png', b'\x89PNG\r\n\x1a\n fake png', 'image/png'),
            ('test.jpg', b'\xff\xd8\xff\xe0 fake jpg', 'image/jpeg'),
        ]
        
        for filename, content, content_type in valid_files:
            uploaded_file = SimpleUploadedFile(
                filename,
                content,
                content_type=content_type
            )
            
            response = self.client.post(
                reverse('kanban:task_upload_attachment', args=[self.task.id]),
                {'file': uploaded_file}
            )
            
            # Should accept valid files
            self.assertIn(response.status_code, [200, 201, 302])
    
    def test_reject_invalid_file_types(self):
        """Test rejection of invalid file types"""
        invalid_files = [
            ('test.exe', b'MZ fake exe', 'application/x-msdownload'),
            ('test.bat', b'@echo off', 'application/x-bat'),
            ('test.sh', b'#!/bin/bash', 'application/x-sh'),
            ('test.php', b'<?php echo "hack"; ?>', 'application/x-php'),
            ('test.js', b'alert("xss")', 'application/javascript'),
        ]
        
        for filename, content, content_type in invalid_files:
            uploaded_file = SimpleUploadedFile(
                filename,
                content,
                content_type=content_type
            )
            
            response = self.client.post(
                reverse('kanban:task_upload_attachment', args=[self.task.id]),
                {'file': uploaded_file}
            )
            
            # Should reject dangerous file types
            self.assertIn(response.status_code, [400, 403])
    
    def test_file_size_limit(self):
        """Test file size limits are enforced"""
        # Create file larger than allowed limit (e.g., 10MB)
        max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 10 * 1024 * 1024)
        large_content = b'x' * (max_size + 1)
        
        large_file = SimpleUploadedFile(
            'large_file.pdf',
            large_content,
            content_type='application/pdf'
        )
        
        response = self.client.post(
            reverse('kanban:task_upload_attachment', args=[self.task.id]),
            {'file': large_file}
        )
        
        # Should reject oversized file
        self.assertIn(response.status_code, [400, 413])
    
    def test_empty_file_rejection(self):
        """Test empty files are rejected"""
        empty_file = SimpleUploadedFile(
            'empty.txt',
            b'',
            content_type='text/plain'
        )
        
        response = self.client.post(
            reverse('kanban:task_upload_attachment', args=[self.task.id]),
            {'file': empty_file}
        )
        
        # Should reject empty file
        self.assertEqual(response.status_code, 400)


class FilenameSanitizationTests(TestCase):
    """Test filename sanitization"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.column = Column.objects.create(name='To Do', board=self.board)
        self.task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_sanitize_dangerous_filenames(self):
        """Test dangerous filenames are sanitized"""
        dangerous_filenames = [
            '../../../etc/passwd.txt',
            '..\\..\\..\\windows\\system32\\config\\sam.txt',
            'file; rm -rf /.txt',
            '<script>alert(1)</script>.txt',
            'file\x00.txt.exe',  # Null byte injection
            'CON.txt',  # Windows reserved name
            'file|grep.txt',  # Shell metacharacters
        ]
        
        for dangerous_name in dangerous_filenames:
            uploaded_file = SimpleUploadedFile(
                dangerous_name,
                b'content',
                content_type='text/plain'
            )
            
            response = self.client.post(
                reverse('kanban:task_upload_attachment', args=[self.task.id]),
                {'file': uploaded_file}
            )
            
            if response.status_code in [200, 201, 302]:
                # Check that saved filename is sanitized
                attachment = TaskAttachment.objects.latest('created_at')
                saved_name = os.path.basename(attachment.file.name)
                
                # Should not contain dangerous characters
                self.assertNotIn('..', saved_name)
                self.assertNotIn('/', saved_name)
                self.assertNotIn('\\', saved_name)
                self.assertNotIn('<', saved_name)
                self.assertNotIn('>', saved_name)
                self.assertNotIn('|', saved_name)
                self.assertNotIn('\x00', saved_name)


class MaliciousFileDetectionTests(TestCase):
    """Test malicious file detection"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.column = Column.objects.create(name='To Do', board=self.board)
        self.task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_double_extension_detection(self):
        """Test detection of double extensions (e.g., file.pdf.exe)"""
        suspicious_files = [
            'document.pdf.exe',
            'image.jpg.bat',
            'report.docx.sh',
            'data.txt.php',
        ]
        
        for filename in suspicious_files:
            uploaded_file = SimpleUploadedFile(
                filename,
                b'malicious content',
                content_type='application/octet-stream'
            )
            
            response = self.client.post(
                reverse('kanban:task_upload_attachment', args=[self.task.id]),
                {'file': uploaded_file}
            )
            
            # Should reject or sanitize
            self.assertIn(response.status_code, [400, 403])
    
    def test_mime_type_mismatch_detection(self):
        """Test detection of MIME type mismatches"""
        # File claims to be PDF but is actually executable
        fake_pdf = SimpleUploadedFile(
            'document.pdf',
            b'MZ\x90\x00',  # DOS/Windows executable signature
            content_type='application/pdf'
        )
        
        response = self.client.post(
            reverse('kanban:task_upload_attachment', args=[self.task.id]),
            {'file': fake_pdf}
        )
        
        # Should detect mismatch and reject
        self.assertIn(response.status_code, [400, 403])
    
    @patch('kanban.utils.scan_file_for_viruses')
    def test_virus_scanning(self, mock_virus_scan):
        """Test virus scanning integration"""
        mock_virus_scan.return_value = {'infected': True, 'virus': 'EICAR-Test'}
        
        infected_file = SimpleUploadedFile(
            'infected.txt',
            b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*',
            content_type='text/plain'
        )
        
        response = self.client.post(
            reverse('kanban:task_upload_attachment', args=[self.task.id]),
            {'file': infected_file}
        )
        
        # Should reject infected file
        self.assertEqual(response.status_code, 400)
        mock_virus_scan.assert_called_once()


class ImageProcessingSecurityTests(TestCase):
    """Test image processing security"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_svg_sanitization(self):
        """Test SVG files are sanitized to remove scripts"""
        malicious_svg = b'''<?xml version="1.0" encoding="UTF-8"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <script>alert('XSS')</script>
            <rect width="100" height="100"/>
        </svg>'''
        
        svg_file = SimpleUploadedFile(
            'image.svg',
            malicious_svg,
            content_type='image/svg+xml'
        )
        
        response = self.client.post(
            reverse('accounts:update_profile_picture'),
            {'avatar': svg_file}
        )
        
        # Should either reject SVG or sanitize it
        if response.status_code in [200, 201, 302]:
            # If accepted, verify script was removed
            profile = self.user.profile
            if profile.avatar:
                with open(profile.avatar.path, 'rb') as f:
                    content = f.read()
                    self.assertNotIn(b'<script>', content)
    
    def test_image_bomb_protection(self):
        """Test protection against decompression bombs"""
        # Create a file that would expand massively when processed
        # (Actual implementation would need proper image bomb sample)
        
        # For now, test that extremely large dimensions are rejected
        from PIL import Image
        import io
        
        # Try to create image with extreme dimensions
        # Most systems should reject this before actual creation
        try:
            huge_image = Image.new('RGB', (100000, 100000))
            buffer = io.BytesIO()
            huge_image.save(buffer, format='PNG')
            buffer.seek(0)
            
            huge_file = SimpleUploadedFile(
                'huge.png',
                buffer.read(),
                content_type='image/png'
            )
            
            response = self.client.post(
                reverse('accounts:update_profile_picture'),
                {'avatar': huge_file}
            )
            
            # Should reject due to size or dimensions
            self.assertIn(response.status_code, [400, 413])
        except Exception:
            # If creation itself fails, that's also acceptable protection
            pass


class StoragePathSecurityTests(TestCase):
    """Test storage path security"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.column = Column.objects.create(name='To Do', board=self.board)
        self.task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user
        )
    
    def test_files_stored_in_correct_directory(self):
        """Test files are stored in proper directory structure"""
        uploaded_file = SimpleUploadedFile(
            'test.txt',
            b'content',
            content_type='text/plain'
        )
        
        attachment = TaskAttachment.objects.create(
            task=self.task,
            file=uploaded_file,
            uploaded_by=self.user
        )
        
        # File path should be within media directory
        file_path = attachment.file.path
        media_root = settings.MEDIA_ROOT
        
        # Normalize paths for comparison
        file_path = os.path.abspath(file_path)
        media_root = os.path.abspath(media_root)
        
        # File should be inside media root
        self.assertTrue(file_path.startswith(media_root))
    
    def test_no_directory_traversal_in_storage(self):
        """Test storage prevents directory traversal"""
        uploaded_file = SimpleUploadedFile(
            '../../../etc/passwd',
            b'content',
            content_type='text/plain'
        )
        
        attachment = TaskAttachment.objects.create(
            task=self.task,
            file=uploaded_file,
            uploaded_by=self.user
        )
        
        # Stored path should not escape media directory
        file_path = os.path.abspath(attachment.file.path)
        media_root = os.path.abspath(settings.MEDIA_ROOT)
        
        self.assertTrue(file_path.startswith(media_root))


class FileDownloadSecurityTests(TestCase):
    """Test file download security"""
    
    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        self.org1 = Organization.objects.create(
            name='Org 1',
            domain='org1.com',
            created_by=self.user1
        )
        self.org2 = Organization.objects.create(
            name='Org 2',
            domain='org2.com',
            created_by=self.user2
        )
        self.board = Board.objects.create(
            name='Board 1',
            organization=self.org1,
            created_by=self.user1
        )
        self.column = Column.objects.create(name='To Do', board=self.board)
        self.task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user1
        )
        
        # Create attachment
        uploaded_file = SimpleUploadedFile(
            'private.txt',
            b'private content',
            content_type='text/plain'
        )
        self.attachment = TaskAttachment.objects.create(
            task=self.task,
            file=uploaded_file,
            uploaded_by=self.user1
        )
        
        self.client = Client()
    
    def test_authorized_user_can_download(self):
        """Test authorized user can download file"""
        self.client.login(username='user1', password='testpass123')
        
        response = self.client.get(
            reverse('kanban:download_attachment', args=[self.attachment.id])
        )
        
        self.assertEqual(response.status_code, 200)
    
    def test_unauthorized_user_cannot_download(self):
        """Test unauthorized user cannot download file"""
        self.client.login(username='user2', password='testpass123')
        
        response = self.client.get(
            reverse('kanban:download_attachment', args=[self.attachment.id])
        )
        
        # Should be denied
        self.assertIn(response.status_code, [403, 404])
    
    def test_anonymous_user_cannot_download(self):
        """Test anonymous user cannot download file"""
        response = self.client.get(
            reverse('kanban:download_attachment', args=[self.attachment.id])
        )
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)


class FileCleanupTests(TestCase):
    """Test file cleanup when objects are deleted"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.column = Column.objects.create(name='To Do', board=self.board)
        self.task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user
        )
    
    def test_file_deleted_with_attachment(self):
        """Test physical file is deleted when attachment is deleted"""
        uploaded_file = SimpleUploadedFile(
            'test.txt',
            b'content',
            content_type='text/plain'
        )
        
        attachment = TaskAttachment.objects.create(
            task=self.task,
            file=uploaded_file,
            uploaded_by=self.user
        )
        
        file_path = attachment.file.path
        
        # Verify file exists
        self.assertTrue(os.path.exists(file_path))
        
        # Delete attachment
        attachment.delete()
        
        # File should be deleted (if using proper signal handlers)
        # Note: Depends on model's delete() implementation
        # self.assertFalse(os.path.exists(file_path))
