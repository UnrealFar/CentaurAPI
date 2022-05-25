import os

os.system("python -m pip install -r requirements.txt")

import quart
# import discode #for later use
import aiohttp
import asyncio
import time
import aiosqlite

import utils
import ratelimiter
import cdn

app = quart.Quart("CentaurAPI")
app.html_files = html_files = {}
app.is_setup: bool = False

#change this if ur hosting this urself
app.base_url = "https://centaurs.live"
app.owner_username = "unrealfar" 
app.owner_email = "unrealreply@yahoo.com"
app.owner_password = os.environ["password"]
app.email_app_password = os.environ["email_app_password"]
app.secret_key = os.environ['secret_key'].encode()

app.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
app.ratelimiter: ratelimiter.Ratelimiter = ratelimiter.Ratelimiter(app)


app.config["dsc_client_id"] = str(os.environ.get("dsc_client_id"))
app.config["dsc_client_secret"] = str(os.environ.get("dsc_client_secret"))
app.config["login_redirect_url"] = os.environ.get("login_redirect_url")
app.config["ver_link_gen"] = os.environ["ver_link_gen"]
app.config["ver_link_dec"] = os.environ["ver_link_dec"]

app.register_blueprint(cdn.cdn)

import endpoints

for _bp in endpoints.blueprints:
    app.register_blueprint(_bp)
    _bp.app = app


async def setup():
    if app.is_setup is True:
        return
    print("Setting up!")
    app.client_session = aiohttp.ClientSession()
    app.account_db = await aiosqlite.connect(
        "data/accounts/accounts.sqlite"
    )
    async with app.account_db.execute(
        """CREATE TABLE IF NOT EXISTS accounts 
        (discord_id BIGINT, username TEXT, display_name TEXT, password TEXT, bio TEXT, pfp TEXT, email TEXT, created_at DATETIME, api_key TEXT, key_type TINYINT)
        """
    ):
        async with app.account_db.execute(
            """CREATE TABLE IF NOT EXISTS image_uploader
            (username TEXT, name TEXT, img_bytes LONGBLOB, created_at DATETIME)
            """
        ): await app.account_db.commit()
    app.pokemon_db = await aiosqlite.connect("data/pokemon/pokemon.sqlite")
    async with app.pokemon_db.execute(
        """CREATE TABLE IF NOT EXISTS pokemon
        (id INT, name TEXT, description LONGTEXT, height INT, weight INT, rarity INT, capture_rate INT, types LONGTEXT, abilities LONGTEXT, moves LONGTEXT, base_exp INT, hp INT, attack INT, defense INT, special_attack INT, special_defense INT, speed INT)
        """
    ): await app.pokemon_db.commit()
    asyncio.create_task(keep_alive_task())
    app.is_setup = True
    print("Done setting up!")


@app.route("/ping")
async def ping_page():
    return "pong!"

@app.route("/")
async def home():
    tk = quart.session.get("user_token")
    if not tk:
        return await quart.render_template("logged_out.html")
    async with app.client_session.get(
        f"https://discord.com/api/v10/users/@me",
        headers = {"Authorization": f"Bearer {tk}"}
    ) as resp:
        if resp.status != 200:
            ref = quart.session["refresh_token"]
            async with app.client_session.get(
                "https://discord.com/api/v10/oauth2/token",
                data = {
                    "client_id": app.config["dsc_client_id"],
                    "client_secret": app.config["dsc_client_secret"],
                    "grant_type": "refresh_token",
                    "refresh_token": ref,
                }
            ) as r:
                if r.status != 200:
                    return quart.redirect("discord_login")
                rj = await r.json()
                quart.session["user_token"] = rj["access_token"]
                quart.session["refresh_token"] = rj["refresh_token"]
        ud = await resp.json()
        dsc_id = int(ud["id"])
        async with app.account_db.execute(
            """SELECT username, display_name, api_key
            FROM accounts
            WHERE discord_id = ?
            """,
            (dsc_id,)
        ) as acc_cursor:
            acct = await acc_cursor.fetchone()
            if not acct:
                return quart.redirect(quart.url_for("signup_page"))
            quart.session["api_key"] = acct[2]
            acc = {
                "discord_id": dsc_id,
                "username": acct[0],
                "display_name": acct[1],
            }
            return await quart.render_template(
                "index.html",
                app = app,
                quart = quart,
                account = acc,
                logged_in = True,
            )

@app.route("/profile")
async def profile_page():
    api_key = quart.session.get("api_key")
    async with app.account_db.execute(
        """SELECT username, display_name, bio, pfp, email, created_at
        FROM accounts
        WHERE api_key = ?
        """,
        (api_key,)
    ) as acc:
        acc = await acc.fetchone()
        if not acc:
            return quart.redirect("discord_login")
        acc = {
            "username": acc[0],
            "display_name": acc[1],
            "bio": acc[2],
            "pfp": acc[3],
            "email": acc[4],
            "created_at": utils.parse_dt(acc[5])
        }
        return await quart.render_template("profile.html", app = app, quart = quart, account_json = acc)

@app.route("/api_key", methods = ("GET", "PATCH"))
async def api_key_page():
    req = quart.request
    ses = quart.session
    if req.method == "GET":
        key = ses.get("api_key")
        if not key:
            quart.abort_json(401, {"message": "Please log in first!"})
        return {"api_key": key}
    elif req.method == "PATCH":
        old_key = req.headers.get("api_key")
        new_key = utils.generate_key(utils.decode_key(old_key)["discord_id"])
        db = app.acount_db
        async with db.execute(
            """SELECT api_key FROM accounts WHERE api_key = ?
            """
        ) as c:
            if await c.fetchone() == None:
                quart.abort_json(403, {"message": "Invalid API key!"})
        async with db.execute(
            """UPDATE accounts
            SET api_key = ?
            WHERE api_key = ?
            """,
            (new_key, old_key,)
        ):
            await db.commit()
            return {"api_key": new_key}

@app.route("/endpoints")
async def endpoints_page():
    return app.html_files["endpoints.html"].format(
        app = app,
        quart = quart,
    )

@app.route("/verify/<code>")
async def verification_page(code):
    quart.abort(404)
    if code not in app.to_verify:
        return utils.abort_json(404, {"message":"Invalid verification code"})
    app.to_verify.remove(code)
    return quart.redirect("home")
    

@app.route("/signup", methods = ("GET", "POST",))
async def signup_page():
    req = quart.request
    ses = quart.session
    for i in ("email", "password", "username"):
        if i not in req.args:
            return await quart.render_template("signup.html", quart = quart, app = app)
    tk = ses.get("user_token")
    if not tk:
        return quart.redirect(quart.url_for("discord_login"))
    async with app.client_session.get(
        f"https://discord.com/api/v10/users/@me",
        headers = {"Authorization": f"Bearer {tk}"}
    ) as resp:
        if resp.status != 200:
            ref = quart.session["refresh_token"]
            async with app.client_session.get(
                "refresh_token",
                data = {
                    "client_id": app.config["dsc_client_id"],
                    "client_secret": app.config["dsc_client_secret"],
                    "grant_type": "refresh_token",
                    "refresh_token": ref,
                }
            ) as r:
                if r.status != 200:
                    return quart.redirect("discord_login")
                rj = await r.json()
                quart.session["user_token"] = rj["access_token"]
                quart.session["refresh_token"] = rj["refresh_token"]
        ud = await resp.json()
    async with app.client_session.post(
        f"{app.base_url}/api/accounts/create",
        data = {"discord_id": int(ud['id']), "email": req.args["email"], "password": req.args["password"], "username": req.args["username"]}
    ) as d:
        if d.status != 200:
            utils.abort_json(d.status, await d.json())
        d = await d.json()
        quart.session["api_key"] = d["api_key"]
        return quart.redirect(quart.url_for("home"))

@app.route("/discord_login")
async def discord_login():
    return quart.redirect(app.config["login_redirect_url"])

@app.route("/login_callback")
async def login_callback():
    code = quart.request.args.get("code")
    resp = await app.client_session.post(
        "https://discord.com/api/oauth2/token",
        data = {
            "client_id": app.config["dsc_client_id"],
            "client_secret": app.config["dsc_client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "scope": "identify%20email%20guilds",
            "redirect_uri": f"{app.base_url}/login_callback",
        },
    )
    if not (200 <= resp.status < 300):
        quart.abort(resp.status, await resp.json())
    user_token_payload = await resp.json()
    quart.session["user_token"] = user_token_payload['access_token']
    quart.session["refresh_token"] = user_token_payload["refresh_token"]
    
    return quart.redirect(quart.url_for('home'))

@app.before_first_request
async def before_first_request():
    await setup()
    app.html_files["endpoints.html"] = ""

@app.before_request
async def before_request():
    req = quart.request
    ses = quart.session
    api_key = req.headers.get("api_key") or ses.get("api_key")
    rc = await app.ratelimiter.process_request(req.path, api_key)
    if rc: utils.abort_json(403, {"message": rc})
    ses.permanent = True

@app.after_request
async def after_request(response: quart.Response):
    if response.content_type == "application/json":
        req = quart.request
        api_key = req.headers.get("api_key")
        if api_key:
            try:
                r = app.ratelimiter.rules[req.path]
                rem = app.ratelimiter.cache[req.path][api_key]

                response.headers["X-Ratelimit-Total"] = r[0]
                response.headers["X-Ratelimit-Remaining"] = rem
                response.headers["X-Ratelimit-Reset"] = ((r[0] - rem) * r[1])
            except:
                pass
    return response

app.endpoints = ()

async def keep_alive_task():
    while True:
        print("ping!")
        print(await (await app.client_session.get(f"{app.base_url}/ping")).text())
        await asyncio.sleep(300)


asyncio.run(app.run_task(
    host = "0.0.0.0",
    use_reloader = False,
))

