import copy
import importlib.util
import json
import stat
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


notes = load('install_note')
catalog = load('check_catalog')


class NoteTests(unittest.TestCase):
    def test_preview_never_creates_or_changes_file(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'AGENTS.md'
            result = notes.install(target)
            self.assertTrue(result['changed'])
            self.assertFalse(target.exists())
            target.write_text('Other instructions.\n')
            notes.install(target)
            self.assertEqual(target.read_text(), 'Other instructions.\n')

    def test_apply_is_idempotent_and_keeps_existing_guidance(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'AGENTS.md'
            target.write_text('Keep this instruction.\n', encoding='utf-8')
            target.chmod(0o640)
            notes.install(target, apply=True)
            first = target.read_text()
            self.assertTrue(first.startswith('Keep this instruction.\n'))
            self.assertEqual(first.count(notes.START), 1)
            self.assertFalse(notes.install(target, apply=True)['changed'])
            self.assertEqual(target.read_text(), first)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)

    def test_update_changes_only_managed_region(self):
        old = 'Before.\n' + notes.START + '\nOld note.\n' + notes.END + '\nAfter.\n'
        result = notes.updated_text(old, 'New note.')
        self.assertTrue(result.startswith('Before.\n'))
        self.assertTrue(result.endswith('\nAfter.\n'))
        self.assertNotIn('Old note.', result)
        self.assertIn('New note.', result)

    def test_remove_preserves_all_unmanaged_text(self):
        old = 'Before.\n' + notes.START + '\nNote.\n' + notes.END + '\nAfter.\n'
        self.assertEqual(notes.updated_text(old, '', remove=True), 'Before.\nAfter.\n')

    def test_malformed_markers_stop_without_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'AGENTS.md'
            original = notes.START + '\nDo not lose this.\n'
            target.write_text(original)
            with self.assertRaises(ValueError):
                notes.install(target, apply=True)
            self.assertEqual(target.read_text(), original)

    def test_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            real = Path(folder) / 'real.md'
            real.write_text('Keep me.')
            link = Path(folder) / 'link.md'
            link.symlink_to(real)
            with self.assertRaises(ValueError):
                notes.install(link, apply=True)
            self.assertEqual(real.read_text(), 'Keep me.')


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'catalog.json').read_text())

    def test_current_catalog_is_valid(self):
        self.assertTrue(catalog.validate(self.data))

    def test_unknown_dependencies_are_rejected(self):
        self.data['solutions'][0]['dependencies'] = ['missing-solution']
        with self.assertRaises(ValueError):
            catalog.validate(self.data)

    def test_unrelated_or_non_https_repository_is_rejected(self):
        for url in ['http://github.com/omiusgm/example', 'https://untrusted.example.org/code',
                    'https://github.com/someone-else/example']:
            with self.subTest(url=url):
                data = copy.deepcopy(self.data)
                data['solutions'][0]['repository'] = url
                with self.assertRaises(ValueError):
                    catalog.validate(data)

    def test_draft_is_not_suggested_as_published_solution(self):
        self.data['solutions'][0]['status'] = 'draft'
        with self.assertRaises(ValueError):
            catalog.validate(self.data)


if __name__ == '__main__':
    unittest.main()
