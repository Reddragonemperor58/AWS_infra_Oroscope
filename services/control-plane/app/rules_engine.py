import json
import os
import logging
from typing import Optional, Dict
from sqlalchemy import text


# Setup basic logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Module-level caches
_clinical_rules_cache = None
_scoring_rules_cache = None

def _load_rules() -> None:
    """
    Task 5: The Loader.
    Reads the JSON files once and caches them in module-level variables.
    This runs exactly once per Lambda cold start.
    """
    global _clinical_rules_cache, _scoring_rules_cache
    
    # Only load if the cache is empty
    if _clinical_rules_cache is not None and _scoring_rules_cache is not None:
        return

    # Determine absolute paths relative to this file's location
    base_dir = os.path.dirname(__file__)
    clinical_path = os.path.join(base_dir, "data", "clinical_rules.json")
    scoring_path = os.path.join(base_dir, "data", "scoring_rules.json")

    try:
        with open(clinical_path, "r") as f:
            _clinical_rules_cache = json.load(f)
        
        with open(scoring_path, "r") as f:
            _scoring_rules_cache = json.load(f)
            
        logger.info("Successfully loaded rules engine data into cache.")
    except Exception as e:
        logger.error(f"Failed to load rule files: {str(e)}")
        # If files are missing/malformed, we need to fail loudly during cold start
        raise

def get_clinical_diagnosis(ulcer: str, patch: str, growth: str, mucosal_condition: str) -> Optional[Dict[str, str]]:
    """
    Task 6: The Clinical Match Function.
    Case-insensitive exact match across all four fields.
    """
    _load_rules()
    
    # Normalize inputs for safe comparison
    u_in = ulcer.strip().lower()
    p_in = patch.strip().lower()
    g_in = growth.strip().lower()
    m_in = mucosal_condition.strip().lower()
    
    matches = []
    
    for rule in _clinical_rules_cache:
        if (rule.get("ulcer", "").strip().lower() == u_in and
            rule.get("patch", "").strip().lower() == p_in and
            rule.get("growth", "").strip().lower() == g_in and
            rule.get("mucosal_condition", "").strip().lower() == m_in):
            
            matches.append({
                "provisional_diagnosis": rule.get("provisional_diagnosis", ""),
                "differential_diagnosis": rule.get("differential_diagnosis", ""),
                "advise": rule.get("advise", "")
            })
            
    if not matches:
        return None
        
    if len(matches) > 1:
        # Decision: Log a warning for auditability, but return the first match 
        # to prevent crashing the clinical workflow.
        logger.warning(f"Duplicate clinical rules found for inputs: {u_in}, {p_in}, {g_in}, {m_in}")
        
    return matches[0]

def calculate_final_score(provisional_diagnosis: str, deviation_score: float) -> Optional[int]:
    """
    Task 7: The Scoring Function.
    Maps deviation index to a category, then matches against the scoring table using substring containment.
    """
    _load_rules()
    
    # Replicate the exact threshold bands from the original app.py
    dev = float(deviation_score)
    if dev < 0.16:
        img_category = "variable diagnosis"
    elif dev <= 0.20:
        img_category = "borderline"
    else:
        img_category = "suggestive of dysplasia"
        
    diag_key = provisional_diagnosis.strip().lower()
    
    for rule in _scoring_rules_cache:
        rule_diag = rule.get("provisional_diagnosis", "").strip().lower()
        rule_analysis = rule.get("image_analysis", "").strip().lower()
        
        # Exact match on provisional diagnosis, substring match on image category
        if diag_key == rule_diag and img_category in rule_analysis:
            return int(rule.get("score", 0))
            
    return None


def get_differential_and_advise(db, ulcer, patch, growth, mucosal_condition,
                                   sharp_objects, pigmentation, symptoms, habits,
                                   oral_mapping, provisional_diagnosis):
    """
    Queries the clinical_rules table via the existing Data API session —
    same database.py engine every other endpoint already uses. No local
    file, no in-memory cache; the 592K-row table lives in Aurora.
    """
    result = db.execute(
        text("""
            SELECT differential_diagnosis, advise FROM clinical_rules
            WHERE ulcer = :ulcer AND patch = :patch AND growth = :growth
              AND mucosal_condition = :mucosal_condition
              AND sharp_objects = :sharp_objects AND pigmentation = :pigmentation
              AND symptoms = :symptoms AND habits = :habits
              AND oral_mapping = :oral_mapping
              AND provisional_diagnosis = :provisional_diagnosis
        """),
        {
            "ulcer": ulcer, "patch": patch, "growth": growth,
            "mucosal_condition": mucosal_condition, "sharp_objects": sharp_objects,
            "pigmentation": pigmentation, "symptoms": symptoms, "habits": habits,
            "oral_mapping": oral_mapping, "provisional_diagnosis": provisional_diagnosis,
        },
    ).first()
    if not result:
        return None
    return {"differential_diagnosis": result[0], "advise": result[1]}