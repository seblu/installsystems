# man pages stuff
man1_MANS = is.1

SUFFIXES = .1 .1.rst

.1.rst.1:
	rst2man $< $@

CLEANFILES = $(man1_MANS)
EXTRA_DIST = $(man1_MANS)
