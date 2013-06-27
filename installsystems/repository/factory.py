# -*- python -*-
# -*- coding: utf-8 -*-

# This file is part of Installsystems.
#
# Installsystems is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Installsystems is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Installsystems.  If not, see <http://www.gnu.org/licenses/>.

'''
Repository Factory
'''

from installsystems.printer import debug, warn
from installsystems.exception import ISWarning, ISError
from installsystems.repository.database import Database
from installsystems.repository.repository1 import Repository1
from installsystems.repository.repository2 import Repository2

class RepositoryFactory(object):
    '''
    Repository factory
    '''

    def __init__(self):

        self.repo_class = {
            1: Repository1,
            2: Repository2,
        }

    def create(self, config):
        db = None
        if not config.offline:
            try:
                db = Database(config.dbpath)
            except ISWarning as e:
                warn('[%s]: %s' % (config.name, e))
                config.offline = True
            except ISError:
                debug(u"Unable to load database %s" % config.dbpath)
                config.offline = True
        if config.offline:
            debug(u"Repository %s is offline" % config.name)
        if db is None:
            return Repository2(config)
        else:
            return self.repo_class[int(db.version)](config, db)

