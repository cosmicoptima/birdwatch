from birdwatch import Scraper


def test_init_scraper():
    global scraper
    scraper = Scraper()


def test_from_query():
    scraper.from_query("twitter")


def test_from_user():
    scraper.from_user("jack")
