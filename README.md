# Sistema de Gestión del Laboratorio de Ergonomía INTERFA-C

Aplicación Streamlit para gestionar proyectos, reservas, cierres operativos, validación administrativa, constancias y evidencias del Laboratorio de Ergonomía INTERFA-C.

## Archivos principales

- `app.py`: aplicación principal.
- `requirements.txt`: dependencias para Streamlit Cloud.
- `.gitignore`: evita subir bases de datos, evidencias y constancias generadas.

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Despliegue en Streamlit Cloud

1. Subir este repositorio a GitHub.
2. Entrar a Streamlit Cloud.
3. Crear una nueva app desde el repositorio.
4. Seleccionar `app.py`.
5. Deploy.

## Clave de administrador inicial

```text
interfac2026
```

Se recomienda cambiarla dentro del archivo `app.py` antes de publicar.

## Nota importante sobre persistencia

Esta versión genera constancias descargables y permite exportar constancias mensuales en ZIP. En Streamlit Cloud, el almacenamiento local puede no ser permanente. Para uso institucional estable se recomienda migrar luego a Supabase/PostgreSQL y Google Drive API.
