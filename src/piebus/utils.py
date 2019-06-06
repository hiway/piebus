import html
import re
import os

import markdown

from cookiecutter.main import cookiecutter

from . import PATH_COOKIECUTTER_TEMPLATES


def cookiecutter_template_path(template_name):
    return os.path.join(PATH_COOKIECUTTER_TEMPLATES, template_name)


def render_project(template_name, **context):
    cookiecutter(cookiecutter_template_path(template_name), extra_context=context)


def render_markdown(content):
    html = markdown.markdown(content, extensions=['codehilite', 'fenced_code'])
    return html


tg_tilde = re.compile(r'^~(.*)', flags=re.MULTILINE | re.UNICODE)


def telegram_markdown(text):
    text = html.unescape(text)
    text =  re.sub(r'(https?:[^\s\n\r]+)', r'<a href="\1">\1</a>', text)
    md = tg_tilde.sub(r'```\1', text)
    ht = render_markdown(md)
    return ht
