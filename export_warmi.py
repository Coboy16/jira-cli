"""
Descarga las HU de los carriles "Nuevo Subtipo Agropecuario: WARMI"
(Solicitud y Evaluación/Propuesta) y las guarda en warmi.json.

Uso:
    python3 export_warmi.py
"""
import json
import time

from export_reprogramacion_evaluacion import HOST, TOKEN, USERNAME, fetch_issue
from jira_api import JiraAPI

OUT_PATH = "warmi.json"

LANES = {
    "Nuevo Subtipo Agropecuario: WARMI - Solicitud": [
        "FCBIN-3381",
        "FCBIN-3383",
        "FCBIN-3384",
    ],
    "Nuevo Subtipo Agropecuario: WARMI - Evaluación/Propuesta": [
        "FCBIN-3385",
        "FCBIN-3386",
    ],
}


def main():
    jira = JiraAPI(HOST, USERNAME, TOKEN)
    me = jira.get_myself()
    if not me:
        return
    print(f"✓ Conectado como: {me.get('displayName')} ({me.get('name')})")

    issues = []
    for lane, keys in LANES.items():
        print(f"\n{lane}")
        for key in keys:
            try:
                data = fetch_issue(jira, key)
                data["lane"] = lane
                issues.append(data)
                print(f"  ✓ {key} — {data['summary']}")
            except Exception as e:
                print(f"  ✗ {key} — error: {e}")
                issues.append({"key": key, "lane": lane, "error": str(e)})
            time.sleep(0.4)

    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(issues, fh, ensure_ascii=False, indent=2)

    print(f"\n✓ {len(issues)} HU guardadas en {OUT_PATH}")


if __name__ == "__main__":
    main()
