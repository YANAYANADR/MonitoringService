import datetime
import logging
from typing import Optional

from sqlalchemy import (create_engine, String, DateTime,
                        text, select, func)
from sqlalchemy.orm import (DeclarativeBase, Mapped,
                            mapped_column, Session)
import psycopg2

# logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# code to only be used in test!!!! vvv

# eng = create_engine("postgresql://postgres:1234@localhost:5432/postgres",
#                     isolation_level="AUTOCOMMIT")
#
# with Session(eng) as sess:
#     try:
#         sess.execute(text('CREATE DATABASE monitoring'))
#         log.info('База создана')
#     except Exception as e:
#         log.info(f'База уже существует')
# ^^^^ end of test code pls remove later

# access db
try:
    eng = create_engine("postgresql://postgres:1234@db:5432/monitoring")
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


class ConditionUrl(Base):
    __tablename__ = 'condition_url'
    id: Mapped[int] = mapped_column(primary_key=True)
    ex_id: Mapped[int] = mapped_column()
    time: Mapped[datetime.datetime] = mapped_column(DateTime())
    status: Mapped[str] = mapped_column(String())


class ConditionDb(Base):
    __tablename__ = 'condition_db'
    id: Mapped[int] = mapped_column(primary_key=True)
    ex_id: Mapped[int] = mapped_column()
    time: Mapped[datetime.datetime] = mapped_column(DateTime())
    status: Mapped[str] = mapped_column(String())


class Ips(Base):
    __tablename__ = 'ips'
    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String())


class Urls(Base):
    __tablename__ = 'urls'
    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String())
    # optional auth???
    username: Mapped[Optional[str]] = mapped_column(String())
    password: Mapped[Optional[str]] = mapped_column(String())


class Dbs(Base):
    __tablename__ = 'dbs'
    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String())
    dbtype: Mapped[str] = mapped_column(String())
    port: Mapped[int] = mapped_column()
    username: Mapped[str] = mapped_column(String())
    password: Mapped[str] = mapped_column(String())


Base.metadata.create_all(eng)


# Methods

# Checks
def ip_in_db(address):
    with Session(eng) as s:
        out = s.execute(select(func.count(1))
                        .where(Ips.address == address)).first()[0]
    return out > 0


# Inserts
def insert_ip(address):
    if not ip_in_db(address):
        with Session(eng) as s:
            ip = Ips(address=address)
            s.add(ip)
            s.flush()
            s.commit()
            # adds unknown status
            add_ip_status(ip.id, datetime.datetime.now(), 'unknown')
    else:
        raise ValueError('Ip is already in database')


def insert_url(address, username: Optional[str] = None,
               password: Optional[str] = None):
    # TODO add check
    with Session(eng) as s:
        url = Urls(address=address, username=username, password=password)
        s.add(url)
        s.flush()
        s.commit()
        add_url_status(url.id, datetime.datetime.now(), 'unknown')


def insert_db(address, user, password, type, port):
    with Session(eng) as s:
        db = Dbs(address=address, dbtype=type, port=port, username=user, password=password)
        s.add(db)
        s.flush()
        s.commit()
        add_db_status(db.id, datetime.datetime.now(), 'unknown')


# Get indiv. ones
def get_ip(id):
    with Session(eng) as s:
        out = s.execute(select(Ips).where(Ips.id == id)).first()[0]
        return out


def get_url(id):
    with Session(eng) as s:
        out = s.execute(select(Urls).where(Urls.id == id)).first()[0]
        return out


def get_db(id):
    with Session(eng) as s:
        out = s.execute(select(Dbs).where(Dbs.id == id)).first()[0]
        return out


# Get all
def get_all_ips():
    with Session(eng) as s:
        out = s.execute(select(Ips.id, Ips.address)).all()
    return out


def get_all_urls():
    with Session(eng) as s:
        out = s.execute(select(Urls.id, Urls.address)).all()
    return out


def get_all_dbs():
    with Session(eng) as s:
        out = s.execute(select(Dbs.id, Dbs.address, Dbs.port)).all()
    return out


# GEt all with status
def get_all_ips_status_time():
    with Session(eng) as s:
        # b=(select(ConditionIp.ip_id,func.max(ConditionIp.time).label('mt')).group_by(ConditionIp.ip_id)).scalar_subquery()
        # b=s.execute(select(ConditionIp.ip_id,func.max(ConditionIp.time).label('mt')).group_by(ConditionIp.ip_id)).all()
        # out=s.execute(select(Ips.address,ConditionIp.status,ConditionIp.ip_id).where(Ips.id==ConditionIp.ip_id).where(b.==ConditionIp.time)).all()
        out = s.execute(text(
            'SELECT ips.address,b.*,c.status FROM condition_ip c,(SELECT ex_id,max(time) as mt FROM condition_ip GROUP BY ex_id) b,ips WHERE b.mt=c.time AND ips.id=c.ex_id')).all()
    return out


def get_all_urls_status_time():
    with Session(eng) as s:
        out = s.execute(text(
            'SELECT urls.address,b.*,'
            'c.status,urls.username,'
            'urls.password FROM condition_url c,'
            '(SELECT ex_id,max(time) as mt FROM condition_url GROUP BY ex_id) b,'
            'urls WHERE b.mt=c.time AND urls.id=c.ex_id')).all()
    return out


def get_all_dbs_status_time():
    with Session(eng) as s:
        out = s.execute(text(
            'SELECT dbs.address,b.*,'
            'c.status,dbs.username,'
            'dbs.password,dbs.port,dbs.dbtype FROM condition_db c,'
            '(SELECT ex_id,max(time) as mt FROM condition_db GROUP BY ex_id) b,'
            'dbs WHERE b.mt=c.time AND dbs.id=c.ex_id')).all()
        return out


# Get all statuses
def get_history_ip():
    with Session(eng) as s:
        # out=s.execute(select(ConditionIp.ip_id,ConditionIp.status,ConditionIp.time).order_by(ConditionIp.ip_id)).all()
        out = s.execute(select(ConditionIp).order_by(ConditionIp.ex_id, ConditionIp.time)).all()
    return out


def get_history_url():
    with Session(eng) as s:
        out = s.execute(select(ConditionUrl).order_by(ConditionUrl.ex_id, ConditionUrl.time)).all()
    return out


def get_history_db():
    with Session(eng) as s:
        out = s.execute(select(ConditionDb).order_by(ConditionDb.ex_id, ConditionDb.time)).all()
    return out


# Inserts(status)
def add_ip_status(ex_id, time, status):
    pass
    with Session(eng) as s:
        record = ConditionIp(ex_id=ex_id, time=time, status=status)
        s.add(record)
        s.flush()
        s.commit()


def add_url_status(ex_id, time, status):
    pass
    with Session(eng) as s:
        record = ConditionUrl(ex_id=ex_id, time=time, status=status)
        s.add(record)
        s.flush()
        s.commit()


def add_db_status(ex_id, time, status):
    pass
    with Session(eng) as s:
        record = ConditionDb(ex_id=ex_id, time=time, status=status)
        s.add(record)
        s.flush()
        s.commit()


# Misc
def sorted_history_ip():
    # get history of all registered times in dictionary format
    history = get_history_ip()
    dc = {
        'ipid': 0,
        'start': 0,
        'end': 0,
    }
    muhData = []
    fin_on_d = False
    for point in history:
        p = point[0]
        if p.status == 'unknown':
            continue
        if not p.ex_id == dc['ipid']:
            if dc['end'] == 0 and not dc['ipid'] == 0:
                dc['end'] = None
                muhData.append(dc)
            dc = {'ipid': p.ex_id, 'start': 0, 'end': 0}
        if p.status == 'down':
            fin_on_d = True
            dc['start'] = (p.time - datetime.timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        elif p.status == 'up':
            fin_on_d = False
            dc['end'] = (p.time - datetime.timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            muhData.append(dc)
            dc = {
                'ipid': 0,
                'start': 0,
                'end': 0,
            }
    if fin_on_d:
        dc['end'] = None
        muhData.append(dc)
    return muhData


def sorted_history(tp):
    # get history of all registered times in dictionary format
    history = get_history_ip()
    match (tp):
        case 0:
            history = get_history_ip()
        case 1:
            history = get_history_url()
        case 2:
            history = get_history_db()
    dc = {
        'ipid': 0,
        'start': 0,
        'end': 0,
    }
    muhData = []
    fin_on_d = False
    for point in history:
        p = point[0]
        if p.status == 'unknown':
            continue
        if not p.ex_id == dc['ipid']:
            if dc['end'] == 0 and not dc['ipid'] == 0:
                dc['end'] = None
                muhData.append(dc)
            dc = {'ipid': p.ex_id, 'start': 0, 'end': 0}
        if p.status == 'down':
            fin_on_d = True
            dc['start'] = (p.time - datetime.timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        elif p.status == 'up':
            fin_on_d = False
            dc['end'] = (p.time - datetime.timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            muhData.append(dc)
            dc = {
                'ipid': 0,
                'start': 0,
                'end': 0,
            }
    if fin_on_d:
        dc['end'] = None
        muhData.append(dc)
    return muhData


def sorted_history_ip_latest():
    # get latest history
    # TODO this is bad fix this
    a = sorted_history_ip()
    j = 0
    for b in range(len(a)):
        if j == a[b]['ipid']:
            a[b - 1] = None
        else:
            j = a[b]['ipid']
    return [k for k in a if k is not None]


def form_jsons(history_type):
    # get latest history
    # TODO this is bad fix this
    a = sorted_history(history_type)
    j = 0
    for b in range(len(a)):
        if j == a[b]['ipid']:
            a[b - 1] = None
        else:
            j = a[b]['ipid']
    res = [k for k in a if k is not None]
    # make em ito jsons
    group = history_type + 1
    output = []
    dc = {
        'id': 0,
        'label': 0,
        'title': 0,
        'group': str(group),
    }
    add_id = 0
    match (history_type):
        case 0:
            names = get_all_ips()
        case 1:
            names = get_all_urls()
            add_id = len(get_all_ips())
        case 2:
            names = get_all_dbs()
            add_id = len(get_all_ips()) + len(get_all_urls())

    for r in res:
        # making title
        if r['end']:
            if r['start']:
                title = f'Был offline с {r['end']} до {r['start']}'
            else:
                title = f'Online с {r['end']}'
        else:
            title = f'Offline с {r['start']}'
        dc['title'] = title
        # making label
        # idk how else to do this
        label = 'err'
        try:
            for n in names:
                if r['ipid'] == n[0]:
                    label = n[1]
                    break
        except:
            raise ValueError('нет такого id')

        dc['label'] = label
        dc['id'] = int(r['ipid']) + add_id
        output.append(dc)
        dc = {
            'id': 0,
            'label': 0,
            'title': 0,
            'group': str(group),
        }
    return output


if __name__ == '__main__':
    # print(get_all_ips()[0])
    # insert_ip('localhost')
    # add_ip_status(3,datetime.datetime.now(),'down')
    # print(get_all_ips_status_time())
    # print(get_history_ip()[0].ex_id)
    print(get_all_urls())
    # print(get_all_dbs_status_time())
    pass
