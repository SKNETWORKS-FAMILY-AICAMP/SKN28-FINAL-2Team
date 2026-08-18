#!/bin/sh
set -e

for sql_file in \
  /seed/package_seed.sql \
  /package-migrations/migrate_package_companion_tags_50.sql
do
  mysql \
    --binary-mode=1 \
    --default-character-set=utf8mb4 \
    -u"${MYSQL_USER}" \
    -p"${MYSQL_PASSWORD}" \
    "${TRAVEL_DB_NAME}" \
    < "${sql_file}"
done
