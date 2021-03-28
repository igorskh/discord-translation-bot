# Discord translation bot

Discord bot for translating messages using Google Translate API.

## Install dependencies
```bash
pip install -r requirements.txt
```

## Configure run
Create run.sh file with the following content to configure environmental variables:
```bash
GOOGLE_APPLICATION_CREDENTIALS="./your_google_auth_file.json" DISCORD_TOKEN={your_discord_token_here} ./bot.py
```

Grant execute permissions and run the script:
```bash
chmod +x run.sh bot.py
./run.sh
```