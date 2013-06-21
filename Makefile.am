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

bashcompdir=@bashcompdir@
zshcompdir=@zshcompdir@

SUBDIRS = doc

EXTRA_DIST = COPYRIGHT LICENSE \
	misc/installsystems.conf misc/repository.conf \
	misc/zsh-completion misc/bash-completion

dist_doc_DATA = README COPYRIGHT LICENSE AUTHORS DEPENDENCIES

# main binary
dist_bin_SCRIPTS = bin/is
noinst_SCRIPTS = installsystems/__init__.py

# python library
installsystemsdir=$(pythondir)/installsystems
installsystems_PYTHON = \
	installsystems/__init__.py \
	installsystems/config.py \
	installsystems/database.py \
	installsystems/exception.py \
	installsystems/image.py \
	installsystems/printer.py \
	installsystems/repository.py \
	installsystems/tarball.py \
	installsystems/template.py \
	installsystems/tools.py

do_substitution = $(SED) -e 's,[@]pythondir[@],$(pythondir),g' \
	-e 's,[@]PACKAGE[@],$(PACKAGE),g' \
	-e 's,[@]VERSION[@],$(VERSION),g'

installsystems/__init__.py: installsystems/__init__.py.in
	$(do_substitution) < $(srcdir)/$< > $@


CLEANFILES = $(bin_SCRIPTS) installsystems/__init__.py

install-exec-hook:
	ln -fs is $(DESTDIR)$(bindir)/installsystems
	install -dm755 $(DESTDIR)$(sysconfdir)/installsystems $(DESTDIR)$(bashcompdir) $(DESTDIR)$(zshcompdir)
	install -m644 misc/{repository,installsystems}.conf $(DESTDIR)$(sysconfdir)/installsystems/
	install -m644 misc/bash-completion $(DESTDIR)$(bashcompdir)/is
	install -m644 misc/zsh-completion $(DESTDIR)$(zshcompdir)/_installsystems

dist-hook:
	rm -f $(distdir)/TODO
