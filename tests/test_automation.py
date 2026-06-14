"""Tests for Prism32 automation system."""
import sys, os, time, json, tempfile, shutil, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
exec(open(os.path.join(os.path.dirname(__file__), '..', 'prism32.py')).read().split("if __name__")[0])

_orig_dir = AUTOMATIONS_DIR
_test_dir = None

def setUpModule():
    global _test_dir
    _test_dir = tempfile.mkdtemp(prefix="prism32_test_auto_")
    globals()['AUTOMATIONS_DIR'] = _test_dir

def tearDownModule():
    global _test_dir
    globals()['AUTOMATIONS_DIR'] = _orig_dir
    if _test_dir and os.path.isdir(_test_dir):
        shutil.rmtree(_test_dir, ignore_errors=True)
    _test_dir = None


class TestAutomationCore(unittest.TestCase):

    def test_generate_id_returns_string(self):
        aid = _auto_generate_id("test task")
        self.assertIsInstance(aid, str)
        self.assertTrue(aid.startswith("auto_"))
        self.assertGreater(len(aid), 15)

    def test_generate_id_unique(self):
        a1 = _auto_generate_id("test")
        a2 = _auto_generate_id("test")
        self.assertNotEqual(a1, a2)

    def test_default_scheduled(self):
        auto = _auto_default("desc", "task", "scheduled", interval=60)
        self.assertEqual(auto["type"], "scheduled")
        self.assertEqual(auto["interval_minutes"], 60)
        self.assertEqual(auto["status"], "active")
        self.assertEqual(auto["run_count"], 0)
        self.assertIsNotNone(auto["next_run"])
        self.assertGreater(auto["next_run"], time.time())

    def test_default_oneshot(self):
        due = time.time() + 86400
        auto = _auto_default("desc", "task", "oneshot", due_at=due)
        self.assertEqual(auto["type"], "oneshot")
        self.assertEqual(auto["due_at"], due)
        self.assertIsNone(auto["interval_minutes"])
        self.assertEqual(auto["status"], "active")

    def test_save_and_load(self):
        auto = _auto_default("save test", "do something", "scheduled", interval=60)
        aid = auto["id"]
        automation_save(auto)
        loaded = automation_load(aid)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["id"], aid)
        self.assertEqual(loaded["description"], "save test")
        self.assertEqual(loaded["task"], "do something")

    def test_list(self):
        a1 = _auto_default("first", "task1", "scheduled", interval=60)
        a2 = _auto_default("second", "task2", "oneshot", due_at=time.time()+3600)
        automation_save(a1)
        automation_save(a2)
        all_a = automation_list()
        self.assertEqual(len(all_a), 2)

    def test_list_empty(self):
        # Use a clean temp dir
        old_dir = AUTOMATIONS_DIR
        td = tempfile.mkdtemp(prefix="p32_empty_")
        try:
            globals()['AUTOMATIONS_DIR'] = td
            all_a = automation_list()
            self.assertEqual(all_a, [])
        finally:
            globals()['AUTOMATIONS_DIR'] = old_dir
            shutil.rmtree(td, ignore_errors=True)

    def test_delete(self):
        auto = _auto_default("delete me", "task", "scheduled", interval=60)
        automation_save(auto)
        self.assertIsNotNone(automation_load(auto["id"]))
        self.assertTrue(automation_delete(auto["id"]))
        self.assertIsNone(automation_load(auto["id"]))

    def test_delete_nonexistent(self):
        self.assertFalse(automation_delete("nonexistent_id"))

    def test_load_nonexistent(self):
        self.assertIsNone(automation_load("nonexistent_id"))

    def test_save_updates_same_id(self):
        auto = _auto_default("overwrite", "task", "scheduled", interval=60)
        aid = auto["id"]
        automation_save(auto)
        auto["description"] = "updated"
        automation_save(auto)
        loaded = automation_load(aid)
        self.assertEqual(loaded["description"], "updated")

    def test_next_run_scheduled(self):
        auto = _auto_default("sched", "task", "scheduled", interval=60)
        auto["next_run"] = time.time() - 10
        result = _automation_next_run(auto)
        self.assertIsNotNone(result)
        self.assertGreater(result, time.time())

    def test_next_run_oneshot_completed(self):
        auto = _auto_default("one", "task", "oneshot", due_at=time.time()-10)
        auto["run_count"] = 1
        result = _automation_next_run(auto)
        self.assertIsNone(result)
        self.assertEqual(auto["status"], "completed")


class TestScheduleParsing(unittest.TestCase):

    def test_every_x_minutes(self):
        result = _parse_schedule_text("every 30 minutes")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "scheduled")
        self.assertEqual(result[1], 30)

    def test_every_x_hours(self):
        result = _parse_schedule_text("every 2 hours")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "scheduled")
        self.assertEqual(result[1], 120)

    def test_every_x_days(self):
        result = _parse_schedule_text("every 3 days")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "scheduled")
        self.assertEqual(result[1], 4320)

    def test_every_morning(self):
        result = _parse_schedule_text("every morning")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "scheduled")
        self.assertEqual(result[1], 1440)

    def test_every_hour(self):
        result = _parse_schedule_text("every hour")
        self.assertIsNotNone(result)
        self.assertEqual(result[1], 60)

    def test_hourly(self):
        result = _parse_schedule_text("hourly")
        self.assertIsNotNone(result)
        self.assertEqual(result[1], 60)

    def test_every_midnight(self):
        result = _parse_schedule_text("every midnight")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "scheduled")

    def test_in_x_minutes(self):
        now = time.time()
        result = _parse_schedule_text("in 15 minutes")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "oneshot")
        self.assertIsNone(result[1])
        self.assertGreater(result[2], now)
        self.assertAlmostEqual(result[2], now + 900, delta=5)

    def test_in_x_hours(self):
        now = time.time()
        result = _parse_schedule_text("in 2 hours")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "oneshot")
        self.assertAlmostEqual(result[2], now + 7200, delta=5)

    def test_in_x_days(self):
        now = time.time()
        result = _parse_schedule_text("in 3 days")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "oneshot")
        self.assertAlmostEqual(result[2], now + 259200, delta=5)

    def test_now(self):
        result = _parse_schedule_text("now")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "oneshot")

    def test_immediately(self):
        result = _parse_schedule_text("immediately")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "oneshot")

    def test_asap(self):
        result = _parse_schedule_text("asap")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "oneshot")

    def test_tomorrow(self):
        result = _parse_schedule_text("tomorrow")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "oneshot")
        tomorrow_midnight = (int(time.time()) // 86400 + 1) * 86400
        # Default time is 9:00 AM = 32400 seconds after midnight
        self.assertAlmostEqual(result[2], tomorrow_midnight + 32400, delta=60)

    def test_every_monday(self):
        result = _parse_schedule_text("every monday")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "scheduled")
        self.assertEqual(result[1], 10080)

    def test_garbage(self):
        result = _parse_schedule_text("foobar baz quux")
        self.assertIsNone(result)

    def test_empty(self):
        result = _parse_schedule_text("")
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main(verbosity=2)