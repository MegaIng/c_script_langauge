import json
from pprint import pprint
import pyparsing

from compiler import compile

TEST_SCRIPT = r"""
cimport "stdio.h" (printf)

printf("%s\n", "Hello World")
"""

code = compile(TEST_SCRIPT)

pprint(code)

json.dump(code.to_json(), open("test.code.json", "w"))
