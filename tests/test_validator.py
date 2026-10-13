import unittest
import os
import tempfile

from pipeline.validator import validate_segments, validate_xml


class SegmentValidatorTests(unittest.TestCase):
    def test_continuous_timeline_passes(self):
        result = validate_segments([
            {"start": 0.0, "duration": 2.0, "camera": 1},
            {"start": 2.0, "duration": 3.0, "camera": 2},
        ], 5.0)
        self.assertTrue(result["valid"])

    def test_gap_fails(self):
        result = validate_segments([
            {"start": 0.0, "duration": 2.0, "camera": 1},
            {"start": 3.0, "duration": 2.0, "camera": 2},
        ], 5.0)
        self.assertFalse(result["valid"])

    def test_malformed_segments_report_errors_without_crashing(self):
        result = validate_segments([None, {"start": "bad", "duration": 1, "camera": 1}], 2)
        self.assertFalse(result["valid"])
        self.assertEqual(len(result["errors"]), 3)

    def test_xmeml_nested_definition_resolves(self):
        xml = """<xmeml version='5'><sequence><duration>10</duration><media>
        <video><track><clipitem id='v'><start>0</start><end>10</end><in>0</in><out>10</out>
        <file id='f'><pathurl>file://localhost/test.mp4</pathurl></file></clipitem></track></video>
        <audio><track><clipitem id='a'><start>0</start><end>10</end><in>0</in><out>10</out>
        <file id='f'/></clipitem></track></audio></media></sequence></xmeml>"""
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as handle:
            handle.write(xml)
            path = handle.name
        try:
            self.assertTrue(validate_xml(path)["valid"])
        finally:
            os.unlink(path)

    def test_malformed_xml_timing_reports_error_without_crashing(self):
        xml = """<xmeml><sequence><duration>bad</duration><media/></sequence></xmeml>"""
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as handle:
            handle.write(xml)
            path = handle.name
        try:
            result = validate_xml(path)
            self.assertFalse(result["valid"])
            self.assertIn("duration is not an integer", result["errors"][0])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
