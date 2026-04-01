from django.apps import AppConfig


class AuthappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'authapp'
    verbose_name = 'Authentication'

    def ready(self):
        # Import signals when the app is ready
        import authapp.signals
