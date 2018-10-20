import sys
import traceback

from IPython import display
from IPython.core.magic import register_cell_magic, Magics, magics_class, cell_magic, line_cell_magic, line_magic
import jinja2
import yaml
import argparse
import re
from typing import Optional, Dict

def identity(v):
    return v

@magics_class
class JinjaMagics(Magics):
    """Magics class containing the Jinja2 magics and state.

    %jinja: Render a Jinja2 template, named or inline.
    %%jinja_template: Define a named Jinja2 template
    %%yaml: Convert a YAML cell to a Python value.

    This class maintains a dictionary of templates created by %jinja_template.
    These can be imported, included, or extended by name. If not found in the
    dictionary, the current directory is searched.
    """

    def __init__(self, shell):
        super(JinjaMagics, self).__init__(shell)

        # We have two loaders: one dictionary-based, for use in notebooks...
        self.jinja_template_dict = {} # type: dict[str, jinja2.Template]
        self.dict_loader = jinja2.DictLoader(self.jinja_template_dict)

        # ...and one which loads from the filesystem. The dict one is used first.
        self.fs_loader = jinja2.FileSystemLoader('.')
        self.loader = jinja2.ChoiceLoader((self.dict_loader, self.fs_loader))

        #self.jinja_environment = jinja2.Environment(loader=self.loader)
        self.set_nb_var("jinja_env", dict())
        self.set_nb_var("jinja_options", dict())

    def get_nb_var(self, k, default=None):
        # type: (str, Optional[str]) -> object
        """Retrieve a variable from the notebook"""
        return self.shell.user_ns.get(k, default)

    def set_nb_var(self, k, v):
        # type: (str, object) -> None
        """Stuff a value into the notebook"""
        self.shell.user_ns[k] = v


    @cell_magic
    def jinja_template(self, line, cell):
        # type: (str, str) -> None
        """'%%jinja_template NAME' creates a template named NAME.

        Named templates are required for extends, includes, and imports.
        """
        f = line.strip()
        if f == "":
            raise NameError("Templates must have names")
        words = f.split()
        if len(words) > 1:
            raise NameError("Too many args")
        template_name = words[0]
        # We want to throw parse errors here rather than later.
        try:
            jinja2.Template(cell)
        except jinja2.exceptions.TemplateSyntaxError as e:
            sys.stderr.write("Syntax error at line {0}: {1}".format(e.lineno+1, e.message))
        else:
            self.jinja_template_dict[template_name] = cell

    # %jinja2 [--template=t] [--variables=v] [--html|--latex|--json|--pretty|--plain|--display|--code] [--lang name]
    jinja_parser = argparse.ArgumentParser(description="Render Jinja2",
                                           prog="%%jinja",
                                           epilog="Format defaults to --pretty")
    jinja_parser.add_argument("--template", "-t", help="Render a pre-defined template")
    jinja_parser.add_argument("--variables", "-v", metavar="DICT_VARIABLE",
                              help="Name of variable for environment (default 'jinja_env')", default="jinja_env")

    format_group = jinja_parser.add_mutually_exclusive_group()
    # For use in argument help: human-readable
    formats_to_human_names = dict(
        plain="plain",
        html="HTML",
        latex="LaTeX",
        pretty="pretty",
        # iframe="iframe",
        markdown="Markdown",
        svg="SVG",
        # code="Code",
    )
    # Map format identifiers to their display.* wrappers
    display_functions = dict(
        plain=display.display,
        html=display.HTML,
        latex=display.Latex,
        pretty=display.Pretty,
        # iframe=display.IFrame,
        markdown=display.Markdown,
        svg = display.SVG,
    ) # type: Dict[str, display.TextDisplayObject]

    try:
        display_functions["code"] = display.Code
        formats_to_human_names["code"] = "Code"
    except:
        formats_to_human_names["code"] = "Code (not installed)"
        display_functions["code"] = display.Pretty

    # Put the various formats into the argparser
    for output_type, human_name in formats_to_human_names.items():
        format_group.add_argument("--" + output_type, action='store_const',
                                  const=output_type, dest="format", help="Format as " + human_name)
    jinja_parser.set_defaults(format="pretty")

    jinja_parser.add_argument("--lang", "-l")

    @line_cell_magic
    def jinja(self, line, cell=None):
        """
        Jinja2 cell magic function. Use '%jinja -h' for parameter help.

        If "--template foo" is specified, "foo" will be looked up in our
        internal dictionary of templates; if not found, the current directory
        will be checked.

        If "--template" is not specified, the remainder of the cell is used
        as a template.

         Output may be formatted as --html, --latex, --markdown, --svg,
         --code, or --pretty (the default).

        If formatted as "--code", Pygment highlighting is available through
        "--lang"; see http://pygments.org/docs/lexers for available lexers.

        If "--variables" is specified, it must be a variable containing a
        dict; its values override notebook variables. If it's not specified,
        the dictionary "jinja_env" is used.

        Notebook variables are available to templates.

        Modifying variables (by <% set %>, for example) stores them back into their source;
        in --variables (including "jinja_env"), or in notebook variables.

        Note that %%yaml sets "jinja_env" by default.
        """

        args = self.jinja_parser.parse_args(line.split())
        # print(args)
        display_func_name = args.format
        display_func = self.display_functions[display_func_name]
        display_kwargs = {}
        if args.lang:
            if args.format != "code":
                raise ValueError("Can't specify --lang without --code")
            display_kwargs["language"] = args.lang

        top_env_var = self.get_nb_var(args.variables)
        all_vars = self.get_jinja_vars(top_env_var)

        jinja_options = self.get_nb_var("jinja_options", {})
        jinja_options["loader"] = self.loader
        self.jinja_environment = jinja2.Environment(**jinja_options) #()jinja_options)
        je = self.jinja_environment

        if args.template:
            # insert check here that the body of the cell is blank
            template = self.jinja_environment.get_template(name=args.template, globals=all_vars)
        else:
            template = self.jinja_environment.from_string(source=cell, globals=all_vars)

        assert isinstance(template, jinja2.Template)
        rend = template.render()

        self.update_vars_updated_by_jinja(template, top_env_var)

        return display_func(rend, **display_kwargs)

    def update_vars_updated_by_jinja(self, template, top_env_var):
        """Find modified variables from the template run, and store them
        back in their source.
        """
        vars = dict((k, v) for (k, v) in template.module.__dict__.items() if not k.startswith('_'))
        for k, v in vars.items():
            # If we were operating on specified globals, munge those instead of notebook globals
            if top_env_var.get(k):
                top_env_var[k] = v
            else:
                self.set_nb_var(k, v)

    # To limit the number of notebook variables pulled, don't pass in the
    # input boxes.
    history_names_re = re.compile("_i?[0-9]*")
    # ...with a few exceptions.
    extra_name_set = frozenset({"In", "Out", "__", "___", "_i", "_ii", "_iii"})

    def get_jinja_vars(self, top_vars: dict):
        """Pull a fine selection of notebook variables into the Jinja namespace"""
        user_vars = dict((k, v) for (k, v) in self.shell.user_ns.items()
                         if not k.startswith('_')
                         and k not in self.shell.user_ns_hidden)

        history_vars = dict((k, v) for (k, v) in self.shell.user_ns.items()
                            if self.history_names_re.fullmatch(k) or
                            k in self.extra_name_set)

        user_vars.update(history_vars)
        user_vars.update(top_vars)
        return user_vars

    # noinspection PyUnusedLocal
    @line_magic
    def jinja_inner(self, line):
        """This magic is for debugging only."""
        return self

    @cell_magic
    def yaml(self, line: str, cell):
        """ Usage:
        %%yaml [variable[=]]

        If "variable=" is omitted, set "jinja_env".
        """
        cmd = line.strip()
        words = cmd.split()
        if len(words) > 1:
            raise ValueError("Max one variable name")

        variable = None  # type: Optional[str]
        if len(words) == 1:
            variable = words[0]
            if variable.endswith("="):
                variable = variable[0:-1]

        v = yaml.load(cell)

        if variable:
            self.shell.user_ns[variable] = v
            return None
        else:
            self.shell.user_ns["jinja_env"] = v
            return v


def load_ipython_extension(ip):
    ip.register_magics(JinjaMagics)
