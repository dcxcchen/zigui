#!/usr/bin/python3
# _*_ coding: UTF-8 _*_

import os
import sys
import sqlite3
from tinytag import TinyTag
import time
import traceback
from flask import Flask, render_template, Response, make_response
import logging
from concurrent.futures import ThreadPoolExecutor
import codecs

is_updating_media_library = False
media_lib_db = 'media_library.db'
media_lib_template = {'FILE_PATH': 'TEXT NOT NULL',
        'ALBUM': 'TEXT',
        'ALBUM_ARTIST': 'TEXT',
        'ARTIST': 'TEXT',
        'BITRATE': 'INT',
        'COMMENT': 'TEXT',
        'COMPOSER': 'TEXT',
        'DISC': 'INT',
        'DISC_TOTAL': 'INT',
        'DURATION': 'INT',
        'FILE_SIZE': 'INT',
        'GENRE': 'TEXT',
        'SAMPLE_RATE': 'INT',
        'TITLE': 'TEXT',
        'TRACK': 'INT',
        'TRACK_TOTAL': 'INT',
        'YEAR': 'TEXT'}

def tag_2_db_dict(tag):
    d = {'ALBUM': tag.album,
        'ALBUM_ARTIST': tag.albumartist,
        'ARTIST': tag.artist,
        'BITRATE': tag.bitrate,
        'COMMENT': tag.comment,
        'COMPOSER': tag.composer,
        'DISC': tag.disc,
        'DISC_TOTAL': tag.disc_total,
        'DURATION': tag.duration,
        'FILE_SIZE': tag.filesize,
        'GENRE': tag.genre,
        'SAMPLE_RATE': tag.samplerate,
        'TITLE': tag.title,
        'TRACK': tag.track,
        'TRACK_TOTAL': tag.track_total,
        'YEAR': tag.year}
    return d

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# no check in this method
def insert_to_media_db(record):
    try:
        conn = sqlite3.connect(media_lib_db)
        conn.row_factory = dict_factory

        utc = int(time.time())

        whole_cmd = 'INSERT INTO MUSIC ( UPDATE_TIME'
        value_cmd = 'VALUES (?'
        values = [utc]
        for key in media_lib_template:
            whole_cmd = whole_cmd + ', ' + key
            value_cmd = value_cmd + ', ?'
            if key == 'FILE_PATH':
                values.append(repr(record[key])[1:-1])
            else:
                values.append(record[key])
        whole_cmd = whole_cmd + ')'
        value_cmd = value_cmd + ')'

        whole_cmd = whole_cmd + ' ' + value_cmd
        
        conn.execute(whole_cmd, values)
        conn.commit()
        conn.close()
    except Exception as e:
        logging.info (whole_cmd)
        logging.info (values)    
        logging.info('Failed to insert ', record, e)

# no check in this method
def update_media_db(index, record):
    try:
        conn = sqlite3.connect(media_lib_db)
        conn.row_factory = dict_factory

        utc = int(time.time())

        whole_cmd = 'UPDATE MUSIC SET UPDATE_TIME=?'
        values = [utc]
        for key in record:
            whole_cmd = whole_cmd + ','+key+'=?'
            if key == 'FILE_PATH':
                values.append(repr(record[key])[1:-1])
            else:
                values.append(record[key])
        whole_cmd = whole_cmd + ' where ID=' + str(index)

        conn.execute(whole_cmd, values)
        conn.commit()
        conn.close()
    except Exception as e:
        logging.info (whole_cmd)
        logging.info('Failed to update ', index, record, e)

def insert_or_update(file_path, tag):
    found = False
    old_record = None

    try:
        conn = sqlite3.connect(media_lib_db)
        conn.row_factory = dict_factory

        utc = int(time.time())
        whole_cmd = "SELECT * FROM MUSIC WHERE FILE_PATH IS ?"
        cursor = conn.execute(whole_cmd, [repr(file_path)[1:-1]])
        records = cursor.fetchall()
        conn.close()
        for r in records:
            #logging.info(r)
            # only use the first one, others will be removed if not updated
            if r['ID']:
                found = True
                old_record = r
    except Exception as e:
        tb = traceback.format_exc()
        logging.info('Failed to query ', repr(file_path)[1:-1], e, tb)

    new_record = tag_2_db_dict(tag)
    new_record['FILE_PATH'] = file_path

    if found:
        for key in old_record:
            if key in new_record and new_record[key] == old_record[key]:
                new_record.pop(key)
        update_media_db(old_record['ID'], new_record)
    else:
        insert_to_media_db(new_record)

def update_media_library_async():
    logging.info ('start update_media_library_async')

    is_updating_media_library = True
    timestampe_of_starting_update = int(time.time())
    traces = os.walk(r"music")
    for path,dir_list,file_list in traces:
        for file_name in file_list:
            file_path = os.path.join(path, file_name)
            try:
                tag = TinyTag.get(file_path)
            except Exception as e:
                logging.info (repr(file_path)[1:-1])
                logging.info (e)
            else:
                insert_or_update(file_path, tag)

    try:
        conn = sqlite3.connect(media_lib_db)
        conn.row_factory = dict_factory

        whole_cmd = "DELETE FROM MUSIC WHERE UPDATE_TIME < " + str(timestampe_of_starting_update)
        conn.execute(whole_cmd)
        conn.commit()
        conn.close()
    except Exception as e:
        tb = traceback.format_exc()
        logging.info('Failed to delete ', e, tb)

    is_updating_media_library = False
    logging.info ('finish update_media_library_async')


def file_path_2_mimetype(file_path):
    file, ext = os.path.splitext(file_path)
    if ext == '.aac':
        return 'audio/aac'
    elif ext == '.flac':
        return 'audio/flac'
    elif ext == '.mp3':
        return 'audio/mp3'
    elif ext == '.m4a':
        return 'audio/mp4'
    elif ext == '.ogg':
        return 'audio/ogg'
    elif ext == '.wav':
        return 'audio/wav'
    elif ext == '.webm':
        return 'audio/webm'
    else:
        return 'audio'

app = Flask(__name__)
executor = ThreadPoolExecutor(2)

@app.route('/api/library/update', methods=['POST'])
def api_library_update():
    executor.submit(update_media_library_async)
    return 'started.'

@app.route("/api/files/<index>", methods=['GET'])
def api_files(index):
    conn = sqlite3.connect(media_lib_db)
    conn.row_factory = dict_factory

    whole_cmd = "SELECT * FROM MUSIC WHERE ID IS ?"
    cursor = conn.execute(whole_cmd, [index])
    records = cursor.fetchall()
    conn.close()
    
    if len(records) == 1:
        file_path = codecs.getdecoder("unicode_escape")(records[0]['FILE_PATH'])[0]
        def generate():
            with open(file_path, "rb") as file:
                data = file.read(1024)
                while data:
                    yield data
                    data = file.read(1024)
        return Response(generate(), mimetype=file_path_2_mimetype(file_path))
        
    return make_response('', 404)
    
@app.route('/')
def home():
    return render_template('home.html')

logging.basicConfig(format='%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s',
                    level=logging.DEBUG)

try:
    conn = sqlite3.connect(media_lib_db)
    whole_cmd = 'CREATE TABLE IF NOT EXISTS MUSIC (ID INTEGER PRIMARY KEY AUTOINCREMENT, UPDATE_TIME INT'
    for key in media_lib_template:
        whole_cmd = whole_cmd + ', ' + key + ' ' + media_lib_template[key]
    whole_cmd = whole_cmd + ');'
    conn.execute(whole_cmd)
    conn.commit()
    conn.close()
except Exception as e:
    logging.info(whole_cmd)
    logging.info ('create sqlite3 db failed', e)
    exit()

if __name__ == '__main__':
    app.run(debug=True, port=4040, host='0.0.0.0')
