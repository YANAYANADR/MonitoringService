import asyncio
import datetime
import functools
import logging
import os
from typing import Optional

import sqlalchemy
from sqlalchemy import (String, DateTime,
                        text, select, func, delete, update, join)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import (DeclarativeBase, Mapped,
                            mapped_column)

# logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

try:
    u = sqlalchemy.URL.create('postgresql+asyncpg', os.environ['POSTGRES_USER'],
                              os.environ['POSTGRES_PASSWORD'], 'db', 5432, os.environ['POSTGRES_DB'])
    eng = create_async_engine(u)
    # eng = create_async_engine("postgresql+asyncpg://postgres:1234@localhost:5432/monitoring")
except:
    log.error('Не удалось подключится к базе')
    quit()


# Db classes
class Base(DeclarativeBase):
    pass


class ConditionIp(Base):
    __tablename__ = 'condition_ip'
    id: Mapped[int] = mapped_column(primary_key=True)
    ex_id: Mapped[int] = mapped_column()
    time: Mapped[datetime.datetime] = mapped_column(DateTime())
    status: Mapped[str] = mapped_column(String())
    reason_id: Mapped[Optional[int]] = mapped_column()


class ConditionUrl(Base):
    __tablename__ = 'condition_url'
    id: Mapped[int] = mapped_column(primary_key=True)
    ex_id: Mapped[int] = mapped_column()
    time: Mapped[datetime.datetime] = mapped_column(DateTime())
    status: Mapped[str] = mapped_column(String())
    reason_id: Mapped[Optional[int]] = mapped_column()


class ConditionDb(Base):
    __tablename__ = 'condition_db'
    id: Mapped[int] = mapped_column(primary_key=True)
    ex_id: Mapped[int] = mapped_column()
    time: Mapped[datetime.datetime] = mapped_column(DateTime())
    status: Mapped[str] = mapped_column(String())
    reason_id: Mapped[Optional[int]] = mapped_column()


class Ips(Base):
    __tablename__ = 'ips'
    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String())
    group_id: Mapped[int] = mapped_column()


class Urls(Base):
    __tablename__ = 'urls'
    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String())
    # optional auth
    username: Mapped[Optional[str]] = mapped_column(String())
    password: Mapped[Optional[str]] = mapped_column(String())
    group_id: Mapped[int] = mapped_column()


class Dbs(Base):
    __tablename__ = 'dbs'
    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String())
    dbtype: Mapped[str] = mapped_column(String())
    port: Mapped[int] = mapped_column()
    username: Mapped[str] = mapped_column(String())
    password: Mapped[str] = mapped_column(String())
    group_id: Mapped[int] = mapped_column()


class Groups(Base):
    __tablename__ = 'groups'
    id: Mapped[int] = mapped_column(primary_key=True)
    group_name: Mapped[str] = mapped_column(String())


class Reasons(Base):
    __tablename__ = 'reasons'
    id: Mapped[int] = mapped_column(primary_key=True)
    reason: Mapped[str] = mapped_column(String())
    pass


# TODO this is slow but idk what else to do
# Decorator
def create_session():
    def create_session2(f):
        @functools.wraps(f)
        async def _create_session(*args):
            async with eng.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with async_sessionmaker(eng,
                                          expire_on_commit=False)() as s:
                async with s.begin():
                    res = await f(s, *args)
                    await s.flush()
                    await s.commit()
                    await eng.dispose()
                    return res

        return _create_session

    return create_session2


class History:
    def __init__(self, id=0, start=0, end=0, reason=''):
        self.id = id
        self.start = start
        self.end = end
        self.reason = reason


# Methods
class Database:
    # Checks
    @staticmethod
    @create_session()
    async def ip_in_db(s: async_sessionmaker[AsyncSession](), address: str) -> bool:
        out = await s.execute(select(func.count(1))
                              .where(Ips.address == str(address)))
        return out.first()[0] > 0

    # Inserts

    @staticmethod
    @create_session()
    async def insert_ip(s: async_sessionmaker[AsyncSession](), address: str, group_id: int) -> None:
        if not await Database.ip_in_db(address):
            ip = Ips(address=address, group_id=group_id)
            s.add(ip)
            await s.flush()
            # adds unknown status
            await Database.add_ip_status(ip.id, datetime.datetime.now(), 'unknown')
        else:
            raise ValueError('Ip is already in database')

    @staticmethod
    @create_session()
    async def insert_url(s: async_sessionmaker[AsyncSession](),
                         address: str, group_id: int, username: Optional[str] = None,
                         password: Optional[str] = None) -> None:
        url = Urls(address=address, username=username, password=password, group_id=group_id)
        s.add(url)
        await s.flush()
        await Database.add_url_status(url.id, datetime.datetime.now(), 'unknown')

    @staticmethod
    @create_session()
    async def insert_db(s: async_sessionmaker[AsyncSession](), address: str,
                        user: str, password: str, tp: str, port: int, group_id: int) -> None:
        db = Dbs(address=address, dbtype=tp, port=int(port), username=user, password=password, group_id=group_id)
        s.add(db)
        await s.flush()
        await Database.add_db_status(db.id, datetime.datetime.now(), 'unknown')

    # Get indiv. ones
    @staticmethod
    @create_session()
    async def get_ip(s: async_sessionmaker[AsyncSession](), id: int):
        out = await s.execute(select(Ips).where(Ips.id == id))
        return out.first()[0]

    @staticmethod
    @create_session()
    async def get_url(s: async_sessionmaker[AsyncSession](), id: int):
        out = await s.execute(select(Urls).where(Urls.id == id))
        res = out.first()[0]
        return res if res else -1

    @staticmethod
    @create_session()
    async def get_db(s: async_sessionmaker[AsyncSession](), id: int):
        out = await s.execute(select(Dbs).where(Dbs.id == id))
        res = out.first()[0]
        return res if res else -1

    # Get last ids
    @staticmethod
    @create_session()
    async def get_last_ip_id(s: async_sessionmaker[AsyncSession]()) -> int:
        out = await s.execute(select(func.max(Ips.id)))
        res = out.first()[0]
        return res if res else 0

    @staticmethod
    @create_session()
    async def get_last_url_id(s: async_sessionmaker[AsyncSession]()) -> int:
        out = await s.execute(select(func.max(Urls.id)))
        res = out.first()[0]
        return res if res else 0

    # Get all
    @staticmethod
    @create_session()
    async def get_all_ips(s: async_sessionmaker[AsyncSession]()):
        out = await s.execute(select(Ips.id, Ips.address, Groups.group_name).where(Ips.group_id == Groups.id))
        return out.all()

    @staticmethod
    @create_session()
    async def get_all_urls(s: async_sessionmaker[AsyncSession]()):
        out = await s.execute(select(Urls.id, Urls.address, Groups.group_name).where(Urls.group_id == Groups.id))
        return out.all()

    @staticmethod
    @create_session()
    async def get_all_dbs(s: async_sessionmaker[AsyncSession]()):
        out = await s.execute(select(Dbs.id, Dbs.address, Dbs.port, Groups.group_name).where(Dbs.group_id == Groups.id))
        return out.all()

    # Delete by id
    @staticmethod
    @create_session()
    async def delete_ip(s: async_sessionmaker[AsyncSession]()
                        , id: int) -> None:
        await Database.del_all_ip_status(id)
        await s.execute(delete(Ips).where(Ips.id == id))

    @staticmethod
    @create_session()
    async def delete_url(s: async_sessionmaker[AsyncSession]()
                         , id: int) -> None:
        await Database.del_all_url_status(id)
        await s.execute(delete(Urls).where(Urls.id == id))

    @staticmethod
    @create_session()
    async def delete_db(s: async_sessionmaker[AsyncSession]()
                        , id: int) -> None:
        await Database.del_all_db_status(id)
        await s.execute(delete(Dbs).where(Dbs.id == id))

    # GEt all with status
    @staticmethod
    @create_session()
    async def get_all_ips_status_time(s: async_sessionmaker[AsyncSession]()):
        out = await s.execute(text(
            'SELECT ips.address,b.*,c.status FROM condition_ip c,(SELECT ex_id,max(time)'
            ' as mt FROM condition_ip GROUP BY ex_id) b,ips WHERE b.mt=c.time AND ips.id=c.ex_id'))
        return out.all()

    @staticmethod
    @create_session()
    async def get_all_urls_status_time(s: async_sessionmaker[AsyncSession]()):
        out = await s.execute(text(
            'SELECT urls.address,b.*,'
            'c.status,urls.username,'
            'urls.password FROM condition_url c,'
            '(SELECT ex_id,max(time) as mt FROM condition_url GROUP BY ex_id) b,'
            'urls WHERE b.mt=c.time AND urls.id=c.ex_id'))
        return out.all()

    @staticmethod
    @create_session()
    async def get_all_dbs_status_time(s: async_sessionmaker[AsyncSession]()):
        out = await s.execute(text(
            'SELECT dbs.address,b.*,'
            'c.status,dbs.username,'
            'dbs.password,dbs.port,dbs.dbtype FROM condition_db c,'
            '(SELECT ex_id,max(time) as mt FROM condition_db GROUP BY ex_id) b,'
            'dbs WHERE b.mt=c.time AND dbs.id=c.ex_id'))
        return out.all()

    # Get all statuses
    @staticmethod
    @create_session()
    async def get_history_ip(s: async_sessionmaker[AsyncSession]()):
        # out = await s.execute(select(ConditionIp,Reasons.reason)
        #                       .where(or_(ConditionIp.reason_id==Reasons.id,ConditionIp.reason_id==None)).
        #                       order_by(ConditionIp.ex_id, ConditionIp.time))
        out = await s.execute(select(ConditionIp, Reasons.reason)
                              .select_from(ConditionIp)
                              .join(Reasons, ConditionIp.reason_id == Reasons.id, isouter=True).
                              order_by(ConditionIp.ex_id, ConditionIp.time))
        return out.all()

    @staticmethod
    @create_session()
    async def get_history_url(s: async_sessionmaker[AsyncSession]()):
        out = await s.execute(select(ConditionUrl, Reasons.reason)
                              .select_from(ConditionUrl)
                              .join(Reasons, ConditionUrl.reason_id == Reasons.id, isouter=True).
                              order_by(ConditionUrl.ex_id, ConditionUrl.time))
        return out.all()

    @staticmethod
    @create_session()
    async def get_history_db(s: async_sessionmaker[AsyncSession]()):
        out = await s.execute(select(ConditionDb, Reasons.reason)
                              .select_from(ConditionDb)
                              .join(Reasons, ConditionDb.reason_id == Reasons.id, isouter=True).
                              order_by(ConditionDb.ex_id, ConditionDb.time))
        return out.all()

    # Inserts(status)
    @staticmethod
    @create_session()
    async def add_ip_status(s: async_sessionmaker[AsyncSession](),
                            ex_id: int, time: datetime.datetime, status: str) -> None:
        if not (ex_id and time and status):
            raise ValueError('Все поля должны быть заполнены для вставки')
        record = ConditionIp(ex_id=int(ex_id), time=time, status=status)
        s.add(record)

    @staticmethod
    @create_session()
    async def add_url_status(s: async_sessionmaker[AsyncSession](),
                             ex_id: int, time: datetime.datetime, status: str) -> None:
        if not (ex_id and time and status):
            raise ValueError('Все поля должны быть заполнены для вставки')
        record = ConditionUrl(ex_id=int(ex_id), time=time, status=status)
        s.add(record)

    @staticmethod
    @create_session()
    async def add_db_status(s: async_sessionmaker[AsyncSession](),
                            ex_id: int, time: datetime.datetime, status: str) -> None:
        if not (ex_id and time and status):
            raise ValueError('Все поля должны быть заполнены для вставки')
        record = ConditionDb(ex_id=int(ex_id), time=time, status=status)
        s.add(record)

    # Delete(status)
    @staticmethod
    @create_session()
    async def del_all_ip_status(s: async_sessionmaker[AsyncSession](),
                                ex_id: int) -> None:
        await s.execute(delete(ConditionIp)
                        .where(ConditionIp.ex_id == ex_id))

    @staticmethod
    @create_session()
    async def del_all_url_status(s: async_sessionmaker[AsyncSession](),
                                 ex_id: int) -> None:
        await s.execute(delete(ConditionUrl)
                        .where(ConditionUrl.ex_id == ex_id))

    @staticmethod
    @create_session()
    async def del_all_db_status(s: async_sessionmaker[AsyncSession](),
                                ex_id: int) -> None:
        await s.execute(delete(ConditionDb)
                        .where(ConditionDb.ex_id == ex_id))

    # Misc

    @staticmethod
    async def sorted_history(tp: int) -> list:
        # get history of all registered times
        match tp:
            case 0:
                history = await Database.get_history_ip()
            case 1:
                history = await Database.get_history_url()
            case 2:
                history = await Database.get_history_db()
            case _:
                raise ValueError('Неверный тип истории')

        dc = History()
        history_data = []
        fin_on_d = False
        reason = ''
        for point in history:

            p = point[0]
            if p.status == 'unknown':
                continue
            if not p.ex_id == dc.id:
                if dc.end == 0 and not dc.id == 0:
                    dc.end = None
                    history_data.append(dc)
                dc = History(id=p.ex_id)
            if p.status == 'down':
                fin_on_d = True
                dc.start = ((p.time)
                            .strftime('%Y-%m-%dT%H:%M:%S.%fZ'))
            elif p.status == 'up':
                fin_on_d = False
                dc.end = ((p.time)
                          .strftime('%Y-%m-%dT%H:%M:%S.%fZ'))
                history_data.append(dc)
                dc = History()
            reason = point.reason
            # print(reason)
            if reason:
                dc.reason = reason
            reason = ''
        if fin_on_d:
            dc.end = None
            dc.reason = history[-1].reason if history[-1].reason else ''
            history_data.append(dc)
        return history_data

    # This is necessary to properly update colours
    @staticmethod
    async def first_load_icons() -> list[dict]:
        ids = [i.id for i in await Database.get_all_ips()]
        for i in await Database.get_all_urls():
            ids.append(i.id + await Database.get_last_ip_id())
        for i in await Database.get_all_dbs():
            ids.append(i.id + await Database.get_last_ip_id() + await Database.get_last_url_id())
        out = []
        for i in ids:
            out.append(
                {'id': i, 'label': 'Неизвестно', 'title': 'Этот сервис есть в базе но ещё не проверялся', 'group': '0'})
        return out

    @staticmethod
    async def form_jsons(history_type: int) -> list[dict]:
        # get latest history
        # TODO this is bad fix this

        history = await Database.sorted_history(history_type)
        j = 0

        for b in range(len(history)):
            if j == history[b].id:
                history[b - 1] = None
            else:
                j = history[b].id

        res = [k for k in history if k is not None]

        # Make em ito jsons
        group = history_type + 1
        output = []
        dc = {
            'id': 0,
            'label': 0,
            'title': 0,
            'group': str(group),
            'shape': "icon",
            'icon': {
                'color': "gray",
                'face': "'Font Awesome 5 Free'",
                'weight': "900",
                'code': 0
            },
        }
        add_id = 0
        match history_type:
            case 0:
                names = await Database.get_all_ips()
                code = "\uf085"
            case 1:
                names = await Database.get_all_urls()
                add_id = await Database.get_last_ip_id()
                code = "\uf233",
            case 2:
                names = await Database.get_all_dbs()
                add_id = await Database.get_last_ip_id() + await Database.get_last_url_id()
                code = "\uf1c0"
            case _:
                raise ValueError('history_type can only be in range 0-2')

        for r in res:
            col = ''
            # making title
            # print(datetime.datetime.time(r.start))
            if r.end:

                if r.start:
                    title = (f'Был offline с {Database.format_time(r.start)}'
                             f' до {Database.format_time(r.end)}')


                    col = '#A9F5D0'
                    offline = False
                    true_start = r.start
                else:
                    title = f'Online с {Database.format_time(r.end)}'
                    col = '#A9F5D0'
                    offline = False
                    true_start = None
            else:
                title = f'Offline с {Database.format_time(r.start)}'
                col = 'red'
                offline = True
                true_start = r.start
            dc['title'] = title
            if r.reason:
                dc['title']+='\nПричина: '+r.reason
            # making label
            # idk how else to do this
            label = 'err'
            try:
                for n in names:

                    if r.id == n.id:
                        label = n.address
                        break
            except Exception as e:
                raise ValueError(f'нет такого id {e}')

            dc['label'] = label
            dc['id'] = int(r.id) + add_id
            dc['icon']['color'] = col
            dc['icon']['code'] = code
            dc['offline'] = offline
            dc['true_start'] = true_start
            output.append(dc)
            dc = {
                'id': 0,
                'label': 0,
                'title': 0,
                'group': str(group),
                'icon': {
                    'color': "red",
                    'face': "'Font Awesome 5 Free'",
                    'weight': "900",
                    'code': 0
                },
            }
        return output

    @staticmethod
    def format_time(time):
        return datetime.datetime.strftime((datetime.datetime.
                                           strptime(time, '%Y-%m-%dT%H:%M:%S.%fZ')), '%Y-%m-%d %H:%M:%S')

    # Groups
    @staticmethod
    @create_session()
    async def group_in_db(s: async_sessionmaker[AsyncSession](), group_name: str):
        out = await s.execute(select(func.count(1)).where(Groups.group_name == group_name))
        return out.first()[0] > 0

    @staticmethod
    @create_session()
    async def get_group_id(s: async_sessionmaker[AsyncSession](), group_name: str):
        out = await s.execute(select(Groups.id).where(Groups.group_name == group_name))
        return out.first()[0]

    @staticmethod
    @create_session()
    async def get_group_name_all(s: async_sessionmaker[AsyncSession]()):
        out = await s.execute(select(Groups.group_name))
        return [a[0] for a in out.all()]

    @staticmethod
    @create_session()
    async def insert_group(s: async_sessionmaker[AsyncSession](), group_name):
        if await Database.group_in_db(group_name):
            # raise ValueError('Такая группа уже есть')
            return await Database.get_group_id(group_name)
        else:
            new_group = Groups(group_name=group_name)
            s.add(new_group)
            await s.flush()
            return new_group.id

    # Reasons
    @staticmethod
    @create_session()
    async def insert_reason(s: async_sessionmaker[AsyncSession](), reason):
        new_reason = Reasons(reason=reason)
        s.add(new_reason)
        await s.flush()
        return new_reason.id

    @staticmethod
    @create_session()
    async def reason_to_condition_ip(s: async_sessionmaker[AsyncSession](), reason_id, cond_id):
        await s.execute(update(ConditionIp).where(ConditionIp.id == cond_id).values(reason_id=reason_id))

    @staticmethod
    @create_session()
    async def reason_to_condition_url(s: async_sessionmaker[AsyncSession](), reason_id, cond_id):
        await s.execute(update(ConditionUrl).where(ConditionUrl.id == cond_id).values(reason_id=reason_id))

    @staticmethod
    @create_session()
    async def reason_to_condition_db(s: async_sessionmaker[AsyncSession](), reason_id, cond_id):
        await s.execute(update(ConditionDb).where(ConditionDb.id == cond_id).values(reason_id=reason_id))

    # GEt by ex_id and time
    @staticmethod
    @create_session()
    async def get_cond_ip(s: async_sessionmaker[AsyncSession](), ex_id: int, time) -> int:
        out = await s.execute(select(ConditionIp.id)
                              .where(ConditionIp.ex_id == ex_id).where(ConditionIp.time == time))
        res = out.first()[0]
        return res if res else 0

    @staticmethod
    @create_session()
    async def get_cond_url(s: async_sessionmaker[AsyncSession](), ex_id: int, time) -> int:
        out = await s.execute(select(ConditionUrl.id)
                              .where(ConditionUrl.ex_id == ex_id)
                              .where(ConditionUrl.time == time))
        res = out.first()[0]
        return res if res else 0

    @staticmethod
    @create_session()
    async def get_cond_db(s: async_sessionmaker[AsyncSession](), ex_id: int, time) -> int:
        out = await s.execute(select(ConditionDb.id)
                              .where(ConditionDb.ex_id == ex_id)
                              .where(ConditionDb.time == time))
        res = out.first()[0]
        return res if res else 0


if __name__ == '__main__':
    async def a():
        # h = await Database.form_jsons(2)
        # print(h)
        pass


    asyncio.run(a())
    pass
