#!/usr/bin/env python3
"""Verify public CI evidence for the pinned binary and inventory its source inputs.

This verifies technical provenance; it does not grant license/release approval.
The downloaded trace is data. No command from the trace is executed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import os
import subprocess

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "compliance/vlckit-build-evidence.json"
ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
PREFIX = re.compile(r"^\S+ \d\d[OE]\+? ")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(path, *args):
    return subprocess.check_output(
        ["git", "-C", str(path), *args], text=True
    ).strip()


def read_log(path, record):
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == record["raw_log_sha256"],
            "Build log checksum differs from the retained public CI record")
    return [PREFIX.sub("", ANSI.sub("", line)) for line in raw.decode().splitlines()]


def platform_block(lines, argument):
    marker = "$ ./compileAndBuildVLCKit.sh " + argument
    starts = [i for i, line in enumerate(lines) if line == marker]
    require(len(starts) == 1, "Expected exactly one platform build command: " + marker)
    start = starts[0]
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("$ ./compileAndBuildVLCKit.sh ")), len(lines))
    return lines[start:end]


def inventory(block, source):
    packages = []
    for i, line in enumerate(block):
        if line == "To-be-built packages:":
            table = []
            for row in block[i + 1:]:
                if not row.startswith("  "):
                    break
                table.extend(row.split())
            require(table, "Empty contrib build list")
            packages.append(sorted(table))
    require(packages and all(p == packages[0] for p in packages),
            "Missing or differing contrib lists across platform architectures")
    text = "\n".join(block)
    sources = {}
    for line in block:
        match = re.search(r'grep -- " ([^" ]+)\$" "\.\./src/([^/]+)/SHA512SUMS"', line)
        if not match:
            continue
        filename, component = match.groups()
        require(Path(filename).name == filename and Path(component).name == component,
                "Invalid source input name")
        checksums = (source / "contrib/src" / component / "SHA512SUMS").read_text()
        checksum = next((row.split()[0] for row in checksums.splitlines()
                         if row.split() and row.split()[-1] == filename), None)
        require(checksum and len(checksum) == 128, "Missing source SHA512: " + filename)
        require(re.search(re.escape(checksum) + r"\s+" + re.escape(filename), text)
                and filename + ": OK" in text, "No successful source check: " + filename)
        fetch = next((row for row in block if '--output "../tarballs/' + filename + '"' in row), "")
        sources[component] = {
            "filename": filename, "sha512": checksum,
            "urls": re.findall(r'-- "(https://[^" ]+)"', fetch),
            "evidence": "CI SHA512 check against patched VLC recipe",
        }
    # Git contribs use commit checks rather than release-archive SHA512SUMS.
    for component in (set(packages[0]) - set(sources) - {"meson-machinefile"}):
        recipe = (source / "contrib/src" / component / "rules.mak").read_text()
        revisions = re.findall(r"(?:HASH|GITVERSION|VERSION)\s*:=\s*([0-9a-f]{40})", recipe)
        require(len(revisions) == 1, "Unresolved Git source input: " + component)
        revision = revisions[0]
        check = next((line for line in block if 'test "$h" = "' + revision + '"' in line), "")
        archive = re.search(r"([^/\s]+-" + revision + r"\.tar\.xz)", check)
        require(archive, "No CI Git revision check: " + component)
        filename = archive[1]
        fetch = next((line for line in block if 'git archive --prefix="' + filename[:-7] + '/"' in line), "")
        remote = re.search(r'git remote add origin "(https://[^" ]+)"', fetch)
        require(remote and '--format=tar "' + revision + '"' in fetch,
                "No exact Git archive creation: " + component)
        sources[component] = {
            "filename": filename, "git_revision": revision, "git_url": remote[1],
            "evidence": "CI Git archive and exact commit check",
        }
    return {"build_packages": packages[0], "sources": dict(sorted(sources.items())),
            "scope": "Build inputs, including tools/headers; not a claim every component remains in the linked binary"}


def verify(log_path, vlckit, vlc, platform, record_path=RECORD, check_metadata=False):
    record = json.loads(record_path.read_text())
    target = "EPTVMac" if platform == "macos" else "EPTVTV"
    with (Path(os.environ.get("EPTV_APP_ROOT", str(ROOT))) / f"apps/apple/{target}/Sources/{target}/ComplianceMetadata.plist").open("rb") as handle:
        metadata = plistlib.load(handle)
    for field, key in (("VLCKitRevision", "distribution_revision"),
                       ("VLCKitArtifactSHA256", "artifact_sha256"),
                       ("VLCPatchedTreeSHA", "vlc_patched_tree"),
                       ("VLCKitBuildScriptVLCRevision", "vlc_base_revision")):
        if check_metadata:
            require(metadata[field] == record[key], "Stale build evidence: " + field)
    if check_metadata:
        require(metadata["LibVLCVersion"] == record["platforms"][platform]["fingerprint"],
                "Stale platform fingerprint")
    require(git(vlckit, "rev-parse", "HEAD") == record["distribution_revision"],
            "VLCKit checkout differs from the distribution revision")
    require(git(vlc, "rev-parse", "HEAD^{tree}") == record["vlc_patched_tree"],
            "VLC checkout differs from the patched tree")
    for checkout in (vlckit, vlc):
        require(not git(checkout, "status", "--porcelain", "--untracked-files=no"),
                "Tracked source files are modified: " + str(checkout))
    changes = git(vlckit, "diff", "--name-only", record["build_revision"],
                  record["distribution_revision"]).splitlines()
    require(sorted(changes) == ["Package.swift", "Packaging/podspecs/VLCKit.podspec"],
            "Distribution and CI build differ beyond package manifests")
    build_script = git(vlckit, "show", record["build_revision"] + ":compileAndBuildVLCKit.sh")
    pin = re.search(r'^TESTEDHASH="([0-9a-f]+)"', build_script, re.MULTILINE)
    require(pin and record["vlc_base_revision"].startswith(pin[1]), "Wrong CI VLC base pin")
    require("git am ${ROOT_DIR}/libvlc/patches/*.patch" in build_script, "Changed patch application")
    lines = read_log(log_path, record)
    require(any("Checking out " + record["build_revision"][:8] + " as detached HEAD" in line for line in lines),
            "CI checkout revision absent")
    checksum_lines = [line for line in lines if line.startswith("[Package] SPM zip checksum: ")]
    require(checksum_lines == ["[Package] SPM zip checksum: " + record["artifact_sha256"]],
            "CI output artifact checksum differs")
    require(lines[-1] == "Job succeeded", "CI job did not succeed")
    block = platform_block(lines, record["platforms"][platform]["build_argument"])
    require(any("Version control:" in line and record["platforms"][platform]["fingerprint"] in line
                for line in block), "CI platform fingerprint differs")
    expected_subjects = git(vlc, "log", "--reverse", "--format=%s",
                            record["vlc_base_revision"] + "..HEAD").splitlines()
    actual_subjects = [line[len("Applying: "):] for line in block if line.startswith("Applying: ")]
    require(len(expected_subjects) == 17 and actual_subjects == expected_subjects,
            "CI patch application differs from the reconstructed source history")
    inputs = inventory(block, vlc)
    return {"schema_version": 1, "platform": platform, "result": "VERIFIED_BINARY_SOURCE_ASSOCIATION",
            "record": record, "inputs": inputs,
            "limits": "License review, distribution rights, export classification and signed-app acceptance remain separate."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-log", type=Path, required=True)
    parser.add_argument("--vlckit-source", type=Path, required=True)
    parser.add_argument("--vlc-source", type=Path, required=True)
    parser.add_argument("--platform", choices=("macos", "tvos"), default="macos")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-app-metadata", action="store_true")
    args = parser.parse_args()
    try:
        report = verify(args.build_log, args.vlckit_source, args.vlc_source, args.platform,
                        check_metadata=args.check_app_metadata)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, "VLC build verification failed: " + str(error) + "\n")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS {args.platform}: exact CI artifact checksum, source revision, patched tree, fingerprint and contrib inputs")


if __name__ == "__main__":
    main()
