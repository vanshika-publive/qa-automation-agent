import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from rest_framework.response import Response

from core.models import Collection, Test, Execution
from utils.json_utils import safe_json_parse
from utils.slug import to_collection_slug

PROJECT_ROOT = settings.PLAYWRIGHT_PROJECT_ROOT
EXCLUDED_SPEC_FILES = {'conftest.py', 'helpers.py'}
MIN_SLUG_WORD_LENGTH = 3


def _serialize_test(t):
    return {
        'id': t.id,
        'collectionId': t.collection_id,
        'name': t.name,
        'prompt': t.prompt,
        'status': t.status,
        'environmentIds': safe_json_parse(t.environment_ids, []),
        'createdAt': t.created_at,
    }


def _find_spec_file(test_name, collection_slug, tests_root):
    collection_dir = os.path.join(tests_root, collection_slug)

    def list_spec_files(d):
        if not os.path.isdir(d):
            return []
        return [
            os.path.join(d, f)
            for f in os.listdir(d)
            if f.startswith('test_') and f.endswith('.py') and f not in EXCLUDED_SPEC_FILES
        ]

    def most_recent(files):
        if not files:
            return None
        return max(files, key=lambda f: os.path.getmtime(f))

    # Generated files are named test_<slug>.py — strip the test_ prefix and .py
    # extension so they compare against the test-name kebab/word slugs.
    def name_slug(f):
        b = re.sub(r'\.py$', '', os.path.basename(f).lower())
        return re.sub(r'^test_', '', b)

    kebab = re.sub(r'[^a-z0-9-]', '', re.sub(r'\s+', '-', test_name.lower()))

    for d in [collection_dir, tests_root]:
        files = list_spec_files(d)
        for f in files:
            if name_slug(f).startswith(kebab):
                return f

    words = [w for w in test_name.lower().split() if len(w) >= MIN_SLUG_WORD_LENGTH]
    for d in [collection_dir, tests_root]:
        files = list_spec_files(d)
        for f in files:
            if any(w in name_slug(f) for w in words):
                return f

    collection_files = list_spec_files(collection_dir)
    if collection_files:
        return most_recent(collection_files)

    root_files = list_spec_files(tests_root)
    if root_files:
        return most_recent(root_files)

    return None


# --- Collection Tests CRUD ---

class CollectionTests(APIView):
    def get(self, request, collection_id):
        try:
            collection = Collection.objects.get(id=collection_id)
        except Collection.DoesNotExist:
            return Response({'error': 'Collection not found'}, status=status.HTTP_404_NOT_FOUND)

        tests = Test.objects.filter(collection_id=collection_id).order_by('-created_at')
        slug = to_collection_slug(collection.name)
        tests_root = os.path.join(PROJECT_ROOT, 'tests')
        specs_root = os.path.join(PROJECT_ROOT, 'specs')

        data = []
        for t in tests:
            serialized = _serialize_test(t)
            spec_path = _find_spec_file(t.name, slug, tests_root)
            if spec_path:
                basename = os.path.basename(spec_path)
                serialized['specFile'] = {'basename': basename, 'filename': f'{slug}/{basename}'}
            else:
                serialized['specFile'] = None
            plan_path = os.path.join(specs_root, slug, str(t.id), 'plan.md')
            serialized['planFile'] = 'plan.md' if os.path.isfile(plan_path) else None
            data.append(serialized)

        return Response(data)

    def post(self, request, collection_id):
        if not Collection.objects.filter(id=collection_id).exists():
            return Response({'error': 'Collection not found'}, status=status.HTTP_404_NOT_FOUND)

        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'error': 'name is required'}, status=status.HTTP_400_BAD_REQUEST)

        prompt = (request.data.get('prompt') or '').strip()
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        test = Test.objects.create(
            id=str(uuid.uuid4()),
            collection_id=collection_id,
            name=name,
            prompt=prompt,
            status='active',
            created_at=now,
        )
        data = {
            'id': test.id,
            'collectionId': test.collection_id,
            'name': test.name,
            'prompt': test.prompt,
            'status': test.status,
            'createdAt': test.created_at,
        }
        return Response(data, status=status.HTTP_201_CREATED)


class TestDetail(APIView):
    def put(self, request, id):
        try:
            test = Test.objects.get(id=id)
        except Test.DoesNotExist:
            return Response({'error': 'Test not found'}, status=status.HTTP_404_NOT_FOUND)

        body = request.data
        new_collection_id = body.get('collection_id')

        if new_collection_id and new_collection_id != test.collection_id:
            if not Collection.objects.filter(id=new_collection_id).exists():
                return Response({'error': 'Collection not found'}, status=status.HTTP_404_NOT_FOUND)

        test.name = (body.get('name') or '').strip() or test.name
        test.prompt = body.get('prompt', test.prompt)
        if 'prompt' in body:
            test.prompt = (body['prompt'] or '').strip()
        test.status = body.get('status', test.status)
        if new_collection_id:
            test.collection_id = new_collection_id
        if 'environment_ids' in body and body['environment_ids'] is not None:
            test.environment_ids = json.dumps(body['environment_ids'])
        test.save()

        if body.get('duplicate'):
            now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            Test.objects.create(
                id=str(uuid.uuid4()),
                collection_id=test.collection_id,
                name=f'{test.name} (copy)',
                prompt=test.prompt,
                status=test.status,
                environment_ids=test.environment_ids,
                created_at=now,
            )

        return Response(_serialize_test(test))

    def delete(self, request, id):
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        updated = Test.objects.filter(id=id).update(deleted_at=now)
        if updated == 0:
            return Response({'error': 'Test not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'id': id})


# --- Spec file operations ---

@api_view(['GET'])
def collection_specs(request, collection_id):
    try:
        collection = Collection.objects.get(id=collection_id)
    except Collection.DoesNotExist:
        return Response({'error': 'Collection not found'}, status=status.HTTP_404_NOT_FOUND)

    slug = to_collection_slug(collection.name)
    collection_dir = os.path.join(PROJECT_ROOT, 'tests', slug)

    if not os.path.isdir(collection_dir):
        return Response([])

    files = []
    for f in os.listdir(collection_dir):
        if f.startswith('test_') and f.endswith('.py') and f not in EXCLUDED_SPEC_FILES:
            full = os.path.join(collection_dir, f)
            stat = os.stat(full)
            files.append({
                'filename': f'{slug}/{f}',
                'basename': f,
                'lastModified': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat().replace('+00:00', 'Z'),
                'sizeBytes': stat.st_size,
            })

    files.sort(key=lambda x: x['lastModified'], reverse=True)
    return Response(files)


@api_view(['GET'])
def view_spec(request):
    file_path = request.query_params.get('file', '')
    if not file_path or '..' in file_path:
        return Response({'error': 'Invalid file path'}, status=status.HTTP_400_BAD_REQUEST)

    abs_path = os.path.join(PROJECT_ROOT, 'tests', file_path)
    if not os.path.isfile(abs_path):
        return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)

    content = Path(abs_path).read_text(encoding='utf-8')
    return Response({'content': content})


@api_view(['DELETE'])
def delete_spec(request):
    file_path = request.query_params.get('file', '')
    if not file_path or '..' in file_path:
        return Response({'error': 'Invalid file path'}, status=status.HTTP_400_BAD_REQUEST)

    abs_path = os.path.join(PROJECT_ROOT, 'tests', file_path)
    if not os.path.isfile(abs_path):
        return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)

    os.unlink(abs_path)
    return Response({'deleted': file_path})


class TestSpec(APIView):
    def get(self, request, id):
        try:
            test = Test.all_objects.select_related('collection').get(id=id, deleted_at__isnull=True)
        except Test.DoesNotExist:
            return Response({'error': 'Test not found'}, status=status.HTTP_404_NOT_FOUND)

        slug = to_collection_slug(test.collection.name)
        tests_root = os.path.join(PROJECT_ROOT, 'tests')
        abs_path = _find_spec_file(test.name, slug, tests_root)

        if not abs_path:
            return Response({
                'data': {'filename': None, 'content': None, 'lastModified': None},
                'error': 'No spec file generated yet for this test',
            })

        content = Path(abs_path).read_text(encoding='utf-8')
        stat = os.stat(abs_path)
        filename = os.path.relpath(abs_path, tests_root).replace('\\', '/')
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat().replace('+00:00', 'Z')

        return Response({'filename': filename, 'content': content, 'lastModified': last_modified})

    def put(self, request, id):
        content = (request.data.get('content') or '').strip()
        filename = (request.data.get('filename') or '').strip()

        if not content:
            return Response({'error': 'content is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not filename:
            return Response({'error': 'filename is required'}, status=status.HTTP_400_BAD_REQUEST)
        if 'import' not in content:
            return Response({'error': 'content must contain an import statement'}, status=status.HTTP_400_BAD_REQUEST)
        if 'def test' not in content:
            return Response({'error': 'content must contain a def test_... function'}, status=status.HTTP_400_BAD_REQUEST)

        tests_root = os.path.join(PROJECT_ROOT, 'tests')
        abs_path = os.path.join(tests_root, filename)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        Path(abs_path).write_text(content, encoding='utf-8')

        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        return Response({'ok': True, 'filename': filename, 'savedAt': now})


@api_view(['POST'])
def run_spec(request, id):
    if not Test.objects.filter(id=id).exists():
        return Response({'error': 'Test not found'}, status=status.HTTP_404_NOT_FOUND)

    environment_id = (request.data.get('environmentId') or '').strip()
    filename = (request.data.get('filename') or '').strip()

    if not environment_id:
        return Response({'error': 'environmentId is required'}, status=status.HTTP_400_BAD_REQUEST)
    if not filename:
        return Response({'error': 'filename is required'}, status=status.HTTP_400_BAD_REQUEST)

    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    execution_id = str(uuid.uuid4())
    Execution.all_objects.create(
        id=execution_id,
        test_id=id,
        environment_id=environment_id,
        status='running',
        started_at=now,
    )

    def _run():
        import django
        django.setup()
        from pipeline.run_pipeline import run_spec_file
        run_spec_file(execution_id, id, filename, environment_id)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return Response({'executionId': execution_id}, status=status.HTTP_202_ACCEPTED)
