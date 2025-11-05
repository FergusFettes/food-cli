# food-cli

command-line food and calorie tracker using usda fooddata central api

## features

- search usda food database (over 1 million foods)
- log food intake with automatic nutrition calculation
- view daily totals
- quick logging (search + log in one command)
- stores data locally in jsonl format

## installation

```bash
# clone the repo
git clone git@github.com:fergusfettes/food-cli.git
cd food-cli

# install with uv
uv pip install -e .

# or run directly with uv
uv run food --help
```

## setup

get a free api key from https://fdc.nal.usda.gov/api-key-signup/

save it to `~/pa/usda` or set `USDA_API_KEY` environment variable

## usage

```bash
# search for foods
food search "banana"
food search "chicken breast" --count 5

# log a food item by id
food log 123456 --servings 1.5

# quick log (search + log first result)
food quick "scrambled eggs" --servings 2
food quick "apple"

# view today's log
food today
```

## voice integration

for voice-based logging, pipe transcribed text to the quick command:

```bash
# with groq whisper
transcribe_audio.sh | xargs food quick
```

## data storage

food logs are stored in `~/.local/share/food-cli/food_log.jsonl`

each entry is a json line with timestamp, food name, serving size, and macros

## license

mit
