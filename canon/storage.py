#  This file is part of canon-remote.
#  Copyright (C) 2011-2012 Kiril Zyapkov <kiril.zyapkov@gmail.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging

from canon import protocol, commands
from canon.util import extract_string, le32toi, itole32a
from canon.bitfield import BooleanFlag, Bitfield
from array import array
import itertools

_log = logging.getLogger(__name__)

class FSAttributes(Bitfield):

    _size = 0x01

    DOWNLOADED = 0x20
    WRITE_PROTECTED = 0x01
    RECURSE_DIR = 0x80
    NONRECURSE_DIR = 0x10

    UNKNOWN_2 = 0x02
    UNKNOWN_4 = 0x04
    UNKNOWN_8 = 0x08
    UNKNOWN_40 = 0x40

    recurse = BooleanFlag(0, true=RECURSE_DIR, false=NONRECURSE_DIR)
    downloaded = BooleanFlag(0, true=DOWNLOADED)
    protected = BooleanFlag(0, true=WRITE_PROTECTED)

    @property
    def is_dir(self):
        return (self.RECURSE_DIR in self.recurse
                    or self.NONRECURSE_DIR in self.recurse)

class FSEntry(object):
    def __init__(self, name, attributes, size=None, timestamp=None):
        self.name = name
        self.size = size
        self.timestamp = timestamp
        if not isinstance(attributes, FSAttributes):
            attributes = FSAttributes(attributes)
        self.attr = attributes
        self.children = []
        self.parent = None

    @property
    def full_path(self):
        if self.parent is None:
            return self.name
        return self.parent.full_path + '\\' + self.name
    @property
    def entry_size(self):
        return 11 + len(self.name)

    @property
    def type_(self):
        return 'd' if self.attr.is_dir else 'f'

    @property
    def is_dir(self):
        return self.attr.is_dir

    @property
    def is_file(self):
        return not self.attr.is_dir

    def __iter__(self):
        yield self
        for entry in itertools.chain(*self.children):
            yield entry

    def __repr__(self):
        return "<FSEntry {0.type_} '{0.full_path}'>".format(self)

    def __str__(self):
        return self.full_path

class ListDirectoryCmd(commands.VariableResponseCommand):
    cmd1 = 0x0b
    cmd2 = 0x11
    def __init__(self, path=None, recurse=12):
        payload = array('B', [recurse])
        payload.extend(array('B', path))
        payload.extend(array('B', [0x00] * 3))
        super(ListDirectoryCmd, self).__init__(payload)

    def _entry_generator(self, data):
        idx = 0
        while True:
            name = extract_string(data, idx+10)
            if not name:
                raise StopIteration()
            entry = FSEntry(name, attributes=data[idx:idx+1],
                            size=le32toi(data[idx+2:idx+6]),
                            timestamp=le32toi(data[idx+6:idx+10]))
            idx += entry.entry_size
            yield entry

    def _parse_response(self, data):
        entry_generator = self._entry_generator(data)
        root = entry_generator.next()
        current = root
        for entry in entry_generator:
            if entry.name == '..':
                current = current.parent
                continue
            current.children.append(entry)
            entry.parent = current
            if entry.name.startswith('.\\'):
                entry.name = entry.name[2:]
                current = entry
            _log.info(entry)

        return root


class GetFileCmd(commands.VariableResponseCommand):
    cmd1 = 0x01
    cmd2 = 0x11
    def __init__(self, path, target, thumbnail=False):
        payload = array('B', [0x00]*8)
        payload[0] = 0x01 if thumbnail else 0x00
        payload[4:8] = itole32a(protocol.MAX_CHUNK_SIZE)
        payload.extend(array('B', path))
        payload.append(0x00)
        self._target = target
        super(GetFileCmd, self).__init__(payload)
    def execute(self, usb):
        reader = self._send(usb)
        for chunk in reader:
            self._target.write(chunk)


class CanonStorage(object):
    def __init__(self, usb):
        self._usb = usb
        self._drive = None

    def initialize(self, force=False):
        self.get_drive()
        #self.get_disk_info()

    def get_disk_info(self):
        raise NotImplementedError()

    def get_drive(self):
        """Returns the Windows-like camera FS root.
        """
        self._drive = commands.IdentifyFlashDeviceCmd().execute(self._usb)
        return self._drive

    @property
    def drive(self):
        if not self._drive:
            self.get_drive()
        return self._drive

    def ls(self, path=None, recurse=12):
        """Return a class:`FSEntry` for the path or storage root.

        By default this will return the tree starting at ``path`` with large
        enough recursion depth to cover every file on the camera storage.
        """
        path = self._normalize_path(path)
        return ListDirectoryCmd(path, recurse).execute(self._usb)

    def walk(self, path=None):
        """Iterate over camera storage contents, like ``os.walk()``.
        """
        root = self.ls(path)
        queue = [root]
        while len(queue):
            entry = queue.pop(0)
            dirpath = entry.full_path
            dirnames = []
            filenames = []
            for child in entry.children:
                if child.is_dir:
                    dirnames.append(child.name)
                    queue.append(child)
                else:
                    filenames.append(child.name)
            yield (dirpath, dirnames, filenames)

    def get_file(self, path, target, thumbnail=False):
        """Download a file from the camera.

        ``target`` is either a file-like object or the file name to open
        and write to.

        ``thumbnail`` says wheter to get the thumbnail or the whole file.

        """
        if not hasattr(target, 'write'):
            target = open(target, 'wb+')
        path = self._normalize_path(path)
        GetFileCmd(path, target, thumbnail).execute(self._usb)

    def mkdir(self):
        raise NotImplementedError()

    def rmdir(self):
        raise NotImplementedError()

    def put_file(self):
        raise NotImplementedError()

    # ...

    def _normalize_path(self, path):
        if path is None:
            path = ''
        if isinstance(path, FSEntry):
            path = path.full_path
        path = path.replace('/', '\\')
        if not path.startswith(self.drive):
            path = '\\'.join([self.drive, path]).rstrip('\\')
        return path



