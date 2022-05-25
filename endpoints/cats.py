import quart
import random
import cdn

cats = quart.Blueprint(
    "cats",
    __name__,
    url_prefix = "/api/cats",
)

@cats.route("/random")
async def random_cat():
    r"""<div class="endpoint_card">
        <h3> /api/cats/random </h3>
        Returns a random cat image in json format.
    </div>
    """
    url = f"{cats.app.base_url}{quart.url_for('cdn.cats', image_name = random.choice(cdn.CATS))}"
    return {
        "url": url
    }

cats.endpoints = (random_cat,)

@cats.before_app_first_request
async def before_app_first_request():
    cats.app.ratelimiter.set_limit("/api/cats/random_cat", 3, 1)
