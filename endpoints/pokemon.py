from dataclasses import dataclass
import quart
import utils
import aiosqlite

@dataclass
class Pokemon:
    id: int

pokemon = quart.Blueprint(
    "pokemon",
    __name__,
    url_prefix = "/api/pokemon",
)
 

@pokemon.route("/")
async def route():
    db = pokemon.app.pokemon_db
    utils.abort_json(500, {"message": "Endpoint not implemented."})

pokemon.endpoints = (route,)
