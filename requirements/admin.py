from django.contrib import admin

from .models import (
    ProjectObjective,
    Requirement,
    RequirementCategory,
    RequirementComment,
    RequirementHistory,
)


class RequirementHistoryInline(admin.TabularInline):
    model = RequirementHistory
    extra = 0
    readonly_fields = ('old_status', 'new_status', 'changed_by', 'timestamp', 'notes')


class RequirementCommentInline(admin.TabularInline):
    model = RequirementComment
    extra = 0
    readonly_fields = ('author', 'created_at')


@admin.register(RequirementCategory)
class RequirementCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'board', 'description')
    list_filter = ('board',)
    search_fields = ('name',)


@admin.register(ProjectObjective)
class ProjectObjectiveAdmin(admin.ModelAdmin):
    list_display = ('title', 'board', 'created_by', 'created_at')
    list_filter = ('board',)
    search_fields = ('title',)


@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'title', 'board', 'type', 'status', 'priority', 'created_by', 'created_at')
    list_filter = ('board', 'status', 'type', 'priority', 'category')
    search_fields = ('identifier', 'title', 'description')
    inlines = [RequirementHistoryInline, RequirementCommentInline]
    readonly_fields = ('identifier', 'created_at', 'updated_at')


@admin.register(RequirementHistory)
class RequirementHistoryAdmin(admin.ModelAdmin):
    list_display = ('requirement', 'old_status', 'new_status', 'changed_by', 'timestamp')
    list_filter = ('new_status',)
    readonly_fields = ('requirement', 'old_status', 'new_status', 'changed_by', 'timestamp', 'notes')
