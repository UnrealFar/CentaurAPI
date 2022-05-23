from dataclasses import dataclass
import quart
import typing
import utils
import json
import aiosqlite

from . types import Types
from .abilities import Abilities
from .moves import Moves

pokemon = quart.Blueprint(
    "pokemon",
    "pokemon",
    url_prefix = "/api/pokemon",
)

@pokemon.route("/")
@pokemon.route("/<name_or_id>")
async def root(name_or_id: typing.Optional[str] = None):
    db = pokemon.app.pokemon_db
    if not name_or_id:
        return {"message": "Please provide a valid name or id"}
    name_or_id = str(name_or_id)
    if name_or_id.isdecimal():
        identifier = "id"
    else: identifier = "name"
    async with db.execute(
        f"""SELECT name, height, weight, types, abilities, moves, base_exp, hp, attack, defense, special_attack, special_defense, speed, rarity, capture_rate
        FROM pokemon
        WHERE {identifier} = ?
        """,
        (name_or_id,)
    ) as cur:
        d = await cur.fetchone()
        if not d:
            utils.abort_json(404, {"message": f"Pokemon with {identifier} {name_or_id!r} was not found on the server."})
        stats = {
            "hp": d[7], "attack": d[8],
            "defense": d[9], "special_attack": d[10],
            "special_defense": d[11], "speed": d[12],
        }
        moves = Moves(int(d[5]))._get_enabled_flags()
        moves.append("return")
        rarity = ("normal", "legendary", "mythical")[d[13]]
        return {
            "name": d[0],
            "height": d[1],
            "weight": d[2],
            "types": Types(int(d[3]))._get_enabled_flags(),
            "abilities": Abilities(int(d[4]))._get_enabled_flags(),
            "moves": moves,
            "base_experience": d[6],
            "stats": stats,
            "rarity": rarity,
            "capture_rate": d[14],
        }


@pokemon.route("/search")
async def search():
    req = quart.request
    args = req.args
    limit = args.get("limit", 20)
    if len(args) > 0:
        dc = ("limit",)
        checks = "WHERE " + (" AND ".join((f"{k} = {v!r}" for k, v in args.items() if k not in dc)))
        print(checks)
    else: checks = ""
    async with pokemon.app.pokemon_db.execute(
        f"""SELECT name, height, weight, types, abilities, moves, base_exp, hp, attack, defense, special_attack, special_defense, speed, rarity, capture_rate
        FROM pokemon
        {checks}
        """
    ) as cursor:
        results = []
        for d in await cursor.fetchmany(limit):
            stats = {
                "hp": d[7], "attack": d[8],
                "defense": d[9], "special_attack": d[10],
                "special_defense": d[11], "speed": d[12],
            }
            moves = Moves(int(d[5]))._get_enabled_flags()
            moves.append("return")
            rarity = ("normal", "legendary", "mythical")[d[13]]
            results.append({
                "name": d[0],
                "height": d[1],
                "weight": d[2],
                "types": Types(int(d[3]))._get_enabled_flags(),
                "abilities": Abilities(int(d[4]))._get_enabled_flags(),
                "moves": moves,
                "base_experience": d[6],
                "stats": stats,
                "rarity": rarity,
                "capture_rate": d[14],
            })
        return await utils.send_json(200, results)

pokemon.endpoints = (root,)
