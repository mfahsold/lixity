"""Synthetic directed speech plans preserve prose and explicit author choices."""
import hashlib

import pytest

from lixity.speech_profiles import AudioProfile

TEXT = '## First\n\nA quiet river flows. A bird calls.\n\n## Second\n\nA quiet river flows. A bird calls.\n'


def test_passage_direction_compiles_separate_model_controls_and_exact_pauses():
    from lixity.speech_direction import Direction, build_speech_plan, speech_passages
    passages = speech_passages(TEXT, 'en')
    anchor = passages[0]['anchor']
    directive = Direction(anchor=anchor, start=0, end=20, instructions='Restrained tension.',
                          pause_after=0.8, profile_id='other')
    profiles = {'other': AudioProfile(voice='Aiden', instructions='Clear narration.')}
    plan = build_speech_plan(TEXT, AudioProfile(), directions=[directive], profiles=profiles, chapter=1)
    assert plan[0].text == 'First'
    spoken = [row for row in plan if row.anchor]
    assert spoken[0].text == 'A quiet river flows.'
    assert spoken[0].profile.voice == 'Aiden'
    assert spoken[0].profile.instructions == 'Clear narration. Restrained tension.'
    assert spoken[0].pause_after == 0.8
    assert spoken[1].text == 'A bird calls.'
    assert spoken[1].profile.instructions == ''
    assert TEXT.count('A quiet river flows.') == 2


def test_base_allows_passage_pauses_and_other_explicit_profiles():
    from lixity.speech_direction import Direction, build_speech_plan, speech_passages

    anchor = speech_passages(TEXT, 'en')[0]['anchor']
    base = AudioProfile(engine='qwen3-base', voice='reference', reference_id='a' * 64)
    pause = Direction(anchor=anchor, pause_before=0.4, pause_after=0.6)
    spoken = [row for row in build_speech_plan(TEXT, base, directions=[pause], chapter=1) if row.anchor]
    assert spoken[0].profile.engine == 'qwen3-base'
    assert spoken[0].pause_before == 0.4 and spoken[-1].pause_after == 0.6

    # A passage explicitly assigned to a supported non-Base profile may retain its instructions.
    assigned = Direction(anchor=anchor, instructions='Quietly.', profile_id='preset')
    spoken = [row for row in build_speech_plan(TEXT, base, directions=[assigned], chapter=1,
              profiles={'preset': AudioProfile()}) if row.anchor]
    assert spoken[0].profile.engine == 'qwen3' and spoken[0].profile.instructions == 'Quietly.'

    # A conflict in a different chapter must not stop this chapter's plan.
    other = Direction(anchor=speech_passages(TEXT, 'en')[1]['anchor'], instructions='Quietly.')
    assert any(row.text for row in build_speech_plan(TEXT, base, directions=[other], chapter=1))


def test_overlap_stale_anchor_and_unsupported_fields_fail_before_synthesis():
    from lixity.speech_direction import Direction, build_speech_plan, speech_passages
    anchor = speech_passages(TEXT, 'en')[0]['anchor']
    a = Direction(anchor=anchor, start=0, end=20, instructions='Calm.')
    b = Direction(anchor=anchor, start=10, end=25, instructions='Tense.')
    with pytest.raises(ValueError, match='overlap'):
        build_speech_plan(TEXT, AudioProfile(), directions=[a,b])
    changed = TEXT.replace('quiet', 'gentle', 1)
    with pytest.raises(ValueError, match=r'changed|stale'):
        build_speech_plan(changed, AudioProfile(), directions=[a])
    with pytest.raises(ValueError):
        Direction(anchor=anchor, pitch=1.2)


def test_identical_paragraphs_are_bound_to_line_identity_not_first_text_match():
    from lixity.speech_direction import Direction, build_speech_plan, speech_passages
    passages = speech_passages(TEXT, 'en')
    direction = Direction(anchor=passages[1]['anchor'], instructions='Whisper softly.')
    plan = build_speech_plan(TEXT, AudioProfile(), directions=[direction])
    assert [row.profile.instructions for row in plan if row.anchor] == ['', 'Whisper softly.']


def test_direction_roundtrip_is_guarded_atomic_and_does_not_write_manuscript(tmp_path):
    from lixity.speech_direction import direction_state, save_direction, speech_passages
    source=tmp_path/'draft.md'
    source.write_text(TEXT)
    (tmp_path/'lixity.toml').write_text('language = "en"\n')
    before=source.read_bytes()
    state=direction_state(tmp_path, source, language='en')
    entry={'anchor':speech_passages(TEXT,'en')[0]['anchor'], 'instructions':'Read calmly.'}
    updated=save_direction(tmp_path,source,entry,expected_source_sha256=state['source_sha256'],
                           expected_settings_sha256=state['settings_sha256'],
                           expected_direction_sha256=state['direction_sha256'],language='en')
    assert len(updated['directions'])==1
    assert source.read_bytes()==before
    with pytest.raises(ValueError,match='changed'):
        save_direction(tmp_path,source,entry,expected_source_sha256=hashlib.sha256(before).hexdigest(),
                       expected_settings_sha256=state['settings_sha256'],
                       expected_direction_sha256=state['direction_sha256'],language='en')


def test_renderer_and_plan_share_effective_controls_and_cache_keys(tmp_path, monkeypatch):
    import lixity.speech_qwen as qwen
    from lixity.speech import generate_silence_wav, render_speech_audio
    from lixity.speech_direction import Direction, build_speech_plan, speech_passages
    source=tmp_path/'source.md'
    source.write_text(TEXT)
    direction=Direction(anchor=speech_passages(TEXT,'en')[0]['anchor'], instructions='Quietly.')
    plan=build_speech_plan(TEXT,AudioProfile(),directions=[direction],chapter=1)
    seen=[]
    def synth(text, profile, **kw):
        seen.append((text,profile.instructions))
        return generate_silence_wav(.01)
    monkeypatch.setattr(qwen,'synthesize_qwen',synth)
    render_speech_audio(source,tmp_path/'reading.wav',profile=AudioProfile(),plan=plan)
    assert seen == [(row.text,row.profile.instructions) for row in plan if row.text]
    assert 'Quietly.' not in source.read_text()


def test_cli_plan_only_reads_saved_direction_without_worker_or_output(tmp_path, capsys):
    from lixity.cli import main
    from lixity.speech_direction import direction_state, save_direction
    source=tmp_path/'draft.md'
    source.write_text(TEXT)
    (tmp_path/'lixity.toml').write_text('language = "en"\n')
    state=direction_state(tmp_path,source)
    save_direction(tmp_path,source,{'anchor':state['passages'][0]['anchor'],'instructions':'Tense.'},
                   expected_source_sha256=state['source_sha256'], expected_settings_sha256=state['settings_sha256'],
                   expected_direction_sha256=state['direction_sha256'])
    assert main(['read-aloud','--project',str(tmp_path),'--plan-only'])==0
    import json
    output=json.loads(capsys.readouterr().out)
    assert any(row['profile']['instructions']=='Tense.' for row in output['segments'])
    assert not list(tmp_path.glob('*.wav'))


def test_multiline_direction_is_normalized_without_spoken_control_characters():
    from lixity.speech_direction import Direction, build_speech_plan, speech_passages
    profile=AudioProfile(instructions='Read clearly.\nKeep a steady pace.')
    direction=Direction(anchor=speech_passages(TEXT,'en')[0]['anchor'],instructions='Restrained tension.\nNo shouting.')
    plan=build_speech_plan(TEXT,profile,directions=[direction])
    assert plan[1].profile.instructions=='Read clearly. Keep a steady pace. Restrained tension. No shouting.'
    assert '\n' not in plan[1].text


def test_block_quote_with_identical_words_cannot_take_a_prose_direction():
    from lixity.speech_direction import Direction, build_speech_plan, speech_passages
    text='## One\n\n> A river flows.\n\nA river flows.\n'
    d=Direction(anchor=speech_passages(text,'en')[0]['anchor'],instructions='Tense.')
    plan=build_speech_plan(text,AudioProfile(),directions=[d])
    rows=[p for p in plan if p.text=='A river flows.']
    assert [p.profile.instructions for p in rows]==['','Tense.']


@pytest.mark.parametrize('text', ['Der Fluss rauscht.','La rivière coule.','El río fluye.','Il fiume scorre.','O rio corre.','De rivier stroomt.','静かな川です。鳥が鳴きます。','A river 🌊 flows.'])
def test_passage_ranges_preserve_multilingual_spoken_text(text):
    from lixity.speech_direction import Direction, build_speech_plan, speech_passages
    source='## One\n\n'+text+'\n'
    d=Direction(anchor=speech_passages(source,'en')[0]['anchor'],instructions='Read calmly.')
    rows=[p for p in build_speech_plan(source,AudioProfile(),directions=[d]) if p.anchor]
    assert ''.join(row.text for row in rows)==text
    assert all(row.profile.instructions=='Read calmly.' for row in rows)


def test_identical_save_is_idempotent_and_config_change_is_rejected(tmp_path):
    from lixity.speech_direction import direction_state, save_direction
    source=tmp_path/'draft.md'
    source.write_text(TEXT)
    config=tmp_path/'lixity.toml'
    config.write_text('language="en"\n')
    def save(view, entry):
        return save_direction(tmp_path,source,entry,expected_source_sha256=view['source_sha256'],
            expected_settings_sha256=view['settings_sha256'],expected_direction_sha256=view['direction_sha256'])
    view=direction_state(tmp_path,source)
    entry={'anchor':view['passages'][0]['anchor'],'instructions':'Calm.'}
    updated=save(view,entry)
    assert save(updated,entry)['direction_sha256']==updated['direction_sha256']
    config.write_text('language="de"\n')
    with pytest.raises(ValueError,match='changed'):
        save(updated,entry)


def test_direction_offsets_are_resolved_before_whitespace_transport_normalization():
    from lixity.speech_direction import Direction, build_speech_plan, speech_passages
    text='## One\n\nA river flows.\nAnother bird calls.\n'
    p=speech_passages(text,'en')[0]
    start=p['text'].index('Another')
    d=Direction(anchor=p['anchor'],start=start,instructions='Tense.')
    plan=build_speech_plan(text,AudioProfile(),directions=[d])
    assert [(row.text,row.profile.instructions) for row in plan if row.anchor]==[
        ('A river flows.',''),('Another bird calls.','Tense.')]


def test_keep_markers_cannot_silently_shift_saved_direction_offsets():
    from lixity.speech_direction import Direction, build_speech_plan, speech_passages
    text='## One\n\nBefore [TODO edit] after words.\n'
    p=speech_passages(text,'en')[0]
    d=Direction(anchor=p['anchor'],start=p['text'].index('after'),instructions='Tense.')
    with pytest.raises(ValueError,match='marker'):
        build_speech_plan(text,AudioProfile(),directions=[d],skip_markers=False)


def test_implicit_preface_is_not_dropped_before_explicit_chapters():
    from lixity.speech_direction import build_speech_plan
    text='Preface\n\nThis is introductory prose.\n\n## One\n\nThis is chapter prose.\n'
    all_text=' '.join(row.text for row in build_speech_plan(text,AudioProfile()))
    assert 'This is introductory prose.' in all_text
    first=' '.join(row.text for row in build_speech_plan(text,AudioProfile(),chapter=1))
    assert 'This is introductory prose.' in first and 'chapter prose' not in first


def test_reselecting_a_saved_range_replaces_that_range_without_retaining_old_direction(tmp_path):
    from lixity.speech_direction import direction_state, save_direction
    source=tmp_path/'draft.md'
    source.write_text(TEXT)
    (tmp_path/'lixity.toml').write_text('language="en"\n')
    def save(view, entry, **kw):
        return save_direction(tmp_path,source,entry,expected_source_sha256=view['source_sha256'],
            expected_settings_sha256=view['settings_sha256'],expected_direction_sha256=view['direction_sha256'],**kw)
    view=direction_state(tmp_path,source)
    a={'anchor':view['passages'][0]['anchor'],'start':0,'end':20,'instructions':'Calm.'}
    saved=save(view,a)
    changed=save(saved,{**a,'end':10},replace_id=saved['directions'][0]['id'])
    assert len(changed['directions'])==1 and changed['directions'][0]['end']==10


@pytest.mark.parametrize(('text','expected'),[
    ('Preface\nThis is introductory prose.\n\n## One\n\nBody text.', ['Preface','This is introductory prose.','One','Body text.']),
    ('# Book\n\n## Empty\n\n## One\n\nBody text.', ['One','Body text.']),
])
def test_speech_preserves_shared_chapter_acceptance_with_soft_preface_lines_and_empty_chapters(text, expected):
    from lixity.speech_direction import build_speech_plan
    assert [row.text for row in build_speech_plan(text,AudioProfile()) if row.text]==expected


def test_yaml_metadata_cannot_capture_an_identically_worded_spoken_anchor():
    from lixity.speech_direction import Direction, build_speech_plan, speech_passages
    text='---\ntitle: Same prose.\n---\n\nSame prose.'
    p=speech_passages(text,'en')[0]
    plan=build_speech_plan(text,AudioProfile(),directions=[Direction(anchor=p['anchor'],instructions='Calm.')])
    assert [(row.text,row.profile.instructions) for row in plan if row.text]==[('Same prose.','Calm.')]


def test_cli_can_preview_an_explicit_voice_design_profile_without_worker(tmp_path, capsys):
    import json

    from lixity.cli import main
    (tmp_path/'draft.md').write_text(TEXT)
    (tmp_path/'lixity.toml').write_text('language="de"\n')
    assert main(['read-aloud', '--project', str(tmp_path), '--plan-only', '--engine', 'qwen3-design',
                 '--voice', 'design', '--voice-description', 'A natural German voice.']) == 0
    plan=json.loads(capsys.readouterr().out)
    assert plan['segments'][0]['profile']['engine'] == 'qwen3-design'
    assert plan['segments'][0]['profile']['voice_description'] == 'A natural German voice.'
