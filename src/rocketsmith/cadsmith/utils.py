import importlib.metadata


def get_build123d_version() -> str:
    """Return the installed build123d version."""
    return importlib.metadata.version("build123d")
