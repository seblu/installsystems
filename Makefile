#!/usr/bin/make

# Installsystems - Python installation framework
# Copyright © 2011-2012 Smartjog S.A
# Copyright © 2011-2012 Sébastien Luttringer
#
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

.PHONY: all tar deb clean cleanbuild buildd dsc doc

NAME=installsystems
VERSION=$(shell sed -rn 's/version = "([^"]+)"/\1/p' installsystems/__init__.py)
BUILD_DIR=__build__
DISTRO=squeeze

all:
	echo all is better than nothing

$(NAME)-$(VERSION).tar.gz:
	git archive --prefix=$(NAME)-$(VERSION)/ HEAD | gzip -9 > $(NAME)-$(VERSION).tar.gz

tar: cleantar $(NAME)-$(VERSION).tar.gz

doc:
	cd doc && make html

dsc: cleanbuild $(NAME)-$(VERSION).tar.gz
	mkdir $(BUILD_DIR)
	tar xfC $(NAME)-$(VERSION).tar.gz $(BUILD_DIR)
	cd $(BUILD_DIR) && dpkg-source -I -b $(NAME)-$(VERSION)

deb: cleanbuild $(NAME)-$(VERSION).tar.gz
	mkdir $(BUILD_DIR)
	tar xfC $(NAME)-$(VERSION).tar.gz $(BUILD_DIR)
	cd $(BUILD_DIR)/$(NAME)-$(VERSION) && dpkg-buildpackage --source-option=-I -us -uc

buildd: dsc
	chmod 644 $(BUILD_DIR)/$(NAME)_*.dsc $(BUILD_DIR)/$(NAME)_*.gz
	scp $(BUILD_DIR)/$(NAME)_*.dsc $(BUILD_DIR)/$(NAME)_*.gz incoming@buildd.fr.lan:$(DISTRO)

clean: cleantar cleanbuild

cleanbuild:
	-rm -rf  $(BUILD_DIR)

cleantar:
	-rm -f $(NAME)-*.tar.gz
