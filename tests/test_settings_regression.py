import pytest

from .conftest import auth_headers


def _unwrap(setting_value):
    if isinstance(setting_value, dict) and 'value' in setting_value and len(setting_value) == 1:
        return setting_value['value']
    return setting_value


def test_bulk_settings_update_normalizes_profile(api_client):
    payload = {
        "updates": {
            "message_length_profile": {"short": 5, "medium": 3, "long": 2},
            "reply_probability": {"value": 0.45},
        }
    }
    response = api_client.put('/settings/bulk', json=payload, headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    profile = _unwrap(next(item for item in data if item['key'] == 'message_length_profile')['value'])
    assert pytest.approx(sum(profile.values()), rel=1e-6) == 1.0
    assert profile['short'] > profile['medium'] > profile['long']

    # Ensure persisted normalization when fetching settings again
    list_resp = api_client.get('/settings', headers=auth_headers())
    assert list_resp.status_code == 200
    settings = {item['key']: _unwrap(item['value']) for item in list_resp.json()}
    assert pytest.approx(sum(settings['message_length_profile'].values()), rel=1e-6) == 1.0
    assert settings['reply_probability'] == pytest.approx(0.45)


def test_patch_setting_updates_single_key(api_client):
    response = api_client.patch(
        '/settings/scale_factor',
        json={'value': 1.75},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data['key'] == 'scale_factor'
    assert _unwrap(data['value']) == pytest.approx(1.75)

    # Update message_length_profile via patch
    patch_resp = api_client.patch(
        '/settings/message_length_profile',
        json={'value': {'short': 0.2, 'medium': 0.2, 'long': 0.6}},
        headers=auth_headers(),
    )
    assert patch_resp.status_code == 200
    profile = _unwrap(patch_resp.json()['value'])
    assert pytest.approx(sum(profile.values()), rel=1e-6) == 1.0
    assert profile['long'] == pytest.approx(0.6)


def test_bulk_update_requires_payload(api_client):
    response = api_client.put('/settings/bulk', json={'updates': {}}, headers=auth_headers())
    assert response.status_code == 400
    assert 'No updates' in response.text


def test_patch_news_feed_urls_validates_and_deduplicates(api_client):
    response = api_client.patch(
        '/settings/news_feed_urls',
        json={
            'value': [
                'https://example.com/rss',
                'https://another.com/feed',
                'https://example.com/rss',  # duplicate
                '  https://third.com/news  ',
            ]
        },
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    feeds = _unwrap(data['value'])
    assert feeds == [
        'https://example.com/rss',
        'https://another.com/feed',
        'https://third.com/news',
    ]

    # Ensure persisted normalization when fetching settings again
    fetched = api_client.get('/settings', headers=auth_headers())
    assert fetched.status_code == 200
    settings = {item['key']: _unwrap(item['value']) for item in fetched.json()}
    assert settings['news_feed_urls'] == feeds


def test_patch_news_feed_urls_rejects_invalid_urls(api_client):
    response = api_client.patch(
        '/settings/news_feed_urls',
        json={'value': ['https://valid.com/rss', 'notaurl']},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert 'Geçersiz RSS adresi' in response.text


def test_metrics_handles_wrapped_setting_values(api_client):
    from database import SessionLocal, Setting

    db = SessionLocal()
    try:
        fixtures = {
            'simulation_active': {'value': True},
            'scale_factor': {'value': 1.75},
            'rate_limit_hits': {'value': 12},
            'telegram_429_count': {'value': 4},
            'telegram_5xx_count': {'value': 7},
        }
        for key, value in fixtures.items():
            row = db.query(Setting).filter(Setting.key == key).first()
            if row is None:
                db.add(Setting(key=key, value=value))
            else:
                row.value = value
        db.commit()
    finally:
        db.close()

    response = api_client.get('/metrics', headers=auth_headers())
    assert response.status_code == 200
    data = response.json()

    assert data['simulation_active'] is True
    assert data['scale_factor'] == pytest.approx(1.75)
    assert data['rate_limit_hits'] == 12
    assert data['telegram_429_count'] == 4
    assert data['telegram_5xx_count'] == 7
