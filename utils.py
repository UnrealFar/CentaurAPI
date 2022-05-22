import quart
import typing
import functools
import asyncio
import json
import base64
import datetime

def async_function(func: typing.Callable):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()
        if len(kwargs) == 0:
            return await loop.run_in_executor(None, func, *args)
        return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
    return wrapper

@async_function
def run_async(func: typing.Callable, *args, **kwargs):
    return func(*args, **kwargs)

@async_function
def aopen(*args, **kwargs):
    with open(*args, **kwargs) as f:
        return f

def abort_json(status_code: int, data: typing.Union[typing.Dict, typing.List]):
    return quart.abort(quart.Response(json.dumps(data), status_code, content_type = "application/json"))

def generate_key(dsc_id: int) -> str:
    return base64.b64encode(f'{dsc_id}|{round(time.time())}'.encode()).decode()

def decode_key(api_key: str) -> str:
    decoded = base64.b64decode(api_key.encode()).decode().split("|")
    return {'discord_id': decoded[0], 'created_at': decoded[1]}

def format_dt():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def parse_dt(_: str, /):
    return datetime.datetime.strptime(_, "%Y-%m-%d %H:%M:%S")
