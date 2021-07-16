# birdwatch

Twitter scraper similar to Twint, but without the bloat. It also
supports higher rates than snscrape.

Currently birdwatch works well for most use cases, but is a bit
bare-bones and very unstable at higher speeds (eg 100 threads).

## usage

birdwatch is currently usable as a Python library.

Create a scraper object with `Scraper` then call its `from_user`
method to get a user's tweets:

	import birdwatch

	scraper = Scraper()
	tweets = scraper.from_user("parafactual", count=2000)

(`count` defaults to 1000 and is not exact.)

This will return a `Tweet` object with the following attributes:

- `text`
- `user_id`
- `likes`
- `retweets`
- `quotes`
- `replies`
