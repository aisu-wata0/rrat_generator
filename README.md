
# Text completion using GPT models

Start a REST API and a Discord Bot by running `python app.py` or `flask run`. Completions processed are saved by default in "log-completions_done.jsonl". To run only the discord bot run `python discord_bot.py`.

But first you need to setup and configure some things.

## Setup

First install `transformers` (https://huggingface.co/docs/transformers/installation). Depending on which version you want. For a quickstart: GPU: `pip install transformers` CPU torch: `pip install transformers[torch]` CPU tensorflow: `pip install transformers[tf-cpu]`

Then `python -r requirements.txt`.

## Configuration

Models are loaded when `gpt_local.py` is imported, it gets its settings from `gpt_local_settings.py`. Most importantly:

* `model_name`: Defines the model you will use, either downloaded from cloud (and cached) or locally. Works as is. There are some models already listed there as possible candidates. More names at  https://huggingface.co/models
* `log_completions_filepath`: The file where all done completions are saved, you can turn this logging off by setting it to `None`.
* `cache_dir`: Where the models downloaded will be saved, setting `None` will use the default dir defined by the `transformers` lib itself, which should be good enough for most people.

### Discord Bot

The Discord bot token should be defined in the enviroment or in a `DISCORD.env` file, the bash command: `printf "DISCORD_TOKEN=${DISCORD_TOKEN}" >> DISCORD.env` for example creates a valid file (provided ${DISCORD_TOKEN} is your token).

## Considerations

The API isn't terribly concerned with possible code injections, it shouldn't be possible as far as I've looked (when loading json from str in python), but the code does return raw error and exception messages to the API user.

You can make bots for other things pretty easily by copying either template from REST or discord.