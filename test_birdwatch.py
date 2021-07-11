from birdwatch import *


def test_init_session():
    global session
    session = init_session()


def test_from_user():
    from_user(session, "jack")
