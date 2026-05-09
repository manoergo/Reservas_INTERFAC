import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, time, timedelta
from pathlib import Path
import secrets
import string
import base64
import zipfile
from io import BytesIO

# =========================================================
# SISTEMA DE GESTIÓN DEL LABORATORIO DE ERGONOMÍA INTERFA-C
# Versión PROYECTOS:
# - Registro maestro de proyectos
# - Código maestro por proyecto
# - Reservas asociadas al proyecto
# - Reservas puntuales y recurrentes
# - Horario semanal visual
# - Consulta de reservas aprobadas por código de proyecto
# - Cierre operativo por código maestro de proyecto
# - Cierre enviado NO finaliza oficialmente
# - Validación final del administrador
# - Constancia HTML de reserva aprobada
# - Constancia HTML final de cierre validado
# - Evidencias adjuntas visibles y descargables
# - Exportación protegida por administrador
# =========================================================

DB_PATH = "laboratorio_interfac_proyectos.db"
EVIDENCE_DIR = Path("evidencias_laboratorio")
EVIDENCE_DIR.mkdir(exist_ok=True)

DOCUMENTS_DIR = Path("documentos_laboratorio")
(DOCUMENTS_DIR / "proyectos").mkdir(parents=True, exist_ok=True)
(DOCUMENTS_DIR / "reservas").mkdir(parents=True, exist_ok=True)
(DOCUMENTS_DIR / "cierres").mkdir(parents=True, exist_ok=True)

ADMIN_PASSWORD = "interfac2026"

RECURSOS = [
    "EMG Trigno",
    "EMG PLUX",
    "VO2 Master",
    "Mesa regulable",
    "Xsens",
    "Meta Quest",
    "Equipos de antropometría",
    "Solo espacio / sin equipo específico",
]

TIPOS_ACTIVIDAD = [
    "Proyecto de investigación",
    "Tesis de pregrado",
    "Tesis de posgrado",
    "Práctica de pregrado",
    "Práctica de posgrado",
    "Capacitación",
    "Mantenimiento",
    "Reunión / demostración",
    "Otro",
]

ESTADOS_PROYECTO = ["Activo", "Pausado", "Finalizado", "Cancelado"]

ESTADOS_RESERVA = [
    "Pendiente",
    "Aprobado",
    "Rechazado",
    "Reprogramar",
    "Cancelado",
    "Cierre enviado",
    "Cierre observado",
    "Subsanación requerida",
    "Finalizado",
]

ESTADOS_CIERRE_OPERATIVO = [
    "Finalizado correctamente",
    "Finalizado con incidencias",
    "Realizado parcialmente",
    "No se realizó",
    "Suspendido",
    "Reprogramado",
    "Cancelado",
]

ESTADOS_VALIDACION_CIERRE = [
    "Pendiente de validación",
    "Validado",
    "Observado",
    "Subsanación requerida",
    "Rechazado",
]

DIAS_SEMANA = {
    "Lunes": 0,
    "Martes": 1,
    "Miércoles": 2,
    "Jueves": 3,
    "Viernes": 4,
    "Sábado": 5,
    "Domingo": 6,
}

DIAS_ORDEN = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


# =========================================================
# BASE DE DATOS
# =========================================================

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def add_column_if_missing(cursor, table, column, column_type):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proyectos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_registro TEXT,
            codigo_proyecto TEXT UNIQUE,
            codigo_maestro TEXT UNIQUE,
            nombre_proyecto TEXT,
            investigador_principal TEXT,
            responsable_proyecto TEXT,
            docente_supervisor TEXT,
            correo_principal TEXT,
            especialidad TEXT,
            linea_investigacion TEXT,
            responsables_autorizados TEXT,
            observaciones_proyecto TEXT,
            estado_proyecto TEXT DEFAULT 'Activo'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reservas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id INTEGER,
            grupo_recurrencia TEXT,
            fecha_solicitud TEXT,
            tipo_reserva TEXT,
            tipo_actividad TEXT,
            solicitante_responsable TEXT,
            correo_solicitante TEXT,
            responsable_operativo TEXT,
            responsable_proyecto_reserva TEXT,
            docente_supervisor_reserva TEXT,
            fecha_uso TEXT,
            hora_inicio TEXT,
            hora_fin TEXT,
            recursos TEXT,
            numero_participantes INTEGER,
            actividad TEXT,
            observaciones TEXT,
            visitantes_externos TEXT,
            estado TEXT DEFAULT 'Pendiente',
            FOREIGN KEY(proyecto_id) REFERENCES proyectos(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visitantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reserva_id INTEGER,
            nombre_visitante TEXT,
            dni TEXT,
            FOREIGN KEY(reserva_id) REFERENCES reservas(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cierres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reserva_id INTEGER,
            fecha_cierre_operativo TEXT,
            responsable_cierre TEXT,
            actividad_realizada TEXT,
            estado_cierre_operativo TEXT,
            hora_inicio_real TEXT,
            hora_fin_real TEXT,
            participantes_reales INTEGER,
            observaciones_cierre TEXT,
            incidencias TEXT,
            equipos_apagados INTEGER,
            materiales_devueltos INTEGER,
            area_limpia INTEGER,
            datos_respaldados INTEGER,
            participantes_retirados INTEGER,
            sin_incidencias INTEGER,
            evidencia_archivos TEXT,
            estado_validacion TEXT DEFAULT 'Pendiente de validación',
            observacion_administrador TEXT,
            administrador_valida TEXT,
            fecha_validacion TEXT,
            FOREIGN KEY(reserva_id) REFERENCES reservas(id)
        )
    """)

    # Compatibilidad por si se edita una base ya creada
    for table, cols in {
        "proyectos": [
            ("codigo_maestro", "TEXT"), ("linea_investigacion", "TEXT"),
            ("responsables_autorizados", "TEXT"), ("estado_proyecto", "TEXT"),
            ("responsable_proyecto", "TEXT"), ("docente_supervisor", "TEXT")
        ],
        "reservas": [
            ("proyecto_id", "INTEGER"), ("grupo_recurrencia", "TEXT"),
            ("tipo_reserva", "TEXT"), ("tipo_actividad", "TEXT"),
            ("responsable_proyecto_reserva", "TEXT"), ("docente_supervisor_reserva", "TEXT")
        ],
        "cierres": [
            ("estado_validacion", "TEXT"), ("observacion_administrador", "TEXT"),
            ("administrador_valida", "TEXT"), ("fecha_validacion", "TEXT")
        ],
    }.items():
        for col, typ in cols:
            add_column_if_missing(cursor, table, col, typ)

    conn.commit()
    conn.close()


def cargar_proyectos():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM proyectos ORDER BY fecha_registro DESC", conn)
    conn.close()
    return df


def cargar_reservas():
    conn = get_connection()
    query = """
        SELECT 
            r.*,
            p.codigo_proyecto,
            p.codigo_maestro,
            p.nombre_proyecto,
            p.investigador_principal,
            p.responsable_proyecto,
            p.docente_supervisor,
            p.correo_principal,
            p.especialidad,
            p.linea_investigacion,
            p.responsables_autorizados
        FROM reservas r
        LEFT JOIN proyectos p ON r.proyecto_id = p.id
        ORDER BY r.fecha_uso, r.hora_inicio
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def cargar_visitantes(reserva_id):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT nombre_visitante, dni FROM visitantes WHERE reserva_id = ?",
        conn,
        params=(int(reserva_id),),
    )
    conn.close()
    return df


def cargar_cierres():
    conn = get_connection()
    query = """
        SELECT 
            c.*,
            r.fecha_uso,
            r.hora_inicio,
            r.hora_fin,
            r.recursos,
            r.estado AS estado_reserva,
            p.codigo_proyecto,
            p.codigo_maestro,
            p.nombre_proyecto,
            p.investigador_principal,
            p.especialidad
        FROM cierres c
        LEFT JOIN reservas r ON c.reserva_id = r.id
        LEFT JOIN proyectos p ON r.proyecto_id = p.id
        ORDER BY c.fecha_cierre_operativo DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def cargar_cierre_por_reserva(reserva_id):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM cierres WHERE reserva_id = ? ORDER BY fecha_cierre_operativo DESC",
        conn,
        params=(int(reserva_id),),
    )
    conn.close()
    return df


# =========================================================
# UTILIDADES
# =========================================================

def generar_codigo(prefijo="PROY"):
    alfabeto = string.ascii_uppercase + string.digits
    return f"{prefijo}-" + "".join(secrets.choice(alfabeto) for _ in range(8))


def obtener_inicio_semana(fecha):
    return fecha - timedelta(days=fecha.weekday())


def generar_slots_horarios(hora_inicio=8, hora_fin=20, intervalo_min=30):
    slots = []
    actual = datetime.combine(date.today(), time(hora_inicio, 0))
    fin = datetime.combine(date.today(), time(hora_fin, 0))
    while actual < fin:
        siguiente = actual + timedelta(minutes=intervalo_min)
        slots.append((actual.time(), siguiente.time()))
        actual = siguiente
    return slots


def horarios_se_cruzan(inicio_1, fin_1, inicio_2, fin_2):
    return inicio_1 < fin_2 and inicio_2 < fin_1


def recursos_a_lista(recursos):
    if isinstance(recursos, list):
        return recursos
    return [r.strip() for r in str(recursos).split(",") if r.strip()]


def recursos_compatibles(recursos_solicitados, recursos_existentes):
    recursos_solicitados = set(recursos_a_lista(recursos_solicitados))
    recursos_existentes = set(recursos_a_lista(recursos_existentes))

    if recursos_solicitados == {"Solo espacio / sin equipo específico"}:
        return True

    if recursos_existentes == {"Solo espacio / sin equipo específico"}:
        return True

    return len(recursos_solicitados.intersection(recursos_existentes)) == 0


def detectar_conflictos(fecha_uso, hora_inicio, hora_fin, recursos_solicitados, excluir_id=None):
    df = cargar_reservas()

    if df.empty:
        return pd.DataFrame()

    # Bloquean reservas aprobadas y reservas con cierre enviado/finalizadas porque ya ocuparon el recurso
    estados_bloqueantes = ["Aprobado", "Cierre enviado", "Cierre observado", "Subsanación requerida", "Finalizado"]
    df_bloqueantes = df[(df["estado"].isin(estados_bloqueantes)) & (df["fecha_uso"] == str(fecha_uso))].copy()

    if excluir_id is not None:
        df_bloqueantes = df_bloqueantes[df_bloqueantes["id"] != int(excluir_id)]

    conflictos = []

    for _, row in df_bloqueantes.iterrows():
        if recursos_compatibles(recursos_solicitados, row["recursos"]):
            continue

        inicio_existente = datetime.strptime(row["hora_inicio"], "%H:%M").time()
        fin_existente = datetime.strptime(row["hora_fin"], "%H:%M").time()

        if horarios_se_cruzan(hora_inicio, hora_fin, inicio_existente, fin_existente):
            conflictos.append(row.to_dict())

    return pd.DataFrame(conflictos)


def fechas_recurrentes(fecha_inicio, fecha_fin, dias_seleccionados):
    dias_num = [DIAS_SEMANA[d] for d in dias_seleccionados]
    fechas = []
    actual = fecha_inicio
    while actual <= fecha_fin:
        if actual.weekday() in dias_num:
            fechas.append(actual)
        actual += timedelta(days=1)
    return fechas


def estado_color(valor):
    valor = str(valor)
    if "Aprobado" in valor:
        return "background-color: #F8D7DA; color: #721C24;"
    if "Pendiente" in valor:
        return "background-color: #FFF3CD; color: #856404;"
    if "Cierre enviado" in valor or "Subsanación" in valor or "Observado" in valor:
        return "background-color: #FFE5B4; color: #7A4A00;"
    if "Finalizado" in valor:
        return "background-color: #D1ECF1; color: #0C5460;"
    if "Libre" in valor:
        return "background-color: #D4EDDA; color: #155724;"
    if "Rechazado" in valor or "Cancelado" in valor:
        return "background-color: #E2E3E5; color: #383D41;"
    return ""


def guardar_archivos_evidencia(reserva_id, archivos):
    if not archivos:
        return ""

    guardados = []
    carpeta_reserva = EVIDENCE_DIR / f"reserva_{reserva_id}"
    carpeta_reserva.mkdir(exist_ok=True)

    for archivo in archivos:
        nombre_seguro = archivo.name.replace(" ", "_")
        destino = carpeta_reserva / f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{nombre_seguro}"

        with open(destino, "wb") as f:
            f.write(archivo.getbuffer())

        guardados.append(str(destino))

    return " | ".join(guardados)


def listar_evidencias(evidencia_archivos):
    if not evidencia_archivos or str(evidencia_archivos).strip() == "":
        return []
    rutas = [Path(r.strip()) for r in str(evidencia_archivos).split("|") if r.strip()]
    return [r for r in rutas if r.exists()]


def mostrar_evidencias(evidencia_archivos, titulo="Evidencias adjuntas"):
    rutas = listar_evidencias(evidencia_archivos)

    if not rutas:
        st.info("No hay evidencias adjuntas o no se encontraron los archivos en la carpeta local.")
        return

    st.markdown(f"### {titulo}")

    for ruta in rutas:
        st.markdown(f"**Archivo:** `{ruta.name}`")
        ext = ruta.suffix.lower()

        if ext in [".png", ".jpg", ".jpeg"]:
            st.image(str(ruta), caption=ruta.name, use_container_width=True)
        elif ext == ".pdf":
            st.info("Archivo PDF disponible para descarga.")
        else:
            st.info("Archivo disponible para descarga.")

        with open(ruta, "rb") as f:
            st.download_button(
                label=f"Descargar {ruta.name}",
                data=f,
                file_name=ruta.name,
                mime="application/octet-stream",
                key=f"download_{ruta.as_posix()}",
            )


# =========================================================
# CRUD PROYECTOS
# =========================================================

def crear_proyecto(datos):
    conn = get_connection()
    cursor = conn.cursor()

    codigo_maestro = generar_codigo("INTERFAC")

    cursor.execute("""
        INSERT INTO proyectos (
            fecha_registro,
            codigo_proyecto,
            codigo_maestro,
            nombre_proyecto,
            investigador_principal,
            responsable_proyecto,
            docente_supervisor,
            correo_principal,
            especialidad,
            linea_investigacion,
            responsables_autorizados,
            observaciones_proyecto,
            estado_proyecto
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        datos["codigo_proyecto"],
        codigo_maestro,
        datos["nombre_proyecto"],
        datos["investigador_principal"],
        datos["responsable_proyecto"],
        datos["docente_supervisor"],
        datos["correo_principal"],
        datos["especialidad"],
        datos["linea_investigacion"],
        datos["responsables_autorizados"],
        datos["observaciones_proyecto"],
        "Activo",
    ))

    proyecto_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return proyecto_id, codigo_maestro


def actualizar_proyecto(proyecto_id, estado_proyecto, responsables_autorizados, observaciones_proyecto, responsable_proyecto, docente_supervisor):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE proyectos
        SET estado_proyecto = ?, responsables_autorizados = ?, observaciones_proyecto = ?,
            responsable_proyecto = ?, docente_supervisor = ?
        WHERE id = ?
    """, (estado_proyecto, responsables_autorizados, observaciones_proyecto, responsable_proyecto, docente_supervisor, int(proyecto_id)))
    conn.commit()
    conn.close()


def regenerar_codigo_maestro(proyecto_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE proyectos SET codigo_maestro = ? WHERE id = ?",
        (generar_codigo("INTERFAC"), int(proyecto_id)),
    )
    conn.commit()
    conn.close()


# =========================================================
# CRUD RESERVAS Y CIERRES
# =========================================================

def guardar_reserva(datos, visitantes):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reservas (
            proyecto_id,
            grupo_recurrencia,
            fecha_solicitud,
            tipo_reserva,
            tipo_actividad,
            solicitante_responsable,
            correo_solicitante,
            responsable_operativo,
            responsable_proyecto_reserva,
            docente_supervisor_reserva,
            fecha_uso,
            hora_inicio,
            hora_fin,
            recursos,
            numero_participantes,
            actividad,
            observaciones,
            visitantes_externos,
            estado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        int(datos["proyecto_id"]),
        datos.get("grupo_recurrencia", ""),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        datos["tipo_reserva"],
        datos["tipo_actividad"],
        datos["solicitante_responsable"],
        datos["correo_solicitante"],
        datos["responsable_operativo"],
        datos["responsable_proyecto_reserva"],
        datos["docente_supervisor_reserva"],
        str(datos["fecha_uso"]),
        datos["hora_inicio"].strftime("%H:%M"),
        datos["hora_fin"].strftime("%H:%M"),
        ", ".join(datos["recursos"]),
        int(datos["numero_participantes"]),
        datos["actividad"],
        datos["observaciones"],
        datos["visitantes_externos"],
        "Pendiente",
    ))

    reserva_id = cursor.lastrowid

    for visitante in visitantes:
        cursor.execute("""
            INSERT INTO visitantes (reserva_id, nombre_visitante, dni)
            VALUES (?, ?, ?)
        """, (reserva_id, visitante["nombre"], visitante["dni"]))

    conn.commit()
    conn.close()
    return reserva_id


def actualizar_estado_reserva(reserva_id, nuevo_estado):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE reservas SET estado = ? WHERE id = ?", (nuevo_estado, int(reserva_id)))
    conn.commit()
    conn.close()


def actualizar_estado_grupo(grupo_recurrencia, nuevo_estado):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE reservas SET estado = ? WHERE grupo_recurrencia = ?", (nuevo_estado, grupo_recurrencia))
    conn.commit()
    conn.close()


def eliminar_reserva(reserva_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cierres WHERE reserva_id = ?", (int(reserva_id),))
    cursor.execute("DELETE FROM visitantes WHERE reserva_id = ?", (int(reserva_id),))
    cursor.execute("DELETE FROM reservas WHERE id = ?", (int(reserva_id),))
    conn.commit()
    conn.close()


def guardar_cierre_operativo(datos_cierre):
    conn = get_connection()
    cursor = conn.cursor()

    # Se reemplaza el cierre operativo previo si se vuelve a enviar por subsanación
    cursor.execute("DELETE FROM cierres WHERE reserva_id = ?", (int(datos_cierre["reserva_id"]),))

    cursor.execute("""
        INSERT INTO cierres (
            reserva_id,
            fecha_cierre_operativo,
            responsable_cierre,
            actividad_realizada,
            estado_cierre_operativo,
            hora_inicio_real,
            hora_fin_real,
            participantes_reales,
            observaciones_cierre,
            incidencias,
            equipos_apagados,
            materiales_devueltos,
            area_limpia,
            datos_respaldados,
            participantes_retirados,
            sin_incidencias,
            evidencia_archivos,
            estado_validacion,
            observacion_administrador,
            administrador_valida,
            fecha_validacion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        int(datos_cierre["reserva_id"]),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        datos_cierre["responsable_cierre"],
        datos_cierre["actividad_realizada"],
        datos_cierre["estado_cierre_operativo"],
        datos_cierre["hora_inicio_real"].strftime("%H:%M"),
        datos_cierre["hora_fin_real"].strftime("%H:%M"),
        int(datos_cierre["participantes_reales"]),
        datos_cierre["observaciones_cierre"],
        datos_cierre["incidencias"],
        int(datos_cierre["equipos_apagados"]),
        int(datos_cierre["materiales_devueltos"]),
        int(datos_cierre["area_limpia"]),
        int(datos_cierre["datos_respaldados"]),
        int(datos_cierre["participantes_retirados"]),
        int(datos_cierre["sin_incidencias"]),
        datos_cierre["evidencia_archivos"],
        "Pendiente de validación",
        "",
        "",
        "",
    ))

    conn.commit()
    conn.close()

    actualizar_estado_reserva(datos_cierre["reserva_id"], "Cierre enviado")


def validar_cierre(reserva_id, estado_validacion, observacion_administrador, administrador_valida):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE cierres
        SET estado_validacion = ?, 
            observacion_administrador = ?, 
            administrador_valida = ?, 
            fecha_validacion = ?
        WHERE reserva_id = ?
    """, (
        estado_validacion,
        observacion_administrador,
        administrador_valida,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        int(reserva_id),
    ))

    conn.commit()
    conn.close()

    if estado_validacion == "Validado":
        actualizar_estado_reserva(reserva_id, "Finalizado")
    elif estado_validacion == "Observado":
        actualizar_estado_reserva(reserva_id, "Cierre observado")
    elif estado_validacion == "Subsanación requerida":
        actualizar_estado_reserva(reserva_id, "Subsanación requerida")
    elif estado_validacion == "Rechazado":
        actualizar_estado_reserva(reserva_id, "Cierre observado")


# =========================================================
# DOCUMENTOS
# =========================================================

def crear_link_descarga_html(html, nombre_archivo, texto="Descargar constancia HTML"):
    b64 = base64.b64encode(html.encode("utf-8")).decode()
    return f'<a href="data:text/html;base64,{b64}" download="{nombre_archivo}">{texto}</a>'


def guardar_documento_html(html, carpeta, nombre_archivo):
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre_archivo
    ruta.write_text(html, encoding="utf-8")
    return ruta


def mostrar_documento_guardado(ruta, texto_boton="Descargar constancia guardada"):
    ruta = Path(ruta)
    if ruta.exists():
        with open(ruta, "rb") as f:
            st.download_button(
                label=texto_boton,
                data=f,
                file_name=ruta.name,
                mime="text/html",
                key=f"doc_{ruta.as_posix()}",
            )
    else:
        st.info("La constancia aún no está guardada en carpeta local.")


def crear_zip_constancias_mes(anio, mes):
    """Genera en memoria un ZIP con constancias HTML del mes seleccionado."""
    df_reservas = cargar_reservas()
    df_cierres = cargar_cierres()

    memoria = BytesIO()
    total_archivos = 0

    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as zipf:
        if not df_reservas.empty:
            df_mes = df_reservas[
                (pd.to_datetime(df_reservas["fecha_uso"], errors="coerce").dt.year == int(anio)) &
                (pd.to_datetime(df_reservas["fecha_uso"], errors="coerce").dt.month == int(mes))
            ].copy()

            for _, reserva in df_mes.iterrows():
                reserva_id = int(reserva["id"])
                proyecto_codigo = str(reserva.get("codigo_proyecto", "SIN_CODIGO")).replace("/", "-").replace("\\", "-")

                if reserva["estado"] in ["Aprobado", "Cierre enviado", "Cierre observado", "Subsanación requerida", "Finalizado"]:
                    html_reserva = generar_constancia_reserva_html(reserva)
                    nombre = f"reservas_aprobadas/{proyecto_codigo}/reserva_{reserva_id}_constancia_aprobada.html"
                    zipf.writestr(nombre, html_reserva)
                    total_archivos += 1

                cierre = cargar_cierre_por_reserva(reserva_id)
                if not cierre.empty:
                    cierre_row = cierre.iloc[0]
                    if cierre_row.get("estado_validacion", "") == "Validado" and reserva["estado"] == "Finalizado":
                        html_cierre = generar_constancia_cierre_html(reserva, cierre_row)
                        nombre = f"cierres_validados/{proyecto_codigo}/reserva_{reserva_id}_constancia_cierre_validado.html"
                        zipf.writestr(nombre, html_cierre)
                        total_archivos += 1

        # Agregar un índice simple del contenido
        indice = f"""Exportación mensual de constancias - Laboratorio INTERFA-C
Año: {anio}
Mes: {mes}
Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total de archivos generados: {total_archivos}

Contenido:
- reservas_aprobadas/: constancias de reservas aprobadas o en proceso.
- cierres_validados/: constancias finales de cierres validados por el administrador.
"""
        zipf.writestr("LEEME_exportacion.txt", indice)

    memoria.seek(0)
    return memoria.getvalue(), total_archivos


def generar_constancia_proyecto_html(proyecto):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <title>Constancia de registro de proyecto</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; color: #222; }}
        .card {{ border: 2px solid #004E64; padding: 28px; border-radius: 14px; }}
        h1 {{ color: #004E64; }}
        h2 {{ color: #2EC4B6; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        .code {{ background: #F6F6F6; padding: 12px; border-radius: 8px; font-weight: bold; }}
        .warning {{ background: #FFF3CD; padding: 12px; border-radius: 8px; color: #856404; }}
        .footer {{ margin-top: 28px; font-size: 12px; color: #555; }}
    </style>
    </head>
    <body>
    <div class="card">
        <h1>Constancia de registro de proyecto</h1>
        <h2>Laboratorio de Ergonomía INTERFA-C</h2>
        <table>
            <tr><td><b>ID interno del proyecto</b></td><td>{proyecto['id']}</td></tr>
            <tr><td><b>Código del proyecto</b></td><td>{proyecto['codigo_proyecto']}</td></tr>
            <tr><td><b>Nombre del proyecto</b></td><td>{proyecto['nombre_proyecto']}</td></tr>
            <tr><td><b>Investigador principal</b></td><td>{proyecto['investigador_principal']}</td></tr>
            <tr><td><b>Responsable del proyecto</b></td><td>{proyecto['responsable_proyecto']}</td></tr>
            <tr><td><b>Docente/licenciado supervisor</b></td><td>{proyecto['docente_supervisor']}</td></tr>
            <tr><td><b>Correo institucional</b></td><td>{proyecto['correo_principal']}</td></tr>
            <tr><td><b>Especialidad</b></td><td>{proyecto['especialidad']}</td></tr>
            <tr><td><b>Línea de investigación</b></td><td>{proyecto['linea_investigacion']}</td></tr>
            <tr><td><b>Responsables autorizados</b></td><td>{proyecto['responsables_autorizados']}</td></tr>
            <tr><td><b>Estado del proyecto</b></td><td>{proyecto['estado_proyecto']}</td></tr>
            <tr><td><b>Fecha de registro</b></td><td>{proyecto['fecha_registro']}</td></tr>
        </table>
        <p class="code">Código maestro del proyecto: {proyecto['codigo_maestro']}</p>
        <p class="warning"><b>Importante:</b> este código permite solicitar reservas y registrar cierres operativos asociados al proyecto. Debe conservarse y compartirse solo con responsables autorizados.</p>
        <div class="footer">
            Documento generado automáticamente por el Sistema de Gestión del Laboratorio de Ergonomía INTERFA-C.
        </div>
    </div>
    </body>
    </html>
    """
    return html


def generar_constancia_reserva_html(reserva):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <title>Constancia de reserva aprobada</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; color: #222; }}
        .card {{ border: 2px solid #004E64; padding: 28px; border-radius: 14px; }}
        h1 {{ color: #004E64; }}
        h2 {{ color: #2EC4B6; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        .code {{ background: #F6F6F6; padding: 12px; border-radius: 8px; font-weight: bold; }}
        .footer {{ margin-top: 28px; font-size: 12px; color: #555; }}
    </style>
    </head>
    <body>
    <div class="card">
        <h1>Constancia de reserva aprobada</h1>
        <h2>Laboratorio de Ergonomía INTERFA-C</h2>
        <table>
            <tr><td><b>ID de reserva</b></td><td>{reserva['id']}</td></tr>
            <tr><td><b>Estado</b></td><td>{reserva['estado']}</td></tr>
            <tr><td><b>Código del proyecto</b></td><td>{reserva['codigo_proyecto']}</td></tr>
            <tr><td><b>Código maestro del proyecto</b></td><td>{reserva['codigo_maestro']}</td></tr>
            <tr><td><b>Proyecto</b></td><td>{reserva['nombre_proyecto']}</td></tr>
            <tr><td><b>Tipo de actividad</b></td><td>{reserva['tipo_actividad']}</td></tr>
            <tr><td><b>Investigador principal</b></td><td>{reserva['investigador_principal']}</td></tr>
            <tr><td><b>Responsable del proyecto</b></td><td>{reserva['responsable_proyecto_reserva']}</td></tr>
            <tr><td><b>Docente/licenciado supervisor</b></td><td>{reserva['docente_supervisor_reserva']}</td></tr>
            <tr><td><b>Responsable operativo</b></td><td>{reserva['responsable_operativo']}</td></tr>
            <tr><td><b>Especialidad</b></td><td>{reserva['especialidad']}</td></tr>
            <tr><td><b>Fecha</b></td><td>{reserva['fecha_uso']}</td></tr>
            <tr><td><b>Horario</b></td><td>{reserva['hora_inicio']} a {reserva['hora_fin']}</td></tr>
            <tr><td><b>Recursos</b></td><td>{reserva['recursos']}</td></tr>
            <tr><td><b>Participantes estimados</b></td><td>{reserva['numero_participantes']}</td></tr>
        </table>
        <p class="code">Esta constancia acredita una reserva aprobada para el uso del laboratorio.</p>
        <p><b>Nota:</b> El cierre operativo debe registrarse al finalizar la actividad usando el código maestro del proyecto.</p>
        <div class="footer">
            Documento generado automáticamente por el Sistema de Gestión del Laboratorio de Ergonomía INTERFA-C.
        </div>
    </div>
    </body>
    </html>
    """
    return html


def generar_constancia_cierre_html(reserva, cierre):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <title>Constancia final de cierre validado</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; color: #222; }}
        .card {{ border: 2px solid #004E64; padding: 28px; border-radius: 14px; }}
        h1 {{ color: #004E64; }}
        h2 {{ color: #2EC4B6; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        .validado {{ background: #D4EDDA; padding: 12px; border-radius: 8px; font-weight: bold; color: #155724; }}
        .footer {{ margin-top: 28px; font-size: 12px; color: #555; }}
    </style>
    </head>
    <body>
    <div class="card">
        <h1>Constancia final de cierre validado</h1>
        <h2>Laboratorio de Ergonomía INTERFA-C</h2>
        <p class="validado">Actividad cerrada y validada oficialmente por el Laboratorio de Ergonomía INTERFA-C.</p>
        <table>
            <tr><td><b>ID de reserva</b></td><td>{reserva['id']}</td></tr>
            <tr><td><b>Código del proyecto</b></td><td>{reserva['codigo_proyecto']}</td></tr>
            <tr><td><b>Proyecto</b></td><td>{reserva['nombre_proyecto']}</td></tr>
            <tr><td><b>Investigador principal</b></td><td>{reserva['investigador_principal']}</td></tr>
            <tr><td><b>Responsable del proyecto</b></td><td>{reserva['responsable_proyecto_reserva']}</td></tr>
            <tr><td><b>Docente/licenciado supervisor</b></td><td>{reserva['docente_supervisor_reserva']}</td></tr>
            <tr><td><b>Responsable operativo</b></td><td>{reserva['responsable_operativo']}</td></tr>
            <tr><td><b>Fecha programada</b></td><td>{reserva['fecha_uso']}</td></tr>
            <tr><td><b>Horario programado</b></td><td>{reserva['hora_inicio']} a {reserva['hora_fin']}</td></tr>
            <tr><td><b>Horario real</b></td><td>{cierre['hora_inicio_real']} a {cierre['hora_fin_real']}</td></tr>
            <tr><td><b>Recursos utilizados</b></td><td>{reserva['recursos']}</td></tr>
            <tr><td><b>Participantes reales</b></td><td>{cierre['participantes_reales']}</td></tr>
            <tr><td><b>Estado operativo declarado</b></td><td>{cierre['estado_cierre_operativo']}</td></tr>
            <tr><td><b>Observaciones finales</b></td><td>{cierre['observaciones_cierre']}</td></tr>
            <tr><td><b>Incidencias</b></td><td>{cierre['incidencias']}</td></tr>
            <tr><td><b>Validación del administrador</b></td><td>{cierre['estado_validacion']}</td></tr>
            <tr><td><b>Administrador que valida</b></td><td>{cierre['administrador_valida']}</td></tr>
            <tr><td><b>Fecha de validación</b></td><td>{cierre['fecha_validacion']}</td></tr>
            <tr><td><b>Observación del administrador</b></td><td>{cierre['observacion_administrador']}</td></tr>
        </table>
        <div class="footer">
            Documento generado automáticamente por el Sistema de Gestión del Laboratorio de Ergonomía INTERFA-C.
        </div>
    </div>
    </body>
    </html>
    """
    return html


def generar_correo_ingreso(reserva_id):
    df = cargar_reservas()
    reserva_df = df[df["id"] == int(reserva_id)]

    if reserva_df.empty:
        return "", "No se encontró la solicitud."

    reserva = reserva_df.iloc[0]
    visitantes = cargar_visitantes(reserva_id)

    lista_visitantes = ""
    for i, row in visitantes.iterrows():
        lista_visitantes += f"{i + 1}. {row['nombre_visitante']} – DNI: {row['dni']}\n"

    asunto = "Solicitud de ingreso de participantes externos – Laboratorio de Ergonomía"

    cuerpo = f"""Estimados,

Por medio del presente solicito el ingreso de participantes externos al Departamento para el desarrollo de actividades vinculadas al Laboratorio de Ergonomía.

Datos de la actividad:

Código del proyecto: {reserva['codigo_proyecto']}
Nombre del proyecto / actividad: {reserva['nombre_proyecto']}
Responsable del proyecto: {reserva['responsable_proyecto_reserva']}
Docente/licenciado supervisor: {reserva['docente_supervisor_reserva']}
Responsable operativo: {reserva['responsable_operativo']}
Especialidad: {reserva['especialidad']}
Fecha de ingreso: {reserva['fecha_uso']}
Horario: {reserva['hora_inicio']} a {reserva['hora_fin']}

Participantes externos:

{lista_visitantes}
Se ha indicado a los participantes que deberán portar su DNI físico para el ingreso correspondiente.

Atentamente,

{reserva['investigador_principal']}
Responsable del Laboratorio de Ergonomía
Grupo INTERFA-C
"""
    return asunto, cuerpo


# =========================================================
# EXPORTAR
# =========================================================

def crear_excel_registro():
    df_proyectos = cargar_proyectos()
    df_reservas = cargar_reservas()
    df_cierres = cargar_cierres()

    conn = get_connection()
    df_visitantes = pd.read_sql_query("SELECT * FROM visitantes", conn)
    conn.close()

    output_path = Path("registro_laboratorio_interfac.xlsx")

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_proyectos.to_excel(writer, sheet_name="Proyectos", index=False)
        df_reservas.to_excel(writer, sheet_name="Reservas", index=False)
        df_visitantes.to_excel(writer, sheet_name="Visitantes", index=False)
        df_cierres.to_excel(writer, sheet_name="Cierres", index=False)

    return output_path


# =========================================================
# COMPONENTES
# =========================================================

def formulario_cierre_operativo(reserva):
    reserva_id = int(reserva["id"])
    cierre_existente = cargar_cierre_por_reserva(reserva_id)

    if not cierre_existente.empty:
        st.warning("Esta reserva ya tiene un cierre operativo. Si guarda nuevamente, se reemplazará el cierre anterior y volverá a quedar pendiente de validación.")
        st.dataframe(cierre_existente, use_container_width=True)
        mostrar_evidencias(cierre_existente.iloc[0].get("evidencia_archivos", ""), "Evidencias actuales")

    with st.form(f"form_cierre_{reserva_id}", clear_on_submit=False):
        st.subheader("Datos del cierre operativo")

        col1, col2 = st.columns(2)

        with col1:
            responsable_cierre = st.text_input("Responsable que realiza el cierre", value=str(reserva["responsable_operativo"]))
            actividad_realizada = st.radio("¿La actividad se realizó?", ["Sí", "Parcialmente", "No"], horizontal=True)
            estado_cierre_operativo = st.selectbox("Estado operativo del uso", ESTADOS_CIERRE_OPERATIVO)

        with col2:
            hora_inicio_real = st.time_input("Hora real de inicio", value=datetime.strptime(reserva["hora_inicio"], "%H:%M").time())
            hora_fin_real = st.time_input("Hora real de fin", value=datetime.strptime(reserva["hora_fin"], "%H:%M").time())
            participantes_reales = st.number_input("Número real de participantes", min_value=0, max_value=100, value=int(reserva["numero_participantes"]))

        observaciones_cierre = st.text_area("Observaciones finales", placeholder="Ejemplo: La actividad se realizó sin inconvenientes. El área quedó limpia.")
        incidencias = st.text_area("Incidencias o implicancias ocurridas", placeholder="Si no hubo incidencias, puede escribir: No hubo incidencias.")

        st.subheader("Checklist de cierre")
        colc1, colc2, colc3 = st.columns(3)

        with colc1:
            equipos_apagados = st.checkbox("Equipos apagados", value=True)
            materiales_devueltos = st.checkbox("Materiales devueltos", value=True)

        with colc2:
            area_limpia = st.checkbox("Área limpia y ordenada", value=True)
            datos_respaldados = st.checkbox("Datos respaldados o entregados", value=True)

        with colc3:
            participantes_retirados = st.checkbox("Participantes retirados", value=True)
            sin_incidencias = st.checkbox("Sin incidencias que reportar", value=True)

        st.subheader("Evidencia adjunta")
        archivos = st.file_uploader(
            "Adjuntar fotos, capturas, PDF, checklist u otra evidencia",
            type=["png", "jpg", "jpeg", "pdf", "xlsx", "docx"],
            accept_multiple_files=True,
            key=f"uploader_{reserva_id}",
        )

        enviar = st.form_submit_button("Enviar cierre operativo")

    if enviar:
        errores = []

        if not responsable_cierre.strip():
            errores.append("Debe ingresar el responsable del cierre.")
        if hora_fin_real <= hora_inicio_real and actividad_realizada != "No":
            errores.append("La hora real de fin debe ser posterior a la hora real de inicio.")

        if not observaciones_cierre.strip():
            observaciones_cierre = "Sin observaciones adicionales."
        if not incidencias.strip():
            incidencias = "No hubo incidencias."

        if errores:
            for error in errores:
                st.error(error)
        else:
            evidencia_archivos = guardar_archivos_evidencia(reserva_id, archivos)

            datos_cierre = {
                "reserva_id": reserva_id,
                "responsable_cierre": responsable_cierre,
                "actividad_realizada": actividad_realizada,
                "estado_cierre_operativo": estado_cierre_operativo,
                "hora_inicio_real": hora_inicio_real,
                "hora_fin_real": hora_fin_real,
                "participantes_reales": participantes_reales,
                "observaciones_cierre": observaciones_cierre,
                "incidencias": incidencias,
                "equipos_apagados": equipos_apagados,
                "materiales_devueltos": materiales_devueltos,
                "area_limpia": area_limpia,
                "datos_respaldados": datos_respaldados,
                "participantes_retirados": participantes_retirados,
                "sin_incidencias": sin_incidencias,
                "evidencia_archivos": evidencia_archivos,
            }

            guardar_cierre_operativo(datos_cierre)
            st.success("Cierre operativo enviado correctamente. Queda pendiente de validación por el administrador.")
            st.rerun()


# =========================================================
# STREAMLIT
# =========================================================

st.set_page_config(
    page_title="Laboratorio INTERFA-C",
    page_icon="🧪",
    layout="wide",
)

init_db()

st.title("🧪 Sistema de Gestión del Laboratorio de Ergonomía INTERFA-C")
st.caption("Proyectos, reservas, trazabilidad, cierre operativo, validación final y evidencias")

menu = st.sidebar.radio(
    "Menú",
    [
        "Horario semanal",
        "Registrar proyecto",
        "Solicitar uso del laboratorio",
        "Consultar proyecto/reservas",
        "Cierre operativo",
        "Panel administrador",
        "Historial y auditoría",
    ],
)


# =========================================================
# HORARIO SEMANAL
# =========================================================

if menu == "Horario semanal":
    st.header("Horario semanal del laboratorio")

    col1, col2, col3 = st.columns(3)

    with col1:
        fecha_base = st.date_input("Seleccione una fecha de la semana", value=date.today())

    with col2:
        recurso_filtro = st.selectbox("Filtrar por recurso", ["Todos"] + RECURSOS)

    with col3:
        mostrar_estados = st.multiselect(
            "Mostrar estados",
            ESTADOS_RESERVA,
            default=["Aprobado", "Pendiente", "Cierre enviado", "Subsanación requerida", "Finalizado"],
        )

    inicio_semana = obtener_inicio_semana(fecha_base)
    fechas_semana = [inicio_semana + timedelta(days=i) for i in range(7)]

    st.info(f"Semana del {fechas_semana[0].strftime('%d/%m/%Y')} al {fechas_semana[-1].strftime('%d/%m/%Y')}")

    df = cargar_reservas()

    if not df.empty:
        df = df[df["fecha_uso"].isin([str(f) for f in fechas_semana])]
        df = df[df["estado"].isin(mostrar_estados)]

        if recurso_filtro != "Todos":
            df = df[df["recursos"].str.contains(recurso_filtro, na=False, regex=False)]

    slots = generar_slots_horarios(8, 20, 30)

    tabla = []

    for slot_inicio, slot_fin in slots:
        fila = {"Hora": f"{slot_inicio.strftime('%H:%M')}-{slot_fin.strftime('%H:%M')}"}

        for dia_nombre, fecha_dia in zip(DIAS_ORDEN, fechas_semana):
            contenido = "Libre"

            if not df.empty:
                reservas_dia = df[df["fecha_uso"] == str(fecha_dia)]

                textos = []
                for _, row in reservas_dia.iterrows():
                    inicio_reserva = datetime.strptime(row["hora_inicio"], "%H:%M").time()
                    fin_reserva = datetime.strptime(row["hora_fin"], "%H:%M").time()

                    if horarios_se_cruzan(slot_inicio, slot_fin, inicio_reserva, fin_reserva):
                        texto = f"{row['estado']} | {row['tipo_actividad']} | {row['nombre_proyecto']} | {row['recursos']}"
                        textos.append(texto)

                if textos:
                    contenido = "\n".join(textos)

            fila[f"{dia_nombre}\n{fecha_dia.strftime('%d/%m')}"] = contenido

        tabla.append(fila)

    horario_df = pd.DataFrame(tabla)

    st.dataframe(
        horario_df.style.map(estado_color),
        use_container_width=True,
        height=720,
    )

    st.caption("Rojo: aprobado. Amarillo: pendiente. Naranja: cierre/subsanación. Celeste: finalizado. Verde: libre.")

    with st.expander("Ver listado de reservas de la semana"):
        if df.empty:
            st.info("No hay reservas o solicitudes para esta semana con los filtros seleccionados.")
        else:
            st.dataframe(
                df[
                    [
                        "id",
                        "estado",
                        "codigo_proyecto",
                        "nombre_proyecto",
                        "tipo_reserva",
                        "tipo_actividad",
                        "fecha_uso",
                        "hora_inicio",
                        "hora_fin",
                        "responsable_operativo",
                        "recursos",
                        "visitantes_externos",
                    ]
                ],
                use_container_width=True,
            )


# =========================================================
# REGISTRAR PROYECTO
# =========================================================

elif menu == "Registrar proyecto":
    st.header("Registro maestro de proyecto")

    st.info("El proyecto tendrá un código maestro único. Ese código servirá para consultar reservas y realizar cierres operativos asociados al proyecto.")

    with st.form("form_proyecto", clear_on_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            codigo_proyecto = st.text_input("Código del proyecto o código interno")
            nombre_proyecto = st.text_area("Nombre del proyecto")
            investigador_principal = st.text_input("Investigador principal")
            responsable_proyecto = st.text_input("Responsable del proyecto")
            docente_supervisor = st.text_input("Docente o licenciado que supervisará")
            correo_principal = st.text_input("Correo institucional del investigador principal")

        with col2:
            especialidad = st.text_input("Especialidad")
            linea_investigacion = st.text_input("Línea de investigación")
            responsables_autorizados = st.text_area("Responsables autorizados", placeholder="Nombres de tesistas, asistentes o docentes autorizados.")
            observaciones_proyecto = st.text_area("Observaciones del proyecto")

        enviar = st.form_submit_button("Registrar proyecto")

    if enviar:
        errores = []

        if not codigo_proyecto.strip():
            errores.append("Debe ingresar el código del proyecto.")
        if not nombre_proyecto.strip():
            errores.append("Debe ingresar el nombre del proyecto.")
        if not investigador_principal.strip():
            errores.append("Debe ingresar el investigador principal.")
        if not responsable_proyecto.strip():
            errores.append("Debe ingresar el responsable del proyecto.")
        if not docente_supervisor.strip():
            errores.append("Debe ingresar el docente o licenciado supervisor.")
        if not correo_principal.strip():
            errores.append("Debe ingresar el correo institucional.")
        if not especialidad.strip():
            errores.append("Debe ingresar la especialidad.")

        df_proy = cargar_proyectos()
        if not df_proy.empty and codigo_proyecto.strip() in df_proy["codigo_proyecto"].astype(str).tolist():
            errores.append("Ya existe un proyecto registrado con ese código de proyecto.")

        if errores:
            for error in errores:
                st.error(error)
        else:
            datos = {
                "codigo_proyecto": codigo_proyecto.strip(),
                "nombre_proyecto": nombre_proyecto.strip(),
                "investigador_principal": investigador_principal.strip(),
                "responsable_proyecto": responsable_proyecto.strip(),
                "docente_supervisor": docente_supervisor.strip(),
                "correo_principal": correo_principal.strip(),
                "especialidad": especialidad.strip(),
                "linea_investigacion": linea_investigacion.strip(),
                "responsables_autorizados": responsables_autorizados.strip(),
                "observaciones_proyecto": observaciones_proyecto.strip(),
            }

            proyecto_id, codigo_maestro = crear_proyecto(datos)
            st.success(f"Proyecto registrado correctamente. ID interno: {proyecto_id}")
            st.info("Guarde este código maestro. Se usará para solicitar reservas, consultar el proyecto y cerrar actividades.")
            st.code(codigo_maestro)

            df_proy_nuevo = cargar_proyectos()
            proyecto_nuevo = df_proy_nuevo[df_proy_nuevo["id"] == int(proyecto_id)].iloc[0]
            html_proyecto = generar_constancia_proyecto_html(proyecto_nuevo)
            ruta_proyecto = guardar_documento_html(
                html_proyecto,
                DOCUMENTS_DIR / "proyectos",
                f"proyecto_{proyecto_id}_constancia_registro.html"
            )
            st.markdown(
                crear_link_descarga_html(
                    html_proyecto,
                    f"constancia_proyecto_{proyecto_id}.html",
                    "Descargar constancia de registro del proyecto"
                ),
                unsafe_allow_html=True,
            )
            st.caption(f"Constancia guardada en: {ruta_proyecto}")


# =========================================================
# SOLICITAR USO DEL LABORATORIO
# =========================================================

elif menu == "Solicitar uso del laboratorio":
    st.header("Solicitud de uso del laboratorio")

    st.info("Para solicitar una reserva, ingrese el código maestro del proyecto. Los proyectos registrados no se muestran públicamente.")

    codigo_maestro_solicitud = st.text_input("Código maestro del proyecto", type="password")

    if st.button("Validar proyecto"):
        df_proyectos = cargar_proyectos()
        proyecto_validado = df_proyectos[
            (df_proyectos["codigo_maestro"] == codigo_maestro_solicitud.strip()) &
            (df_proyectos["estado_proyecto"] == "Activo")
        ]

        if proyecto_validado.empty:
            st.error("No se encontró un proyecto activo con ese código maestro.")
        else:
            st.session_state["proyecto_solicitud_id"] = int(proyecto_validado.iloc[0]["id"])
            st.success("Proyecto validado. Puede completar la solicitud.")

    if "proyecto_solicitud_id" in st.session_state:
        df_proyectos = cargar_proyectos()
        proyecto_df = df_proyectos[df_proyectos["id"] == int(st.session_state["proyecto_solicitud_id"])]

        if proyecto_df.empty:
            st.error("El proyecto validado ya no está disponible.")
        else:
            proyecto_sel = proyecto_df.iloc[0]

            st.subheader("Proyecto asociado")
            st.write(
                proyecto_sel[
                    [
                        "codigo_proyecto",
                        "nombre_proyecto",
                        "investigador_principal",
                        "responsable_proyecto",
                        "docente_supervisor",
                        "especialidad",
                        "linea_investigacion",
                        "responsables_autorizados",
                    ]
                ].to_frame(name="Detalle")
            )

            tipo_reserva = st.radio(
                "Tipo de reserva",
                ["Reserva puntual", "Reserva recurrente por rango de fechas"],
                horizontal=True,
            )

            with st.form("form_solicitud_privada", clear_on_submit=False):
                st.subheader("Datos de la solicitud")

                col1, col2 = st.columns(2)

                with col1:
                    tipo_actividad = st.selectbox("Tipo de actividad", TIPOS_ACTIVIDAD)
                    solicitante_responsable = st.text_input("Nombre de quien solicita")
                    correo_solicitante = st.text_input("Correo institucional")
                    responsable_operativo = st.text_input("Responsable operativo / tesista responsable")
                    responsable_proyecto_reserva = st.text_input(
                        "Responsable del proyecto para esta reserva",
                        value=str(proyecto_sel.get("responsable_proyecto", "")) if pd.notna(proyecto_sel.get("responsable_proyecto", "")) else "",
                    )
                    docente_supervisor_reserva = st.text_input(
                        "Docente o licenciado supervisor para esta reserva",
                        value=str(proyecto_sel.get("docente_supervisor", "")) if pd.notna(proyecto_sel.get("docente_supervisor", "")) else "",
                    )

                with col2:
                    numero_participantes = st.number_input(
                        "Número estimado de participantes",
                        min_value=1,
                        max_value=80,
                        value=1,
                    )
                    actividad = st.text_area("Descripción de la actividad")
                    observaciones = st.text_area("Observaciones")

                st.subheader("Datos de reserva")

                if tipo_reserva == "Reserva puntual":
                    col3, col4, col5 = st.columns(3)

                    with col3:
                        fecha_uso = st.date_input("Fecha de uso", min_value=date.today())

                    with col4:
                        hora_inicio = st.time_input("Hora de inicio", value=time(9, 0))

                    with col5:
                        hora_fin = st.time_input("Hora de fin", value=time(11, 0))

                    fechas_a_guardar = [fecha_uso]

                else:
                    col3, col4 = st.columns(2)

                    with col3:
                        fecha_inicio_rango = st.date_input("Fecha de inicio del rango", min_value=date.today())

                    with col4:
                        fecha_fin_rango = st.date_input("Fecha de fin del rango", min_value=date.today())

                    dias_recurrentes = st.multiselect("Días de la semana", DIAS_ORDEN, default=["Lunes"])

                    col5, col6 = st.columns(2)

                    with col5:
                        hora_inicio = st.time_input("Hora de inicio", value=time(9, 0))

                    with col6:
                        hora_fin = st.time_input("Hora de fin", value=time(11, 0))

                    fechas_a_guardar = fechas_recurrentes(fecha_inicio_rango, fecha_fin_rango, dias_recurrentes)

                recursos = st.multiselect("Recursos requeridos", RECURSOS)

                st.subheader("Visitantes externos")

                visitantes_externos = st.radio("¿Asistirán participantes externos?", ["No", "Sí"], horizontal=True)
                visitantes = []

                if visitantes_externos == "Sí":
                    st.info("Indicar a cada visitante que deberá portar su DNI físico para el ingreso.")
                    n_visitantes = st.number_input("Número de visitantes externos", min_value=1, max_value=40, value=1)

                    for i in range(int(n_visitantes)):
                        st.markdown(f"**Visitante {i + 1}**")
                        c1, c2 = st.columns(2)
                        with c1:
                            nombre = st.text_input(f"Nombre y apellidos del visitante {i + 1}", key=f"nombre_visitante_{i}")
                        with c2:
                            dni = st.text_input(f"Número de DNI {i + 1}", key=f"dni_visitante_{i}")
                        visitantes.append({"nombre": nombre, "dni": dni})

                enviar = st.form_submit_button("Enviar solicitud")

            if enviar:
                errores = []

                if not solicitante_responsable.strip():
                    errores.append("Debe ingresar el nombre de quien solicita.")
                if not correo_solicitante.strip():
                    errores.append("Debe ingresar el correo institucional.")
                if not responsable_operativo.strip():
                    errores.append("Debe ingresar el responsable operativo.")
                if not responsable_proyecto_reserva.strip():
                    errores.append("Debe ingresar el responsable del proyecto para esta reserva.")
                if not docente_supervisor_reserva.strip():
                    errores.append("Debe ingresar el docente o licenciado supervisor para esta reserva.")
                if not recursos:
                    errores.append("Debe seleccionar al menos un recurso.")
                if hora_fin <= hora_inicio:
                    errores.append("La hora de fin debe ser posterior a la hora de inicio.")
                if tipo_reserva == "Reserva recurrente por rango de fechas":
                    if fecha_fin_rango < fecha_inicio_rango:
                        errores.append("La fecha de fin no puede ser anterior a la fecha de inicio.")
                    if not dias_recurrentes:
                        errores.append("Debe seleccionar al menos un día.")
                    if not fechas_a_guardar:
                        errores.append("No se generaron fechas dentro del rango.")

                if visitantes_externos == "Sí":
                    for visitante in visitantes:
                        if not visitante["nombre"].strip() or not visitante["dni"].strip():
                            errores.append("Debe completar nombre y DNI de todos los visitantes externos.")
                            break

                conflictos_totales = []
                for f in fechas_a_guardar:
                    conflictos = detectar_conflictos(f, hora_inicio, hora_fin, recursos)
                    if not conflictos.empty:
                        conflictos_totales.append(conflictos)

                if errores:
                    for error in errores:
                        st.error(error)
                else:
                    if conflictos_totales:
                        st.warning("La solicitud presenta posibles cruces con reservas aprobadas o en uso. Se registrará como pendiente para revisión.")
                        st.dataframe(pd.concat(conflictos_totales), use_container_width=True)

                    grupo_recurrencia = ""
                    if tipo_reserva == "Reserva recurrente por rango de fechas":
                        grupo_recurrencia = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                    ids_creados = []

                    for f in fechas_a_guardar:
                        datos = {
                            "proyecto_id": int(proyecto_sel["id"]),
                            "grupo_recurrencia": grupo_recurrencia,
                            "tipo_reserva": tipo_reserva,
                            "tipo_actividad": tipo_actividad,
                            "solicitante_responsable": solicitante_responsable,
                            "correo_solicitante": correo_solicitante,
                            "responsable_operativo": responsable_operativo,
                            "responsable_proyecto_reserva": responsable_proyecto_reserva,
                            "docente_supervisor_reserva": docente_supervisor_reserva,
                            "fecha_uso": f,
                            "hora_inicio": hora_inicio,
                            "hora_fin": hora_fin,
                            "recursos": recursos,
                            "numero_participantes": numero_participantes,
                            "actividad": actividad,
                            "observaciones": observaciones,
                            "visitantes_externos": visitantes_externos,
                        }

                        reserva_id = guardar_reserva(datos, visitantes if visitantes_externos == "Sí" else [])
                        ids_creados.append(reserva_id)

                    st.success(f"Solicitud registrada correctamente. Se generaron {len(ids_creados)} registro(s).")
                    st.info("La solicitud queda como Pendiente hasta revisión del administrador.")
                    st.write("IDs de reserva:", ids_creados)

                    if st.button("Limpiar proyecto validado"):
                        del st.session_state["proyecto_solicitud_id"]
                        st.rerun()


# =========================================================
# CONSULTAR PROYECTO / RESERVAS
# =========================================================

elif menu == "Consultar proyecto/reservas":
    st.header("Consultar proyecto y reservas aprobadas")

    st.info("Ingrese el código maestro del proyecto para ver sus reservas aprobadas/finalizadas y descargar constancias disponibles.")

    codigo_maestro = st.text_input("Código maestro del proyecto", type="password")

    if st.button("Consultar"):
        df_proyectos = cargar_proyectos()
        proy = df_proyectos[df_proyectos["codigo_maestro"] == codigo_maestro.strip()]

        if proy.empty:
            st.error("No se encontró un proyecto con ese código maestro.")
        else:
            proyecto = proy.iloc[0]
            st.success("Proyecto encontrado.")
            st.write(proyecto[["codigo_proyecto", "nombre_proyecto", "investigador_principal", "responsable_proyecto", "docente_supervisor", "especialidad", "estado_proyecto"]].to_frame(name="Detalle"))

            df_res = cargar_reservas()
            reservas = df_res[(df_res["proyecto_id"] == int(proyecto["id"])) & (df_res["estado"].isin(["Aprobado", "Cierre enviado", "Cierre observado", "Subsanación requerida", "Finalizado"]))]

            if reservas.empty:
                st.info("Este proyecto aún no tiene reservas aprobadas o finalizadas.")
            else:
                st.subheader("Reservas del proyecto")
                st.dataframe(
                    reservas[
                        [
                            "id",
                            "estado",
                            "tipo_actividad",
                            "fecha_uso",
                            "hora_inicio",
                            "hora_fin",
                            "responsable_operativo",
                            "recursos",
                        ]
                    ],
                    use_container_width=True,
                )

                reserva_id = st.selectbox("Seleccione reserva para ver constancias", reservas["id"].tolist())
                reserva = reservas[reservas["id"] == int(reserva_id)].iloc[0]

                if reserva["estado"] == "Aprobado":
                    html = generar_constancia_reserva_html(reserva)
                    ruta_reserva = guardar_documento_html(
                        html,
                        DOCUMENTS_DIR / "reservas",
                        f"reserva_{reserva_id}_constancia_aprobada.html"
                    )
                    st.markdown(crear_link_descarga_html(html, f"constancia_reserva_{reserva_id}.html", "Descargar constancia de reserva aprobada"), unsafe_allow_html=True)
                    mostrar_documento_guardado(ruta_reserva, "Descargar constancia guardada de reserva aprobada")

                cierre = cargar_cierre_por_reserva(reserva_id)
                if not cierre.empty:
                    st.subheader("Estado del cierre")
                    st.dataframe(cierre, use_container_width=True)

                    cierre_row = cierre.iloc[0]
                    if cierre_row["estado_validacion"] == "Validado" and reserva["estado"] == "Finalizado":
                        html_final = generar_constancia_cierre_html(reserva, cierre_row)
                        ruta_cierre = guardar_documento_html(
                            html_final,
                            DOCUMENTS_DIR / "cierres",
                            f"reserva_{reserva_id}_constancia_cierre_validado.html"
                        )
                        st.markdown(crear_link_descarga_html(html_final, f"constancia_cierre_{reserva_id}.html", "Descargar constancia final de cierre validado"), unsafe_allow_html=True)
                        mostrar_documento_guardado(ruta_cierre, "Descargar constancia final guardada")
                    else:
                        st.warning("La constancia final se habilita únicamente cuando el administrador valida el cierre.")


# =========================================================
# CIERRE OPERATIVO
# =========================================================

elif menu == "Cierre operativo":
    st.header("Cierre operativo de actividad")

    st.info("Este acceso es para tesistas o responsables operativos. El cierre enviado queda pendiente de validación por el administrador.")

    codigo_maestro = st.text_input("Código maestro del proyecto", type="password")

    if st.button("Buscar reservas para cierre"):
        df_proyectos = cargar_proyectos()
        proy = df_proyectos[df_proyectos["codigo_maestro"] == codigo_maestro.strip()]

        if proy.empty:
            st.error("Código maestro no válido.")
        else:
            proyecto = proy.iloc[0]
            df_res = cargar_reservas()
            reservas = df_res[
                (df_res["proyecto_id"] == int(proyecto["id"])) &
                (df_res["estado"].isin(["Aprobado", "Cierre observado", "Subsanación requerida"]))
            ]

            if reservas.empty:
                st.info("No hay reservas aprobadas o pendientes de subsanación para este proyecto.")
            else:
                st.session_state["codigo_maestro_validado"] = codigo_maestro.strip()
                st.session_state["proyecto_cierre_id"] = int(proyecto["id"])
                st.success("Código validado. Seleccione la reserva a cerrar.")

    if "proyecto_cierre_id" in st.session_state:
        df_res = cargar_reservas()
        reservas = df_res[
            (df_res["proyecto_id"] == int(st.session_state["proyecto_cierre_id"])) &
            (df_res["estado"].isin(["Aprobado", "Cierre observado", "Subsanación requerida"]))
        ]

        if not reservas.empty:
            st.subheader("Reservas disponibles para cierre operativo")
            st.dataframe(
                reservas[
                    [
                        "id",
                        "estado",
                        "fecha_uso",
                        "hora_inicio",
                        "hora_fin",
                        "tipo_actividad",
                        "nombre_proyecto",
                        "responsable_operativo",
                        "recursos",
                    ]
                ],
                use_container_width=True,
            )

            reserva_id = st.selectbox("Seleccione reserva a cerrar", reservas["id"].tolist())
            reserva = reservas[reservas["id"] == int(reserva_id)].iloc[0]
            formulario_cierre_operativo(reserva)


# =========================================================
# PANEL ADMINISTRADOR
# =========================================================

elif menu == "Panel administrador":
    st.header("Panel administrador")

    password = st.text_input("Clave de administrador", type="password")

    if password == ADMIN_PASSWORD:
        st.success("Acceso concedido")

        with st.expander("Exportar registro completo del laboratorio"):
            st.warning("Exportación solo para administrador. Contiene código maestro, trazabilidad, visitantes, cierres y evidencias.")
            output_path = crear_excel_registro()
            with open(output_path, "rb") as file:
                st.download_button(
                    label="Descargar Excel completo",
                    data=file,
                    file_name="registro_laboratorio_interfac.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            st.markdown("### Exportar constancias del mes en ZIP")
            col_zip1, col_zip2 = st.columns(2)
            with col_zip1:
                anio_zip = st.number_input("Año", min_value=2024, max_value=2100, value=date.today().year, step=1)
            with col_zip2:
                mes_zip = st.selectbox(
                    "Mes",
                    list(range(1, 13)),
                    index=date.today().month - 1,
                    format_func=lambda x: f"{x:02d}",
                )

            if st.button("Generar ZIP de constancias del mes"):
                zip_data, total_archivos = crear_zip_constancias_mes(anio_zip, mes_zip)
                st.success(f"ZIP generado con {total_archivos} constancia(s).")
                st.download_button(
                    label="Descargar ZIP de constancias",
                    data=zip_data,
                    file_name=f"constancias_INTERFAC_{int(anio_zip)}_{int(mes_zip):02d}.zip",
                    mime="application/zip",
                )

        tab_proy, tab_res, tab_cierres = st.tabs(["Proyectos", "Reservas", "Validación de cierres"])

        with tab_proy:
            st.subheader("Gestión de proyectos")

            df_proy = cargar_proyectos()

            if df_proy.empty:
                st.info("No hay proyectos registrados.")
            else:
                st.dataframe(df_proy, use_container_width=True)

                proyecto_id = st.selectbox("Seleccione proyecto", df_proy["id"].tolist(), key="admin_proyecto_id")
                proyecto = df_proy[df_proy["id"] == int(proyecto_id)].iloc[0]

                st.markdown("### Detalle del proyecto")
                st.write(proyecto.to_frame(name="Detalle"))

                estado_proyecto = st.selectbox("Estado del proyecto", ESTADOS_PROYECTO, index=ESTADOS_PROYECTO.index(proyecto["estado_proyecto"]) if proyecto["estado_proyecto"] in ESTADOS_PROYECTO else 0)
                responsable_proyecto_edit = st.text_input("Responsable del proyecto", value=str(proyecto.get("responsable_proyecto", "")) if pd.notna(proyecto.get("responsable_proyecto", "")) else "")
                docente_supervisor_edit = st.text_input("Docente o licenciado supervisor", value=str(proyecto.get("docente_supervisor", "")) if pd.notna(proyecto.get("docente_supervisor", "")) else "")
                responsables_autorizados = st.text_area("Responsables autorizados", value=str(proyecto["responsables_autorizados"]))
                observaciones_proyecto = st.text_area("Observaciones del proyecto", value=str(proyecto["observaciones_proyecto"]))

                colp1, colp2 = st.columns(2)

                with colp1:
                    if st.button("Guardar cambios del proyecto"):
                        actualizar_proyecto(proyecto_id, estado_proyecto, responsables_autorizados, observaciones_proyecto, responsable_proyecto_edit, docente_supervisor_edit)
                        st.success("Proyecto actualizado.")
                        st.rerun()

                with colp2:
                    if st.button("Regenerar código maestro del proyecto"):
                        regenerar_codigo_maestro(proyecto_id)
                        st.warning("Código maestro regenerado. El anterior dejará de servir.")
                        st.rerun()

                st.subheader("Historial del proyecto")
                df_res = cargar_reservas()
                res_proy = df_res[df_res["proyecto_id"] == int(proyecto_id)]
                if res_proy.empty:
                    st.info("Este proyecto aún no tiene reservas.")
                else:
                    st.dataframe(res_proy, use_container_width=True)

        with tab_res:
            st.subheader("Gestión de reservas")

            df = cargar_reservas()

            if df.empty:
                st.info("No hay reservas registradas.")
            else:
                colf1, colf2, colf3 = st.columns(3)

                with colf1:
                    filtro_estado = st.selectbox("Filtrar por estado", ["Todos"] + ESTADOS_RESERVA)

                with colf2:
                    filtro_tipo = st.selectbox("Filtrar por tipo de actividad", ["Todos"] + TIPOS_ACTIVIDAD)

                with colf3:
                    filtro_recurso = st.selectbox("Filtrar por recurso", ["Todos"] + RECURSOS)

                df_panel = df.copy()

                if filtro_estado != "Todos":
                    df_panel = df_panel[df_panel["estado"] == filtro_estado]

                if filtro_tipo != "Todos":
                    df_panel = df_panel[df_panel["tipo_actividad"] == filtro_tipo]

                if filtro_recurso != "Todos":
                    df_panel = df_panel[df_panel["recursos"].str.contains(filtro_recurso, na=False, regex=False)]

                columnas_res = [
                    "id",
                    "estado",
                    "codigo_proyecto",
                    "nombre_proyecto",
                    "tipo_reserva",
                    "tipo_actividad",
                    "fecha_uso",
                    "hora_inicio",
                    "hora_fin",
                    "responsable_operativo",
                    "responsable_proyecto_reserva",
                    "docente_supervisor_reserva",
                    "recursos",
                    "visitantes_externos",
                    "grupo_recurrencia",
                ]

                st.dataframe(df_panel[columnas_res], use_container_width=True)

                ids = df_panel["id"].tolist()

                if ids:
                    reserva_id = st.selectbox("Seleccione reserva", ids)
                    reserva = df[df["id"] == int(reserva_id)].iloc[0]

                    st.markdown("### Detalle de reserva")
                    st.write(reserva.to_frame(name="Detalle"))

                    visitantes = cargar_visitantes(reserva_id)

                    if not visitantes.empty:
                        st.markdown("### Visitantes externos")
                        st.dataframe(visitantes, use_container_width=True)

                        asunto, cuerpo = generar_correo_ingreso(reserva_id)
                        st.markdown("### Correo interno para solicitar ingreso")
                        st.text_input("Asunto", asunto)
                        st.text_area("Cuerpo del correo", cuerpo, height=360)

                    cierre = cargar_cierre_por_reserva(reserva_id)
                    if not cierre.empty:
                        st.markdown("### Cierre operativo registrado")
                        st.dataframe(cierre, use_container_width=True)
                        mostrar_evidencias(cierre.iloc[0].get("evidencia_archivos", ""), "Evidencias del cierre")

                    nuevo_estado = st.selectbox(
                        "Actualizar estado de reserva",
                        ESTADOS_RESERVA,
                        index=ESTADOS_RESERVA.index(reserva["estado"]) if reserva["estado"] in ESTADOS_RESERVA else 0,
                    )

                    aplicar_a_grupo = False
                    if str(reserva["grupo_recurrencia"]).strip():
                        aplicar_a_grupo = st.checkbox("Aplicar cambio a toda la reserva recurrente", value=False)

                    colb1, colb2 = st.columns(2)

                    with colb1:
                        if st.button("Guardar cambio de estado"):
                            if nuevo_estado == "Aprobado":
                                if aplicar_a_grupo and str(reserva["grupo_recurrencia"]).strip():
                                    df_grupo = df[df["grupo_recurrencia"] == reserva["grupo_recurrencia"]]
                                    conflictos_grupo = []

                                    for _, r in df_grupo.iterrows():
                                        conflictos = detectar_conflictos(
                                            r["fecha_uso"],
                                            datetime.strptime(r["hora_inicio"], "%H:%M").time(),
                                            datetime.strptime(r["hora_fin"], "%H:%M").time(),
                                            r["recursos"],
                                            excluir_id=r["id"],
                                        )
                                        if not conflictos.empty:
                                            conflictos_grupo.append(conflictos)

                                    if conflictos_grupo:
                                        st.error("No se puede aprobar todo el grupo porque existen cruces.")
                                        st.dataframe(pd.concat(conflictos_grupo), use_container_width=True)
                                    else:
                                        actualizar_estado_grupo(reserva["grupo_recurrencia"], nuevo_estado)
                                        st.success("Estado actualizado para toda la reserva recurrente.")
                                        st.rerun()

                                else:
                                    conflictos = detectar_conflictos(
                                        reserva["fecha_uso"],
                                        datetime.strptime(reserva["hora_inicio"], "%H:%M").time(),
                                        datetime.strptime(reserva["hora_fin"], "%H:%M").time(),
                                        reserva["recursos"],
                                        excluir_id=reserva_id,
                                    )

                                    if not conflictos.empty:
                                        st.error("No se puede aprobar porque existe cruce con otra reserva bloqueante.")
                                        st.dataframe(conflictos, use_container_width=True)
                                    else:
                                        actualizar_estado_reserva(reserva_id, nuevo_estado)
                                        st.success("Estado actualizado correctamente.")
                                        st.rerun()
                            else:
                                if aplicar_a_grupo and str(reserva["grupo_recurrencia"]).strip():
                                    actualizar_estado_grupo(reserva["grupo_recurrencia"], nuevo_estado)
                                    st.success("Estado actualizado para toda la reserva recurrente.")
                                else:
                                    actualizar_estado_reserva(reserva_id, nuevo_estado)
                                    st.success("Estado actualizado correctamente.")
                                st.rerun()

                    with colb2:
                        if st.button("Eliminar esta reserva"):
                            eliminar_reserva(reserva_id)
                            st.warning("Reserva eliminada.")
                            st.rerun()

                    if reserva["estado"] == "Aprobado":
                        st.markdown("### Constancia de reserva aprobada")
                        html = generar_constancia_reserva_html(reserva)
                        ruta_reserva = guardar_documento_html(
                            html,
                            DOCUMENTS_DIR / "reservas",
                            f"reserva_{reserva_id}_constancia_aprobada.html"
                        )
                        st.markdown(
                            crear_link_descarga_html(html, f"constancia_reserva_{reserva_id}.html", "Descargar constancia de reserva aprobada"),
                            unsafe_allow_html=True,
                        )
                        mostrar_documento_guardado(ruta_reserva, "Descargar constancia guardada de reserva aprobada")

        with tab_cierres:
            st.subheader("Validación de cierres operativos")

            df_cierres = cargar_cierres()

            if df_cierres.empty:
                st.info("No hay cierres registrados.")
            else:
                st.dataframe(
                    df_cierres[
                        [
                            "reserva_id",
                            "codigo_proyecto",
                            "nombre_proyecto",
                            "fecha_uso",
                            "estado_reserva",
                            "estado_validacion",
                            "responsable_cierre",
                            "fecha_cierre_operativo",
                            "estado_cierre_operativo",
                            "incidencias",
                        ]
                    ],
                    use_container_width=True,
                )

                reserva_id_cierre = st.selectbox("Seleccione cierre a validar", df_cierres["reserva_id"].tolist())
                cierre = df_cierres[df_cierres["reserva_id"] == int(reserva_id_cierre)].iloc[0]

                df_res = cargar_reservas()
                reserva = df_res[df_res["id"] == int(reserva_id_cierre)].iloc[0]

                st.markdown("### Detalle del cierre operativo")
                st.write(cierre.to_frame(name="Detalle"))

                mostrar_evidencias(cierre.get("evidencia_archivos", ""), "Evidencias del cierre")

                estado_validacion = st.selectbox(
                    "Estado de validación del administrador",
                    ESTADOS_VALIDACION_CIERRE,
                    index=ESTADOS_VALIDACION_CIERRE.index(cierre["estado_validacion"]) if cierre["estado_validacion"] in ESTADOS_VALIDACION_CIERRE else 0,
                )

                observacion_administrador = st.text_area(
                    "Observación del administrador",
                    value=str(cierre["observacion_administrador"]) if pd.notna(cierre["observacion_administrador"]) else "",
                    placeholder="Ejemplo: cierre conforme / requiere subir evidencia adicional / subsanar limpieza del área.",
                )

                administrador_valida = st.text_input(
                    "Administrador que valida",
                    value=str(cierre["administrador_valida"]) if pd.notna(cierre["administrador_valida"]) and str(cierre["administrador_valida"]).strip() else "Carlos Manuel Escobar Galindo",
                )

                if st.button("Guardar validación del cierre"):
                    if not administrador_valida.strip():
                        st.error("Debe indicar el administrador que valida.")
                    else:
                        validar_cierre(reserva_id_cierre, estado_validacion, observacion_administrador, administrador_valida)
                        st.success("Validación guardada correctamente.")
                        st.rerun()

                cierre_actualizado = cargar_cierre_por_reserva(reserva_id_cierre)
                if not cierre_actualizado.empty:
                    cierre_row = cierre_actualizado.iloc[0]
                    if cierre_row["estado_validacion"] == "Validado":
                        st.markdown("### Constancia final de cierre validado")
                        html_final = generar_constancia_cierre_html(reserva, cierre_row)
                        ruta_cierre = guardar_documento_html(
                            html_final,
                            DOCUMENTS_DIR / "cierres",
                            f"reserva_{reserva_id_cierre}_constancia_cierre_validado.html"
                        )
                        st.markdown(
                            crear_link_descarga_html(html_final, f"constancia_cierre_{reserva_id_cierre}.html", "Descargar constancia final de cierre validado"),
                            unsafe_allow_html=True,
                        )
                        mostrar_documento_guardado(ruta_cierre, "Descargar constancia final guardada")

    elif password:
        st.error("Clave incorrecta")


# =========================================================
# HISTORIAL Y AUDITORÍA
# =========================================================

elif menu == "Historial y auditoría":
    st.header("Historial y auditoría del laboratorio")

    password = st.text_input("Clave de administrador", type="password")

    if password == ADMIN_PASSWORD:
        st.success("Acceso concedido")

        df_proyectos = cargar_proyectos()
        df_reservas = cargar_reservas()
        df_cierres = cargar_cierres()

        st.subheader("Indicadores generales")

        total_proyectos = len(df_proyectos)
        total_reservas = len(df_reservas)
        total_finalizadas = len(df_reservas[df_reservas["estado"] == "Finalizado"]) if not df_reservas.empty else 0
        total_cierres = len(df_cierres)
        total_incidencias = 0

        if not df_cierres.empty:
            total_incidencias = len(
                df_cierres[
                    ~df_cierres["incidencias"].astype(str).str.lower().str.contains("no hubo incidencias", na=False)
                ]
            )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Proyectos registrados", total_proyectos)
        col2.metric("Reservas registradas", total_reservas)
        col3.metric("Reservas finalizadas", total_finalizadas)
        col4.metric("Cierres con posible incidencia", total_incidencias)

        st.subheader("Historial por proyecto")

        if df_proyectos.empty:
            st.info("No hay proyectos registrados.")
        else:
            df_proyectos["label"] = df_proyectos["codigo_proyecto"] + " | " + df_proyectos["nombre_proyecto"]
            proyecto_label = st.selectbox("Seleccione proyecto", df_proyectos["label"].tolist())
            proyecto_id = int(df_proyectos[df_proyectos["label"] == proyecto_label]["id"].iloc[0])

            st.markdown("### Reservas del proyecto")
            res = df_reservas[df_reservas["proyecto_id"] == proyecto_id] if not df_reservas.empty else pd.DataFrame()
            if res.empty:
                st.info("Este proyecto no tiene reservas.")
            else:
                st.dataframe(res, use_container_width=True)

            st.markdown("### Cierres del proyecto")
            if not df_cierres.empty:
                cierres_proy = df_cierres[df_cierres["codigo_proyecto"].isin(df_proyectos[df_proyectos["id"] == proyecto_id]["codigo_proyecto"].tolist())]
                if cierres_proy.empty:
                    st.info("Este proyecto no tiene cierres.")
                else:
                    st.dataframe(cierres_proy, use_container_width=True)

                    reserva_evidencia = st.selectbox("Seleccione reserva para ver evidencias", cierres_proy["reserva_id"].tolist())
                    cierre_sel = cierres_proy[cierres_proy["reserva_id"] == int(reserva_evidencia)].iloc[0]
                    mostrar_evidencias(cierre_sel.get("evidencia_archivos", ""), "Evidencias del cierre")
            else:
                st.info("Aún no hay cierres registrados.")

        st.subheader("Uso por recurso")
        if not df_reservas.empty:
            conteo_recursos = []
            for _, row in df_reservas.iterrows():
                for recurso in recursos_a_lista(row["recursos"]):
                    conteo_recursos.append({"recurso": recurso, "estado": row["estado"], "fecha_uso": row["fecha_uso"]})
            df_rec = pd.DataFrame(conteo_recursos)
            if not df_rec.empty:
                st.dataframe(df_rec.groupby(["recurso", "estado"]).size().reset_index(name="n_reservas"), use_container_width=True)

    elif password:
        st.error("Clave incorrecta")
