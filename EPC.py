from datetime import datetime
import socket
import string
import sctp
import binascii
from state_machine import EPC_state_machine
from pycrate_asn1dir import S1AP
import threading
import  lte_cause
import pytz
import datetime
from extension import EPCData,init_db,socketio,db


'''
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
Base = declarative_base()
class EPCData(Base):
    __tablename__ = 'epc_data'
    id = Column(Integer, primary_key=True, autoincrement=True)
    unique_id = Column(String(15), unique=True, nullable=False)
    connection_type = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    action = Column(String(50), nullable=True)
    whitelist = Column(Boolean, default=False)
    fingerprint = Column(JSON, nullable=True)
'''

class EPCServer:
    #sctp_socket = None
    fd = None
    addr = None
    #state = EPC_state_machine()
    #IMSI_output = None
    omit = None
    target = None
    listenAddress = "0.0.0.0" # watch out ip address
    listenPort = 36412
    #clients = []
    #lock = threading.Lock()
    #attach_reject_reason = 8
    attach_reject_reason = 15
    def __init__(self, process_packet_callback,database_url):
        # Initialize database connection
        #self.engine = create_engine(database_url)
        #Base.metadata.create_all(self.engine)
        self.Session = init_db(database_url)
        #self.Session = db.session()
        self.sctp_socket = None
        self.clients = []
        self.state = EPC_state_machine()
        self.IMSI_output = None
        self.lock = threading.Lock()
        self.process_packet_callback = process_packet_callback
        self.running = False
    
    def init_server(self) -> None:
        """Creates server socket and saves the socket in the EPCServer obj"""
        self.sctp_socket = sctp.sctpsocket_tcp(socket.AF_INET)
        return
    
    def start(self,):
        self.running=True
        try:
            self.sctp_socket.bind((self.listenAddress,self.listenPort))
        except:
            print("\nThe socket is already in use")
            exit()
        try:
            self.sctp_socket.listen(5)
            #fd,addr = sctp_socket.accept()
        except KeyboardInterrupt:
            print("\nThe program was interrupted while awaiting a connection. Exiting ..")
            exit()
        #self.fd = fd
        #self.addr = addr
        if self.IMSI_output == None:
            self.IMSI_output = open("IMSI_output.txt","a")
        #while True:
        while self.running:
            try:
                self.sctp_socket.settimeout(3.0)  # Set timeout for accept
                fd, addr = self.sctp_socket.accept()
                print(f"Accepted connection from {addr}")
                client_thread = threading.Thread(target=self.handle_client, args=(fd, addr))
                client_thread.start()
                with self.lock:
                    self.clients.append((fd, addr))
            except socket.timeout:
                #print('socket timeout ') # print just for debug
                continue
            except OSError as e:
                if not self.running and e.errno == 9:
                    # The server socket was closed, which is expected during shutdown
                    break
                else:
                    print(f"Exception occurred: {e}")
                    break
            except KeyboardInterrupt:
                print("\nThe program was interrupted while awaiting a connection. Exiting ..")
                self.close_server()
                exit() 
    def handle_client(self, fd, addr):
        """Handles communication with a single client"""
        while self.running:
            try:
                #fd.settimeout(3.0)  # Set timeout for recv
                # bad idea to use a timeout on a asynch connection
                # keep comment for further devel
                s1ap, success = self.get_packet(fd)
                #print(s1ap) # for quick and dirty debug process
                if s1ap is None or not success:
                    print(f's1ap : {s1ap } or  success {success}')
                    break
                # Process the received packet
                # Spawn a new thread for processing the packet
                processing_thread = threading.Thread(target=self.process_packet, args=(s1ap, fd))
                processing_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error handling client {addr}: {e}")
                break
        self.close_client(fd, addr)

    def process_packet(self,s1ap,fd):
        """Delegate the packet processing to the provided callback"""
        self.process_packet_callback(self,s1ap, fd)

    def close_client(self, fd, addr):
        """Closes a client connection"""
        print(f"Closing connection to {addr}")
        fd.close()
        with self.lock:
            try:
                if (fd, addr) in self.clients:
                    self.clients.remove((fd, addr))
                #self.clients.remove((fd, addr))
            except ValueError as e:
                print(f"error while removing client in EPC")
                pass
                
    def close_server(self) -> None:
        """Closes the saved socket connections in EPCServer"""
        self.running = False
        #if self.fd:
        with self.lock:
            for fd, addr in self.clients:
                fd.close()
        if self.sctp_socket:
            self.sctp_socket.close()
        if self.IMSI_output:
            self.IMSI_output.close()
        self.sctp_socket = None
        #self.fd = None
        #self.addr = None
        self.clients = []
        self.state.set_current_state("null_state")
    def get_packet(self,fd) -> tuple:
        """Receive a packet on the initialised socket in the EPCServer"""
        try:
            #print('get packet')
            fromaddr, flags, msgret, notif = fd.sctp_recv(2048)
        except ConnectionResetError:
            print("Connection reset while receiving packet. Closing connection ..")
            #self.close_server()
            return (None,False)
        if len(msgret) == 0:
            return None,False
        s1ap_hex = msgret.hex()
        
        #print(s1ap_hex)
        try:
            # decode using pycrate
            s1ap = S1AP.S1AP_PDU_Descriptions.S1AP_PDU
            s1ap.from_aper(binascii.unhexlify(s1ap_hex))
            print(s1ap)
            return s1ap, (True if flags == sctp.FLAG_EOR else False)
        except Exception as err:
            print("Error during S1AP dissection. Skipping..")
    def send_packet(self,fd,value: string):
        """The function wants the input hexlified. Function is better not used directly, use encode_and_send_packet()"""
        fd.sctp_send(bytes.fromhex(value), ppid=socket.htonl(18))

    def encode_and_send_packet(self,s1ap_decoded,fd):
        """encode a message and send it on the preset socket in the EPCServer"""
        s1ap = S1AP.S1AP_PDU_Descriptions.S1AP_PDU
        s1ap.set_val(s1ap_decoded)
        s1ap_hex_out = binascii.hexlify(s1ap.to_aper()).decode('ascii')
        self.send_packet(fd,s1ap_hex_out)
        '''
    def write_imsi(self,imsi: string) -> None:
        "prints IMSI information to an opened file"
        if self.IMSI_output == None:
            return
        self.IMSI_output.write(f"{datetime.now()}")
        self.IMSI_output.write("    ")
        self.IMSI_output.write(imsi)
        self.IMSI_output.write("\n")

    '''
    def write_imsi(self, unique_id, connection_type, fingerprint):
        """Write IMSI data to the database"""
        local_timezone = pytz.timezone("Europe/Brussels")
        
        session = self.Session()
        epc_data = session.query(EPCData).filter_by(unique_id=unique_id).first()
        if epc_data:
            epc_data.lastseen = datetime.datetime.now()
            epc_data.fingerprint = fingerprint
            epc_data.count = epc_data.count+1
        else:
            epc_data = EPCData(
                unique_id=unique_id,
                connection_type=connection_type,
                fingerprint=fingerprint,
                whitelist = "unknown"
            )
            session.add(epc_data)
        session.commit()
        session.close()
        # Notify the web app to update the table
        print('update table')
        socketio.emit('update_table',1)
    def Imsi_reject(self,unique_id):
        session = self.Session()
        epc_data = session.query(EPCData).filter_by(unique_id=unique_id).first()
        if epc_data.action:
            reject = getattr(lte_cause, epc_data.action, None)
            return reject
        else:
            return None
