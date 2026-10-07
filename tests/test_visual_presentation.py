import re
import unittest
from flask import render_template_string
import test_flow

class Presentation(unittest.TestCase):
    setUp=test_flow.Flow.setUp
    tearDown=test_flow.Flow.tearDown
    def test_radial_bands_at_reference_percentages(self):
        # No-JS output must represent real score, not an empty graphic with a final number.
        with self.app.test_request_context('/'):
            self.app.preprocess_request()
            for score,expected in [(0,121),(10,113.3),(50,82.5),(100,44)]:
                markup=render_template_string("{% from 'components/blackgold_link.html' import link_scene with context %}{{ link_scene('A','B',score) }}",score=score)
                values=re.findall(r'data-scan-inner[^>]*r="([0-9.]+)"',markup)
                self.assertEqual(len(values),2)
                for value in values:self.assertAlmostEqual(float(value),expected)
            self.app.do_teardown_request(None)
    def test_landing_presents_visual_before_explanations(self):
        page=self.client.get('/').data
        self.assertIn(b'John Doe',page)
        self.assertIn(b'Jane Doe',page)
        self.assertIn(b'data-presentation="true"',page)
        self.assertNotIn(b'presentation-about',page)
        self.assertNotIn(b'Explore the demo',page)
        self.assertNotIn(b'Two shelves.',page)
        self.assertIn(b'Compare your collection with others.',page)
        self.assertNotIn(b'<table',page)
        self.assertIn(b'brand/blackgoldlink-logo.png',page)
        self.assertNotIn(b'brand-icon',page)
        with self.client.get('/static/brand/blackgoldlink-logo.png') as logo:
            self.assertEqual(logo.status_code,200)
            self.assertEqual(logo.mimetype,'image/png')
