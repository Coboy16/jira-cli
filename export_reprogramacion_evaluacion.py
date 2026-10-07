"""
Descarga las HU del carril "Migración Agro: Reprogramación - Evaluación/Propuesta"
y las guarda con todo su detalle en reprogramacion_evaluacion_propuesta.json.

Uso:
    python3 export_reprogramacion_evaluacion.py
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

OUT_PATH = "reprogramacion_evaluacion_propuesta.json"

KEYS = [
    # En Progreso
    "FCBIN-3072",
    "FCBIN-3073",
    "FCBIN-3074",
    "FCBIN-3315",
    # En Revisión
    "FCBIN-2912",
    "FCBIN-2913",
    "FCBIN-2914",
    "FCBIN-2915",
    "FCBIN-2916",
    "FCBIN-2917",
    "FCBIN-2918",
    "FCBIN-2919",
    "FCBIN-2920",
    "FCBIN-2921",
    "FCBIN-2922",
    "FCBIN-2923",
    "FCBIN-2924",
    "FCBIN-2925",
    "FCBIN-3029",
    "FCBIN-3030",
    "FCBIN-3031",
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


def fetch_issue(jira, key):
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
    for key in KEYS:
        try:
            data = fetch_issue(jira, key)
            issues.append(data)
            print(f"  ✓ {key} — {data['summary']}")
        except Exception as e:
            print(f"  ✗ {key} — error: {e}")
            issues.append({"key": key, "error": str(e)})
        time.sleep(0.4)

    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(issues, fh, ensure_ascii=False, indent=2)

    print(f"\n✓ {len(issues)} HU guardadas en {OUT_PATH}")


if __name__ == "__main__":
    main()
