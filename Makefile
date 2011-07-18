## Makefile

.PHONY: all tar deb clean cleanbuild buildd dsc

NAME=installsystems
VERSION=$(shell sed -rn 's/version = "([^"]+)"/\1/p' installsystems/__init__.py)
BUILD_DIR=__build__
DISTRO=sid

all:
	echo all is better than nothing

$(NAME)-$(VERSION).tar.gz:
	git archive --prefix=$(NAME)-$(VERSION)/ HEAD | gzip -9 > $(NAME)-$(VERSION).tar.gz

tar: cleantar $(NAME)-$(VERSION).tar.gz

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
	-rm -f $(NAME)-$(VERSION).tar.gz
