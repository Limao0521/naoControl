from nao.scripts.runtime.intelligence.safety_supervisor import SafetySupervisor


class Facade(object):
    def __init__(self, battery):
        self.battery = battery

    def get_battery_level(self):
        return self.battery


def test_intelligent_entry_distinguishes_low_and_unavailable_battery():
    assert SafetySupervisor(Facade(29)).check_intelligent_entry() == (
        False, ["battery_below_minimum"]
    )
    assert SafetySupervisor(Facade(None)).check_intelligent_entry() == (
        False, ["battery_unavailable"]
    )
    assert SafetySupervisor(Facade(30)).check_intelligent_entry() == (True, [])
