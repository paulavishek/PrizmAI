"""
API Serializers for v1
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from kanban.models import Board, Column, Task, TaskLabel, Comment
from accounts.models import UserProfile, Organization


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    organization = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'organization']
        read_only_fields = ['id', 'username', 'email']
    
    def get_organization(self, obj):
        if hasattr(obj, 'profile') and obj.profile.organization:
            return {
                'id': obj.profile.organization.id,
                'name': obj.profile.organization.name
            }
        return None


class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for Organization model"""
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Organization
        fields = ['id', 'name', 'domain', 'created_at', 'member_count']
        read_only_fields = ['id', 'created_at']
    
    def get_member_count(self, obj):
        return obj.members.count()


class TaskLabelSerializer(serializers.ModelSerializer):
    """Serializer for TaskLabel model"""
    
    class Meta:
        model = TaskLabel
        fields = ['id', 'name', 'color', 'category']
        read_only_fields = ['id']


class ColumnSerializer(serializers.ModelSerializer):
    """Serializer for Column model"""
    task_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Column
        fields = ['id', 'name', 'position', 'task_count']
        read_only_fields = ['id']
    
    def get_task_count(self, obj):
        return obj.tasks.count()


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for Task model"""
    assigned_to_user = UserSerializer(source='assigned_to', read_only=True)
    created_by_user = UserSerializer(source='created_by', read_only=True)
    labels = TaskLabelSerializer(many=True, read_only=True)
    label_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        queryset=TaskLabel.objects.all(),
        source='labels',
        required=False
    )
    column_name = serializers.CharField(source='column.name', read_only=True)
    board_id = serializers.IntegerField(source='column.board.id', read_only=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'column', 'column_name', 'board_id',
            'position', 'created_at', 'updated_at', 'start_date', 'due_date',
            'assigned_to', 'assigned_to_user', 'created_by', 'created_by_user',
            'labels', 'label_ids', 'priority', 'progress', 'ai_risk_score',
            'required_skills', 'skill_match_score'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def create(self, validated_data):
        # Set created_by from request user
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class TaskListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for task lists"""
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True)
    column_name = serializers.CharField(source='column.name', read_only=True)
    label_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'column', 'column_name', 'priority', 'progress',
            'assigned_to', 'assigned_to_username', 'due_date', 'label_count',
            'created_at', 'updated_at'
        ]
    
    def get_label_count(self, obj):
        return obj.labels.count()


class BoardSerializer(serializers.ModelSerializer):
    """Serializer for Board model"""
    created_by_user = UserSerializer(source='created_by', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    columns = ColumnSerializer(many=True, read_only=True)
    member_count = serializers.SerializerMethodField()
    task_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Board
        fields = [
            'id', 'name', 'description', 'organization', 'organization_name',
            'created_at', 'created_by', 'created_by_user', 'columns',
            'member_count', 'task_count', 'members'
        ]
        read_only_fields = ['id', 'created_at', 'created_by']
    
    def get_member_count(self, obj):
        return obj.members.count()
    
    def get_task_count(self, obj):
        return Task.objects.filter(column__board=obj).count()
    
    def create(self, validated_data):
        # Set created_by from request user
        validated_data['created_by'] = self.context['request'].user
        # Set organization from user's profile
        user = self.context['request'].user
        if hasattr(user, 'profile'):
            validated_data['organization'] = user.profile.organization
        return super().create(validated_data)


class BoardListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for board lists"""
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    task_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Board
        fields = ['id', 'name', 'description', 'organization_name', 'created_at', 'task_count']
    
    def get_task_count(self, obj):
        return Task.objects.filter(column__board=obj).count()


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for Comment model"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Comment
        fields = ['id', 'task', 'user', 'content', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class APITokenSerializer(serializers.Serializer):
    """Serializer for creating API tokens"""
    name = serializers.CharField(max_length=100)
    scopes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    expires_in_days = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=365,
        help_text="Number of days until token expires (omit for no expiration)"
    )
