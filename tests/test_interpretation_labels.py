"""Cross-locale interpretation contracts for descriptive style diagnostics."""

import unittest

from lixity.language import LANGUAGE_PROFILES
from lixity.language_data import (
    GROUP_LABELS,
    GUIDANCE_LABELS,
    HELP_TEXTS,
    IDENTITY_LABELS,
    LABELS,
    LAYER_LABELS,
    METRIC_LABELS,
    SCENE_LABELS,
    UI_LABELS,
)
from lixity.workspace_labels import WORKSPACE_LABELS
from tests.locales import LOCALES


class TestInterpretationLabels(unittest.TestCase):
    def test_flesch_help_describes_inputs_without_claiming_syntactic_analysis(self):
        terms = {
            "en": ("sentence", "syllables", "comprehension"),
            "de": ("Satz", "Silben", "Verständnis"),
            "fr": ("phrase", "syllabes", "compréhension"),
            "es": ("oración", "sílabas", "comprensión"),
            "it": ("frase", "sillabe", "comprensione"),
            "pt": ("frase", "sílabas", "compreensão"),
            "nl": ("zin", "lettergrepen", "begrip"),
        }
        for language, words in terms.items():
            with self.subTest(language=language):
                help_text = LANGUAGE_PROFILES[language].labels["help_flesch"].casefold()
                for word in words:
                    self.assertIn(word.casefold(), help_text)
                for unsupported in ("nesting", "hypotaxis", "Schachtelung", "Hypotaxen"):
                    self.assertNotIn(unsupported.casefold(), help_text)

    def test_resolved_labels_have_one_authoritative_definition(self):
        packs = (GUIDANCE_LABELS, SCENE_LABELS, IDENTITY_LABELS, LABELS,
                 METRIC_LABELS, HELP_TEXTS, GROUP_LABELS, LAYER_LABELS,
                 UI_LABELS, WORKSPACE_LABELS)
        for language in LOCALES:
            with self.subTest(language=language):
                owners = set()
                for pack in packs:
                    labels = pack.get(language, pack.get("en", {}))
                    self.assertFalse(owners.intersection(labels),
                                     f"Shadowed explanations in {language}: {owners.intersection(labels)}")
                    owners.update(labels)

    def test_jsd_names_divergence_rather_than_its_square_root(self):
        stems = {"en": "divergence", "de": "Divergenz", "fr": "divergence",
                 "es": "divergencia", "it": "divergenza", "pt": "divergência",
                 "nl": "divergentie"}
        for language, stem in stems.items():
            with self.subTest(language=language):
                self.assertIn(stem, LANGUAGE_PROFILES[language].labels["help_jsd"])

    def test_style_axes_declare_rank_space_complete_rows_and_omissions(self):
        terms = {
            "en": ("rank", "complete", "variance", "omitted"),
            "de": ("Rang", "vollständig", "Varianz", "ausgelassen"),
            "fr": ("rang", "complèt", "variance", "omis"),
            "es": ("rango", "complet", "varianza", "omiten"),
            "it": ("rang", "complet", "varianza", "omessi"),
            "pt": ("postos", "complet", "variância", "omitidos"),
            "nl": ("rang", "volledig", "variantie", "weggelaten"),
        }
        for language, words in terms.items():
            with self.subTest(language=language):
                value = LANGUAGE_PROFILES[language].labels["help_dimensions"]
                for word in words:
                    self.assertIn(word.casefold(), value.casefold())

    def test_fdr_labels_describe_nominal_selection_without_confirmation(self):
        old_claims = ("confirmed", "bestätigt", "confirmé", "confirmado",
                      "confermato", "bevestigd")
        for language in LOCALES:
            with self.subTest(language=language):
                labels = LANGUAGE_PROFILES[language].labels
                self.assertIn("nom", labels["help_fdr"].lower())
                self.assertIn("nom", labels["help_fdr_q"].lower())
                for key in ("fdr_flagged", "help_fdr"):
                    self.assertFalse(any(word in labels[key].lower() for word in old_claims))
                self.assertIn("nom", WORKSPACE_LABELS[language]["structural_confirmed"].lower())
                self.assertIn("nom", WORKSPACE_LABELS[language]["welcome_fdr_desc"].lower())

    def test_structural_help_qualifies_segmentation_and_nominal_probabilities(self):
        independence = {"en": "independent", "de": "unabhängige", "fr": "indépendantes",
                        "es": "independientes", "it": "indipendenti",
                        "pt": "independentes", "nl": "onafhankelijke"}
        for language in LOCALES:
            with self.subTest(language=language):
                labels = WORKSPACE_LABELS[language]
                for key in ("help_structural", "structural_guide", "help_changepoints",
                            "structural_changepoints_title"):
                    self.assertNotIn("PELT", labels[key])
                self.assertIn("nom", labels["help_trends"].lower())
                self.assertIn(independence[language], labels["help_trends"])
                self.assertIn("nom", labels["help_distribution_shift"].lower())
                self.assertIn(independence[language], labels["help_distribution_shift"])
                self.assertIn("nom", labels["structural_no_trends"].lower())
                self.assertIn("nom", labels["structural_no_shifts"].lower())
