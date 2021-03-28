#!venv/bin/python
import discord
import os
import re
import json
import asyncio

from google.cloud import translate_v2 as translate


class DiscordTranslatorBotClient(discord.Client):
    _available_languages = {}
    _flags = {}
    _tr_prefix: str = ""
    _config_prefix: str = ""
    _config_prefix_re = None
    _prefix_re = None
    _translate_client = None
    _save_path = ""

    _servers_config = {}

    def __init__(self, tr_prefix: str = "\?", save_path="db.json"):
        self._tr_prefix = tr_prefix
        self._config_prefix = "tr"+self._tr_prefix
        self._config_prefix_re = re.compile(
            r"^"+self._config_prefix+"([a-z]+)"
        )
        self._prefix_re = re.compile(r"^"+self._tr_prefix+"([a-z]{2})\s")
        self._save_path = save_path
        self._load_db()

        super().__init__()

    def _get_server_config(self, server_id: str, param: str) -> any:
        if not server_id in self._servers_config or not param in self._servers_config[server_id]:
            return None
        return self._servers_config[server_id][param]

    def _set_server_config(self, server_id: str, param: str, value: any) -> bool:
        if not server_id in self._servers_config:
            self._servers_config[server_id] = {}
        self._servers_config[server_id][param] = value
        self._save_db()

    def _save_db(self):
        json.dump(self._servers_config, open(self._save_path, "w"))

    def _load_db(self):
        self._servers_config = json.load(open(self._save_path, "r"))

    async def _manual_translate(self, message):
        match = self._prefix_re.match(message.content)
        if not match:
            return

        lang_code = match.group(1)
        if not lang_code in self._available_languages:
            await message.channel.send(f"Unrecognized language code {lang_code}")
            return

        translated = self._translate(message.content[3:], lang_code)
        if translated is not None:
            reply_msg = await message.reply(translated)

    async def _config(self, message) -> bool:
        match = self._config_prefix_re.match(message.content)
        if not match:
            return False

        cmd = match.group(1)
        if cmd == "timeout":
            await self._config_timeout(message)
        elif cmd == "auto":
            await self._config_auto_tr(message)
        return True

    # checks every message if needs translation
    async def _auto_translate(self, message) -> bool:
        user_id = str(message.author.id)
        guild_id = str(message.guild.id)
        activated_users = self._get_server_config(guild_id, "activated_users")

        if activated_users is None or not user_id in activated_users or not activated_users[user_id]["active"]:
            return False

        lang_code = activated_users[user_id]["target_lang_code"]
        translated = self._translate(message.content, lang_code)
        if translated is None:
            return True

        await message.reply(translated)
        return True

    # timeout {duration}
    async def _config_timeout(self, message) -> bool:
        guild_id = str(message.guild.id)

        parts = message.content.split()
        try:
            timeout = int(parts[1])
            self._set_server_config(guild_id, "timeout", timeout)
            await message.channel.send(f"Set auto destruction timer to {timeout} s")
            return True
        except:
            pass

    # auto on/off {lang_code}
    async def _config_auto_tr(self, message) -> bool:
        user_id = str(message.author.id)
        guild_id = str(message.guild.id)

        parts = message.content.split()
        if len(parts) < 2:
            return False

        activated_users = self._get_server_config(guild_id, "activated_users")
        if activated_users is None:
            activated_users = {}

        if not user_id in activated_users:
            activated_users[user_id] = {
                "target_lang_code": "",
                "active": False
            }

        if not parts[1] in ["on", "off"]:
            return False

        activated_users[user_id]["active"] = parts[1] == "on"
        if len(parts) > 2:
            lang_code = parts[2]
            if not lang_code in self._available_languages:
                activated_users[user_id]["active"] = False
                await message.channel.send(f"Unrecognized language code {lang_code}")
                return
            activated_users[user_id]["target_lang_code"] = lang_code
            await message.channel.send(f"Turn {parts[1]} translation to {self._available_languages[lang_code]} for {message.author.nick}")
        self._set_server_config(guild_id, "activated_users", activated_users)
        return True

    def init_translator(self):
        self._translate_client = translate.Client()
        self.available_languages = self._translate_client.get_languages()

    def load_flags(self, path: str):
        self._flags = json.load(open(path, "r"))

    def _translate(self, text: str, target_language_code: str):
        target_language_code = target_language_code.lower()
        if self._translate_client is None:
            print("_translate_client is not initialised")
            return
        result = self._translate_client.translate(
            text,
            target_language=target_language_code
        )
        if result["detectedSourceLanguage"] == target_language_code:
            return None
        return result["translatedText"]

    @property
    def available_languages(self):
        return self._available_languages

    @available_languages.setter
    def available_languages(self, val: list):
        res = {}
        for lang in val:
            res[lang["language"]] = lang["name"]
        self._available_languages = res

    async def on_ready(self):
        print('Logged on as', self.user)

    async def on_reaction_add(self, reaction, user):
        guild_id = str(reaction.guild.id)
        if not reaction.emoji in self._flags:
            return

        lang = self._flags[reaction.emoji]

        translated = self._translate(reaction.message.content, lang["code"])
        reply_msg = await reaction.message.reply(translated)

        remove_timeout = self._get_server_config(guild_id, "timeout")
        await reply_msg.delete(delay=remove_timeout)

        await asyncio.sleep(remove_timeout)
        await reaction.clear()

    async def on_message(self, message):
        if message.author == self.user:
            return

        if await self._config(message):
            return
        if await self._manual_translate(message):
            return
        if await self._auto_translate(message):
            return


if __name__ == "__main__":
    discord_client = DiscordTranslatorBotClient()
    discord_client.init_translator()
    discord_client.load_flags("./flags.json")
    discord_client.run(os.getenv('DISCORD_TOKEN'))
