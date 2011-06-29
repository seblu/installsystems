## Makefile

.PHONY: all tar deb clean cleanbuild buildd dsc

NAME=installsystems
VERSION=$(shell sed -rn 's/version = "([^"]+)"/\1/p' installsystems/__init__.py)
BUILD_DIR=__build__

all:
	echo all is better than nothing

tar:
	git archive --prefix=$(NAME)-$(VERSION)/ HEAD | gzip -9 > $(NAME)-$(VERSION).tar.gz

dsc: cleanbuild tar
	mkdir $(BUILD_DIR)
	tar xfC $(NAME)-$(VERSION).tar.gz $(BUILD_DIR)
	cd $(BUILD_DIR) && dpkg-source -I -b $(NAME)-$(VERSION)

deb: cleanbuild
	mkdir $(BUILD_DIR)
	tar xfC $(NAME)-$(VERSION).tar.gz $(BUILD_DIR)
	cd $(BUILD_DIR)/$(NAME)-$(VERSION) && dpkg-buildpackage --source-option=-I

buildd: dsc
	chmod 644 $(BUILD_DIR)/$(NAME)_*.dsc $(BUILD_DIR)/$(NAME)_*.gz
	scp $(BUILD_DIR)/$(NAME)_*.dsc $(BUILD_DIR)/$(NAME)_*.gz incoming@buildd.fr.lan:sid

clean: cleanbuild

cleanbuild:
	-rm -rf  $(BUILD_DIR)

