# Eclair#2494
The CRK Eclair Discord Bot!
  
https://eclair.community/add-bot

https://discord.gg/r6ZQFcRUK7

## Features
- Topping Optimization
- Stat Math
- Gacha Simulator
- & More!

## Contributing
**We welcome any and all contributions, whether that's code or issues, everything is valuable**
  
If you have any questions, please don't hesitate to reach out on [[Discord]](https://discordapp.com/users/everym4n/)

## Setup
1. Rename `.env.template` to `.env`, fill in API token
2. `poetry install`
3. `poetry run python topping_bot/bot.py` OR `./run`

## Config
1. In `config.yaml`, specify `img-dump` to a channel id the bot has access to. It will use this channel to temporarily
upload images (i.e. inventories)
2. Rename `guilds/guilds.yaml.template` to `guilds/guilds.yaml`, specify values for your guild
3. Change `debug` value in `config.yaml` to a valid guild specified in `guilds.yaml`

## Debug
1. Add `DEBUG_BOT=True` to `.env`
2. Run with `poetry run python topping_bot/bot.py`

## Further Documentation
Please see `docs` for more info on how certain aspects of the bot works