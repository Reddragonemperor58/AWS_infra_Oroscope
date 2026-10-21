"""Clinical rules lookup against the clinical_rules table in Aurora (ADR 0011).

Scoring lives in scoring_engine.py; the old JSON-file loader, 4-field matcher and
calculate_final_score were removed (dead code, and a second copy of the band thresholds).
"""
from typing import Dict, Optional

from sqlalchemy import text


def get_differential_and_advise(db, ulcer, patch, growth, mucosal_condition,
                                sharp_objects, pigmentation, symptoms, habits,
                                oral_mapping, provisional_diagnosis) -> Optional[Dict[str, str]]:
    """Returns {"differential_diagnosis", "advise"} for the ten-field key, or None.

    The nine clinical inputs are exact matches (fixed dropdown values; keeps the unique
    index usable). provisional_diagnosis ignores case and surrounding spaces, because the
    source data stores the same diagnosis in several spellings (e.g. "SPECKLED LEUKOPLAKIA",
    " Speckled Leukoplakia"). Verified safe: no nine-input combination has two spellings
    of one diagnosis with different answers (0 conflicts). ORDER BY id makes the pick
    deterministic when several spellings match.
    """
    row = db.execute(
        text("""
            SELECT differential_diagnosis, advise FROM clinical_rules
            WHERE ulcer = :ulcer AND patch = :patch AND growth = :growth
              AND mucosal_condition = :mucosal_condition
              AND sharp_objects = :sharp_objects AND pigmentation = :pigmentation
              AND symptoms = :symptoms AND habits = :habits
              AND oral_mapping = :oral_mapping
              AND upper(btrim(provisional_diagnosis)) = upper(btrim(:provisional_diagnosis))
            ORDER BY id
            LIMIT 1
        """),
        {
            "ulcer": ulcer, "patch": patch, "growth": growth,
            "mucosal_condition": mucosal_condition, "sharp_objects": sharp_objects,
            "pigmentation": pigmentation, "symptoms": symptoms, "habits": habits,
            "oral_mapping": oral_mapping, "provisional_diagnosis": provisional_diagnosis,
        },
    ).first()
    if not row:
        return None
    return {"differential_diagnosis": row[0], "advise": row[1]}