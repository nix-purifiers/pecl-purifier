#ifdef HAVE_CONFIG_H
#include "config.h"
#endif
#include "php.h"
ZEND_BEGIN_ARG_WITH_RETURN_TYPE_INFO_EX(arginfo_purifier_answer, 0, 0, IS_LONG, 0)
ZEND_END_ARG_INFO()
PHP_FUNCTION(purifier_answer) { ZEND_PARSE_PARAMETERS_NONE(); RETURN_LONG(42); }
static const zend_function_entry purifierproof_functions[] = {
    PHP_FE(purifier_answer, arginfo_purifier_answer)
    PHP_FE_END
};
zend_module_entry purifierproof_module_entry = {
    STANDARD_MODULE_HEADER, "purifierproof", purifierproof_functions,
    NULL, NULL, NULL, NULL, NULL, "0.1.0", STANDARD_MODULE_PROPERTIES
};
#ifdef COMPILE_DL_PURIFIERPROOF
ZEND_GET_MODULE(purifierproof)
#endif
