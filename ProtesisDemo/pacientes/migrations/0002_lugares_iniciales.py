from django.db import migrations

LUGARES_INICIALES = [
    {"nombre": "Clínica Rosa – Sala de captura 1", "direccion": "Av. Universidad 102, Zacatecas"},
    {"nombre": "Hospital Regional – Consultorio 4", "direccion": "Calzada Solidaridad s/n, Guadalupe"},
    {"nombre": "Centro Oncológico Norte – Sala B", "direccion": "Blvd. Héroes de Chapultepec 300, Zacatecas"},
]


def crear_lugares_iniciales(apps, schema_editor):
    LugarCaptura = apps.get_model("pacientes", "LugarCaptura")
    for lugar in LUGARES_INICIALES:
        LugarCaptura.objects.get_or_create(
            nombre=lugar["nombre"],
            defaults={"direccion": lugar["direccion"], "activo": True},
        )


def eliminar_lugares_iniciales(apps, schema_editor):
    LugarCaptura = apps.get_model("pacientes", "LugarCaptura")
    nombres = [lugar["nombre"] for lugar in LUGARES_INICIALES]
    LugarCaptura.objects.filter(nombre__in=nombres).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("pacientes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(crear_lugares_iniciales, eliminar_lugares_iniciales),
    ]

