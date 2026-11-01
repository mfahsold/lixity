"""Provider-neutral exports retain authored controls and report SSML losses."""
from xml.etree import ElementTree as ET

import pytest

from lixity.speech_direction import (
    Direction,
    SpeechSegment,
    build_speech_plan,
    plan_json,
    speech_passages,
)
from lixity.speech_profiles import AudioProfile

NS = {'s': 'http://www.w3.org/2001/10/synthesis'}
XML_LANG = '{http://www.w3.org/XML/1998/namespace}lang'


def test_export_keeps_direction_for_a_backend_that_cannot_render_it():
    from lixity.speech_export import ssml_export, timeline_json

    text = 'Der Fluss rauscht.'
    profile = AudioProfile(engine='coqui', language='de', voice='thorsten')
    direction = Direction(anchor=speech_passages(text, 'de')[0]['anchor'], instructions='Quietly.')
    with pytest.raises(ValueError, match='Coqui cannot'):
        build_speech_plan(text, profile, directions=[direction])
    plan = build_speech_plan(text, profile, directions=[direction], for_export=True)
    row = timeline_json(plan)['segments'][0]
    assert row['instructions'] == 'Quietly.'
    assert row['direction']['instructions'] == 'Quietly.'
    assert plan[0].profile.instructions == ''
    assert plan_json(plan)['segments'][0]['profile']['instructions'] == ''
    assert 'unsupported_instructions' in {w['code'] for w in ssml_export(plan)['warnings']}


def test_timeline_preserves_original_ranges_substitutions_and_unknown_times():
    from lixity.speech_export import timeline_json

    text = 'A Vale walks. Vale waits.'
    profile = AudioProfile(pronunciations={'Vale': 'Vail'}, instructions='Clearly.')
    anchor = speech_passages(text, 'en')[0]['anchor']
    direction = Direction(anchor=anchor, start=13, instructions='Softly.', pause_before=.3, pause_after=.7)
    plan = build_speech_plan(text, profile, directions=[direction], for_export=True)
    result = timeline_json(plan)
    assert result['schema_version'] == 'lixity-audio-timeline/1'
    rows = result['segments']
    assert ''.join(r['original_text'] for r in rows) == text
    assert ''.join(r['text'] for r in rows) == 'A Vail walks. Vail waits.'
    assert rows[0]['source_range'] == {'start': 0, 'end': 13, 'unit': 'unicode-code-point', 'projection': 'spoken-projection'}
    assert rows[1]['source_range']['start'] == 13
    assert rows[1]['anchor'] == anchor
    assert rows[1]['instructions'] == 'Clearly. Softly.'
    assert rows[1]['pause_before'] == .3 and rows[1]['pause_after'] == .7
    assert rows[0]['substitutions'] == [{'start': 2, 'end': 6, 'original': 'Vale', 'replacement': 'Vail'}]
    assert result['timing']['duration_seconds'] is None
    assert result['timing']['reason']
    assert all(r['start_seconds'] is None and r['end_seconds'] is None and r['duration_seconds'] is None for r in rows)
    assert all(r['text'] == r['spoken_text'] for r in rows)


def test_ssml_has_root_language_and_faithful_escaped_sub_aliases():
    from lixity.speech_export import ssml_export

    profile = AudioProfile(pronunciations={'Vale': 'Vail "A" & B'}, speed=1.15)
    plan = build_speech_plan('Vale <river> & Vale.', profile, for_export=True)
    result = ssml_export(plan, default_lang='en')
    document = ET.fromstring(result['ssml'])  # noqa: S314 - generated synthetic SSML
    assert document.get(XML_LANG) == 'en'
    aliases = document.findall('.//s:sub', NS)
    assert [(node.text, node.get('alias')) for node in aliases] == [('Vale', 'Vail "A" & B')] * 2
    assert document.find('.//s:prosody', NS).get('rate') == '1.15'
    assert document.find('s:break', NS).get('time') == '450ms'


def test_casefold_whole_word_substitutions_match_the_shared_pronunciation_rules():
    from lixity.speech_export import ssml_export, timeline_json

    profile = AudioProfile()
    settings = {'audio': {'schema_version': 'lixity-audio-settings/2', 'selected': 'n',
                         'profiles': {'n': profile.model_dump()}, 'pronunciations': {'Vale': 'Vail'},
                         'pronunciation_matching': {'case_sensitive': False, 'whole_words': True}}}
    plan = build_speech_plan('VALE Valeport vale.', profile, project_config=settings, for_export=True)
    row = timeline_json(plan)['segments'][0]
    assert row['text'] == 'Vail Valeport Vail.'
    document = ET.fromstring(ssml_export(plan)['ssml'])  # noqa: S314 - generated synthetic SSML
    assert [node.text for node in document.findall('.//s:sub', NS)] == ['VALE', 'vale']


def test_distinct_designed_and_reference_voices_remain_distinct_and_stable():
    from lixity.speech_export import ssml_export, timeline_json

    profiles = [AudioProfile(engine='qwen3-design', voice='design', voice_description=value)
                for value in ('A low voice.', 'A high voice.')]
    profiles += [AudioProfile(engine='qwen3-base', voice='reference', reference_id=value * 64)
                 for value in ('a', 'b')]
    plan = [SpeechSegment('Synthetic prose.', profile) for profile in profiles]
    result = timeline_json(plan)
    ids = [row['speaker_id'] for row in result['segments']]
    assert len(set(ids)) == 4
    assert list(reversed(ids)) == [row['speaker_id'] for row in timeline_json(list(reversed(plan)))['segments']]
    assert [row['profile'] for row in result['segments']] == [p.model_dump() for p in profiles]
    markup = ssml_export(plan)
    names = [node.get('name') for node in ET.fromstring(markup['ssml']).findall('s:voice', NS)]  # noqa: S314 - generated synthetic SSML
    assert names == ids
    assert len([w for w in markup['warnings'] if w['code'] == 'voice_binding_required']) == 4


def test_export_does_not_apply_backend_transport_word_limits():
    from lixity.speech import MAX_SEGMENT_CHARS
    from lixity.speech_export import timeline_json

    text = 'a' * (MAX_SEGMENT_CHARS + 1)
    with pytest.raises(ValueError, match='segment limit'):
        build_speech_plan(text, AudioProfile())
    plan = build_speech_plan(text, AudioProfile(), for_export=True)
    assert timeline_json(plan)['segments'][0]['original_text'] == text
    assert plan[0].text == text


def test_plain_legacy_segments_report_unavailable_provenance_without_inventing_it():
    from lixity.speech_export import timeline_json

    result = timeline_json([SpeechSegment('Synthetic prose.', AudioProfile())])
    row = result['segments'][0]
    assert row['original_text'] is None and row['source_range'] is None
    assert 'source_provenance_unavailable' in {w['code'] for w in result['warnings']}


def test_ssml_rejects_characters_not_representable_in_xml_instead_of_corrupting_text():
    from lixity.speech_export import ssml_export

    with pytest.raises(ValueError, match=r'XML 1\.0'):
        ssml_export([SpeechSegment('Synthetic\x01prose.', AudioProfile())])


def test_ssml_preserves_submillisecond_pause_precision():
    from lixity.speech_export import ssml_export

    document = ET.fromstring(ssml_export([SpeechSegment('', AudioProfile(), .0005, .0015)])['ssml'])  # noqa: S314 - generated synthetic SSML
    assert [node.get('time') for node in document.findall('s:break', NS)] == ['0.5ms', '1.5ms']


def test_export_retains_combined_direction_longer_than_a_render_profile_limit():
    from lixity.speech_export import timeline_json

    text = 'A quiet river.'
    profile = AudioProfile(instructions='a' * 1500)
    direction = Direction(anchor=speech_passages(text, 'en')[0]['anchor'], instructions='b' * 1500)
    with pytest.raises(ValueError):
        build_speech_plan(text, profile, directions=[direction])
    row = timeline_json(build_speech_plan(text, profile, directions=[direction], for_export=True))['segments'][0]
    assert row['instructions'] == 'a' * 1500 + ' ' + 'b' * 1500
    assert row['profile']['instructions'] == 'a' * 1500


def test_external_voice_attribute_quotes_cannot_change_xml_structure():
    from lixity.speech_export import ssml_export

    profile = AudioProfile(engine='openai-compatible', voice='voice"quoted&safe', language='en',
                           base_url='http://localhost:8888/v1', model='synthetic-model')
    document = ET.fromstring(ssml_export([SpeechSegment('Synthetic prose.', profile)])['ssml'])  # noqa: S314 - generated synthetic SSML
    assert document.find('s:voice', NS).get('name') == profile.voice
    assert len(document.findall('s:voice', NS)) == 1


def test_colliding_provider_voice_names_keep_distinct_stable_ssml_bindings():
    from lixity.speech_export import ssml_export, timeline_json

    profiles = [AudioProfile(engine='openai-compatible', voice='narrator', language='en',
                             base_url=url, model=model)
                for url, model in [('http://localhost:8888/v1', 'first'),
                                   ('http://localhost:9999/v1', 'first'),
                                   ('http://localhost:8888/v1', 'second')]]
    plan = [SpeechSegment('Synthetic prose.', profile) for profile in profiles]
    plan += [SpeechSegment('Again.', profiles[0]), SpeechSegment('A preset.', AudioProfile())]
    timeline = timeline_json(plan)
    result = ssml_export(plan)
    document = ET.fromstring(result['ssml'])  # noqa: S314 - generated synthetic SSML
    names = [node.get('name') for node in document.findall('s:voice', NS)]
    ids = [row['speaker_id'] for row in timeline['segments']]
    assert names == [*ids[:4], 'Ryan']
    assert len(set(names[:3])) == 3
    bindings = {warning['speaker_id']: warning['voice'] for warning in result['warnings']
                if warning['code'] == 'voice_binding_required'}
    assert [bindings[speaker] for speaker in ids] == names
    reversed_document = ET.fromstring(ssml_export(list(reversed(plan)))['ssml'])  # noqa: S314 - generated synthetic SSML
    assert [node.get('name') for node in reversed_document.findall('s:voice', NS)] == list(reversed(names))
    assert timeline_json(plan) == timeline


def test_partial_word_replacements_fall_back_to_spoken_text_with_explicit_warning():
    from lixity.speech_export import ssml_export, timeline_json

    plan = build_speech_plan('Valeport.', AudioProfile(pronunciations={'Vale': 'Vail'}), for_export=True)
    result = ssml_export(plan)
    document = ET.fromstring(result['ssml'])  # noqa: S314 - generated synthetic SSML
    assert document.find('.//s:sub', NS) is None
    assert document.find('s:voice', NS).text == 'Vailport.'
    assert 'pronunciation_markup_unavailable' in {w['code'] for w in result['warnings']}
    assert timeline_json(plan)['segments'][0]['substitutions'][0]['original'] == 'Vale'


def test_legacy_plan_only_preserves_base_direction_without_loading_reference_bytes(tmp_path, capsys):
    import json

    from lixity.cli import main
    from lixity.speech_direction import direction_state, save_direction

    source = tmp_path / 'draft.md'
    source.write_text('A quiet river flows.')
    (tmp_path / 'lixity.toml').write_text(
        'language="en"\nmanuscript="draft.md"\n[audio]\n'
        'schema_version="lixity-audio-settings/1"\nselected="narrator"\n'
        '[audio.profiles.narrator]\nengine="qwen3-base"\nvoice="reference"\n'
        'reference_id="' + 'a' * 64 + '"\n'
    )
    state = direction_state(tmp_path, source)
    save_direction(tmp_path, source, {'anchor': state['passages'][0]['anchor'], 'instructions': 'Whisper softly.'},
                   expected_source_sha256=state['source_sha256'], expected_settings_sha256=state['settings_sha256'],
                   expected_direction_sha256=state['direction_sha256'])
    assert main(['read-aloud', '--project', str(tmp_path), '--plan-only']) == 0
    output = json.loads(capsys.readouterr().out)
    assert output['schema_version'] == 'lixity-speech-plan/1'
    row = output['segments'][0]
    assert row['instructions'] == 'Whisper softly.'
    assert AudioProfile.model_validate(row['profile']).instructions == ''


def test_legacy_json_keeps_render_transport_spacing_and_splitting():
    from lixity.speech import MAX_SEGMENT_CHARS
    from lixity.speech_export import timeline_json

    text = 'A bird crosses the garden. ' + 'A quiet river flows. ' * 60
    profile = AudioProfile()
    direction = Direction(anchor=speech_passages(text, 'en')[0]['anchor'], start=0, end=6, pause_before=.3)
    rendered = build_speech_plan(text, profile, directions=[direction])
    exported = build_speech_plan(text, profile, directions=[direction], for_export=True)
    assert len(exported) == 2
    assert len(rendered) > 2
    assert plan_json(exported) == plan_json(rendered)
    assert all(len(row['text']) <= MAX_SEGMENT_CHARS for row in plan_json(exported)['segments'])
    assert timeline_json(exported)['segments'][1]['original_text'].startswith(' crosses')


def test_partial_word_substitution_across_direction_boundary_is_reported():
    from lixity.speech_export import ssml_export

    text = 'Valeport.'
    direction = Direction(anchor=speech_passages(text, 'en')[0]['anchor'], start=0, end=4, pause_after=0.0)
    plan = build_speech_plan(text, AudioProfile(pronunciations={'Vale': 'Vail'}),
                             directions=[direction], for_export=True)
    result = ssml_export(plan)
    assert '<sub' not in result['ssml']
    assert 'pronunciation_markup_unavailable' in {warning['code'] for warning in result['warnings']}
