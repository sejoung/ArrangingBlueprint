from typing import Set, List, Optional

import unreal

from utils import _warn, _log


def _pkg_join(*parts: str) -> str:
    p = "/".join(x.strip("/") for x in parts if x)
    return p if p.startswith("/") else "/" + p


def is_engine(path: str) -> bool:
    if path.startswith("/Engine") or path.startswith("/Script"):
        return True
    return False


def _ensure_dir(path: str):
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)


def _list_assets(root: str, asset_class=None) -> List[unreal.AssetData]:
    """
    특정 폴더 하위의 에셋 목록을 반환.
    asset_class가 None이면 모든 에셋, 지정하면 해당 클래스만 필터링.
    """
    arm = unreal.AssetRegistryHelpers.get_asset_registry()
    if asset_class is not None:
        flt = unreal.ARFilter(package_paths=[unreal.Name(root)], recursive_paths=True,
                              class_paths=[asset_class.static_class().get_class_path_name()])
    else:
        flt = unreal.ARFilter(package_paths=[unreal.Name(root)], recursive_paths=True)
    return arm.get_assets(flt)


def _list_blueprints(root: str) -> List[unreal.AssetData]:
    """Blueprint 에셋만 필터링하여 반환."""
    return _list_assets(root, unreal.Blueprint)


def _list_levels(root: str) -> List[unreal.AssetData]:
    """Level(World) 에셋만 필터링하여 반환."""
    return _list_assets(root, unreal.World)


def _unique_move_path(dst_pkg_path: str, desired_name: str) -> str:
    base = desired_name
    name = base
    i = 1
    while True:
        obj_path = f"{dst_pkg_path}/{name}"
        if not unreal.EditorAssetLibrary.does_asset_exist(obj_path):
            return obj_path
        i += 1
        name = f"{base}_{i:03d}"


def _unique_name_in(dst_pkg_path: str, desired_name: str) -> str:
    name = desired_name
    i = 1
    while True:
        if not unreal.EditorAssetLibrary.does_asset_exist(f"{dst_pkg_path}/{name}"):
            return name
        i += 1
        name = f"{desired_name}_{i:03d}"


def _get_asset_name(ad: unreal.AssetData) -> str:
    uobj = ad.get_asset()

    if isinstance(uobj, unreal.Material):
        kind = "M_"
    elif isinstance(uobj, unreal.MaterialInstanceConstant):
        kind = "MI_"
    elif isinstance(uobj, unreal.StaticMesh):
        kind = "SM_"
    elif isinstance(uobj, unreal.Texture):
        kind = "T_"
    else:
        kind = ""

    asset_name = str(ad.asset_name)
    index = asset_name.find(kind)

    if index != 0:
        return kind + asset_name
    else:
        return asset_name


def _move_asset(obj_path: str, dst_pkg_path: str) -> Optional[str]:
    ad = unreal.EditorAssetLibrary.find_asset_data(obj_path)
    if not ad or is_engine(obj_path):
        _warn(f"[Skip] Not found or engine asset: {obj_path}")
        return None

    new_obj_path = _unique_move_path(dst_pkg_path, str(ad.asset_name))
    new_asset_name = _get_asset_name(ad)

    new_name = _unique_name_in(dst_pkg_path, new_asset_name)
    uobj = ad.get_asset()
    rename_data = unreal.AssetRenameData(uobj, dst_pkg_path, new_name)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    ok = tools.rename_assets([rename_data])

    # 변경분 저장(선택)
    try:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    except Exception:
        pass

    if not ok:
        _warn(f"[Move Failed] {obj_path} -> {new_obj_path}")
        return None
    return new_obj_path


def _collect_textures(mi_or_mat: unreal.MaterialInterface) -> Set[unreal.Texture]:
    """
    UMaterial / UMaterialInstance 모두 지원.
    """
    out: Set[unreal.Texture] = set()
    try:
        tex_list = unreal.MaterialEditingLibrary.get_used_textures(mi_or_mat)
        for t in tex_list:
            if isinstance(t, unreal.Texture) and not is_engine(t.get_path_name()):
                out.add(t)
        return out
    except Exception:
        pass

    if isinstance(mi_or_mat, unreal.MaterialInstance):
        try:
            for tp in mi_or_mat.get_editor_property("texture_parameter_values"):
                if isinstance(tp.parameter_value, unreal.Texture):
                    if not is_engine(tp.parameter_value.get_path_name()):
                        out.add(tp.parameter_value)
        except Exception:
            pass
    return out


def _static_mesh_materials(sm: unreal.StaticMesh) -> List[unreal.MaterialInterface]:
    out: List[unreal.MaterialInterface] = []
    try:
        for smat in sm.get_editor_property("static_materials"):
            if smat.material_interface and not is_engine(smat.material_interface.get_path_name()):
                out.append(smat.material_interface)
    except Exception:
        pass
    return out


def _skeletal_mesh_materials(skm: unreal.SkeletalMesh) -> List[unreal.MaterialInterface]:
    out: List[unreal.MaterialInterface] = []
    try:
        for mat_slot in skm.get_editor_property("materials"):
            if mat_slot.material_interface and not is_engine(mat_slot.material_interface.get_path_name()):
                out.append(mat_slot.material_interface)
    except Exception:
        pass
    return out


def _collect_from_static_mesh(sm: unreal.StaticMesh, result: dict):
    """StaticMesh와 연관된 Materials, Textures 수집"""
    if is_engine(sm.get_path_name()):
        return
    result['static_meshes'].add(sm)
    for mat in _static_mesh_materials(sm):
        result['materials'].add(mat)
        for tex in _collect_textures(mat):
            result['textures'].add(tex)


def _collect_from_skeletal_mesh(skm: unreal.SkeletalMesh, result: dict):
    """SkeletalMesh와 연관된 Materials, Textures 수집"""
    if is_engine(skm.get_path_name()):
        return
    result['skeletal_meshes'].add(skm)
    for mat in _skeletal_mesh_materials(skm):
        result['materials'].add(mat)
        for tex in _collect_textures(mat):
            result['textures'].add(tex)


def _collect_from_actor(actor: unreal.Actor, result: dict):
    """Actor의 컴포넌트에서 에셋 수집"""
    try:
        components = actor.get_components_by_class(unreal.ActorComponent)
        for comp in components:
            # StaticMeshComponent
            if isinstance(comp, unreal.StaticMeshComponent):
                sm = comp.get_editor_property("static_mesh")
                if sm and isinstance(sm, unreal.StaticMesh):
                    _collect_from_static_mesh(sm, result)

            # SkeletalMeshComponent
            elif isinstance(comp, unreal.SkeletalMeshComponent):
                try:
                    skm = comp.get_editor_property("skeletal_mesh_asset")
                except Exception:
                    skm = None
                if not skm:
                    try:
                        skm = comp.get_editor_property("skeletal_mesh")
                    except Exception:
                        skm = None
                if skm and isinstance(skm, unreal.SkeletalMesh):
                    _collect_from_skeletal_mesh(skm, result)

            # AudioComponent
            elif isinstance(comp, unreal.AudioComponent):
                try:
                    sound = comp.get_editor_property("sound")
                    if sound and isinstance(sound, unreal.SoundBase) and not is_engine(sound.get_path_name()):
                        result['sounds'].add(sound)
                except Exception:
                    pass

            # ParticleSystemComponent (Legacy)
            elif hasattr(unreal, 'ParticleSystemComponent') and isinstance(comp, unreal.ParticleSystemComponent):
                try:
                    ps = comp.get_editor_property("template")
                    if ps and not is_engine(ps.get_path_name()):
                        result['particles'].add(ps)
                except Exception:
                    pass

            # NiagaraComponent
            elif hasattr(unreal, 'NiagaraComponent') and isinstance(comp, unreal.NiagaraComponent):
                try:
                    ns = comp.get_editor_property("asset")
                    if ns and not is_engine(ns.get_path_name()):
                        result['particles'].add(ns)
                except Exception:
                    pass

    except Exception as e:
        _warn(f"Failed to collect from actor {actor.get_name()}: {e}")


def _collect_level_dependencies(level_path: str) -> dict:
    """
    Level(Map)에 배치된 모든 액터에서 에셋 수집.
    """
    result = {
        'static_meshes': set(),
        'skeletal_meshes': set(),
        'materials': set(),
        'textures': set(),
        'sounds': set(),
        'animations': set(),
        'particles': set(),
    }

    _log(f"Loading level: {level_path}")

    try:
        # 레벨을 에디터에서 열기
        editor_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if not editor_subsystem.load_level(level_path):
            _warn(f"Failed to load level: {level_path}")
            return result

        # 현재 열린 레벨의 모든 액터 가져오기
        actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        all_actors = actor_subsystem.get_all_level_actors()

        _log(f"Found {len(all_actors)} actors in level")

        for actor in all_actors:
            _collect_from_actor(actor, result)

    except Exception as e:
        _warn(f"Failed to collect level dependencies: {e}")

    return result


def _find_levels_in_blueprint(bp: unreal.Blueprint) -> List[str]:
    """
    Blueprint의 프로퍼티(변수)에서 Level(World) 참조를 찾음.
    """
    levels = []

    try:
        bp_path = bp.get_path_name()
        _log(f"Searching level properties in Blueprint: {bp_path}")

        # Blueprint의 CDO(Class Default Object)에서 프로퍼티 값 가져오기
        generated_class = bp.get_editor_property("generated_class")
        if not generated_class:
            _log("No generated_class found")
            return levels

        cdo = unreal.get_default_object(generated_class)
        if not cdo:
            _log("No CDO found")
            return levels

        # CDO의 모든 프로퍼티 순회
        for prop_name in dir(cdo):
            if prop_name.startswith("_"):
                continue
            try:
                prop_value = getattr(cdo, prop_name)
                # World(Level) 타입인지 확인
                if isinstance(prop_value, unreal.World):
                    level_path = prop_value.get_path_name().split('.')[0]
                    if not is_engine(level_path):
                        levels.append(level_path)
                        _log(f"Found Level property '{prop_name}': {level_path}")
                # SoftObjectPath로 Level 참조하는 경우
                elif hasattr(prop_value, 'asset_path_name'):
                    path_str = str(prop_value.asset_path_name)
                    if path_str and "World" in path_str or path_str.endswith("_C"):
                        # 실제 에셋 로드해서 확인
                        ad = unreal.EditorAssetLibrary.find_asset_data(path_str.split('.')[0])
                        if ad:
                            asset = ad.get_asset()
                            if isinstance(asset, unreal.World):
                                level_path = path_str.split('.')[0]
                                if not is_engine(level_path):
                                    levels.append(level_path)
                                    _log(f"Found Level soft reference '{prop_name}': {level_path}")
            except Exception:
                continue

    except Exception as e:
        _warn(f"Failed to find levels in blueprint: {e}")

    return levels


def collect_all_from_folder(source_root: str) -> dict:
    """
    폴더 내의 모든 Blueprint를 찾고,
    Blueprint 프로퍼티에 연결된 Level과 그 안의 모든 에셋을 수집.
    """
    result = {
        'blueprints': set(),
        'levels': set(),
        'static_meshes': set(),
        'skeletal_meshes': set(),
        'materials': set(),
        'textures': set(),
        'sounds': set(),
        'animations': set(),
        'particles': set(),
    }

    # 1. Blueprint 수집 및 Blueprint 프로퍼티에서 Level 찾기
    blueprints = _list_blueprints(source_root)
    for ad in blueprints:
        bp = ad.get_asset()
        if isinstance(bp, unreal.Blueprint):
            bp_path = bp.get_path_name()
            if not is_engine(bp_path):
                result['blueprints'].add(bp_path)
                _log(f"Found Blueprint: {bp_path}")

                # Blueprint 프로퍼티에서 Level 참조 찾기
                bp_levels = _find_levels_in_blueprint(bp)
                for level_path in bp_levels:
                    result['levels'].add(level_path)

    _log(f"Total Blueprints: {len(result['blueprints'])}, Levels from properties: {len(result['levels'])}")

    # 2. 각 Level에서 에셋 수집
    for level_path in list(result['levels']):
        deps = _collect_level_dependencies(level_path)
        for sm in deps['static_meshes']:
            result['static_meshes'].add(sm.get_path_name())
        for skm in deps['skeletal_meshes']:
            result['skeletal_meshes'].add(skm.get_path_name())
        for mat in deps['materials']:
            result['materials'].add(mat.get_path_name())
        for tex in deps['textures']:
            result['textures'].add(tex.get_path_name())
        for snd in deps['sounds']:
            result['sounds'].add(snd.get_path_name())
        for particle in deps['particles']:
            result['particles'].add(particle.get_path_name())

    return result
