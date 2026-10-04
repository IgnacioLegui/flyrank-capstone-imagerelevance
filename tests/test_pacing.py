"""Request pacing with a fake clock: no real sleeping."""

from app.ai.pacing import Pacer


class FakeTime:
    def __init__(self):
        self.now = 1000.0
        self.slept = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def test_first_request_goes_immediately_then_requests_are_spaced():
    t = FakeTime()
    pacer = Pacer(5, clock=t.clock, sleep=t.sleep)  # 5 RPM -> 12 s apart
    assert pacer.wait() == 0
    assert pacer.wait() == 12
    t.now += 5  # 5 s of work happened since the last request started
    assert pacer.wait() == 7
    assert t.slept == [12, 7]


def test_no_wait_when_enough_time_already_passed():
    t = FakeTime()
    pacer = Pacer(60, clock=t.clock, sleep=t.sleep)  # 1 s apart
    pacer.wait()
    t.now += 3
    assert pacer.wait() == 0
    assert t.slept == []
