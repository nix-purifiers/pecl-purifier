PHP_ARG_ENABLE([purifierproof], [whether to enable purifierproof],
  [AS_HELP_STRING([--enable-purifierproof], [Enable purifierproof])], [yes])
if test "$PHP_PURIFIERPROOF" != "no"; then
  PHP_NEW_EXTENSION([purifierproof], [purifierproof.c], [$ext_shared])
fi
