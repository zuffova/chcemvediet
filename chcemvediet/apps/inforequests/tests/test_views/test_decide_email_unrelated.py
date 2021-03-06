# vim: expandtab
# -*- coding: utf-8 -*-
import json

from django.core.urlresolvers import reverse
from django.http import JsonResponse

from poleno.utils.misc import Bunch
from poleno.utils.test import patch_with_exception

from ...models import InforequestEmail
from . import CustomTestCase
from .common_tests import OwnedNotClosedInforequestArgTests, OldestUndecitedEmailArgTests
from .common_tests import CommonDecoratorsTests

class DecideEmailUnrelatedViewTest(
        CommonDecoratorsTests,
        OwnedNotClosedInforequestArgTests,
        OldestUndecitedEmailArgTests,
        CustomTestCase,
        ):
    u"""
    Tests for ``decide_email_unrelated()`` view registered as
    "inforequests:decide_email_unrelated".
    """
    view_name = u'inforequests:decide_email_unrelated'

    def _create_scenario(self, **kwargs):
        res = Bunch()

        inforequest_args = kwargs.pop(u'inforequest_args', [])
        res.inforequest, res.branch, res.actions = self._create_inforequest_scenario(*inforequest_args)

        email_args = kwargs.pop(u'email_args', {})
        email_args.setdefault(u'inforequest', res.inforequest)
        res.email, res.rel = self._create_inforequest_email(**email_args)

        self.assertEqual(kwargs, {})
        return res

    def _create_url(self, scenario, **kwargs):
        inforequest_pk = kwargs.pop(u'inforequest_pk', scenario.inforequest.pk)
        email_pk = kwargs.pop(u'email_pk', scenario.email.pk)
        url = reverse(self.view_name, args=(inforequest_pk, email_pk))

        self.assertEqual(kwargs, {})
        return url


    def test_get_renders_form(self):
        scenario = self._create_scenario()
        url = self._create_url(scenario)

        self._login_user()
        response = self.client.get(url, HTTP_X_REQUESTED_WITH=u'XMLHttpRequest')

        self.assertTemplateUsed(response, u'inforequests/modals/unrelated-email.html')
        self.assertEqual(response.context[u'inforequest'], scenario.inforequest)
        self.assertEqual(response.context[u'email'], scenario.email)
        self.assertNotIn(u'form', response.context)

    def test_get_related_models_are_prefetched_before_render(self):
        scenario = self._create_scenario()
        url = self._create_url(scenario)

        self._login_user()
        with self.assertQueriesDuringRender([]):
            response = self.client.get(url, HTTP_X_REQUESTED_WITH=u'XMLHttpRequest')

    def test_post_marks_email_as_unrelated(self):
        scenario = self._create_scenario()
        data = self._create_post_data()
        url = self._create_url(scenario)

        self._login_user()
        response = self.client.post(url, data, HTTP_X_REQUESTED_WITH=u'XMLHttpRequest')

        scenario.rel = InforequestEmail.objects.get(pk=scenario.rel.pk)
        self.assertEqual(scenario.rel.type, InforequestEmail.TYPES.UNRELATED)

    def test_post_does_not_mark_email_as_unrelated_if_exception_raised(self):
        scenario = self._create_scenario()
        data = self._create_post_data()
        url = self._create_url(scenario)

        self._login_user()
        with patch_with_exception(u'chcemvediet.apps.inforequests.views.JsonResponse'):
            response = self.client.post(url, data, HTTP_X_REQUESTED_WITH=u'XMLHttpRequest')

        scenario.rel = InforequestEmail.objects.get(pk=scenario.rel.pk)
        self.assertEqual(scenario.rel.type, InforequestEmail.TYPES.UNDECIDED)

    def test_post_returns_json_with_success_and_inforequests_detail(self):
        scenario = self._create_scenario()
        data = self._create_post_data()
        url = self._create_url(scenario)

        self._login_user()
        response = self.client.post(url, data, HTTP_X_REQUESTED_WITH=u'XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, JsonResponse)
        self.assertTemplateUsed(response, u'inforequests/detail-main.html')
        self.assertEqual(response.context[u'inforequest'], scenario.inforequest)

        data = json.loads(response.content)
        self.assertEqual(data[u'result'], u'success')

    def test_post_related_models_are_prefetched_before_render(self):
        scenario = self._create_scenario()
        data = self._create_post_data()
        url = self._create_url(scenario)

        self._login_user()
        with self.assertQueriesDuringRender([]):
            response = self.client.post(url, data, HTTP_X_REQUESTED_WITH=u'XMLHttpRequest')
