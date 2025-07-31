
Estructura de la tabla: users
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'username', 'TEXT', 1, None, 0)
(2, 'chat_id', 'INTEGER', 1, None, 0)
(3, 'notification_time', 'TEXT', 0, "'09:00'", 0)
(4, 'notification_enabled', 'BOOLEAN', 0, '1', 0)
(5, 'country_filter', 'TEXT', 0, "'ES'", 0)
(6, 'service_ticketmaster', 'BOOLEAN', 0, '1', 0)
(7, 'service_spotify', 'BOOLEAN', 0, '1', 0)
(8, 'service_setlistfm', 'BOOLEAN', 0, '1', 0)
(9, 'created_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)
(10, 'last_activity', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)

Estructura de la tabla: sqlite_sequence
(0, 'name', '', 0, None, 0)
(1, 'seq', '', 0, None, 0)

Estructura de la tabla: artists
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'name', 'TEXT', 1, None, 0)
(2, 'mbid', 'TEXT', 0, None, 0)
(3, 'country', 'TEXT', 0, None, 0)
(4, 'formed_year', 'INTEGER', 0, None, 0)
(5, 'ended_year', 'INTEGER', 0, None, 0)
(6, 'total_works', 'INTEGER', 0, None, 0)
(7, 'musicbrainz_url', 'TEXT', 0, None, 0)
(8, 'artist_type', 'TEXT', 0, None, 0)
(9, 'disambiguation', 'TEXT', 0, None, 0)
(10, 'created_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)
(11, 'spotify_url', 'TEXT', 0, None, 0)

Estructura de la tabla: user_followed_artists
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'user_id', 'INTEGER', 1, None, 0)
(2, 'artist_id', 'INTEGER', 1, None, 0)
(3, 'followed_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)

Estructura de la tabla: pending_artist_selections
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'chat_id', 'INTEGER', 1, None, 0)
(2, 'search_results', 'TEXT', 1, None, 0)
(3, 'original_query', 'TEXT', 1, None, 0)
(4, 'created_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)

Estructura de la tabla: concerts
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'artist_name', 'TEXT', 1, None, 0)
(2, 'concert_name', 'TEXT', 1, None, 0)
(3, 'venue', 'TEXT', 0, None, 0)
(4, 'city', 'TEXT', 0, None, 0)
(5, 'country', 'TEXT', 0, None, 0)
(6, 'date', 'TEXT', 0, None, 0)
(7, 'time', 'TEXT', 0, None, 0)
(8, 'url', 'TEXT', 0, None, 0)
(9, 'source', 'TEXT', 0, None, 0)
(10, 'concert_hash', 'TEXT', 0, None, 0)
(11, 'created_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)

Estructura de la tabla: notifications_sent
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'user_id', 'INTEGER', 1, None, 0)
(2, 'concert_id', 'INTEGER', 1, None, 0)
(3, 'notification_date', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)

Estructura de la tabla: user_search_cache
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'user_id', 'INTEGER', 1, None, 0)
(2, 'search_type', 'TEXT', 1, None, 0)
(3, 'search_data', 'TEXT', 1, None, 0)
(4, 'created_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)

Estructura de la tabla: countries
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'code', 'TEXT', 1, None, 0)
(2, 'name', 'TEXT', 1, None, 0)
(3, 'phone_code', 'TEXT', 0, None, 0)
(4, 'currency', 'TEXT', 0, None, 0)
(5, 'created_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)
(6, 'updated_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)

Estructura de la tabla: cities
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'country_code', 'TEXT', 1, None, 0)
(2, 'state_code', 'TEXT', 0, None, 0)
(3, 'state_name', 'TEXT', 0, None, 0)
(4, 'name', 'TEXT', 1, None, 0)
(5, 'latitude', 'REAL', 0, None, 0)
(6, 'longitude', 'REAL', 0, None, 0)
(7, 'created_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)

Estructura de la tabla: user_countries
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'user_id', 'INTEGER', 1, None, 0)
(2, 'country_code', 'TEXT', 1, None, 0)
(3, 'added_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)

Estructura de la tabla: user_lastfm
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'user_id', 'INTEGER', 1, None, 0)
(2, 'lastfm_username', 'TEXT', 1, None, 0)
(3, 'lastfm_playcount', 'INTEGER', 0, '0', 0)
(4, 'lastfm_registered', 'TEXT', 0, "''", 0)
(5, 'sync_limit', 'INTEGER', 0, '20', 0)
(6, 'created_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)
(7, 'updated_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)

Estructura de la tabla: pending_lastfm_sync
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'user_id', 'INTEGER', 1, None, 0)
(2, 'period', 'TEXT', 1, None, 0)
(3, 'artists_data', 'TEXT', 1, None, 0)
(4, 'created_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)

Estructura de la tabla: user_spotify
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'user_id', 'INTEGER', 1, None, 0)
(2, 'spotify_username', 'TEXT', 1, None, 0)
(3, 'spotify_display_name', 'TEXT', 0, "''", 0)
(4, 'spotify_followers', 'INTEGER', 0, '0', 0)
(5, 'spotify_playlists', 'INTEGER', 0, '0', 0)
(6, 'artists_limit', 'INTEGER', 0, '20', 0)
(7, 'created_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)
(8, 'updated_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)

Estructura de la tabla: pending_spotify_artists
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'user_id', 'INTEGER', 1, None, 0)
(2, 'artists_data', 'TEXT', 1, None, 0)
(3, 'created_at', 'TIMESTAMP', 0, 'CURRENT_TIMESTAMP', 0)
