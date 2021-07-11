import logging
from math import ceil
import random
import re
import requests
from requests.exceptions import ProxyError, Timeout

__all__ = ["init_session", "from_user"]

BEARER = "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
# tried random user agent libraries; they kept generating unsupported browsers
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

SEARCH_URL = "https://api.twitter.com/2/search/adaptive.json"
# some proxies may not support https
TOKEN_URL = "http://twitter.com"

PROXY_LIST = requests.get(
    "https://github.com/TheSpeedX/PROXY-List/raw/master/http.txt"
).text.splitlines()
current_proxy = None


class BirdwatchException(Exception):
    def __init__(self, message, log_message=None):
        super().__init__(message)

        if log_message is not None:
            open("exception.log", "w").write(log_message)


def init_session():
    """Returns a session that can be passed into other functions.

    This probably should not be used if it is possible to reuse an existing session."""
    session = requests.Session()
    session.headers.update({"Authorization": BEARER, "x-guest-token": get_token()})

    return session


def get_token():
    global current_proxy

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "http": current_proxy})

    match = request_token(session)

    # most proxies don't work, so find a good one and stick with it
    if match is None:
        logging.warning("Can't find guest token, finding proxy")
        while True:
            proxy = random.choice(PROXY_LIST)
            session.proxies["http"] = proxy

            try:
                match = request_token(session)
            except (ProxyError, Timeout):
                continue

            if match is not None:
                current_proxy = proxy
                break

    return match.group(1)


def request_token(session):
    response = session.get(TOKEN_URL, timeout=5)
    # i stole this regex from twint, so if it looks wrong it probably is
    return re.search(r'\("gt=(\d+);', response.text)


def get_page(session, q, cursor):
    # counts >100 return 100 anyway
    # without "tweet_mode": "extended", long tweets are truncated
    #         "tweet_search_mode": "live", only the first few pages contain tweets
    params = {
        "q": q,
        "count": 100,
        "cursor": cursor,
        "tweet_mode": "extended",
        "tweet_search_mode": "live",
    }

    response = session.get(SEARCH_URL, params=params)

    # single guest token can only be used so many times
    if response.status_code == 429:
        session.headers["x-guest-token"] = get_token()
        response = session.get(SEARCH_URL, params=params)
    if not response.ok:
        raise BirdwatchException(
            f"Failed with status code {response.status_code}",
            f"Failed with status code {response.status_code}, full text:\n\n{response.text}",
        )

    data = response.json()["globalObjects"]

    # idk wtf i'm doing
    cursor_base = response.json()["timeline"]["instructions"]
    from_loc = lambda l: l["content"]["operation"]["cursor"]["value"]
    try:
        next_cursor = from_loc(cursor_base[0]["addEntries"]["entries"][-1])
    except (IndexError, KeyError):
        next_cursor = from_loc(cursor_base[-1]["replaceEntry"]["entry"])

    return data, next_cursor


def from_user_raw(session, username, pages):
    data, cursor = get_page(session, f"from:{username}", -1)

    for _ in range(pages - 1):
        next_page, cursor = get_page(session, f"from:{username}", cursor)

        for category in data:
            data[category].update(next_page[category])

    return data


def from_user(session, username, count=1000):
    """Returns a user's tweets."""
    pages = ceil(count / 100)
    data = from_user_raw(session, username, pages)

    # raw returned follows/mentions(?) as well before; not sure if it does now
    # if not, most of this is unnecessary
    try:
        user_id = [
            user["id"]
            for user in data["users"].values()
            if user["screen_name"].lower() == username.lower()
        ][0]
    except IndexError:
        all_ids = [user["id"] for user in data["users"].values()]
        raise BirdwatchException(
            "Could not get user ID",
            f"Could not get user ID, all users retrieved:\n\n{all_ids}",
        )

    tweets = [
        tweet["full_text"]
        for tweet in data["tweets"].values()
        if tweet["user_id"] == user_id
    ]

    return tweets
