from django import forms
from ..models import Board, Column, Task, TaskLabel, Comment, TaskFile

class BoardForm(forms.ModelForm):
    class Meta:
        model = Board
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class ColumnForm(forms.ModelForm):
    class Meta:
        model = Column
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }

class TaskLabelForm(forms.ModelForm):
    class Meta:
        model = TaskLabel
        fields = ['name', 'color', 'category']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'start_date', 'due_date', 'assigned_to', 'labels', 'priority', 'progress', 'dependencies'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date',
                'title': 'When this task should start (for Gantt chart)'
            }),
            'due_date': forms.DateTimeInput(attrs={
                'class': 'form-control', 
                'type': 'datetime-local',
                'title': 'When this task should be completed'
            }),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'labels': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'progress': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 100,
                'title': 'Task completion progress (0-100%)'
            }),
            'dependencies': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': '5',
                'title': 'Tasks that must be completed before this task can start (for Gantt chart dependencies)'
            }),
        }
        
    def __init__(self, *args, **kwargs):
        board = kwargs.pop('board', None)
        super().__init__(*args, **kwargs)
        
        if board:
            self.fields['labels'].queryset = TaskLabel.objects.filter(board=board)
            self.fields['assigned_to'].queryset = board.members.all()
            
            # Filter dependencies to only show tasks from the same board with dates
            self.fields['dependencies'].queryset = Task.objects.filter(
                column__board=board,
                start_date__isnull=False,
                due_date__isnull=False
            ).exclude(id=self.instance.id if self.instance.pk else None).order_by('start_date', 'title')
            
            # Set help text for dependencies
            self.fields['dependencies'].help_text = 'Select tasks that must be completed before this task can start. Hold Ctrl/Cmd to select multiple tasks.'
        else:
            # If no board, show all tasks with dates
            self.fields['dependencies'].queryset = Task.objects.filter(
                start_date__isnull=False,
                due_date__isnull=False
            ).exclude(id=self.instance.id if self.instance.pk else None).order_by('start_date', 'title')
        
        # Add empty choice for assigned_to
        self.fields['assigned_to'].empty_label = "Not assigned"
        self.fields['dependencies'].required = False

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Add a comment...'}),
        }

class TaskMoveForm(forms.Form):
    column = forms.ModelChoiceField(queryset=None, widget=forms.Select(attrs={'class': 'form-select'}))
    position = forms.IntegerField(widget=forms.NumberInput(attrs={'class': 'form-control'}))
    
    def __init__(self, *args, **kwargs):
        board = kwargs.pop('board', None)
        super().__init__(*args, **kwargs)
        
        if board:
            self.fields['column'].queryset = Column.objects.filter(board=board)

class TaskSearchForm(forms.Form):
    column = forms.ModelChoiceField(
        queryset=Column.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    priority = forms.ChoiceField(
        choices=[('', 'Any Priority')] + Task.PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    label = forms.ModelChoiceField(
        queryset=TaskLabel.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    label_category = forms.ChoiceField(
        choices=[
            ('', 'Any Category'),
            ('regular', 'Regular Labels'),
            ('lean', 'Lean Six Sigma Labels'),
            ('lean_va', 'Value-Added'),
            ('lean_nva', 'Necessary Non-Value-Added'),
            ('lean_waste', 'Waste/Eliminate')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    assignee = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    search_term = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search tasks...'})
    )
    
    def __init__(self, *args, **kwargs):
        board = kwargs.pop('board', None)
        super().__init__(*args, **kwargs)
        
        if board:
            self.fields['column'].queryset = Column.objects.filter(board=board)
            self.fields['label'].queryset = TaskLabel.objects.filter(board=board)
            self.fields['assignee'].queryset = board.members.all()


class TaskFileForm(forms.ModelForm):
    """Form for uploading files to tasks"""
    
    class Meta:
        model = TaskFile
        fields = ['file', 'description']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png',
                'id': 'task-file-input'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional: Add a description for this file',
                'maxlength': '500'
            })
        }
    
    def clean_file(self):
        """Validate file type and size"""
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file size
            if file.size > TaskFile.MAX_FILE_SIZE:
                raise forms.ValidationError(
                    f'File size exceeds {TaskFile.MAX_FILE_SIZE / (1024*1024):.0f}MB limit'
                )
            
            # Check file type
            if not TaskFile.is_valid_file_type(file.name):
                allowed = ', '.join(TaskFile.ALLOWED_FILE_TYPES)
                raise forms.ValidationError(
                    f'Invalid file type. Allowed types: {allowed}'
                )
        
        return file


class TaskFileForm(forms.ModelForm):
    """Form for uploading files to tasks"""
    
    class Meta:
        model = TaskFile
        fields = ['file', 'description']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png',
                'id': 'task-file-input'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional: Add a description for this file',
                'maxlength': '500'
            })
        }
    
    def clean_file(self):
        """Validate file type and size"""
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file size
            if file.size > TaskFile.MAX_FILE_SIZE:
                raise forms.ValidationError(
                    f'File size exceeds {TaskFile.MAX_FILE_SIZE / (1024*1024):.0f}MB limit'
                )
            
            # Check file type
            if not TaskFile.is_valid_file_type(file.name):
                allowed = ', '.join(TaskFile.ALLOWED_FILE_TYPES)
                raise forms.ValidationError(
                    f'Invalid file type. Allowed types: {allowed}'
                )
        
        return file