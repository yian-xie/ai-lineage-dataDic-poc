"""Load the unchanged graph UI templates from this installed package."""

from importlib.resources import files


def template_path(name: str):
    return files(__package__).joinpath("templates", name)


def read_template(name: str) -> str:
    return template_path(name).read_text(encoding="utf-8")
