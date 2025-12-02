import unreal

from ab_menu import register_menus


def _startup():
    try:
        register_menus()
        unreal.log("[ArrangingBlueprint] Menus registered")
    except Exception as e:
        unreal.log_error(f"[ArrangingBlueprint] Menu registration failed: {e}")


_startup()
