from copy import deepcopy
from unittest import mock
from urllib.parse import quote_plus

from django.test import TestCase, Client
from django.test.utils import override_settings
from django.urls import reverse

from globus_portal_framework.tests import test_gsearch, MOCK_RESULT
from globus_portal_framework.tests.mocks import (
    get_logged_in_client, MockTransferClient)

from globus_portal_framework import (
    PreviewException, PreviewPermissionDenied, PreviewNotFound,
    PreviewServerError, PreviewBinaryData)

SEARCH_INDEXES = {'myindex': {
    # Randomly generated and not real
    'uuid': '1e0be00f-8156-499e-980d-f7fb26157c02'
}}

MOCK_RFM = [
    {
        'url': 'https://foo.example.com',
        'length': 1337,
        'filename': 'foo.txt',
        'sha256': 'sha256securehashexample'
    }
]

SEARCH_INDEXES_TRANSFER = deepcopy(SEARCH_INDEXES)
SEARCH_INDEXES_TRANSFER['myindex']['fields'] = ['remote_file_manifest']


class MockSearchGetSubject:
    def __init__(self):
        self.data = test_gsearch.get_mock_data(MOCK_RESULT)


class SearchViewsTest(TestCase):

    def setUp(self):
        self.c = Client()
        # Mock endpoint for transfer and preview (Globus HTTPS)
        self.foo_ep = 'eae9d78d-b353-4fa7-9dbe-c60d681bc783'
        # A valid subject url given our views
        self.subject_url = quote_plus('globus://{}/{}'.format(self.foo_ep,
                                                              'foo'))
        self.index = 'myindex'

    @mock.patch('globus_portal_framework.views.post_search')
    @override_settings(SEARCH_INDEXES=SEARCH_INDEXES)
    def test_index(self, post_search):
        post_search.return_value = {}
        r = self.c.get(reverse('search', args=[self.index]))
        self.assertEqual(r.status_code, 200)

    @mock.patch('globus_sdk.SearchClient.get_subject')
    @override_settings(SEARCH_INDEXES=SEARCH_INDEXES)
    def test_detail(self, get_subject):
        get_subject.return_value = MockSearchGetSubject()
        url = reverse('detail', args=[self.index, 'mysubject'])
        r = self.c.get(url)
        self.assertEqual(r.status_code, 200)

    @mock.patch('globus_portal_framework.views.log')
    @mock.patch('globus_portal_framework.views.get_helper_page_url',
                mock.Mock())
    @mock.patch('globus_sdk.SearchClient.get_subject')
    @mock.patch('globus_sdk.TransferClient', MockTransferClient)
    @override_settings(SEARCH_INDEXES=SEARCH_INDEXES)
    def test_detail_transfer_no_field_rfm(self, get_subject, log):
        client, user = get_logged_in_client('mal', ['search.api.globus.org',
                                                    'transfer.api.globus.org'])
        get_subject.return_value = MockSearchGetSubject()
        url = reverse('detail-transfer', args=[self.index, self.subject_url])
        r = client.get(url)
        self.assertTrue(log.error.called)
        self.assertEqual(r.status_code, 200)

    @mock.patch('globus_portal_framework.views.log')
    @mock.patch('globus_portal_framework.views.get_helper_page_url',
                mock.Mock())
    @mock.patch('globus_sdk.SearchClient.get_subject')
    @mock.patch('globus_sdk.TransferClient', MockTransferClient)
    @override_settings(SEARCH_INDEXES=SEARCH_INDEXES_TRANSFER)
    def test_detail_transfer_no_search_rfm(self, get_subject, log):
        client, user = get_logged_in_client('mal', ['search.api.globus.org',
                                                    'transfer.api.globus.org'])
        get_subject.return_value = MockSearchGetSubject()
        url = reverse('detail-transfer', args=[self.index, self.subject_url])
        r = client.get(url)
        self.assertTrue(log.error.called)
        self.assertEqual(r.status_code, 200)

    @mock.patch('globus_portal_framework.views.log')
    @mock.patch('globus_portal_framework.views.get_helper_page_url',
                mock.Mock())
    @mock.patch('globus_sdk.SearchClient.get_subject')
    @mock.patch('globus_sdk.TransferClient', MockTransferClient)
    @override_settings(SEARCH_INDEXES=SEARCH_INDEXES_TRANSFER)
    def test_detail_transfer_setup_correctly(self, get_subject, log):
        client, user = get_logged_in_client('mal', ['search.api.globus.org',
                                                    'transfer.api.globus.org'])
        mock_search = MockSearchGetSubject()
        mock_search.data['content'][0]['remote_file_manifest'] = MOCK_RFM
        get_subject.return_value = mock_search
        url = reverse('detail-transfer', args=[self.index, self.subject_url])
        r = client.get(url)
        self.assertFalse(log.error.called)
        self.assertEqual(r.status_code, 200)

    @mock.patch('globus_portal_framework.views.log')
    @mock.patch('globus_portal_framework.views.preview')
    @mock.patch('globus_sdk.SearchClient.get_subject')
    @mock.patch('globus_sdk.TransferClient', MockTransferClient)
    @override_settings(SEARCH_INDEXES=SEARCH_INDEXES)
    def test_detail_preview(self, get_subject, preview, log):
        preview.return_value = mock.Mock()
        client, user = get_logged_in_client('mal', ['search.api.globus.org',
                                                    'transfer.api.globus.org'])
        get_subject.return_value = MockSearchGetSubject()
        url = reverse('detail-preview', args=[self.index, self.subject_url,
                                              self.foo_ep, 'bar'],
                      )
        r = client.get(url)
        self.assertEqual(len(r.context['messages']), 0)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(log.warning.called)
        self.assertTrue(preview.called)

    @mock.patch('globus_portal_framework.views.log')
    @mock.patch('globus_portal_framework.views.preview')
    @mock.patch('globus_sdk.SearchClient.get_subject')
    @mock.patch('globus_sdk.TransferClient', MockTransferClient)
    @override_settings(SEARCH_INDEXES=SEARCH_INDEXES)
    def test_detail_preview_exceptions(self, get_subject, preview, log):
        client, user = get_logged_in_client('mal', ['search.api.globus.org',
                                                    'transfer.api.globus.org'])
        get_subject.return_value = MockSearchGetSubject()
        excs = (PreviewException, PreviewPermissionDenied, PreviewNotFound,
                PreviewServerError, PreviewBinaryData)
        for exc in excs:
            if exc == PreviewServerError:
                preview.side_effect = PreviewServerError(500, 'Serv Err')
            else:
                preview.side_effect = exc
            url = reverse('detail-preview',
                          args=[self.index, self.subject_url, self.foo_ep,
                                'bar'])
            r = client.get(url)
            self.assertEqual(r.status_code, 200)

        # Once for each: ['UnexpectedError', 'ServerError']
        self.assertEqual(log.exception.call_count, 2)

    @mock.patch('globus_portal_framework.views.post_search')
    @override_settings(SEARCH_INDEXES=SEARCH_INDEXES)
    def test_search_debug(self, post_search):
        post_search.return_value = {'facets': []}
        r = self.c.get(reverse('search-debug', args=[self.index]))
        self.assertEqual(r.status_code, 200)

    @mock.patch('globus_sdk.SearchClient.get_subject')
    @override_settings(SEARCH_INDEXES=SEARCH_INDEXES)
    def test_search_debug_detail(self, get_subject):
        get_subject.return_value = MockSearchGetSubject()
        url = reverse('search-debug-detail', args=[self.index, 'mysubject'])
        r = self.c.get(url)
        self.assertEqual(r.status_code, 200)
