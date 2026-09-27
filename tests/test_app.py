"""Streamlit arayüzünün temel kullanıcı akışlarını kontrol eder."""

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def create_app(self):
        path = Path(__file__).resolve().parents[1] / "app.py"
        return AppTest.from_file(str(path), default_timeout=30).run()

    def test_default_and_three_phase(self):
        app = self.create_app()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 4)
        app.sidebar.selectbox[0].set_value("trifaz").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 4)

    def test_no_suitable_station(self):
        app = self.create_app()
        app.sidebar.number_input[5].set_value(1.0).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("Uygun istasyon bulunamadı" in item.value for item in app.warning))

    def test_inconsistent_ahp_stops_ranking(self):
        app = self.create_app()
        app.selectbox(key="ahp_0_1").set_value(9.0)
        app.selectbox(key="ahp_0_2").set_value(1 / 9)
        app.selectbox(key="ahp_1_2").set_value(9.0)
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("tutarsız" in item.value for item in app.error))


if __name__ == "__main__":
    unittest.main()
