# from __future__ import annotations
# 
# from subprocess import check_output
# import re
# 
# import pycparser
# import pycparserext.ext_c_lexer
# import pycparserext.ext_c_parser
# import pycparser_fake_libc
# from pycparser.plyparser import ParseError
# 
# 
# def preprocess_code(code, cpp_path='cpp', cpp_args: str | list[str] = ''):
#     """ Preprocess code as string using cpp.
# 
#         code:
#             The code to be piped to cpp
# 
#         cpp_path:
#         cpp_args:
#             Refer to the documentation of parse_file for the meaning of these
#             arguments.
# 
#         When successful, returns the preprocessed file's contents.
#         Errors from cpp will be printed out.
#     """
#     path_list = [cpp_path]
#     if isinstance(cpp_args, list):
#         path_list += cpp_args
#     elif cpp_args != '':
#         path_list += [cpp_args]
# 
#     try:
#         # Note the use of universal_newlines to treat all newlines
#         # as \n for Python's purpose
#         text = check_output(path_list, universal_newlines=True, input=code)
#     except OSError as e:
#         raise RuntimeError("Unable to invoke 'cpp'.  " +
#                            'Make sure its path was passed correctly\n' +
#                            ('Original error: %s' % e))
# 
#     return text
# 
# 
# code = preprocess_code("#include <stdarg.h>", cpp_path="cpp.exe",
#                        cpp_args=["-x", "c", "-D__attribute__(x)=", "-D__extension__="])
# 
# with open("preprocessed.c", "w") as f:
#     f.write(code)
# c_parser = pycparserext.ext_c_parser.GnuCParser()
# 
# try:
#     print(c_parser.parse(code, "<stdin>"))
# except ParseError as e:
#     m = re.fullmatch("((?:[cC]:)?[^:]+):(\d+):(\d+):(.*)", str(e))
#     path, line, column, message = m.groups()
#     raise ParseError(f"\n    File \"{path}\", line {line}, column {column}\n        {message}")
from pprint import pprint

from extract_headers import extract_header

header = extract_header("windows.h")

print(header.enum_values)
# pprint(header, width=160)
# 17.512kB
# 15.973kB
# 14.132kB
# 14.037kB
# 13.767kB
# 12.126kB
