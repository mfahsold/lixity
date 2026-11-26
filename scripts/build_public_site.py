#!/usr/bin/env python3
"""Build equivalent, crawlable public introductions; technical docs stay English."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import struct
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {'en': 'English', 'de': 'Deutsch', 'fr': 'Français', 'es': 'Español',
             'it': 'Italiano', 'pt': 'Português', 'nl': 'Nederlands'}
OG_LOCALES = {'en': 'en_US', 'de': 'de_DE', 'fr': 'fr_FR', 'es': 'es_ES',
              'it': 'it_IT', 'pt': 'pt_PT', 'nl': 'nl_NL'}
BASE = 'https://lixity.de/'
TOUR_MEDIA = {
    'tour_landscape_mp4': 'videos/product-tour.mp4',
    'tour_landscape_webm': 'videos/product-tour.webm',
    'tour_landscape_poster': 'videos/product-tour.webp',
    'tour_portrait_mp4': 'videos/product-tour-portrait.mp4',
    'tour_portrait_poster': 'videos/product-tour-portrait.png',
    'tour_social_horizontal': 'videos/social-hook-16x9.mp4',
    'tour_social_vertical': 'videos/social-hook-9x16.mp4',
}


def page_path(language: str) -> str:
    return 'index.html' if language == 'en' else f'index-{language}.html'


def page_url(language: str) -> str:
    return BASE if language == 'en' else BASE + page_path(language)


def render_pages(root: Path | None = None) -> dict[str, str]:
    """Require complete translations rather than silently shipping English fallback."""
    from lixity.site import FUNDING_DETAILS_PATH

    try:
        from check_release import source_version
    except ModuleNotFoundError:
        from scripts.check_release import source_version

    base = ROOT if root is None else root
    dictionaries = {lang: json.loads((base / f'docs/locales/{lang}.json').read_text(encoding="utf-8"))
                    for lang in LANGUAGES}
    tour = json.loads((base / 'docs/videos/product-tour-timing.json').read_text(encoding='utf-8'))
    tour_urls = {}
    for field, path in TOUR_MEDIA.items():
        fingerprint = hashlib.sha256((base / 'docs' / path).read_bytes()).hexdigest()[:12]
        tour_urls[field] = f'{path}?v={fingerprint}'
    template = Template((base / 'docs/templates/home.html.template').read_text(encoding="utf-8"))
    footer = Template((base / 'docs/templates/home-footer.html.template').read_text(encoding="utf-8"))
    version = source_version(base)
    preview_image = base / 'docs/screenshots/dashboard-light.png'
    image_width, image_height = struct.unpack('>II', preview_image.read_bytes()[16:24])
    results = {}
    for lang, content in dictionaries.items():
        if set(content) != set(dictionaries['en']):
            raise ValueError(f'Incomplete public translation: {lang}')
        if any(not isinstance(value, str) or not value.strip() for value in content.values()):
            raise ValueError(f'Empty public translation: {lang}')
        fields = {
            key: html.escape(value.replace('{version}', version)
                             .replace('{tour_duration}', str(tour['duration'])), quote=True)
            for key, value in content.items()
        }
        fields.update(tour_urls)
        fields['tour_cues'] = ''.join(
            f'<li data-start="{scene["start"]}">{fields["tour_" + scene["id"]]}</li>'
            for scene in tour['scenes']
        )
        fields['headline'] = html.escape(' '.join(content['headline'].splitlines()))
        fields['lang'] = lang
        fields['language_name'] = LANGUAGES[lang]
        fields['version'] = version
        fields['image_width'] = str(image_width)
        fields['image_height'] = str(image_height)
        fields['canonical'] = page_url(lang)
        fields['home_path'] = './' if lang == 'en' else page_path(lang)
        fields['funding_url'] = FUNDING_DETAILS_PATH
        fields['sandbox_language'] = 'de' if lang == 'de' else 'en'
        fields['passage_guide_language'], fields['passage_guide_path'] = (
            ('de', 'guides/first-look-de.html#beleg') if lang == 'de'
            else ('en', 'guides/first-look.html#passage')
        )
        fields['rhythm_guide_path'] = (
            'guides/first-look-de.html#rhythmus' if lang == 'de' else 'guides/first-look.html#contrast'
        )
        fields['research_guide_path'] = (
            'guides/first-look-de.html#recherche' if lang == 'de' else 'guides/first-look.html#decision'
        )
        fields['alternates'] = '\n'.join(
            f'<link rel="alternate" hreflang="{code}" href="{page_url(code)}"/>'
            for code in LANGUAGES) + f'\n<link rel="alternate" hreflang="x-default" href="{BASE}"/>'
        fields['og_locales'] = '\n'.join(
            [f'<meta property="og:locale" content="{OG_LOCALES[lang]}"/>']
            + [f'<meta property="og:locale:alternate" content="{locale}"/>'
               for code, locale in OG_LOCALES.items() if code != lang]
        )
        fields['language_links'] = '\n'.join(
            f'<a href="{page_path(code)}" lang="{code}" hreflang="{code}"'
            + f' data-language-action="{html.escape(dictionaries[code]["language_action"], quote=True)}"'
            + (' aria-current="page"' if code == lang else '') + f'>{name}</a>'
            for code, name in LANGUAGES.items())
        fields['structured'] = json.dumps({
            '@context': 'https://schema.org', '@type': 'SoftwareApplication',
            'name': 'Lixity', 'applicationCategory': 'WritingApplication',
            'operatingSystem': 'Windows, macOS, Linux', 'url': page_url(lang),
            'image': f'{BASE}screenshots/dashboard-light.png',
            'description': content['description'], 'inLanguage': list(LANGUAGES),
            'license': 'https://github.com/mfahsold/lixity/blob/main/LICENSE',
            'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'EUR'},
            'sameAs': [
                'https://github.com/mfahsold/lixity',
                'https://mastodon.social/@lixity',
                'https://bsky.app/profile/lixity.bsky.social',
            ],
            'author': {
                '@type': 'Person',
                'name': 'Matthias Fahsold',
                'url': 'https://github.com/mfahsold',
            },
        }, ensure_ascii=False).replace('<', '\\u003c')
        fields['footer'] = footer.substitute(fields)
        results[page_path(lang)] = template.substitute(fields)
    return results


def build(*, check_only: bool = False, root: Path | None = None) -> list[str]:
    """Render localized homepages and public download links."""
    try:
        from desktop_downloads import build as build_downloads
    except ModuleNotFoundError:
        from scripts.desktop_downloads import build as build_downloads

    base = ROOT if root is None else root
    stale: list[str] = []
    for name, text in render_pages(base).items():
        target = base / 'docs' / name
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current != text:
            stale.append(name)
            if not check_only:
                target.write_text(text, encoding="utf-8")
    return stale + build_downloads(check_only=check_only, root=base)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    stale = build(check_only=args.check)
    if args.check and stale:
        print('Stale public pages; run make docs-sync: ' + ', '.join(stale))
        return 1
    print('Public introductions: seven complete languages.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
