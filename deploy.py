# Plugins/YourPlugin/Scripts/YourPlugin/deploy.py
import json
import os
import zipfile
from datetime import datetime
from logging import error

EXCLUDE_DIRS = {"Binaries", "Intermediate", "Saved", ".git", ".vs", "__pycache__", ".idea", "venv", "Dist", "deploy.py",
                "LICENSE", "README.md", "requirements.txt", ".gitignore","CLAUDE.md"}
EXCLUDE_EXTS = {".pdb", ".obj", ".exp", ".idb", ".log"}

PLUGIN_NAME = "ArrangingBlueprint"


def _project_dir() -> str:
    return "." + os.sep


def _plugin_root_from_this_file() -> str:
    here = os.path.abspath(__file__)
    plugin_root = os.path.dirname(here)  # .../Plugins/<PluginName>
    return plugin_root


def _read_uplugin(plugin_root: str) -> dict:
    uplugin_path = os.path.join(plugin_root, PLUGIN_NAME + ".uplugin")
    with open(uplugin_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _suggest_zip_name(plugin_name: str, version_name: str | None) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    vn = (version_name or "").strip().replace(" ", "")
    core = f"{plugin_name}_{vn}_{ts}" if vn else f"{plugin_name}_{ts}"
    return f"{core}.zip"


def _default_output_dir() -> str:
    out = os.path.join(_project_dir(), "Dist")
    os.makedirs(out, exist_ok=True)
    return out


def _should_skip(path: str) -> bool:
    bn = os.path.basename(path)
    if bn in EXCLUDE_DIRS:
        return True

    ext = os.path.splitext(path)[1].lower()
    if ext in EXCLUDE_EXTS:
        return True

    return False


def _zip_plugin(plugin_root: str, zip_path: str):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(plugin_root):
            # 제외 폴더 필터
            dirs[:] = [d for d in dirs if not _should_skip(os.path.join(root, d))]
            for fn in files:
                fp = os.path.join(root, fn)
                if _should_skip(fp):
                    continue
                # ZIP 내 상대 경로는 플러그인 루트 폴더명 포함
                rel = os.path.relpath(fp, os.path.dirname(plugin_root))
                zf.write(fp, rel)


def export_plugin_zip() -> str | None:
    try:
        plugin_root = _plugin_root_from_this_file()
        meta = _read_uplugin(plugin_root)
        plugin_name = os.path.basename(plugin_root)
        version_name = meta.get("VersionName") or meta.get("Version")

        default_dir = _default_output_dir()
        default_name = _suggest_zip_name(plugin_name, version_name)
        default_full = os.path.join(default_dir, default_name)

        zip_path = default_full

        # 확장자 보정
        if not zip_path.lower().endswith(".zip"):
            zip_path += ".zip"

        _zip_plugin(plugin_root, zip_path)
        return zip_path

    except Exception as e:
        error(f"[Deploy] Failed: {e}")
        return None


if __name__ == "__main__":
    export_plugin_zip()
