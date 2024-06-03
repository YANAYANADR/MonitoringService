import asyncio
import datetime
import json
import os
from typing import Optional
import logging

import starlette.status as status
from fastapi import (FastAPI, Request, Form,
                     WebSocket)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates as j

import db

# logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
template = j(directory="templates")


@app.get('/')
def redirect():
    return RedirectResponse(url='/now', status_code=status.HTTP_303_SEE_OTHER)


@app.get('/now', response_class=HTMLResponse)
def main_page(request: Request):
    return template.TemplateResponse(request=request, name='index.html')


@app.get('/history', response_class=HTMLResponse)
async def history(request: Request):
    return template.TemplateResponse(request=request, name='history.html',
                                     context={
                                         'ips': await db.Database.get_all_ips(),
                                         'ip_history': await db.Database.sorted_history(0),
                                         'last_ip':await db.Database.get_last_ip_id(),
                                         'urls': await db.Database.get_all_urls(),
                                         'url_history': await db.Database.sorted_history(1),
                                         'last_url': await db.Database.get_last_url_id(),
                                         'dbs': await db.Database.get_all_dbs(),
                                         'db_history': await db.Database.sorted_history(2),
                                     })


@app.get('/add', response_class=HTMLResponse)
async def add(request: Request):
    return template.TemplateResponse(request=request, name='add.html', context={
        'groups': await db.Database.get_group_name_all(),
    })


@app.get('/table', response_class=HTMLResponse)
async def table(request: Request):
    return template.TemplateResponse(request=request, name='table.html')


@app.get('/tdata', response_class=JSONResponse)
async def tdata():
    data_list = []
    data = await db.Database.get_all_ips()
    if data:
        data_list += await parse_data(0, data)
    data = await db.Database.get_all_urls()
    if data:
        data_list += await parse_data(1, data)
    data = await db.Database.get_all_dbs()
    if data:
        data_list += await parse_data(2, data)

    # log.info(data_list)
    return data_list


async def parse_data(type, data):
    # match type and add index
    add_id = 0
    match type:
        case 0:
            tp = 'ip'
        case 1:
            tp = 'url'
            add_id = await db.Database.get_last_ip_id()

        case 2:
            tp = 'db'
            add_id = (await db.Database.get_last_ip_id() +
                      await db.Database.get_last_url_id())
        case _:
            raise ValueError('Индекс типа неверрен')

    # main code
    out = []
    for d in data:
        o = d._asdict()
        o['type'] = tp
        o['id'] = int(o['id']) + add_id
        # Clicks on delete cell don't work otherwise
        o['act'] = '❌'

        out.append(o)
    # print(out)
    return out


@app.post('/add')
async def get_target(type: int = Form(), address: str = Form(),
                     username: Optional[str] = Form(None),
                     password: Optional[str] = Form(None),
                     dbtype: Optional[str] = Form(None),
                     port: Optional[str] = Form(None),
                     group: str = Form()):
    group_id = await db.Database.insert_group(group)
    match (type):
        case 0:
            await db.Database.insert_ip(address, group_id)
        case 1:
            await db.Database.insert_url(address, group_id,
                                         username, password)
        case 2:
            await db.Database.insert_db(address, username, password, dbtype, port, group_id)
    return RedirectResponse(url='/add', status_code=status.HTTP_303_SEE_OTHER)


@app.post('/table')
async def form(id: int = Form(), tp: str = Form()):
    await delById(tp, id)
    log.info('Удаляем ' + str(id))
    return True


@app.post('/history')
async def get_reason(id: int = Form(), start=Form(), reason: str = Form()):
    log.info(start)
    start = datetime.datetime.strptime(start, '%Y-%m-%dT%H:%M:%S.%fZ')
    # This checks if id is bigger than the biggest id of ips and urls and if so,
    # Sets type
    last_id = await db.Database.get_last_ip_id()
    last_url = await db.Database.get_last_url_id()
    log.info(last_url)
    log.info(id)
    if id <= last_id:
        await (db.Database.
               reason_to_condition_ip(await db.Database.insert_reason(reason),
                                      await db.Database.get_cond_ip(id, start)))
    elif id <= last_url + last_id:
        id = id - last_id
        await (db.Database.
               reason_to_condition_url(await db.Database.insert_reason(reason),
                                       await db.Database.get_cond_url(id, start)))
    else:
        id = id - last_id - last_url
        await (db.Database.
               reason_to_condition_db(await db.Database.insert_reason(reason),
                                      await db.Database.get_cond_db(id, start)))

    return True


async def delById(type, id):
    match type:
        case 'id':
            await db.Database.delete_ip(id)
        case 'url':
            id = id - await db.Database.get_last_ip_id()
            await db.Database.delete_url(id)

        case 'db':
            id = id - (await db.Database.get_last_ip_id() +
                       await db.Database.get_last_url_id())
            await db.Database.delete_db(id)
        case _:
            raise ValueError('Индекс типа неверрен')


@app.websocket('/ws')
async def ws(websocket: WebSocket):
    await websocket.accept()
    data = await db.Database.first_load_icons()
    await websocket.send_json(data)
    while True:
        data = await db.Database.form_jsons(0)
        await websocket.send_json(data)
        data = await db.Database.form_jsons(1)
        await websocket.send_json(data)
        data = await db.Database.form_jsons(2)
        await websocket.send_json(data)
        await asyncio.sleep(int(os.environ['WAIT_TIME']))
        # await asyncio.sleep(60)
