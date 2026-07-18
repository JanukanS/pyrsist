import click
import ast
import inspect
from pathlib import Path
from dataclasses  import dataclass
from functools import singledispatchmethod
from typing import Self

BEGIN_COMMENT: str = "# PERSIST"
END_COMMENT: str = "# END PERSIST"

@dataclass
class PersistRead:
    """
    Data about persistence section within a script
    """
    src: str # Entire script source code
    begin_index: int  # index of line where persistence section beings
    end_index: int # index of line where persistence section ends
    persist_src: str # source code within persistence section
    persist_state: dict # Initial value of persisted variables
    init_ast: ast.Module # ast of src

    @classmethod
    def from_src(cls, src: str) -> Self:
        """
        construct a PersistRead object given python source code
        """
        src_lines = src.split("\n")
        for line_ind, line in enumerate(src_lines):
            if line.startswith(BEGIN_COMMENT):
                begin_persist = line_ind 
            elif line.startswith(END_COMMENT):
                end_persist = line_ind 

        init_src = "\n".join(src_lines[:begin_persist])
        persist_src = "\n".join(src_lines[begin_persist: end_persist+1])
        
        init_state = {}
        exec(init_src, init_state)
        persist_state = init_state.copy()
        exec(persist_src,persist_state)
        var_state = {k: persist_state[k] for k in persist_state.keys() - init_state.keys()}
        persist_state = {k:v for k,v in var_state.items() if not k.startswith("_")}
        init_ast = ast.parse(persist_src)
        return cls(src, begin_persist, end_persist, persist_src, persist_state,init_ast)


@dataclass
class PersistExecute:
    src: str
    final_state: dict
    persist_state: dict
    final_ast: ast.Module

    @classmethod
    def from_persist_read(cls, pr: PersistRead):
        fstate = {}
        exec(pr.src, fstate)
        pstate = {k: fstate[k] for k in pr.persist_state}

        value_ast = {k: cls.gen_ast(v) for k,v in pstate.items()} 
        final_ast = PersistTransformer(value_ast).visit(pr.init_ast)
        ast.fix_missing_locations(final_ast)
        return cls(pr.src, fstate, pstate, final_ast)

    @classmethod
    def from_globals(cls, pr: PersistRead, gl):
        pstate = {k: gl[k] for k in pr.persist_state}

        value_ast = {k: cls.gen_ast(v) for k,v in pstate.items()} 
        final_ast = PersistTransformer(value_ast).visit(pr.init_ast)
        ast.fix_missing_locations(final_ast)
        return cls(pr.src, gl, pstate, final_ast)



    @classmethod
    def gen_ast(cls, val):
        return ast.parse(val.__repr__()).body[0].value


class PersistTransformer(ast.NodeTransformer):
    def __init__(self, value_ast):
        super().__init__()
        self.value_ast = value_ast
        self.persist_vars = list(value_ast.keys())

    def visit_Assign(self,node):
        node.value = self._parse_expression(node.targets[0])# self.value_ast[assign_targets.id]  
        return node

    def visit_AnnAssign(self,node):
        if node.target.id in self.persist_vars:
            node.value = self.value_ast[node.target.id] 
        return node

    @singledispatchmethod
    def _parse_expression(self,asgn_target):
        pass

    @_parse_expression.register(ast.Tuple)
    def _(self,asgn_target: ast.Tuple):
        tuple_vals = []
        for var_name in asgn_target.elts:
            if var_name.id in self.persist_vars:
                tuple_vals.append(self.value_ast[var_name.id])
        return ast.Tuple(tuple_vals, ast.Load)

    @_parse_expression.register(ast.Name)
    def _(self,asgn_target: ast.Name):
        if asgn_target.id in self.persist_vars:
            return self.value_ast[asgn_target.id]




class ScriptPersist:
    def __init__(self, src_analysis: PersistRead, src_execute: PersistExecute):
        self.analysis = src_analysis
        self.update_persist_src = (BEGIN_COMMENT
                                   + "\n"
                                   + ast.unparse(src_execute.final_ast)
                                   + "\n"
                                   + END_COMMENT)
    
    def generate_new_src(self) -> str:
        init_src = self.analysis.src
        return init_src.replace(self.analysis.persist_src, self.update_persist_src)
    
    @classmethod
    def run_after_execution(cls, fname,global_dict):
        target_path = Path(fname)
        target_src = target_path.read_text()

        sa = PersistRead.from_src(target_src)
        se = PersistExecute.from_globals(sa,global_dict)
        sp = ScriptPersist(sa,se)
        new_src = sp.generate_new_src()
   
        with open(target_path,'w+') as f:
            f.write(new_src)



def persist():
    frame = inspect.currentframe().f_back
    if frame.f_back is not None:
        raise RuntimeError("This function must be called from the top-level frame (module level).")
    globdict = frame.f_globals
    fname = frame.f_globals["__file__"]
    ScriptPersist.run_after_execution(fname, globdict)

@click.group
def pyrsist():
    pass

@pyrsist.command('info')
@click.argument('target')
def pyrsist_info(target):
    """List persistent variables within the TARGET script"""
    target_path = Path(target)
    target_src = target_path.read_text()

    sa = PersistRead.from_src(target_src)
    click.echo("Persisting Variables: " + list(sa.persist_state.keys()).__repr__())

@pyrsist.command('init')
@click.argument('target')
def pyrsist_init(target):
    """Create a template copy called TARGET"""
    template_prog = "\n".join([BEGIN_COMMENT,
                               'a=1',
                               END_COMMENT,
                               'print("a=",a)',
                               'a+=1'])
                    
    with open(target,'w') as f:
        f.write(template_prog)

if __name__ == "__main__":
    pyrsist()
