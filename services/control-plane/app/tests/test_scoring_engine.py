import pytest

from app.scoring_engine import SCORE_TABLE, get_band, get_final_score

# Every spelling of provisional_diagnosis that exists in the live clinical_rules table.
LIVE_DB_SPELLINGS = [
    "APTHOUS STOMATITIS", "APTHOUS ULCER", "APTHOUS ULCER ", "BURNING MOUTH SYNDROME", "CANDIDIASIS",
    "CARCINOMA IN SITU", "FIBRO EPITHELIAL POLYP", "FIBROMA", "FRICTIONAL KERATOSIS", "INFLAMMATORY LESION",
    "Irritation Fibroma", "IRRITATION FIBROMA", "LINEA ALBA", "NO ABNORMALITY DETECTED", "ORAL LEUKOPLAKIA",
    "ORAL LICHEN PLANUS", "ORAL SQUAMOUS CELL CARCINOMA", "OSMF", " Speckled Leukoplakia",
    "Speckled Leukoplakia", " SPECKLED LEUKOPLAKIA", "SPECKLED LEUKOPLAKIA", "Squamous Papilloma",
    "SQUAMOUS PAPILLOMA", "TOBACCO POUCH KERATOSIS", "Traumatic Ulcer", "TRAUMATIC ULCER",
    "VARIABLE DIAGNOSIS", "VERRUCOUS LEUKOPLAKIA",
]


@pytest.mark.parametrize("deviation, band", [
    (0.0, "Variable Diagnosis"),
    (0.159, "Variable Diagnosis"),
    (0.16, "Borderline"),       # lower edge is inclusive
    (0.20, "Borderline"),       # upper edge is inclusive
    (0.2001, "Suggestive of Dysplasia"),
    (0.21, "Suggestive of Dysplasia"),
    (1.0, "Suggestive of Dysplasia"),
])
def test_band_thresholds(deviation, band):
    assert get_band(deviation) == band


def test_table_is_complete():
    # 26 sheet diagnoses + "Variable Diagnosis" (dentist-confirmed 0), each with all 3 bands.
    assert len(SCORE_TABLE) == 27
    assert all(len(bands) == 3 for bands in SCORE_TABLE.values())


@pytest.mark.parametrize("diagnosis, deviation, score", [
    ("Fibroma", 0.10, 1),
    ("Fibroma", 0.18, 2),
    ("Fibroma", 0.50, 3),                 # owner decision: 3 (sheet held both 2 and 3)
    ("Oral Squamous Cell Carcinoma", 0.05, 5),
    ("Oral Squamous Cell Carcinoma", 0.50, 5),
    ("Nothing abnormal Detected", 0.05, 0),
    ("Nothing abnormal Detected", 0.18, 1),
    ("Severe Dysplasia", 0.05, 3),
    ("Severe Dysplasia", 0.50, 4),
    ("VARIABLE DIAGNOSIS", 0.05, 0),      # dentist-confirmed: 0 in every band
    ("VARIABLE DIAGNOSIS", 0.18, 0),
    ("VARIABLE DIAGNOSIS", 0.50, 0),
])
def test_known_scores(diagnosis, deviation, score):
    assert get_final_score(diagnosis, deviation) == score


@pytest.mark.parametrize("spelling", LIVE_DB_SPELLINGS)
def test_every_live_db_spelling_resolves(spelling):
    assert get_final_score(spelling, 0.1) is not None


def test_name_matching_ignores_case_spaces_and_apostrophe():
    assert get_final_score("  fibroma ", 0.5) == 3
    assert get_final_score("Smoker’s Palate", 0.1) == get_final_score("smoker's palate", 0.1) == 2
    assert get_final_score("FIBRO EPITHELIAL POLYP", 0.1) == get_final_score("Fibroepithelial Polyp", 0.1)


def test_unknown_diagnosis_returns_none():
    assert get_final_score("Nonexistent Diagnosis", 0.15) is None