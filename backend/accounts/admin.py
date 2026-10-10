from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import StudentProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "role", "timezone", "is_active"]
    list_filter = ["role", "is_active"]
    search_fields = ["email", "first_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("first_name", "last_name", "role", "timezone")}),
        ("Access", {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
    )
    add_fieldsets = ((None, {"fields": ("email", "first_name", "role", "password1", "password2")}),)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "sass_level", "supportive_mode", "onboarding_done"]
