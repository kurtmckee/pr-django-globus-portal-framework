import json
from django.shortcuts import render
from globus_portal_framework.search import utils
from django.conf import settings


def index(request, index=settings.SEARCH_INDEX):
    context = {}
    if request.method == 'POST' and request.body:
        results = utils.search(index, request.POST.get('q'),
                               request.POST.get('filters'), request.user)
        context.update(results)
    return render(request, 'search.html', context)


def mock_overview(request, index='foo', subject='bar'):
    filename = 'globus_portal_framework/search/data/mock-detail-overview.json'
    with open(filename) as f:
        data = json.loads(f.read())
        detail_data = utils.map_to_datacite(data)
        return render(request, 'detail-overview.html',
                      {'detail_data': detail_data,
                       'index': index, 'subject': subject})


def mock_metadata(request, index='foo', subject='bar'):
    filename = 'globus_portal_framework/search/data/mock-detail-metadata.json'
    with open(filename) as f:
        data = json.loads(f.read())
        context = {'table_head': data['headers'],
                   'table_body': data['body'],
                   'index': index, 'subject': subject}

        return render(request, 'detail-metadata.html', context)


def detail(request, index, subject):
    client = utils.load_search_client(request.user)
    result = client.get_subject(index, subject)
    result_data = result.data['content'][0][settings.SEARCH_INDEX]
    detail_data = utils.map_to_datacite(result_data)
    context = {'detail_data': detail_data, 'index': index, 'subject': subject}
    return render(request, 'detail-overview.html', context)