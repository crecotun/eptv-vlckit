#!/usr/bin/env python3
"""Read VLC module license declarations without executing the framework.

Fails on GPL module declarations, known GPL-only libzvbi entry points, or getters
that cannot be decoded. A pass is a focused binary check, not a complete license
review: transitive source notices and distribution rights are separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile

ZVBI_GPL_SYMBOLS = {
    "_vbi_decode_teletext_8301_cni", "_vbi_decode_teletext_8301_local_time",
    "_vbi_decode_teletext_8302_cni", "_vbi_decode_teletext_8302_pdc",
}
# The pinned VLC source declares GPL-2.0-or-later for these modules. Some
# distribution slices strip their license getters but retain their entry points.
GPL_MODULE_ENTRIES = {
    "logger_file", "logger_syslog", "video_filter_rotate",
    "services_discovery_libsap", "stream_out_cycle",
    "stream_out_libstream_out_rtp", "control_dummy",
}


def classify(declarations, symbols, unknown):
    gpl = {name: license for name, license in declarations.items()
           if "GNU General Public License" in license and "Lesser" not in license}
    entries = sorted(name for name in GPL_MODULE_ENTRIES
                     if "_vlc_entry__" + name in symbols)
    zvbi = sorted(ZVBI_GPL_SYMBOLS & symbols)
    status = ("BLOCKED_GPL_CODE" if gpl or entries or zvbi else
              "INCOMPLETE" if unknown or not declarations else "FOCUSED_CHECK_PASSED")
    return gpl, entries, zvbi, status


def arm64_constant_address(code, address):
    # These C getters return a constant string. Decode only the known compiler
    # sequence: optional BTI, ADRP X0, ADD X0/X0/imm, RET. Fail closed otherwise.
    if struct.unpack_from("<I", code)[0] == 0xD503245F:
        code, address = code[4:], address + 4
    adrp, add, ret = struct.unpack_from("<III", code)
    if adrp & 0x9F00001F != 0x90000000 or add & 0xFFC003FF != 0x91000000 or ret != 0xD65F03C0:
        raise ValueError("Unrecognized arm64 license getter")
    immediate = ((adrp >> 5) & 0x7FFFF) << 2 | ((adrp >> 29) & 3)
    if immediate & (1 << 20):
        immediate -= 1 << 21
    return (address & ~4095) + (immediate << 12) + ((add >> 10) & 0xFFF)


def x86_constant_address(code, address):
    # Optimized getters optionally retain the usual frame-pointer prologue.
    if code.startswith(b"\x55\x48\x89\xe5"):
        code, address = code[4:], address + 4
        ending = b"\x5d\xc3"
    else:
        ending = b"\xc3"
    if not code.startswith(b"\x48\x8d\x05") or code[7:7 + len(ending)] != ending:
        raise ValueError("Unrecognized x86_64 license getter")
    return address + 7 + struct.unpack_from("<i", code, 3)[0]


def identity(binary, architecture):
    """Cheap signing-independent identity; no symbols or license decoding."""
    with tempfile.TemporaryDirectory(prefix="eptv-vlc-identity-") as directory:
        thin = Path(directory) / "image"
        archs = subprocess.check_output(["lipo", "-archs", str(binary)], text=True).split()
        if architecture not in archs:
            raise ValueError("Framework has no " + architecture + " slice")
        if len(archs) == 1:
            data = binary.read_bytes()
        else:
            subprocess.run(["lipo", "-thin", architecture, str(binary), "-output", str(thin)], check=True)
            data = thin.read_bytes()
        if len(data) < 32 or struct.unpack_from("<I", data)[0] != 0xFEEDFACF:
            raise ValueError("Expected a little-endian 64-bit Mach-O image")
        sections, commands = hashlib.sha256(), hashlib.sha256()
        # Include CPU/type/flags, but ncmds/sizeofcmds change when signing.
        commands.update(data[4:16] + data[24:32])
        offset = 32
        linkedit_range, signature_offset = None, None
        for _ in range(struct.unpack_from("<I", data, 16)[0]):
            command, size = struct.unpack_from("<II", data, offset)
            if size < 8 or offset + size > len(data):
                raise ValueError("Invalid Mach-O load command")
            raw = bytearray(data[offset:offset + size])
            if command == 0x19:
                if raw[8:24].rstrip(b"\0") == b"__LINKEDIT":
                    linkedit_range = struct.unpack_from('<QQ', raw, 40)
                    # codesign resizes only the signature-bearing segment.
                    raw[32:40] = bytes(8)
                    raw[48:56] = bytes(8)
                for i in range(struct.unpack_from("<I", data, offset + 64)[0]):
                    section = offset + 72 + i * 80
                    length, start = struct.unpack_from("<QI", data, section + 40)
                    kind = struct.unpack_from("<I", data, section + 64)[0] & 255
                    if kind not in (1, 12, 18) and length:
                        if start + length > len(data):
                            raise ValueError("Mach-O section extends beyond the binary")
                        sections.update(data[section:section + 32])
                        sections.update(data[start:start + length])
            if command == 0x1d:
                signature_offset = struct.unpack_from("<I", raw, 8)[0]
            if command != 0x1d:  # LC_CODE_SIGNATURE changes on re-signing.
                commands.update(raw)
            offset += size
        linkedit = hashlib.sha256()
        if linkedit_range:
            start, length = linkedit_range
            end = signature_offset if signature_offset is not None else start + length
            if not start <= end <= len(data):
                raise ValueError("Invalid Mach-O linkedit/signature range")
            # Includes symbols, exports, relocations and dynamic binding data.
            linkedit.update(data[start:end])
        return {"sections_sha256": sections.hexdigest(),
                "load_commands_sha256": commands.hexdigest(),
                "linkedit_sha256": linkedit.hexdigest()}


def audit(binary, architecture):
    with tempfile.TemporaryDirectory(prefix="eptv-vlc-license-") as directory:
        thin = Path(directory) / (architecture + ".bin")
        archs = subprocess.check_output(["lipo", "-archs", str(binary)], text=True).split()
        if architecture not in archs:
            raise ValueError("Framework has no " + architecture + " slice")
        if len(archs) == 1:
            thin.write_bytes(binary.read_bytes())
        else:
            subprocess.run(["lipo", "-thin", architecture, str(binary), "-output", str(thin)], check=True)
        data = thin.read_bytes()
        if struct.unpack_from("<I", data)[0] != 0xFEEDFACF:
            raise ValueError("Expected a little-endian 64-bit Mach-O image")
        segments, offset = [], 32
        section_digest = hashlib.sha256()
        for _ in range(struct.unpack_from("<I", data, 16)[0]):
            command, size = struct.unpack_from("<II", data, offset)
            if command == 0x19:
                segments.append(struct.unpack_from("<QQQQ", data, offset + 24))
                for i in range(struct.unpack_from("<I", data, offset + 64)[0]):
                    section = offset + 72 + i * 80
                    section_size, start = struct.unpack_from("<QI", data, section + 40)
                    kind = struct.unpack_from("<I", data, section + 64)[0] & 255
                    if kind not in (1, 12, 18) and section_size:
                        if start + section_size > len(data):
                            raise ValueError("Mach-O section extends beyond the binary")
                        section_digest.update(data[section:section + 32])
                        section_digest.update(data[start:start + section_size])
            offset += size
        def file_offset(address):
            for vmaddr, _, fileoff, filesize in segments:
                if vmaddr <= address < vmaddr + filesize:
                    return address - vmaddr + fileoff
            raise ValueError("License string/code address is outside file-backed segments")
        symbols = {}
        for line in subprocess.check_output(["nm", "-n", str(thin)], text=True).splitlines():
            parts = line.split()
            if len(parts) == 3:
                symbols[parts[2]] = int(parts[0], 16)
        declarations, unknown = {}, []
        decode = arm64_constant_address if architecture == "arm64" else x86_constant_address
        def constant_string(address):
            getter = file_offset(address)
            constant = decode(data[getter:getter + 16], address)
            start = file_offset(constant)
            end = data.index(b"\0", start, start + 512)
            return data[start:end].decode()
        for name, address in symbols.items():
            if not name.startswith("_vlc_entry_license__"):
                continue
            try:
                declarations[name.split("__", 1)[1]] = constant_string(address)
            except (ValueError, struct.error):
                unknown.append(name)
        gpl, entries, zvbi, status = classify(declarations, set(symbols), unknown)
        return {"schema_version": 1, "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "sections_sha256": section_digest.hexdigest(),
                "runtime_changeset": constant_string(symbols["_libvlc_get_changeset"]),
                "runtime_version": constant_string(symbols["_libvlc_get_version"]),
                "audited_architecture": architecture, "module_declarations": declarations,
                "gpl_modules": gpl, "known_gpl_module_entries": entries,
                "gpl_zvbi_symbols": zvbi, "undecoded_getters": unknown,
                "status": status}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--architecture", choices=("all", "arm64", "x86_64"), default="all")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        architectures = (subprocess.check_output(["lipo", "-archs", str(args.binary)], text=True).split()
                         if args.architecture == "all" else [args.architecture])
        if set(architectures) - {"arm64", "x86_64"}:
            raise ValueError("Unsupported architecture in framework")
        slices = [audit(args.binary, architecture) for architecture in architectures]
        status = ("BLOCKED_GPL_CODE" if any(s["status"] == "BLOCKED_GPL_CODE" for s in slices) else
                  "INCOMPLETE" if any(s["status"] == "INCOMPLETE" for s in slices) else "FOCUSED_CHECK_PASSED")
        report = {"schema_version": 2, "status": status, "slices": slices}
    except (ValueError, KeyError, struct.error, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, "VLC license audit failed: " + str(error) + "\n")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    for slice in slices:
        print(f"{slice['audited_architecture']}: {slice['status']}: "
              f"{len(slice['module_declarations'])} module declarations, "
              f"{len(slice['known_gpl_module_entries'])} known GPL module entries, "
              f"{len(slice['gpl_zvbi_symbols'])} GPL teletext symbols")
    if report["status"] != "FOCUSED_CHECK_PASSED":
        parser.exit(2)


if __name__ == "__main__":
    main()
