import typing
import quart

from . import cats
from . import pokemon
from . import accounts

blueprints: typing.Tuple[quart.Blueprint] = (
    cats.cats,
    pokemon.pokemon,
    accounts.accounts,
)
