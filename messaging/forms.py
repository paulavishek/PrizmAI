from django import forms
from django.db.models import Q
from .models import TaskThreadComment, ChatRoom, ChatMessage, FileAttachment
from django.contrib.auth.models import User


class TaskThreadCommentForm(forms.ModelForm):
    """Form for adding real-time comments to tasks"""
    
    class Meta:
        model = TaskThreadComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add a comment... (use @username to mention someone)',
                'style': 'resize: vertical;'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].label = 'Comment'


class ChatRoomForm(forms.ModelForm):
    """Form for creating/editing chat rooms"""
    required_css_class = 'required'
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Add members to this room'
    )
    
    class Meta:
        model = ChatRoom
        fields = ['name', 'description', 'members']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Room name (e.g., #frontend-team)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'What is this room about?'
            })
        }
    
    def __init__(self, *args, board=None, **kwargs):
        super().__init__(*args, **kwargs)
        if board:
            if board.is_official_demo_board or board.is_sandbox_copy or (
                board.workspace_id and board.workspace.is_demo
            ):
                # Demo/sandbox boards only ever have the demo personas plus
                # the sandbox owner (board creator) as candidate members —
                # every other active account in the system (other testers'
                # real logins, fixtures, etc.) isn't part of this sandbox
                # and must not be offered here.
                users = User.objects.filter(is_active=True).filter(
                    Q(profile__is_demo_account=True) | Q(id=board.created_by_id)
                )
            else:
                users = User.objects.filter(is_active=True).exclude(id=board.created_by_id)
            if self.instance.pk:
                # A room's current members must always stay selectable.
                # ModelForm.save() replaces the members set with exactly
                # what's submitted, so anyone missing from the rendered
                # checkboxes would be silently removed from the room.
                users = users | self.instance.members.filter(is_active=True)
            self.fields['members'].queryset = users.distinct()
            self.fields['members'].help_text = (
                'Selected users will be added to the room immediately and notified.'
            )


class ChatMessageForm(forms.ModelForm):
    """Form for sending messages in a chat room"""
    
    class Meta:
        model = ChatMessage
        fields = ['content']
        widgets = {
            'content': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Type a message... (use @username to mention)',
                'autocomplete': 'off'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].label = ''


class MentionForm(forms.Form):
    """Form for autocomplete mentions"""
    search = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Search users...',
            'autocomplete': 'off'
        })
    )


class ChatRoomFileForm(forms.ModelForm):
    """Form for uploading files to chat rooms with comprehensive security validation"""
    
    class Meta:
        model = FileAttachment
        fields = ['file', 'description']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png',
                'id': 'chat-file-input'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional: Add a description for this file',
                'maxlength': '500'
            })
        }
    
    def clean_file(self):
        """Validate file with comprehensive security checks"""
        from kanban.utils.file_validators import FileValidator
        from django.core.exceptions import ValidationError as DjangoValidationError
        
        file = self.cleaned_data.get('file')
        
        if not file:
            raise forms.ValidationError('No file provided')
        
        # Comprehensive security validation
        try:
            FileValidator.validate_file(file)
        except DjangoValidationError as e:
            raise forms.ValidationError(str(e))
        
        return file
    
    def save(self, commit=True):
        from kanban.utils.file_validators import FileValidator
        
        instance = super().save(commit=False)
        
        if self.cleaned_data.get('file'):
            file = self.cleaned_data['file']
            
            # Sanitize filename for security
            instance.filename = FileValidator.sanitize_filename(file.name)
            instance.file_size = file.size
            instance.file_type = FileValidator._get_extension(file.name)
        
        if commit:
            instance.save()
        
        return instance
