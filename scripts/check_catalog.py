#!/usr/bin/env python3
"""Validate catalog structure and optionally check public GitHub availability."""
import argparse
import json
import re
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPO = re.compile(r'^https://github\.com/omiusgm/([A-Za-z0-9_.-]+)$')
REQUIRED = {'id', 'title', 'kind', 'status', 'repository', 'readme', 'agent_handoff',
            'capabilities', 'platforms', 'requirements', 'dependencies',
            'limitations', 'verified_on', 'verification'}


def validate(data):
    if data.get('schema_version') != 1 or data.get('owner') != 'omiusgm':
        raise ValueError('Unsupported schema or catalog owner.')
    date.fromisoformat(data['updated_at'])
    rows = data.get('solutions')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Expected a non-empty solutions list.')
    ids = set()
    for item in rows:
        if not REQUIRED.issubset(item):
            raise ValueError('Incomplete solution entry.')
        if item['id'] in ids:
            raise ValueError('Duplicate solution identifier.')
        ids.add(item['id'])
        if item['status'] != 'published' or not REPO.fullmatch(item['repository']):
            raise ValueError('Only published public-owner repository entries are supported.')
        for field in ['readme', 'agent_handoff']:
            if not item[field].startswith(item['repository'] + '/blob/'):
                raise ValueError('Documentation must belong to its repository.')
        for field in ['capabilities', 'platforms', 'requirements', 'limitations']:
            if not isinstance(item[field], list) or not item[field] or not all(
                    isinstance(x, str) and x.strip() for x in item[field]):
                raise ValueError('Expected meaningful capability/requirement lists.')
        if not isinstance(item['dependencies'], list):
            raise ValueError('Dependencies must be a list.')
        date.fromisoformat(item['verified_on'])
    for item in rows:
        if not set(item['dependencies']).issubset(ids):
            raise ValueError('Dependency points to an unknown solution.')
    return rows


def get_json(url):
    request = Request(url, headers={'User-Agent': 'Agent-Ezh-Catalog-Check',
                                   'Accept': 'application/vnd.github+json'})
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def check_online(rows):
    for item in rows:
        name = REPO.fullmatch(item['repository']).group(1)
        base = 'https://api.github.com/repos/omiusgm/' + name
        info = get_json(base)
        if info.get('private') is not False or info.get('archived'):
            raise ValueError('Repository is not an active public repository: ' + name)
        readme = get_json(base + '/readme')
        if not readme.get('size'):
            raise ValueError('README is empty: ' + name)
        print('public + README:', name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--online', action='store_true')
    args = parser.parse_args()
    data = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
    rows = validate(data)
    print('Catalog structure OK:', len(rows), 'solutions')
    if args.online:
        check_online(rows)


if __name__ == '__main__':
    main()
