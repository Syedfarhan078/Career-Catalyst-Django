from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
    )

    fieldsets = UserAdmin.fieldsets + (
        (
            "Career Catalyst",
            {
                "fields": (
                    "profile_picture",
                    "bio",
                    "github",
                    "linkedin",
                )
            },
        ),
    )