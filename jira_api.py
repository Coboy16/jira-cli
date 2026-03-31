import base64
import requests


class JiraAPI:
    def __init__(self, host, email, token):
        credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
        self.host = host
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }

    def _url(self, path):
        return f"{self.host}/rest/api/2{path}"

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

    def get_my_issues(self, project, max_results=50):
        jql = f"assignee = currentUser() AND project = {project} ORDER BY updated DESC"
        params = {
            "jql": jql,
            "maxResults": max_results,
            "fields": "summary,status,assignee,priority",
        }
        try:
            r = requests.get(
                self._url("/search"), headers=self.headers, params=params, timeout=15
            )
            r.raise_for_status()
            issues = []
            for item in r.json().get("issues", []):
                fields = item.get("fields", {})
                assignee = fields.get("assignee") or {}
                priority = fields.get("priority") or {}
                issues.append(
                    {
                        "key": item.get("key"),
                        "summary": fields.get("summary", ""),
                        "status": fields.get("status", {}).get("name", ""),
                        "assignee": assignee.get("displayName", "Sin asignar"),
                        "priority": priority.get("name", ""),
                    }
                )
            return issues
        except Exception as e:
            print(f"❌  Error al obtener issues: {e}")
            return []

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
