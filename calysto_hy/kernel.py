'''
A Hy Lang kernel for Jupyter based on MetaKernel.
'''
from __future__ import print_function

import __future__  # NOQA

import ast
import sys
import types
import traceback
import hy.core
import hy.macros

from hy.version import __version__ as hy_version
from hy.compiler import hy_compile, HyASTCompiler
from hy.lex import hy_parse
from metakernel import MetaKernel

from .version import __version__

try:
    from IPython.core.latex_symbols import latex_symbols
except:
    latex_symbols = []

def create_jedhy_completer(env):
    '''
    Return code completions from jedhy.
    '''
    jedhy = Actions(globals_=env)
    def complete(txt):
        jedhy.set_namespace(globals_=env)
        return jedhy.complete(txt)
    return complete


def create_fallback_completer(env):
    '''
    Return simple completions from env listing,
    macros and compile table
    '''
    def complete(txt):
        try:
            from hy.compiler import _compile_table, load_stdlib
            load_stdlib()
        except:
            _compile_table = []

        matches = [word for word in env if word.startswith(txt)]
        for p in list(hy.core.macros.__macros__.values()) + _compile_table:
            p = filter(lambda x: isinstance(x, str), p.keys())
            p = [x.replace('_', '-') for x in p]
            matches.extend([
                x for x in p
                if x.startswith(txt) and x not in matches
            ])
        return matches
    return complete

try:
    from jedhy import Actions
    create_completer = create_jedhy_completer
except:
    create_completer = create_fallback_completer


class CalystoHy(MetaKernel):
    '''
    A Jupyter kernel for Hy based on MetaKernel.
    '''
    implementation = 'hy'
    implementation_version = __version__
    language = 'hy'
    language_version = hy_version
    banner = 'Hy is a wonderful dialect of Lisp that’s embedded in Python.'
    language_info = {
        'name': 'hy',
        'mimetype': 'text/x-hylang',
        'codemirror_mode': {
            'name': 'scheme'
        },
        'pygments_lexer': 'lisp'
    }
    kernel_json = {
        "argv": [sys.executable,
                 "-m", "calysto_hy",
                 "-f", "{connection_file}"],
        "display_name": "Calysto Hy",
        "language": "hy",
        "codemirror_mode": "hy",
        "name": "calysto_hy"
    }
    identifier_regex = r'\\?[\w\.][\w\.\?\!\-\>\<]*'
    function_call_regex = r'\(([\w\.][\w\.\?\!\-\>\>]*)[^\)\()]*\Z'
    magic_prefixes = dict(magic='%', shell='!', help='?')
    help_suffix = None

    def __init__(self, *args, **kwargs):
        '''
        Create the hy environment
        '''
        self.env = {}
        super(CalystoHy, self).__init__(*args, **kwargs)
        [hy.macros.load_macros(m) for m in [hy.core, hy.macros]]
        if "str" in dir(__builtins__):
            self.env.update({key: getattr(__builtins__, key)
                             for key in dir(__builtins__)})
        if "keys" in dir(__builtins__):
            self.env.update(__builtins__)
        self.env["raw_input"] = self.raw_input
        self.env["read"] = self.raw_input
        self.env["input"] = self.raw_input
        self.complete = create_completer(self.env)
        self.locals = {"__name__": "__console__", "__doc__": None}
        module_name = self.locals.get('__name__', '__console__')
        self.module = sys.modules.setdefault(module_name,
                                             types.ModuleType(module_name))
        self.module.__dict__.update(self.locals)
        self.locals = self.module.__dict__
        self.hy_compiler = HyASTCompiler(self.module)

    def set_variable(self, var, value):
        self.env[var] = value

    def get_variable(self, var):
        return self.env[var]

    def do_execute_direct(self, code):
        '''
        Execute the code, and return result.
        '''
        self.result = None
        #### try to parse it:
        try:
            filename = "In [%s]" % self.execution_count
            hy_ast = hy_parse(code, filename=filename)
            exec_ast, eval_ast = hy_compile(hy_ast, self.module,
                                            root=ast.Interactive,
                                            get_expr=True,
                                            compiler=self.hy_compiler,
                                            filename=filename, source=code)
            exec_code = compile(exec_ast, filename, 'single')
            eval_code = compile(eval_ast, filename, 'eval')
            eval(exec_code, self.locals)
            self.result = eval(eval_code, self.locals)

        except Exception as e:
            self.Error(traceback.format_exc())
            self.kernel_resp.update({
                "status": "error",
                'ename' : e.__class__.__name__,   # Exception name, as a string
                'evalue' : e.__class__.__name__,  # Exception value, as a string
                'traceback' : [], # traceback frames as strings
            })
            return None
        return self.result

    def get_completions(self, info):
        txt = info["help_obj"]
        # from latex
        matches = latex_matches(txt)
        if matches:
            return matches

        matches = self.complete(txt)

        return matches


def latex_matches(text):
    """
    Match Latex syntax for unicode characters.
    After IPython.core.completer
    """
    slashpos = text.rfind('\\')
    if slashpos > -1:
        s = text[slashpos:]
        if s in latex_symbols:
            # Try to complete a full latex symbol to unicode
            return [latex_symbols[s]]
        else:
            # If a user has partially typed a latex symbol, give them
            # a full list of options \al -> [\aleph, \alpha]
            matches = [k for k in latex_symbols if k.startswith(s)]
            return matches
    return []
