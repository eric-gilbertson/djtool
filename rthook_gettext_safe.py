# rthook_gettext_safe.py
#
# Cross-platform safe gettext override for PyInstaller builds.
# Prevents FileNotFoundError: No translation file found for domain: 'base'

import gettext

_real_translation = gettext.translation

def _safe_translation(domain, localedir=None, languages=None, class_=None, fallback=False):
    try:
        # Force fallback=True no matter what caller requested
        return _real_translation(
            domain,
            localedir=localedir,
            languages=languages,
            class_=class_,
            fallback=True
        )
    except Exception:
        return gettext.NullTranslations()

gettext.translation = _safe_translation

