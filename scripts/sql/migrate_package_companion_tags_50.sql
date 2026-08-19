-- Stores companion/package tags on packages and subtype tags on each item.
SET @package_ddl = (
    SELECT IF(COUNT(*) = 0, 'ALTER TABLE travel_packages ADD COLUMN companion VARCHAR(100) NOT NULL DEFAULT ''''', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'companion'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 0, 'ALTER TABLE travel_packages ADD COLUMN tags VARCHAR(255) NOT NULL DEFAULT ''''', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'tags'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 0, 'ALTER TABLE package_items ADD COLUMN tags VARCHAR(100) NOT NULL DEFAULT ''''', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'package_items'
      AND COLUMN_NAME = 'tags'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

START TRANSACTION;

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D1-01';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D1-02';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,experience'
WHERE package_id = 'VIRTUAL-JEJU-D1-03';

UPDATE travel_packages
SET companion = 'friend,couple,family',
    tags = 'nature'
WHERE package_id = 'VIRTUAL-JEJU-D1-04';

UPDATE travel_packages
SET companion = 'solo,friend,couple,family',
    tags = 'nature'
WHERE package_id = 'VIRTUAL-JEJU-D1-05';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,experience'
WHERE package_id = 'VIRTUAL-JEJU-D1-06';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature'
WHERE package_id = 'VIRTUAL-JEJU-D1-07';

UPDATE travel_packages
SET companion = 'friend',
    tags = 'experience'
WHERE package_id = 'VIRTUAL-JEJU-D1-08';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,experience'
WHERE package_id = 'VIRTUAL-JEJU-D1-09';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature'
WHERE package_id = 'VIRTUAL-JEJU-D1-10';

UPDATE travel_packages
SET companion = 'solo',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D2-01';

UPDATE travel_packages
SET companion = 'friend,couple,family',
    tags = 'nature'
WHERE package_id = 'VIRTUAL-JEJU-D2-02';

UPDATE travel_packages
SET companion = 'friend,couple,family',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D2-03';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D2-04';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D2-05';

UPDATE travel_packages
SET companion = 'friend,couple,family',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D2-06';

UPDATE travel_packages
SET companion = 'friend',
    tags = 'nature,experience'
WHERE package_id = 'VIRTUAL-JEJU-D2-07';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,experience'
WHERE package_id = 'VIRTUAL-JEJU-D2-08';

UPDATE travel_packages
SET companion = 'solo',
    tags = 'culture'
WHERE package_id = 'VIRTUAL-JEJU-D2-09';

UPDATE travel_packages
SET companion = 'friend',
    tags = 'nature'
WHERE package_id = 'VIRTUAL-JEJU-D2-10';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D3-01';

UPDATE travel_packages
SET companion = 'friend',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D3-02';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D3-03';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D3-04';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D3-05';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D3-06';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D3-07';

UPDATE travel_packages
SET companion = 'friend,couple,family',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D3-08';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,experience'
WHERE package_id = 'VIRTUAL-JEJU-D3-09';

UPDATE travel_packages
SET companion = 'solo',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D3-10';

UPDATE travel_packages
SET companion = 'friend',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D4-01';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D4-02';

UPDATE travel_packages
SET companion = 'friend,couple,family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D4-03';

UPDATE travel_packages
SET companion = 'friend,couple,family',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D4-04';

UPDATE travel_packages
SET companion = 'solo',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D4-05';

UPDATE travel_packages
SET companion = 'friend,couple,family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D4-06';

UPDATE travel_packages
SET companion = 'friend',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D4-07';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D4-08';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D4-09';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D4-10';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,experience'
WHERE package_id = 'VIRTUAL-JEJU-D5-01';

UPDATE travel_packages
SET companion = 'friend,couple,family',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D5-02';

UPDATE travel_packages
SET companion = 'friend',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D5-03';

UPDATE travel_packages
SET companion = 'friend,couple,family',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D5-04';

UPDATE travel_packages
SET companion = 'friend,couple,family',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D5-05';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D5-06';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D5-07';

UPDATE travel_packages
SET companion = 'family',
    tags = 'nature,experience'
WHERE package_id = 'VIRTUAL-JEJU-D5-08';

UPDATE travel_packages
SET companion = 'solo',
    tags = 'nature,culture'
WHERE package_id = 'VIRTUAL-JEJU-D5-09';

UPDATE travel_packages
SET companion = 'friend,couple,family',
    tags = 'nature,culture,experience'
WHERE package_id = 'VIRTUAL-JEJU-D5-10';

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-01'
  AND pi.content_id = 2704412;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-01'
  AND pi.content_id = 2606696;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-01'
  AND pi.content_id = 2876854;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-01'
  AND pi.content_id = 130461;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-01'
  AND pi.content_id = 2553685;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-02'
  AND pi.content_id = 126470;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-02'
  AND pi.content_id = 126438;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-02'
  AND pi.content_id = 1305270;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-02'
  AND pi.content_id = 130494;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-03'
  AND pi.content_id = 126441;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-03'
  AND pi.content_id = 2606214;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-03'
  AND pi.content_id = 2765209;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-03'
  AND pi.content_id = 3410648;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-04'
  AND pi.content_id = 2715650;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'cafe'
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-04'
  AND pi.content_id = 2384996;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-04'
  AND pi.content_id = 228854;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-04'
  AND pi.content_id = 127861;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-05'
  AND pi.content_id = 2564158;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-05'
  AND pi.content_id = 126435;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-05'
  AND pi.content_id = 2839742;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-05'
  AND pi.content_id = 127336;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-06'
  AND pi.content_id = 2779449;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-06'
  AND pi.content_id = 2714659;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-06'
  AND pi.content_id = 1866904;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-06'
  AND pi.content_id = 1993734;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-07'
  AND pi.content_id = 126437;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-07'
  AND pi.content_id = 2359165;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-07'
  AND pi.content_id = 2781401;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-07'
  AND pi.content_id = 129617;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-08'
  AND pi.content_id = 637398;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-08'
  AND pi.content_id = 2751854;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-08'
  AND pi.content_id = 2714241;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-08'
  AND pi.content_id = 2852023;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-08'
  AND pi.content_id = 2738675;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-09'
  AND pi.content_id = 2472824;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-09'
  AND pi.content_id = 664081;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-09'
  AND pi.content_id = 228853;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-09'
  AND pi.content_id = 4073368;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-09'
  AND pi.content_id = 3056135;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-10'
  AND pi.content_id = 126448;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-10'
  AND pi.content_id = 2714306;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-10'
  AND pi.content_id = 2850048;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'shopping'
WHERE tp.package_id = 'VIRTUAL-JEJU-D1-10'
  AND pi.content_id = 1013246;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-01'
  AND pi.content_id = 142976;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-01'
  AND pi.content_id = 3061676;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-01'
  AND pi.content_id = 1906195;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-01'
  AND pi.content_id = 2660122;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-01'
  AND pi.content_id = 2850014;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-01'
  AND pi.content_id = 2763726;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-01'
  AND pi.content_id = 2740014;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-01'
  AND pi.content_id = 3083715;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-01'
  AND pi.content_id = 2851992;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-01'
  AND pi.content_id = 128050;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-02'
  AND pi.content_id = 3344565;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-02'
  AND pi.content_id = 2715648;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-02'
  AND pi.content_id = 2847737;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-02'
  AND pi.content_id = 126672;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-02'
  AND pi.content_id = 126446;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'shopping'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-02'
  AND pi.content_id = 1013258;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-02'
  AND pi.content_id = 1620936;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-02'
  AND pi.content_id = 2894407;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-02'
  AND pi.content_id = 129405;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-03'
  AND pi.content_id = 2561932;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-03'
  AND pi.content_id = 2661407;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-03'
  AND pi.content_id = 2785301;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-03'
  AND pi.content_id = 987913;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-03'
  AND pi.content_id = 2778897;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-03'
  AND pi.content_id = 130512;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-03'
  AND pi.content_id = 2837142;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-03'
  AND pi.content_id = 1911160;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-03'
  AND pi.content_id = 2753082;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-03'
  AND pi.content_id = 2663244;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-04'
  AND pi.content_id = 984523;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-04'
  AND pi.content_id = 1798082;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-04'
  AND pi.content_id = 3410530;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-04'
  AND pi.content_id = 2837142;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-04'
  AND pi.content_id = 2606298;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-04'
  AND pi.content_id = 129699;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-04'
  AND pi.content_id = 2870559;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-04'
  AND pi.content_id = 2742344;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-04'
  AND pi.content_id = 1206420;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-05'
  AND pi.content_id = 735781;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-05'
  AND pi.content_id = 3061676;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-05'
  AND pi.content_id = 2861489;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-05'
  AND pi.content_id = 129400;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-05'
  AND pi.content_id = 126452;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-05'
  AND pi.content_id = 126472;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-05'
  AND pi.content_id = 2714222;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-05'
  AND pi.content_id = 2836910;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-05'
  AND pi.content_id = 2765208;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-05'
  AND pi.content_id = 1918639;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-06'
  AND pi.content_id = 4081269;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'shopping'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-06'
  AND pi.content_id = 1013258;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-06'
  AND pi.content_id = 2831961;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-06'
  AND pi.content_id = 1220821;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-06'
  AND pi.content_id = 129276;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-06'
  AND pi.content_id = 127052;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-06'
  AND pi.content_id = 2738763;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-06'
  AND pi.content_id = 4002839;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-06'
  AND pi.content_id = 126443;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-06'
  AND pi.content_id = 2940981;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-06'
  AND pi.content_id = 126457;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-07'
  AND pi.content_id = 2019719;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-07'
  AND pi.content_id = 2792565;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-07'
  AND pi.content_id = 2870537;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-07'
  AND pi.content_id = 2738665;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-07'
  AND pi.content_id = 2778044;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-07'
  AND pi.content_id = 2522221;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-07'
  AND pi.content_id = 1909258;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-07'
  AND pi.content_id = 127479;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-07'
  AND pi.content_id = 637212;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-08'
  AND pi.content_id = 142946;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-08'
  AND pi.content_id = 3505052;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-08'
  AND pi.content_id = 2791440;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-08'
  AND pi.content_id = 126439;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-08'
  AND pi.content_id = 126449;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-08'
  AND pi.content_id = 126440;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-08'
  AND pi.content_id = 2840903;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-08'
  AND pi.content_id = 3031021;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-08'
  AND pi.content_id = 2562214;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-09'
  AND pi.content_id = 2948165;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-09'
  AND pi.content_id = 2553685;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-09'
  AND pi.content_id = 4083815;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-09'
  AND pi.content_id = 2738692;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-09'
  AND pi.content_id = 126460;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-09'
  AND pi.content_id = 2931932;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-09'
  AND pi.content_id = 2791473;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-09'
  AND pi.content_id = 2877751;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-09'
  AND pi.content_id = 2048059;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-09'
  AND pi.content_id = 2778809;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-10'
  AND pi.content_id = 935073;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-10'
  AND pi.content_id = 126474;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-10'
  AND pi.content_id = 2853604;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-10'
  AND pi.content_id = 3056151;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-10'
  AND pi.content_id = 2414827;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'shopping'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-10'
  AND pi.content_id = 2931257;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-10'
  AND pi.content_id = 2871898;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-10'
  AND pi.content_id = 2853484;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-10'
  AND pi.content_id = 128641;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D2-10'
  AND pi.content_id = 2788436;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 3079902;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 3037603;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 2759036;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 2863658;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 2847726;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 2723542;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 1964507;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 3112043;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 2836855;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 2663244;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 572973;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 3329719;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 2854015;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-01'
  AND pi.content_id = 126473;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 984523;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 3037977;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 930345;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 2839771;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 3056448;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 2503694;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 636393;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 594065;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 2911053;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 2562214;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 3013283;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 128793;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 2654153;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-02'
  AND pi.content_id = 3030930;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 2007416;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 759595;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 2837242;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 128556;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 127202;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 130872;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 778296;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 2708338;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 2858445;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 130853;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 2791523;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 2851930;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 2738675;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 126473;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-03'
  AND pi.content_id = 2759120;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 3520495;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 2798703;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 2851320;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 2758837;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 129071;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 4058180;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 635701;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 664154;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 2751843;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 572960;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 128777;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 129455;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 2863597;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-04'
  AND pi.content_id = 126454;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-05'
  AND pi.content_id = 142976;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-05'
  AND pi.content_id = 3061676;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-05'
  AND pi.content_id = 1928421;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-05'
  AND pi.content_id = 2759096;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-05'
  AND pi.content_id = 1064572;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-05'
  AND pi.content_id = 2606214;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-05'
  AND pi.content_id = 1876813;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-05'
  AND pi.content_id = 2723689;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-05'
  AND pi.content_id = 127635;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-05'
  AND pi.content_id = 2714826;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-05'
  AND pi.content_id = 2759036;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-05'
  AND pi.content_id = 2910930;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-05'
  AND pi.content_id = 126448;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 2411625;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 228853;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 2738692;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 4073368;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 2861702;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'shopping'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 2765319;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 3056205;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 2788882;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 130308;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 126463;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 317558;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 129401;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 2863597;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-06'
  AND pi.content_id = 130461;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 984611;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 126444;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 2752772;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 2854041;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 2704703;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 2789652;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 665594;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 2503694;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 820822;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 127490;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 2660802;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 2562239;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 2840903;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-07'
  AND pi.content_id = 2713585;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 3079902;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 2765233;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 2752772;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 2854041;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 2986689;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 126444;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 2847726;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 2714241;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 2861349;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 2765234;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 2738712;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 2479639;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 2871863;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-08'
  AND pi.content_id = 2740014;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-09'
  AND pi.content_id = 2623827;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-09'
  AND pi.content_id = 741109;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-09'
  AND pi.content_id = 2756100;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-09'
  AND pi.content_id = 131784;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-09'
  AND pi.content_id = 126469;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-09'
  AND pi.content_id = 1146121;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-09'
  AND pi.content_id = 1933217;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-09'
  AND pi.content_id = 1876994;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-09'
  AND pi.content_id = 2905045;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-09'
  AND pi.content_id = 2553685;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-09'
  AND pi.content_id = 2836976;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-09'
  AND pi.content_id = 2738665;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-09'
  AND pi.content_id = 2714306;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 3076392;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 2638440;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 130723;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 3553902;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 664154;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 126465;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 2778809;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 126447;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 2717330;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 2767628;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 2798703;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 3559736;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 2847916;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 131589;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D3-10'
  AND pi.content_id = 2714222;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 2561932;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 2738692;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 4073368;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 2778044;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 2894522;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 127514;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 129699;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 2606298;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 2837142;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 130512;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 128555;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 2783376;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 228854;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 2715650;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 126457;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 127861;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 2940981;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 404151;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-01'
  AND pi.content_id = 126443;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 139008;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 3063420;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'shopping'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 1013246;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 2939004;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 1069144;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 126435;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 2564158;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 1984236;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 127813;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 1973369;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 2704353;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 2759849;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 2792565;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 127046;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 2851686;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 3056829;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-02'
  AND pi.content_id = 129400;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 935073;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 2837222;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 2726291;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 1329201;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 126472;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 1798082;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 2845383;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 2819599;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 2908846;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 127479;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 1672315;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 1909258;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 2704412;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 637398;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 2851874;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 128050;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 3083715;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-03'
  AND pi.content_id = 3038062;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 3076484;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 130494;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 2359168;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 127048;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 879234;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 1620997;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 404151;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 126440;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 2753082;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 1911160;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 2606690;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 129405;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 2359165;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 2781401;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 129617;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 2946628;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 2809900;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 1556005;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-04'
  AND pi.content_id = 572973;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2561932;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 3553902;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2763826;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 128794;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2767629;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 130474;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2663244;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 741109;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2606211;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2783376;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2852538;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 3013283;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2406460;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2845370;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 596964;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2789652;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2948051;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2809900;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2713583;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-05'
  AND pi.content_id = 2765268;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 2561880;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 126446;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 126672;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 2843921;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 2858467;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 2723542;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 1964507;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 3037977;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 3112043;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 2606209;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 2660763;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 129276;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 664982;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 129767;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 2742373;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 2809900;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 597562;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-06'
  AND pi.content_id = 2740130;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 397643;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 2048059;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 126447;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 664154;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 126465;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 2414827;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 3056151;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 2853604;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 126474;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 1621077;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 130857;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 2864287;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 2023328;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 2774821;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 2847852;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 131949;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 3037623;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-07'
  AND pi.content_id = 2779449;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 935073;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 127514;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'shopping'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 2931257;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 2837242;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 2765293;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 759595;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 3080405;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 3097805;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 2851686;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 3097814;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 1925362;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 228853;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 2794971;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 2931932;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 2759624;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 2633955;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 3057021;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 2833409;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-08'
  AND pi.content_id = 2789378;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 3515241;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 3026604;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 2806043;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 590415;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 2894407;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 3530411;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 130682;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 1945578;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 2562475;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 2738724;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 128050;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 2759091;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 2759120;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 126473;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 2791523;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 2767778;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 2359168;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 127283;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-09'
  AND pi.content_id = 2606690;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 2926949;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 3026604;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 2765280;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 3553979;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 2894407;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 1220821;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 3329719;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 2840903;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 2751836;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 2707930;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 3505052;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 819583;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 2858485;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 127050;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 3559559;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 128665;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 664982;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D4-10'
  AND pi.content_id = 127049;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 2621853;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 2606214;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 2765209;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 3410648;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 1945208;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 572968;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 131949;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 2847916;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 131589;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 2930935;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 2780263;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 127870;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 3110802;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 2781401;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 1918417;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 2850090;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 129617;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 126469;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 1861656;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 2861349;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-01'
  AND pi.content_id = 2742344;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 2948165;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 128794;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 2861372;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 127857;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 572960;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 577461;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 126472;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 2902758;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 2779449;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 636266;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 2853604;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 2746268;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 1672315;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 1544730;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 2759603;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 2847703;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 1898484;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 2714222;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 2836910;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 2877950;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-02'
  AND pi.content_id = 2724387;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2007416;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 3056829;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2851686;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2498717;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 1918639;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2713585;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2845383;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2606298;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2714241;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2986689;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2789652;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2674014;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 404216;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 591866;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 3037977;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2759061;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2751854;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2765234;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 1945768;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 3030930;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 2829949;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-03'
  AND pi.content_id = 131784;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 3031466;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 1620936;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 1019521;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 129276;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 127052;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 309943;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 127861;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 2756099;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 2858467;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 2661407;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 2946628;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 2809900;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 2713583;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 129699;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 2753082;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 2847823;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 2663244;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 1798082;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 2792565;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 3038062;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 1828395;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-04'
  AND pi.content_id = 2738665;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 3076491;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 1928421;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 2778905;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 2862097;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 2837222;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 130461;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 3386123;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 1069322;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 2806871;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 2738692;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 635701;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 3559736;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 664154;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 126465;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 3553902;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 127813;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 126447;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 2877751;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 2717330;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 2564158;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 1984236;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 2798703;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 3317905;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-05'
  AND pi.content_id = 2791473;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 397643;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 3559716;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 2783385;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 2717330;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 2048059;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 2023328;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 2864287;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 130857;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 1621077;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 3030949;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 128345;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 2828666;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 130474;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 3013283;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 2715648;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 404180;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 126443;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 2660763;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 2891397;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 2836814;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-06'
  AND pi.content_id = 2723689;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 139008;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 1329201;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 2723555;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 2861378;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 3071816;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 1925362;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 228853;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 2794971;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 2931932;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 3063420;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 2763726;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 2759603;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 128049;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 126474;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 3056151;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 1937744;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 2704435;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 2864287;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 128796;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 2789378;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 2798046;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 126463;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 2767704;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-07'
  AND pi.content_id = 3080144;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 2007416;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 2763739;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 1984253;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 3071841;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 2731801;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 2710264;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 3015718;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 2843815;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 2740123;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 3031021;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 2785301;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 2742373;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 2948051;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 987913;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 2877734;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 2707930;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 126440;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'activity'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 637398;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 3112043;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 2847726;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 2854015;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-08'
  AND pi.content_id = 126473;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2007416;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2714306;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2876836;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 126460;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2852695;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 129894;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2834656;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2833763;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2861702;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 128641;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 127635;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2908846;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2845383;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 1556005;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2986689;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2843982;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2778890;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 130363;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2406460;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2852538;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 596964;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2753082;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2863701;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-09'
  AND pi.content_id = 2738726;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 2948165;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 2704353;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 2839916;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 1755806;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 127744;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'shopping'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 2737330;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 2522221;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 2850014;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 2660122;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 3080405;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 1769266;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 3026711;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 3030422;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 1866904;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 2606611;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 2778809;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 2877751;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 2791473;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 577461;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 1069144;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'food'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 2805320;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = ''
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 3056135;

UPDATE package_items AS pi
JOIN travel_packages AS tp ON tp.id = pi.package_db_id
SET pi.tags = 'shopping'
WHERE tp.package_id = 'VIRTUAL-JEJU-D5-10'
  AND pi.content_id = 2860687;

COMMIT;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 1, 'ALTER TABLE travel_packages DROP COLUMN match_profile', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'match_profile'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 1, 'ALTER TABLE travel_packages DROP COLUMN companion_solo', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'companion_solo'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 1, 'ALTER TABLE travel_packages DROP COLUMN companion_friend', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'companion_friend'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 1, 'ALTER TABLE travel_packages DROP COLUMN companion_couple', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'companion_couple'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 1, 'ALTER TABLE travel_packages DROP COLUMN companion_family', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'companion_family'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 1, 'ALTER TABLE travel_packages DROP COLUMN tag_nature', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'tag_nature'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 1, 'ALTER TABLE travel_packages DROP COLUMN tag_culture', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'tag_culture'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 1, 'ALTER TABLE travel_packages DROP COLUMN tag_festival', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'tag_festival'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 1, 'ALTER TABLE travel_packages DROP COLUMN tag_experience', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'tag_experience'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 1, 'ALTER TABLE travel_packages DROP COLUMN tag_food', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'tag_food'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 1, 'ALTER TABLE travel_packages DROP COLUMN tag_cafe', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'tag_cafe'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 1, 'ALTER TABLE travel_packages DROP COLUMN tag_activity', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'tag_activity'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SET @package_ddl = (
    SELECT IF(COUNT(*) = 1, 'ALTER TABLE travel_packages DROP COLUMN tag_shopping', 'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'travel_packages'
      AND COLUMN_NAME = 'tag_shopping'
);
PREPARE package_stmt FROM @package_ddl;
EXECUTE package_stmt;
DEALLOCATE PREPARE package_stmt;

SELECT package_id, companion, tags
FROM travel_packages
WHERE is_active = TRUE
ORDER BY id;

SELECT id, package_db_id, content_id, tags
FROM package_items
ORDER BY id;
