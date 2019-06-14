import asyncio
import base64
import datetime
import hashlib
import json
import os
import traceback
from json import JSONDecodeError
from uuid import uuid4

import bcrypt
import peewee
from peewee import (
    Model,
    CharField,
    TextField,
    IntegerField,
    ForeignKeyField,
    DateTimeField,
    BooleanField,
)
from playhouse.sqlite_ext import (
    SqliteExtDatabase,
    FTSModel)
from pysyncobj import SyncObj, replicated
from asgiref.sync import sync_to_async

from . import PATH_DATABASE

loop = asyncio.get_event_loop()

pragmas = [
    ('journal_mode', 'wal'),
    ('cache_size', -1024 * 32)]

db = SqliteExtDatabase(PATH_DATABASE, pragmas=pragmas)


class BaseModel(Model):
    timestamp = DateTimeField(default=datetime.datetime.utcnow, index=True)

    class Meta:
        database = db


class User(BaseModel):
    username = CharField(index=True, unique=True)
    password = CharField(index=False)
    note = TextField(index=True, default='')


class Preference(BaseModel):
    key = CharField(index=True, unique=True)
    value = CharField(index=False)


class Frame(BaseModel):
    # Zentropi fields:
    uuid = CharField(index=True, unique=True)
    kind = IntegerField(index=True)
    name = TextField(index=True)
    data = TextField(default='')
    meta = TextField(default='')
    # piebus fields:
    publish = BooleanField(default=False, index=True)
    render = CharField(index=True, default='default')
    source = CharField(default='')
    tags = TextField(index=True, default='')

    @property
    def jdata(self):
        try:
            if self.data:
                return dict(json.loads(self.data))
        except JSONDecodeError:
            print('cannot decode data', self.data)
            pass
        return {}

    @property
    def jmeta(self):
        try:
            if self.meta:
                return dict(json.loads(self.meta))
        except JSONDecodeError:
            print('cannot decode meta', self.meta)
            pass
        return {}


class FTSEntry(FTSModel):
    content = TextField()

    class Meta:
        database = db

    @classmethod
    def index_frame(cls, frame: Frame):
        try:
            existing = cls.get_or_none(docid=frame.id)
            if frame.name == 'telegram-message':
                content = '\n'.join([frame.jdata.get('text', ''), frame.jdata.get('caption', ''), frame.tags])
            else:
                content = '\n'.join([frame.name, str(frame.data), frame.tags])
            if not content.strip():
                return
            if existing:
                existing.update(content=content)
            else:
                cls.create(docid=frame.id, content=content)
        except peewee.OperationalError:
            cls.create_table()
            cls.index_frame(frame)


class Kind(object):
    command = 0
    event = 1
    message = 2
    request = 3
    response = 4
    state = 5
    stream = 6


def ensure_db():
    if os.path.exists(PATH_DATABASE):
        return False
    User.create_table()
    Preference.create_table()
    Frame.create_table()
    return True


class PiebusAPI(SyncObj):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @replicated
    def _register(self, username, password):
        password = base64.b64encode(hashlib.sha256(password.encode('utf-8')).digest())
        hashed = bcrypt.hashpw(password, bcrypt.gensalt())
        try:
            User.create(username=username, password=hashed)
            return True
        except:
            traceback.print_exc()
            return False

    async def register(self, username, password):
        return await sync_to_async(self._register)(username, password, sync=True)

    @replicated
    def _login(self, username, password):
        user = User.get_or_none(username=username)
        if not user:
            return False
        password = base64.b64encode(hashlib.sha256(password.encode('utf-8')).digest())
        hashed = user.password.encode('utf-8')
        if bcrypt.checkpw(password, hashed):
            return True
        return False

    async def login(self, username, password):
        return await sync_to_async(self._login)(username, password, sync=True)

    @replicated
    def _logout(self, username):
        return True

    async def logout(self, username):
        return await sync_to_async(self._logout)(username, sync=True)

    def _get_preference(self, key, default=None):
        pref = Preference.get_or_none(key=key)
        if pref is None:
            return default
        return pref.value if pref.value is not None else default

    @replicated
    def _set_preference(self, key, value):
        pref = Preference.get_or_none(key=key)
        if pref is not None:
            q = Preference.update(value=value).where(Preference.key == key)
            q.execute()
        else:
            Preference.create(key=key, value=value)
        return value

    async def preference(self, key, value=None):
        if value is not None:
            await sync_to_async(self._set_preference)(key, value, sync=True)
        return self._get_preference(key)

    async def enable_register(self, value=None):
        if value is not None:
            await sync_to_async(self._set_preference)('enable_register', 1 if value else 0, sync=True)
        return bool(int(self._get_preference('enable_register', 0)))

    @replicated
    def _create_frame(self, kind, name, data, meta, publish, render, source, tags):
        frame = Frame.create(
            uuid=uuid4().hex,
            kind=int(kind) if kind != '' else 1,
            name=name,
            data=json.dumps(data) or '',
            meta=json.dumps(meta) or '',
            publish=publish or False,
            render=render or 'default',
            source=source or '',
            tags=tags or '',
        )
        return frame

    async def create_frame(self, kind, name, data=None, meta=None, publish=False, render='', tags=''):
        source = meta.get('source', '') if meta else ''
        frame = await sync_to_async(self._create_frame)(kind=kind, name=name,
                                                        data=data, meta=meta,
                                                        publish=publish, render=render,
                                                        source=source, tags=tags,
                                                        sync=True)
        await sync_to_async(FTSEntry.index_frame)(frame)
        return frame

    async def list_frames(self, limit=10):
        frames = Frame.select().order_by(Frame.timestamp.desc()).limit(limit)
        return frames

    @replicated
    def _index_frames(self):
        frames = Frame.select().order_by(Frame.timestamp.desc())
        for frame in frames:
            FTSEntry.index_frame(frame)

    async def index_frames(self):
        await sync_to_async(self._index_frames)(sync=True)
        return True

    async def search_frames(self, query):
        frames = Frame \
            .select() \
            .join(FTSEntry, on=(Frame.id == FTSEntry.docid)) \
            .where(FTSEntry.match(query)).order_by(Frame.timestamp.desc())
        return frames

    async def search_public_frames(self, query):
        frames = Frame \
            .select() \
            .join(FTSEntry, on=(Frame.id == FTSEntry.docid)) \
            .where((FTSEntry.match(query)) & (Frame.publish == True)).order_by(Frame.timestamp.desc())
        return frames

    async def list_public_frames(self, limit=10):
        frames = Frame.select() \
            .where(Frame.publish == True) \
            .order_by(Frame.timestamp.desc()) \
            .limit(limit)
        return frames

    async def frame_from_uuid(self, uuid):
        frame = Frame.get(Frame.uuid == uuid)
        return frame

    async def publish(self, uuid, status):
        frame = Frame.get(Frame.uuid == uuid)
        frame.publish = status
        await sync_to_async(frame.save)()
        return frame
