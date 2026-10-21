from unittest import mock

from django.core.cache import caches
from django.test import TestCase

from core.test_helpers import create_test_interactive_user
from location import models as location_models
from location.models import free_cache_for_user
from location.test_helpers import create_test_location


class FreeCacheForUserTest(TestCase):
    """Dropping the cached location sets of users leaves the rest of the cache alone."""

    def setUp(self):
        self.cache = caches["location"]
        self.default = caches["default"]
        self.cache.clear()
        self.addCleanup(self.cache.clear)
        self.addCleanup(self.default.clear)
        self.user = create_test_interactive_user(username="LocationCacheUser").i_user
        self.other = create_test_interactive_user(username="LocationCacheOther").i_user
        self.user_keys = [f"user_locations_{self.user.id}", f"user_districts_{self.user.id}"]
        self.other_keys = [f"user_locations_{self.other.id}", f"user_districts_{self.other.id}"]
        self.cache.set_many({key: [1] for key in self.user_keys + self.other_keys + ["user_districts_all"]})
        self.cache.set("location_types", "kept")
        self.default.set("unrelated", "kept")

    def _assert_others_kept(self):
        self.assertEqual(self.cache.get("location_types"), "kept")
        self.assertEqual(self.default.get("unrelated"), "kept")

    def test_one_user(self):
        free_cache_for_user(self.user.id)
        self.assertEqual(self.cache.get_many(self.user_keys), {})
        self.assertEqual(set(self.cache.get_many(self.other_keys + ["user_districts_all"])),
                         set(self.other_keys + ["user_districts_all"]))
        self._assert_others_kept()

    def test_every_user(self):
        free_cache_for_user()
        self.assertEqual(self.cache.get_many(self.user_keys + self.other_keys + ["user_districts_all"]), {})
        self._assert_others_kept()

    def test_saving_a_location_drops_every_user_set_only(self):
        create_test_location("R")
        self.assertEqual(self.cache.get_many(self.user_keys + self.other_keys), {})
        self.assertEqual(self.default.get("unrelated"), "kept")

    def test_every_user_with_a_pattern_capable_backend(self):
        backend = mock.Mock(spec=["delete_pattern", "delete_many", "clear"])
        with mock.patch.object(location_models, "cache", backend):
            free_cache_for_user()
        backend.delete_pattern.assert_has_calls([mock.call("user_locations_*"), mock.call("user_districts_*")])
        backend.delete_many.assert_not_called()
        backend.clear.assert_not_called()
