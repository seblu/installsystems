## Makefile

.PHONY: all tar deb clean cleanbuild buildd

NAME=installsystems
BUILD_DIR=__build__

all:
	echo all is better than nothing

tar: cleanbuild
	git clone "." $(BUILD_DIR)/$(NAME)
	-dpkg-source -Zbzip2 -I -b $(BUILD_DIR)/$(NAME)
	-rm -rf  $(BUILD_DIR)

deb: cleanbuild
	git clone "." $(BUILD_DIR)/$(NAME)
	-cd $(BUILD_DIR)/$(NAME) && dpkg-buildpackage --source-option=-I
	-rm -rf  $(BUILD_DIR)/$(NAME)
	mv -vf $(BUILD_DIR)/* .
	-rm -rf $(BUILD_DIR)

buildd: tar
	chmod 644 $(NAME)_*.dsc $(NAME)_*.tar.bz2
	scp $(NAME)_*.dsc $(NAME)_*.tar.bz2 incoming@buildd.fr.lan:squeeze

clean: clean_build

cleanbuild:
	-rm -rf  $(BUILD_DIR)

