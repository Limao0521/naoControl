# -*- coding: utf-8 -*-
"""Robot-local safety checks that never depend on the cloud."""


class SafetySupervisor(object):
    def __init__(self, facade, minimum_battery=30):
        self.facade = facade
        self.minimum_battery = minimum_battery

    def check_intelligent_entry(self):
        reasons = []
        battery = self.facade.get_battery_level()
        if battery is None or battery < self.minimum_battery:
            reasons.append("battery_below_minimum")
        return (not reasons, reasons)

    def emergency_stop(self, reason):
        self.facade.stop_move()
        self.facade.stop_all_behaviors()
        return {"status": "stopped", "reason": reason}
