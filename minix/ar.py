"""ar - unarchiver for minix archives"""

import struct
import collections

MINIX_ARCHIVE_MAGIC = 0xFF2C
MINIX_ARCHIVE_HEADER_SIZE = 26
MINIX_ARCHIVE_SYMDEF = "__.SYMDEF"

# struct  ar_hdr {
#    14 char    ar_name[14];
#     4 long    ar_date;
#     1 char    ar_uid;
#     1 char    ar_gid;
#     2 short   ar_mode;
#     4 long    ar_size;
# };

header_names = (
    "name",
    "date_hi",
    "date_lo",
    "uid",
    "gid",
    "mode",
    "size_hi",
    "size_lo",
)
header_type = collections.namedtuple("ArchiveHeader", header_names)


class MinixArchiveEntry:
    def __init__(self, header, archive):
        self.header = header
        self.archive = archive
        self.name = self.header.name.rstrip(b"\x00").decode("ascii")
        self.date = self.header.date_hi << 16 | self.header.date_lo
        self.size = self.header.size_hi << 16 | self.header.size_lo
        if self.size & 1 == 1:
            self.pad_size = 1
        else:
            self.pad_size = 0

    def __repr__(self):
        return f"MinixArchiveEntry(name={self.name},size={self.size:08x},date={self.date:08x})"


class MinixArchive:
    def __init__(self, name):
        self.name = name
        self.fobj = open(name, "rb")
        self._check_magic()

    def close(self):
        self.fobj.close()

    def _check_magic(self):
        buf = self.fobj.read(2)
        magic = struct.unpack("<H", buf)[0]
        assert magic == MINIX_ARCHIVE_MAGIC

    def _get_entry(self):
        data = self.fobj.read(MINIX_ARCHIVE_HEADER_SIZE)
        if not data:
            return
        fields = struct.unpack("<14sHHBBHHH", data)
        hdr = header_type(*fields)
        return MinixArchiveEntry(hdr, self)

    def walk(self):
        while True:
            entry = self._get_entry()
            if not entry:
                return
            # skip ranlib entry
            if entry.name == MINIX_ARCHIVE_SYMDEF:
                self.skip(entry)
            else:
                yield entry

    def skip(self, entry):
        self.fobj.seek(entry.size + entry.pad_size, 1)

    def read(self, entry):
        data = self.fobj.read(entry.size)
        if entry.pad_size:
            self.fobj.seek(entry.pad_size, 1)
        return data
