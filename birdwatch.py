from math import ceil
import random
import re
import requests
from requests.exceptions import ProxyError, Timeout

__all__ = ["Scraper"]

BEARER = "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
# tried random user agent libraries; they kept generating unsupported browsers
# setting a user agent may also do nothing
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

SEARCH_URL = "https://api.twitter.com/2/search/adaptive.json"
# some proxies may not support https
TOKEN_URL = "http://twitter.com"


def get_proxies():
    proxy_list = requests.get(
        "https://github.com/clarketm/proxy-list/raw/master/proxy-list-status.txt"
    ).text.splitlines()[:-6]

    proxy_list = [row.split(": ") for row in proxy_list]
    proxies = [proxy for proxy, status in proxy_list if status == "success"]

    return proxies


PROXY_LIST = get_proxies()


class BirdwatchException(Exception):
    def __init__(self, message, log_message=None):
        super().__init__(message)

        if log_message is not None:
            open("exception.log", "w").write(log_message)


class Scraper:
    def __init__(self):
        self.current_proxy = None
        self.proxies = get_proxies()

        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": BEARER, "x-guest-token": self.get_token()}
        )

    def get_token(self):
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        session.proxies["http"] = self.current_proxy

        match = self.request_token(session)

        # most proxies don't work, so find a good one and stick with it
        if match is None:
            while True:
                proxy = random.choice(self.proxies)
                session.proxies["http"] = proxy

                try:
                    match = self.request_token(session)
                except (ProxyError, Timeout):
                    continue

                if match is not None:
                    self.current_proxy = proxy
                    break

        return match.group(1)

    def request_token(self, session):
        response = session.get(TOKEN_URL, timeout=5)
        return re.search(r'\("gt=(\d+);', response.text)

    def get_page(self, q, cursor):
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

        response = self.session.get(SEARCH_URL, params=params)

        # single guest token can only be used so many times
        if response.status_code == 429:
            self.session.headers["x-guest-token"] = self.get_token()
            response = self.session.get(SEARCH_URL, params=params)
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

    def from_user_raw(self, username, pages):
        data, cursor = self.get_page(f"from:{username}", -1)

        for _ in range(pages - 1):
            next_page, cursor = self.get_page(f"from:{username}", cursor)

            for category in data:
                data[category].update(next_page[category])

        return data

    def from_user(self, username, count=1000):
        """Returns a user's tweets."""
        pages = ceil(count / 100)
        data = self.from_user_raw(username, pages)

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
