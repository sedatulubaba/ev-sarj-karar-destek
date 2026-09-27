"""Sade Streamlit arayüzünün kullanıcı akışları."""

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    def create_app(self):
        path = Path(__file__).resolve().parents[1] / "app.py"
        return AppTest.from_file(str(path), default_timeout=30).run()

    def test_initial_and_submitted_result(self):
        app = self.create_app()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.dataframe), 0)
        self.assertEqual(len(app.expander), 2)
        app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Teknik uygunluk" in item.value for item in app.markdown))
        self.assertGreaterEqual(len(app.dataframe), 3)

    def test_unknown_phase_requires_confirmation(self):
        app = self.create_app()
        app.selectbox(key="home_phase").set_value("Bilmiyorum")
        app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Kesin teknik uygunluk" in item.value for item in app.warning))

    def test_unknown_vehicle_value_is_provisional(self):
        app = self.create_app()
        app.checkbox(key="vehicle_ac_kw_unknown").check()
        app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Ön değerlendirme" in item.value for item in app.markdown))

    def test_no_suitable_station(self):
        app = self.create_app()
        app.number_input(key="budget").set_value(1.0)
        app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("uygun cihaz bulunamadı" in item.value for item in app.warning))


if __name__ == "__main__":
    unittest.main()
