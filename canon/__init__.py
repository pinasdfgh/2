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
"""Use old Canon cameras with Python.
"""

import logging

version_info = (0, 0, 1, 'dev')

__author__ = u'Kiril Zyapkov'
__contact__ = u'<kiril.zyapkov@gmail.com>'
__version__ = u'.'.join(map(str, version_info[:3]))
__copyright__ = u'Copyright (c) 2012 Kiril Zyapkov'
__license__   = u'GPLv3'

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

class CanonError(Exception): pass
