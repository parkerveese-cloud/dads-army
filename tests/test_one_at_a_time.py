"""1.22.1: many things at once. Each thread has its own database connection (one shared connection failed with "bad
parameter or other API misuse" when two threads asked at once), and the daily briefing can't be switched, or another
AI chosen, while one is being written."""
import threading
import time

from support import AppTest, server

REPLY = ("BRIEFING: Overnight things are quiet near home, with a yellow wind warning for the coast tomorrow, so it's worth "
         "charging power banks. Across the UK the threat level is unchanged.\nHEADLINE: Quiet\n"
         "LEVELS: local=2 national=3 global=3\nVS_USUAL: local=same national=same global=same")


def gemini(text=REPLY):
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP",
                            "groundingMetadata": {"webSearchQueries": ["London news today"]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 10}}


class DatabaseTest(AppTest):

    def test_threads_at_once(self):
        """Reads and writes from eight threads at once: no "API misuse", and every write is there afterwards."""
        errors, start = [], threading.Event()

        def work(n):
            start.wait()
            try:
                for i in range(150):
                    server.setting_raw("briefing", {})
                    server.month_spend()
                    with server.tx() as db:
                        server.set_setting_raw(db, "t%d" % n, i)
                    server.brief_public()
            except Exception as e:   # noqa: BLE001 - any of them is the failure
                errors.append(repr(e))
        threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join(60)
        self.assertEqual(errors, [])
        self.assertEqual([server.setting_raw("t%d" % n) for n in range(8)], [149] * 8)

    def test_each_thread_its_own(self):
        here = server.DB.conn()
        there = []
        t = threading.Thread(target=lambda: there.append(server.DB.conn()))
        t.start()
        t.join()
        self.assertIsNot(here, there[0])
        self.assertIs(server.DB.conn(), here)   # and the same one each time in a thread

    def test_a_transaction_is_its_own_threads(self):
        """What's written inside tx() is seen there at once, and by other threads only once it's committed."""
        seen = []
        with server.tx() as db:
            server.set_setting_raw(db, "x", 1)
            self.assertEqual(server.setting_raw("x"), 1)
            t = threading.Thread(target=lambda: seen.append(server.setting_raw("x")))
            t.start()
            t.join()
        self.assertEqual(seen, [None])
        self.assertEqual(server.setting_raw("x"), 1)

    def test_closed(self):
        server.DB.close()
        with self.assertRaises(server.sqlite3.ProgrammingError):
            server.DB.execute("SELECT 1")
        server.init_db()   # for tearDown


class BriefingBusyTest(AppTest):

    def setUp(self):
        super().setUp()
        with server.tx() as db:
            server.set_setting_raw(db, "scan_ai", {"provider": "google", "keys": {"google": "AIza-test-key-0123456789"}})
        server.BRIEF.update(busy=False, error="", day="", tries=0, last_try=0.0)
        self.real_post = server._post_json
        self.go = threading.Event()

        def slow(url, body, headers, timeout=60):
            self.go.wait(10)
            return gemini()
        server._post_json = slow

    def tearDown(self):
        self.go.set()
        self.wait_done()
        server._post_json = self.real_post
        super().tearDown()

    def wait_done(self):
        for _ in range(200):
            if not server.BRIEF["busy"]:
                return
            time.sleep(0.05)
        self.fail("still being written")

    def test_switching_on_says_its_being_written(self):
        """The answer says so straight away (it used to race the thread), and the switch is locked until it's done."""
        r = server.api_briefing_put({"on": True}, {})
        self.assertTrue(r["busy"])
        for change in ({"on": False}, {"model": "gemini-4-argon"}):
            with self.assertRaises(server.ApiError) as e:
                server.api_briefing_put(change, {})
            self.assertEqual(e.exception.status, 409)
            self.assertIn("when it's done", e.exception.message)
        self.assertTrue(server.api_briefing_put({"on": True}, {})["config"]["on"])   # no change: fine
        self.assertEqual(server.api_briefing_put({"area": "Greenwich"}, {})["config"]["area"], "Greenwich")   # for next time
        with self.assertRaises(server.ApiError):
            server.api_briefing_now({}, {})
        self.go.set()
        self.wait_done()
        b = server.brief_public()
        self.assertEqual((b["busy"], b["error"], b["latest"]["headline"]), (False, "", "Quiet"))
        self.assertFalse(server.api_briefing_put({"on": False}, {})["config"]["on"])   # and now it can be switched

    def test_write_one_now_says_its_being_written(self):
        with server.tx() as db:
            server.set_setting_raw(db, "briefing", {"on": True, "model": "gemini-4-hydrogen"})
        self.assertTrue(server.api_briefing_now({}, {})["busy"])
        self.go.set()
        self.wait_done()
        self.assertEqual(server.brief_public()["latest"]["headline"], "Quiet")

    def test_a_fault_on_the_pi_doesnt_leave_it_being_written(self):
        """It used to read the settings before its try: a fault there left it "being written" until a restart."""
        with server.tx() as db:
            server.set_setting_raw(db, "briefing", {"on": True, "model": "gemini-4-hydrogen"})
        real = server.brief_cfg
        server.brief_cfg = lambda: (_ for _ in ()).throw(server.sqlite3.InterfaceError("bad parameter or other API misuse"))
        try:
            with self.assertRaises(server.ApiError) as e:
                server.make_briefing()
        finally:
            server.brief_cfg = real
        self.assertEqual(e.exception.status, 500)
        self.assertFalse(server.BRIEF["busy"])
        self.assertIn("Something went wrong on the Pi", server.BRIEF["error"])
        self.go.set()
        self.assertEqual(server.make_briefing()["headline"], "Quiet")   # and the next try goes ahead
        self.assertEqual(server.BRIEF["error"], "")


class OfflineListBusyTest(AppTest):

    def test_switching_on_says_its_updating(self):
        ran, release = [], threading.Event()
        real = server.build_offline

        def build(url=None, claimed=False):
            ran.append(claimed)
            release.wait(5)
            server.OFFLINE["building"] = False
            return True
        server.build_offline = build
        try:
            r = server.api_scan_offline_set({"enabled": True}, {})
            self.assertTrue(r["building"])   # straight away, not once the thread gets going
            self.assertTrue(server.api_scan_offline_update({}, {})["building"])   # already updating: not a second one
            release.set()
            for _ in range(100):
                if not server.OFFLINE["building"]:
                    break
                time.sleep(0.05)
            self.assertEqual(ran, [True])
        finally:
            release.set()
            server.build_offline = real
            server.OFFLINE["building"] = False
