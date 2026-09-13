#!/usr/bin/env python3
"""OpenCore Studio — Desktop Application Server.

Provides a unified REST API and serves the dark-mode OpenCore Studio GUI.
Requires no external pip dependencies (runs on pure Python 3.9+).
"""

from __future__ import annotations

import base64
import json
import mimetypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from engine.efi_builder import assemble_efi, efi_zip_path, last_manifest
from engine.bootstrap import choose_first_open, prepare_first_open
from engine.paths import work_dir
from engine.macos_catalog import list_macos_installers
from engine.macos_downloader import cancel_download, download_status, remove_partial, start_download
from engine.hardware import gpu_apply_plan, list_gpus, match_cpu, match_gpu
from engine.kext_manager import (
    add_custom_repo,
    load_kext_catalog,
    load_repos_config,
)
from engine.plist_builder import build_config_plist
from engine.plist_importer import import_config_bytes, import_config_plist, import_pending_plist
from engine.profiles import (
    get_profile,
    import_profile_from_json,
    import_profile_from_url,
    list_profiles,
)
from engine.smbios import generate_smbios
from engine.updater import apply_updates, check_updates, local_status, rollback_updates
from engine.usb_writer import copy_efi_to_volume, list_usb_targets, prepare_usb_and_copy
from engine.validator import validate_config

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


class OpenCoreStudioHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _send_json(self, data: any, status: int = 200) -> None:
        def _json_default(obj):
            if isinstance(obj, (bytes, bytearray)):
                return obj.hex()
            return str(obj)

        payload = json.dumps(data, indent=2, default=_json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def _send_file(self, path: Path, download_name: str, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/profiles":
            profiles = list_profiles()
            self._send_json({"success": True, "profiles": profiles})
            return

        if path.startswith("/api/profiles/"):
            pid = path[len("/api/profiles/"):]
            p = get_profile(pid)
            if p:
                self._send_json({"success": True, "profile": p})
            else:
                self._send_json({"success": False, "error": f"Profile '{pid}' not found"}, status=404)
            return

        if path == "/api/kexts":
            catalog = load_kext_catalog()
            self._send_json({"success": True, "kexts": catalog})
            return

        if path == "/api/gpus":
            self._send_json({"success": True, "gpus": list_gpus()})
            return

        if path == "/api/hardware/match":
            qs = parse_qs(parsed.query)
            cpu_q = (qs.get("cpu") or qs.get("q") or [""])[0]
            gpu_q = (qs.get("gpu") or [""])[0]
            payload = {"success": True}
            if cpu_q:
                payload["cpu"] = match_cpu(cpu_q)
            if gpu_q:
                payload["gpu"] = match_gpu(gpu_q)
            if not cpu_q and not gpu_q:
                payload = {"success": False, "error": "Pass ?cpu=W-2133 and/or ?gpu=RX+6800+XT"}
            self._send_json(payload)
            return

        if path == "/api/repos":
            repos = load_repos_config()
            self._send_json({"success": True, "data": repos})
            return

        if path == "/api/updates/status":
            refresh = parse_qs(parsed.query).get("refresh", ["0"])[0] in ("1", "true", "yes")
            try:
                self._send_json(check_updates() if refresh else local_status())
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/macos/catalog":
            refresh = parse_qs(parsed.query).get("refresh", ["0"])[0] in ("1", "true", "yes")
            try:
                self._send_json(list_macos_installers(refresh=refresh))
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/macos/download/status":
            try:
                self._send_json(download_status())
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/efi/status":
            self._send_json(last_manifest())
            return

        if path == "/api/efi/targets":
            try:
                self._send_json(list_usb_targets())
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/efi/download":
            zip_path = efi_zip_path()
            if not zip_path:
                self._send_json({"success": False, "error": "No EFI zip yet. Build first."}, status=404)
                return
            self._send_file(zip_path, "OpenCore-Studio-EFI.zip", "application/zip")
            return

        if path == "/api/bootstrap":
            force = parse_qs(parsed.query).get("force", ["0"])[0] in ("1", "true", "yes")
            try:
                self._send_json(prepare_first_open(force=force))
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/plist/export":
            export_path = work_dir() / "export-config.plist"
            if not export_path.exists():
                self._send_json({"success": False, "error": "No plist staged. Export again."}, status=404)
                return
            self._send_file(export_path, "config.plist", "application/x-plist")
            return

        if path == "/api/plist/pending-import":
            try:
                res = import_pending_plist()
                self._send_json(res, status=200 if res.get("success") else 400)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=400)
            return

        if path == "/api/schema":
            try:
                self._send_json(local_status())
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        # Default: serve static web frontend
        if path == "/" or not path or path == "/index.html":
            self.path = "/index.html"
            return super().do_GET()

        file_path = STATIC_DIR / path.lstrip("/")
        if file_path.exists() and file_path.is_file():
            return super().do_GET()

        # Fallback to index.html for SPA routing
        self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/generate-smbios":
            body = self._read_json_body()
            model = body.get("model", "iMac20,1")
            smbios_data = generate_smbios(model)
            self._send_json({"success": True, "smbios": smbios_data})
            return

        if path == "/api/build-plist":
            body = self._read_json_body()
            try:
                pl, xml_str = build_config_plist(body)
                val_results = validate_config(pl, body.get("hardwareInfo", {}))
                self._send_json({
                    "success": True,
                    "xml": xml_str,
                    "validation": val_results,
                    "kextCount": len(pl.get("Kernel", {}).get("Add", [])),
                    "ssdtCount": len(pl.get("ACPI", {}).get("Add", [])),
                    "patchCount": len(pl.get("Kernel", {}).get("Patch", []))
                })
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/validate":
            body = self._read_json_body()
            config_dict = body.get("config", {})
            hw_info = body.get("hardwareInfo", {})
            results = validate_config(config_dict, hw_info)
            self._send_json({"success": True, "validation": results})
            return

        if path == "/api/repos":
            body = self._read_json_body()
            try:
                res = add_custom_repo(body)
                self._send_json(res, status=200 if res.get("success") else 400)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=400)
            return

        if path == "/api/updates/apply":
            body = self._read_json_body()
            try:
                res = apply_updates(
                    components=body.get("components"),
                    opencore_tag=body.get("opencoreTag") or body.get("tag"),
                )
                self._send_json(res, status=200 if res.get("success") else 400)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/updates/rollback":
            try:
                res = rollback_updates()
                self._send_json(res, status=200 if res.get("success") else 400)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/import-plist":
            body = self._read_json_body()
            xml_text = body.get("xml") or body.get("plist") or ""
            b64 = body.get("b64") or body.get("base64") or ""
            try:
                if b64:
                    self._send_json(import_config_bytes(base64.b64decode(b64)))
                    return
                if not xml_text:
                    self._send_json({"success": False, "error": "Provide a config.plist."}, status=400)
                    return
                self._send_json(import_config_plist(xml_text))
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=400)
            return

        if path == "/api/plist/export":
            body = self._read_json_body()
            xml_text = body.get("xml") or body.get("plist") or ""
            if not xml_text:
                self._send_json({"success": False, "error": "Provide plist XML in 'xml'."}, status=400)
                return
            export_path = work_dir() / "export-config.plist"
            export_path.write_text(xml_text, encoding="utf-8")
            self._send_json({"success": True, "download": "/api/plist/export"})
            return

        if path == "/api/bootstrap":
            body = self._read_json_body()
            try:
                res = choose_first_open(body.get("opencoreTag") or body.get("tag") or "")
                self._send_json(res, status=200 if res.get("success") else 400)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/macos/download":
            body = self._read_json_body()
            try:
                res = start_download(body.get("id") or body.get("installerId") or "")
                self._send_json(res, status=200 if res.get("success") else 400)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/macos/download/cancel":
            try:
                self._send_json(cancel_download())
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/macos/download/remove":
            body = self._read_json_body()
            try:
                res = remove_partial(body.get("id") or body.get("installerId") or "")
                self._send_json(res, status=200 if res.get("success") else 400)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/efi/build":
            body = self._read_json_body()
            try:
                self._send_json(assemble_efi(body))
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/efi/copy":
            body = self._read_json_body()
            mount = body.get("mountPoint") or body.get("volume") or ""
            try:
                res = copy_efi_to_volume(mount)
                self._send_json(res, status=200 if res.get("success") else 400)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/efi/prepare":
            body = self._read_json_body()
            try:
                res = prepare_usb_and_copy(body.get("device") or "", body.get("confirm") or "")
                self._send_json(res, status=200 if res.get("success") else 400)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        if path == "/api/gpu/apply-plan":
            body = self._read_json_body()
            self._send_json(gpu_apply_plan(body.get("gpuId") or ""))
            return

        if path == "/api/profiles/import":
            body = self._read_json_body()
            url = body.get("url")
            raw_json = body.get("json")
            try:
                if url:
                    res = import_profile_from_url(url)
                elif raw_json:
                    res = import_profile_from_json(raw_json)
                else:
                    res = {"success": False, "error": "Either 'url' or 'json' must be provided."}
                self._send_json(res, status=200 if res.get("success") else 400)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=400)
            return

        self._send_json({"success": False, "error": "Not Found"}, status=404)


def run(host: str = "127.0.0.1", port: int = 8088):
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), OpenCoreStudioHandler)
    print(f"===========================================================")
    print(f"  OpenCore Studio Desktop Engine running at:")
    print(f"  --> http://{host}:{port}/")
    print(f"===========================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down OpenCore Studio.")
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OpenCore Studio Desktop Engine")
    parser.add_argument("--host", default="0.0.0.0", help="Binding host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8088, help="Binding port (default: 8088)")
    args = parser.parse_args()
    run(host=args.host, port=args.port)
