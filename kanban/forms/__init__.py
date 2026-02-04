from django import forms
from ..models import Board, Column, Task, TaskLabel, Comment, TaskFile
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime


class LocalDateTimeInput(forms.DateTimeInput):
    """
    Custom widget for datetime-local input that properly handles timezone-aware datetimes.
    This widget ensures that datetime values are displayed in the user's local timezone
    and properly parsed when submitted from the browser.
    """
    input_type = 'datetime-local'
    
    def format_value(self, value):
        """Format value for datetime-local input (YYYY-MM-DDTHH:MM)"""
        if value is None or value == '':
            return None
        
        # If value is a string, try to parse it first
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return None
        
        # Convert timezone-aware datetime to local timezone for display
        if timezone.is_aware(value):
            # Convert to local timezone for proper display
            value = timezone.localtime(value)
        
        # Format as YYYY-MM-DDTHH:MM for datetime-local input
        return value.strftime('%Y-%m-%dT%H:%M')


class BoardForm(forms.ModelForm):
    class Meta:
        model = Board
        fields = ['name', 'description', 'num_phases']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'num_phases': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 10,
                'placeholder': '0 = no phases, 3 = Phase 1, 2, 3',
                'title': 'Number of phases for organizing tasks in this board (0 to disable phases)'
            }),
        }
        help_texts = {
            'num_phases': 'Set the number of phases for your project (e.g., 3 for Phase 1, Phase 2, Phase 3). Set to 0 if you don\'t need phase-based organization.',
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
    # Add custom text fields for risk management
    risk_indicators_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter risk indicators to monitor, one per line (e.g., "Monitor task progress weekly", "Track team member availability")'
        }),
        help_text='Key indicators to monitor for this task (one per line)',
        label='Risk Indicators to Monitor'
    )
    
    mitigation_strategies_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter mitigation strategies, one per line (e.g., "Allocate additional resources if needed", "Conduct technical review early")'
        }),
        help_text='Strategies to mitigate identified risks (one per line)',
        label='Mitigation Strategies'
    )
    
    # Budget & Cost fields (stored in TaskCost model)
    estimated_cost = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0',
        }),
        help_text='Estimated cost for completing this task',
        label='Estimated Cost'
    )
    
    estimated_hours = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.0',
            'step': '0.5',
            'min': '0',
        }),
        help_text='Estimated hours to complete this task',
        label='Estimated Hours'
    )
    
    hourly_rate = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0',
        }),
        help_text='Hourly rate for labor cost calculation (optional - uses project default if not set)',
        label='Hourly Rate'
    )
    
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'phase',
            'start_date', 'due_date', 'assigned_to', 'labels', 'lss_classification', 'priority', 'progress',
            'dependencies', 'parent_task', 'complexity_score', 'required_skills', 'skill_match_score',
            'collaboration_required', 'workload_impact', 'related_tasks',
            'risk_likelihood', 'risk_impact', 'risk_level'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'phase': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_phase',
                'title': 'Select the phase this item belongs to'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'title': 'When this task should start (for Gantt chart)'
            }),
            'due_date': LocalDateTimeInput(attrs={
                'class': 'form-control',
                'title': 'When this task should be completed'
            }),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'labels': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'lss_classification': forms.RadioSelect(attrs={
                'class': 'form-check-input',
                'title': 'Lean Six Sigma classification - select ONE category'
            }),
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
            'parent_task': forms.Select(attrs={
                'class': 'form-select',
                'title': 'Select a parent task to create a subtask hierarchy'
            }),
            'complexity_score': forms.NumberInput(attrs={
                'class': 'form-control form-range',
                'type': 'range',
                'min': 1,
                'max': 10,
                'step': 1,
                'title': 'Task complexity from 1 (simple) to 10 (very complex)',
                'value': 5,
                'id': 'id_complexity_score'
            }),
            'required_skills': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter required skills as JSON list (e.g., [{"name": "Python", "level": "Advanced"}, {"name": "Django", "level": "Intermediate"}])',
                'title': 'List of required skills for this task'
            }),
            'skill_match_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 100,
                'step': 1,
                'title': 'Skill match score for the assigned user (0-100%)'
            }),
            'collaboration_required': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'title': 'Check if this task requires collaboration with other team members'
            }),
            'related_tasks': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': '4',
                'title': 'Select tasks that are related to this task (but not dependencies or parent-child)'
            }),
            'risk_likelihood': forms.Select(attrs={
                'class': 'form-select',
                'title': 'How likely is this risk to occur? (1=Low, 2=Medium, 3=High)'
            }),
            'risk_impact': forms.Select(attrs={
                'class': 'form-select',
                'title': 'What would be the impact if this risk occurs? (1=Low, 2=Medium, 3=High)'
            }),
            'risk_level': forms.Select(attrs={
                'class': 'form-select',
                'title': 'Overall risk classification for this task'
            }),
            'workload_impact': forms.Select(attrs={
                'class': 'form-select',
                'title': 'Estimated impact on assignee\'s workload'
            }),
        }
        
    def __init__(self, *args, **kwargs):
        board = kwargs.pop('board', None)
        super().__init__(*args, **kwargs)
        
        # Store board reference for duplicate detection in clean method
        self._board = board
        
        # Initialize risk indicators and mitigation strategies from JSON fields
        if self.instance and self.instance.pk:
            if self.instance.risk_indicators:
                # Handle both list of strings and list of dicts (new format with explainability)
                risk_lines = []
                for item in self.instance.risk_indicators:
                    if isinstance(item, dict):
                        # New format: {"indicator": "...", "frequency": "...", "threshold": "..."}
                        indicator = item.get('indicator', '')
                        frequency = item.get('frequency', '')
                        threshold = item.get('threshold', '')
                        if indicator:
                            line = indicator
                            if frequency:
                                line += f" (Monitor: {frequency})"
                            if threshold:
                                line += f" [Alert: {threshold}]"
                            risk_lines.append(line)
                    else:
                        # Old format: just a string
                        risk_lines.append(str(item))
                self.fields['risk_indicators_text'].initial = '\n'.join(risk_lines)
            
            if self.instance.mitigation_suggestions:
                # Handle both list of strings and list of dicts
                mitigation_lines = []
                for item in self.instance.mitigation_suggestions:
                    if isinstance(item, dict):
                        # New format: {"action": "...", "timeline": "...", "priority": "...", "expected_impact": "..."}
                        action = item.get('action', item.get('strategy', ''))
                        timeline = item.get('timeline', '')
                        priority = item.get('priority', '')
                        expected_impact = item.get('expected_impact', item.get('description', ''))
                        
                        if action:
                            line = action
                            if expected_impact:
                                line += f" - {expected_impact}"
                            if timeline:
                                line += f" (Timeline: {timeline})"
                            if priority:
                                line += f" [Priority: {priority}]"
                            mitigation_lines.append(line)
                    else:
                        mitigation_lines.append(str(item))
                
                if mitigation_lines:
                    self.fields['mitigation_strategies_text'].initial = '\n'.join(mitigation_lines)
            
            # Initialize budget fields from TaskCost model
            try:
                from kanban.budget_models import TaskCost
                task_cost = TaskCost.objects.filter(task=self.instance).first()
                if task_cost:
                    if task_cost.estimated_cost:
                        self.fields['estimated_cost'].initial = task_cost.estimated_cost
                    if task_cost.estimated_hours:
                        self.fields['estimated_hours'].initial = task_cost.estimated_hours
                    if task_cost.hourly_rate:
                        self.fields['hourly_rate'].initial = task_cost.hourly_rate
            except Exception:
                pass  # TaskCost doesn't exist yet, use defaults
        
        if board:
            # Filter out Lean Six Sigma labels - they have their own dedicated field
            self.fields['labels'].queryset = TaskLabel.objects.filter(board=board).exclude(category='lean')
            
            # Show all users (no board-level or organization restrictions - simplified access model)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            self.fields['assigned_to'].queryset = User.objects.all().order_by('username')
            
            # Filter dependencies to only show tasks from the same board with dates
            self.fields['dependencies'].queryset = Task.objects.filter(
                column__board=board,
                start_date__isnull=False,
                due_date__isnull=False
            ).exclude(id=self.instance.id if self.instance.pk else None).order_by('start_date', 'title')
            
            # Set help text for dependencies
            self.fields['dependencies'].help_text = 'Select tasks that must be completed before this task can start. Only tasks with start and due dates are shown (required for Gantt chart). Hold Ctrl/Cmd to select multiple.'
            
            # Filter related_tasks to only show tasks from the same board (exclude current task)
            self.fields['related_tasks'].queryset = Task.objects.filter(
                column__board=board
            ).exclude(id=self.instance.id if self.instance.pk else None).order_by('title')
            self.fields['related_tasks'].help_text = 'Select tasks that are related but not in a parent-child or dependency relationship. Hold Ctrl/Cmd to select multiple.'
            
            # Filter parent_task to only show tasks from the same board (exclude current task and its subtasks to prevent circular dependencies)
            parent_queryset = Task.objects.filter(column__board=board).exclude(id=self.instance.id if self.instance.pk else None)
            
            # If editing existing task, exclude all its subtasks to prevent circular dependencies
            if self.instance and self.instance.pk:
                subtask_ids = [st.id for st in self.instance.get_all_subtasks()]
                if subtask_ids:
                    parent_queryset = parent_queryset.exclude(id__in=subtask_ids)
            
            self.fields['parent_task'].queryset = parent_queryset.order_by('title')
            self.fields['parent_task'].help_text = 'Select a parent task to make this a subtask (creates hierarchical relationship).'
        else:
            # If no board, show all tasks with dates
            self.fields['dependencies'].queryset = Task.objects.filter(
                start_date__isnull=False,
                due_date__isnull=False
            ).exclude(id=self.instance.id if self.instance.pk else None).order_by('start_date', 'title')
            
            # related_tasks without board filter
            self.fields['related_tasks'].queryset = Task.objects.exclude(id=self.instance.id if self.instance.pk else None).order_by('title')
            
            # Parent task queryset without board filter
            self.fields['parent_task'].queryset = Task.objects.exclude(id=self.instance.id if self.instance.pk else None).order_by('title')
        
        # Add empty choice for assigned_to and parent_task
        self.fields['assigned_to'].empty_label = "Not assigned"
        self.fields['parent_task'].empty_label = "No parent (root task)"
        self.fields['dependencies'].required = False
        self.fields['related_tasks'].required = False
        self.fields['parent_task'].required = False
        self.fields['complexity_score'].required = False
        self.fields['progress'].required = False  # Progress defaults to 0 for new tasks

        # Configure phase field based on board's num_phases
        if board and board.num_phases > 0:
            # Build dynamic phase choices based on board's num_phases
            phase_choices = [('', '-- Select Phase --')]
            for i in range(1, board.num_phases + 1):
                phase_choices.append((f'Phase {i}', f'Phase {i}'))
            self.fields['phase'].widget = forms.Select(
                choices=phase_choices,
                attrs={'class': 'form-select', 'id': 'id_phase', 'title': 'Select the phase this item belongs to'}
            )
            self.fields['phase'].required = True
            self.fields['phase'].help_text = f'Select which phase this item belongs to (1-{board.num_phases}).'
        else:
            # Hide phase field if no phases configured for this board
            self.fields['phase'].widget = forms.HiddenInput()
            self.fields['phase'].required = False
        
        # Set initial value for complexity score if editing existing task
        if self.instance and self.instance.pk and self.instance.complexity_score:
            self.fields['complexity_score'].initial = self.instance.complexity_score
        
        # Set initial value for progress (0 for new tasks)
        if not self.instance.pk:
            self.fields['progress'].initial = 0
        
        # Set help text for complexity score
        self.fields['complexity_score'].help_text = 'Rate the task complexity from 1 (simple) to 10 (very complex). AI can suggest this value.'
        
        # Set help text for collaboration_required
        self.fields['collaboration_required'].help_text = 'Check this if the task requires collaboration with other team members'
        self.fields['collaboration_required'].required = False
        
        # Add help text and initialization for skill fields
        self.fields['required_skills'].required = False
        self.fields['required_skills'].help_text = 'Enter required skills as a JSON list. Format: [{"name": "Skill Name", "level": "Level"}]'
        
        self.fields['skill_match_score'].required = False
        self.fields['skill_match_score'].help_text = 'Percentage match of assignee skills to required skills (0-100%)'
        
        # Initialize required_skills field with JSON representation if editing
        if self.instance and self.instance.pk and self.instance.required_skills:
            import json
            try:
                self.fields['required_skills'].initial = json.dumps(self.instance.required_skills, indent=2)
            except:
                self.fields['required_skills'].initial = str(self.instance.required_skills)
        
        # Make risk fields optional
        self.fields['risk_likelihood'].required = False
        self.fields['risk_impact'].required = False
        self.fields['risk_level'].required = False
        
        # Add empty labels
        self.fields['risk_likelihood'].empty_label = "Not assessed"
        self.fields['risk_impact'].empty_label = "Not assessed"
        self.fields['risk_level'].empty_label = "Not assessed"
        
        # Make workload impact optional
        self.fields['workload_impact'].required = False
        
        # Add help text for risk fields
        self.fields['risk_likelihood'].help_text = 'Probability of risk occurring (optional - will auto-calculate risk score)'
        self.fields['risk_impact'].help_text = 'Severity if risk occurs (optional - will auto-calculate risk score)'
        self.fields['risk_level'].help_text = 'Overall risk classification (can be set manually or auto-calculated from likelihood × impact)'
        self.fields['workload_impact'].help_text = 'Estimated impact on the assignee\'s workload (Low, Medium, High, or Critical)'
    
    def clean_progress(self):
        """Validate that progress is between 0 and 100."""
        progress = self.cleaned_data.get('progress')
        if progress is not None:
            if progress < 0:
                raise forms.ValidationError("Progress cannot be negative.")
            if progress > 100:
                raise forms.ValidationError("Progress cannot exceed 100%.")
        return progress
    
    def clean_due_date(self):
        """
        Properly handle due_date from datetime-local input.
        Browser sends datetime as naive (without timezone), so we need to make it aware.
        """
        due_date = self.cleaned_data.get('due_date')
        if due_date and timezone.is_naive(due_date):
            # Make the naive datetime aware using the current timezone
            # This assumes the user entered the datetime in their local timezone
            due_date = timezone.make_aware(due_date, timezone.get_current_timezone())
        return due_date
    
    def clean(self):
        """Calculate risk_score automatically if likelihood and impact are provided, and validate parent_task"""
        cleaned_data = super().clean()
        risk_likelihood = cleaned_data.get('risk_likelihood')
        risk_impact = cleaned_data.get('risk_impact')
        risk_level = cleaned_data.get('risk_level')
        parent_task = cleaned_data.get('parent_task')
        title = cleaned_data.get('title')
        
        # Check for duplicate task titles in the same board
        if title and hasattr(self, '_board') and self._board:
            # Look for existing tasks with the same title in the board
            existing_tasks = Task.objects.filter(
                column__board=self._board,
                title__iexact=title  # Case-insensitive match
            )
            
            # Exclude current task if editing
            if self.instance and self.instance.pk:
                existing_tasks = existing_tasks.exclude(pk=self.instance.pk)
            
            # Store duplicate info for the view to handle
            if existing_tasks.exists():
                # Store duplicate tasks info in a non-field error attribute
                self._duplicate_tasks = list(existing_tasks[:5])  # Limit to 5 for display
                # Add a warning (not an error, so form can still be submitted)
                self.add_error(None, forms.ValidationError(
                    f'⚠️ Warning: {existing_tasks.count()} task(s) with the title "{title}" already exist in this board. '
                    'Are you sure you want to create a duplicate?',
                    code='duplicate_warning'
                ))
        
        # Validate parent_task to prevent circular dependencies
        if parent_task and self.instance:
            if parent_task == self.instance:
                raise forms.ValidationError({'parent_task': 'A task cannot be its own parent.'})
            
            # Check if this would create a circular dependency
            if hasattr(self.instance, 'has_circular_dependency') and self.instance.has_circular_dependency(parent_task):
                raise forms.ValidationError({
                    'parent_task': f'Cannot set "{parent_task.title}" as parent - this would create a circular dependency.'
                })
        
        # Auto-calculate risk score if both likelihood and impact are provided
        if risk_likelihood is not None and risk_impact is not None:
            risk_score = risk_likelihood * risk_impact
            cleaned_data['risk_score'] = risk_score
            
            # Auto-suggest risk level if not manually set
            if not risk_level:
                if risk_score >= 6:
                    cleaned_data['risk_level'] = 'critical'
                elif risk_score >= 4:
                    cleaned_data['risk_level'] = 'high'
                elif risk_score >= 2:
                    cleaned_data['risk_level'] = 'medium'
                else:
                    cleaned_data['risk_level'] = 'low'
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save the task with calculated risk_score and processed risk fields"""
        instance = super().save(commit=False)
        
        # Set risk_score from cleaned data if available
        if hasattr(self, 'cleaned_data') and 'risk_score' in self.cleaned_data:
            instance.risk_score = self.cleaned_data['risk_score']
        
        # Process required_skills JSON field - SECURITY: Only use safe JSON parsing, NO eval()
        required_skills_input = self.cleaned_data.get('required_skills', '')
        
        # Handle if it's already a list (from form submission)
        if isinstance(required_skills_input, list):
            # Validate and limit list items
            instance.required_skills = [str(skill)[:100] for skill in required_skills_input[:50]]
        else:
            required_skills_input = required_skills_input.strip() if isinstance(required_skills_input, str) else ''
            if required_skills_input:
                import json
                try:
                    # SECURITY: Only use JSON parsing - NEVER eval() for security
                    parsed_skills = json.loads(required_skills_input)
                    
                    # Validate it's a list
                    if isinstance(parsed_skills, list):
                        # Validate all items are strings and limit length
                        instance.required_skills = [
                            str(skill)[:100] for skill in parsed_skills 
                            if isinstance(skill, (str, int, float))
                        ][:50]  # Limit to 50 items
                    else:
                        instance.required_skills = []
                except (json.JSONDecodeError, ValueError, TypeError):
                    # If parsing fails, set to empty list (secure default)
                    instance.required_skills = []
            elif not instance.required_skills:
                instance.required_skills = []
        
        # Process risk indicators from text field
        risk_indicators_text = self.cleaned_data.get('risk_indicators_text', '').strip()
        if risk_indicators_text:
            # Split by newlines and filter out empty lines
            indicators = [line.strip() for line in risk_indicators_text.split('\n') if line.strip()]
            instance.risk_indicators = indicators
        elif not instance.risk_indicators:
            # Set to empty list if nothing provided and field is empty
            instance.risk_indicators = []
        
        # Process mitigation strategies from text field
        mitigation_text = self.cleaned_data.get('mitigation_strategies_text', '').strip()
        if mitigation_text:
            # Split by newlines and filter out empty lines
            mitigation_lines = [line.strip() for line in mitigation_text.split('\n') if line.strip()]
            
            # Try to parse structured format "Strategy: Description (Timeline)"
            mitigation_suggestions = []
            for line in mitigation_lines:
                # Try to parse structured format
                if ':' in line:
                    parts = line.split(':', 1)
                    strategy = parts[0].strip()
                    rest = parts[1].strip()
                    
                    # Extract timeline if present (text in parentheses at end)
                    timeline = ''
                    description = rest
                    if '(' in rest and rest.endswith(')'):
                        last_paren = rest.rfind('(')
                        timeline = rest[last_paren+1:-1].strip()
                        description = rest[:last_paren].strip()
                    
                    mitigation_suggestions.append({
                        'strategy': strategy,
                        'description': description,
                        'timeline': timeline
                    })
                else:
                    # If no colon, treat entire line as a simple mitigation
                    mitigation_suggestions.append({
                        'strategy': 'Mitigate',
                        'description': line,
                        'timeline': ''
                    })
            
            instance.mitigation_suggestions = mitigation_suggestions
        elif not instance.mitigation_suggestions:
            # Set to empty list if nothing provided and field is empty
            instance.mitigation_suggestions = []
        
        if commit:
            instance.save()
            # Save many-to-many relationships
            self.save_m2m()
            
            # Update dependency chain if parent_task was changed
            if 'parent_task' in self.cleaned_data:
                instance.update_dependency_chain()
            
            # Save budget/cost fields to TaskCost model
            self._save_task_cost(instance)
        
        return instance
    
    def _save_task_cost(self, task):
        """Save budget fields to TaskCost model"""
        from decimal import Decimal
        
        estimated_cost = self.cleaned_data.get('estimated_cost')
        estimated_hours = self.cleaned_data.get('estimated_hours')
        hourly_rate = self.cleaned_data.get('hourly_rate')
        
        # Only create/update TaskCost if at least one budget field has a value
        if estimated_cost is not None or estimated_hours is not None or hourly_rate is not None:
            try:
                from kanban.budget_models import TaskCost
                
                task_cost, created = TaskCost.objects.get_or_create(
                    task=task,
                    defaults={
                        'estimated_cost': estimated_cost or Decimal('0.00'),
                        'estimated_hours': estimated_hours or Decimal('0.00'),
                        'hourly_rate': hourly_rate,
                    }
                )
                
                if not created:
                    # Update existing TaskCost
                    if estimated_cost is not None:
                        task_cost.estimated_cost = estimated_cost
                    if estimated_hours is not None:
                        task_cost.estimated_hours = estimated_hours
                    if hourly_rate is not None:
                        task_cost.hourly_rate = hourly_rate
                    task_cost.save()
                    
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error saving TaskCost for task {task.id}: {e}")

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
            # Show all users instead of just board members
            self.fields['assignee'].queryset = User.objects.all().order_by('username')




class TaskFileForm(forms.ModelForm):
    """Form for uploading files to tasks with comprehensive security validation"""
    
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
