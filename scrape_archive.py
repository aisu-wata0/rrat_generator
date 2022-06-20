#%%

import urllib.request
import os
import time
import datetime
import logging
import shutil
import math
import re
import pickle
import json
import itertools
import urllib.request
from click import echo
import requests
from bs4 import BeautifulSoup, NavigableString
from urllib.error import HTTPError
import urllib.parse
from pathlib import Path
from threading import Thread
import traceback
from tqdm import tqdm

# %%

# aesthetic customization of the progressbar
tqdm_kwargs = {
    "smoothing": 0.0,
    "position": 0,
    "leave": True,
    "bar_format": "{r_bar} {l_bar}{bar}",
    "dynamic_ncols": True,
    "mininterval": 1 / 60,
    "maxinterval": 1 / 24,
}


# %%
max_backups = 3
backup_dir = "bak"


def removeOldFiles(list_of_files, max_files):
    old_files = list(
        sorted(
            list_of_files,
            key=lambda x: os.stat(x).st_ctime,
            reverse=True,
        )
    )[max_files:]
    for f in old_files:
        os.remove(f)
    return old_files


save_funs = {
    "pickle": (pickle.dump, "wb"),
    "json": (lambda data, f: json.dump(data, f, indent=2), "w"),
}


def save_file(filepath, data, save_fun, backup_dir=backup_dir, max_backups=max_backups):
    """Save data to filepath. Creates backup in `backup_dir` and deletes old backups too keep them at `max_backups`."""
    if isinstance(save_fun, str):
        save_fun = save_funs[save_fun]
    filepath_bak = ""
    if backup_dir:
        backup_dir = Path(filepath).parent / backup_dir
        filepath_bak = (
            str(backup_dir / str(Path(filepath).name))
            + "-"
            + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        )
    try:
        try:
            if backup_dir:
                Path(filepath_bak).parent.mkdir(exist_ok=True)
                shutil.copyfile(filepath, filepath_bak)
                try:
                    removeOldFiles(
                        Path(backup_dir).glob(f"{Path(filepath).name}*"), max_backups
                    )
                except Exception as e:
                    logging.exception(e)
        except FileNotFoundError:
            pass
        if "b" in save_fun[1]:
            with open(filepath, save_fun[1]) as f:
                save_fun[0](data, f)
        else:
            with open(filepath, save_fun[1], encoding="utf8") as f:
                save_fun[0](data, f)
        print("Saved!", filepath)
    except Exception as e:
        if backup_dir:
            shutil.copyfile(filepath_bak, filepath_bak + ".err")
        logging.warning("Exception on saving file ", filepath)
        logging.exception(e)


def save_file_json(filepath, data):
    return save_file(filepath, data, save_fun="json")


def save_file_pickle(filepath, data):
    return save_file(filepath, data, save_fun="pickle")


# %%
# Bypassing Error 403
# User-Agent

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
    # "User-Agent": "Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.17 (KHTML, like Gecko) Chrome/24.0.1312.27 Safari/537.17",
}


def bypassOpen(url):
    response = requests.get(url, headers=headers)
    return response


def bypassRead(address):
    response = bypassOpen(address)
    if response.status_code == 200:
        html = BeautifulSoup(response.content, "html.parser")
        error_string = "404: Page Not Found"
        if html.find(text=error_string) is not None:
            raise HTTPError(address, code=404, msg=error_string, hdrs=None, fp=None)
        return html
    else:
        raise Exception("Error while reading url")


import urllib

board = "vt"
base_url = f"https://archive.alice.al/{board}/"
thread_blacklist = set({1})
# %%
page_num = 1
soup_cache = {}
items = {}
items_new = {}
break_when_no_new_items = False

try:
    while True:
        url = base_url + f"page/{urllib.parse.quote(str(page_num))}"
        print("Getting... ", url)

        soup = None
        if page_num not in soup_cache:
            soup = bypassRead(url)
            soup_cache[page_num] = str(soup)
        else:
            soup = BeautifulSoup(soup_cache[page_num], "html.parser")
        class_str = "post_is_op"
        items_found = soup.find_all("article", class_=class_str)
        if not items_found:
            print("No items found, breaking from loop")
            break
        print("Got ", len(items_found), " items")
        new_items = 0
        for item in items_found:
            item_id = str(item.get("id"))
            if item_id not in items:
                new_items += 1
                items_new[int(item_id)] = None

        page_num += 1
        if break_when_no_new_items:
            if not new_items:
                break

except KeyboardInterrupt as e:
    print("Stopped by keyboard interrupt")
except Exception as e:
    print("Caught exception")
    logging.exception(e)


items = {**items_new, **items}

print(len(items.keys()), " items total,", len(items_new.keys()), " new")

save_file_json(f"items_{board}.json", items)

# %%

re_emoji = r'<\/?(img)[^>]*src="([0-9a-zA-Z\/:\._]+\/)+([0-9a-zA-Z\/:\._]+)">;?|<\/?(span)[^>]*>'
re_emoji = re.compile(re_emoji)

# from here: https://gist.github.com/zmwangx/ad0830ba94b1fd98f428
def text_with_newlines(elem):
    text = ""
    for e in elem.descendants:
        if isinstance(e, str):
            # text += e.strip()
            text += e
        elif e.name == "br" or e.name == "p":
            text += "\n"

    for emoji in reversed(list(re_emoji.finditer(text))):
        if emoji.group(3):
            text = (
                text[: emoji.start()]
                + str(emoji.group(3)).split("_")[1].split(".")[0]
                + text[emoji.end() :]
            )
        else:
            text = text[: emoji.start()] + text[emoji.end() :]
    return text.strip()


json_threads_filename = f"{board}-threads.jsonl"
try:
    num_lines = sum(1 for line in open(json_threads_filename))
except FileNotFoundError:
    num_lines = 0

print(f"{num_lines} lines in file {json_threads_filename}")

thread_images = {}

key_list = list(sorted(items.keys()))
len(key_list)

write_thread = None

pbar = tqdm(total=len(key_list), **tqdm_kwargs)

for item_id in key_list:
    try:
        item_id = int(item_id)
        if (
            item_id in items and items[item_id] is not None
        ) or item_id in thread_blacklist:
            pbar.update(1)
            continue
        url = base_url + f"thread/{urllib.parse.quote(str(item_id))}"
        pbar.set_description(f"get id {item_id}")
        soup = bypassRead(url)
        item = {}
        item["id"] = item_id
        # item["html"] = str(soup)
        subitem_count = soup.find_all(
            "div", {"title": "Post Count / File Count / Posters"}
        )
        if subitem_count:
            subitem_count_s = subitem_count[0].text[1:-1].split("/")
            item["post_count"] = int(subitem_count_s[0].strip())
            item["file_count"] = int(subitem_count_s[1].strip())
            try:
                item["poster_count"] = int(subitem_count_s[2].strip())
            except ValueError:
                item["poster_count"] = 0

        if item["post_count"] == 1:
            items[item_id] = -1
            pbar.update(1)
            continue

        posts = soup.find_all("article", class_="post")
        if posts:
            item["posts"] = []
            post_op = soup.find("article", class_="post_is_op")
            for post in [post_op, *posts]:
                post_item = {}

                post_item["id"] = post.find("a", {"title": "Reply to this post"}).text
                post_item["date"] = post.find("time").get("datetime")

                replies = post.find("span", class_="post_backlink")
                if replies and not isinstance(replies, NavigableString):
                    post_item["replies"] = int(
                        len(replies.find_all("a", {"class": "backlink"}))
                    )
                else:
                    post_item["replies"] = 0

                text = post.find("div", class_="text")
                contents = str(text_with_newlines(text))
                post_item["com"] = contents

                order = ("id", "date", "replies", "com")
                post_point = []
                for key in order:
                    if key in post_item:
                        post_point.append(post_item[key])

                post_extra = {}

                thumb = post.find("img")
                if thumb:
                    md5 = thumb.get("data-md5")
                    post_extra["image"] = md5
                    if md5 and md5 not in thread_images:
                        thread_images[md5] = {
                            "thumb": thumb.get("src"),
                        }
                        image = post.find("a", class_="thread_image_link")
                        if image:
                            thread_images[md5]["image"] = image.get("href")

                post_title = post.find("h2", {"class": "post_title"})
                if post_title and post_title.text:
                    post_extra["post_title"] = post_title.text

                post_author = post.find("span", {"class": "post_author"})
                if post_author and post_author.text != "Anonymous":
                    post_extra["name"] = post_author.text

                trip = post.find("span", {"class": "post_tripcode"})
                if trip and trip.text.strip():
                    post_extra["trip"] = trip.text

                post_point.append(post_extra)

                item["posts"].append(post_point)

            if write_thread:
                try:
                    write_thread.join()
                except Exception as e:
                    pass

            def write_item(item):
                global num_lines
                with open(json_threads_filename, "a", encoding="utf-8") as f:
                    f.write(json.dumps(item) + "\n")
                    items[item_id] = num_lines
                    num_lines += 1

            write_thread = Thread(target=write_item, args=(item,))
            write_thread.start()

            pbar.update(1)
    except KeyboardInterrupt as e:
        print("Stopped by keyboard interrupt")
        break
    except Exception as e:
        print("Caught exception")
        print(f"item_id = {item_id}")
        logging.exception(e)
        break

save_file_json(f"{board}-items.json", items)
save_file_json(f"{board}-images.json", thread_images)
# %%
