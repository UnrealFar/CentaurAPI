import utils


class Types(utils.Flags):
    normal = 1 << 0
    fighting = 1 << 1
    flying = 1 << 2
    poison = 1 << 3
    ground = 1 << 4
    rock = 1 << 5
    bug = 1 << 6
    ghost = 1 << 7
    steel = 1 << 8
    fire = 1 << 9
    water = 1 << 10
    grass = 1 << 11
    electric = 1 << 12
    psychic = 1 << 13
    ice = 1 << 14
    dragon = 1 << 15
    dark = 1 << 16
    fairy = 1 << 17
    unknown = 1 << 18
    shadow = 1 << 19
