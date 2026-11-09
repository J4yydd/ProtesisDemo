from django.db import migrations

ROLES_INICIALES = [
    "Operador",
    "Administrador",
    "Doctor",
    "Enfermera",
    "Psicóloga",
    "Modelador",
    "Investigador",
]


def crear_roles_iniciales(apps, schema_editor):
    Rol = apps.get_model("usuarios", "Rol")
    for nombre in ROLES_INICIALES:
        Rol.objects.get_or_create(nombre=nombre)


def eliminar_roles_iniciales(apps, schema_editor):
    Rol = apps.get_model("usuarios", "Rol")
    Rol.objects.filter(nombre__in=ROLES_INICIALES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_roles_iniciales, eliminar_roles_iniciales),
    ]
