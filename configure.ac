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

AC_INIT([installsystems], [9], [sebastien.luttringer@smartjog.com])

AM_INIT_AUTOMAKE([foreign dist-xz no-dist-gzip])
AM_PATH_PYTHON([2.6])

AC_CONFIG_FILES([
	Makefile
	doc/Makefile
])

AC_ARG_WITH([bashcompdir],
	AS_HELP_STRING([--with-bashcompdir=DIR], [Bash completion directory]),
	[], [with_bashcompdir=${datadir}/bash-completion/completions]
)
AC_SUBST([bashcompdir], [$with_bashcompdir])

AC_ARG_WITH([zshcompdir],
	AS_HELP_STRING([--with-zshcompdir=DIR], [Zsh completion directory]),
	[], [with_zshcompdir=${datadir}/zsh/site-functions]
)
AC_SUBST([zshcompdir], [$with_zshcompdir])

AC_OUTPUT
