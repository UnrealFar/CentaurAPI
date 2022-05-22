import quart
import utils
import typing
import os
import io

CATS = os.listdir("data/images/cats")

cdn = quart.Blueprint(
    "cdn",
    __name__,
    url_prefix = "/cdn",
)

@cdn.route("/cats/<image_name>")
async def cats(image_name: str):
    filename = f'data/images/cats/{image_name}'
    try:
        f = await utils.aopen(filename, "rb")
    except FileNotFoundError:
        utils.abort_json(404, "Requested file was not found on the server!")
    return await quart.send_file(f)
