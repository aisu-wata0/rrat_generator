# %%
import logging
from flask import Flask, request, jsonify, make_response
from queue import Queue
import threading

logging.basicConfig(level=logging.INFO)

loggers = [
    logging.getLogger(name).setLevel(logging.WARN)
    for name in logging.root.manager.loggerDict
    if name.startswith("discord")
]


app = Flask(__name__)

from consume_requests import requests_queue, stop_event, consume_requests


def _build_cors_prelight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "*")
    response.headers.add("Access-Control-Allow-Methods", "*")
    return response


def _corsify_actual_response(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route("/")
def index():
    return "get completions on GET /completions"


@app.route("/complete", methods=["POST", "OPTIONS"])
def complete():
    if request.method == "OPTIONS":  # CORS preflight
        return _build_cors_prelight_response()
    elif request.method == "POST":  # The actual request following the preflight
        content = request.json
        if content:
            if requests_queue.qsize() > 100:
                return {"error": "queue full, try again later"}

            response_queue = Queue()

            requests_queue.put((content, response_queue))

            return _corsify_actual_response(jsonify({**response_queue.get()}))
    else:
        raise RuntimeError(
            "Weird - don't know how to handle method {}".format(request.method)
        )


# %%


thread_consume_requests = threading.Thread(target=consume_requests)
thread_consume_requests.start()

if __name__ == "__main__":
    kwargs_app = {"port": 5000, "host": "0.0.0.0"}
    thread_app = threading.Thread(target=app.run, kwargs=kwargs_app)
    thread_app.start()

from discord_bot import discord_bot_run

thread_discord_bot = threading.Thread(target=discord_bot_run)
thread_discord_bot.start()


import signal


def signal_handler(sig, frame):
    logging.info("Keyboard interrupt")
    stop_event.set()
    thread_consume_requests.join()
    exit(0)


signal.signal(signal.SIGINT, signal_handler)
