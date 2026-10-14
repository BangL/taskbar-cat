from taskbar_cat.guard import guarded


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def boom():
    raise ValueError("kaputt")


def test_exception_is_swallowed_and_logged():
    logs = []
    f = guarded(boom, log=logs.append, clock=Clock())
    f()
    assert len(logs) == 1
    assert "ValueError: kaputt" in logs[0]


def test_same_error_logged_once_per_minute():
    logs, clock = [], Clock()
    f = guarded(boom, log=logs.append, clock=clock)
    for _ in range(100):
        f()
    assert len(logs) == 1
    clock.t = 61
    f()
    assert len(logs) == 2


def test_different_error_logged_immediately():
    logs, clock = [], Clock()
    errors = iter([ValueError("a"), KeyError("b")])

    def fn():
        raise next(errors)

    f = guarded(fn, log=logs.append, clock=clock)
    f()
    f()
    assert len(logs) == 2


def test_return_value_and_args_pass_through():
    f = guarded(lambda a, b: a + b, log=print, clock=Clock())
    assert f(2, 3) == 5
