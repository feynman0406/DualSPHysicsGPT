import unittest
from controller import loop as controller_loop


class UnlockParseTest(unittest.TestCase):
    def test_unlock_false_when_empty_or_A(self):
        self.assertFalse(controller_loop._should_unlock(""))
        txt = "fixer_output:\n  error_type: A\n  retrieval:\n    request_unlock: true\n"
        # A 類錯誤不允許解鎖，即便 request_unlock 標了 true 也應該拒絕
        self.assertFalse(controller_loop._should_unlock(txt))

    def test_unlock_true_when_B_and_request_true(self):
        txt = "fixer_output:\n  error_type: B\n  retrieval:\n    request_unlock: true\n"
        self.assertTrue(controller_loop._should_unlock(txt))

    def test_unlock_true_case_insensitive_and_variants(self):
        txt = "Error_Type: b\nRetrieval:\n  request_unlock: Yes\n"
        self.assertTrue(controller_loop._should_unlock(txt))

    def test_unlock_false_when_B_but_request_false(self):
        txt = "fixer_output:\n  error_type: B\n  retrieval:\n    request_unlock: false\n"
        self.assertFalse(controller_loop._should_unlock(txt))


if __name__ == "__main__":
    unittest.main()
