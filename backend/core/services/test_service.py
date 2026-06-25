import json
import os
import re
import uuid
from datetime import timezone
from pathlib import Path

from core.models import Collection, Test
from pipeline.constants import EXCLUDED_SPEC_FILES, MIN_SLUG_WORD_LENGTH
from utils.datetime_utils import DateTimeUtils
from utils.slug import to_collection_slug


class TestService:

    @staticmethod
    def list_by_collection(collection_id: str, project_root: str) -> list:
        from core.serializers import TestSerializer
        collection = Collection.objects.get(id=collection_id)
        tests = Test.objects.filter(collection_id=collection_id).order_by('-created_at')
        slug = to_collection_slug(collection.name)
        tests_root = os.path.join(project_root, 'tests')
        specs_root = os.path.join(project_root, 'specs')

        result = []
        for test in tests:
            data = dict(TestSerializer(test).data)
            spec_path = TestService.find_spec_file(test.name, slug, tests_root)
            if spec_path:
                basename = os.path.basename(spec_path)
                data['specFile'] = {'basename': basename, 'filename': f'{slug}/{basename}'}
            else:
                data['specFile'] = None
            plan_path = os.path.join(specs_root, slug, str(test.id), 'plan.md')
            data['planFile'] = 'plan.md' if os.path.isfile(plan_path) else None
            result.append(data)
        return result

    @staticmethod
    def create(collection_id: str, name: str, prompt: str) -> Test:
        return Test.objects.create(
            id=str(uuid.uuid4()),
            collection_id=collection_id,
            name=name,
            prompt=prompt,
            status='active',
            created_at=DateTimeUtils.now_iso(),
        )

    @staticmethod
    def update(test: Test, data: dict) -> Test:
        # `data` is validated_data from TestUpdateSerializer — only sent keys are
        # present, and collectionId existence is already validated there.
        new_collection_id = data.get('collectionId')
        if new_collection_id and new_collection_id != test.collection_id:
            test.collection_id = new_collection_id

        if data.get('name'):
            test.name = data['name']
        if 'prompt' in data:
            test.prompt = data['prompt']
        if 'status' in data:
            test.status = data['status']
        if 'environmentIds' in data:
            test.environment_ids = json.dumps(data['environmentIds'])
        test.save()

        if data.get('duplicate'):
            Test.objects.create(
                id=str(uuid.uuid4()),
                collection_id=test.collection_id,
                name=f'{test.name} (copy)',
                prompt=test.prompt,
                status=test.status,
                environment_ids=test.environment_ids,
                created_at=DateTimeUtils.now_iso(),
            )
        return test

    @staticmethod
    def soft_delete(test_id: str) -> int:
        return Test.objects.filter(id=test_id).update(deleted_at=DateTimeUtils.now_iso())

    @staticmethod
    def find_spec_file(test_name: str, collection_slug: str, tests_root: str):
        collection_dir = os.path.join(tests_root, collection_slug)

        def _list(d):
            if not os.path.isdir(d):
                return []
            return [
                os.path.join(d, f)
                for f in os.listdir(d)
                if f.startswith('test_') and f.endswith('.py') and f not in EXCLUDED_SPEC_FILES
            ]

        def _most_recent(files):
            return max(files, key=lambda f: os.path.getmtime(f)) if files else None

        def _name_slug(f):
            b = re.sub(r'\.py$', '', os.path.basename(f).lower())
            return re.sub(r'^test_', '', b)

        kebab = re.sub(r'[^a-z0-9-]', '', re.sub(r'\s+', '-', test_name.lower()))
        for d in [collection_dir, tests_root]:
            for f in _list(d):
                if _name_slug(f).startswith(kebab):
                    return f

        words = [w for w in test_name.lower().split() if len(w) >= MIN_SLUG_WORD_LENGTH]
        for d in [collection_dir, tests_root]:
            for f in _list(d):
                if any(w in _name_slug(f) for w in words):
                    return f

        return _most_recent(_list(collection_dir)) or _most_recent(_list(tests_root))

    @staticmethod
    def list_spec_files(collection_slug: str, tests_root: str) -> list:
        collection_dir = os.path.join(tests_root, collection_slug)
        if not os.path.isdir(collection_dir):
            return []
        files = []
        for f in os.listdir(collection_dir):
            if f.startswith('test_') and f.endswith('.py') and f not in EXCLUDED_SPEC_FILES:
                full = os.path.join(collection_dir, f)
                stat = os.stat(full)
                from datetime import datetime
                files.append({
                    'filename': f'{collection_slug}/{f}',
                    'basename': f,
                    'lastModified': datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat().replace('+00:00', 'Z'),
                    'sizeBytes': stat.st_size,
                })
        return sorted(files, key=lambda x: x['lastModified'], reverse=True)

    @staticmethod
    def read_spec_file(abs_path: str, tests_root: str) -> dict:
        from datetime import datetime
        stat = os.stat(abs_path)
        return {
            'filename': os.path.relpath(abs_path, tests_root).replace('\\', '/'),
            'content': Path(abs_path).read_text(encoding='utf-8'),
            'lastModified': datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat().replace('+00:00', 'Z'),
        }

    @staticmethod
    def read_raw_spec(file_path: str, tests_root: str) -> str:
        return Path(os.path.join(tests_root, file_path)).read_text(encoding='utf-8')

    @staticmethod
    def write_spec_file(filename: str, content: str, tests_root: str) -> None:
        abs_path = os.path.join(tests_root, filename)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        Path(abs_path).write_text(content, encoding='utf-8')

    @staticmethod
    def delete_spec_file(file_path: str, tests_root: str) -> None:
        os.unlink(os.path.join(tests_root, file_path))
