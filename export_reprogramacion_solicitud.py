"""
Descarga todas las HU de la épica "Migración Agro: Reprogramación - Solicitud"
(AGIL-1243) con todo su detalle y las guarda en reprogramacion_solicitud.json.

Uso:
    python3 export_reprogramacion_solicitud.py                    # épica por defecto
    python3 export_reprogramacion_solicitud.py "Nombre de la épica"
    python3 export_reprogramacion_solicitud.py AGIL-1243          # por key
"""
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

from jira_api import JiraAPI

load_dotenv()

HOST     = os.getenv("JIRA_HOST", "").rstrip("/")
USERNAME = os.getenv("JIRA_USERNAME", "")
TOKEN    = os.getenv("JIRA_API_TOKEN", "")
EPIC_PROJECT = os.getenv("JIRA_EPIC_PROJECT", "AGIL")

OUT_PATH = "reprogramacion_solicitud.json"

DEFAULT_EPIC = "Migración Agro: Reprogramación - Solicitud"

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


def resolve_epic_key(jira, epic):
    """Si `epic` ya parece un key (AGIL-123) lo devuelve; si no, lo busca por summary."""
    parts = epic.split("-")
    if len(parts) == 2 and parts[0].isalpha() and parts[1].isdigit():
        return epic

    jql = f'project = {EPIC_PROJECT} AND issuetype = Epic AND summary ~ "{epic}" ORDER BY key'
    r = _get(jira._url("/search"), jira.headers,
             {"jql": jql, "maxResults": 50, "fields": "summary"})
    issues = r.json().get("issues", [])

    for it in issues:
        if it["fields"]["summary"].strip() == epic.strip():
            return it["key"]
    if len(issues) == 1:
        return issues[0]["key"]
    if not issues:
        raise SystemExit(f"❌ No se encontró ninguna épica que matchee: {epic!r}")
    opts = ", ".join(f'{it["key"]} ({it["fields"]["summary"]})' for it in issues)
    raise SystemExit(f"❌ Varias épicas coinciden, especifica el key. Candidatas: {opts}")


def epic_issue_keys(jira, epic_key):
    """Todas las HU/issues vinculadas a la épica, vía API Agile."""
    keys, start = [], 0
    while True:
        r = _get(jira._agile_url(f"/epic/{epic_key}/issue"), jira.headers,
                 {"startAt": start, "maxResults": 100, "fields": "summary"})
        data = r.json()
        items = data.get("issues", [])
        keys.extend(it["key"] for it in items)
        if not items or len(keys) >= data.get("total", 0):
            break
        start += len(items)
    return keys


def fetch_issue(jira, key):
    r = _get(jira._url(f"/issue/{key}"), jira.headers,
             {"fields": FIELDS, "expand": "renderedFields"})
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
    epic = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EPIC

    jira = JiraAPI(HOST, USERNAME, TOKEN)
    me = jira.get_myself()
    if not me:
        return
    print(f"✓ Conectado como: {me.get('displayName')} ({me.get('name')})")

    epic_key = resolve_epic_key(jira, epic)
    print(f"✓ Épica: {epic_key}")

    keys = epic_issue_keys(jira, epic_key)
    print(f"✓ {len(keys)} incidencias vinculadas a la épica")

    issues = []
    for key in keys:
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
