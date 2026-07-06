import base64
import requests


class JiraAPI:
    def __init__(self, host, email, token, board_id=None):
        credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
        self.host     = host
        self.board_id = board_id
        self.headers  = {
            "Authorization": f"Basic {credentials}",
            "Content-Type":  "application/json",
        }
        # Adjuntos/imágenes requieren Bearer (Basic auth devuelve 403 en este servidor)
        self.download_headers = {
            "Authorization": f"Bearer {token}",
        }

    def _url(self, path):
        return f"{self.host}/rest/api/2{path}"

    def _agile_url(self, path):
        return f"{self.host}/rest/agile/1.0{path}"

    def get_myself(self):
        try:
            r = requests.get(self._url("/myself"), headers=self.headers, timeout=10)
            if r.status_code == 401:
                print("❌  Token inválido o vencido")
                return None
            if r.status_code == 403:
                print("❌  Sin permisos en este proyecto")
                return None
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ConnectionError:
            print(f"❌  No se puede conectar a {self.host}, verifica la URL")
            return None
        except Exception as e:
            print(f"❌  Error inesperado: {e}")
            return None

    def _parse_issues(self, raw_list):
        issues = []
        for item in raw_list:
            fields   = item.get("fields", {})
            assignee = fields.get("assignee") or {}
            priority = fields.get("priority") or {}
            issues.append({
                "key":      item.get("key"),
                "summary":  fields.get("summary", ""),
                "status":   fields.get("status", {}).get("name", ""),
                "assignee": assignee.get("displayName", "Sin asignar"),
                "priority": priority.get("name", ""),
                "epic_key": fields.get("customfield_10100"),
            })
        return issues

    def get_epics_info(self, epic_keys):
        """Devuelve {epic_key: epic_name} para los keys dados."""
        if not epic_keys:
            return {}
        result = {}
        jql = "key in (" + ",".join(epic_keys) + ")"
        try:
            r = requests.get(
                self._url("/search"),
                headers=self.headers,
                params={"jql": jql, "maxResults": len(epic_keys), "fields": "summary"},
                timeout=15,
            )
            r.raise_for_status()
            for item in r.json().get("issues", []):
                result[item["key"]] = item["fields"]["summary"]
        except Exception:
            pass
        return result

    def get_sprint_issues(self, project, max_results=500):
        """
        Obtiene issues del sprint activo usando la API Agile (RapidBoard).
        Si hay board_id configurado lo usa directamente; si no, intenta
        buscarlo por proyecto. Fallback final: JQL básico.
        """
        # ── 1. Via API Agile con board_id ─────────────────────────────────────
        board_id = self.board_id
        if not board_id:
            board_id = self._find_board_for_project(project)

        if board_id:
            issues = self._issues_from_board(board_id, max_results, project=project)
            if issues:
                return issues

        # ── 2. Fallback JQL ────────────────────────────────────────────────────
        for jql in [
            f"project = {project} AND sprint in openSprints() ORDER BY updated DESC",
            f"project = {project} ORDER BY updated DESC",
        ]:
            try:
                r = requests.get(
                    self._url("/search"),
                    headers=self.headers,
                    params={"jql": jql, "maxResults": max_results,
                            "fields": "summary,status,assignee,priority"},
                    timeout=15,
                )
                if r.status_code != 200:
                    continue
                data = r.json()
                if data.get("errorMessages"):
                    continue
                items = data.get("issues", [])
                if items:
                    return self._parse_issues(items)
            except Exception:
                continue
        return []

    def _find_board_for_project(self, project):
        """Busca el primer board de tipo Scrum/Kanban para el proyecto."""
        try:
            r = requests.get(
                self._agile_url("/board"),
                headers=self.headers,
                params={"projectKeyOrId": project, "maxResults": 10},
                timeout=10,
            )
            if r.status_code != 200:
                return None
            boards = r.json().get("values", [])
            if boards:
                return boards[0]["id"]
        except Exception:
            pass
        return None

    def _get_active_sprints(self, board_id):
        """Devuelve todos los sprints activos del board con paginación."""
        sprints, start = [], 0
        while True:
            r = requests.get(
                self._agile_url(f"/board/{board_id}/sprint"),
                headers=self.headers,
                params={"state": "active", "maxResults": 50, "startAt": start},
                timeout=10,
            )
            if r.status_code != 200:
                break
            data = r.json()
            vals = data.get("values", [])
            sprints.extend(vals)
            if data.get("isLast", True) or not vals:
                break
            start += len(vals)
        return sprints

    def _issues_from_sprint(self, sprint_id, project, max_results):
        """Descarga todos los issues de un sprint, opcionalmente filtrando por proyecto."""
        all_issues, start = [], 0
        jql_filter = f"project = {project}" if project else ""
        while True:
            params = {
                "startAt":    start,
                "maxResults": min(max_results - len(all_issues), 100),
                "fields":     "summary,status,assignee,priority,customfield_10100",
            }
            if jql_filter:
                params["jql"] = jql_filter
            r = requests.get(
                self._agile_url(f"/sprint/{sprint_id}/issue"),
                headers=self.headers,
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

    def _issues_from_board(self, board_id, max_results, project=None):
        """
        Obtiene issues del sprint activo del board via API Agile.
        Si hay varios sprints activos, selecciona el que tenga más issues
        del proyecto target.
        """
        try:
            sprints = self._get_active_sprints(board_id)
            if not sprints:
                return []

            if len(sprints) == 1:
                items = self._issues_from_sprint(sprints[0]["id"], project, max_results)
                return self._parse_issues(items)

            # Varios sprints activos → elegir el que tenga más issues del proyecto
            best_sprint, best_count = None, -1
            for s in sprints:
                # Sondeo rápido: pedir solo 1 issue con filtro de proyecto
                params = {"maxResults": 1, "startAt": 0, "fields": "summary"}
                if project:
                    params["jql"] = f"project = {project}"
                r = requests.get(
                    self._agile_url(f"/sprint/{s['id']}/issue"),
                    headers=self.headers,
                    params=params,
                    timeout=10,
                )
                if r.status_code != 200:
                    continue
                count = r.json().get("total", 0)
                if count > best_count:
                    best_count = count
                    best_sprint = s["id"]

            if not best_sprint:
                best_sprint = sprints[0]["id"]

            items = self._issues_from_sprint(best_sprint, project, max_results)
            return self._parse_issues(items)
        except Exception:
            return []

    def get_my_issues(self, project, max_results=500):
        return self.get_sprint_issues(project, max_results)

    def get_issue(self, issue_key):
        try:
            r = requests.get(
                self._url(f"/issue/{issue_key}"),
                headers=self.headers,
                params={"fields": "summary,status,assignee,priority,description,attachment"},
                timeout=10,
            )
            r.raise_for_status()
            item = r.json()
            fields = item.get("fields", {})
            assignee = fields.get("assignee") or {}
            priority = fields.get("priority") or {}
            attachments = []
            for att in fields.get("attachment", []):
                att_id = att.get("id", "")
                name   = att.get("filename", "")
                mime   = att.get("mimeType", "")
                from pathlib import Path as _Path
                ext  = _Path(name).suffix.lower()
                icon = "🖼 " if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"} else "📄"
                attachments.append({
                    "id":   att_id,
                    "name": name,
                    "mime": mime,
                    "icon": icon,
                    # URL correcta para Jira Server
                    "url":  f"{self.host}/secure/attachment/{att_id}/{name}",
                })
            return {
                "key":         item.get("key"),
                "summary":     fields.get("summary", ""),
                "status":      fields.get("status", {}).get("name", ""),
                "assignee":    assignee.get("displayName", "Sin asignar"),
                "priority":    priority.get("name", ""),
                "description": fields.get("description") or "",
                "attachments": attachments,
            }
        except Exception as e:
            print(f"❌  Error al obtener issue {issue_key}: {e}")
            return None

    def get_transitions(self, issue_key):
        try:
            r = requests.get(
                self._url(f"/issue/{issue_key}/transitions"),
                headers=self.headers,
                timeout=10,
            )
            r.raise_for_status()
            return [
                {"id": t["id"], "name": t["name"]}
                for t in r.json().get("transitions", [])
            ]
        except Exception as e:
            print(f"❌  Error al obtener transiciones: {e}")
            return []

    def transition_issue(self, issue_key, transition_id):
        try:
            r = requests.post(
                self._url(f"/issue/{issue_key}/transitions"),
                headers=self.headers,
                json={"transition": {"id": transition_id}},
                timeout=10,
            )
            return r.status_code == 204
        except Exception as e:
            print(f"❌  Error al transicionar issue: {e}")
            return False

    def upload_attachment(self, issue_key, file_path):
        # NO incluir Content-Type aquí; requests lo setea solo con multipart
        upload_headers = {
            k: v for k, v in self.headers.items() if k != "Content-Type"
        }
        upload_headers["X-Atlassian-Token"] = "nocheck"
        try:
            with open(file_path, "rb") as f:
                import os
                filename = os.path.basename(file_path)
                r = requests.post(
                    self._url(f"/issue/{issue_key}/attachments"),
                    headers=upload_headers,
                    files={"file": (filename, f)},
                    timeout=30,
                )
            r.raise_for_status()
            attachments = r.json()
            if attachments:
                return attachments[0].get("filename")
            return None
        except Exception as e:
            print(f"❌  Error al subir adjunto: {e}")
            return None

    def add_comment(self, issue_key, body):
        try:
            r = requests.post(
                self._url(f"/issue/{issue_key}/comment"),
                headers=self.headers,
                json={"body": body},
                timeout=10,
            )
            return r.status_code == 201
        except Exception as e:
            print(f"❌  Error al agregar comentario: {e}")
            return False
