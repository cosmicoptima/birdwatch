from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
import logging
from math import ceil
import random
import re
import requests
from requests.exceptions import ProxyError, Timeout
from typing import Optional

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

    proxy_list = [row.split(" => ") for row in proxy_list]
    proxies = [proxy for proxy, status in proxy_list if status == "success"]

    return proxies


PROXY_LIST = get_proxies()


class BirdwatchException(Exception):
    def __init__(self, message, log_message=None):
        super().__init__(message)

        if log_message is not None:
            open("exception.log", "w").write(log_message)


@dataclass
class Tweet:
    text: str
    user_id: int

    likes: Optional[int] = None
    retweets: Optional[int] = None
    quotes: Optional[int] = None
    replies: Optional[int] = None


class Scraper:
    def __init__(self):
        self.proxies = get_proxies()
        self.current_proxy = None

        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": BEARER, "x-guest-token": self.get_token()}
        )

    def get_token(self):
        # this is the only method that benefits from scraper being an object
        # a separate scraper session object might be better

        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        session.proxies["http"] = self.current_proxy

        match = self.request_token(session)

        # most proxies don't work, so find a good one and stick with it
        if match is None:
            if self.proxy is None:
                logging.warning("Switching to proxy")

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
            "include_quote_count": True,
            "include_reply_count": True,
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

    def from_query_raw(self, q, pages):
        data, cursor = self.get_page(q, None)

        for _ in range(pages - 1):
            next_page, cursor = self.get_page(q, cursor)

            for category in data:
                data[category].update(next_page[category])

        return data

    def from_query(self, q, count=1000):
        """Returns tweets that match a Twitter search query."""
        pages = ceil(count / 100)
        data = self.from_query_raw(q, pages)

        return [self.to_object(tweet) for tweet in data["tweets"].values()]

    def to_object(self, tweet):
        return Tweet(
            tweet["full_text"],
            tweet["user_id"],
            likes=tweet["favorite_count"],
            retweets=tweet["retweet_count"],
            quotes=tweet["quote_count"],
            replies=tweet["reply_count"],
        )

    def from_user_raw(self, username, pages):
        return self.from_query_raw(f"from:{username}", pages)

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
            self.to_object(tweet)
            for tweet in data["tweets"].values()
            if tweet["user_id"] == user_id
        ]

        return tweets

    def from_users(users, count=1000, workers=100):
        """Retrieve and return the tweets of multiple users concurrently."""
        with ThreadPoolExecutor(max_workers=workers) as executor:
            from_user = partial(self.from_user, count=count)

            return executor.map(from_user, users)
