import os

import markdown

from cookiecutter.main import cookiecutter

from . import PATH_COOKIECUTTER_TEMPLATES


def cookiecutter_template_path(template_name):
    return os.path.join(PATH_COOKIECUTTER_TEMPLATES, template_name)


def render_project(template_name, **context):
    cookiecutter(cookiecutter_template_path(template_name), extra_context=context)


def render_markdown(content):
    return markdown.markdown(content, extensions=['codehilite', 'fenced_code'])


