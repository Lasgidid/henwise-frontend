def site(request):
    """Values every template can use.

    TODO(backend): take `role` from request.user (e.g. a group or a profile
    field) and `farm_name` from the user's farm. `today_label` should be the
    real date.
    """
    role = request.session.get("role", "admin")
    return {
        "brand": "Henwise",  # working product name, change in one place
        "farm_name": "Green Acre Farm",
        "today_label": "Oct 27, 2026",
        "role": role,
        "is_admin": role == "admin",
    }
