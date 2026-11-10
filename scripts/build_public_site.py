#!/usr/bin/env python3
"""Build equivalent, crawlable public introductions; technical docs stay English."""
import argparse
import html
import json
import re
import struct
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {'en': 'English', 'de': 'Deutsch', 'fr': 'Français', 'es': 'Español',
             'it': 'Italiano', 'pt': 'Português', 'nl': 'Nederlands'}
BASE = 'https://mfahsold.github.io/lixity/'


def page_path(language: str) -> str:
    return 'index.html' if language == 'en' else f'index-{language}.html'


def page_url(language: str) -> str:
    return BASE if language == 'en' else BASE + page_path(language)


def render_pages() -> dict[str, str]:
    """Require complete translations rather than silently shipping English fallback."""
    dictionaries = {lang: json.loads((ROOT / f'docs/locales/{lang}.json').read_text(encoding="utf-8"))
                    for lang in LANGUAGES}
    template = Template((ROOT / 'docs/templates/home.html.template').read_text(encoding="utf-8"))
    footer = Template((ROOT / 'docs/templates/home-footer.html.template').read_text(encoding="utf-8"))
    version = re.search(r'__version__ = "([^"]+)"', (ROOT / 'src/lixity/_version.py').read_text(encoding="utf-8")).group(1)
    width, height = struct.unpack('>II', (ROOT / 'docs/screenshots/dashboard-light.png').read_bytes()[16:24])
    results = {}
    for lang, content in dictionaries.items():
        if set(content) != set(dictionaries['en']):
            raise ValueError(f'Incomplete public translation: {lang}')
        if any(not isinstance(value, str) or not value.strip() for value in content.values()):
            raise ValueError(f'Empty public translation: {lang}')
        fields = {key: html.escape(value, quote=True) for key, value in content.items()}
        fields['headline'] = '<br/>'.join(html.escape(line) for line in content['headline'].splitlines())
        fields['lang'] = lang
        fields['version'] = version
        fields['image_width'] = str(width)
        fields['image_height'] = str(height)
        fields['canonical'] = page_url(lang)
        fields['home_path'] = './' if lang == 'en' else page_path(lang)
        fields['tour_url'] = 'guides/first-look-de.html' if lang == 'de' else 'guides/first-look.html'
        fields['alternates'] = '\n'.join(
            f'<link rel="alternate" hreflang="{code}" href="{page_url(code)}"/>'
            for code in LANGUAGES) + f'\n<link rel="alternate" hreflang="x-default" href="{BASE}"/>'
        fields['language_links'] = '\n'.join(
            f'<a href="{page_path(code)}" lang="{code}" hreflang="{code}"'
            + (' aria-current="page"' if code == lang else '') + f'>{name}</a>'
            for code, name in LANGUAGES.items())
        fields['structured'] = json.dumps({
            '@context': 'https://schema.org', '@type': 'SoftwareApplication',
            'name': 'Lixity', 'applicationCategory': 'WritingApplication',
            'operatingSystem': 'Windows, macOS, Linux', 'url': page_url(lang),
            'description': content['description'], 'inLanguage': list(LANGUAGES),
            'license': 'https://github.com/mfahsold/lixity/blob/main/LICENSE',
            'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'EUR'},
        }, ensure_ascii=False).replace('<', '\\u003c')
        fields['footer'] = footer.substitute(fields)
        results[page_path(lang)] = template.substitute(fields)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    stale = []
    for name, text in render_pages().items():
        target = ROOT / 'docs' / name
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            target.write_text(text, encoding="utf-8")
    if stale:
        print('Stale public pages; run make docs-sync: ' + ', '.join(stale))
        return 1
    print('Public introductions: seven complete languages.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
