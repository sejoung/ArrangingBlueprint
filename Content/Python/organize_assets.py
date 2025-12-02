from unreal_file_utils import collect_all_from_folder, _pkg_join, _ensure_dir, _move_asset
from utils import _log, _warn, _err


def run(source_root: str) -> int:
    """
    폴더 내의 Blueprint와 Level을 찾고,
    Level 안에 배치된 모든 에셋들을 타입별 폴더로 이동.

    폴더 구조:
    - Blueprints/ (Blueprint + Level)
    - Meshes/
    - Materials/
    - Textures/
    - Sounds/
    - Animations/
    - Particles/
    """
    if not source_root.startswith("/Game"):
        _err("source_root must start with /Game")
        return 0

    _log(f"=== Collecting assets from: {source_root} ===")

    # 폴더에서 모든 에셋 수집
    collected = collect_all_from_folder(source_root)

    bp_count = len(collected['blueprints'])
    level_count = len(collected['levels'])
    _log(f"Found {bp_count} Blueprints, {level_count} Levels (from Blueprint properties)")

    if bp_count == 0:
        _warn(f"No Blueprint under {source_root}")
        return 0

    # 타입별 폴더 경로
    dest_root = source_root
    dst_blueprints = _pkg_join(dest_root, "Blueprints")
    dst_meshes = _pkg_join(dest_root, "Meshes")
    dst_materials = _pkg_join(dest_root, "Materials")
    dst_textures = _pkg_join(dest_root, "Textures")
    dst_sounds = _pkg_join(dest_root, "Sounds")
    dst_animations = _pkg_join(dest_root, "Animations")
    dst_particles = _pkg_join(dest_root, "Particles")

    # 폴더 생성
    for p in (dst_blueprints, dst_meshes, dst_materials, dst_textures,
              dst_sounds, dst_animations, dst_particles):
        _ensure_dir(p)

    moved = 0

    # 이동 실행 (의존성 순서: Textures -> Materials -> Meshes -> 나머지 -> Levels -> Blueprints)
    _log(f"Moving {len(collected['textures'])} textures...")
    for path in collected['textures']:
        if _move_asset(path, dst_textures):
            moved += 1

    _log(f"Moving {len(collected['materials'])} materials...")
    for path in collected['materials']:
        if _move_asset(path, dst_materials):
            moved += 1

    _log(f"Moving {len(collected['static_meshes'])} static meshes...")
    for path in collected['static_meshes']:
        if _move_asset(path, dst_meshes):
            moved += 1

    _log(f"Moving {len(collected['skeletal_meshes'])} skeletal meshes...")
    for path in collected['skeletal_meshes']:
        if _move_asset(path, dst_meshes):
            moved += 1

    _log(f"Moving {len(collected['sounds'])} sounds...")
    for path in collected['sounds']:
        if _move_asset(path, dst_sounds):
            moved += 1

    _log(f"Moving {len(collected['particles'])} particles...")
    for path in collected['particles']:
        if _move_asset(path, dst_particles):
            moved += 1

    _log(f"Moving {len(collected['levels'])} levels...")
    for path in collected['levels']:
        if _move_asset(path, dst_blueprints):
            moved += 1

    _log(f"Moving {len(collected['blueprints'])} blueprints...")
    for path in collected['blueprints']:
        if _move_asset(path, dst_blueprints):
            moved += 1

    _log(f"=== Done === moved={moved}, destination={dest_root}")
    return moved
