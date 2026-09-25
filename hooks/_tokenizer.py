"""Seraph · _tokenizer — detective write-target tokenizer for shell-like tools.

Consumed by the runtime translator (adapters/*/hooks/session_audit.py), which
parses a mutant command's write targets in memory and persists only the parsed
targets plus a flag — never the raw command line (secret leak surface).

This detective tokenizer deliberately has a fail-closed policy on unparseable
write intent. It is intentionally NOT shared with pre_exec_guard's preventive
tokenizer, which fails open to avoid blocking on uncertainty — see that module.
"""

import shlex


ALLOWED_MUTANT_PREFIX = "bin/matrix corpus-ingest"
_WRITE_ALL_ARGS = {"rm", "rmdir", "truncate", "tee"}
_WRITE_LAST_ARG = {"mv", "cp"}
_CONTROL_OPS = {";", "&&", "||", "|", "&"}
_WRITE_HINTS = (">", ">>", "tee ", "rm ", "rmdir ", "mv ", "cp ", "truncate ", "sed -i")


def _strip_heredocs(command):
    """Return the command's shell lines with heredoc bodies removed.

    A heredoc body is data, not shell syntax: an eval artifact written with
    `cat > path << 'EOF'` carries prose that must never reach the tokenizer
    (a `>` inside a sentence is not a redirection). Delimiter forms handled:
    << EOF, <<- EOF, << 'EOF', << "EOF".
    """
    lines, out, i = command.splitlines(), [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        marker = None
        idx = line.find("<<")
        if idx != -1 and not line[idx:].startswith("<<<"):
            rest = line[idx + 2:].lstrip()
            if rest.startswith("-"):
                rest = rest[1:].lstrip()
            token = rest.split()[0] if rest.split() else ""
            marker = token.strip("'\"") or None
        i += 1
        if marker:
            while i < len(lines) and lines[i].strip() != marker:
                i += 1
            i += 1  # skip the terminating delimiter line
    return out


def _lexical_chunks(lines):
    """Group physical shell lines into minimal chunks that shlex can parse.

    A shell command is ONE lexical unit even when it spans several physical
    lines: a quote opened on line 1 and closed on line 7 is valid syntax, not
    garbage. Tokenizing line-by-line reported `python3 -c "` as unparseable
    write intent and fail-closed on a command whose only target was /tmp.

    shlex is the oracle for "is a quote still open" -- a ValueError means the
    chunk is incomplete, so the next line is appended and the parse retried.
    Nothing here re-implements shell lexing on purpose (Foundation 4).

    Returns a list of (text, tokens) pairs. `tokens` is None when the chunk
    never parsed (unterminated quote through the end of the command), leaving
    the fail-closed policy of the caller in charge.
    """
    chunks, buffer = [], None
    for line in lines:
        buffer = line if buffer is None else buffer + "\n" + line
        try:
            tokens = shlex.split(buffer)
        except ValueError:
            continue
        chunks.append((buffer, tokens))
        buffer = None
    if buffer is not None:
        chunks.append((buffer, None))
    return chunks


def write_targets(command, root):
    """Return parsed write targets and whether write intent could not be parsed.

    A shell command is a single lexical unit even across physical lines; see
    `_lexical_chunks`. Order of operations: strip heredocs, chunk by quotable
    lines, tokenize each chunk. This detective tokenizer intentionally
    diverges from pre_exec_guard but fails closed on unparseable write intent;
    the preventive guard fails open to avoid blocking on uncertainty.
    """
    targets = []
    unparsed = False
    for text, tokens in _lexical_chunks(_strip_heredocs(command)):
        if tokens is None:
            if any(hint in text for hint in _WRITE_HINTS):
                unparsed = True
            continue
        for i, token in enumerate(tokens):
            if token in (">", ">>") and i + 1 < len(tokens):
                targets.append(tokens[i + 1])
        segments, segment = [], []
        for token in tokens:
            if token in _CONTROL_OPS:
                if segment:
                    segments.append(segment)
                segment = []
            else:
                segment.append(token)
        if segment:
            segments.append(segment)
        for segment in segments:
            verb = segment[0]
            args = segment[1:]
            if verb in _WRITE_ALL_ARGS:
                targets.extend(arg for arg in args if not arg.startswith("-"))
            elif verb in _WRITE_LAST_ARG and args:
                targets.append(args[-1])
            elif verb == "git" and args and args[0] == "rm":
                targets.extend(arg for arg in args[1:] if not arg.startswith("-"))
            elif verb == "sed" and any(arg == "-i" or arg.startswith("-i.") or arg == "--in-place" for arg in args):
                targets.extend(arg for arg in args if not arg.startswith("-"))
    return targets, unparsed
