"""Dropping every user's location sets on Django's own Redis backend.

That backend has no ``delete_pattern``, and its ``clear()`` is a FLUSHDB of the
database that the default, location and coverage aliases share. The backend is
stood in for by a stub of its class; the keys are read and dropped through the
configured location cache.
"""
from unittest.mock import MagicMock, patch

from django.core.cache import caches
from django.core.cache.backends.redis import RedisCache
from django.test import TestCase

from core.test_helpers import create_test_interactive_user, create_test_technical_user
from location import models as location_models
from location.models import free_cache_for_user
from location.test_helpers import create_test_location


class FreeCacheForEveryUserOnDjangoRedisTest(TestCase):
    def setUp(self):
        self.location = caches["location"]
        self.default = caches["default"]
        self.user = create_test_interactive_user(username="LocationFlushUser").i_user
        self.other = create_test_interactive_user(username="LocationFlushOther").i_user
        self.technical = create_test_technical_user(username="LocationFlushTechnical").t_user
        self.user_keys = [
            f"{key}_{owner.id}"
            for owner in (self.user, self.other, self.technical)
            for key in ("user_locations", "user_districts")
        ] + ["user_districts_all"]
        self.location.set_many({key: [1] for key in self.user_keys})
        self.location.set("location_probe", "kept")
        self.default.set("default_probe", "kept")
        self.addCleanup(self.location.clear)
        self.addCleanup(self.default.clear)
        self.backend = MagicMock(spec=RedisCache)
        patcher = patch.object(location_models, "cache", self.backend)
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_every_user_set_dropped_rest_kept(self):
        self.backend.clear.assert_not_called()
        self.assertEqual(self.location.get_many(self.user_keys), {})
        self.assertEqual(self.location.get("location_probe"), "kept")
        self.assertEqual(self.default.get("default_probe"), "kept")

    def test_every_user(self):
        free_cache_for_user()
        self.assert_every_user_set_dropped_rest_kept()

    def test_saving_a_location(self):
        with self.captureOnCommitCallbacks(execute=True):
            create_test_location("R", custom_props={"code": "FLUSHR"})
        self.assert_every_user_set_dropped_rest_kept()

    def test_one_user_still_drops_only_that_users_keys(self):
        free_cache_for_user(self.user.id)
        self.assertEqual(
            ["user_locations_%s" % self.user.id, "user_districts_%s" % self.user.id],
            [call.args[0] for call in self.backend.delete.call_args_list],
        )
        self.backend.clear.assert_not_called()
