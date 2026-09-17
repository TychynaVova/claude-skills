#!/usr/bin/env python3
"""Postman API helper для skill provider-postman.

Команди:
  workspaces                              список робочих просторів (id, тип, назва)
  find <provider>                         колекції/папки/оточення з назвою провайдера
  tree <collection_uid>                   дерево колекції (папки, запити)
  build <spec.json> [--dry]               створити колекцію (якщо треба), папку версії, підпапки (довільної
                                          вкладеності: "folders" всередині папки), запити, оточення
  update <spec.json>                      оновити на місці запити вже створеної папки версії (пошук за назвами)
  sync <spec.json> [--dry]                доповнити вже створену папку версії: створити відсутні підпапки й запити,
                                          оновити описи наявних папок, додати в оточення відсутні змінні
                                          (значення наявних не змінюються); наявні запити не чіпає — для них update
  verify <spec.json>                      звірити змінні з запитів і змінні оточення

Ключ: змінна середовища POSTMAN_API_KEY (або файл .env у поточній директорії).

Особливості Postman API (перевірено):
  * PUT/DELETE папок і запитів — id з префіксом власника КОЛЕКЦІЇ: <owner>-<id>;
  * PUT запиту — шлях колекції БЕЗ префікса власника, інакше changeParentError;
  * вкладена папка — поле "folder" (id без префікса) у тілі POST /folders;
  * запит у папку — POST /collections/<uid>/requests?folder=<owner>-<folderId>;
  * відсутній auth у запиту = успадкування від папки.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = 'https://api.getpostman.com'


def load_key():
    key = os.environ.get('POSTMAN_API_KEY')
    if not key and os.path.exists('.env'):
        for line in open('.env', encoding='utf-8'):
            if line.startswith('POSTMAN_API_KEY='):
                key = line.split('=', 1)[1].strip().strip('"')
    if not key:
        sys.exit('POSTMAN_API_KEY не знайдено (env або ./.env)')
    return key


KEY = None
DRY = '--dry' in sys.argv


def call(method, path, body=None):
    if DRY and method != 'GET':
        print('  DRY', method, path, (body or {}).get('name', ''))
        return {'model_id': 'dry', 'collection': {'uid': 'dry-dry'}, 'environment': {'uid': 'dry'}}
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
        headers={'X-Api-Key': KEY, 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f'HTTP {e.code} {method} {path}: {e.read().decode()[:500]}')


def owner_of(uid):
    return uid.split('-', 1)[0]


def bare(uid):
    return uid.split('-', 1)[1]


# ---------- spec → Postman request ----------

def script(listen, lines):
    return {'listen': listen, 'script': {'type': 'text/javascript', 'exec': lines}}


def save_script(saves):
    """saves: {"env_var": "js expression over r"}"""
    lines = ['if (pm.response.code >= 200 && pm.response.code < 300) {', '    const r = pm.response.json();']
    lines += [f"    pm.environment.set('{k}', {v});" for k, v in saves.items()]
    return script('test', lines + ['}'])


def to_request(spec_req, docs_default):
    docs = spec_req.get('docs') or docs_default
    desc = spec_req.get('description', '').rstrip()
    if docs:
        desc += f'\n\n📖 Документація: {docs}'
    body = {
        'name': spec_req['name'],
        'method': spec_req['method'],
        'url': spec_req['url'],
        'description': desc.strip(),
        'headerData': [{'key': h[0], 'value': h[1], 'description': h[2] if len(h) > 2 else ''}
                       for h in spec_req.get('headers', [])],
        'events': [],
    }
    if spec_req.get('auth'):
        body['auth'] = spec_req['auth']
    b = spec_req.get('body') or {'mode': 'none'}
    if b['mode'] in ('urlencoded', 'formdata'):
        body['dataMode'] = 'params' if b['mode'] == 'formdata' else 'urlencoded'
        body['data'] = [{'key': p[0], 'value': p[1], 'description': p[2] if len(p) > 2 else '',
                         'type': 'text', 'enabled': not (len(p) > 3 and p[3] is False)}
                        for p in b['params']]
    elif b['mode'] == 'raw':
        raw = b['raw'] if isinstance(b['raw'], str) else json.dumps(b['raw'], ensure_ascii=False, indent=2)
        body['dataMode'] = 'raw'
        body['rawModeData'] = raw
        body['dataOptions'] = {'raw': {'language': b.get('language', 'json')}}
    else:
        body['dataMode'] = None
        body['data'] = []
    if spec_req.get('prerequest'):
        body['events'].append(script('prerequest', spec_req['prerequest']))
    if spec_req.get('saves'):
        body['events'].append(save_script(spec_req['saves']))
    return body


# ---------- commands ----------

def cmd_workspaces():
    for w in call('GET', '/workspaces')['workspaces']:
        print(w['id'], w['type'], w['name'])


def cmd_find(name):
    n = name.lower()
    for c in call('GET', '/collections')['collections']:
        if n in c['name'].lower():
            print('COLLECTION', c['uid'], c['name'])
            col = call('GET', f"/collections/{c['uid']}")['collection']
            print('   top-level folders:', [i['name'] for i in col['item'] if 'item' in i])
    for e in call('GET', '/environments')['environments']:
        if n in e['name'].lower():
            print('ENV', e['uid'], e['name'])


def cmd_tree(uid):
    col = call('GET', f'/collections/{uid}')['collection']

    def walk(items, ind):
        for it in items:
            if 'item' in it:
                print('  ' * ind + '📁', it['name'], f"(id {it['id']})")
                walk(it['item'], ind + 1)
            else:
                r = it['request']
                print('  ' * ind + '-', r['method'], it['name'], '|', r['url']['raw'] if isinstance(r['url'], dict) else r['url'])
    walk(col['item'], 0)


def next_version(col):
    versions = [int(m.group(1)) for i in col['item'] if 'item' in i
                for m in [re.fullmatch(r'v(\d+)', i['name'].strip(), re.I)] if m]
    has_unversioned = any('item' in i for i in col['item'])
    if versions:
        return max(versions) + 1
    return 2 if has_unversioned else 1


def cmd_build(path):
    spec = json.load(open(path, encoding='utf-8'))
    ws = spec['workspace_id']
    docs = spec.get('docs_url', '')
    uid = spec.get('collection_uid')
    if not uid:
        res = call('POST', f'/collections?workspace={ws}', {'collection': {
            'info': {'name': spec['provider'], 'description': f'📖 Документація: {docs}',
                     'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'},
            'item': []}})
        uid = res['collection']['uid']
        print('created collection', uid)
        version = 1
    else:
        version = next_version(call('GET', f'/collections/{uid}')['collection'])
    version = spec.get('version') or version
    owner = owner_of(uid)
    vname = f'v{version}'
    res = call('POST', f'/collections/{uid}/folders', {
        'name': vname,
        'description': spec.get('description', '') + (f'\n\n📖 Документація: {docs}' if docs else ''),
    })
    vid = res['model_id']
    print('version folder', vname, vid)
    if spec.get('auth') or spec.get('folder_test'):
        upd = {}
        if spec.get('auth'):
            upd['auth'] = spec['auth']
        if spec.get('folder_test'):
            upd['events'] = [script('test', spec['folder_test'])]
        call('PUT', f'/collections/{uid}/folders/{owner}-{vid}', upd)
    def create(folder, parent_id, inherited_docs, depth):
        fdocs = folder.get('docs') or inherited_docs
        fdesc = folder.get('description', '') + (f"\n\n📖 Документація: {folder['docs']}" if folder.get('docs') else '')
        fres = call('POST', f'/collections/{uid}/folders', {'name': folder['name'], 'description': fdesc, 'folder': parent_id})
        fid = fres['model_id']
        print('  ' * depth + '📁', folder['name'])
        for r in folder.get('requests', []):
            call('POST', f'/collections/{uid}/requests?folder={owner}-{fid}', to_request(r, fdocs))
            print('  ' * depth + '   +', r['name'])
        for sub in folder.get('folders', []):
            create(sub, fid, fdocs, depth + 1)

    for folder in spec['folders']:
        create(folder, vid, docs, 1)
    env = spec.get('environment')
    if env:
        values = [{'key': v['key'], 'value': v.get('value', ''), 'type': v.get('type', 'default'), 'enabled': True}
                  for v in env['values']]
        eres = call('POST', f'/environments?workspace={ws}', {'environment': {'name': env['name'], 'values': values}})
        print('environment', env['name'], eres['environment']['uid'])
    print(f'\nDONE: collection {uid}, folder {vname} (id {vid}). Запиши ці id у spec (collection_uid, version).')


def find_version_folder(uid, version):
    col = call('GET', f'/collections/{uid}')['collection']
    return next(i for i in col['item'] if i['name'] == f'v{version}')


def postman_requests(items, path=()):
    """(шлях папок, запит) для всіх запитів у дереві Postman."""
    for it in items:
        if 'item' in it:
            yield from postman_requests(it['item'], path + (it['name'],))
        else:
            yield path, it


def spec_requests(folders, docs, path=()):
    """(шлях папок, запит, docs за замовчуванням) для всіх запитів у spec."""
    for f in folders:
        fpath, fdocs = path + (f['name'],), f.get('docs') or docs
        for r in f.get('requests', []):
            yield fpath, r, fdocs
        yield from spec_requests(f.get('folders', []), fdocs, fpath)


def cmd_update(path):
    spec = json.load(open(path, encoding='utf-8'))
    uid, docs = spec['collection_uid'], spec.get('docs_url', '')
    vf = find_version_folder(uid, spec['version'])
    existing = {(p, r['name']): r['id'] for p, r in postman_requests(vf['item'])}
    for fpath, r, fdocs in spec_requests(spec['folders'], docs):
        label = ' / '.join(fpath + (r['name'],))
        rid = existing.get((fpath, r['name']))
        if not rid:
            print('SKIP (нема в Postman, створи через build або вручну):', label)
            continue
        call('PUT', f'/collections/{bare(uid)}/requests/{owner_of(uid)}-{rid}', to_request(r, fdocs))
        print('updated', label)


def cmd_sync(path):
    spec = json.load(open(path, encoding='utf-8'))
    uid, docs = spec['collection_uid'], spec.get('docs_url', '')
    owner = owner_of(uid)
    vf = find_version_folder(uid, spec['version'])

    def folder_desc(folder):
        return folder.get('description', '') + (f"\n\n📖 Документація: {folder['docs']}" if folder.get('docs') else '')

    def walk(spec_folders, pm_items, parent_id, inherited_docs, path):
        existing = {i['name']: i for i in pm_items if 'item' in i}
        for folder in spec_folders:
            fdocs = folder.get('docs') or inherited_docs
            label = ' / '.join(path + (folder['name'],))
            pm = existing.get(folder['name'])
            if pm is None:
                fid = call('POST', f'/collections/{uid}/folders',
                           {'name': folder['name'], 'description': folder_desc(folder), 'folder': parent_id})['model_id']
                print('+ folder', label)
                children = []
            else:
                fid, children = pm['id'], pm['item']
                if (pm.get('description') or '') != folder_desc(folder):
                    call('PUT', f'/collections/{uid}/folders/{owner}-{fid}', {'description': folder_desc(folder)})
                    print('~ folder description', label)
            have = {i['name'] for i in children if 'item' not in i}
            for r in folder.get('requests', []):
                if r['name'] not in have:
                    call('POST', f'/collections/{uid}/requests?folder={owner}-{fid}', to_request(r, fdocs))
                    print('+ request', label, '/', r['name'])
            walk(folder.get('folders', []), children, fid, fdocs, path + (folder['name'],))

    walk(spec['folders'], vf['item'], vf['id'], docs, (vf['name'],))

    env = spec.get('environment')
    if env:
        found = [e for e in call('GET', '/environments')['environments'] if e['name'] == env['name']]
        if not found:
            print('environment', env['name'], 'не знайдено — створи через build або вручну')
            return
        euid = found[0]['uid']
        current = call('GET', f'/environments/{euid}')['environment']['values']
        keys = {v['key'] for v in current}
        missing = [v for v in env['values'] if v['key'] not in keys]
        if missing:
            values = current + [{'key': v['key'], 'value': v.get('value', ''), 'type': v.get('type', 'default'),
                                 'enabled': True} for v in missing]
            call('PUT', f'/environments/{euid}', {'environment': {'name': env['name'], 'values': values}})
            print('+ env vars', [v['key'] for v in missing])


def cmd_verify(path):
    spec = json.load(open(path, encoding='utf-8'))
    vf = find_version_folder(spec['collection_uid'], spec['version'])
    used, local = set(), set()
    for _, r in postman_requests(vf['item']):
        txt = json.dumps(r, ensure_ascii=False)
        used |= set(re.findall(r'\{\{([\w.-]+)\}\}', json.dumps(r['request'], ensure_ascii=False)))
        local |= set(re.findall(r"pm\.variables\.set\('([\w.-]+)'", txt))
    used |= set(re.findall(r'\{\{([\w.-]+)\}\}', json.dumps(vf.get('auth') or {})))
    env_keys = {v['key'] for v in spec['environment']['values']}
    print('tree:')
    counts = {}
    for p, _ in postman_requests(vf['item']):
        counts[p] = counts.get(p, 0) + 1
    for p, n in counts.items():
        print('  📁', ' / '.join(p), n, 'requests')
    print('used but not in env/local:', sorted(used - env_keys - local))
    print('in env but unused in requests:', sorted(env_keys - used))


def main():
    global KEY
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        sys.exit(__doc__)
    KEY = load_key()
    cmd, rest = args[0], args[1:]
    {'workspaces': cmd_workspaces, 'find': cmd_find, 'tree': cmd_tree, 'build': cmd_build, 'update': cmd_update, 'sync': cmd_sync, 'verify': cmd_verify}[cmd](*rest)


if __name__ == '__main__':
    main()
