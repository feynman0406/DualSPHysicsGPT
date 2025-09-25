import os
import unittest

from chains import generator, fixer


class RagFlagReloadTest(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)
        generator.reload_use_rag()
        fixer.reload_use_rag()

    def test_reload_use_rag_syncs_env(self) -> None:
        os.environ.pop('USE_RAG', None)
        generator.reload_use_rag()
        fixer.reload_use_rag()
        self.assertFalse(generator.is_rag_enabled())
        self.assertFalse(fixer.is_rag_enabled())

        os.environ['USE_RAG'] = '1'
        generator.reload_use_rag()
        fixer.reload_use_rag()
        self.assertTrue(generator.is_rag_enabled())
        self.assertTrue(fixer.is_rag_enabled())

        os.environ['USE_RAG'] = '0'
        generator.reload_use_rag()
        fixer.reload_use_rag()
        self.assertFalse(generator.is_rag_enabled())
        self.assertFalse(fixer.is_rag_enabled())


if __name__ == '__main__':
    unittest.main()
