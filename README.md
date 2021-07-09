# birdwatch

Twitter scraper similar to Twint, but without the bloat.

## usage

birdwatch is currently usable as a Python library.

Create a session with `init_session` then pass it into `from_user` to
get a user's tweets:

	import birdwatch

	session = birdwatch.init_session()
	tweets = birdwatch.from_user(session, "parafactual", count=1000)

`count` defaults to 3200.
