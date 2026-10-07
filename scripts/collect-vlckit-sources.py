#!/usr/bin/env python3
"""Collect checksummed source inputs from the verified VLCKit CI record.

Includes build tools and headers conservatively. Output is a private review
package until the separate license and distribution decisions are complete.
"""
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request

spec = importlib.util.spec_from_file_location("build_evidence", Path(__file__).with_name("verify-vlckit-build.py"))
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


def digest(path, algorithm):
    h = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(root, component, item):
    item = dict(item)
    path = root / item["filename"]
    if "git_revision" in item:
        checkout = root / "git" / component
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        def run(*args):
            return subprocess.check_output(["git", "-C", str(checkout), *args], env=env)
        if not (checkout / ".git").exists():
            checkout.mkdir(parents=True, exist_ok=True)
            run("init", "-q")
            run("remote", "add", "origin", item["git_url"])
        revision = item["git_revision"]
        probe = subprocess.run(["git", "-C", str(checkout), "cat-file", "-e", revision],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        if probe.returncode:
            run("fetch", "-q", "--depth=1", "origin", revision)
        evidence.require(run("rev-parse", revision).decode().strip() == revision, "Wrong Git source revision")
        archive = run("archive", "--format=tar", "--prefix=" + path.name[:-7] + "/", revision)
        path.write_bytes(lzma.compress(archive))
        item["tree"] = run("rev-parse", revision + "^{tree}").decode().strip()
        item["retrieved_from"] = item["git_url"]
    else:
        if not path.exists() or digest(path, "sha512") != item["sha512"]:
            errors = []
            mirror = "https://downloads.videolan.org/pub/contrib/" + component + "/" + path.name
            for url in dict.fromkeys([mirror, *item["urls"]]):
                temporary = path.with_suffix(path.suffix + ".incomplete")
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": "EPTV-source-audit/1.0"})
                    with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as output:
                        for chunk in iter(lambda: response.read(1024 * 1024), b""):
                            output.write(chunk)
                    evidence.require(digest(temporary, "sha512") == item["sha512"], "Source SHA512 mismatch")
                    temporary.replace(path)
                    item["retrieved_from"] = url
                    break
                except Exception as error:
                    errors.append(str(error))
                finally:
                    temporary.unlink(missing_ok=True)
            else:
                raise ValueError(component + ": " + "; ".join(errors))
        item["retrieved_from"] = item.get("retrieved_from", "verified local cache")
    item.update(sha256=digest(path, "sha256"), bytes=path.stat().st_size)
    return component, item


def licenses(root, component, filename):
    result = []
    with tarfile.open(root / filename) as archive:
        for member in archive:
            relative = Path(*Path(member.name).parts[1:])
            if not member.isfile() or member.size > 512 * 1024 or ".." in relative.parts:
                continue
            name = relative.name.lower()
            if not any(word in name for word in ("copying", "copyright", "license", "licence", "notice", "patent")) \
                    and str(relative) not in ("docs/FTL.TXT", "README.ijg", "doc/readme.html"):
                continue
            content = archive.extractfile(member).read()
            target = root / "licenses" / component / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            result.append({"path": str(relative), "sha256": hashlib.sha256(content).hexdigest()})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-log", type=Path, required=True)
    parser.add_argument("--vlckit-source", type=Path, required=True)
    parser.add_argument("--vlc-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = {platform: evidence.verify(args.build_log, args.vlckit_source, args.vlc_source, platform)
               for platform in ("macos", "tvos")}
    sources = {}
    for report in reports.values():
        for component, item in report["inputs"]["sources"].items():
            evidence.require(component not in sources or sources[component] == item,
                             "Platform source inputs disagree: " + component)
            sources[component] = item
    args.output.mkdir(parents=True, exist_ok=True)
    results, errors = {}, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(collect, args.output, component, item): component
                   for component, item in sorted(sources.items())}
        for future in concurrent.futures.as_completed(futures):
            component = futures[future]
            try:
                _, item = future.result()
                item["license_files"] = licenses(args.output, component, item["filename"])
                results[component] = item
                print(component + ": source verified", flush=True)
            except Exception as error:
                errors[component] = str(error)
                print(component + ": FAILED", flush=True)
    manifest = {"schema_version": 1, "status": "SOURCE_INPUTS_VERIFIED" if not errors else "INCOMPLETE",
                "build_record": reports["macos"]["record"],
                "platform_inputs": {p: r["inputs"]["build_packages"] for p, r in reports.items()},
                "sources": dict(sorted(results.items())), "errors": errors,
                "license_review": "GPL_COMPONENT_REMEDIATION_REQUIRED",
                "limits": "Source verification does not approve license/distribution terms; tools/headers are included."}
    (args.output / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if errors:
        parser.exit(1, "Source collection incomplete: " + json.dumps(errors) + "\n")
    print(f"Verified {len(results)} exact source inputs; license review remains separate.")


if __name__ == "__main__":
    main()
