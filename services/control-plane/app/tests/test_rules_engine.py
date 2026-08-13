import pytest
from app.rules_engine import get_clinical_diagnosis, calculate_final_score

# --- CLINICAL MATCH TESTS ---

def test_clinical_diagnosis_exact_match():
    """Test that an exact, case-insensitive match returns the correct row."""
    # Using mixed casing to prove the .lower() logic works
    result = get_clinical_diagnosis(
        ulcer="ROUND ulcer", 
        patch="RED Patch", 
        growth="round GROWTH", 
        mucosal_condition="Marble Appearance"
    )
    
    assert result is not None
    assert result["provisional_diagnosis"] == "PLACEHOLDER - Diagnosis A"
    assert result["differential_diagnosis"] == "PLACEHOLDER - Diff A"
    assert result["advise"] == "PLACEHOLDER - Advise A"

def test_clinical_diagnosis_near_miss():
    """Test that changing a single field breaks the match and returns None."""
    result = get_clinical_diagnosis(
        ulcer="Round Ulcer", 
        patch="White Patch", # <-- This is wrong for Diagnosis A
        growth="Round Growth", 
        mucosal_condition="Marble Appearance"
    )
    
    assert result is None

# --- SCORING TESTS ---

def test_score_boundary_variable_diagnosis():
    """Test value strictly less than 0.16 (< 0.16)."""
    # 0.159 should map to "variable diagnosis" (Score 1 for Diagnosis A)
    score = calculate_final_score("PLACEHOLDER - Diagnosis A", 0.159)
    assert score == 1

def test_score_boundary_exactly_0_16():
    """
    Test exactly 0.16. 
    The rule is < 0.16 for variable, <= 0.20 for borderline. 
    Therefore, exactly 0.16 must be borderline.
    """
    # "borderline" is Score 3 for Diagnosis A
    score = calculate_final_score("PLACEHOLDER - Diagnosis A", 0.16)
    assert score == 3

def test_score_boundary_exactly_0_20():
    """
    Test exactly 0.20.
    The rule is <= 0.20 for borderline.
    """
    score = calculate_final_score("PLACEHOLDER - Diagnosis A", 0.20)
    assert score == 3

def test_score_boundary_suggestive():
    """Test value strictly greater than 0.20."""
    # "suggestive of dysplasia" is Score 5 for Diagnosis A
    score = calculate_final_score("PLACEHOLDER - Diagnosis A", 0.21)
    assert score == 5

def test_scoring_no_match():
    """Test that an unrecognized provisional diagnosis returns None."""
    score = calculate_final_score("Nonexistent Diagnosis", 0.15)
    assert score is None