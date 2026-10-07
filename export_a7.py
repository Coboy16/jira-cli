"""
Descarga el detalle completo (desde Jira) de las HU del carril
"Nuevo destino Agropecuario: WASI - Evaluación/Propuesta" y las
guarda en a7.json, agregando la metadata declarada (asignado, tipo,
prioridad, horas) que traía el listado original.

Uso:
    python3 export_a7.py
"""
import json
import os
import time

import requests
from dotenv import load_dotenv

from jira_api import JiraAPI

load_dotenv()

HOST     = os.getenv("JIRA_HOST", "").rstrip("/")
USERNAME = os.getenv("JIRA_USERNAME", "")
TOKEN    = os.getenv("JIRA_API_TOKEN", "")

OUT_PATH = "a7.json"
CARRIL   = "Nuevo destino Agropecuario: WASI - Evaluación/Propuesta"

# Metadata declarada originalmente (título, asignado, tipo, prioridad, horas).
# El detalle real (summary/description/status/etc.) se trae de Jira.
DECLARADAS = [
    {"key": "FCBIN-2943", "titulo": "Registro de Disponibilidad y Cuentas por Cobrar", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-2944", "titulo": "Gestión de Adelanto de Proveedores", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-2945", "titulo": "Registro de Inventario en Activos Corrientes - Inventarios", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-2946", "titulo": "Registro de Activos Fijos (No Corrientes)", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-2947", "titulo": "Registro de FINES DE VIVIENDA (Destino del Crédito)", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3174", "titulo": "Visualización y Estructura de Pasivos Corrientes", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3175", "titulo": "Sincronización Automática de Deudas (Pre-Evaluador)", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3176", "titulo": "Edición y Detalle de Obligaciones Financieras", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3177", "titulo": "Registro Manual de Cuentas por Pagar", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3178", "titulo": "Gestión de Pasivos No Corrientes y Lógica de Flujo", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3179", "titulo": "Clasificación automática de deudas a Pasivo No Corriente", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3180", "titulo": "Visualización y detalle de Cuentas por Pagar No Corrientes", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3181", "titulo": "Visualización y Categorización de Referencias", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3182", "titulo": "Formulario de Registro de Referencias", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3183", "titulo": "Estructura y Dimensiones del Cuestionario No Financiero", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3184", "titulo": "Validación y Guardado de la Evaluación No Financiera", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3185", "titulo": "Acceso Condicional a Evaluación PYME (Cliente Recurrente)", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3186", "titulo": "Cálculo de Costos con Márgenes Preestablecidos por Giro", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3187", "titulo": "Consolidación de Gastos Familiares y Operativos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3188", "titulo": "Visualización de Resumen PYME y Capacidad de Pago", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3189", "titulo": "Registro de información en la pestaña Gastos Familiares (Clientes Nuevos)", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3190", "titulo": "Registro de Otros Ingresos en la pestaña Gastos Familiares", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3191", "titulo": "Estructura General de la vista Evaluación PYME para Clientes Nuevos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3192", "titulo": "Registro y Gestión de Otros Ingresos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3193", "titulo": "Registro y Gestión de Gastos de la Unidad Familiar", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3194", "titulo": "Ocultamiento dinámico de opciones registradas en Gastos de la Unidad Familiar", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3195", "titulo": "Registro de Ventas y Costos por Tipo de Negocio (Giros)", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3196", "titulo": "Registro detallado de Giros Comerciales en Ventas/Costos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3197", "titulo": "Estructura y visualización de Gastos Operativos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3198", "titulo": "Registro de información en Gastos Operativos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3199", "titulo": "Registro de información en Otros Gastos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3200", "titulo": "Estructura y campos visuales del Resumen PYME", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3201", "titulo": "Visualización y cálculo automático del Resumen PYME", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3202", "titulo": "Registro de Garantías para el Sustento del Crédito", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3203", "titulo": "Validación de Documentación de Garantía", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3204", "titulo": "Registro de Rendimiento Escalonado mediante Modal", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3205", "titulo": "Validación y Listado de Rendimientos Escalonados", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3206", "titulo": "Cálculos Acumulados y Validación de Rendimiento por Hectárea", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3207", "titulo": "Proyección de Calendario Escalonado y Rendimientos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3208", "titulo": "Registro de Campaña Agrícola con Calendario Mensual", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3209", "titulo": "Selección de Parámetros Agrícolas mediante Desplegables", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3210", "titulo": "Selección de la Modalidad de Calendario de Campaña", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3211", "titulo": "Cálculo Automático de Rendimiento y Bloqueo de Campos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3212", "titulo": "Registro de Datos Generales de la Parcela e Indicador de Financiamiento", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3213", "titulo": "Ayuda informativa sobre clasificación de tipos de cultivo", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3214", "titulo": "Selección de Modalidad de Calendario \"Estacional\" y Cronograma", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3215", "titulo": "Ingreso de Variables de Cosecha y Cálculo Automático (Estacional)", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3216", "titulo": "Actualización Dinámica de Campos Dependientes en Catálogos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3217", "titulo": "Lógica de Transición entre Modalidades de Calendario Agrícola", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3218", "titulo": "Validación de Fechas de Campaña y Topes de Producción", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3219", "titulo": "Registro y Cálculo de Egresos Agrícolas", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3220", "titulo": "Registro y Cálculo de Egresos Agrícolas Inversión Realizada y Falta Invertir", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3221", "titulo": "Calculo de Resumen de cultivos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3222", "titulo": "Gestión de Formulario Pecuario con Navegación por Pestañas y Progreso", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3223", "titulo": "Selección de Actividad Pecuaria y Tipo de Calendario", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3224", "titulo": "Cálculo Dinámico de Ingresos Pecuarios según Actividad", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3225", "titulo": "Declaración de Ingresos Secundarios y Frecuencia de Subproductos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3226", "titulo": "Selección de Actividad Pecuaria y Calendario Escalonado", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3227", "titulo": "Registro y Cálculo en la Matriz de Ingresos Escalonados", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3228", "titulo": "Registro de Subproductos y Comentarios de la Actividad", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3229", "titulo": "Configuración de Actividad Pecuaria en Modalidad Estacional", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3230", "titulo": "Cálculo Matemático de Ingresos Pecuarios Estacionales", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3231", "titulo": "Declaración de Ingresos Secundarios Estacionales", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3232", "titulo": "Registro Dinámico de Egresos Pecuarios por Categoría", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3233", "titulo": "Cálculo Automático de Total de Gastos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3234", "titulo": "Definición de Tipo de Gasto (Mensual/Estacional) y Fechas", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3235", "titulo": "Resumen Pecuario y Análisis de Rentabilidad", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3236", "titulo": "Exclusión de Ítems Seleccionados en Registro de Gastos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3237", "titulo": "Registro de Gastos con Requerimiento Editable (Categoría OTROS)", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3238", "titulo": "Registro de Otros Egresos en Evaluación Financiera", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3239", "titulo": "Visualización de Resumen Agro y Alerta de Ratios", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3240", "titulo": "Validación de gestor documental", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3241", "titulo": "Identificación Visual de Documentación Obligatoria Pendiente", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3242", "titulo": "Validación y Envío del Expediente Agropecuario", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3243", "titulo": "Acceso a la gestión de Garantías desde la pantalla de Propuesta", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3244", "titulo": "Visualización segmentada y detallada de las Garantías", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3245", "titulo": "Selección múltiple y acción de Asociar Garantías", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3246", "titulo": "Selección múltiple y acción de Asociar Garantías", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3247", "titulo": "VALIDACIÓN DE CONTRATACIÓN ELECTRONICA", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3248", "titulo": "VALIDACIÓN DE COMITE ORDINARIO", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3249", "titulo": "Procedimiento de administración de expedientes de créditos", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3250", "titulo": "Funciones del comite de crédito", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3251", "titulo": "Visualización de Totales del Flujo de Caja", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3252", "titulo": "Acceso a la Vista Detallada de Flujo de Caja por Categorías", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3253", "titulo": "Visualización Consolidada en Formato Extendido (Landscape)", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3254", "titulo": "Navegación y acceso a la pestaña de Diseño Crediticio", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3255", "titulo": "Configuración del Monto Propuesto y Necesidad del crédito en la cabecera", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3256", "titulo": "Visualización e ingreso de parámetros en la tabla de Diseño Crediticio", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3257", "titulo": "Registro y Gestión de la Evaluación Cualitativa del Cliente", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3258", "titulo": "VALIDACIÓN DE CONTRATACIÓN ELECTRONICA", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3259", "titulo": "Configuración de los Datos de la Solicitud y el Producto", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3260", "titulo": "Configuración de los Datos de la Solicitud y el Producto", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3261", "titulo": "Revisión de Políticas y Justificación de Excepciones", "asignado": "Usuario Externo QOXIT12", "tipo": "Historia", "prioridad": "Bajo", "horas": "4h"},
    {"key": "FCBIN-3262", "titulo": "Visualización de Criterios de Autonomía y Situación Final (título truncado en el documento fuente)", "asignado": None, "tipo": None, "prioridad": None, "horas": None},
]

FIELDS = (
    "summary,status,assignee,reporter,priority,issuetype,description,"
    "labels,components,created,updated,duedate,parent,customfield_10100,"
    "subtasks,issuelinks,fixVersions,attachment,comment"
)


def _get(url, headers, params, timeout=20, retries=5):
    """GET con reintentos y backoff ante 429 / errores transitorios."""
    for attempt in range(retries):
        r = requests.get(url, headers=headers, params=params, timeout=timeout)
        if r.status_code == 429 or r.status_code >= 500:
            wait = float(r.headers.get("Retry-After", 2 ** attempt))
            time.sleep(min(wait, 30))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r


def fetch_issue(jira, key, declarada):
    r = _get(
        jira._url(f"/issue/{key}"),
        jira.headers,
        {"fields": FIELDS, "expand": "renderedFields"},
    )
    item = r.json()
    f = item.get("fields", {})
    rf = item.get("renderedFields", {}) or {}

    assignee = f.get("assignee") or {}
    reporter = f.get("reporter") or {}
    priority = f.get("priority") or {}
    issuetype = f.get("issuetype") or {}
    parent = f.get("parent") or {}

    attachments = []
    for att in f.get("attachment", []) or []:
        attachments.append({
            "id": att.get("id"),
            "name": att.get("filename"),
            "mime": att.get("mimeType"),
            "size": att.get("size"),
            "created": att.get("created"),
            "url": f"{jira.host}/secure/attachment/{att.get('id')}/{att.get('filename')}",
        })

    comments = []
    for c in (f.get("comment") or {}).get("comments", []) or []:
        author = c.get("author") or {}
        comments.append({
            "author": author.get("displayName", ""),
            "created": c.get("created"),
            "updated": c.get("updated"),
            "body": c.get("body", ""),
        })

    links = []
    for l in f.get("issuelinks", []) or []:
        lt = l.get("type", {})
        if l.get("outwardIssue"):
            links.append({
                "type": lt.get("outward"),
                "key": l["outwardIssue"]["key"],
                "summary": l["outwardIssue"]["fields"]["summary"],
            })
        elif l.get("inwardIssue"):
            links.append({
                "type": lt.get("inward"),
                "key": l["inwardIssue"]["key"],
                "summary": l["inwardIssue"]["fields"]["summary"],
            })

    return {
        "key": item.get("key"),
        "url": f"{jira.host}/browse/{item.get('key')}",
        "carril": CARRIL,
        "titulo_declarado": declarada.get("titulo"),
        "asignado_declarado": declarada.get("asignado"),
        "tipo_declarado": declarada.get("tipo"),
        "prioridad_declarada": declarada.get("prioridad"),
        "horas_declaradas": declarada.get("horas"),
        "summary": f.get("summary", ""),
        "issuetype": issuetype.get("name", ""),
        "status": (f.get("status") or {}).get("name", ""),
        "priority": priority.get("name", ""),
        "assignee": assignee.get("displayName", "Sin asignar"),
        "reporter": reporter.get("displayName", ""),
        "created": f.get("created"),
        "updated": f.get("updated"),
        "duedate": f.get("duedate"),
        "labels": f.get("labels", []),
        "components": [c.get("name") for c in f.get("components", []) or []],
        "fix_versions": [v.get("name") for v in f.get("fixVersions", []) or []],
        "epic_key": f.get("customfield_10100"),
        "parent": {"key": parent.get("key"), "summary": (parent.get("fields") or {}).get("summary")} if parent else None,
        "subtasks": [
            {"key": s.get("key"), "summary": s.get("fields", {}).get("summary", ""),
             "status": s.get("fields", {}).get("status", {}).get("name", "")}
            for s in f.get("subtasks", []) or []
        ],
        "links": links,
        "description": f.get("description") or "",
        "description_html": rf.get("description") or "",
        "attachments": attachments,
        "comments": comments,
    }


def main():
    jira = JiraAPI(HOST, USERNAME, TOKEN)
    me = jira.get_myself()
    if not me:
        return
    print(f"✓ Conectado como: {me.get('displayName')} ({me.get('name')})")

    issues = []
    for declarada in DECLARADAS:
        key = declarada["key"]
        try:
            data = fetch_issue(jira, key, declarada)
            issues.append(data)
            print(f"  ✓ {key} — {data['summary']}")
        except Exception as e:
            print(f"  ✗ {key} — error: {e}")
            issues.append({"key": key, "url": f"{HOST}/browse/{key}", **declarada, "error": str(e)})
        time.sleep(0.4)

    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(issues, fh, ensure_ascii=False, indent=2)

    print(f"\n✓ {len(issues)} HU guardadas en {OUT_PATH}")


if __name__ == "__main__":
    main()
