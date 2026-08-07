#!/bin/sh
set -e

mysql \
  --binary-mode=1 \
  --default-character-set=utf8mb4 \
  -u"${MYSQL_USER}" \
  -p"${MYSQL_PASSWORD}" \
  "${TRAVEL_DB_NAME}" \
  < /seed/package_seed.sql