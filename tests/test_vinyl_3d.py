"""3D is optional: keep the live score/copy, self-hosted assets and safe names."""
import hashlib
import json
from pathlib import Path
import unittest
from flask import render_template_string
import test_flow

class Vinyl3D(unittest.TestCase):
    setUp=test_flow.Flow.setUp
    tearDown=test_flow.Flow.tearDown
    def test_live_dom_keeps_accessible_fallback_without_lab_copy(self):
        page=self.client.get('/').data
        self.assertIn(b'data-vinyl-3d aria-hidden="true"',page)
        self.assertIn(b'data-scan-inner',page)
        self.assertIn(b'data-target="70.7"',page)
        for copy in [b'Demo score',b'MATERIAL STUDY',b'Tonearms on',b'A different kind of connection.',b'THE RECORDS SPEAK.']:
            self.assertNotIn(copy,page)
        self.assertIn(b'Compare your collection with others.',page)
        self.assertIn(b'brand/blackgoldlink-logo.png',page)
    def test_autostart_is_prepared_and_intro_follows_the_scene(self):
        page=self.client.get('/').data.decode()
        self.assertIn('is-preparing" data-presentation="true"',page)
        self.assertLess(page.index('data-blackgold-link'),page.index('class="presentation-intro"'))
        self.assertIn('<noscript><p class="fine">Your collection · The other collection · 70.7%',page)
    def test_common_disclaimer_is_present_on_public_pages(self):
        notice='This application uses Discogs’ API but is not affiliated with, sponsored or endorsed by Discogs. ‘Discogs’ is a trademark of Zink Media, LLC.'
        for path in ('/','/about','/privacy','/imprint','/invite'):
            page=self.client.get(path).get_data(as_text=True)
            self.assertIn(notice,page)

    def test_actual_names_are_escaped_and_never_interpreted_as_html(self):
        with self.app.test_request_context('/'):
            self.app.preprocess_request()
            markup=render_template_string("{% from 'components/blackgold_link.html' import link_scene with context %}{{ link_scene(a,b,31.2) }}",a='<script>alert("name")</script>',b='Collector & Friends')
            self.assertIn('data-name-a="&lt;script&gt;',markup)
            self.assertNotIn('<script>alert(',markup)
            self.assertIn('Collector &amp; Friends',markup)
            self.app.do_teardown_request(None)
    def test_renderer_assets_are_local_and_security_policy_is_unchanged(self):
        page=self.client.get('/')
        policy=page.headers['Content-Security-Policy']
        self.assertIn("script-src 'self'",policy)
        self.assertNotIn('unsafe-eval',policy)
        for path in ('vinyl3d.js','tonearm-motion.js','vinyl3d.css','vendor/three/three.module.js','vendor/three/three.core.js','vendor/three/LICENSE'):
            with self.client.get('/static/'+path) as response:self.assertEqual(response.status_code,200)
    def test_pinned_vendor_provenance_matches_the_shipped_build(self):
        root=Path(__file__).resolve().parents[1]/'static/vendor/three'
        provenance=json.loads((root/'provenance.json').read_text())
        self.assertEqual(provenance['version'],'0.186.1')
        for name,digest in provenance['sha256'].items():self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),digest)
        self.assertIn('MIT',(root/'LICENSE').read_text())
