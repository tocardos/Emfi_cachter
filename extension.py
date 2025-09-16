# models.py
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy.orm import sessionmaker
import datetime
import pytz # to synch with brussels time

from flask_socketio import SocketIO
from flask_cors import CORS
from flask import Flask, render_template, jsonify,request
#import lte_cause



socketio = SocketIO()
db = SQLAlchemy()

Base = declarative_base()

database_url = 'sqlite:///epcserver.db'  # Example using SQLite

ENB_MCC = "--enb.mcc"
ENB_MNC = "--enb.mnc"
RF_DLEARFCN = "--rf.dl_earfcn"
PROXIMUS = (206,1)
ORANGE = (206,10)
BASE = (206,20)
TELENET = (206,4)




def init_db(database_url):
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
# Define a function to get the current time in Europe/Brussels timezone
def get_brussels_time():
    return datetime.datetime.now(pytz.timezone('Europe/Brussels'))

def init_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app((app))
    socketio.init_app(app)
    CORS(app)

    with app.app_context():
        db.create_all()

    return app

class EPCData(Base):
    
    __tablename__ = 'epc_data'
    id = Column(Integer, primary_key=True, autoincrement=True)
    unique_id = Column(String(15), unique=True, nullable=False)
    connection_type = Column(String(50), nullable=True)
    firstseen = Column(DateTime, default=datetime.datetime.utcnow)
    lastseen = Column(DateTime, default=datetime.datetime.utcnow)
    count = Column(Integer,default=1)
    #action = Column(String(50), nullable="RELEASE")
    action = Column(String(50), default=None)
    whitelist = Column(String(50), default="Unknown")
    alias = Column(String(50),default=None)
    fingerprint = Column(JSON, nullable=True)
    '''
    __tablename__ = 'epc_data'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    unique_id = db.Column(db.String(15), unique=True, nullable=False)
    connection_type = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    action = db.Column(db.String(50), default="C&R")
    whitelist = db.Column(db.String(50), default="Unknown")
    alias = db.Column(db.String(50), default=None)
    fingerprint = db.Column(db.JSON, nullable=True)
'''

