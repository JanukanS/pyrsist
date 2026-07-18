import unittest
import pyrsist

class TestIdentifyVariables(unittest.TestCase):
    def _wrap_persist(self, line: str) -> str:
        return "\n".join(["# PERSIST",
                          line,
                          "# END PERSIST"])

    def _test_src(self, test_src):
        sa = pyrsist.PersistRead.from_src(test_src)
        script_globals = {}
        exec(test_src, script_globals)
        se = pyrsist.PersistExecute.from_globals(sa, script_globals)
        pyrsist.ScriptPersist(sa,se).generate_new_src()

    def test_assign(self):
        test_src = self._wrap_persist("x=1")
        self._test_src(test_src) 

    def test_ann_assign(self):
        test_src = self._wrap_persist("x:int=1")
        self._test_src(test_src)

    def test_multi_assign(self):
        test_src = self._wrap_persist("x,y=1,2")
        self._test_src(test_src)

 
