# Makefile.am
# copyright (C) 2003 by Frank Mori Hess
# email : fmhess@users.sourceforge.net
#
#   This Makefile.am is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.

SUBDIRS = drivers

EXTRA_DIST = util bootstrap compat

ACLOCAL_AMFLAGS = -I m4

distclean-local:
	$(RM) $(srcdir)/util/linux_flags/fake.*
	$(RM) $(srcdir)/util/linux_flags/.*.cmd
	$(RM) -r $(srcdir)/util/linux_flags/.tmp_versions

dist-hook:
	-find $(distdir) -depth -name '.svn' -type d -exec $(RM) -r \{\} \;
	-find $(distdir) \( -name '*~' -o -name '.#*' \) -exec $(RM) \{\} \;
	$(RM) $(distdir)/util/linux_flags/fake.*
	$(RM) $(distdir)/util/linux_flags/.*.cmd
	$(RM) $(distdir)/util/linux_flags/flags 
	$(RM) $(distdir)/util/linux_flags/Module.*
	$(RM) $(distdir)/util/linux_flags/modules.order
	$(RM) -r $(distdir)/util/linux_flags/.tmp_versions
