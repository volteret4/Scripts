#!/usr/bin/env bash
#
# Script Name: newpipe-links.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO:     ALL
# Notes:    WIP
#
#



from io import StringIO
from sqlite3 import Error
import csv
import sqlite3
import sys


def create_connection(db_file):
    """ create a database connection to the SQLite database
        specified by the db_file
    :param db_file: database file
    :return: Connection object or None
    """
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)
 
    return None


def get_rows(db_file):
    conn = create_connection(db_file)

    cmds = """
    select 
            url,
            title,
            stream_type,
            duration,
            uploader,
            streams.thumbnail_Url,
            playlists.name as playlist_name,
            playlists.thumbnail_url as playlist_thumbnail_url
    from streams 
    inner join playlist_stream_join on playlist_stream_join.stream_id = streams.uid
    inner join playlists on playlists.uid == playlist_stream_join.playlist_id
    """
    cur = conn.cursor()
    cur.execute(cmds)
    rows = cur.fetchall()
    return rows


def main(db_file):
    rows = get_rows(db_file)
    f = StringIO()
    wr = csv.writer(f)
    wr.writerow([
        'url', 'title', 'stream_type', 'duration', 'uploader',
        'stream_thumbnail_url', 'playlist_name', 'playlist_thumbnail_url'])
    for row in rows:
        wr.writerow(row)
    print(f.getvalue())


if __name__ == '__main__':
    main(sys.argv[1])