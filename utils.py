import quart
import typing
import functools
import asyncio
import json
import time
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

@async_function
def send_json(status_code: int, data: typing.Union[typing.Dict[str, typing.Any], typing.List[typing.Any]]) -> quart.Response:
    return quart.Response(json.dumps(data), status_code, content_type = "application/json")

def abort_json(status_code: int, data: typing.Union[typing.Dict[str, typing.Any], typing.List[typing.Any]]):
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


class Flags:

    __slots__ = (
        "__items__",
        "__settings__",
        "value",
    )

    __items__: typing.Dict[str, int]
    __settings__: typing.Dict[str, typing.Any]

    def __init__(self, value: int = 0, **flags):
        self.value: int = value
        for flag, toggle in flags.items():
            if flag in self.__items__:
                self._apply(flag, toggle)

    def _apply(self, flag: str, toggle: bool):
        value = self.__items__[flag]

        if toggle is True:
            self.value |= value
        elif toggle is False:
            self.value &= ~value
        else:
            raise TypeError(f"{flag} must be a bool, not {toggle.__class__!r}")

    def _get_enabled_flags(self):
        return [f for f in self.__items__.keys() if getattr(self, f, False)]

    def __init_subclass__(cls):
        items = dict()

        for k, v in vars(cls).items():
            if (k.startswith("_")) or (not isinstance(v, int)):
                continue
            else:
                items[k] = v
                setattr(cls, k, Flag(k, v))

        cls.__items__ = items

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} value={self.value}>"

    def __int__(self) -> int:
        return self.value

    def __iter__(self) -> typing.Iterator[typing.Tuple[str, bool]]:
        for k in self.__items__:
            yield k, getattr(self, k)

    __eq__ = (
        lambda self, other: isinstance(other, self.__class__)
        and self.value == other.value
    )
    __ne__ = (
        lambda self, other: isinstance(other, self.__class__)
        and self.value != other.value
    )
    __lt__ = (
        lambda self, other: isinstance(other, self.__class__)
        and self.value < other.value
    )
    __le__ = (
        lambda self, other: isinstance(other, self.__class__)
        and self.value <= other.value
    )
    __gt__ = (
        lambda self, other: isinstance(other, self.__class__)
        and self.value > other.value
    )
    __ge__ = (
        lambda self, other: isinstance(other, self.__class__)
        and self.value >= other.value
    )


class Flag:
    __slots__ = ("name", "value")

    def __init__(self, name: str, value: int):
        self.name = name
        self.value = value

    def __get__(
        self, instance: typing.Optional[Flags], owner: typing.Type[Flags]
    ) -> typing.Union[int, bool]:
        if instance is None:
            return self.value

        return instance.value & self.value > 0

    def __set__(self, instance: typing.Optional[Flags], toggle: bool) -> None:
        if instance is None:
            raise AttributeError(
                "Cannot set this attribute on non-instansiated Flags class."
            )

        instance.apply(self.name, toggle)
