# %%
import logging
import traceback
from flask import Flask, request, jsonify, make_response, Response
from markupsafe import escape
from queue import Queue, Empty

app = Flask(__name__)

requests_queue = Queue()


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


@app.route("/completions", methods=["GET"])
def completions():
    json = request.json
    return json


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

            requests_queue.put(
                (
                    {
                        "context": content["context"],
                        "top_p": float(content["top_p"]),
                        "top_k": float(content["top_k"]),
                        "temperature": float(content["temperature"]),
                    },
                    response_queue,
                )
            )

            return _corsify_actual_response(jsonify({**response_queue.get()}))
    else:
        raise RuntimeError(
            "Weird - don't know how to handle method {}".format(request.method)
        )


# %%

if __name__ == "__main__":
    import threading
    import time

    threading.Thread(target=app.run, kwargs={"port": 5000, "host": "0.0.0.0"}).start()

    start = time.time()
    from gpt_local import get_completions, default_kwargs

    logging.info(f"Models initialized in {time.time() - start:.06}s")

    total_batch = 1

    while True:
        all_context = []
        all_top_p = []
        all_top_k = []
        all_temperature = []
        all_q = []
        while len(all_context) < total_batch:
            try:
                o, q = requests_queue.get(block=False)
                try:
                    g = {
                        "context": o["context"],
                        "top_p": o["top_p"]
                        if "top_p" in o
                        else default_kwargs["top_p"],
                        "top_k": o["top_k"]
                        if "top_k" in o
                        else default_kwargs["top_k"],
                        "temperature": o["temperature"]
                        if "temperature" in o
                        else default_kwargs["temperature"],
                        "max_length": o["max_length"]
                        if "max_length" in o
                        else default_kwargs["max_length"],
                    }
                    all_context.append(g["context"])
                    all_top_p.append(g["top_p"])
                    all_top_k.append(g["top_k"])
                    all_temperature.append(g["temperature"])
                    all_q.append(q)
                except Exception as e:
                    logging.exception(e)
                    q.put(
                        {
                            "error": str(e),
                            "request": o,
                        }
                    )
                    continue
            except Empty:
                if len(all_context):
                    break
                else:
                    time.sleep(1)

        start = time.time()
        while len(all_context) < total_batch:
            all_context.append("whatever")
            all_top_p.append(1)
            all_top_k.append(1)
            all_temperature.append(1)

        all_tokenized = []
        all_length = []

        logging.info(f"get_completions {all_context}")
        output = get_completions(
            all_context,
            # TODO: check if this works
            # top_p=all_top_p,
            # top_k=all_top_k,
            # temperature=all_temperature,
        )

        for o, s, q in zip(output["completion"], output["sentiment"], all_q):
            q.put(
                {
                    "completion": o,
                    "sentiment": s,
                }
            )

        logging.info(f"completion done in {time.time() - start:06}s")
