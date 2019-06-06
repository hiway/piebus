import html
import re
import os

import markdown

from cookiecutter.main import cookiecutter
from jinja2.utils import urlize

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
    print('tgmd - input:', text)
    text = html.unescape(text)
    print('tgmd - unescape:', text)
    text =  re.sub(r'(http:[^\s\n\r]+)', r'<a href="\1">\1</a>',
text)
    print('tgmd - urlize:', text)
    md = tg_tilde.sub(r'```\1', text)
    print('tgmd - inter - tilde sub:', md)
    ht = render_markdown(md)
    print('tgmd - output:', ht)
    return ht
