from datetime import date, datetime
from app.services import classify as C
from app.services import textmine as T
from app.services.etl import timeparse as TP


def test_severity_rules():
    assert C.classify(1, "Node Down", "X has stopped responding")["severity"] == "P1"
    assert C.classify(5, "Node Up", "X is responding again")["severity"] == "P4"
    assert C.classify(10, "Interface Down", "Port 1 Down")["severity"] == "P2"
    assert C.classify(58, "Group Critical", "Group X is in a Critical state due to member status")["severity"] == "P3"


def test_category_name_first():
    # The message mentions a UPS port, but the event is an interface event.
    assert C.category_of("Interface Down", "Port 24 Gigabit - Smart APC UPS Management Down") == "interface"
    assert C.category_of("UPS On Line", "UPS Status changed to 'On Line'") == "power"
    assert C.category_of("Rogue AP Detected", "Thin AP disassociated") == "wireless"


def test_transition_last_word_wins():
    assert C.transition_of("Interface Status Changed", "BGP primary state changed to DOWN. Secondary failover active.") == "down"
    assert C.transition_of("Interface Up", "Uplink restored") == "up"
    assert C.transition_of("Interface Down", "Uplink to Edge Router Down") == "down"  # "Uplink" is not "up"


def test_pair_keys_match_down_and_up():
    k1 = C.pair_key("sw1", "Interface Down", "sw1 - Port TenGigabitEthernet1/0/1 - Uplink Down")
    k2 = C.pair_key("sw1", "Interface Up", "sw1 - Port TenGigabitEthernet1/0/1 - Uplink Restored")
    assert k1 == k2 == "sw1|if:tengigabitethernet1/0/1"


def test_site_extraction():
    assert T.site_from_device("0412-Dallas-TX-CoreSW-01") == "0412"
    assert T.site_from_device("feisw030.ustxhouston1502.int.wolseley.com") == "1502"
    assert T.sites_in_text("FEI 412\nFEI 0412 and 1965-Cookeville-TN") == ["0412", "1965"]
    assert T.site_label_from_device("3728-Santa-Clara-CA-N2248-X1-30") == ("Santa Clara", "CA")


def test_ips_and_resolution():
    assert T.ips_in_text("edge router at 10.170.80.1. Next 10.141.82.XXX") == ["10.170.80.1"]
    notes = "10-09-2026 09:24:00 - Switch rebooted cleanly; link UP.\n10-09-2026 09:17:30 - Dispatched on-site engineer."
    assert T.resolution_summary(None, notes, is_open=False).startswith("Switch rebooted")


def test_timestamp_formats():
    assert TP.parse_moment("19-05-2026 20:00", True) == (date(2026, 5, 19), 72000)
    assert TP.parse_moment("2026-05-19T20:00:05Z")[0] == date(2026, 5, 19)
    assert TP.parse_moment("May 19, 2026 08:00 PM") == (date(2026, 5, 19), 72000)
    assert TP.parse_moment("46161.5")[0] == date(2026, 5, 19)  # Excel day number
    assert TP.parse_moment("06/24/2026 21:22 PM")[1] == 21 * 3600 + 22 * 60  # 24-hour time with a stray PM
    assert TP.parse_moment("06/24/2026 21:22 AM")[1] is None  # contradictory


def test_date_order_detection():
    assert TP.detect_order(["19-05-2026 20:00", "01-05-2026 10:00"])["day_first"] is True
    assert TP.detect_order(["05-19-2026 20:00", "05-01-2026 10:00"])["day_first"] is False
    # No value above 12: the reading with the tighter span wins (1-3 May, not 5 Jan-5 Mar).
    assert TP.detect_order(["01-05-2026 10:00", "03-05-2026 10:00"])["day_first"] is True
    assert TP.detect_order(["13-05-2026", "05-14-2026"])["mixed"] is True


def test_bad_timestamps_are_explained():
    now = datetime(2026, 10, 9, 12, 0)
    reasons = {raw: TP.check(*TP.parse_moment(raw, True), raw, now) for raw in
               ("", "20:00:04", "31-02-2026 10:00", "01-01-1999 10:00", "01-01-2030 10:00", "19-05-2026 20:00")}
    assert reasons == {"": "Missing timestamp", "20:00:04": "Time without a date", "31-02-2026 10:00": "Invalid date",
                       "01-01-1999 10:00": "Date before 2000", "01-01-2030 10:00": "Date in the future", "19-05-2026 20:00": None}


def test_stated_incident_start():
    assert T.stated_start("Switch down | FEI0609/2800 | Start time: 07/08/26 1:19 AM | IDF down") == "07/08/26 1:19 AM"
    assert T.stated_start("start time : 07/04/2026 17:04:33") == "07/04/2026 17:04:33"
    assert T.stated_start("Router rebooted, no times given") is None
