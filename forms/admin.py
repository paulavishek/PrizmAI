from django.contrib import admin

from .models import Form, FormField, FormSubmission, FormAnswer


class FormFieldInline(admin.TabularInline):
    model = FormField
    extra = 0


@admin.register(Form)
class FormAdmin(admin.ModelAdmin):
    list_display = ('title', 'workspace', 'target_destination', 'is_active', 'created_by', 'created_at')
    list_filter = ('target_destination', 'is_active')
    search_fields = ('title',)
    inlines = [FormFieldInline]


class FormAnswerInline(admin.TabularInline):
    model = FormAnswer
    extra = 0


@admin.register(FormSubmission)
class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = ('form', 'submitter_user', 'created_idea', 'created_task', 'created_at')
    inlines = [FormAnswerInline]
