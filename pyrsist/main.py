import click
import ast
from pathlib import Path

BEGIN_COMMENT: str = "# PERSIST"
END_COMMENT: str = "# END PERSIST"

class ScriptAnalysis:
    def __init__(self, src: str):
        self.src: str = src
        self.begin_persist, self.end_persist = self.locate_persist(self.src)
        
        self.init_state = self.identify_persist(self.src, self.begin_persist, self.end_persist) 
        self.init_ast = self.get_init_ast(self.src, self.begin_persist, self.end_persist) 
  
        self.persist_vars = list(self.init_state.keys())


    @classmethod
    def locate_persist(cls, src: str):
        """ 
        Find sections of code to persist from:
        """
        src_lines = src.split("\n")
        begin_persist: list[int] = []
        end_persist: list[int] = []
        
        for line_ind, line in enumerate(src_lines):
            if line.startswith(BEGIN_COMMENT):
                begin_persist.append(line_ind+1)
            elif line.startswith(END_COMMENT):
                end_persist.append(line_ind+1)
        return begin_persist[0], end_persist[0]

    @classmethod
    def get_init_ast(cls, src:str, line_begin:int, line_end: int):
        src_lines = src.split("\n")
        persist_lines = src_lines[line_begin-1:line_end-1]
        persist_src = "\n".join(persist_lines)
        return ast.parse(persist_src)
        

    @classmethod
    def identify_persist(cls, src:str, line_begin: int, line_end: int):
        src_lines = src.split("\n")
        persist_lines = src_lines[line_begin-1:line_end-1]
        persist_src = "\n".join(persist_lines)
        persist_dict = {}

        exec(persist_src, persist_dict)
        persist_var_dict = {k:v for k,v in persist_dict.items() if not k.startswith("_")}
        return persist_var_dict

class ScriptExecute:
    def __init__(self, src_analysis: ScriptAnalysis):
        self.final_state = {}
        exec(src_analysis.src, self.final_state)
        
        self.persist_state = {var_name: self.final_state[var_name] for var_name in src_analysis.persist_vars}

class PersistTransformer(ast.NodeTransformer):
    def __init__(self, value_ast):
        super().__init__()
        self.value_ast = value_ast
        self.persist_vars = list(value_ast.keys())

    def general_transform(self, node):
        if node.target.id in self.persist_vars:
            node.value = self.value_ast[node.target.id] 
        return node

    def visit_Assign(self,node):
        return self.general_transform(node)

    def visit_AnnAssign(self,node):
        return self.general_transform(node)

class ScriptPersist:
    def __init__(self, src_analysis: ScriptAnalysis, src_execute: ScriptExecute):
        self.analysis = src_analysis

        value_ast = {}
        for key in src_analysis.persist_vars:
            val = src_execute.persist_state[key]
            value_ast[key] = ast.parse(val.__repr__()).body[0].value
        
        self.update_ast = PersistTransformer(value_ast).visit(src_analysis.init_ast)
        ast.fix_missing_locations(self.update_ast)
        self.update_persist_src = ast.unparse(self.update_ast)

    def generate_new_src(self) -> str:
        init_src = self.analysis.src
        begin_index = self.analysis.begin_persist - 1
        end_index = self.analysis.end_persist - 1
        
        init_src_lines = init_src.split("\n")
        pre_persist_src = init_src_lines[:begin_index]
        post_persist_src = init_src_lines[end_index+1:]
        
        new_src_lines = (pre_persist_src + 
                         [BEGIN_COMMENT] + 
                         self.update_persist_src.split("\n") +  
                         [END_COMMENT] + 
                         post_persist_src)

 
        new_src = "\n".join(new_src_lines)
        return new_src


@click.group
def pyrsist():
    pass

@pyrsist.command('run')
@click.argument('target')
@click.argument('output_path', nargs=1, default=None)
@click.option('--dryrun', is_flag=True, help="Do not modify script")
def pyrsist_run(target,output_path,dryrun):
    """Execute TARGET and rewrite TARGET if OUTPUT_PATH is not specified"""
    if dryrun and output_path is not None:
        raise click.UsageError("Cannot specify an output file with dryrun enabled")
    
    target_path = Path(target)
    target_src = target_path.read_text()

    sa = ScriptAnalysis(target_src)
    se = ScriptExecute(sa)
    sp = ScriptPersist(sa,se)
    new_src = sp.generate_new_src()
   
    output_file = output_path or target_path
    if not dryrun:
        with open(output_file,'w+') as f:
            f.write(new_src)

@pyrsist.command('info')
@click.argument('target')
def pyrsist_info(target):
    """List persistent variables within the TARGET script"""
    target_path = Path(target)
    target_src = target_path.read_text()

    sa = ScriptAnalysis(target_src)
    click.echo("Persisting Variables: " + sa.persist_vars.__repr__())

if __name__ == "__main__":
    pyrsist()
