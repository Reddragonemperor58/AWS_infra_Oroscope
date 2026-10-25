"""API Gateway forwards only routes declared in Terraform. A FastAPI endpoint with no matching
route_key works in every unit test and then fails in production (404 without CORS headers, which the
browser shows as "Cannot reach the server"). This test compares the two lists."""
import re
from pathlib import Path

INFRA = Path(__file__).resolve().parents[4] / "infra"


def declared_routes():
    keys = set()
    for tf in INFRA.glob("*.tf"):
        for m in re.finditer(r'route_key\s*=\s*"([A-Z]+) (/[^"]*)"', tf.read_text(encoding="utf-8")):
            keys.add((m.group(1), m.group(2)))
    return keys


def test_every_api_endpoint_has_a_gateway_route():
    from app import main

    if not INFRA.is_dir():  # e.g. the app is packaged without the infra folder
        import pytest
        pytest.skip("infra folder not found")
    declared = declared_routes()
    needed = {(method.upper(), path) for path, ops in main.app.openapi()["paths"].items() for method in ops}
    missing = sorted(needed - declared)
    assert not missing, f"Add these to infra/*.tf (aws_apigatewayv2_route): {missing}"
