import datetime
import logging
import os

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

log.error(os.environ['WAIT_TIME'])
global_time = int(os.environ['WAIT_TIME'])


# The function that runs the FastAPI server
async def server() -> None:
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

class Checks:
    @staticmethod
    def ping(ip: str) -> bool:
        try:
            return p.ping(ip)
        except:
            return False

    @staticmethod
    def html(url: str, username: str = None, password: str = None) -> bool:
        # Sends head req if 401 attempts auth
        try:
            res = urllib3.request('HEAD', url)
            if res.status == 401 and username and password:
                head = urllib3.make_headers(basic_auth=username + ':' + password)
                http = urllib3.PoolManager()
                req = http.request('GET', url, headers=head)
                return req.status == 200
            else:
                return res.status == 200
        except:
            return False

    # Checks an individual db
    # TODO add type hint
    @staticmethod
    def try_connect(dbtype: str, username: str, password: str,
                    address: str, port: int):
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

    @staticmethod
    async def check_ips() -> None:
        # This pings an ip every minute and if it's down records time
        # later pings get last status and if still down - ignore
        # if up - record time, vice versa if down
        while True:
            all_ips = await db.Database.get_all_ips_status_time()
            for ip in all_ips:
                log.info('Checking ' + str(ip.address))
                if Checks.ping(ip.address):
                    log.info(str(ip.address) + ' is up')
                    if ip.status == 'down' or ip.status == 'unknown':
                        await (db.Database
                               .add_ip_status(ip.ex_id, datetime.datetime.now(), 'up'))
                else:
                    log.info(str(ip.address) + ' is down')
                    if ip.status == 'up' or ip.status == 'unknown':
                        await (db.Database
                               .add_ip_status(ip.ex_id, datetime.datetime.now(), 'down'))
            await asyncio.sleep(global_time)

    @staticmethod
    async def check_urls() -> None:
        # I dont even know
        while True:
            all_urls = await db.Database.get_all_urls_status_time()
            for url in all_urls:
                log.info('Checking ' + str(url.address))
                if Checks.html(url.address, url.username, url.password):
                    log.info(str(url.address) + ' is up')
                    if url.status == 'down' or url.status == 'unknown':
                        await (db.Database
                               .add_url_status(url.ex_id, datetime.datetime.now(), 'up'))
                else:
                    log.info(str(url.address) + ' is down')
                    if url.status == 'up' or url.status == 'unknown':
                        await (db.Database
                               .add_url_status(url.ex_id, datetime.datetime.now(), 'down'))

            await asyncio.sleep(global_time)

    @staticmethod
    async def check_dbs() -> None:
        while True:
            all_dbs = await db.Database.get_all_dbs_status_time()
            for db1 in all_dbs:
                log.info(f'Checking {db1.address}/{db1.port}({db1.dbtype})')
                if Checks.try_connect(dbtype=db1.dbtype,
                                      username=db1.username,
                                      password=db1.password,
                                      address=db1.address,
                                      port=db1.port):
                    log.info(str(db1.address) + ' is up')
                    if db1.status == 'down' or db1.status == 'unknown':
                        await (db.Database.
                               add_db_status(db1.ex_id, datetime.datetime.now(), 'up'))
                else:
                    log.info(str(db1.address) + ' is down')
                    if db1.status == 'down' or db1.status == 'unknown':
                        await (db.Database.
                               add_db_status(db1.ex_id, datetime.datetime.now(), 'down'))
            await asyncio.sleep(global_time)


async def main() -> None:
    t1 = asyncio.create_task(server())
    t2 = asyncio.create_task(Checks.check_ips())
    t3 = asyncio.create_task(Checks.check_urls())
    t4 = asyncio.create_task(Checks.check_dbs())
    await t1
    await t2
    await t3
    await t4
    # pass


if __name__ == '__main__':
    # print(try_connect('postgresql', 'postgres',
    #                   '1234', 'localhost', '5432'))
    # print(html('https://authenticationtest.com/HTTPAuth/'))
    asyncio.run(main())
