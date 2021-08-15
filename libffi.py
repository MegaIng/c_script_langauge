from __future__ import annotations

import c_type
import extract_headers
from c_type import c_void, c_float, c_double, c_long_double

ffi_header = extract_headers.extract_header("ffi.h")

integer_sizes = {}

for name in ("uchar", "schar", "ushort", "sshort", "uint", "sint", "ulong", "slong"):
    m = ffi_header.macros["ffi_type_" + name]
    n = m.replacement.removeprefix("ffi_type_")
    integer_sizes[name] = n

integer_sizes["ulong_long"] = "uint64"
integer_sizes["slong_long"] = "sint64"

FFI_TYPE_IDS = {
    t: ffi_header.get_constant_int("FFI_TYPE_" + n)
    for t, n in (
        (c_void, "VOID"),
        ("struct", "STRUCT"),
        ("pointer", "POINTER"),
        (c_float, "FLOAT"),
        (c_double, "DOUBLE"),
        (c_long_double, "LONGDOUBLE"),
        *((getattr(c_type, "c_"+n), t.upper()) for n,t in integer_sizes.items())
    )
}