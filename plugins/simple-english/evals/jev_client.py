"""TypeSafe Jev client, per docs/jev-contract.md.

Every failure comes back as {"ok": False, "reason": ...}; nothing here raises
to the caller. Three byte-identical copies exist: session-tools
(skills/session-digest/scripts/), project-glossary (skills/glossary/scripts/),
and simple-english (evals/). A test in each copying plugin compares its copy,
so edit the session-tools copy and copy it over. The commit-scope plugin
carries a TypeScript twin. All of them pass the fixtures in
plugins/session-tools/tests/fixtures/jev/. Change them together.
"""

import http.client
import json
import math
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
KEY_VAR = "TYPESAFE_API_KEY"
TIMEOUT_SECONDS = 15
RETRY_DELAY_SECONDS = 1
RETRY_STATUSES = (429, 529)
REDACTED = "[redacted]"

# Order matters: specific token shapes first, then the generic `name = value`
# rule, so "token=sk-..." ends as "token=[redacted]" either way.
# re.A and explicit [ \t] keep Python and JavaScript matching the same text.
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----(?:[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----|(?:\r?\n[A-Za-z0-9+/=]+)*)", re.A), REDACTED),
    (re.compile(r"\b(Bearer|bearer|Basic|basic)[ \t]+(?=[A-Za-z._~-]*[0-9+/=])[A-Za-z0-9._~+/=-]{16,}", re.A), r"\1 " + REDACTED),
    (re.compile(r"\b(?:sk|tsk)[-_][A-Za-z0-9_-]{16,}", re.A), REDACTED),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}", re.A), REDACTED),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}", re.A), REDACTED),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b", re.A), REDACTED),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}", re.A), REDACTED),
    (re.compile(r"""\b((?:[A-Za-z0-9]+[_-])*(?:password|passwd|secret|token|api[_-]?key)(?:[_-][A-Za-z0-9]+)*)(["']?[ \t]*[:=][ \t]*)("(?:[^"\\]|\\.)*"|'[^']*'|[^ \t\r\n,;}\]]+)""", re.I | re.A),
     r"\1\2" + REDACTED),
]


# Consent per docs/jev-contract.md, "Opt-in": the first row that matches decides.
# Pure, so both clients pass consent-cases.json; each caller reads the files.


def _reject_constant(name):
    raise ValueError(name)


def _parse_object(text):
    if text is None:
        return None
    if text.startswith("\ufeff"):
        text = text[1:]
    try:
        value = json.loads(text, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _broken(text):
    """The file exists but does not parse to a JSON object. A missing file is not broken."""
    return text is not None and _parse_object(text) is None


def _block(data, feature):
    block = data.get(feature) if isinstance(data, dict) else None
    return block if isinstance(block, dict) else None


def normal_folder(folder, windows):
    """Forward slashes, no trailing slash, and lower case on Windows."""
    slashed = re.sub(r"/+\Z", "", folder.replace("\\", "/"))
    return slashed.lower() if windows else slashed


def covering_folders(user_file, folder, windows):
    """The opt_out_folders entries, as written, that cover `folder` or a folder above it."""
    data = _parse_object(user_file)
    entries = data.get("opt_out_folders") if data else None
    if not isinstance(entries, list):
        return []
    target = normal_folder(folder, windows)
    found = []
    for entry in entries:
        if not isinstance(entry, str) or not entry.strip():
            continue
        norm = normal_folder(entry, windows)
        if target == norm or target.startswith(norm + "/"):
            found.append(entry)
    return found


def consent(feature, repo_file, git_opt_out, user_file, folder, windows):
    """{"on": True}, or {"on": False, "reason": ...} with the first rule that matched.

    repo_file and user_file are file text or None. git_opt_out is the value of
    `git config --local jev.<feature>.optout`, or None when unset or outside git.
    """
    if _broken(repo_file):
        return {"on": False, "reason": "repository file does not parse"}
    block = _block(_parse_object(repo_file), feature)
    if block is not None and block.get("allowed") is False:
        return {"on": False, "reason": "repository forbids"}
    if git_opt_out is not None and git_opt_out.strip().lower() != "false":
        return {"on": False, "reason": "you opted out"}
    if covering_folders(user_file, folder, windows):
        return {"on": False, "reason": "you opted out"}
    if _broken(user_file):
        return {"on": False, "reason": "user file does not parse"}
    block = _block(_parse_object(user_file), feature)
    if block is not None and block.get("enabled") is True:
        return {"on": True}
    return {"on": False, "reason": "not opted in"}


# Gather the consent inputs for one feature. The TypeScript twin is jevInputs
# in commit-scope's jev.ts. Only a missing git or a clean "not a git
# repository" counts as outside git. Any other git failure is an unknown
# repository and comes back as an opt-out value, so a git error never turns a
# feature on.

GIT_TIMEOUT_SECONDS = 10
_NOT_A_REPOSITORY = re.compile(r"not a git repository", re.I)


def _read_file(path):
    """The file's text, or None when it does not exist.

    A file that exists but cannot be read comes back as "", which does not
    parse, so consent treats it as broken rather than as missing.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError):
        return ""


def _git(folder, args, run):
    """(exit code, stdout, stderr) of one git call. The code is None when git is missing."""
    try:
        done = run(["git", *args], cwd=folder, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT_SECONDS)
    except FileNotFoundError:
        return None, "", ""
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return -1, "", str(error)
    return done.returncode, done.stdout or "", done.stderr or ""


def _git_inputs(feature, folder, run):
    """(toplevel or None, the git opt-out value or None) for `folder`."""
    code, out, err = _git(folder, ["rev-parse", "--show-toplevel"], run)
    if code == 0 and out.strip():
        toplevel = out.strip()
    elif code is None or (code == 128 and _NOT_A_REPOSITORY.search(err)):
        return None, None
    else:
        return None, "error (rev-parse exit %s)" % code
    code, out, _ = _git(folder, ["config", "--local", "--get", "jev.%s.optout" % feature], run)
    if code == 0:
        return toplevel, out.strip()
    if code == 1:  # the key is unset
        return toplevel, None
    return toplevel, "error (config exit %s)" % code


def feature_consent(feature, folder, home=None, run=subprocess.run):
    """{"on": bool, "reason": str or None, "block": dict} per docs/jev-contract.md."""
    # `folder` is the session's folder. abspath resolves "." and "..", so a
    # relative path cannot step around an opt_out_folders entry. `home` holds
    # .claude/jev-user.json and defaults to the user's home folder. `run`
    # stands in for subprocess.run in tests. `block` is the repository file's
    # block for the feature, or {}, so a caller can read its tuning keys.
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        # A folder that is gone would read as outside git, where no git
        # opt-out applies. Its repository is unknown, so it counts as an opt-out.
        return {"on": False, "reason": "you opted out", "block": {}}
    home = os.path.expanduser("~") if home is None else home
    toplevel, git_opt_out = _git_inputs(feature, folder, run)
    repo_file = _read_file(os.path.join(toplevel or folder, ".claude", "jev.json"))
    user_file = _read_file(os.path.join(home, ".claude", "jev-user.json"))
    result = consent(feature, repo_file, git_opt_out, user_file, folder, os.name == "nt")
    return {"on": result["on"], "reason": result.get("reason"),
            "block": _block(_parse_object(repo_file), feature) or {}}


def redact(text, key=None):
    """Replace the API key and anything shaped like a secret."""
    if key:
        text = text.replace(key, REDACTED)
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_state(value, key=None):
    """redact() every string inside a JSON-shaped value."""
    if isinstance(value, str):
        return redact(value, key)
    if isinstance(value, list):
        return [redact_state(item, key) for item in value]
    if isinstance(value, dict):
        return {name: redact_state(item, key) for name, item in value.items()}
    return value


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _valid_answers(answers, questions):
    """Every question has an answer of its own type with usable numbers."""
    if not isinstance(answers, dict):
        return False
    for qid, question in questions.items():
        answer = answers.get(qid)
        if not isinstance(answer, dict) or answer.get("type") != question.get("type"):
            return False
        if question.get("type") == "noul" and not (_finite(answer.get("noul")) and 0 <= answer["noul"] <= 1):
            return False
        if question.get("type") == "score" and not (_finite(answer.get("score")) and _finite(answer.get("confidence"))):
            return False
    return True


def ask(state, questions, key, send, sleep=time.sleep):
    """Send one request. Returns {"ok": True, "answers"} or {"ok": False, "reason"[, "detail"]}.

    send(body) returns (status, text), raises TimeoutError or socket.timeout on
    a timeout, and raises OSError on any other connection failure.
    """
    key = (key or "").strip()
    if not key:
        return {"ok": False, "reason": "no-key"}
    body = {"model": MODEL, "state": redact_state(state, key), "questions": questions}
    for attempt in (1, 2):
        try:
            status, text = send(body)
        except (socket.timeout, TimeoutError):
            return {"ok": False, "reason": "timeout"}
        except OSError as error:
            return {"ok": False, "reason": "network", "detail": redact(str(error), key)[:300]}
        except Exception as error:
            return {"ok": False, "reason": "network", "detail": redact(str(error), key)[:300]}
        if status in RETRY_STATUSES and attempt == 1:
            sleep(RETRY_DELAY_SECONDS)
            continue
        if status != 200:
            return {"ok": False, "reason": "http-%d" % status, "detail": redact(text, key)[:300]}
        try:
            answers = json.loads(text).get("answers")
        except (ValueError, AttributeError):
            return {"ok": False, "reason": "bad-response"}
        if not _valid_answers(answers, questions):
            return {"ok": False, "reason": "bad-response"}
        return {"ok": True, "answers": answers}


def make_sender(key, timeout=TIMEOUT_SECONDS, opener=None):
    """Return send(body) for ask(), posting to the live endpoint.

    With no opener, urllib.request.urlopen is looked up on each call rather
    than bound here, so a test that patches it really does stop the request.
    """

    key = (key or "").strip()

    def send(body):
        open_url = opener or urllib.request.urlopen
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        )
        try:
            with open_url(request, timeout=timeout) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            try:
                text = error.read().decode("utf-8", "replace")
            except Exception:
                text = ""
            return error.code, text
        except urllib.error.URLError as error:
            if isinstance(error.reason, (socket.timeout, TimeoutError)):
                raise TimeoutError() from None
            raise OSError(str(error.reason)) from None
        except (http.client.HTTPException, ValueError) as error:
            raise OSError(str(error)) from None

    return send
