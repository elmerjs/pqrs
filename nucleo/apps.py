from django.apps import AppConfig


class NucleoConfig(AppConfig):
    print("--- ¡HOLA! EL ARCHIVO APPS.PY SE ESTÁ CARGANDO ---") # <-- AÑADE ESTA LÍNEA
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nucleo'

    def ready(self):
        import nucleo.signals # ¡Añade esta línea!
