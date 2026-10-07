"""
Exporta las HU de las épicas "Migración Agro" (Ampliación / Reprogramación)
del sprint activo, cruzadas contra el asignado, a JSON y CSV.

Uso:
    python3 export_agro.py                  # las 13 épicas (Ampliación + Reprogramación)
    python3 export_agro.py ampliacion        # solo las 7 épicas de Ampliación
    python3 export_agro.py reprogramacion    # solo las 6 épicas de Reprogramación
"""
import csv
import json
import os
import sys

from dotenv import load_dotenv

from jira_api import JiraAPI

load_dotenv()

HOST     = os.getenv("JIRA_HOST", "").rstrip("/")
USERNAME = os.getenv("JIRA_USERNAME", "")
TOKEN    = os.getenv("JIRA_API_TOKEN", "")
PROJECT  = os.getenv("JIRA_PROJECT", "")
BOARD_ID = os.getenv("JIRA_BOARD_ID", "")
EPIC_PROJECT = os.getenv("JIRA_EPIC_PROJECT", "AGIL")

OUT_DIR = "exports"


def find_agro_epics(jira, keyword="Migración Agro"):
    """Épicas del proyecto de épicas cuyo resumen matchea el keyword y
    pertenecen a un flujo de Ampliación/Reprogramación (no genéricas)."""
    import requests

    jql = f'project = {EPIC_PROJECT} AND issuetype = Epic AND summary ~ "{keyword}" ORDER BY key'
    r = requests.get(
        jira._url("/search"),
        headers=jira.headers,
        params={"jql": jql, "maxResults": 50, "fields": "summary"},
        timeout=20,
    )
    r.raise_for_status()
    epics = []
    for it in r.json().get("issues", []):
        summary = it["fields"]["summary"]
        if "Ampliación" in summary or "Reprogramación" in summary:
            epics.append((it["key"], summary))
    return epics


ISSUE_FIELDS = "summary,status,assignee,customfield_10100,description"


def _issues_from_sprint(jira, sprint_id, project, max_results=1000):
    """Igual que JiraAPI._issues_from_sprint pero pidiendo también description."""
    import requests

    all_issues, start = [], 0
    while True:
        params = {
            "startAt":    start,
            "maxResults": min(max_results - len(all_issues), 100),
            "fields":     ISSUE_FIELDS,
            "jql":        f"project = {project}",
        }
        r = requests.get(
            jira._agile_url(f"/sprint/{sprint_id}/issue"),
            headers=jira.headers,
            params=params,
            timeout=15,
        )
        if r.status_code != 200:
            break
        data  = r.json()
        items = data.get("issues", [])
        all_issues.extend(items)
        if not items or len(all_issues) >= data.get("total", 0) or len(all_issues) >= max_results:
            break
        start += len(items)
    return all_issues


def issues_in_active_sprints(jira, board_id, project):
    """Todas las issues del proyecto en los sprints activos del board,
    indexadas por key (deduplicadas si hay más de un sprint activo)."""
    sprints = jira._get_active_sprints(board_id)
    all_issues = {}
    for sprint in sprints:
        for it in _issues_from_sprint(jira, sprint["id"], project):
            all_issues[it["key"]] = it
    return all_issues


SCOPES = {
    "ampliacion": ("Ampliación", "ampliacion"),
    "reprogramacion": ("Reprogramación", "reprogramacion"),
}


def main():
    scope = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    if scope != "all" and scope not in SCOPES:
        print(f"❌ scope inválido: {scope!r}. Usa: ampliacion, reprogramacion o nada (todas).")
        return

    jira = JiraAPI(HOST, USERNAME, TOKEN, board_id=BOARD_ID)
    me = jira.get_myself()
    if not me:
        return
    me_name = me.get("name")

    print(f"✓ Conectado como: {me.get('displayName')} ({me_name})")

    epics = find_agro_epics(jira)
    if scope != "all":
        needle, _ = SCOPES[scope]
        epics = [(k, label) for k, label in epics if needle in label]
    print(f"✓ {len(epics)} épicas encontradas en {EPIC_PROJECT}" + (f" (scope={scope})" if scope != "all" else ""))

    all_issues = issues_in_active_sprints(jira, BOARD_ID, PROJECT)
    print(f"✓ {len(all_issues)} issues en el/los sprint(s) activo(s) de {PROJECT}")

    by_epic = {key: [] for key, _ in epics}
    for it in all_issues.values():
        epic_key = it["fields"].get("customfield_10100")
        if epic_key in by_epic:
            by_epic[epic_key].append(it)

    groups = []
    for key, label in epics:
        issues = sorted(by_epic[key], key=lambda x: x["key"])
        group = {"key": key, "label": label, "found": len(issues), "issues": []}
        for it in issues:
            fields = it["fields"]
            assignee = fields.get("assignee") or {}
            group["issues"].append({
                "key": it["key"],
                "summary": fields["summary"],
                "description": fields.get("description") or "",
                "status": fields["status"]["name"],
                "assignee": assignee.get("displayName", "Sin asignar"),
                "mine": assignee.get("name") == me_name,
            })
        groups.append(group)

    os.makedirs(OUT_DIR, exist_ok=True)

    suffix = SCOPES[scope][1] if scope != "all" else "agro"
    json_path = os.path.join(OUT_DIR, f"{suffix}_data.json" if scope != "all" else "agro_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)

    csv_name = f"migracion_{suffix}_HU.csv" if scope != "all" else "migracion_agro_HU.csv"
    csv_path = os.path.join(OUT_DIR, csv_name)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Carril / Épica", "Clave épica", "Issue", "Resumen", "Descripción", "Estado", "Asignado", "Es mía"])
        for group in groups:
            for issue in group["issues"]:
                w.writerow([
                    group["label"], group["key"], issue["key"], issue["summary"],
                    issue["description"], issue["status"], issue["assignee"],
                    "SI" if issue["mine"] else "NO",
                ])

    total = sum(g["found"] for g in groups)
    total_mine = sum(1 for g in groups for i in g["issues"] if i["mine"])
    print(f"\n✓ {total} HU exportadas ({total_mine} asignadas a mí)")
    print(f"  → {json_path}")
    print(f"  → {csv_path}")


if __name__ == "__main__":
    main()
