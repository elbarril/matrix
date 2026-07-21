#!/usr/bin/env python3
import argparse
import json
import re
import sqlite3
import sys
from collections import namedtuple
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "America/Argentina/Buenos_Aires"
DB_PATH = Path.home() / ".local" / "share" / "devin" / "cli" / "sessions.db"
MATRIX_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_COLUMNS = {
    "sessions": {"id", "working_directory", "created_at", "last_activity_at", "metadata", "title"},
    "message_nodes": {"session_id", "node_id", "chat_message", "created_at"},
}
SessionCost = namedtuple(
    "SessionCost",
    "session_id cwd created_at last_activity_at duration_seconds acu_cost credit_cost title",
)
SubagentInvocation = namedtuple(
    "SubagentInvocation", "name start_ts end_ts duration_seconds exact"
)
NOTE = (
    "Nota: las tareas de run_subagent (Architect/Trinity/Smith/etc.) quedan grabadas como nodos "
    "'user' dentro de este mismo árbol — no son necesariamente texto tipeado por el humano. "
    "Para distinguir, mirá si el mensaje 'assistant' inmediatamente anterior tiene un tool_call "
    "run_subagent con el mismo texto."
)


class QueryError(Exception):
    pass


def load_timezone():
    config_path = MATRIX_ROOT / "brain" / "config.yaml"
    timezone_name = DEFAULT_TIMEZONE
    try:
        with config_path.open(encoding="utf-8") as config:
            for line in config:
                match = re.match(r"^\s*timezone\s*:\s*([^#]+?)\s*(?:#.*)?$", line)
                if match:
                    timezone_name = match.group(1).strip().strip("\"'")
                    break
        return ZoneInfo(timezone_name)
    except (OSError, ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def connect_read_only(path=DB_PATH):
    path = Path(path).expanduser().resolve()
    try:
        return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as error:
        raise QueryError(
            f"session_query: no se pudo abrir sessions.db en modo read-only ({path}): {error}"
        ) from error


def guard_schema(connection):
    for table, expected in EXPECTED_COLUMNS.items():
        try:
            actual = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        except sqlite3.Error as error:
            raise QueryError(f"session_query: no se pudo verificar el schema: {error}") from error
        for column in sorted(expected - actual):
            raise QueryError(
                "session_query: schema de sessions.db cambió "
                f"(falta columna '{column}' en tabla '{table}') — este script necesita "
                "actualizarse, no vamos a adivinar. Abortando."
            )


def local_datetime(epoch, timezone):
    return datetime.fromtimestamp(epoch, timezone)


def format_datetime(epoch, timezone):
    return local_datetime(epoch, timezone).isoformat(sep=" ", timespec="seconds")


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("la fecha debe tener formato YYYY-MM-DD") from error


def parse_clock(value):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as error:
        raise argparse.ArgumentTypeError("la hora debe tener formato HH:MM") from error


def truncate(text, limit, suffix_template="... [truncado, {length} chars totales]"):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + suffix_template.format(length=len(text))


def find_sessions(connection, cwd_substring, day, timezone):
    sql = (
        "SELECT id, working_directory, created_at, last_activity_at, title "
        "FROM sessions WHERE working_directory LIKE ?"
    )
    params = [f"%{cwd_substring}%"]
    if day is not None:
        start = datetime.combine(day, time.min, timezone)
        end = start + timedelta(days=1)
        sql += " AND last_activity_at >= ? AND last_activity_at < ?"
        params.extend([int(start.timestamp()), int(end.timestamp())])
    sql += " ORDER BY last_activity_at DESC"
    try:
        return connection.execute(sql, params).fetchall()
    except sqlite3.Error as error:
        raise QueryError(f"session_query: falló la consulta de sesiones: {error}") from error


def command_find(args, connection, timezone):
    rows = find_sessions(connection, args.cwd_substring, args.day, timezone)
    if not rows:
        detail = f" para el día {args.day.isoformat()}" if args.day else ""
        print(f"session_query: no se encontraron sesiones para '{args.cwd_substring}'{detail}.")
        return
    print("session_id | cwd | created_at (local) | last_activity_at (local) | title")
    for session_id, cwd, created_at, last_activity_at, title in rows:
        print(
            f"{session_id} | {cwd} | {format_datetime(created_at, timezone)} | "
            f"{format_datetime(last_activity_at, timezone)} | {title or ''}"
        )


def parse_session_metadata(raw):
    try:
        parsed = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def collect_sessions_cost(connection, cwd_substring, day, timezone):
    sql = (
        "SELECT id, working_directory, created_at, last_activity_at, title, metadata "
        "FROM sessions WHERE working_directory LIKE ?"
    )
    params = [f"%{cwd_substring}%"]
    if day is not None:
        start = datetime.combine(day, time.min, timezone)
        end = start + timedelta(days=1)
        sql += " AND last_activity_at >= ? AND last_activity_at < ?"
        params.extend([int(start.timestamp()), int(end.timestamp())])
    sql += " ORDER BY last_activity_at DESC"
    try:
        rows = connection.execute(sql, params).fetchall()
    except sqlite3.Error as error:
        raise QueryError(f"session_query: falló la consulta de consumo: {error}") from error
    return [
        SessionCost(
            session_id,
            cwd,
            created_at,
            last_activity_at,
            last_activity_at - created_at if created_at is not None and last_activity_at is not None else None,
            parse_session_metadata(metadata).get("total_acu_cost"),
            parse_session_metadata(metadata).get("total_credit_cost"),
            title,
        )
        for session_id, cwd, created_at, last_activity_at, title, metadata in rows
    ]


def format_duration(seconds):
    if seconds is None:
        return "—"
    seconds = max(0, int(seconds))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours}h {minutes:02d}m {seconds:02d}s" if hours else f"{minutes}m {seconds:02d}s"


def format_cost(value):
    return "—" if value is None else str(value)


def command_cost(args, connection, timezone):
    rows = collect_sessions_cost(connection, args.cwd_substring, args.day, timezone)
    if not rows:
        detail = f" para el día {args.day.isoformat()}" if args.day else ""
        print(f"session_query: no se encontraron sesiones para '{args.cwd_substring}'{detail}.")
        return
    print("Duración de sesión: wall-clock, incluye tiempo ocioso.")
    print("session_id | cwd | created_at (local) | duración | ACU | crédito | title")
    for row in rows:
        print(
            f"{row.session_id} | {row.cwd} | {format_datetime(row.created_at, timezone)} | "
            f"{format_duration(row.duration_seconds)} | {format_cost(row.acu_cost)} | "
            f"{format_cost(row.credit_cost)} | {row.title or ''}"
        )


def load_messages(connection, session_id):
    try:
        rows = connection.execute(
            "SELECT node_id, chat_message, created_at FROM message_nodes "
            "WHERE session_id = ? ORDER BY node_id",
            (session_id,),
        ).fetchall()
    except sqlite3.Error as error:
        raise QueryError(f"session_query: falló la consulta de mensajes: {error}") from error

    messages = []
    seen = set()
    for node_id, raw_message, created_at in rows:
        try:
            message = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError) as error:
            raise QueryError(
                f"session_query: chat_message inválido en node_id {node_id}; abortando: {error}"
            ) from error
        message_id = message.get("message_id")
        dedup_key = ("message_id", message_id) if message_id is not None else ("node_id", node_id)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        messages.append((created_at, message))
    return messages


def in_clock_range(timestamp, timezone, from_time, to_time):
    clock = local_datetime(timestamp, timezone).time().replace(tzinfo=None)
    if from_time is not None and clock < from_time:
        return False
    if to_time is not None and clock > to_time:
        return False
    return True


def tool_call_parts(tool_call):
    function = tool_call.get("function") if isinstance(tool_call, dict) else None
    if isinstance(function, dict):
        name = function.get("name") or "<sin nombre>"
        arguments = function.get("arguments", "")
    elif isinstance(tool_call, dict):
        name = tool_call.get("name") or "<sin nombre>"
        arguments = tool_call.get("arguments", "")
    else:
        return "<inválido>", tool_call
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
    return name, arguments


def tool_call_id(tool_call):
    return tool_call.get("id") if isinstance(tool_call, dict) else None


def parse_subagent_name(arguments):
    try:
        parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    for key in ("profile", "subagent", "agent", "subagent_type", "agent_name", "type", "title"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def extract_subagent_invocations(messages):
    pending = {}
    invocations = []
    for timestamp, message in messages:
        matched_id = message.get("tool_call_id")
        if matched_id in pending:
            name, start_ts = pending.pop(matched_id)
            invocations.append(
                SubagentInvocation(name, start_ts, timestamp, timestamp - start_ts, True)
            )
        if message.get("role") != "assistant":
            continue
        for tool_call in message.get("tool_calls") or []:
            name, arguments = tool_call_parts(tool_call)
            call_id = tool_call_id(tool_call)
            if name != "run_subagent":
                continue
            subagent_name = parse_subagent_name(arguments) or "<subagente no identificado>"
            if call_id:
                pending.setdefault(call_id, (subagent_name, timestamp))
            else:
                invocations.append(SubagentInvocation(subagent_name, timestamp, None, None, False))
    invocations.extend(
        SubagentInvocation(name, start_ts, None, None, False)
        for name, start_ts in pending.values()
    )
    return sorted(invocations, key=lambda invocation: invocation.start_ts)


def command_subagents(args, connection, timezone):
    messages = load_messages(connection, args.session_id)
    if not messages:
        print(f"session_query: no se encontraron mensajes para la sesión '{args.session_id}'.")
        return
    invocations = extract_subagent_invocations(messages)
    if not invocations:
        print(f"session_query: no se encontraron invocaciones run_subagent en '{args.session_id}'.")
        return
    print("Duración por subagente: message_nodes; ACU no atribuible por subagente.")
    print("inicio (local) | subagente | duración | estado")
    for invocation in invocations:
        state = "pareado por tool_call_id" if invocation.exact else "sin cierre registrado"
        print(
            f"{format_datetime(invocation.start_ts, timezone)} | {invocation.name} | "
            f"{format_duration(invocation.duration_seconds)} | {state}"
        )


def print_message(timestamp, message, timezone, full):
    role = message.get("role") or "unknown"
    content = message.get("content") or ""
    print(f"\n[{format_datetime(timestamp, timezone)}] {role}")
    if role == "system":
        if full:
            if content:
                print(content)
        else:
            preview = truncate(content.replace("\n", " "), 100, "...")
            print(f"[system: {preview}]")
    elif role == "tool":
        preview = truncate(content.replace("\n", " "), 150, "...")
        print(content if full else f"[tool result, {preview}]")
    elif role in ("user", "assistant") and content:
        print(content if full else truncate(content, 800))
    elif content:
        print(content if full else truncate(content, 800))

    for tool_call in message.get("tool_calls") or []:
        name, arguments = tool_call_parts(tool_call)
        print(f"TOOLCALL {name} {truncate(arguments, 200, '...')}")


def command_dump(args, connection, timezone):
    messages = load_messages(connection, args.session_id)
    print(NOTE)
    if not messages:
        print(f"session_query: no se encontraron mensajes para la sesión '{args.session_id}'.")
        return
    filtered = [
        (timestamp, message)
        for timestamp, message in messages
        if in_clock_range(timestamp, timezone, args.from_time, args.to_time)
    ]
    if not filtered:
        print(f"session_query: no hay mensajes de '{args.session_id}' en el rango horario indicado.")
        return
    for timestamp, message in filtered:
        print_message(timestamp, message, timezone, args.full)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="session_query.py",
        description="Consulta read-only del store de sesiones de Devin CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    find_parser = subparsers.add_parser("find", help="buscar sesiones por cwd")
    find_parser.add_argument("cwd_substring")
    find_parser.add_argument("day", nargs="?", type=parse_date, metavar="YYYY-MM-DD")

    dump_parser = subparsers.add_parser("dump", help="reconstruir mensajes de una sesión")
    dump_parser.add_argument("session_id")
    dump_parser.add_argument("--from", dest="from_time", type=parse_clock, metavar="HH:MM")
    dump_parser.add_argument("--to", dest="to_time", type=parse_clock, metavar="HH:MM")
    dump_parser.add_argument("--full", action="store_true")

    cost_parser = subparsers.add_parser("cost", help="consumo por sesión (ACU/crédito/duración)")
    cost_parser.add_argument("cwd_substring", nargs="?", default="")
    cost_parser.add_argument("day", nargs="?", type=parse_date, metavar="YYYY-MM-DD")

    subagents_parser = subparsers.add_parser("subagents", help="desglose de subagentes de una sesión")
    subagents_parser.add_argument("session_id")
    return parser


def main():
    args = build_parser().parse_args()
    timezone = load_timezone()
    connection = None
    try:
        connection = connect_read_only()
        guard_schema(connection)
        if args.command == "find":
            command_find(args, connection, timezone)
        elif args.command == "dump":
            command_dump(args, connection, timezone)
        elif args.command == "cost":
            command_cost(args, connection, timezone)
        else:
            command_subagents(args, connection, timezone)
    except QueryError as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            connection.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
