import asyncio
import json
import os
from typing import Optional

import starlette.status as status
from fastapi import (FastAPI, Request, Form,
                     WebSocket)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates as j

import db

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
template = j(directory="templates")


@app.get('/')
def redirect(request: Request):
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


@app.websocket('/ws')
async def ws(websocket: WebSocket):
    await websocket.accept()
    data= await db.Database.first_load_icons()
    await websocket.send_json(data)
    while True:
        data =await db.Database.form_jsons(0)
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
