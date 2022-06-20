import logging
import traceback
import threading
import time
import json
from queue import Queue, Empty

from gpt_local_settings import *

requests_queue = Queue()
stop_event = threading.Event()


def consume_requests():
    try:
        start = time.time()
        from gpt_local import get_completions, default_kwargs

        logging.info(f"Models initialized in {time.time() - start:.06}s")

        total_batch = 1
        while not stop_event.is_set():
            all_g = []
            all_context = []
            all_top_p = []
            all_top_k = []
            all_temperature = []
            all_max_length = []
            all_q = []
            while len(all_context) < total_batch:
                if stop_event.is_set():
                    return
                try:
                    o, q = requests_queue.get(block=False)
                    try:
                        g = {
                            "context": str(o["context"]),
                            "max_length": int(
                                o.get("max_length", default_kwargs["max_length"])
                            ),
                            "top_p": float(o.get("top_p", default_kwargs["top_p"])),
                            "top_k": int(o.get("top_k", default_kwargs["top_k"])),
                            "temperature": float(
                                o.get("temperature", default_kwargs["temperature"])
                            ),
                        }
                        all_g.append(g)
                        all_context.append(g["context"])
                        all_max_length.append(g["max_length"])
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
                                "traceback": traceback.format_exc(),
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
                all_max_length.append(1)
                all_top_p.append(1)
                all_top_k.append(1)
                all_temperature.append(1)

            logging.info(f"get_completions {all_context}")
            try:
                output = get_completions(
                    all_context,
                    # the below doesn't work with batched requests
                    max_length=all_max_length[0],
                    top_p=all_top_p[0],
                    top_k=all_top_k[0],
                    temperature=all_temperature[0],
                )
            except Exception as e:
                output = {
                    "completion": ["" for _ in all_context],
                    "sentiment": [str(e) for _ in all_context],
                }
                logging.exception(e)

            for o, s, q, g in zip(
                output["completion"], output["sentiment"], all_q, all_g
            ):
                q.put(
                    {
                        "completion": o,
                        "sentiment": s,
                    }
                )
                # append done completions in jsonl file
                g["completion"] = o
                g["sentiment"] = s
                g["model"] = model_name
                with open("done.jsonl", "a") as f:
                    f.write(json.dumps(g) + "\n")

            logging.info(f"completion done in {time.time() - start:06}s")
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt")
        exit(0)
