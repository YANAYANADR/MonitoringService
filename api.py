import asyncio
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
                                         'urls': await db.Database.get_all_urls(),
                                         'url_history': await db.Database.sorted_history(1),
                                         'dbs': await db.Database.get_all_dbs(),
                                         'db_history': await db.Database.sorted_history(2),
                                     })


@app.get('/add', response_class=HTMLResponse)
async def add(request: Request):
    return template.TemplateResponse(request=request, name='add.html')


@app.get('/table', response_class=HTMLResponse)
async def table(request: Request):
    return template.TemplateResponse(request=request, name='table.html')


@app.get('/tdata', response_class=JSONResponse)
async def tdata():
    data_list=[]
    data = await db.Database.get_all_ips()
    if data:
        # data_list.append(await parseData(0, data))
        data_list+=await parseData(0, data)
    data = await db.Database.get_all_urls()
    if data:
        data_list+=await parseData(1, data)
    data = await db.Database.get_all_dbs()
    if data:
        data_list+=await parseData(2, data)

    # log.info(data_list)
    return data_list


async def parseData(type, data):
    # match type and add index
    add_id = 0
    match type:
        case 0:
            tp = 'id'
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

        out.append(o)
    return out


@app.post('/add')
async def get_target(type: int = Form(), address: str = Form(),
                     username: Optional[str] = Form(None),
                     password: Optional[str] = Form(None),
                     dbtype: Optional[str] = Form(None),
                     port: Optional[str] = Form(None)):
    match (type):
        case 0:
            await db.Database.insert_ip(address)
        case 1:
            await db.Database.insert_url(address, username, password)
        case 2:
            await db.Database.insert_db(address, username, password, dbtype, port)
    return RedirectResponse(url='/add', status_code=status.HTTP_303_SEE_OTHER)


@app.post('/table')
async def form(id: int = Form(), tp: str = Form()):
    await delById(tp, id)
    log.info('Удаляем '+str(id))
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
        # await asyncio.sleep(3)
        # await websocket.send_json({
        #     'id': 1,
        #     'group': str(1),
        #     'shape': "icon",
        #     'icon': {
        #         'color': "red",
        #     },
        # })
        await asyncio.sleep(int(os.environ['WAIT_TIME']))
