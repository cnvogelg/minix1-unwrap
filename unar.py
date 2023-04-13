#!/usr/bin/env python3
#
# unar.py <archive.a>
#
# unpack a minix1 .a archive file
#

import sys
import minix.ar

if len(sys.argv) != 2:
    print("no archive given!")
    sys.exit(1)

archive_name = sys.argv[1]
ar = minix.ar.MinixArchive(archive_name)
for entry in ar.walk():
    print(f"{entry.name:<20s} {entry.size}")
    data = ar.read(entry)
    with open(entry.name, "wb") as fh:
        fh.write(data)
ar.close()
