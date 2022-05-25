import quart
import os
import base64
import time
import utils
import datetime

accounts = quart.Blueprint(
    "accounts",
    __name__,
    url_prefix = "/api/accounts",
)

password_encoder = os.environ.get("password_encoder") #eval code to encode password, defaults to None
password_decoder = os.environ.get("password_decoder") # eval code to decode password, defaults to None


def encode_password(password: str) -> str:
    return password if not password_encoder else eval(
        password_encoder,
        {"password": password}
    )

def decode_password(password: str):
    return password if not password_decoder else eval(
        password_decoder,
        {"password": password}
    )

@accounts.route("/<username>")
async def root(username):
    async with accounts.app.account_db.execute(
        """SELECT discord_id, username, display_name, bio, pfp, created_at, email, password, api_key
        FROM accounts
        WHERE username = ?
        """,
        (username.lower(),)
    ) as cursor:
        rt = await cursor.fetchone()
        if not rt:
            utils.abort_json(404, {"message": f"Account with username {username} doesn't exist."})
        ret = {
            "discord_id": rt[0],
            "username": rt[1],
            "display_name": rt[2],
            "bio": rt[3],
            "pfp": rt[4],
            "created_at": utils.parse_dt(rt[5])
        }
        req = quart.request
        if req.headers.get("api_key") == rt[8]:
            ret["email"] = rt[6]
            ret["password"] = decode_password(rt[7])
            ret["api_key"] = rt[8]
        return ret

@accounts.route("/images", defaults = {"img_name": None})
@accounts.route("/images/<img_name>", methods = ("GET", "POST",))
async def acc_images(img_name: str = None):
    db = accounts.app.account_db
    req = quart.request
    if 'api_key' not in req.headers:
        utils.abort_json(401, {"message": "API key is required to access this endpoint!"})
    async with db.execute(
        """SELECT username, api_key
        FROM accounts
        WHERE api_key = ?
        """,
        (req.headers['api_key'])
    ) as c:
        c = await c.fetchone()
        if not c:
            utils.abort_json(403, {"message": "Invalid API key!"})
        username = c[0]
    if req.method == "POST":
        d = None
        ct = req.headers.get("Content-Type")
        if ct == "application/json":
            d = await req.get_json(silent = True)
        elif ct == "application/x-www-form-urlencoded":
            d = (await req.form).to_dict()
        if not d:
            utils.abort_json(400, {"message": "Expected content-type to be of eitherapplication/json or of type application/x-www-form-urlencoded."})
        img_name = str(d["name"])
        if len(img_name) > 20:
            utils.abort_json(400, {"message": "Image name can only have a maximum of 20 characters."})
        a_ex = (".jpg", ".jpeg", ".png")
        if not img_name.endswith(a_ex):
            utils.abort_json(400, {"message": f"File extension {img_name.split('.')[-1]!r} is not recognized!"})
        img_bytes = d["image_data"]
        if len(img_bytes) > 55242880:
            utils.abort_json(400, {"message": "Image size cannot be larger than 5 MegaBytes / 55242880 Bytes."})
        created_at = utils.format_dt()

        async with db.execute(
            """SELECT img_bytes
            FROM image_uploader
            WHERE username = ?
            """,
            (username,),
        ) as c:
            c = await c.fetchall()
            if not c:
                pass
            b = bytearray().extend((_[0] for _ in c))
            if len(b) > 52428800:
                utils.abort_json(403, {"message": "You have reached your upload limit of 50mb!"})

        async with db.execute(
            """INSERT INTO image_uploader
            (username, name, img_bytes, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                username,
                img_name,
                img_bytes,
                created_at,
            )
        ):
            await db.commit()
            return quart.Response('{"message": "Success!"}', 200, content_type = "application/json")
    elif req.method == "GET":
        async with db.execute(
            """SELECT img_bytes, created_at
            FROM image_uploader
            WHERE username = ? AND name = ?
            """,
            (username, img_name)
        )as data:
            data = await data.fetchone()
            if not data:
                utils.abort_json(404, {"message": "The image was not found on the server!"})
            f = data[0]
            return await quart.send_file(f)

@accounts.route("/create", methods = ("POST",))
async def create_account():
    r"""<div class="endpoint_card">
        <h3> /api/accounts/create </h3>
        Create a CentaurAPI account.
    </div>
    """
    req = quart.request
    h = req.headers
    ct = h.get("Content-Type")
    d = None
    if ct == "application/json":
        d = await req.get_json(silent = True)
    elif ct == "application/x-www-form-urlencoded":
        d = (await req.form).to_dict()
    if not d:
        utils.abort_json(400, {"message": "Expected content-type to be of eitherapplication/json or of type application/x-www-form-urlencoded."})
    discord_id = d["discord_id"]
    try:
        username = d["username"].lower()
        assert (20 >= len(username) > 3), "Number of characters in username must be between 4 & 20"
        assert " " not in username
        assert username not in ("images", "create", "delete", "edit")
        password = d["password"]
        assert (30 >= len(password) >= 8), "Number of characters in password must be between 8 & 30"
        password = encode_password(password)
    except Exception as err:
        utils.abort_json(400, {"message": str(err)})
    email = d["email"]
    api_key = utils.generate_key(discord_id)
    created_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    db = accounts.app.account_db
    async with db.execute(
        """SELECT discord_id
        FROM accounts
        WHERE discord_id = ? OR username = ? OR email = ?
        """,
        (discord_id, username, email)
    ) as acc_check:
        if await acc_check.fetchone():
            utils.abort_json(400, {"message": "A user with existing credentials already exists!"})
    async with db.execute(
        "INSERT INTO accounts (discord_id, username, email, password, created_at, api_key, key_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            discord_id,
            username,
            email,
            password,
            created_at,
            api_key,
            0,
        )
    ):
        await db.commit()
        return {
            "discord_id": discord_id,
            "username": username,
            "email": email,
            "password": decode_password(password),
            "created_at": created_at,
            "api_key": api_key,
            "key_type": 0,
        }

@accounts.route("/edit/<username>")
async def edit_account(username):
    return utils.abort_json(500, {"message": "Not implemented!"})
    req = quart.request
    h = req.headers
    ct = h.get("Content-Type")
    if ct == "application/json":
        d = await req.get_json(silent = True)
    elif ct == "application/x-www-form-urlencoded":
        d = (await req.form).to_dict()
    if not d:
        quart.abort(400, "Expected content-type to be of either <i> application/json </i> or of type <i> application/x-www-form-urlencoded </i>.")
    k = h.get("api_key")
    if not k:
        utils.abort_json(401, {"message": "Please provide an API key."})
    db = accounts.app.account_db
    async with db.execute(
        """SELECT username, api_key
        FROM accounts
        WHERE api_key = ?
        """,
        (k,)
    ) as acd:
        acd = await acd.fetchone()
        if not acd:
            utils.abort_json(403, {"message": "Invalid API key!"})
        if acd[0] != username:
            utils.abort_json(403, {"message": "You can only edit your own account!"})

@accounts.route("/delete/<username>")
async def delete_account(username):
    db = accounts.app.account_db
    k = quart.request.headers.get("api_key")
    if not k:
        utils.abort_json(401, {"message": "Please provide an API key."})
    async with db.execute(
        """SELECT api_key, key_type
        FROM accounts
        WHERE username = ?
        """,
        (username,)
    ) as cur:
        d = await cur.fetchone()
        if k != d[0]:
            utils.abort_json(403, {"message": "Invalid API key."})
        if d[1] != 0:
            utils.abort_json(400, {"message": "Only free accounts can be deleted."})
    async with db.execute(
        """DELETE FROM accounts
        WHERE username = ?
        """,
        (username,)
    ):
        async with db.execute(
            """DELETE FROM image_uploader
            WHERE username = ?""",
            (username,)
        ):
            await db.commit()
            return quart.Response('{"message": "Success!"}', 204, content_type = "application/json")

accounts.endpoints = root, acc_images, create_account, edit_account, delete_account,

@accounts.before_app_first_request
async def before_app_first_request():
    accounts.app.ratelimiter.set_limit("/api/accounts", 5, 1)
    accounts.app.ratelimiter.set_limit("/api/accounts/create", 1, 2)
    accounts.app.ratelimiter.set_limit("/api/accounts/edit", 1, 2)
    accounts.app.ratelimiter.set_limit("/api/accounts/delete", 1, 2)
    accounts.app.ratelimiter.set_limit("/api/accounts/images", 2, 1)
    
