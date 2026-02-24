"""Tests du service coach."""
import pytest
from unittest.mock import MagicMock


def test_get_coaches_list_empty_when_no_users():
    """get_coaches_list retourne liste vide si pas d'utilisateurs."""
    from services.coach_service import get_coaches_list
    
    load_users = MagicMock(return_value={})
    get_by_gym = MagicMock(return_value=[])
    
    result = get_coaches_list(
        load_users_fn=load_users,
        get_coaches_by_gym_id_fn=get_by_gym,
        gym_id=None,
    )
    assert result == []
    load_users.assert_called_once()


def test_get_coaches_list_filters_by_gym_id():
    """get_coaches_list délègue à get_coaches_by_gym_id quand gym_id fourni."""
    from services.coach_service import get_coaches_list
    
    load_users = MagicMock()
    get_by_gym = MagicMock(return_value=[{"id": "c1", "email": "coach@test.com"}])
    
    result = get_coaches_list(
        load_users_fn=load_users,
        get_coaches_by_gym_id_fn=get_by_gym,
        gym_id="gym_123",
    )
    assert len(result) == 1
    assert result[0]["email"] == "coach@test.com"
    get_by_gym.assert_called_once_with("gym_123")
    load_users.assert_not_called()


def test_get_coaches_list_excludes_blocked():
    """get_coaches_list exclut les coaches bloqués."""
    from services.coach_service import get_coaches_list
    
    load_users = MagicMock(return_value={
        "coach1@test.com": {
            "role": "coach",
            "profile_completed": True,
            "subscription_status": "active",
            "full_name": "Coach 1",
        },
        "coach2@test.com": {
            "role": "coach",
            "profile_completed": True,
            "subscription_status": "blocked",
            "full_name": "Coach 2",
        },
    })
    get_by_gym = MagicMock()
    
    result = get_coaches_list(
        load_users_fn=load_users,
        get_coaches_by_gym_id_fn=get_by_gym,
    )
    assert len(result) == 1
    assert result[0]["email"] == "coach1@test.com"
