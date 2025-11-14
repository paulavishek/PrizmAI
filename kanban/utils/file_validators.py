"""
Secure file upload validators
Comprehensive file validation to prevent malicious uploads
"""
import magic
import os
from django.core.exceptions import ValidationError


class FileValidator:
    """Comprehensive file upload validation with security checks"""
    
    # Allowed MIME types with their extensions
    ALLOWED_TYPES = {
        'application/pdf': ['pdf'],
        'application/msword': ['doc'],
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['docx'],
        'application/vnd.ms-excel': ['xls'],
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['xlsx'],
        'application/vnd.ms-powerpoint': ['ppt'],
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['pptx'],
        'image/jpeg': ['jpg', 'jpeg'],
        'image/png': ['png'],
        'image/gif': ['gif'],
        'text/plain': ['txt'],
        'text/csv': ['csv'],
    }
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    @classmethod
    def validate_file(cls, uploaded_file):
        """
        Comprehensive file validation with security checks
        
        Args:
            uploaded_file: Django UploadedFile object
            
        Raises:
            ValidationError: If file is invalid or potentially malicious
        """
        # 1. Check file size
        if uploaded_file.size > cls.MAX_FILE_SIZE:
            raise ValidationError(
                f'File too large. Maximum size is {cls.MAX_FILE_SIZE / (1024*1024):.1f}MB'
            )
        
        if uploaded_file.size == 0:
            raise ValidationError('File is empty')
        
        # 2. Check file extension
        filename = uploaded_file.name
        ext = cls._get_extension(filename)
        
        if not ext:
            raise ValidationError('File has no extension')
        
        # 3. Validate filename for security
        cls._validate_filename(filename)
        
        # 4. Check MIME type from content (magic bytes) - prevents extension spoofing
        uploaded_file.seek(0)
        file_content = uploaded_file.read(8192)  # Read first 8KB
        uploaded_file.seek(0)
        
        try:
            mime = magic.from_buffer(file_content, mime=True)
        except Exception as e:
            raise ValidationError(f'Unable to determine file type: {str(e)}')
        
        # 5. Verify MIME type is in allowed list
        if mime not in cls.ALLOWED_TYPES:
            raise ValidationError(
                f'File type not allowed: {mime}. Allowed types: PDF, Word, Excel, PowerPoint, Images, Text'
            )
        
        # 6. Verify extension matches MIME type (prevent spoofing)
        allowed_extensions = cls.ALLOWED_TYPES[mime]
        if ext not in allowed_extensions:
            raise ValidationError(
                f'File extension .{ext} does not match content type {mime}. Possible file spoofing detected.'
            )
        
        # 7. Additional security checks for malicious content
        cls._check_malicious_content(file_content, mime, ext)
        
        return True
    
    @staticmethod
    def _get_extension(filename):
        """Extract file extension safely"""
        if '.' not in filename:
            return None
        return filename.rsplit('.', 1)[1].lower()
    
    @staticmethod
    def _validate_filename(filename):
        """Validate filename for security vulnerabilities"""
        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            raise ValidationError('Invalid filename: path traversal detected')
        
        # Check for null bytes (used in null byte injection attacks)
        if '\x00' in filename:
            raise ValidationError('Invalid filename: null bytes detected')
        
        # Check length
        if len(filename) > 255:
            raise ValidationError('Filename too long (max 255 characters)')
        
        # Check for suspicious characters
        suspicious_chars = ['<', '>', ':', '"', '|', '?', '*']
        if any(char in filename for char in suspicious_chars):
            raise ValidationError('Filename contains invalid characters')
        
        # Check for hidden files or system files
        if filename.startswith('.'):
            raise ValidationError('Hidden files are not allowed')
    
    @staticmethod
    def _check_malicious_content(content, mime, ext):
        """Check for malicious content patterns in files"""
        # Check for embedded scripts in images
        if mime.startswith('image/'):
            dangerous_patterns = [
                b'<?php',
                b'<script',
                b'javascript:',
                b'onerror=',
                b'onload=',
                b'<html',
                b'<body',
            ]
            
            content_lower = content.lower()
            for pattern in dangerous_patterns:
                if pattern in content_lower:
                    raise ValidationError('Suspicious content detected in image file')
        
        # Check for executable content in text files
        if mime == 'text/plain':
            dangerous_patterns = [
                b'#!/bin/bash',
                b'#!/bin/sh',
                b'@echo off',
                b'<?php',
            ]
            
            for pattern in dangerous_patterns:
                if content.startswith(pattern):
                    raise ValidationError('Executable scripts are not allowed in text files')
    
    @staticmethod
    def sanitize_filename(filename):
        """Sanitize filename to prevent security issues"""
        # Remove path components
        filename = os.path.basename(filename)
        
        # Replace spaces and special characters with underscores
        filename = filename.replace(' ', '_')
        
        # Remove any remaining dangerous characters
        safe_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-'
        filename = ''.join(c if c in safe_chars else '_' for c in filename)
        
        # Ensure filename doesn't start with dot or dash
        if filename.startswith(('.', '-', '_')):
            filename = 'file_' + filename
        
        # Limit length while preserving extension
        if len(filename) > 100:
            name_parts = filename.rsplit('.', 1)
            if len(name_parts) == 2:
                name, ext = name_parts
                filename = name[:95] + '.' + ext
            else:
                filename = filename[:100]
        
        return filename
    
    @classmethod
    def get_allowed_extensions(cls):
        """Get list of all allowed file extensions"""
        extensions = set()
        for ext_list in cls.ALLOWED_TYPES.values():
            extensions.update(ext_list)
        return sorted(extensions)
