from dotenv import load_dotenv, set_key
import os
import sys
import shutil
import requests
from pathlib import Path

load_dotenv()

host     = os.getenv("JIRA_HOST", "").rstrip("/")
username = os.getenv("JIRA_USERNAME", "")
token    = os.getenv("JIRA_API_TOKEN", "")
project  = os.getenv("JIRA_PROJECT", "")
board_id = os.getenv("JIRA_BOARD_ID", "") or None

if host == "https://TU-EMPRESA.atlassian.net":
    host = ""

if not all([host, username, token, project]):
    env_path    = Path(".env")
    example_path = Path(".env.example")
    if not env_path.exists() and example_path.exists():
        shutil.copy(example_path, env_path)
    print(
        "\n⚠️  Completa el archivo .env con tus credenciales de Jira y vuelve a ejecutar.\n"
        "    Token: https://id.atlassian.com/manage-profile/security/api-tokens\n"
    )
    sys.exit(1)

from jira_api import JiraAPI
from tui import run_app, RESET, BOLD, DIM, C_CYAN, C_GREEN, C_YELLOW, C_RED, get_key, read_line

jira = JiraAPI(host, username, token, board_id=board_id)

me = jira.get_myself()
if not me:
    sys.exit(1)

print(f"\n✓  Conectado como: {me.get('displayName')}")


def fetch_projects():
    try:
        r = requests.get(
            f"{host}/rest/api/2/project",
            headers=jira.headers,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def validate_project(key, projects):
    return any(p["key"] == key for p in projects)


def pick_project(projects):
    print(f"\n  {C_YELLOW}⚠  El proyecto '{project}' no existe en este servidor.{RESET}")
    print(f"  {DIM}Proyectos disponibles:{RESET}\n")
    for i, p in enumerate(projects, 1):
        print(f"  {DIM}[{i:2d}]{RESET}  {C_CYAN}{p['key']:<15}{RESET}  {p['name']}")
    print()
    while True:
        choice = read_line("  Elige número de proyecto: ")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(projects):
                chosen = projects[idx]
                # Save to .env
                env_path = Path(".env")
                if env_path.exists():
                    set_key(str(env_path), "JIRA_PROJECT", chosen["key"])
                    print(f"\n  {C_GREEN}✓ Proyecto guardado en .env: {chosen['key']}{RESET}\n")
                return chosen["key"]
            print(f"  {C_RED}Número fuera de rango.{RESET}")
        except ValueError:
            print(f"  {C_RED}Ingresa un número válido.{RESET}")


projects = fetch_projects()

if projects and not validate_project(project, projects):
    project = pick_project(projects)
elif not projects:
    print(f"  {C_YELLOW}⚠  No se pudo obtener la lista de proyectos. Usando '{project}' del .env.{RESET}\n")

print(f"  {DIM}Proyecto: {project}{RESET}\n")
run_app(jira, project)
