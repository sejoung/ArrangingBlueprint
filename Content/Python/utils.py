import unreal


def _log(s: str): unreal.log(s)


def _warn(s: str): unreal.log_warning(s)


def _err(s: str): unreal.log_error(s)
