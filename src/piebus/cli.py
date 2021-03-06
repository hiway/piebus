import asyncio
import os
import click

from uuid import uuid4

from piebus import conf


@click.group()
def main():
    pass


@main.command()
@click.argument('path')
@click.option('--template', default='default')
@click.option('--security-contact', default='yolo@example.com')
def init(path, template, security_contact):
    from .utils import render_project
    render_project(
        template,
        project_name=path.title(),
        project_slug=path,
        project_security_contact=security_contact,
        project_secret_key=str(uuid4().hex),
        project_content_dir='content/',
        project_copyright=f'{path.title()}, All Rights Reserved.',
    )


@main.command()
@click.argument('path', default='.')
@click.option('--debug/--no-debug', default=False)
@click.option('--reload/--no-reload', default=False)
@click.option('--register/--no-register', default=False, help='Allow registering new users.')
@click.option('--telegram/--no-telegram', default=False)
@click.option('--host', default='127.0.0.1')
@click.option('--port', default='5000')
def serve(path, debug, reload, register, telegram, host, port):
    global PATH_CURRENT, APP_NAME
    PATH_CURRENT = os.path.expanduser(path)
    from .server import app
    os.chdir(os.path.expanduser(path))
    app.static_folder = conf['paths']['static']
    app.static_url_path = '/static'
    app.config['CONTENT_FOLDER'] = conf['paths']['content']
    app.config['SECRET_KEY'] = conf['webapp']['secret_key']
    app.config['APP_NAME'] = conf['webapp']['name']
    app.config['ENABLE_REGISTER'] = register or conf['webapp']['register']
    app.config['COPYRIGHT'] = conf['owner']['copyright']
    tg = None
    if telegram:
        from .agents.telegram import start
        print('Starting telegram polling...')
        tg = start()
    loop = asyncio.get_event_loop()
    print('Starting web application...')
    app.run(host=host, port=port, debug=debug, use_reloader=reload, loop=loop)
    print('Exiting...')
    if tg:
        print('Stopping telegram polling...')
        loop.run_until_complete(tg())


if __name__ == '__main__':
    main()
