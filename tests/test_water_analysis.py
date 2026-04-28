import unittest

from urban_water_detection.services.water_analysis import analyze_dataset, analyze_water_loss, prepare_dataframe_from_text


class TestWaterAnalysis(unittest.TestCase):
    def test_leak_detection_and_metrics(self):
        csv_text = """zone,water_supplied,water_billed,date
Zone A,1000,900,2026-04-01
Zone B,800,790,2026-04-01
Zone A,900,870,2026-04-02
Zone B,850,830,2026-04-02
"""

        df = prepare_dataframe_from_text(csv_text)
        payload = analyze_water_loss(df, threshold=100)

        self.assertEqual(payload["metrics"]["zone_count"], 2)
        self.assertGreater(payload["metrics"]["total_loss"], 0)
        self.assertIn("trends", payload)
        self.assertEqual(len(payload["trends"]["labels"]), 2)
        self.assertEqual(len(payload["zones"]["table"]), 2)

    def test_required_columns_validation(self):
        bad_csv_text = """zone,water_supplied
Zone A,1000
"""

        with self.assertRaises(ValueError):
            prepare_dataframe_from_text(bad_csv_text)

    def test_kaggle_leakage_flag_mode(self):
        csv_text = """Zone,Pressure,Flow_Rate,Leakage_Flag,date
Zone_1,64.9,73.6,0,2026-04-01
Zone_2,57.6,90.9,1,2026-04-01
Zone_1,59.2,80.4,1,2026-04-02
Zone_2,62.0,85.2,0,2026-04-02
"""

        df = prepare_dataframe_from_text(csv_text)
        payload = analyze_dataset(df, threshold=30)

        self.assertEqual(payload["mode"], "leakage_detection")
        self.assertEqual(payload["metrics"]["zone_count"], 2)
        self.assertEqual(payload["metrics"]["total_supplied"], 4)
        self.assertEqual(payload["metrics"]["total_loss"], 2)
        self.assertIn("metric_labels", payload)


if __name__ == "__main__":
    unittest.main()
