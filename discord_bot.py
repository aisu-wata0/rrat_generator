# bot.py

import logging
from operator import is_

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

import os
from pathlib import Path
import shutil

import discord
from dotenv import load_dotenv
import json
from json.decoder import JSONDecodeError
from queue import Queue
from threading import Thread
import traceback
import ast
import re

if __name__ == "__main__":
    loggers = [
        logging.getLogger(name).setLevel(logging.WARN)
        for name in logging.root.manager.loggerDict
    ]

from consume_requests import requests_queue, stop_event, consume_requests
import gpt_local_settings

keyword_complete = "!rrat "
keyword_help = "!rrat_help "
keyword_settings = "!rrat_set "
help_string = f"""examples: \n{keyword_complete} Text to be completed\n`{keyword_complete} "context": "\""Complete the text in the context field. The parameters can be adjusted"\"", "max_length": 70, "top_p": 0.9, "top_k": 0, "temperature": 0.75`\nYou can change the settings for all your next queries (each user has his), example:\n`{keyword_settings} "max_length": 70, "top_p": 0.9, "top_k": 0, "temperature": 0.75`\nwill react with 🛑 if the request queue is full"""

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
except JSONDecodeError as e:
    logging.warning(
        f"Unable to load user settings from file: {filepath}, JSONDecodeError"
    )
    shutil.copy(filepath, Path(filepath).with_suffix(".json.bak"))
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
    params = {}
    if message_author_id in users_settings:
        params = users_settings[message_author_id]
    return {**params, **parameters}


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
            if not parameters.startswith('{"context":'):
                parameters = '{"context":' + parameters[1:]
                if not parameters.startswith(
                    '{"context":"'
                ) and not parameters.endswith('"}'):
                    parameters = '{"context":"""' + parameters[len('{"context":'):-1] + '"""}'
    return ast.literal_eval(parameters)


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

    keyw = ""
    is_dm = not message.guild
    if message.content.startswith(keyword_complete):
        keyw = keyword_complete
    should_complete = keyw or is_dm
    if should_complete:
        if requests_queue.qsize() > 100:
            await message.add_reaction("🛑")
            return
        # react to message while preparing response
        await message.add_reaction("⌛")
        try:
            parameters = parse_message_parameters(
                message.content, keyw, has_context=True
            )
            parameters = parameters_user(parameters, message.author.id)
            if parameters:
                response_queue = Queue()

                requests_queue.put((parameters, response_queue))

                @to_thread
                def blocking_func():
                    return response_queue.get()

                out = await blocking_func()

                response = str(json.dumps(out, indent=2))[2:-2]
                if not keyw:
                    if out["completion"]:
                        # response = out["completion"][len(parameters["context"]):]
                        response = out["completion"]
                # remove reaction
                await message.remove_reaction("⌛", client.user)
                # send response
                await message.reply(response, mention_author=False)
        except Exception as e:
            logging.exception(e)
            await message.remove_reaction("⌛", client.user)
            await message.add_reaction("❌")
            e_name = type(e).__name__
            error_msg = "" if e_name in str(e) else (e_name + ": ")
            error_msg += str(e) + help_string
            await message.reply(error_msg, mention_author=False)
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
