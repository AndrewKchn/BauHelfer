"""Admin pages for user accounts."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .forms import UserAdminChangeForm, UserAdminCreationForm, WorkerProfileForm
from .models import User, WorkerProfile


class WorkerProfileInline(admin.StackedInline):
    """The worker profile, edited right on the user's admin page (#11)."""

    model = WorkerProfile
    form = WorkerProfileForm  # checkboxes for skills and languages, as on the site


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Django's user admin, adapted to email login and BauHelfer fields."""

    form = UserAdminChangeForm
    add_form = UserAdminCreationForm

    list_display = ("email", "name", "role", "preferred_language", "is_staff")
    list_filter = ("role", "preferred_language", "is_staff", "is_active")
    search_fields = ("email", "name", "phone")
    ordering = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Profile"),
            {
                "fields": (
                    "name",
                    "phone",
                    "role",
                    "preferred_language",
                    "work_permit_confirmed",
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    # The "Add user" page: only what is needed to create an account.
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "usable_password", "password1", "password2"),
            },
        ),
    )

    def get_inlines(self, request, obj):
        """Show the worker profile only on the page of an existing worker."""
        if obj is not None and obj.role == User.Role.WORKER:
            return [WorkerProfileInline]
        return []
