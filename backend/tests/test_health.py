"""Basic smoke tests for the Flask application bootstrap."""


def test_health_check(client):
    """GET /health returns 200 or 503 (depending on DB availability)."""
    resp = client.get('/health')
    assert resp.status_code in (200, 503)
    body = resp.get_json()
    assert 'status' in body
    assert body['service'] == 'district360-api'


def test_ping(client):
    """GET /api/v1/ping returns pong."""
    resp = client.get('/api/v1/ping')
    assert resp.status_code == 200
    assert resp.get_json()['message'] == 'pong'


def test_404_returns_json(client):
    """Missing routes return a JSON error, not an HTML page."""
    resp = client.get('/api/v1/does-not-exist')
    assert resp.status_code == 404
    body = resp.get_json()
    assert body['success'] is False
    assert 'error' in body


def test_405_returns_json(client):
    """Wrong HTTP method returns 405 JSON."""
    resp = client.delete('/api/v1/ping')
    assert resp.status_code == 405
    body = resp.get_json()
    assert body['success'] is False
