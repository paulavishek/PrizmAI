from django import forms
from django.forms import inlineformset_factory
from ..models import WikiPage, WikiCategory, WikiAttachment, WikiLink, MeetingNotes


class WikiCategoryForm(forms.ModelForm):
    class Meta:
        model = WikiCategory
        fields = ['name', 'description', 'icon', 'color', 'position', 'ai_assistant_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Category description'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., folder, book, lightbulb'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'position': forms.NumberInput(attrs={'class': 'form-control'}),
            'ai_assistant_type': forms.Select(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'ai_assistant_type': 'Choose which AI assistant will be available for pages in this category. '
                               'Meeting Analysis for meeting notes, Documentation Assistant for guides/references, '
                               'or None to disable AI features.',
        }


class WikiPageForm(forms.ModelForm):
    class Meta:
        model = WikiPage
        fields = ['title', 'category', 'content', 'parent_page', 'is_published', 'is_pinned', 'tags']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Page title'
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={
                'class': 'form-control markdown-editor',
                'rows': 15,
                'placeholder': 'Enter page content (Markdown supported)',
                'data-provide': 'markdown'
            }),
            'parent_page': forms.Select(attrs={
                'class': 'form-control',
            }),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tags separated by commas',
                'data-role': 'tagsinput'
            }),
        }
    
    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            # Filter categories to organization
            self.fields['category'].queryset = WikiCategory.objects.filter(organization=organization)
            # Filter parent pages to organization
            self.fields['parent_page'].queryset = WikiPage.objects.filter(
                organization=organization
            ).exclude(pk=self.instance.pk if self.instance.pk else None)
    
    def clean_tags(self):
        """Convert comma-separated tags to list"""
        tags_str = self.cleaned_data.get('tags', '')
        if isinstance(tags_str, str):
            tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            return tags
        return tags_str


class WikiAttachmentForm(forms.ModelForm):
    class Meta:
        model = WikiAttachment
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.gif,.txt,.md'
            }),
        }


class WikiLinkForm(forms.ModelForm):
    task = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    board = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = WikiLink
        fields = ['link_type', 'description']
        widgets = {
            'link_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Why is this wiki page relevant to this item?'
            }),
        }
    
    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            from kanban.models import Board, Task
            # Filter tasks and boards to organization
            self.fields['task'].queryset = Task.objects.filter(column__board__organization=organization)
            self.fields['board'].queryset = Board.objects.filter(organization=organization)
    
    def clean(self):
        cleaned_data = super().clean()
        task = cleaned_data.get('task')
        board = cleaned_data.get('board')
        
        if not task and not board:
            raise forms.ValidationError('Please select either a task or a board.')
        
        if task and board:
            raise forms.ValidationError('Please select either a task or a board, not both.')
        
        return cleaned_data


# MEETING FEATURE DISABLED - MeetingNotesForm commented out
# class MeetingNotesForm(forms.ModelForm):
#     attendee_usernames = forms.CharField(
#         required=False,
#         widget=forms.TextInput(attrs={
#             'class': 'form-control',
#             'placeholder': 'Attendee usernames separated by commas',
#             'data-role': 'tagsinput'
#         }),
#         help_text='Enter usernames separated by commas'
#     )
#     
#     class Meta:
#         model = MeetingNotes
#         fields = ['title', 'meeting_type', 'date', 'content', 'transcript_text', 'transcript_file', 
#                   'related_board', 'duration_minutes', 'decisions']
#         widgets = {
#             'title': forms.TextInput(attrs={
#                 'class': 'form-control form-control-lg',
#                 'placeholder': 'Meeting title'
#             }),
#             'meeting_type': forms.Select(attrs={'class': 'form-control'}),
#             'date': forms.DateTimeInput(attrs={
#                 'class': 'form-control',
#                 'type': 'datetime-local'
#             }),
#             'content': forms.Textarea(attrs={
#                 'class': 'form-control markdown-editor',
#                 'rows': 10,
#                 'placeholder': 'Enter meeting notes (Markdown supported)'
#             }),
#             'transcript_text': forms.Textarea(attrs={
#                 'class': 'form-control',
#                 'rows': 8,
#                 'placeholder': 'Paste meeting transcript here for AI analysis'
#             }),
#             'transcript_file': forms.FileInput(attrs={
#                 'class': 'form-control',
#                 'accept': '.txt,.pdf,.docx'
#             }),
#             'related_board': forms.Select(attrs={'class': 'form-control'}),
#             'duration_minutes': forms.NumberInput(attrs={
#                 'class': 'form-control',
#                 'placeholder': 'Duration in minutes'
#             }),
#             'decisions': forms.TextInput(attrs={
#                 'class': 'form-control',
#                 'placeholder': 'Decisions separated by commas',
#                 'data-role': 'tagsinput'
#             }),
#         }
#     
#     def __init__(self, *args, organization=None, **kwargs):
#         super().__init__(*args, **kwargs)
#         if organization:
#             from kanban.models import Board
#             self.fields['related_board'].queryset = Board.objects.filter(organization=organization)
#     
#     def clean_decisions(self):
#         """Convert comma-separated decisions to list"""
#         decisions_str = self.cleaned_data.get('decisions', '')
#         if isinstance(decisions_str, str):
#             decisions = [d.strip() for d in decisions_str.split(',') if d.strip()]
#             return decisions
#         return decisions_str


class WikiPageSearchForm(forms.Form):
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search wiki pages...'
        })
    )
    category = forms.ModelChoiceField(
        queryset=WikiCategory.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    tag = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by tag'
        })
    )
    
    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields['category'].queryset = WikiCategory.objects.filter(organization=organization)


# Inline formsets for attachments
WikiPageAttachmentFormSet = inlineformset_factory(
    WikiPage,
    WikiAttachment,
    form=WikiAttachmentForm,
    extra=1,
    can_delete=True
)


class QuickWikiLinkForm(forms.Form):
    """Quick form to link a task/board to wiki pages"""
    wiki_pages = forms.ModelMultipleChoiceField(
        queryset=WikiPage.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False
    )
    link_description = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Why are these pages relevant?'
        })
    )
    
    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            from django.db.models import Q
            from accounts.models import Organization
            
            # Include demo organization pages along with user's org pages
            demo_org_names = ['Demo - Acme Corporation']
            demo_orgs = Organization.objects.filter(name__in=demo_org_names)
            
            self.fields['wiki_pages'].queryset = WikiPage.objects.filter(
                Q(organization=organization) | Q(organization__in=demo_orgs),
                is_published=True
            )
