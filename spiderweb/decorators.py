def csrf_exempt(func):
    """Mark a view as not requiring CSRF verification on POST requests."""
    func.csrf_exempt = True
    return func
