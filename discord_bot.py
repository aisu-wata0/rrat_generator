# bot.py
import os

import discord
from dotenv import load_dotenv
from markupsafe import escape
import json
from queue import Queue

from consume_requests import requests_queue, stop_event

load_dotenv("DISCORD.env")
TOKEN = os.getenv("DISCORD_TOKEN")
# GUILD = os.getenv('DISCORD_GUILD')

client = discord.Client()


@client.event
async def on_ready():
    for guild in client.guilds:
        # if guild.name == GUILD:
        #     break
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


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    rock_p_s = [
        "rock",
        "paper",
        "scissors",
    ]
    keyword = "!rrat"

    if message.content.startswith(keyword):
        # react to message while preparing response
        await message.add_reaction("⌛")
        parameters = message.content.split(keyword)[-1]
        try:
            parameters = json.loads(parameters)
            if parameters:
                if requests_queue.qsize() > 100:
                    return {"error": "queue full, try again later"}

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
                await message.channel.send(response)
        except Exception as e:
            await message.remove_reaction("⌛", client.user)
            await message.add_reaction("❌")
            await message.channel.send(str(e))
            return


def discord_bot_run():
    client.run(TOKEN)


if __name__ == "__main__":
    import threading
    import multiprocessing

    thread_discord_bot = threading.Thread(target=discord_bot_run)
    thread_discord_bot.start()
    # discord_bot_run()


# import signal


# def signal_handler(sig, frame):
#     global app_running
#     stop_event.set()
#     exit(0)


# signal.signal(signal.SIGINT, signal_handler)
