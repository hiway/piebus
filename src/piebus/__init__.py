import datetime
import io
import os
from uuid import uuid4
from sys import intern

import configparser

YEAR = intern(str(datetime.datetime.now().year))

conf = configparser.ConfigParser()
conf._interpolation = configparser.ExtendedInterpolation()

conf['owner'] = {}
conf['owner']['name'] = 'edit: piebus.conf'
conf['owner']['copyright'] = '%s ${owner:name}' % YEAR

conf['paths'] = {}
conf['paths']['database'] = 'piebus.db'
conf['paths']['content'] = 'content'
conf['paths']['templates'] = '${package}/templates'
conf['paths']['static'] = '${package}/static'
conf['paths']['projects'] = '${package}/projects'
conf['paths']['package'] = os.path.dirname(os.path.abspath(__file__))

conf['webapp'] = {}
conf['webapp']['name'] = 'piebus'
conf['webapp']['register'] = 'no'
conf['webapp']['secret_key'] = uuid4().hex
conf['webapp']['live_posts_max'] = '20'
# conf['webapp']['live_posts_max_age'] = '1 week'
# conf['webapp']['live_posts_per_page'] = 10
conf['telegram-bot'] = {}
conf['telegram-bot']['name'] = ''
conf['telegram-bot']['token'] = ''
conf['telegram-bot']['owner'] = ''
conf['telegram-bot']['owner_id'] = ''

if not os.path.exists('piebus.conf'):
    iofile = io.StringIO()
    conf.write(iofile)
    iofile.seek(0)
    conf_string = iofile.readlines()
    newlines = []
    for line in conf_string:
        if line.startswith('package'):
            continue
        newlines.append(line)
    with open('piebus.conf', 'w') as outfile:
        outfile.writelines(newlines)

conf.read('piebus.conf')

PATH_BASE = intern(conf['paths']['package'])
PATH_TEMPLATES = intern(conf['paths']['templates'])
PATH_COOKIECUTTER_TEMPLATES = intern(conf['paths']['projects'])
PATH_DATABASE = intern(conf['paths']['database'])
PATH_CURRENT = intern(os.getcwd() + '/')
