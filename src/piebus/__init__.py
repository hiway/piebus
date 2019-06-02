import datetime
import os

from sys import intern


PATH_BASE = intern(os.path.dirname(os.path.abspath(__file__)))
PATH_TEMPLATES = intern(os.path.join(PATH_BASE, 'templates/'))
PATH_COOKIECUTTER_TEMPLATES = intern(os.path.join(PATH_BASE, 'projects/'))

PATH_CURRENT = intern(os.getcwd() + '/')
PATH_DATABASE = intern(os.path.join(PATH_CURRENT, 'piebus.db'))

YEAR = intern(str(datetime.datetime.now().year))
