"""Small explicit catalog. English default, German uses original source strings."""
import json
import re
from pathlib import Path
from flask import g
TRANSLATIONS=json.loads(Path(__file__).with_name('translations.json').read_text())

EN_TO_DE={english:source for source,english in TRANSLATIONS.items()}

def translate(text):
    text=str(text or '')
    if getattr(g,'language','en')=='de':
        return EN_TO_DE.get(text,text)
    if text in TRANSLATIONS:return TRANSLATIONS[text]
    if re.fullmatch(r'(Collection|Wantlist): Seite \d+ von \d+',text):
        return text.replace('Seite','page').replace(' von ',' of ')
    if text.startswith('Discogs antwortet mit HTTP '):
        return re.sub(r'Discogs antwortet mit HTTP (\d+)\..*',r'Discogs returned HTTP \1. Please connect or sync again later.',text)
    return text
