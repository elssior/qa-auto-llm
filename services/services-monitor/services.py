import pytest
from services.conftest import validate_schema

ENDPOINT = "/services"
METHOD = "GET"

SUCCESS_RESPONSE_SCHEMA = {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string", "description": "Service name"}, "system": {"type": "string", "description": "System name"}, "description": {"type": "string", "description": "Service description"}, "address": {
    "type": "string", "description": "Service address"}, "enabled": {"type": "boolean", "description": "Service enabled status"}, "last_good_time": {"type": "string", "format": "date-time", "description": "Last good time"}, "state": {"type": "string", "enum": ["good", "bad"], "description": "Service state"}}, "required": ["name", "address", "state"]}}

POSITIVE_CASES = [
    pytest.param({"body": None}, 200, id="TC-001_name"),
    pytest.param({"query_params": {"name": "service1",
                 "system": "system1"}}, 200, id="TC-002_name"),
]

NEGATIVE_CASES = [
    pytest.param({"path": "/services1"}, 404, id="TC-003_invalid_path"),
    pytest.param({"method": "POST"}, 405, id="TC-004_invalid_method"),
    pytest.param({"headers": {"Authorization": ""}}, 401, id="TC-005_no_auth"),
    pytest.param({"headers": {"X-Invalid-Header": ""}},
                 400, id="TC-006_invalid_header"),
    pytest.param({"headers": {"Content-Type": "application/json; charset=utf-8"}},
                 400, id="TC-007_invalid_content_type"),
    pytest.param({"headers": {"Accept": "application/json; charset=utf-8"}},
                 400, id="TC-008_invalid_accept_header"),
    pytest.param({"path": "/services/very/long/path/with/multiple/directory/names"},
                 414, id="TC-009_very_long_url"),
    pytest.param({"path": "/services?name=service1' OR 1=1 --"},
                 400, id="TC-010_sql_injection"),
    pytest.param({"path": "/services?name=<script>alert('XSS')</script>"},
                 400, id="TC-011_xss_attack"),
]


@pytest.mark.parametrize("data, expected_status", POSITIVE_CASES)
def test_get_positive(api_client, attach_curl_on_fail, data, expected_status):
    """Позитивные тесты"""
    with attach_curl_on_fail(ENDPOINT, data, None, METHOD):
        response = api_client.get(ENDPOINT, params=data)
        assert response.status_code == expected_status
        validate_schema(response.json(), SUCCESS_RESPONSE_SCHEMA)


@pytest.mark.parametrize("data, expected_status", NEGATIVE_CASES)
def test_services_negative(api_client, attach_curl_on_fail, data, expected_status):
    """Негативные тесты"""
    with attach_curl_on_fail(ENDPOINT, data, None, METHOD):
        response = api_client.get(ENDPOINT, params=data)
        assert response.status_code == expected_status