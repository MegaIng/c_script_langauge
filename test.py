from compiler import compile

TEST_SCRIPT = r"""
cimport "stdlib" (printf)

printf("%s", "Hello World")
"""

compile(TEST_SCRIPT)