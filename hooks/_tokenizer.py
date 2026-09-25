"""Seraph · _tokenizer — detective write-target tokenizer for shell-like tools.

Consumed by the runtime translator (adapters/*/hooks/session_audit.py), which
parses a mutant command's write targets in memory and persists only the parsed
targets plus a flag — never the raw command line (secret leak surface).

This detective tokenizer deliberately has a fail-closed policy on unparseable
write intent. It is intentionally NOT shared with pre_exec_guard's preventive
tokenizer, which fails open to avoid blocking on uncertainty — see that module.

Segmentation divergence: the detective tokenizer splits control operators that
are glued to a token (`clean;` -> `clean`, `;`); pre_exec_guard's preventive
tokenizer does NOT. Do not fix one without the other as a tracked change.
"""

import os
import shlex


ALLOWED_MUTANT_PREFIX = "bin/matrix corpus-ingest"
_WRITE_ALL_ARGS = {"rm", "rmdir", "tee"}
_WRITE_LAST_ARG = {"mv", "cp"}
_CONTROL_OPS = {";", "&&", "||", "|", "&"}
_WRITE_HINTS = (">", ">>", "tee ", "rm ", "rmdir ", "mv ", "cp ", "truncate ", "sed -i", "dd ")


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
            lexer = shlex.shlex(buffer, posix=True, punctuation_chars=";&|<>")
            lexer.whitespace_split = True
            lexer.commenters = ""
            tokens = list(lexer)
        except ValueError:
            continue
        chunks.append((buffer, tokens))
        buffer = None
    if buffer is not None:
        chunks.append((buffer, None))
    return chunks


# Shell variables the detective can resolve against the root it already
# receives. $MATRIX_ROOT is always exported by the adapter runtime; $HOME is
# the user home. $ROOT is deliberately NOT listed: it is never exported to
# the exec runtime (only MATRIX_ROOT is), so treating it as known would be a
# dead branch. An unresolved $VAR target is left as-is and surfaced by the
# detector in an informative bucket, never flagged as an anomaly.
_KNOWN_SHELL_VARS = ("MATRIX_ROOT", "HOME")


def _resolve_shell_var(target, root):
    """Resolve a leading known shell var in `target` against `root`.

    Only a full `$VAR` or `$VAR/...` prefix is resolved; anything else (an
    unknown variable such as `$FR/...`, or a `$` appearing mid-token) is
    returned unchanged so the detector can bucket it without losing evidence.
    """
    for name in _KNOWN_SHELL_VARS:
        prefix = "$" + name
        if target == prefix:
            return root if name == "MATRIX_ROOT" else os.path.expanduser("~")
        if target.startswith(prefix + "/"):
            base = root if name == "MATRIX_ROOT" else os.path.expanduser("~")
            return base + target[len(prefix):]
    return target


def _sed_write_targets(args):
    """Write targets for `sed` in-place editing; [] when no in-place flag.

    Option-aware walk: `-e`/`-f`/`--expression=`/`--file=` consume their value
    as script/script-file (never a target); short clusters are walked
    char-by-char with `i` marking in-place and `e`/`f` consuming the
    rest-of-cluster or the next token as script/script-file. The first bare
    token is the script only when no script source was seen; every later bare
    token is a FILE. A residual FP on `sed -i ''` (BSD) is accepted by design;
    the file operands still resolve.
    """
    in_place = False
    saw_script_source = False
    bare = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            if arg == "--in-place" or arg.startswith("--in-place="):
                in_place = True
            elif arg.startswith("--expression=") or arg.startswith("--file="):
                saw_script_source = True
        elif arg.startswith("-") and arg != "-":
            j = 0
            cluster = arg[1:]
            while j < len(cluster):
                if cluster[j] == "i":
                    in_place = True
                elif cluster[j] in ("e", "f"):
                    saw_script_source = True
                    if j + 1 < len(cluster):
                        break  # rest of the cluster is the script value
                    i += 1  # the next token is the script value
                    break
                j += 1
        else:
            bare.append(arg)
        i += 1
    if not in_place:
        return []
    if not saw_script_source and bare:
        return bare[1:]
    return bare


def _truncate_write_targets(args):
    """Write targets for `truncate`.

    `-s`/`--size` and `-r`/`--reference` consume their operand (a size or a
    read-only reference file, never a target); `-o`/`--io-blocks` and
    `-c`/`--no-create` are ignored. Short clusters are walked char-by-char
    with `s`/`r` consuming the rest-of-cluster or the next token. Remaining
    bare tokens are FILEs. A trailing `-s`/`-r` with no operand yields [].
    """
    bare = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            if arg == "--size" or arg == "--reference":
                i += 1  # the next token is the operand
            elif arg.startswith("--size=") or arg.startswith("--reference="):
                pass  # value attached, consumed
        elif arg.startswith("-") and arg != "-":
            j = 0
            cluster = arg[1:]
            while j < len(cluster):
                if cluster[j] in ("s", "r"):
                    if j + 1 < len(cluster):
                        break  # rest of the cluster is the operand
                    i += 1  # the next token is the operand
                    break
                j += 1
        else:
            bare.append(arg)
        i += 1
    return bare


def write_targets(command, root):
    """Return parsed write targets and whether write intent could not be parsed.

    A shell command is a single lexical unit even across physical lines; see
    `_lexical_chunks`. Order of operations: strip heredocs, chunk by quotable
    lines, tokenize each chunk with control operators split even when glued to
    a token (`clean;` -> `clean`, `;`). This detective tokenizer intentionally
    diverges from pre_exec_guard but fails closed on unparseable write intent;
    the preventive guard fails open to avoid blocking on uncertainty.

    A write target that begins with a known shell var (`$MATRIX_ROOT`, `$HOME`)
    is resolved against `root` so the detector can judge it; an unknown var
    (`$FR/...`) is returned unchanged and the detector buckets it
    informatively instead of flagging a false anomaly.
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
            elif verb == "sed":
                targets.extend(_sed_write_targets(args))
            elif verb == "truncate":
                targets.extend(_truncate_write_targets(args))
            elif verb == "dd":
                # dd's write target is the `of=` operand only: `if=` is an
                # input and loose operands (bs=, count=, status=) are not
                # files the command creates. Confining this to the `dd` verb
                # keeps unrelated tokens that merely start with `of=` from
                # becoming false targets.
                targets.extend(arg[3:] for arg in args if arg.startswith("of=") and arg[3:])
    return [_resolve_shell_var(target, root) for target in targets], unparsed
