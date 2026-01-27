# Project file for unified translation extraction
SOURCES += ../Main.py \
           ../gui/*.py \
           ../utils/*.py \
           ../core/*.py \
           ../parsers/*.py

# Unified translation files
TRANSLATIONS += app_en.ts \
                app_sv.ts \
                app_es.ts \
                app_fr.ts \
                app_id.ts \
                app_de.ts \
                app_ja.ts \
                app_zh.ts

# Output directory for compiled translations
QM_FILES_RESOURCE_PREFIX = /translations
