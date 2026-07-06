import os
import re
import sys
import tty
import termios
import shutil
import unicodedata
import webbrowser
import requests
import tempfile
from pathlib import Path
from datetime import datetime

# ── Colores ANSI ─────────────────────────────────────────────────────────────
RESET    = "\033[0m"
BOLD     = "\033[1m"
DIM      = "\033[2m"

C_YELLOW = "\033[38;5;214m"
C_BLUE   = "\033[38;5;75m"
C_GREEN  = "\033[38;5;84m"
C_CYAN   = "\033[38;5;87m"
C_WHITE  = "\033[97m"
C_RED    = "\033[38;5;196m"

# ── Mapeo de estados (5 columnas como en Jira web) ───────────────────────────
COLUMN_ORDER  = ["Por Hacer", "En Progreso", "En Revisión", "Listo para Entregar", "Hecho"]
COLUMN_COLORS = [C_YELLOW,    C_BLUE,        C_CYAN,        C_GREEN,               C_WHITE]
COLUMN_ICONS  = ["○",         "◐",           "◑",           "◕",                   "●"]

STATUS_MAP = {name: (color, icon)
              for name, color, icon in zip(COLUMN_ORDER, COLUMN_COLORS, COLUMN_ICONS)}

IMAGE_EXTS       = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
VALID_EXTENSIONS = IMAGE_EXTS


# ── Helpers generales ─────────────────────────────────────────────────────────
def status_display(status):
    if status in STATUS_MAP:
        return STATUS_MAP[status]
    idx = get_column_index(status)
    return COLUMN_COLORS[idx], COLUMN_ICONS[idx]


def clear():
    os.system("clear")


def term_size():
    return shutil.get_terminal_size((80, 24))


def term_width():
    return term_size().columns


def trunc(s, n):
    if n <= 0:
        return ""
    return s if len(s) <= n else s[:n - 1] + "…"


def strip_ansi(s):
    return re.sub(r"\033\[[0-9;]*m", "", s)


def visible_len(s):
    return len(strip_ansi(s))


def pad_to(s, width):
    return s + " " * max(0, width - visible_len(s))


def wrap_text(text, width):
    """Word-wrap retornando lista de líneas."""
    if not text.strip():
        return [""]
    words = text.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + (1 if current else 0) <= width:
            current = (current + " " + word) if current else word
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


# ── Fix 2 v3: Normalización de estados ───────────────────────────────────────
def _normalize(text):
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().lower()


def get_column_index(status):
    s = status.strip()
    for i, name in enumerate(COLUMN_ORDER):
        if s == name:
            return i
    sl = _normalize(s)
    for i, name in enumerate(COLUMN_ORDER):
        if sl == _normalize(name):
            return i
    # 4: Hecho / Done / Cerrado / Completado
    if any(w in sl for w in ("hecho", "done", "complet", "cerrad", "resuelto",
                              "resolved", "closed", "finaliz", "terminad")):
        return 4
    # 3: Listo para Entregar / Ready
    if any(w in sl for w in ("listo", "ready", "entregar", "entrega")):
        return 3
    # 2: En Revisión / In Review
    if any(w in sl for w in ("review", "revision", "revisio")):
        return 2
    # 1: En Progreso / En Curso / Doing
    if any(w in sl for w in ("progress", "curso", "ejecuci", "doing", "construcci",
                              "activ", "started", "proceso", "progres", "desarrollo")):
        return 1
    # 0: Por Hacer / Backlog / Pendiente (default)
    return 0


def group_by_status(issues):
    cols = [[] for _ in COLUMN_ORDER]
    for issue in issues:
        cols[get_column_index(issue.get("status", ""))].append(issue)
    return cols


# ── Captura de teclas ─────────────────────────────────────────────────────────
def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.buffer.read(1)
        if ch == b"\x1b":
            ch2 = sys.stdin.buffer.read(1)
            if ch2 == b"[":
                ch3 = sys.stdin.buffer.read(1)
                return {b"A": "UP", b"B": "DOWN", b"C": "RIGHT", b"D": "LEFT"}.get(ch3, "")
            return "ESC"
        return ch.decode("utf-8", errors="ignore")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


read_key = get_key


def read_line(prompt=""):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    buf = []
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.buffer.read(1)
            if ch in (b"\r", b"\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                break
            elif ch in (b"\x7f", b"\x08"):
                if buf:
                    buf.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            elif ch == b"\x03":
                raise KeyboardInterrupt
            else:
                decoded = ch.decode("utf-8", errors="ignore")
                if decoded.isprintable() or decoded == " ":
                    buf.append(decoded)
                    sys.stdout.write(decoded)
                    sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return "".join(buf).strip()


def read_line_with_esc(prompt=""):
    """Como read_line pero retorna None si el usuario presiona ESC."""
    sys.stdout.write(prompt)
    sys.stdout.flush()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    buf = []
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.buffer.read(1)
            if ch == b"\x1b":
                sys.stdout.write("\n")
                sys.stdout.flush()
                return None
            elif ch in (b"\r", b"\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                break
            elif ch in (b"\x7f", b"\x08"):
                if buf:
                    buf.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            elif ch == b"\x03":
                raise KeyboardInterrupt
            else:
                decoded = ch.decode("utf-8", errors="ignore")
                if decoded.isprintable() or decoded == " ":
                    buf.append(decoded)
                    sys.stdout.write(decoded)
                    sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return "".join(buf).strip()


# ── Fix 1 v3: Renderizado de descripción (tabla o texto) ─────────────────────
def render_description(desc, max_width):
    """
    Detecta si la descripción tiene formato tabla con pipes y la renderiza
    como tabla ASCII. Retorna (list[(str, None)], is_table).
    """
    raw_lines  = [l.strip() for l in desc.strip().split("\n") if l.strip()]
    pipe_lines = [l for l in raw_lines if l.startswith("|")]
    is_table   = (len(pipe_lines) >= 3 and
                  len(raw_lines) > 0 and
                  len(pipe_lines) / len(raw_lines) >= 0.6)

    if not is_table:
        result = []
        for line in raw_lines:
            for chunk in wrap_text(line, max_width):
                result.append((chunk, None))
        return result, False

    # Parsear filas
    rows = []
    for line in pipe_lines:
        clean = line.strip("|").strip()
        parts = clean.split("|", 1)
        if len(parts) == 2:
            rows.append((parts[0].strip(), parts[1].strip()))
        elif len(parts) == 1 and parts[0].strip():
            rows.append(("", parts[0].strip()))

    if not rows:
        result = []
        for line in raw_lines:
            for chunk in wrap_text(line, max_width):
                result.append((chunk, None))
        return result, False

    col1_w = min(max((len(r[0]) for r in rows), default=10), 22)
    # Overhead de caracteres de borde: │ col1 │ col2 │ = col1+col2+7
    col2_w = max_width - col1_w - 7
    if col2_w < 8:
        result = []
        for line in raw_lines:
            for chunk in wrap_text(line, max_width):
                result.append((chunk, None))
        return result, False

    top = f"┌{'─' * (col1_w + 2)}┬{'─' * (col2_w + 2)}┐"
    sep = f"├{'─' * (col1_w + 2)}┼{'─' * (col2_w + 2)}┤"
    bot = f"└{'─' * (col1_w + 2)}┴{'─' * (col2_w + 2)}┘"
    result = [(top, None)]

    for i, (c1, c2) in enumerate(rows):
        c2_lines = wrap_text(c2, col2_w) if c2.strip() else [""]
        for j, c2l in enumerate(c2_lines):
            lc1 = c1.ljust(col1_w) if j == 0 else " " * col1_w
            lc2 = c2l.ljust(col2_w)
            result.append((f"│ {lc1} │ {lc2} │", None))
        if i < len(rows) - 1:
            result.append((sep, None))

    result.append((bot, None))
    return result, True


# ── Análisis Scrum Master ─────────────────────────────────────────────────────
def analyze_issue(issue):
    status   = issue.get("status", "")
    priority = issue.get("priority", "")
    desc     = issue.get("description", "") or ""
    lines    = []
    if "hecha" in status.lower() or "hecho" in status.lower():
        lines.append("Lista para revisión. Valida con QA antes de cerrar el sprint.")
    elif "construcci" in status.lower():
        lines.append("En desarrollo. Monitorea tiempo restante vs estimado.")
    else:
        lines.append("Tarea en cola. Verifica que los criterios de aceptación estén definidos.")
    if priority in ("High", "Highest"):
        lines.append(f"{C_RED}⚠  Prioridad {priority} — requiere atención inmediata.{RESET}")
    if not desc.strip():
        lines.append(f"{C_YELLOW}⚠  Descripción vacía — agrega criterios de aceptación.{RESET}")
    return lines


# ── Renombrar imagen ──────────────────────────────────────────────────────────
def rename_image(original_path, issue_key, index=1):
    p = Path(original_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_name = f"evidencia_{index}_{issue_key}_{timestamp}{p.suffix.lower()}"
    new_path = p.parent / new_name
    shutil.copy2(p, new_path)
    return str(new_path), new_name


# ── Fetch attachments con URL correcta para Jira Server ──────────────────────
def fetch_attachments(jira, issue_key):
    try:
        r = requests.get(
            f"{jira.host}/rest/api/2/issue/{issue_key}",
            headers=jira.headers,
            params={"fields": "attachment"},
            timeout=10,
        )
        r.raise_for_status()
        result = []
        for att in r.json().get("fields", {}).get("attachment", []):
            name   = att.get("filename", "")
            att_id = att.get("id", "")
            mime   = att.get("mimeType", "")
            ext    = Path(name).suffix.lower()
            icon   = "🖼 " if ext in IMAGE_EXTS else "📄"
            # Fix 2: URL correcta para Jira Server
            result.append({
                "id":   att_id,
                "name": name,
                "mime": mime,
                "icon": icon,
                "url":  f"{jira.host}/secure/attachment/{att_id}/{name}",
            })
        return result
    except Exception:
        return []


# ── Fix 2 v3: render_image_preview con URL y auth correctos ──────────────────
def render_image_preview(url, headers, width=55):
    """
    Descarga la imagen y la convierte a ASCII art.
    Retorna lista de strings (líneas). Usa las mismas credenciales de la API.
    """
    tmp_path = None
    try:
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        if r.status_code != 200:
            return [f"  {C_RED}[Error {r.status_code} al cargar imagen]{RESET}"]

        ct     = r.headers.get("Content-Type", "image/png")
        ct_map = {"image/png": ".png", "image/jpeg": ".jpg",
                  "image/gif": ".gif", "image/webp": ".webp"}
        suffix = ct_map.get(ct.split(";")[0].strip(), ".png")

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(r.content)
            tmp_path = f.name

        # Intentar ascii_magic 2.x
        try:
            from ascii_magic import AsciiArt
            art = AsciiArt.from_image(tmp_path)
            return art.to_ascii(columns=width).splitlines()
        except (ImportError, AttributeError, TypeError):
            pass

        # Intentar ascii_magic 1.x
        try:
            import ascii_magic
            return ascii_magic.from_image_file(tmp_path, columns=width).splitlines()
        except Exception:
            pass

        # Fallback: mostrar dimensiones con Pillow
        try:
            from PIL import Image
            img = Image.open(tmp_path)
            w_px, h_px = img.size
            return [f"  {DIM}[Imagen: {w_px}×{h_px}px — instala ascii-magic para preview]{RESET}"]
        except Exception:
            pass

        return [f"  {DIM}[Preview no disponible — instala: pip install ascii-magic Pillow]{RESET}"]

    except Exception as e:
        return [f"  {DIM}[No se pudo cargar: {str(e)[:50]}]{RESET}"]
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# ── Abrir imagen en navegador ────────────────────────────────────────────────
def expand_image(att, headers=None):
    """Abre la imagen en el navegador por defecto del sistema."""
    url = att.get("url", "")
    if not url:
        return
    clear()
    w = term_width()
    print(f"\n  {BOLD}Abriendo en navegador:{RESET}  {C_CYAN}{att['name']}{RESET}")
    print(f"  {DIM}{url}{RESET}\n")
    webbrowser.open(url)
    print(f"  {C_GREEN}✓ Imagen abierta en el navegador.{RESET}")
    print(f"  {DIM}{'─' * (w - 4)}{RESET}")
    print(f"  {DIM}Presiona cualquier tecla para volver{RESET}")
    get_key()


# ── Construir líneas del detalle como lista scrolleable ───────────────────────
def build_detail_lines(issue, attachments, jira):
    """
    Retorna list[(str, dict|None)].
    - str  = línea formateada (con ANSI) lista para print()
    - dict = metadata: {"type": "image", "att": {...}} para líneas de imagen,
             None para todas las demás.
    """
    w     = term_width()
    box_w = w - 4
    inner = box_w - 2
    lines = []

    def add_hline(left="├", right="┤"):
        lines.append((f"  {left}{'─' * box_w}{right}", None))

    def add_box_row(plain, ansi=None, bold=False):
        a   = ansi or (f"{BOLD}{plain}{RESET}" if bold else plain)
        pad = inner - len(plain)
        lines.append((f"  │ {a}{' ' * max(0, pad)} │", None))

    def add_blank():
        lines.append((f"  │ {' ' * inner} │", None))

    # ── Top border ──
    lines.append((f"  ┌{'─' * box_w}┐", None))

    # Key + status alineado a la derecha
    color, icon = status_display(issue["status"])
    status_vis  = f"{icon} {issue['status']}"
    key_vis     = issue["key"]
    gap         = inner - len(key_vis) - len(status_vis)
    lines.append((
        f"  │ {BOLD}{C_CYAN}{key_vis}{RESET}"
        f"{' ' * max(0, gap)}{color}{status_vis}{RESET} │",
        None,
    ))

    # Summary (hasta 2 líneas)
    for line in wrap_text(issue["summary"], inner - 1)[:2]:
        add_box_row(line, bold=True)

    add_hline()

    # Asignado + prioridad
    meta_str = f"👤 {issue.get('assignee', 'Sin asignar')}    ⚑ {issue.get('priority', '—')}"
    add_box_row(meta_str)

    add_hline()

    # Descripción — con render de tabla si aplica
    add_box_row("DESCRIPCIÓN", bold=True)
    lines.append((f"  │ {DIM}{'─' * inner}{RESET} │", None))
    desc = (issue.get("description") or "").strip()
    if desc:
        desc_parts, is_table = render_description(desc, inner - 1)
        for text, _ in desc_parts:
            pad = inner - 1 - len(text)
            if is_table:
                # Tabla: sin DIM para que los bordes sean visibles
                lines.append((f"  │ {text}{' ' * max(0, pad)} │", None))
            else:
                lines.append((f"  │ {DIM}{text}{RESET}{' ' * max(0, pad)} │", None))
    else:
        add_box_row("(Sin descripción)", ansi=f"{DIM}(Sin descripción){RESET}")

    # Adjuntos
    if attachments:
        add_hline()
        add_box_row("ADJUNTOS", bold=True)
        lines.append((f"  │ {DIM}{'─' * inner}{RESET} │", None))

        for att in attachments:
            is_img   = (att.get("mime", "").startswith("image/") or
                        Path(att["name"]).suffix.lower() in IMAGE_EXTS)
            icon_chr = att.get("icon", "📄")
            name_d   = trunc(att["name"], inner - 10)

            if is_img:
                # Línea marcada con metadata para Enter → abrir en navegador
                img_meta = {"type": "image", "att": att}
                plain    = f"{icon_chr} {name_d}  → Enter: abrir en navegador"
                ansi_str = (f"{icon_chr} {C_BLUE}{name_d}{RESET}"
                            f"  {DIM}→ Enter: abrir en navegador{RESET}")
                pad = inner - len(plain)
                lines.append((f"  │ {ansi_str}{' ' * max(0, pad)} │", img_meta))
            else:
                add_box_row(f"{icon_chr} {name_d}")

            # Hint para abrir en navegador
            if is_img:
                hint_plain = "[Enter para abrir en navegador]"
                hint_ansi  = f"{DIM}{hint_plain}{RESET}"
                pad = inner - len(hint_plain)
                lines.append((f"  │ {hint_ansi}{' ' * max(0, pad)} │", None))

    # Análisis Scrum Master
    add_hline()
    add_box_row("ANÁLISIS SCRUM MASTER", bold=True)
    lines.append((f"  │ {DIM}{'─' * inner}{RESET} │", None))
    for line in analyze_issue(issue):
        vis = strip_ansi(line)
        pad = inner - len(vis)
        lines.append((f"  │ {line}{' ' * max(0, pad)} │", None))

    # Bottom border
    lines.append((f"  └{'─' * box_w}┘", None))

    return lines


# ── Pantalla 0: Menú de carriles (epics) ─────────────────────────────────────

def _build_epic_groups(all_issues, epics_map):
    """Agrupa issues por epic. Retorna lista ordenada de (epic_key, name, [issues])."""
    groups = {}
    for issue in all_issues:
        ek = issue.get("epic_key") or "__none__"
        groups.setdefault(ek, []).append(issue)

    result = []
    for ek, issues in sorted(groups.items(), key=lambda x: -len(x[1])):
        name = epics_map.get(ek, "(Sin carril)" if ek == "__none__" else ek)
        result.append((ek, name, issues))
    return result


def screen_epic_menu(jira, project, all_issues, epics_map):
    cursor  = 0
    num_buf = ""

    while True:
        epic_groups  = _build_epic_groups(all_issues, epics_map)
        total_epics  = len(epic_groups)
        total_issues = len(all_issues)
        cursor = min(cursor, max(0, total_epics - 1))

        ts = term_size()
        w  = ts.columns
        header_h  = 5
        footer_h  = 2
        visible_h = max(1, ts.lines - header_h - footer_h)

        clear()

        title = f"JIRA TUI  ·  {project}  ·  Sprint Activo"
        bar_w = w - 2
        pad_l = (bar_w - len(title)) // 2
        pad_r = bar_w - len(title) - pad_l
        print(f"{BOLD}{C_CYAN}╔{'═' * bar_w}╗")
        print(f"║{' ' * pad_l}{title}{' ' * pad_r}║")
        print(f"╚{'═' * bar_w}╝{RESET}")

        print(
            f"  {DIM}[↑↓] Navegar  [Enter] Abrir carril  "
            f"[número+Enter] Ir directo  [r] Recargar  [q] Salir{RESET}"
        )
        if num_buf:
            print(
                f"  {C_CYAN}→ Carril #{BOLD}{num_buf}{RESET}"
                f"{C_CYAN}_  {DIM}(Enter confirmar · ESC cancelar){RESET}"
            )
        else:
            print(
                f"  {DIM}{total_issues} incidencias en {total_epics} carriles  "
                f"│  Escribe un número para ir directo{RESET}"
            )

        print()
        print(f"  {DIM}{'─' * (w - 4)}{RESET}")

        # Render epic rows with scroll
        all_rows = []
        for i, (ek, name, issues) in enumerate(epic_groups):
            all_rows.append((i, ek, name, len(issues)))

        # Scroll so cursor stays visible
        if not hasattr(screen_epic_menu, "_scroll"):
            screen_epic_menu._scroll = 0
        sc = screen_epic_menu._scroll

        if cursor < sc:
            sc = cursor
        elif cursor >= sc + visible_h:
            sc = cursor - visible_h + 1
        sc = max(0, min(sc, max(0, len(all_rows) - visible_h)))
        screen_epic_menu._scroll = sc

        for i, ek, name, count in all_rows[sc:sc + visible_h]:
            selected = (i == cursor)
            num_s   = f"[{i + 1:2d}]"
            count_s = f"{count} incidencia{'s' if count != 1 else ''}"
            name_w  = max(10, w - 4 - 6 - 2 - len(count_s) - 4)
            name_t  = trunc(name, name_w)
            gap     = max(0, name_w - len(name_t))

            if selected:
                print(
                    f"  {C_CYAN}{BOLD}{num_s}  {name_t}{' ' * gap}  "
                    f"{count_s}{RESET}  {C_CYAN}{BOLD}◀{RESET}"
                )
            else:
                print(
                    f"  {DIM}{num_s}{RESET}  {name_t}{' ' * gap}  "
                    f"{DIM}{count_s}{RESET}"
                )

        print(f"  {DIM}{'─' * (w - 4)}{RESET}")
        print()

        key = get_key()

        if key in "0123456789":
            num_buf += key
        elif key in ("\x7f", "\x08"):
            num_buf = num_buf[:-1]
        elif key == "ESC":
            num_buf = ""
        elif key == "\r":
            target_idx = cursor
            if num_buf:
                try:
                    target_idx = int(num_buf) - 1
                except ValueError:
                    pass
                num_buf = ""
            if 0 <= target_idx < total_epics:
                cursor = target_idx
                ek, name, issues = epic_groups[cursor]
                result = screen_issue_list(jira, project, issues, epic_name=name)
                if result == "reload":
                    return "reload"
        elif key == "UP":
            cursor  = max(0, cursor - 1)
            num_buf = ""
        elif key == "DOWN":
            cursor  = min(total_epics - 1, cursor + 1)
            num_buf = ""
        elif key.lower() == "r":
            return "reload"
        elif key.lower() == "q":
            clear()
            print(f"\n  {C_GREEN}¡Hasta luego!{RESET}\n")
            sys.exit(0)


# ── Pantalla 1: Lista de incidencias ─────────────────────────────────────────

def build_list_rows(columns):
    rows = []
    num = 1
    for ci, col_issues in enumerate(columns):
        rows.append({"type": "header", "ci": ci, "count": len(col_issues)})
        for issue in col_issues:
            rows.append({"type": "issue", "issue": issue, "num": num})
            num += 1
        if not col_issues:
            rows.append({"type": "empty"})
        rows.append({"type": "spacer"})
    return rows


def render_issue_row(issue, num, selected, w):
    key      = issue["key"]
    summary  = issue["summary"]
    assignee = trunc(issue.get("assignee", "—"), 14)
    priority = trunc(issue.get("priority", "—"), 8)
    st_color, st_icon = status_display(issue.get("status", ""))

    num_s    = f"[{num:2d}]"
    assign_s = f"@{assignee}"
    prio_s   = f"!{priority}"

    # prefix fixed width: 2 + 4 + 2 + 10 + 2 = 20
    prefix_len = 20
    tail_plain = f"  {assign_s:<16}  {prio_s:<10}  {st_icon}"
    sum_w = max(10, w - prefix_len - len(tail_plain) - (3 if selected else 0) - 2)
    sum_s = trunc(summary, sum_w)

    if selected:
        return (
            f"  {C_CYAN}{BOLD}{num_s}{RESET}  "
            f"{C_CYAN}{BOLD}{key:<10}{RESET}  "
            f"{BOLD}{C_WHITE}{sum_s:<{sum_w}}{RESET}"
            f"  {DIM}{assign_s:<16}  {prio_s:<10}{RESET}  "
            f"{st_color}{st_icon}{RESET}"
            f"  {C_CYAN}{BOLD}◀{RESET}"
        )
    return (
        f"  {DIM}{num_s}{RESET}  "
        f"{key:<10}  "
        f"{trunc(summary, sum_w):<{sum_w}}"
        f"  {DIM}{assign_s:<16}  {prio_s:<10}{RESET}  "
        f"{st_color}{st_icon}{RESET}"
    )


def screen_issue_list(jira, project, issues, epic_name=""):
    cursor  = 0
    scroll  = 0
    num_buf = ""

    columns     = group_by_status(issues)
    rows        = build_list_rows(columns)
    issues_flat = [r["issue"] for r in rows if r["type"] == "issue"]
    total_issues = len(issues_flat)

    while True:
        cursor = min(cursor, max(0, total_issues - 1))

        ts = term_size()
        w  = ts.columns
        header_h  = 6
        footer_h  = 2
        visible_h = max(1, ts.lines - header_h - footer_h)

        # Build flat rendered lines
        flat_lines = []   # (text, is_issue, issue_idx)
        issue_idx  = 0
        for row in rows:
            t = row["type"]
            if t == "header":
                ci    = row["ci"]
                color = COLUMN_COLORS[ci]
                icon  = COLUMN_ICONS[ci]
                name  = COLUMN_ORDER[ci]
                count = row["count"]
                flat_lines.append(("", False, -1))
                flat_lines.append((
                    f"  {BOLD}{color}{icon}  {name}  ({count}){RESET}",
                    False, -1,
                ))
                flat_lines.append((
                    f"  {DIM}{'─' * (w - 4)}{RESET}",
                    False, -1,
                ))
            elif t == "empty":
                flat_lines.append((f"  {DIM}    (sin tareas){RESET}", False, -1))
            elif t == "spacer":
                flat_lines.append(("", False, -1))
            elif t == "issue":
                selected = (issue_idx == cursor)
                line = render_issue_row(row["issue"], row["num"], selected, w)
                flat_lines.append((line, True, issue_idx))
                issue_idx += 1

        total_lines = len(flat_lines)

        # Keep cursor's line visible
        sel_line = next(
            (i for i, (_, is_issue, idx) in enumerate(flat_lines)
             if is_issue and idx == cursor),
            0,
        )
        if sel_line < scroll:
            scroll = sel_line
        elif sel_line >= scroll + visible_h:
            scroll = sel_line - visible_h + 1
        scroll = max(0, min(scroll, max(0, total_lines - visible_h)))

        clear()

        # Header
        carril_label = trunc(epic_name, w - 20) if epic_name else project
        title = f"JIRA TUI  ·  {carril_label}"
        bar_w = w - 2
        pad_l = (bar_w - len(title)) // 2
        pad_r = bar_w - len(title) - pad_l
        print(f"{BOLD}{C_CYAN}╔{'═' * bar_w}╗")
        print(f"║{' ' * pad_l}{title}{' ' * pad_r}║")
        print(f"╚{'═' * bar_w}╝{RESET}")

        pct = (f"  {int(scroll / max(1, total_lines - visible_h) * 100)}%"
               if total_lines > visible_h else "")
        print(
            f"  {DIM}[↑↓] Navegar  [Enter] Abrir  "
            f"[número+Enter] Ir directo  [b/ESC] Volver  [q] Salir{RESET}"
            f"{DIM}{pct}{RESET}"
        )
        print(
            f"  {C_CYAN}{trunc(epic_name, w - 6)}{RESET}"
            if epic_name else ""
        )

        if num_buf:
            print(
                f"  {C_CYAN}→ Tarea #{BOLD}{num_buf}{RESET}"
                f"{C_CYAN}_  {DIM}(Enter confirmar · ESC cancelar){RESET}"
            )
        else:
            print(
                f"  {DIM}{total_issues} incidencias  │  "
                f"Escribe un número para ir directo{RESET}"
            )

        # Content
        for text, _, _ in flat_lines[scroll:scroll + visible_h]:
            print(text)

        # Footer
        print()
        print(
            f"  {DIM}Abre una tarea y usa: "
            f"[1] Subir evidencia  [2] Comentar  [3] Estado  "
            f"[4] {C_CYAN}✦ Flujo completo{RESET}"
        )

        key = get_key()

        if key in "0123456789":
            num_buf += key
        elif key in ("\x7f", "\x08"):
            num_buf = num_buf[:-1]
        elif key == "ESC":
            num_buf = ""
        elif key == "\r":
            if num_buf:
                try:
                    target = int(num_buf) - 1
                    if 0 <= target < total_issues:
                        cursor = target
                        result = screen_issue_detail(jira, issues_flat[cursor])
                        if result == "reload":
                            return "reload"
                except ValueError:
                    pass
                num_buf = ""
            elif issues_flat and 0 <= cursor < total_issues:
                result = screen_issue_detail(jira, issues_flat[cursor])
                if result == "reload":
                    return "reload"
        elif key == "UP":
            cursor  = max(0, cursor - 1)
            num_buf = ""
        elif key == "DOWN":
            cursor  = min(total_issues - 1, cursor + 1)
            num_buf = ""
        elif key.lower() == "r":
            return "reload"
        elif key.lower() == "b" or key == "ESC":
            return None
        elif key.lower() == "q":
            clear()
            print(f"\n  {C_GREEN}¡Hasta luego!{RESET}\n")
            sys.exit(0)


# ── Pantalla 2: Detalle con scroll y cursor ───────────────────────────────────
def screen_issue_detail(jira, issue_summary):
    clear()
    print(f"\n  {DIM}Cargando detalle...{RESET}")

    issue = jira.get_issue(issue_summary["key"])
    if not issue:
        print(f"\n  {C_RED}No se pudo cargar la tarea.{RESET}")
        get_key()
        return None

    # Adjuntos con URL correcta
    attachments = issue.pop("attachments", None)
    if attachments is None:
        attachments = fetch_attachments(jira, issue["key"])

    detail_lines   = build_detail_lines(issue, attachments, jira)
    scroll         = 0
    cursor_in_view = 0
    rebuild        = False

    while True:
        if rebuild:
            detail_lines   = build_detail_lines(issue, attachments, jira)
            scroll         = 0
            cursor_in_view = 0
            rebuild        = False

        ts        = term_size()
        content_h = max(1, ts.lines - 6)
        total     = len(detail_lines)

        # Clamp cursor
        max_cursor     = max(0, min(content_h - 1, total - scroll - 1))
        cursor_in_view = min(cursor_in_view, max_cursor)

        clear()

        # ── Header fijo ──
        print(f"\n  {DIM}[b] Volver{RESET}  "
              f"{BOLD}{C_CYAN}{issue['key']}{RESET}  "
              f"{DIM}[1] Subir  [2] Comentar  [3] Estado  "
              f"[4] {C_CYAN}✦ Flujo completo{RESET}")

        if total > content_h:
            abs_cursor = scroll + cursor_in_view
            pct        = int(scroll / max(1, total - content_h) * 100)
            print(f"  {DIM}[↑↓] Navegar  línea {abs_cursor + 1}/{total}  ({pct}%){RESET}")
        else:
            print()

        # ── Contenido scrolleable con cursor ──
        visible_count = min(content_h, total - scroll)
        for i in range(visible_count):
            abs_i      = scroll + i
            line_text, _ = detail_lines[abs_i]
            if i == cursor_in_view:
                # Reemplazar el primer carácter (espacio) por el indicador
                print(f"{C_CYAN}▶{RESET}{line_text[1:]}")
            else:
                print(line_text)

        # ── Footer fijo ──
        print()
        print(f"  {DIM}[1] Subir evidencia   [2] Comentar   [3] Cambiar estado   "
              f"[4] {C_CYAN}✦ Flujo completo{RESET}{DIM}   [b] Volver{RESET}")

        key = get_key()

        if key == "UP":
            if cursor_in_view > 0:
                cursor_in_view -= 1
            elif scroll > 0:
                scroll -= 1
        elif key == "DOWN":
            abs_next = scroll + cursor_in_view + 1
            if abs_next < total:
                if cursor_in_view < content_h - 1:
                    cursor_in_view += 1
                else:
                    scroll += 1
        elif key == "\r":
            # Fix 3: Enter sobre línea de imagen → expandir
            abs_i = scroll + cursor_in_view
            if abs_i < total:
                _, meta = detail_lines[abs_i]
                if meta and meta.get("type") == "image":
                    expand_image(meta["att"], jira.download_headers)
        elif key == "1":
            action_upload_only(jira, issue)
        elif key == "2":
            action_comment_only(jira, issue)
        elif key == "3":
            # Fix 4: recargar issue y reconstruir líneas si el estado cambió
            changed = action_change_status(jira, issue)
            if changed:
                rebuild = True
        elif key == "4":
            result = action_full_flow(jira, issue)
            if result == "done":
                return "reload"
        elif key.lower() == "b" or key == "ESC":
            return None


# ── Drop zone ─────────────────────────────────────────────────────────────────
def screen_drop_zone():
    print(f"""
  ┌─────────────────────────────────────────┐
  │                                         │
  │      Arrastra tu imagen aquí            │
  │         ↓  DROP IMAGE  ↓               │
  │    o escribe la ruta manualmente        │
  │                                         │
  └─────────────────────────────────────────┘

  Formatos: PNG, JPG, JPEG, GIF, WEBP
  {DIM}ESC o Enter vacío para volver · 's' para saltar{RESET}
""")
    while True:
        path = read_line_with_esc(f"  {C_CYAN}➜  Ruta de imagen: {RESET}")
        if path is None:
            return None
        path = path.strip().strip("'\"")
        if path == "" or path.lower() == "b":
            return None
        if path.lower() == "s":
            return "skip"
        p = Path(path)
        if not p.exists():
            print(f"  {C_RED}Archivo no encontrado: {path}{RESET}")
            continue
        if p.suffix.lower() not in VALID_EXTENSIONS:
            print(f"  {C_RED}Formato no válido. Usa PNG, JPG, JPEG, GIF o WEBP.{RESET}")
            continue
        return str(p)


# ── Acciones ──────────────────────────────────────────────────────────────────
def action_upload_only(jira, issue):
    print()
    path = screen_drop_zone()
    if not path or path == "skip":
        return
    new_path, new_name = rename_image(path, issue["key"])
    print(f"\n  {DIM}Subiendo {new_name}...{RESET}")
    uploaded = jira.upload_attachment(issue["key"], new_path)
    if uploaded:
        print(f"  {C_GREEN}✓ Adjunto subido: {uploaded}{RESET}")
    else:
        print(f"  {C_RED}✗ Error al subir el adjunto.{RESET}")
    print()
    read_line("  Presiona Enter para continuar...")


def action_comment_only(jira, issue):
    print(f"\n  {DIM}Escribe el comentario (Enter para terminar):{RESET}")
    body = read_line("  › ")
    if not body:
        print(f"  {C_YELLOW}Comentario vacío, cancelado.{RESET}")
        return
    ok = jira.add_comment(issue["key"], body)
    if ok:
        print(f"  {C_GREEN}✓ Comentario publicado.{RESET}")
    else:
        print(f"  {C_RED}✗ Error al publicar comentario.{RESET}")
    print()
    read_line("  Presiona Enter para continuar...")


def action_change_status(jira, issue):
    """
    Muestra transiciones, ejecuta la elegida y recarga el issue.
    Retorna True si el estado cambió (para que el detalle se reconstruya).
    """
    print(f"\n  {DIM}Obteniendo transiciones disponibles...{RESET}")
    transitions = jira.get_transitions(issue["key"])
    if not transitions:
        print(f"  {C_RED}No se encontraron transiciones.{RESET}")
        read_line("  Presiona Enter para continuar...")
        return False

    print(f"\n  {BOLD}Transiciones disponibles:{RESET}")
    for i, t in enumerate(transitions):
        print(f"  [{i + 1}]  {t['name']}")
    print()
    choice = read_line("  Elige número: ")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(transitions):
            t  = transitions[idx]
            ok = jira.transition_issue(issue["key"], t["id"])
            if ok:
                # Fix 4: recargar desde API para obtener nombre exacto del estado
                updated = jira.get_issue(issue["key"])
                if updated:
                    issue["status"] = updated["status"]
                print(f"  {C_GREEN}✓ Estado cambiado a: {issue['status']}{RESET}")
                read_line("  Presiona Enter para continuar...")
                return True
            else:
                print(f"  {C_RED}✗ Error al cambiar estado.{RESET}")
        else:
            print(f"  {C_YELLOW}Opción fuera de rango.{RESET}")
    except ValueError:
        print(f"  {C_YELLOW}Opción no válida.{RESET}")
    print()
    read_line("  Presiona Enter para continuar...")
    return False


def action_full_flow(jira, issue):
    issue_key = issue["key"]
    summary   = issue["summary"]

    print()
    path = screen_drop_zone()
    if not path or path == "skip":
        print(f"  {C_YELLOW}Imagen omitida.{RESET}")
        return None

    new_path, new_name = rename_image(path, issue_key)
    print(f"\n  {DIM}Imagen renombrada: {new_name}{RESET}")
    print(f"  {DIM}Subiendo adjunto...{RESET}")
    uploaded = jira.upload_attachment(issue_key, new_path)
    if not uploaded:
        print(f"  {C_RED}✗ Error al subir el adjunto. Abortando flujo.{RESET}")
        read_line("  Presiona Enter para continuar...")
        return None
    print(f"  {C_GREEN}✓ Adjunto subido: {uploaded}{RESET}")

    now  = datetime.now().strftime("%d/%m/%Y %H:%M")
    body = (
        f"[{now}] ✅ *{issue_key} — Actualización de avance*\n\n"
        f"La tarea \"{summary}\" ha sido revisada. "
        f"Se verificó el cumplimiento de los criterios de aceptación del sprint. "
        f"Se adjunta evidencia visual.\n\n"
        f"Estado final: *DOING (construcción hecha)*. "
        f"Sin bloqueantes identificados. ¡Buen trabajo! 🚀\n\n"
        f"!{uploaded}|thumbnail!"
    )
    print(f"  {DIM}Publicando comentario...{RESET}")
    ok_comment = jira.add_comment(issue_key, body)
    if ok_comment:
        print(f"  {C_GREEN}✓ Comentario publicado.{RESET}")
    else:
        print(f"  {C_RED}✗ Error al publicar comentario.{RESET}")

    print(f"  {DIM}Obteniendo transiciones...{RESET}")
    transitions       = jira.get_transitions(issue_key)
    target_transition = None
    for t in transitions:
        if "hecha" in t["name"].lower() or "hecho" in t["name"].lower():
            target_transition = t
            break

    new_status = None
    if target_transition:
        ok_trans = jira.transition_issue(issue_key, target_transition["id"])
        if ok_trans:
            new_status = target_transition["name"]
            print(f"  {C_GREEN}✓ Estado cambiado a: {new_status}{RESET}")
        else:
            print(f"  {C_RED}✗ Error al cambiar estado.{RESET}")
    else:
        print(f"\n  {C_YELLOW}No se encontró la transición automáticamente.{RESET}")
        print(f"  {BOLD}Transiciones disponibles:{RESET}")
        for i, t in enumerate(transitions):
            print(f"  [{i + 1}]  {t['name']}")
        choice = read_line("  Elige número (o Enter para omitir): ")
        if choice.strip():
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(transitions):
                    t        = transitions[idx]
                    ok_trans = jira.transition_issue(issue_key, t["id"])
                    if ok_trans:
                        new_status = t["name"]
                        print(f"  {C_GREEN}✓ Estado cambiado a: {new_status}{RESET}")
            except ValueError:
                pass

    print(f"\n  {DIM}{'─' * 46}{RESET}")
    print(f"  {C_GREEN}✓{RESET} {issue_key} procesada exitosamente")
    print(f"  {C_GREEN}✓{RESET} Evidencia: {uploaded}")
    if ok_comment:
        print(f"  {C_GREEN}✓{RESET} Comentario publicado como Scrum Master")
    if new_status:
        print(f"  {C_GREEN}✓{RESET} Estado → {new_status}")
    print(f"  {DIM}{'─' * 46}{RESET}\n")

    read_line("  Presiona Enter para volver a la lista...")
    return "done"


# ── Punto de entrada ──────────────────────────────────────────────────────────
def run_app(jira, project):
    try:
        while True:
            clear()
            print(f"\n  {DIM}Cargando sprint activo...{RESET}")
            all_issues = jira.get_my_issues(project)

            if not all_issues:
                clear()
                print(f"\n  {C_YELLOW}⚠  No se encontraron tareas en el proyecto {project}.{RESET}")
                print(f"  {DIM}  • Verifica la clave del proyecto y el board ID en .env{RESET}")
                print(f"  {DIM}  • Asegúrate de que hay un sprint activo{RESET}")
                print(f"\n  {DIM}[r] Reintentar  [q] Salir{RESET}\n")
                while True:
                    k = get_key()
                    if k.lower() == "r":
                        break
                    elif k.lower() == "q":
                        clear()
                        print(f"\n  {C_GREEN}¡Hasta luego!{RESET}\n")
                        sys.exit(0)
                continue

            print(f"  {DIM}Cargando información de carriles...{RESET}")
            epic_keys = list({i["epic_key"] for i in all_issues if i.get("epic_key")})
            epics_map = jira.get_epics_info(epic_keys)

            # Resetear scroll del menú en cada recarga
            if hasattr(screen_epic_menu, "_scroll"):
                screen_epic_menu._scroll = 0

            result = screen_epic_menu(jira, project, all_issues, epics_map)
            if result != "reload":
                break
    except KeyboardInterrupt:
        clear()
        print(f"\n  {C_GREEN}¡Hasta luego!{RESET}\n")
        sys.exit(0)
