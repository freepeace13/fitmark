#!/usr/bin/env python3
"""Find the Fitmark workspace and work out every path a skill reads or writes.

Standard library only. Prints JSON. Exit 0 on success, 1 with a JSON error, 2 on bad usage.
The workspace is never allowed inside the plugin root or plugin data folder.
"""

import argparse
import contextlib
import datetime
import itertools
import json
import os
import re
import stat
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

MARKER = "fitmark.yaml"
REMEMBERED = "workspace.json"  # in the plugin data folder: which folder was chosen at first use
DEFAULT_WORKSPACE = "~/Fitmark"
SCRIPT_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
STATUSES = ("intake", "spec_sent", "confirmed", "on_hold", "filled", "closed")
CLOSED_STATUSES = ("filled", "closed")
LOCK_FILE = ".job.lock"
LOCK_WAIT_SECONDS = 10
LOCK_STALE_SECONDS = 60
SUBMITTAL_FILE = re.compile(r"submittal-s(\d+)(?:-\d+)?\.json")


class FitmarkError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class JsonParser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({"error": message, "code": "usage"}))
        sys.exit(2)


def slug(text, what="name"):
    plain = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in plain if not unicodedata.combining(c)).casefold()
    # Symbols that tell names apart become words: C++, C# and C must not share a folder.
    plain = re.sub(r"(?<=[\w+])\+", "-plus-", plain)
    plain = re.sub(r"(?<=\w)#", "-sharp-", plain)
    plain = re.sub(r"(?<![\w.])\.(?=\w)", "dot-", plain)
    plain = re.sub(r"(?<=\w)\s*&\s*(?=\w)", "-and-", plain)
    result = re.sub(r"[\W_]+", "-", plain).strip("-")
    if not result:
        raise FitmarkError("bad_name", f"{what} {text!r} has no letters or digits")
    return result


def readable(text):
    """Make text safe to use inside one file name, keeping it readable."""
    return re.sub(r"[/\\:\x00-\x1f]+", "-", text).strip()


def is_set(value):
    return bool(value) and not value.startswith("${")


def full_path(value):
    return Path(os.path.expanduser(value)).resolve()


def guard(path, args):
    """Refuse any path inside the plugin root or plugin data folder."""
    protected = [SCRIPT_PLUGIN_ROOT]
    protected += [full_path(v) for v in (args.plugin_root, args.plugin_data) if is_set(v)]
    for folder in protected:
        if path == folder or folder in path.parents:
            raise FitmarkError(
                "inside_plugin", f"{path} is inside the plugin folder {folder}; choose another"
            )
    return path


def setting_text(args):
    return str(full_path(args.workspace)) if is_set(args.workspace) else ""


def remember_workspace(root, args):
    """Save the folder chosen at first use so later sessions find it. Returns whether it saved."""
    if not is_set(args.plugin_data):
        return False
    folder = full_path(args.plugin_data)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        write_atomic(
            folder / REMEMBERED, json.dumps({"root": str(root), "setting": setting_text(args)})
        )
    except OSError:
        return False
    return True


def remembered_workspace(args):
    """Return the remembered folder, unless it is gone or the folder setting has since changed."""
    if not is_set(args.plugin_data):
        return None
    try:
        saved = json.loads((full_path(args.plugin_data) / REMEMBERED).read_text(encoding="utf-8"))
        root, setting = full_path(saved["root"]), saved["setting"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if setting != setting_text(args) or not (root / MARKER).is_file():
        return None
    return guard(root, args)


def find_workspace(args):
    """Return (root, found_by, suggested_path). Root is None when there is no workspace."""
    setting = guard(full_path(args.workspace), args) if is_set(args.workspace) else None
    if setting and (setting / MARKER).is_file():
        return setting, "setting", None
    start = Path.cwd().resolve()
    for folder in (start, *start.parents):
        if (folder / MARKER).is_file():
            return guard(folder, args), "marker", None
    remembered = remembered_workspace(args)
    if remembered:
        return remembered, "saved", None
    if setting:
        return None, None, setting
    default = guard(full_path(DEFAULT_WORKSPACE), args)
    if (default / MARKER).is_file():
        return default, "default", None
    return None, None, default


def require_workspace(args):
    root, _, suggested = find_workspace(args)
    if root is None:
        raise FitmarkError("no_workspace", f"No Fitmark workspace. Suggested path: {suggested}")
    return root


def file_mode(path):
    """Keep the mode of a file being replaced; a new file gets the normal one for this user."""
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        return 0o666 & ~umask


def write_atomic(path, text):
    # mkstemp makes the file private to this user, which would lock out a shared workspace.
    handle, temp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.chmod(temp, file_mode(path))
        os.replace(temp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp)
        raise


@contextlib.contextmanager
def job_lock(job_file):
    """Let one process at a time read, change and replace a job file."""
    lock = job_file.parent / LOCK_FILE
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            with contextlib.suppress(FileNotFoundError):
                if time.time() - lock.stat().st_mtime > LOCK_STALE_SECONDS:
                    lock.unlink()
                    continue
            if time.monotonic() > deadline:
                raise FitmarkError(
                    "job_locked", f"{job_file} is being changed by another run; try again"
                ) from None
            time.sleep(0.02)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock.unlink()


def job_problem(job):
    """Return what is wrong with a parsed job file, or None. Keeps the script dependency-free."""
    if not isinstance(job, dict):
        return "it is not a job object"
    for key in ("spec_id", "client", "client_slug", "job_slug", "role", "status"):
        if not isinstance(job.get(key), str) or not job[key]:
            return f"{key} must be text"
    if not re.search(r"\w", job["client"]):
        return "client has no letters or digits"
    version = job.get("current_spec_version")
    if not isinstance(version, int) or isinstance(version, bool):
        return "current_spec_version must be a number"
    submittals = job.get("submittals")
    if not isinstance(submittals, list):
        return "submittals must be a list"
    for item in submittals:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("candidate"), str)
            or not isinstance(item.get("file"), str)
            or not isinstance(item.get("spec_version"), int)
        ):
            return "a submittal entry is incomplete"
    return None


def read_job(path):
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise FitmarkError("bad_job_file", f"{path} cannot be read: {error}") from error
    problem = job_problem(job)
    if problem:
        raise FitmarkError("bad_job_file", f"{path} cannot be read: {problem}")
    return job


def write_job(path, job):
    # JSON is valid YAML, so job.yaml needs no YAML library. Only scripts write this file.
    write_atomic(path, json.dumps(job, indent=2, ensure_ascii=False) + "\n")


def all_jobs(root, unreadable=None):
    """Yield every readable job. One bad file must not stop work on the others."""
    for path in sorted((root / "clients").glob("*/*/job.yaml")):
        try:
            yield path, read_job(path)
        except FitmarkError as error:
            if unreadable is not None:
                unreadable.append({"path": str(path), "error": str(error)})


def find_job(root, spec_id):
    unreadable = []
    for path, job in all_jobs(root, unreadable):
        if job["spec_id"] == spec_id:
            return path, job
    note = f"; could not read {', '.join(u['path'] for u in unreadable)}" if unreadable else ""
    raise FitmarkError("unknown_job", f"No job with spec_id {spec_id}{note}")


def match_names(text):
    inline = re.search(r"^match:\s*\[(.*)\]\s*$", text, re.M)
    if inline:
        items = re.findall(r"\"[^\"]*\"|'[^']*'|[^,\s][^,]*", inline[1])
    else:
        block = re.search(r"^match:\s*\n((?:[ \t]*-[ \t]*.+\n?)+)", text, re.M)
        items = re.findall(r"-[ \t]*(.+)", block[1]) if block else []
    return [item.strip().strip("\"'") for item in items if item.strip()]


def rule_slugs(path):
    """Return the client slugs one rule file matches, ignoring anything unusable in it."""
    try:
        names = match_names(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return []
    slugs = []
    for name in names:
        with contextlib.suppress(FitmarkError):
            slugs.append(slug(name, "client"))
    return slugs


def client_slug(root, name):
    wanted = slug(name, "client")
    for path in sorted((root / "agency" / "clients").glob("*.yaml")):
        if wanted == path.stem or wanted in rule_slugs(path):
            return path.stem
    return wanted


def matching_job(root, client, role, client_name):
    """Find a job by what the client's rules say now, so a later rule doesn't orphan it."""
    jobs = [
        (path, job)
        for path, job in all_jobs(root)
        if job["job_slug"] == role and client_slug(root, job["client"]) == client
    ]
    # If a rule has joined two folders, the job created under this exact name comes first.
    wanted = slug(client_name, "client")
    jobs.sort(key=lambda item: slug(item[1]["client"], "client") != wanted)
    return jobs[0] if jobs else (None, None)


def saved_versions(job_dir):
    versions = []
    for path in (job_dir / "spec").glob("v*/spec.json"):
        number = path.parent.name[1:]
        if number.isdigit():
            versions.append(int(number))
    return versions


def free_path(folder, stem, suffix, reserve=False):
    """Return folder/stem+suffix, adding -2, -3 and so on until nothing would be overwritten.

    With reserve, also create it empty, so a run happening at the same time gets another name.
    """
    for number in itertools.count(1):
        path = folder / (f"{stem}{suffix}" if number == 1 else f"{stem}-{number}{suffix}")
        if path.exists():
            continue
        if not reserve:
            return path
        try:
            os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return path
        except FileExistsError:
            continue


def cmd_init(args):
    root = guard(full_path(args.path), args)
    if root.exists() and not root.is_dir():
        raise FitmarkError("not_a_folder", f"{root} is a file")
    folders = [root / f for f in ("agency/brand", "agency/criteria", "agency/clients", "clients")]
    for folder in folders:
        guard(full_path(folder), args)
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
    marker = root / MARKER
    if marker.exists():
        return {"status": "exists", "root": str(root), "remembered": remember_workspace(root, args)}
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_atomic(
        marker,
        f"schema_version: 1\nagency: {json.dumps(args.agency, ensure_ascii=False)}\n"
        f'created_at: "{created}"\n',
    )
    return {"status": "created", "root": str(root), "remembered": remember_workspace(root, args)}


def cmd_resolve(args):
    root, found_by, suggested = find_workspace(args)
    if root is None:
        return {"status": "no_workspace", "suggested_path": str(suggested)}
    return {
        "status": "ok",
        "root": str(root),
        "found_by": found_by,
        "agency_dir": str(root / "agency"),
        "profile_exists": (root / "agency" / "profile.yaml").is_file(),
    }


def cmd_job(args):
    root = require_workspace(args)
    client = client_slug(root, args.client)
    role = slug(args.role, "role")
    found, found_job = matching_job(root, client, role, args.client)
    if found:
        client, spec_id, job_dir = found_job["client_slug"], found_job["spec_id"], found.parent
    else:
        spec_id = f"{client}-{role}"
        job_dir = root / "clients" / client / role
    job_file = job_dir / "job.yaml"

    for path, job in all_jobs(root):
        if job["spec_id"] == spec_id and path != job_file:
            raise FitmarkError("spec_id_clash", f"{spec_id} is already used by {path.parent}")

    version = max(saved_versions(guard(full_path(job_dir), args)), default=0) + 1
    spec_dir = job_dir / "spec" / f"v{version}"
    subfolders = [job_dir / "intake", job_dir / "spec", job_dir / "candidates"]
    for folder in (*subfolders, spec_dir):
        guard(full_path(folder), args)

    exists = job_file.is_file()
    job = read_job(job_file) if exists else None
    if args.create:
        for folder in subfolders:
            folder.mkdir(parents=True, exist_ok=True)
        spec_dir.mkdir(exist_ok=True)
        with job_lock(job_file):
            if job_file.is_file():
                exists, job = True, read_job(job_file)
            elif not exists:
                job = {
                    "spec_id": spec_id,
                    "client": args.client,
                    "client_slug": client,
                    "job_slug": role,
                    "role": args.role,
                    "status": "intake",
                    "current_spec_version": 0,
                    "submittals": [],
                }
                write_job(job_file, job)

    client_name = readable(job["client"] if job else args.client)
    role_name = readable(job["role"] if job else args.role)
    outputs = {
        "spec_json": str(spec_dir / "spec.json"),
        "spec_document": str(spec_dir / f"{client_name} – {role_name} – Job spec v{version}.docx"),
        "confirmation_email": str(spec_dir / "confirmation-email.txt"),
        "intake_dir": str(job_dir / "intake"),
        "job_yaml": str(job_file),
    }
    if version > 1:
        outputs["changes_from_previous"] = str(spec_dir / f"changes-from-v{version - 1}.md")
    for path in outputs.values():
        guard(full_path(path), args)
    return {
        "exists": exists,
        "client_slug": client,
        "job_slug": role,
        "spec_id": spec_id,
        "job_dir": str(job_dir),
        "current_spec_version": job["current_spec_version"] if job else 0,
        "next_spec_version": version,
        "outputs": outputs,
    }


def initials(name):
    return "".join(f"{word[0].upper()}." for word in name.split())


def same_name_folders(candidates, base):
    """Return the folders for everyone sharing this name: base, base-2, base-3, in order."""
    pattern = re.compile(re.escape(base) + r"(?:-(\d+))?")
    found = []
    for path in candidates.glob("*"):
        parsed = pattern.fullmatch(path.name)
        if parsed and path.is_dir():
            found.append((int(parsed[1] or 1), path))
    return [path for _, path in sorted(found)]


def has_content(folder):
    return any(path.is_file() and path.stat().st_size for path in folder.rglob("*"))


def choose_candidate_folder(args, candidates, base):
    folders = same_name_folders(candidates, base)
    names = [path.name for path in folders]
    if args.slug:
        if args.slug not in names:
            raise FitmarkError(
                "unknown_candidate", f"{args.slug} is not a folder for {args.name}: {names}"
            )
        return candidates / args.slug
    if args.new:
        # A retry must not make a third person: an unused -N folder is still free.
        if len(folders) > 1 and not has_content(folders[-1]):
            return folders[-1]
        return free_path(candidates, base, "")
    if len(folders) > 1:
        raise FitmarkError(
            "ambiguous_candidate",
            f"More than one person is called {args.name}: {', '.join(names)}. "
            "Say which with --slug, or use --new for someone else.",
        )
    return candidates / base


def cmd_candidate(args):
    root = require_workspace(args)
    job_file, job = find_job(root, args.job)
    version = job["current_spec_version"]
    if version < 1:
        raise FitmarkError("no_spec", f"{args.job} has no saved spec to assess against")

    base = slug(args.name, "candidate")
    candidates = job_file.parent / "candidates"
    guard(full_path(candidates), args)
    folder = choose_candidate_folder(args, candidates, base)
    title = readable(f"{initials(args.name)} – {job['role']} – {job['client']} v{version}")
    submittal = free_path(folder, f"submittal-s{version}", ".json")
    document = free_path(folder, title, ".docx")
    for path in (folder, folder / "source", submittal, document):
        guard(full_path(path), args)

    exists = folder.is_dir()
    if args.create:
        (folder / "source").mkdir(parents=True, exist_ok=True)
        submittal = free_path(folder, f"submittal-s{version}", ".json", reserve=True)
        document = free_path(folder, title, ".docx", reserve=True)
    return {
        "exists": exists,
        "slug": folder.name,
        "candidate_dir": str(folder),
        "source_dir": str(folder / "source"),
        "spec_version": version,
        "spec_json": str(job_file.parent / "spec" / f"v{version}" / "spec.json"),
        "submittal_path": str(submittal),
        "document_path": str(document),
    }


def record_spec(args, job_file, job):
    if args.version is None:
        raise FitmarkError("usage", "spec_saved needs --version")
    spec = job_file.parent / "spec" / f"v{args.version}" / "spec.json"
    if not spec.is_file():
        raise FitmarkError("missing_file", f"{spec} does not exist")
    job["current_spec_version"] = max(job["current_spec_version"], args.version)


def record_submittal(args, job_file, job):
    if not args.candidate or not args.file:
        raise FitmarkError("usage", "submittal_saved needs --candidate and --file")
    candidate = slug(args.candidate, "candidate")
    name = Path(args.file).name
    parsed = SUBMITTAL_FILE.fullmatch(name)
    if not parsed:
        raise FitmarkError("bad_file", f"{name} is not a submittal file name")
    saved = job_file.parent / "candidates" / candidate / name
    if not saved.is_file() or saved.stat().st_size == 0:
        raise FitmarkError("missing_file", f"{candidate}/{name} has not been written")
    if not any(s["candidate"] == candidate and s["file"] == name for s in job["submittals"]):
        job["submittals"].append(
            {
                "candidate": candidate,
                "spec_version": int(parsed[1]),
                "file": name,
                "date": datetime.date.today().isoformat(),
            }
        )


def record_status(args, job_file, job):
    if args.status not in STATUSES:
        raise FitmarkError("bad_status", f"Status must be one of {', '.join(STATUSES)}")
    job["status"] = args.status


RECORDERS = {
    "spec_saved": record_spec,
    "submittal_saved": record_submittal,
    "status": record_status,
}


def cmd_record(args):
    root = require_workspace(args)
    job_file, _ = find_job(root, args.job)
    with job_lock(job_file):
        job = read_job(job_file)
        RECORDERS[args.event](args, job_file, job)
        write_job(job_file, job)
    return {"job": job, "job_yaml": str(job_file)}


def stale_submittals(job):
    latest = {}
    for submittal in job["submittals"]:
        current = latest.get(submittal["candidate"])
        if current is None or submittal["spec_version"] >= current["spec_version"]:
            latest[submittal["candidate"]] = submittal
    return [
        {"candidate": s["candidate"], "spec_version": s["spec_version"], "file": s["file"]}
        for s in latest.values()
        if s["spec_version"] < job["current_spec_version"]
    ]


def cmd_status(args):
    root = require_workspace(args)
    wanted = client_slug(root, args.client) if args.client else None
    jobs = []
    unreadable = []
    for _, job in all_jobs(root, unreadable):
        if wanted and client_slug(root, job["client"]) != wanted:
            continue
        if args.open and job["status"] in CLOSED_STATUSES:
            continue
        jobs.append({**job, "stale_submittals": stale_submittals(job)})
    return {"root": str(root), "jobs": jobs, "unreadable_jobs": unreadable}


def build_parser():
    common = JsonParser(add_help=False)
    common.add_argument("--workspace", default="", help="the Fitmark folder setting")
    common.add_argument(
        "--workspace-stdin",
        action="store_true",
        help="read the folder setting from stdin, for values substituted into a command as text",
    )
    common.add_argument("--plugin-root", default="")
    common.add_argument("--plugin-data", default="")

    parser = JsonParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def add(name, handler):
        command = commands.add_parser(name, parents=[common])
        command.set_defaults(handler=handler)
        return command

    init = add("init", cmd_init)
    init.add_argument("--path", required=True)
    init.add_argument("--agency")

    add("resolve", cmd_resolve)

    job = add("job", cmd_job)
    job.add_argument("--client", required=True)
    job.add_argument("--role", required=True)
    job.add_argument("--create", action="store_true")

    candidate = add("candidate", cmd_candidate)
    candidate.add_argument("--job", required=True, help="spec_id")
    candidate.add_argument("--name", required=True)
    candidate.add_argument("--create", action="store_true")
    person = candidate.add_mutually_exclusive_group()
    person.add_argument(
        "--new", action="store_true", help="a different person who shares this name"
    )
    person.add_argument("--slug", help="which person, when several share this name")

    record = add("record", cmd_record)
    record.add_argument("--job", required=True, help="spec_id")
    record.add_argument("--event", required=True, choices=sorted(RECORDERS))
    record.add_argument("--version", type=int)
    record.add_argument("--candidate")
    record.add_argument("--file")
    record.add_argument("--status")

    status = add("status", cmd_status)
    status.add_argument("--client")
    status.add_argument("--open", action="store_true")
    return parser


def read_setting_from_stdin():
    value = sys.stdin.read().strip("\r\n")
    if "\n" in value:
        raise FitmarkError("bad_setting", "The Fitmark folder setting must be one line")
    return value


def main(argv=None):
    # Output is always UTF-8 JSON, whatever the locale.
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stdin.reconfigure(encoding="utf-8", errors="surrogateescape")
    args = build_parser().parse_args(argv)
    try:
        if args.workspace_stdin:
            args.workspace = read_setting_from_stdin()
        result = args.handler(args)
    except FitmarkError as error:
        print(json.dumps({"error": str(error), "code": error.code}, ensure_ascii=False))
        return 1
    except OSError as error:
        print(json.dumps({"error": str(error), "code": "os_error"}, ensure_ascii=False))
        return 1
    except UnicodeError as error:
        print(json.dumps({"error": str(error), "code": "bad_encoding"}, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    # Under a non-UTF-8 locale Python decodes arguments and paths with that locale, which can't
    # hold every name. Run again in UTF-8 mode, which covers all of them at once.
    if sys.getfilesystemencoding().lower() != "utf-8" and not sys.flags.utf8_mode:
        os.execv(sys.executable, [sys.executable, "-X", "utf8", *sys.argv])
    sys.exit(main())
