#!/usr/bin/env python3
#
# read_minix.py <disk_img>
#
# read good old amiga minix disks
#

import collections
import struct
import sys
import os

# device constants
BLK_SIZE = 1024


class BlockDev:
    def __init__(self, img_file, blk_size=BLK_SIZE):
        self.blk_size = blk_size
        with open(img_file, "rb") as fh:
            self.image = fh.read()
        self.image_size = len(self.image)
        self.num_blks = self.image_size // self.blk_size

    def read_block(self, num, size=1):
        if num >= self.num_blks:
            raise ValueError("invalid block num: " + num)
        offset = num * self.blk_size
        return self.image[offset : offset + (self.blk_size * size)]


# minix fs constants
MINIX_SUPER_BLK = 1
MINIX_SUPER_MAGIC = 0x137F
MINIX_VALID_FS = 0x0001
MINIX_ROOT_INODE = 1
MINIX_V1_INODE_SIZE = 32
MINIX_V1_INODE_PER_BLOCK = BLK_SIZE // MINIX_V1_INODE_SIZE
MINIX_V1_DIR_ENTRY_SIZE = 16

# inode mode
# define S_IFMT          0170000
# define S_IFSOCK        0140000         /* Reserved, not used */
# define S_IFLNK         0120000         /* Reserved, not used */
# define S_IFREG         0100000
# define S_IFBLK         0060000
# define S_IFDIR         0040000
# define S_IFCHR         0020000
# define S_IFIFO         0010000
MINIX_S_MODE = 0o7777
MINIX_S_IFMT = 0o170000
MINIX_S_IFREG = 0o0100000
MINIX_S_IFDIR = 0o040000

# /*
# * minix super-block data on disk
# */
# struct minix_super_block {
#        u16 s_ninodes; /* Number of inodes */
#        u16 s_nzones;  /* device size in blocks (v1) */
#        u16 s_imap_blocks; /* inode map size in blocks */
#        u16 s_zmap_blocks; /* zone map size in blocks */
#        u16 s_firstdatazone;   /* Where data blocks begin */
#        u16 s_log_zone_size;   /* unused... */
#        u32 s_max_size;    /* Max file size supported in bytes*/
#        u16 s_magic;   /* magic number... fs version */
#        u16 s_state;   /* filesystem state */
#        u32 s_zones;   /* device size in blocks (v2) */
#        u32 s_unused[4];
# };

super_names = (
    "ninode",
    "nzones",
    "imap_blocks",
    "zmap_blocks",
    "firstdatazone",
    "log_zone_size",
    "max_size",
    "magic",
    "state",
    "zones",
)
super_type = collections.namedtuple("SuperBlock", super_names)

# /*
# * This is the original minix inode layout on disk.
# * Note the 8-bit gid and atime and ctime.
# */
# struct minix_inode {
#        2 u16 i_mode;  /* File type and permissions for file */
#        2 u16 i_uid;   /* 16 uid */
#        4 u32 i_size;  /* File size in bytes */
#        4 u32 i_time;
#        1 u8  i_gid;
#        1 u8  i_nlinks;
#       14 u16 i_zone[7];
#        2 u16 i_indir_zone;
#        2 u16 i_dbl_indr_zone;
#   sum:32
# };

inode_names = (
    "mode",
    "uid",
    "size",
    "time",
    "gid",
    "nlinks",
    "zone0",
    "zone1",
    "zone2",
    "zone3",
    "zone4",
    "zone5",
    "zone6",
    "indir_zone",
    "dbl_indir_zone",
)
inode_type = collections.namedtuple("INode", inode_names)


class MinixINode:
    def __init__(self, num, raw_inode, fs):
        self.num = num
        self.raw_inode = raw_inode
        self.fs = fs

    def __repr__(self):
        ino = self.raw_inode
        mode = ino.mode & MINIX_S_MODE
        fmt = ino.mode & MINIX_S_IFMT
        return (
            f"MinixInode(id={self.num},mode={mode:04o},fmt={fmt:06o},size={ino.size})"
        )

    def dump(self, func=print):
        func(f"----- Inode #{self.num} -----")
        for k, v in self.raw_inode._asdict().items():
            if k == "mode":
                func(f"{k:20s} = {v:05o}")
            else:
                func(f"{k:20s} = {v}")

    def enum_data_zones(self):
        blk_size = self.fs.blk_dev.blk_size
        size = self.raw_inode.size
        blks = (size + blk_size - 1) // blk_size
        data_zones = []
        # direct zones
        blks = self._add_direct_zones(blks, data_zones)
        # indirect zone
        if blks > 0:
            idz_blk = self.raw_inode.indir_zone
            blks = self._add_indir_zones(idz_blk, blks, data_zones)
        # double indirect
        if blks > 0:
            did_blk = self.raw_inode.dbl_indir_zone
            blks = self._add_dbl_indir_zones(did_blk, blks, data_zones)
        assert blks == 0
        return data_zones

    def _add_direct_zones(self, blks, result_zones):
        ino = self.raw_inode
        zones = (
            ino.zone0,
            ino.zone1,
            ino.zone2,
            ino.zone3,
            ino.zone4,
            ino.zone5,
            ino.zone6,
        )
        for z in zones:
            result_zones.append(z)
            blks -= 1
            if blks == 0:
                break
        return blks

    def _add_indir_zones(self, idz_blk, blks, result_zones):
        data = self.fs.blk_dev.read_block(idz_blk)
        blk_size = self.fs.blk_dev.blk_size
        num_idz = blk_size // 2  # words
        decode = self.fs.endian_tag + "H"
        off = 0
        for i in range(num_idz):
            zone = struct.unpack_from(decode, data, off)[0]
            result_zones.append(zone)
            blks -= 1
            if blks == 0:
                break
            off += 2
        return blks

    def _add_dbl_indir_zones(self, did_blk, blks, result_zones):
        data = self.fs.blk_dev.read_block(did_blk)
        blk_size = self.fs.blk_dev.blk_size
        num_idz = blk_size // 2  # words
        decode = self.fs.endian_tag + "H"
        off = 0
        for i in range(num_idz):
            zone = struct.unpack_from(decode, data, off)[0]
            blks = self._add_indir_zones(zone, blks, result_zones)
            if blks == 0:
                break
            off += 2
        return blks

    def read_data(self):
        blk_size = self.fs.blk_dev.blk_size
        zones = self.enum_data_zones()
        data = bytearray()
        size = self.raw_inode.size
        for d in zones:
            blk = self.fs.blk_dev.read_block(d)
            if size < blk_size:
                data += blk[:size]
            else:
                data += blk
                size -= blk_size
        return data

    def is_dir(self):
        return (self.raw_inode.mode & MINIX_S_IFMT) == MINIX_S_IFDIR

    def is_file(self):
        return (self.raw_inode.mode & MINIX_S_IFMT) == 0

    def is_special(self):
        return (self.raw_inode.mode & MINIX_S_IFMT) != MINIX_S_IFREG

    def read_dir(self):
        assert self.is_dir()
        data = self.read_data()
        size = len(data)
        entries = size // MINIX_V1_DIR_ENTRY_SIZE
        off = 0
        result = {}
        for i in range(entries):
            inode, name = struct.unpack_from(">H14s", data, off)
            name = name.rstrip(b"\x00").decode("ascii")
            off += MINIX_V1_DIR_ENTRY_SIZE
            ino = self.fs.get_inode(inode)
            result[name] = ino
        return result

    def walk(self, path="", with_dir=True, with_special=False):
        entries = self.read_dir()
        for name, ino in entries.items():
            if ino.is_dir():
                if name not in (".", ".."):
                    # add dir itself
                    if with_dir:
                        yield path, name, ino
                    # add entries
                    yield from ino.walk(path + name + "/")
                else:
                    continue
            else:
                # skip special?
                if ino.is_special() and not with_special:
                    continue
                # yield non dir
                yield path, name, ino


class MinixFS:
    def __init__(self, blk_dev, big_endian=True):
        self.blk_dev = blk_dev
        self.big_endian = big_endian
        if big_endian:
            self.endian_tag = ">"
        else:
            self.endian_tag = "<"
        self.super_blk = self._read_super_block()
        self.imap = self._read_imap()
        self.zmap = self._read_zmap()
        self.inodes = self._read_inodes()
        self.root_inode = self.get_inode(MINIX_ROOT_INODE)

    def _read_super_block(self):
        data = self.blk_dev.read_block(MINIX_SUPER_BLK)
        fields = struct.unpack_from(self.endian_tag + "HHHHHHIHHI", data, 0)
        super_blk = super_type(*fields)
        assert super_blk.magic == MINIX_SUPER_MAGIC
        #   assert super_blk.state == MINIX_VALID_FS
        return super_blk

    def dump_super_block(self, func=print):
        func("----- Super Block -----")
        for k, v in self.super_blk._asdict().items():
            func(f"{k:20s} = {v}")

    def _read_imap(self):
        blk_off = MINIX_SUPER_BLK + 1
        blk_num = self.super_blk.imap_blocks
        return self.blk_dev.read_block(blk_off, blk_num)

    def _read_zmap(self):
        blk_off = MINIX_SUPER_BLK + 1
        blk_off += self.super_blk.imap_blocks
        blk_num = self.super_blk.zmap_blocks
        return self.blk_dev.read_block(blk_off, blk_num)

    def _read_inodes(self):
        blk_off = MINIX_SUPER_BLK + 1
        blk_off += self.super_blk.imap_blocks
        blk_off += self.super_blk.zmap_blocks
        blk_num = (self.super_blk.ninode + 1) // MINIX_V1_INODE_PER_BLOCK
        # check first data zone
        first_data_zone = blk_off + blk_num
        assert self.super_blk.firstdatazone == first_data_zone
        return self.blk_dev.read_block(blk_off, blk_num)

    def _read_inode(self, num):
        off = (num - 1) * MINIX_V1_INODE_SIZE
        data = self.inodes[off : off + MINIX_V1_INODE_SIZE]
        fields = struct.unpack(self.endian_tag + "HHIIBBHHHHHHHHH", data)
        inode = inode_type(*fields)
        return inode

    def get_inode(self, num):
        raw_inode = self._read_inode(num)
        return MinixINode(num, raw_inode, self)

    def get_root_inode(self):
        return self.root_inode

    def walk(self):
        return self.root_inode.walk()


# --- main ---
if len(sys.argv) != 2:
    print("no diskimage given!")
    sys.exit(1)

img_file_name = sys.argv[1]
out_dir_name = os.path.basename(img_file_name)
out_dir_name = os.path.splitext(out_dir_name)[0]

# read disk image
blk_dev = BlockDev(img_file_name)

# create minix fs
mfs = MinixFS(blk_dev)

# create out dir
if not os.path.isdir(out_dir_name):
    os.mkdir(out_dir_name)
os.chdir(out_dir_name)

for path, name, inode in mfs.walk():
    full = path + name
    print(f"{full:<40s} : {inode}")
    if inode.is_dir():
        # create sub dir if its not existing
        if not os.path.isdir(full):
            os.mkdir(full)
    else:
        # extract file
        data = inode.read_data()
        with open(full, "wb") as fh:
            fh.write(data)
