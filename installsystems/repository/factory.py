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

from installsystems.exception import ISError
from installsystems.repository.repository1 import Repository1
from installsystems.repository.repository2 import Repository2

class RepositoryFactory(object):
    '''
    Repository factory
    '''

    def __new__(cls, config):
        '''
        Factory design pattern.
        Return the right object version based on a version detector function
        '''
        version = cls.version(config.dbpath)
        if version == 1:
            return Repostory1(config)
        elif version == 2:
            return Repository2(config)
        raise ISError(u"Unsupported repository version")

    @staticmethod
    def version(path):
        '''
        Return the version of a database
        '''
        return 2
