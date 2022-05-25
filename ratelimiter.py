import quart
import typing
import asyncio

class Ratelimiter:

    def __init__(self, app: quart.Quart):
        self.app: quart.Quart = app
        self.key_types: typing.Dict[str, typing.Any] = {}
        self.global_max: int = 50
        self.globals: typing.Dict[str, int] = {}
        self.rules: typing.Dict[str, typing.Tuple[int, int]] = {}
        self.cache: typing.Dict[str, typing.Dict[str, int]] = {}

    def set_limit(self, path, limit, per = 1):
        self.rules[path] = (limit, per)

    async def process_request(self, path: str, api_key: str):
        if path not in self.rules: return None
        if path not in self.cache:
            self.cache[path] = {api_key: self.rules[path][0]}
        if api_key not in self.key_types:
            async with self.app.account_db.execute(
                """SELECT key_type
                FROM accounts
                WHERE api_key = ?
                """,
                (api_key,)
            ) as cur:
                d = await cur.fetchone()
                self
                if not d: return
                kt = d[0]
                self.key_types[api_key] = kt
                if kt == 10:
                    return
        else: kt = self.key_types[api_key]
        if api_key in self.globals:
            if self.globals[api_key] < 1:
                return "You have reached the global ratelimit!"
        path = path.split("?")[0]
        if api_key in self.cache[path]:
            if (self.cache[path][api_key] * (kt + 1)) < 1:
                return "You have reached the ratelimit for this path!"
        else:
            self.cache[path][api_key] = self.rules[path][0]
        self.globals[api_key] = self.globals[api_key] - 1
        self.cache[path][api_key] = self.cache[path][api_key] - 1
        asyncio.create_task(self.update_cache(api_key, self.rules[path][1]))
        return None

        async def update_cache(self, api_key, st):
            await asyncio.sleep(st)
            self.globals[api_key] = self.globals[api_key] + 1
            self.cache[path][api_key] + self.cache[path][api_key] + 1
