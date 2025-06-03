import ast
from pathlib import Path


class MyVisitor(ast.NodeVisitor):
    def __init__(self):
        self.indent = ""
        self.reader_name = None
        self.identifier = None
        self.priority = None
        self.check = None
        self.prepare_tables = None

    def generic_visit(self, node):
        old_indent = self.indent
        self.indent += "  "
        super().generic_visit(node)
        self.indent = old_indent

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.id == "identifier":
                    self.identifier_found = True
                    if isinstance(node.value, ast.Constant):
                        self.identifier = node.value.value
                elif target.id == "priority":
                    self.priority_found = True
                    if isinstance(node.value, ast.Constant):
                        self.priority = node.value.value
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.reader_name = node.name
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if node.name == "check":
            self.check = ast.unparse(node)
        elif node.name == "prepare_tables":
            self.prepare_tables = ast.unparse(node)
        self.generic_visit(node)


def read_metadata_from_readercode(path):
    """
    :param path:
    :return: mv.reader_name, mv.identifier, mv.priority, mv.check, mv.prepare_tables
    """
    with open(path) as f:
        source = f.read()
    tree = ast.parse(source)
    mv = MyVisitor()
    mv.visit(tree)
    return mv.reader_name, mv.identifier, mv.priority, mv.check, mv.prepare_tables

if __name__ == "__main__":
    res = read_metadata_from_readercode(Path(__file__).parent.parent.joinpath('readers/aif.py'))
    for i in range(len(res)):
        print(res[i])


