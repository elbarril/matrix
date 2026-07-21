#!/usr/bin/env python3
import argparse
import html
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import session_query as sq


OUTPUT_DIR = sq.MATRIX_ROOT / "brain" / "output"
OUTPUT_FILE = OUTPUT_DIR / "session-report.html"


def esc(value):
    return html.escape("" if value is None else str(value))


def render_subagents(connection, session_id, timezone):
    invocations = sq.extract_subagent_invocations(sq.load_messages(connection, session_id))
    if not invocations:
        return "<p>No se registraron invocaciones de subagentes.</p>"
    rows = []
    for invocation in invocations:
        state = "Pareado por tool_call_id" if invocation.exact else "Sin cierre registrado"
        rows.append(
            "<tr>"
            f"<td>{esc(sq.format_datetime(invocation.start_ts, timezone))}</td>"
            f"<td>{esc(invocation.name)}</td>"
            f"<td>{esc(sq.format_duration(invocation.duration_seconds))}</td>"
            f"<td>{esc(state)}</td>"
            "</tr>"
        )
    return (
        "<p>Duración por message_nodes; ACU no atribuible por subagente.</p>"
        "<table><thead><tr><th>Inicio</th><th>Subagente</th><th>Duración</th>"
        f"<th>Estado</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def render_report(connection, timezone, cwd_substring, day, limit):
    sessions = sq.collect_sessions_cost(connection, cwd_substring, day, timezone)[:limit]
    filters = f"cwd contiene: {cwd_substring or 'todos'}"
    if day:
        filters += f" · día: {day.isoformat()}"
    rows = []
    for session in sessions:
        details = render_subagents(connection, session.session_id, timezone)
        rows.append(
            "<tr>"
            f"<td>{esc(session.session_id)}</td><td>{esc(session.cwd)}</td>"
            f"<td>{esc(sq.format_datetime(session.created_at, timezone))}</td>"
            f"<td>{esc(sq.format_duration(session.duration_seconds))}</td>"
            f"<td>{esc(sq.format_cost(session.acu_cost))}</td>"
            f"<td>{esc(sq.format_cost(session.credit_cost))}</td>"
            f"<td>{esc(session.title)}</td>"
            f"<td><details><summary>Ver subagentes</summary>{details}</details></td>"
            "</tr>"
        )
    body = "".join(rows) or "<tr><td colspan='8'>No se encontraron sesiones.</td></tr>"
    generated = datetime.now(timezone).isoformat(sep=" ", timespec="seconds")
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Matrix · Session report</title>
<style>
body {{ background:#0d0d0d; color:#e6e6e6; font:14px system-ui,sans-serif; margin:2rem; }}
h1,h2 {{ color:#00ff41; }} .meta,p {{ color:#a8b3aa; }} table {{ border-collapse:collapse; width:100%; margin:1rem 0; }}
th,td {{ border:1px solid #294333; padding:.55rem; vertical-align:top; text-align:left; }} th {{ color:#00ff41; }}
details {{ min-width:20rem; }} summary {{ cursor:pointer; color:#00ff41; }} details table {{ font-size:.9em; }}
</style></head><body>
<h1>Matrix · Reporte de sesiones Devin</h1>
<p class="meta">Generado: {esc(generated)} · {esc(filters)} · límite: {limit}</p>
<p>Duración de sesión: <strong>wall-clock, incluye tiempo ocioso</strong>.</p>
<table><thead><tr><th>Session ID</th><th>CWD</th><th>Creada</th><th>Duración</th><th>ACU</th><th>Crédito</th><th>Título</th><th>Desglose</th></tr></thead>
<tbody>{body}</tbody></table></body></html>"""


def main():
    parser = argparse.ArgumentParser(prog="session_report.py")
    parser.add_argument("cwd_substring", nargs="?", default="")
    parser.add_argument("day", nargs="?", type=sq.parse_date, metavar="YYYY-MM-DD")
    parser.add_argument("--out", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit debe ser cero o positivo")
    connection = None
    try:
        connection = sq.connect_read_only()
        sq.guard_schema(connection)
        report = render_report(connection, sq.load_timezone(), args.cwd_substring, args.day, args.limit)
    except sq.QueryError as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            connection.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"session_report: {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
