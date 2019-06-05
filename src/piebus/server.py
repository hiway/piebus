import asyncio
import base64
import functools
import io
import json
import os
from datetime import datetime

import aiofiles
from functools import lru_cache

from PIL import Image
from piebus import conf
from quart import (
    abort,
    flash,
    Quart,
    redirect,
    request,
    render_template,
    Response,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from . import (
    PATH_CURRENT
)
from .api import PiebusAPI, ensure_db, Kind
from .utils import render_markdown

app = Quart('piebus')
api = PiebusAPI('127.0.0.1:8008', [])
admin_sse_clients = set()

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'css', 'js', 'py', 'sh',
                      'jpg', 'png', 'gif',
                      'mp4',
                      'oga', 'mp3',
                      'zip', 'gz', 'tar',
                      }


def content_path(path):
    return os.path.join(app.config['CONTENT_FOLDER'], path)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def ensure_database(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if ensure_db():
            return redirect(url_for('register'))
        return func(*args, **kwargs)

    return wrapper


def login_required(fn):
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        if session.get('logged_in'):
            return fn(*args, **kwargs)
        return redirect(url_for('login', next=request.path))

    return inner


async def render(template, **context):
    extra_context = dict(
        copyright=conf['owner']['copyright'],
        app_name=conf['webapp']['name'],
    )
    extra_context.update(context)
    return await render_template(template, **extra_context)


async def query_or_form_field(req, name, default):
    form = await req.form
    return req.args.get(name, None) or form.get(name, default)


async def intercooler_request(req):
    return (await query_or_form_field(request, 'ic-request', False)) == 'true'


async def frame_from_form(form):
    kind = form.get('kind', '')
    name = form.get('name', '')
    data = form.get('data', '')
    meta = form.get('meta', '')
    publish = form.get('publish', False)
    render = form.get('render', '')
    tags = form.get('tags', '')
    frame = await api.create_frame(kind=kind, name=name,
                                   data=data, meta=meta,
                                   publish=publish, render=render,
                                   tags=tags)
    return frame


def humanize_ts(timestamp=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    https://shubhamjain.co/til/how-to-render-human-readable-time-in-jinja/
    """
    now = datetime.utcnow()
    if isinstance(timestamp, int):
        timestamp = datetime.fromtimestamp(timestamp)
    diff = now - timestamp
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(int(second_diff)) + " seconds ago"
        if second_diff < 120:
            return "a minute ago"
        if second_diff < 3600:
            return str(int(second_diff / 60)) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str(int(second_diff / 3600)) + " hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return str(day_diff) + " days ago"
    if day_diff < 31:
        return str(int(day_diff / 7)) + " weeks ago"
    if day_diff < 365:
        return str(int(day_diff / 30)) + " months ago"
    return str(int(day_diff / 365)) + " years ago"


app.jinja_env.filters['humanize'] = humanize_ts


@app.route('/register/', methods=['GET', 'POST'])
@ensure_database
async def register():
    if not (app.config['ENABLE_REGISTER'] or await api.enable_register()):
        raise abort(404)
    form = await request.form
    if request.method == 'POST' and form.get('username') and form.get('password'):
        username = str(form.get('username'))
        password = str(form.get('password'))
        if not await api.register(username, password):
            await flash(f'Username {username} is not vailable.', category='danger')
            return await render('register.html',
                                title='logout',
                                username=username,
                                password='')
        session['logged_in'] = True
        session['username'] = username
        session.permanent = True
        await flash(f'You are now registered as {username} and logged in.')
        return redirect(url_for('index'))
    return await render('register.html',
                        title='logout')


@app.route('/login/', methods=['GET', 'POST'])
@ensure_database
async def login():
    form = await request.form
    next_url = request.args.get('next') or form.get('next') or '/'
    if request.method == 'POST' and form.get('username') and form.get('password'):
        username = str(form.get('username'))
        password = str(form.get('password'))
        if await api.login(username, password):
            session['logged_in'] = True
            session['username'] = username
            session.permanent = True
            await flash('You are now logged in.', 'success')
            return redirect(next_url or url_for('index'))
        else:
            await flash('Incorrect password.', 'danger')
    return await render('login.html', next_url=next_url,
                        title='logout')


@app.route('/logout/', methods=['GET', 'POST'])
@ensure_database
async def logout():
    if request.method == 'POST':
        username = str(session.get('username', ''))
        if not username:
            session.clear()
            await flash('You are now logged out.', 'success')
            return redirect(url_for('index'))
        if await api.logout(username):
            session.clear()
            await flash('You are now logged out.', 'success')
            return redirect(url_for('index'))
    return await render('logout.html',
                        title='logout')


@app.route('/favicon.ico')
def favicon():
    if os.path.exists(os.path.join(app.config['CONTENT_FOLDER'], 'favicon.ico')):
        return send_from_directory(app.config['CONTENT_FOLDER'], 'favicon.ico')
    abort(404)


@app.route('/.well-known/security.txt')
@lru_cache(maxsize=8)
def security():
    return send_from_directory(
        app.config['CONTENT_FOLDER'], 'security.txt')


@app.route('/robots.txt')
@lru_cache(maxsize=8)
def robots():
    return send_from_directory(
        app.config['CONTENT_FOLDER'], 'robots.txt')


@app.route('/content/<path:filename>')
def content_file(filename):
    if filename and allowed_file(filename):
        filename = secure_filename(filename)
        return send_from_directory(
            app.config['CONTENT_FOLDER'], filename)
    raise abort(404)


@app.route('/resize/<int:width>/content/<path:filename>')
def resize_image(width, filename):
    filename = secure_filename(filename)
    filename = 'content/' + filename
    if filename and allowed_file(filename):
        size = (width, width)
        image = Image.open(filename)
        image.thumbnail(size, Image.ANTIALIAS)
        mem_file = io.BytesIO()
        if width <= 500:
            quality = 50
        elif width <= 900:
            quality = 70
        else:
            quality = 85
        image.save(mem_file, image.format, quality=quality)
        mem_file.seek(0)
        return Response(mem_file.read(), content_type=f'image/{image.format}')
    abort(404)


@app.route('/')
async def index():
    async with aiofiles.open(content_path('index.md'), 'r') as f:
        content = await f.read()
    return await render('page.html',
                        title='home',
                        post=render_markdown(content))


@app.route('/live/')
async def live():
    frames = await api.list_public_frames(limit=conf['webapp']['live_posts_max'])
    if await intercooler_request(request):
        return await render('includes/live.html', frames=frames, Kind=Kind)
    return await render('live.html', frames=frames, Kind=Kind)


@app.route('/search/', methods=['GET', 'POST'])
async def search():
    query = await query_or_form_field(request, 'q', 'nothing')
    return await render('page.html',
                        title='search',
                        post=f'you searched for: {query}')


@app.route('/frame/create/', methods=['GET', 'POST'])
@login_required
async def frame_create():
    if request.method == 'POST':
        form = await request.form
        frame = await frame_from_form(form)
        if await intercooler_request(request):
            return await render('includes/frame_render.html', frame=frame, Kind=Kind)
        return redirect(url_for('frame_detail', uuid=frame.uuid))
    return await render('frame_create.html', Kind=Kind)


@app.route('/frame/<uuid>/', methods=['GET'])
async def frame_detail(uuid):
    frame = await api.frame_from_uuid(uuid)
    if not (frame.publish or session.get('logged_in')):
        raise abort(404)
    if await intercooler_request(request):
        return await render('includes/frame_render.html', frame=frame, Kind=Kind)
    return await render('frame.html', frame=frame, Kind=Kind)


@app.route('/frames/', methods=['GET', 'POST'])
@login_required
async def list_frames():
    frames = await api.list_frames(limit=100)
    if await intercooler_request(request):
        return await render('includes/frames.html', frames=frames, Kind=Kind)
    return await render('frames.html', frames=frames, Kind=Kind)


@app.route('/admin/')
@login_required
async def admin():
    enable_register = await api.enable_register()
    return await render('admin/index.html',
                        title='admin',
                        enable_register=enable_register)


@app.route('/admin/settings/')
@login_required
async def admin_settings():
    enable_register = await api.enable_register()
    tg_settings = await api.preference('telegram_bot') or '{}'
    tg_settings = json.loads(tg_settings)
    return await render('admin/settings.html',
                        title='admin',
                        enable_register=enable_register, **tg_settings)


@app.route('/admin/settings/register', methods=['POST'])
async def admin_settings_register():
    enable = (await query_or_form_field(request, 'enable_register', '')) == 'on'
    await api.enable_register(enable)
    if await intercooler_request(request):
        return await render('admin/settings/register.html', enable_register=enable)
    return redirect(url_for('admin_settings'))


@app.route('/admin/settings/telegram', methods=['POST'])
async def admin_settings_telegram():
    form = await request.form
    tg_settings = dict(
        telegram_bot_enable=form.get('telegram_bot_enable', 'off') == 'on',
        telegram_bot_name=form['telegram_bot_name'],
        telegram_bot_owner_id=form['telegram_bot_owner_id'],
        telegram_bot_owner_username=form['telegram_bot_owner_username'],
        telegram_bot_token=form['telegram_bot_token'],
    )
    await api.preference('telegram_bot', json.dumps(tg_settings))
    if await intercooler_request(request):
        return await render('admin/settings/telegram.html', **tg_settings)
    return redirect(url_for('admin_settings'))


@app.route('/admin/settings/<setting>', methods=['POST'])
async def admin_settings_setting(setting):
    value = (await query_or_form_field(request, setting, ''))
    await api.preference(setting, value)
    if await intercooler_request(request):
        return await render(f'admin/settings/{setting}.html', **{setting: value})
    return redirect(url_for('admin_settings'))
