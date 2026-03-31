from dotenv import load_dotenv
import os
import sys
import shutil
from pathlib import Path

load_dotenv()

host    = os.getenv("JIRA_HOST", "").rstrip("/")
username = os.getenv("JIRA_USERNAME", "")
token   = os.getenv("JIRA_API_TOKEN", "")
project = os.getenv("JIRA_PROJECT", "")

# Si el .env no tiene valores reales (aún tiene el placeholder), tratar como vacío
if host == "https://TU-EMPRESA.atlassian.net":
    host = ""

if not all([host, username, token, project]):
    env_path = Path(".env")
    example_path = Path(".env.example")

    if not env_path.exists() and example_path.exists():
        shutil.copy(example_path, env_path)

    print(
        "\n⚠️  Completa el archivo .env con tus credenciales de Jira y vuelve a ejecutar.\n"
        "    Token: https://id.atlassian.com/manage-profile/security/api-tokens\n"
    )
    sys.exit(1)

from jira_api import JiraAPI
from tui import run_app

jira = JiraAPI(host, username, token)

me = jira.get_myself()
if not me:
    sys.exit(1)

print(f"\n✓  Conectado como: {me.get('displayName')}\n")
run_app(jira, project)
