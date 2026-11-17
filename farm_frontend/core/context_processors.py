def site(request):
    """Values every template can use.

    Role is derived from Django's authenticated user.
    """
    from django.utils import timezone
    role = "admin" if request.user.is_authenticated and request.user.is_staff else "worker"
    return {
        "brand": "Henwise",  # working product name, change in one place
        "farm_name": "Green Acre Farm",
        "today_label": timezone.localdate().strftime("%b %d, %Y"),
        "role": role,
        "is_admin": role == "admin",
    }
