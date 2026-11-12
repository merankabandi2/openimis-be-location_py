import json

from django.conf import settings
from graphql_jwt.shortcuts import get_token
from rest_framework import status

from core.models.openimis_graphql_test_case import (
    BaseTestContext as DummyContext,
    openIMISGraphQLTestCase,
)
from core.test_helpers import create_test_interactive_user, create_test_role
from location.test_helpers import assign_user_districts, create_basic_test_locations


class LocationsStrRestrictedUserTest(openIMISGraphQLTestCase):
    """`locationsStr` narrows on `str` for a user limited to some districts."""

    GRAPHQL_URL = f"/{settings.SITE_ROOT()}graphql"
    GRAPHQL_SCHEMA = True

    @classmethod
    def setUpTestData(cls):
        create_basic_test_locations()
        role = create_test_role(perm_names=["gql_query_locations_perms"], name="LocationsStrReader")
        cls.user = create_test_interactive_user(username="testLocationsStrUser", roles=[role.id])
        cls.token = get_token(cls.user, DummyContext(user=cls.user))
        assign_user_districts(cls.user, ["R2D1", "R2D2"])

    def _codes(self, filters):
        response = self.query(
            "query { locationsStr(%s) { edges { node { code } } } }" % filters,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = json.loads(response.content)
        self.assertNotIn("errors", content)
        return sorted(edge["node"]["code"] for edge in content["data"]["locationsStr"]["edges"])

    def test_without_search_lists_every_allowed_village(self):
        self.assertEqual(self._codes('type: "V"'), ["R2D1M1V1", "R2D2M1V1"])

    def test_search_on_name_narrows_the_allowed_villages(self):
        self.assertEqual(self._codes('type: "V", str: "Radho"'), ["R2D2M1V1"])

    def test_search_on_code_narrows_the_allowed_villages(self):
        self.assertEqual(self._codes('type: "V", str: "R2D1M1V"'), ["R2D1M1V1"])

    def test_search_matching_nothing_returns_nothing(self):
        self.assertEqual(self._codes('type: "V", str: "no-such-village"'), [])

    def test_search_never_reaches_outside_the_allowed_districts(self):
        # R1D1 is not assigned to the user.
        self.assertEqual(self._codes('type: "W", str: "Jamu"'), [])
