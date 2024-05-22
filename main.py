import datetime
import logging

import ping3 as p
import urllib3
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists

import uvicorn
import asyncio

import db

# logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

global_time = 60


def ping(ip):
    return p.ping(ip)


def html(url, username=None, password=None):
    # Sends head req if 401 attempts auth
    res = urllib3.request('HEAD', url)
    if res.status == 401 and username and password:
        head = urllib3.make_headers(basic_auth=username + ':' + password)
        http = urllib3.PoolManager()
        req = http.request('GET', url, headers=head)
        return req.status == 200
    else:
        return res.status == 200


# Checks an individual db
def try_connect(dbtype, username, password, address, port):
    # a = db.get_db(db)
    # url = sqlalchemy.URL.create(a.dbtype, a.username, a.password, a.address, a.port)
    if dbtype == 'postgresql':
        url = sqlalchemy.URL.create(dbtype, username, password, address, port, 'postgres')
    else:
        url = sqlalchemy.URL.create(dbtype, username, password, address, port)

    # TODO support diff dbs
    try:
        # create_engine(url)
        if database_exists(url):
            return create_engine(url, pool_pre_ping=True)
    except:
        return False


pass


# The function that runs the FastAPI server
async def server():
    # This allows the server to be run async
    conf = uvicorn.Config("api:app",
                          host='0.0.0.0',
                          port=8000,
                          reload=True)
    serv = uvicorn.Server(conf)
    while True:
        await serv.serve()


# Functions that check every connection....
# They are a bit slow though

async def check_ips():
    # This pings an ip every minute and if it's down records time
    # later pings get last status and if still down - ignore
    # if up - record time, vice versa if down
    while True:
        all_ips = db.get_all_ips_status_time()
        for ip in all_ips:
            log.info('Checking ' + str(ip[0]))
            if ping(ip[0]):
                log.info(str(ip[0]) + ' is up')
                if ip[3] == 'down' or ip[3] == 'unknown':
                    db.add_ip_status(ip[1], datetime.datetime.now(), 'up')
            else:
                log.info(str(ip[0]) + ' is down')
                if ip[3] == 'up' or ip[3] == 'unknown':
                    db.add_ip_status(ip[1], datetime.datetime.now(), 'down')
        await asyncio.sleep(global_time)


async def check_urls():
    # I dont even know
    while True:
        all_urls = db.get_all_urls_status_time()
        for url in all_urls:
            log.info('Checking ' + str(url[0]))
            if html(url[0], url[4], url[5]):
                log.info(str(url[0]) + ' is up')
                if url[3] == 'down' or url[3] == 'unknown':
                    db.add_url_status(url[1], datetime.datetime.now(), 'up')
            else:
                log.info(str(url[0]) + ' is down')
                if url[3] == 'up' or url[3] == 'unknown':
                    db.add_url_status(url[1], datetime.datetime.now(), 'down')

        await asyncio.sleep(global_time)


async def check_dbs():
    while True:
        all_dbs = db.get_all_dbs_status_time()
        for db1 in all_dbs:
            log.info(f'Checking {db1[0]}/{db1[6]}({db1[7]})')
            if try_connect(dbtype=db1[7],
                           username=db1[4],
                           password=db1[5],
                           address=db1[0],
                           port=db1[6]):
                log.info(str() + ' is up')
                if db1[3] == 'down' or db1[3] == 'unknown':
                    db.add_db_status(db1[1], datetime.datetime.now(), 'up')
            else:
                log.info(str() + ' is down')
                if db1[3] == 'down' or db1[3] == 'unknown':
                    db.add_db_status(db1[1], datetime.datetime.now(), 'down')
        await asyncio.sleep(global_time)


async def main():
    t1 = asyncio.create_task(server())
    t2 = asyncio.create_task(check_ips())
    t3 = asyncio.create_task(check_urls())
    t4 = asyncio.create_task(check_dbs())
    await t1
    await t2
    await t3
    await t4
    # pass


if __name__ == '__main__':
    # front = m.Process(target=server())
    # back = m.Process(target=main())
    # front.start()
    # back.start()
    # front.join()
    # back.join()
    # print(try_connect('postgresql', 'postgres',
    #                   '1234', 'localhost', '5432'))
    # print(html('https://authenticationtest.com/HTTPAuth/'))
    asyncio.run(main())
