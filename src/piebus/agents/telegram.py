import asyncio
import functools
import os

from uuid import uuid4

from aiogram import Bot, Dispatcher, executor, types, filters
from aiogram.types import ReplyKeyboardRemove
from aiogram.types.message import ContentType
from aiogram.utils.executor import Executor, log, _setup_callbacks
from piebus import conf

from piebus.api import Kind
from piebus.bot import PieBot

from piebus.server import api, content_path, render
from quart import url_for

BOT_NAME = conf['telegram-bot']['name']
BOT_TOKEN = conf['telegram-bot']['token']
BOT_OWNER = conf['telegram-bot']['owner']
BOT_OWNER_ID = int(conf['telegram-bot']['owner_id'] or 0)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
pie = PieBot(data_path=os.path.join(conf['paths']['package'], 'data'))


def mkfilename(prefix, suffix):
    return content_path(f'{prefix}{uuid4().hex}.{suffix}')


def require_owner(func):
    functools.wraps(func)

    def wrapper(msg_or_inline):
        owner_id = int(conf['telegram-bot']['owner_id'])

        async def nop():
            return

        if msg_or_inline.chat and \
                msg_or_inline.from_user.id != owner_id:
            print('!!! skipping chat', msg_or_inline)
            return nop()
        if msg_or_inline.from_user and \
                msg_or_inline.from_user.id != owner_id:
            print('!!! skipping inline query', msg_or_inline)
            return nop()

        return func(msg_or_inline)

    return wrapper


@dp.message_handler(filters.CommandStart())
@require_owner
async def send_welcome(message: types.Message):
    print('handling /start annd /help commands', message.text)
    await api.create_frame(Kind.event, 'telegram-chat-start', data=dict(message))
    await message.reply(f"Hi!\nI'm {BOT_NAME}!\n")


@dp.message_handler(content_types=ContentType.ANY)
@require_owner
async def messages(message: types.Message):
    data = dict(message)
    path = None
    if message.photo:
        path = await message.photo[-1].download(mkfilename('img_', 'jpg'))
    elif message.voice:
        path = await message.voice.download(mkfilename('voi_', 'oga'))
    elif message.video_note:
        path = await message.video_note.download(mkfilename('vin_', 'mp4'))
    elif message.video:
        path = await message.video.download(mkfilename('vid_', 'mp4'))
    elif message.sticker:
        path = await message.sticker.thumb.download(mkfilename('stk_', 'webp'))
    elif message.text:
        pass
    else:
        print('unknown media:', message)
    if path:
        data.update({'media_url': path.name})
    text = message.text.lower() if message.text else ''
    if text.startswith('post '):
        data.update({'text': text[5:]})
    frame = await api.create_frame(Kind.event, 'telegram-message', data=data, render='telegram')
    if path or text.startswith('post '):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('Public', callback_data=f'frame public {frame.uuid}'))
        markup.add(types.InlineKeyboardButton('Private', callback_data=f'frame private {frame.uuid}'))
        await message.reply('Privacy for this post:', reply_markup=markup)
    else:
        reply = pie.reply(text) or '...'
        await message.reply(reply)


@dp.callback_query_handler()
@require_owner
async def callback_query(message: types.Message):
    if not message.data.startswith('frame'):
        await message.answer('dunno')
        return
    if message.data.startswith('frame public '):
        await api.publish(message.data.replace('frame public ', ''), True)
        await message.answer(f'marked as pulic')
        await bot.send_message(message.message.chat.id, f'Marked as public.')
    elif message.data.startswith('frame private '):
        await api.publish(message.data.replace('frame private ', ''), False)
        await message.answer(f'marked as private')
        await bot.send_message(message.message.chat.id, f'Marked as private.')
    await bot.send_message(message.message.chat.id, f'Published.')


@dp.inline_handler()
@require_owner
async def inline(inline_query: types.InlineQuery):
    input_content = types.InputTextMessageContent(inline_query.query or 'echo')
    item1 = types.InlineQueryResultArticle(id='1', title='echo %s' % input_content['message_text'],
                                           input_message_content=input_content)
    item2 = types.InlineQueryResultArticle(id='2', title='beep %s' % input_content['message_text'],
                                           input_message_content=input_content)
    await bot.answer_inline_query(inline_query.id, results=[item1, item2], cache_time=1)


class ZExecutor(Executor):
    def start_polling(self, reset_webhook=None, timeout=20, fast=True):
        self._prepare_polling()
        loop: asyncio.AbstractEventLoop = self.loop
        loop.run_until_complete(self._startup_polling())
        loop.create_task(self.dispatcher.start_polling(reset_webhook=reset_webhook, timeout=timeout, fast=fast))


def start_polling(dispatcher, *, loop=None, skip_updates=False, reset_webhook=True,
                  on_startup=None, on_shutdown=None, timeout=20, fast=True):
    executor = ZExecutor(dispatcher, skip_updates=skip_updates, loop=loop)
    _setup_callbacks(executor, on_startup, on_shutdown)
    executor.start_polling(reset_webhook=reset_webhook, timeout=timeout, fast=fast)
    return executor._shutdown_polling


def start():
    return start_polling(dp, skip_updates=False)
