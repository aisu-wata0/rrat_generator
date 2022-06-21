# bot.py
import logging
import os

import discord
from dotenv import load_dotenv
import json
from queue import Queue
from threading import Thread
import traceback

from consume_requests import requests_queue, stop_event, consume_requests
import gpt_local_settings

keyword_complete = "!rrat "
keyword_help = "!rrat help "
keyword_settings = "!rrat set "
help_string = f"""example: `{keyword_complete} "context": "GPT will complete the text in the context field. The parameters can be adjusted", "max_length": 70, "top_p": 0.9, "top_k": 0, "temperature": 0.75`\nwill return with 🛑 when request queue is full"""

discord_env_filepath = "DISCORD.env"
discord_token_var = "DISCORD_TOKEN"
load_dotenv(discord_env_filepath)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

users_settings = {}
filepath = f"discord-user_settings.json"
try:
    with open(filepath, "rb") as f:
        users_settings = json.load(f)
except FileNotFoundError:
    pass
except Exception as e:
    logging.exception(e)


client = discord.Client()


@client.event
async def on_ready():
    for guild in client.guilds:
        print(
            f"{client.user} is connected to the following guild:\n"
            f"{guild.name}(id: {guild.id})"
        )


import functools
import typing
import asyncio


def to_thread(func: typing.Callable):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        wrapped = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(None, func)

    return wrapper


def parameters_user(parameters, message_author_id):
    return {**users_settings[message_author_id], **parameters}


def parse_settings(parameters):
    return {
        key: value
        for key, value in parameters.items()
        if key in gpt_local_settings.default_kwargs.keys()
    }, {
        key: value
        for key, value in parameters.items()
        if key not in gpt_local_settings.default_kwargs.keys()
    }


def parse_message_parameters(msg_content, keyword, has_context):
    parameters = msg_content[len(keyword) :]
    parameters = parameters.strip()
    if not parameters.startswith("{"):
        parameters = "{" + parameters + "}"

    if has_context:
        if '"context":' not in parameters:
            parameters = '{"context": ' + parameters[1:]
    return json.loads(parameters, strict=False)


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith(keyword_help):
        await message.reply(help_string)
        return

    if message.content.startswith(keyword_settings):
        try:
            parameters = parse_message_parameters(
                message.content, keyword_settings, has_context=False
            )
            settings_ok, settings_fail = parse_settings(parameters)
            users_settings[message.author.id] = settings_ok

            def saveNoInterrupt():
                with open(filepath, "w", encoding="utf8") as f:
                    json.dump(users_settings, f, indent=2)

            a = Thread(target=saveNoInterrupt)
            a.start()
            a.join()
            reply = "```json\n" + json.dumps(settings_ok, indent=2) + "\n```"
            if settings_fail:
                reply += (
                    "\n failed: ```json\n"
                    + json.dumps(settings_fail, indent=2)
                    + "\n```"
                )
            await message.reply(reply, mention_author=False)
        except Exception as e:
            await message.remove_reaction("⌛", client.user)
            await message.add_reaction("❌")
            await message.reply(str(e) + "\n" + help_string, mention_author=False)
        return

    if message.content.startswith(keyword_complete):
        if requests_queue.qsize() > 100:
            await message.add_reaction("🛑")
            return
        # react to message while preparing response
        await message.add_reaction("⌛")
        try:
            parameters = parse_message_parameters(
                message.content, keyword_complete, has_context=True
            )
            parameters = parameters_user(parameters, message.author.id)
            if parameters:
                response_queue = Queue()

                requests_queue.put((parameters, response_queue))

                @to_thread
                def blocking_func():
                    return response_queue.get()

                response = str(json.dumps(await blocking_func(), indent=2))

                # remove reaction
                await message.remove_reaction("⌛", client.user)
                await message.add_reaction("✅")
                # send response
                await message.reply(response, mention_author=False)
        except Exception as e:
            await message.remove_reaction("⌛", client.user)
            await message.add_reaction("❌")
            await message.reply(str(e) + "\n" + help_string, mention_author=False)
        return


def discord_bot_run():
    if not DISCORD_TOKEN:
        raise IOError(
            f"Missing discord token in env file, please define `{discord_token_var}` in the file {discord_env_filepath}"
        )
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    import threading

    thread_consume_requests = threading.Thread(target=consume_requests)
    thread_consume_requests.start()

    import signal

    def signal_handler(sig, frame):
        global app_running
        stop_event.set()
        thread_consume_requests.join()
        exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    discord_bot_run()
