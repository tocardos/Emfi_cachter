from flask import Flask, render_template, jsonify,request,Response,redirect,url_for,session
from threading import Thread
from EPC import *
from MME import process_packet
import json
import multiprocessing as mp
import subprocess
#from parsing import parsing
import os
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import psutil
import time
import  lte_cause
from flask_sqlalchemy import SQLAlchemy
from extension import init_db,EPCData,socketio,init_app,db
import logging

from config import init_database,add_frequency_band,get_operator_frequencies
import sqlite3

import tscm_logo 

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
# adapt following working dir based on your path where you place srsran
# default is in config folder 
#working_dir = '/home/baddemanax/development/python/EPC_webapp/config'
working_dir = './config'

# database to store phone's information
database_url = 'sqlite:///epcserver.db'  # Example using SQLite

app = Flask(__name__)
app.secret_key = "BigSecret"  # needed for sessions
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///epcserver.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db_session = init_db(app.config['SQLALCHEMY_DATABASE_URI'])
#db.create_all()
CORS(app)

#socketio = SocketIO(app)
socketio.init_app(app)

#app=init_app()

# database to store phone operator
# copy from another code, using sqlite3, better would be to use sqlalchemy for all db
# tbc...
init_database()
def get_db_connection():
    conn = sqlite3.connect('mobile_network.db')
    conn.row_factory = sqlite3.Row
    return conn


server_thread = None
server_instance = None
server_running = False 
thread_enb = None
ENB_running = False
sp = None
stop_event = None
console_output_queue = []
MAX_CONSOLE_LINES = 100

# Store the current server mode
epc_current_mode = "LIBLTE_MME_EMM_CAUSE_NO_SUITABLE_CELLS_IN_TRACKING_AREA"
# Store the status of each Raspberry Pi
pi_statuses = {}
server_info = {
    'hostname': socket.gethostname(),
    'cpu': psutil.cpu_percent(interval=1),
    'memory': psutil.virtual_memory().percent,
    'heartbeat': time.time()
}

@app.route('/')
def index():
    return render_template('index.html')
@app.route('/settings')
def settings():

    conn = get_db_connection()
    countries = conn.execute('SELECT * FROM countries').fetchall()
    operators = conn.execute('SELECT * FROM operators').fetchall()
    conn.close()

    # default settings if none stored yet
    current_settings = session.get('current_settings', {
        'tx_gain': 80,
        'country_name': 'belgique',
        'mcc': 206,
        'mnc': 1,
        'earfcn': 1315,
        'frequency': 1920,
        'operator_name': 'DefaultOperator',
        'bandwidth': 10,
        'technology': 'LTE'
    })

    
    
    return render_template('settings.html',current_settings=current_settings,countries=countries, operators=operators)

@app.route('/update_tx_gain', methods=['POST'])
def update_tx_gain():
    data = request.get_json()
    tx_gain = int(data.get("tx_gain", 80))
    logging.info(f"update tx_gain: {tx_gain} ")
    # Get current settings or initialize
    current_settings = session.get("current_settings", {})
    current_settings['tx_gain'] = tx_gain
    session['current_settings'] = current_settings  # save back to session

    return jsonify(success=True, tx_gain=tx_gain)

@app.route('/search', methods=['GET'])
def search():
    country = request.args.get('country')
    operator = request.args.get('operator')
    

    if not country:
        return redirect(url_for('settings'))
    
    
    conn = get_db_connection()
    results = conn.execute('''
        SELECT f.*, ocm.mnc, ocm.mcc, o.operator_name, c.country_name
        FROM frequency_bands f
        JOIN operator_frequency_mappings ofm ON f.id = ofm.frequency_band_id
        JOIN operator_country_mappings ocm ON ofm.operator_country_id = ocm.id
        JOIN operators o ON ocm.operator_id = o.id
        JOIN countries c ON ocm.mcc = c.mcc
        WHERE c.country_name = ? 
    ''', (country,)).fetchall()
    conn.close()
    
    return render_template('search.html', results=results, 
                         country=country, operator=operator)

@app.route('/select_operator', methods=['POST'])
def select_operator():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400
     # default settings if none stored yet
    current_settings = session.get('current_settings', {
        'tx_gain': 80,
        'country_name': 'belgique',
        'mcc': 206,
        'mnc': 1,
        'earfcn': 1315,
        'frequency': 1920,
        'operator_name': 'DefaultOperator',
        'bandwidth': 10,
        'technology': 'LTE'
    })

    
    # update only the fields that come from the table click
    current_settings.update({
        'operator_name': data['operator_name'],
        'country_name' : data['country_name'],
        'earfcn': data['earfcn'],
        'frequency': data['frequency'],
        'bandwidth': data['bandwidth'],
        'technology': data['technology'],
        'mnc': data['mnc'],
        'mcc': data['mcc'],
    })
    session['current_settings'] = current_settings
    return jsonify({"status": "ok"})

@app.route('/status')
def status():
    return render_template('status.html')

@app.route('/api/server_info')
def get_server_status():
    return jsonify(server_info)

@app.route('/api/pi_status')
def get_pi_status():
    return jsonify(pi_statuses)
@app.route('/table')
def table():
    return render_template('table.html')
@app.route('/pi_status_update', methods=['POST'])
def receive_pi_status_update():
    data = request.json
    pi_id = data['pi_id']
    pi_statuses[pi_id] = data
   # print(f"Received status from {pi_id}: {data}")  # Debugging line
    socketio.emit('pi_status', pi_statuses)
    return jsonify({'status': 'success'})
#----------------------------------------------------
# database
#----------------------------------------------------
@app.route('/api/fetch_data', methods=['GET'])
def fetch_data():
    session = db_session()
    data = session.query(EPCData).all()
    
    result = []
    for entry in data:
        
        result.append({
            'id': entry.id,
            'unique_id': entry.unique_id,
            'connection_type': entry.connection_type,
            'firstseen': entry.firstseen,
            'lastseen': entry.lastseen,
            'count': entry.count,
            'action': entry.action,
            'whitelist': entry.whitelist,
            'alias': entry.alias
        })
    session.close()
    return jsonify(result)

@app.route('/api/update_whitelist', methods=['POST'])
def update_whitelist():
    data = request.json
    unique_id = data.get('unique_id')
    whitelist = data.get('whitelist')
    session = db_session()
    entry = session.query(EPCData).filter_by(unique_id=unique_id).first()
    

    if entry:
        entry.whitelist = whitelist
        session.commit()
        session.close()
        return jsonify({'status': 'success'})
    session.close()
    return jsonify({'status': 'error', 'message': 'Record not found'})

@app.route('/api/update_action', methods=['POST'])
def update_action():
    data = request.json
    unique_id = data.get('unique_id')
    action = data.get('action')
    session = db_session()
    entry = session.query(EPCData).filter_by(unique_id=unique_id).first()
    
    if entry:
        entry.action = action
        session.commit()
        session.close()
        return jsonify({'status': 'success'})
    session.close()
    return jsonify({'status': 'error', 'message': 'Record not found'})
@app.route('/api/update_alias', methods=['POST'])
def update_alias():
    data = request.get_json()
    unique_id = data['unique_id']
    alias = data['alias']
    session = db_session()
    epc_data = session.query(EPCData).filter_by(unique_id=unique_id).first()
    
    if epc_data:
        epc_data.alias = alias
        session.commit()
        session.close()
        return jsonify({'status': 'success', 'message': 'Alias updated successfully'})
    else:
        return jsonify({'status': 'error', 'message': 'Unique ID not found'}), 404

#-------------------------------------------------
# send msg to newly connected clients
#-------------------------------------------------
@socketio.on('connect')
def handle_connect():
    emit('pi_status', pi_statuses)
    emit('server_info', server_info)
    emit('current_mode', epc_current_mode)

@socketio.on('change_server_mode')
def handle_change_server_mode(data):
    global epc_current_mode
    mode = data['mode']
    epc_current_mode= mode
    test = getattr(lte_cause, mode, None)
    server_instance.attach_reject_reason=getattr(lte_cause, mode, None) 
    
    print(f"Changed server mode to {mode}")
    socketio.emit('current_mode', epc_current_mode) 
'''
@socketio.on('pi_status_update')
def handle_pi_status_update(data):
    pi_id = data['pi_id']
    pi_statuses[pi_id] = data
    emit('pi_status', pi_statuses)
''' # not needed 
def update_server_status():
    global server_info
    while True:
        server_info = {
            'hostname': socket.gethostname(),
            'cpu': psutil.cpu_percent(interval=1),
            'memory': psutil.virtual_memory().percent,
            'heartbeat': time.time()
        }
        socketio.emit('server_info', server_info)
        time.sleep(10)

#------------------------------------------------------------------
#
#   SERVER EPC
#
#------------------------------------------------------------------
    
@app.route('/start_server', methods=['POST'])
def start_server():
    global server_thread, server_instance,server_running
    if not server_running:
        server_instance = EPCServer(process_packet,database_url)
        server_instance.init_server()
        
        server_thread = Thread(target=server_instance.start)
        server_thread.start()
        server_running = True
        socketio.emit('server_status', {'status': 'EPC Server started'})

        return jsonify({'status': 'EPC Server started'})
    else:
        return jsonify({'status': 'EPC Server is already running'})

@app.route('/stop_server', methods=['POST'])
def stop_server():
    global server_instance,server_running,server_thread
    if server_running:
        server_instance.close_server()
        server_running = False
        socketio.emit('server_status', {'status': 'EPC Server stopped'})
        if server_thread.is_alive():
            server_thread.join()
        return jsonify({'status': 'EPC Server stopped'})
    else:
        return jsonify({'status': 'EPC Server is not running'})

@app.route('/server_status', methods=['GET'])
def server_status():
    global server_running
    return jsonify({'running': server_running})
#-----------------------------------------------------------------------
#
#   ENB
#
#-----------------------------------------------------------------------
def execute_command_nonblocking(command, config_file ,args):
    global sp,working_dir
    
    """
    expanded_args = [
        command,
        config_file,
        f"--enb.mcc {args['mcc']}",
        f"--enb.mnc {args['mnc']}",
        #f"--enb.tx_gain={args['tx_gain']}",
        #"--enb.name={args['operator_name']}",
        f"--rf.dl_earfcn {args['earfcn']}",
        #f"--enb.bandwidth={args['bandwidth']}",
        #f"--enb.technology={args['technology']}"
    ]
    """
    
    expanded_args = [
    './srsenb',
    './enb.conf',
    '--enb.mcc', str(args['mcc']),
    '--enb.mnc', str(args['mnc']),
    '--rf.dl_earfcn', str(args['earfcn']),
    '--rf.tx_gain', str(args['tx_gain'])
]
    print("Running:", expanded_args)
    #print(expanded_args)
    try:
        logging.info(f"start subprocess enb")
        
        
        # Create process with proper error handling
        sp = subprocess.Popen(
            expanded_args, 
            shell=False, 
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,  # Separate stderr for better debugging
            cwd=working_dir,  # Set working directory
            env=os.environ.copy(),  # Copy current environment
            universal_newlines=True,  # Handle text properly
            bufsize=1  # Line buffered
        )
        
        logger.info(f"Subprocess started with PID: {sp.pid}")
        
        
        # Give process a moment to start
        time.sleep(0.1)
        
        # Check if process started successfully
        if sp.poll() is None:
            logger.info("Process is running")
            logging.info(f"subprocess started {sp.stdout.readline()}")
            return sp
        else:
            # Process terminated immediately
            stdout, stderr = sp.communicate()
            print(f"Process terminated immediately. stdout: {stdout}, stderr: {stderr}")
            return None
        #logging.info(f"subprocess started {sp.stdout.readline()}")
        
    except FileNotFoundError as e:
        logger.error(f"Command not found: {command} - {str(e)}")
        return None
    except PermissionError as e:
        logger.error(f"Permission denied: {str(e)}")
        return None  
    except Exception as e:
        logging.error(f"error while creating subprocess enb {str(e)}")
        pass
    return None
def read_terminal(process):
    
    """Read terminal output and store in queue - NOT a generator"""
    global stop_event, console_output_queue
    logging.info(f"Starting terminal reader thread")
    
    while not stop_event.is_set():
        try:
            # Use a timeout to make it interruptible
            process.stdout.flush()
            output = process.stdout.readline()
            
            if output == '' and process.poll() is not None:
                logging.info("Process terminated")
                break
                
            if output:
                output = output.strip()
                if output:  # Only add non-empty lines
                    console_output_queue.append(output)
                    # Keep only last MAX_CONSOLE_LINES
                    if len(console_output_queue) > MAX_CONSOLE_LINES:
                        console_output_queue.pop(0)
                    logging.info(f"Console output: {output}")
                    
        except Exception as e:
            logging.error(f"Error reading terminal: {e}")
            break
    
    logging.info("Terminal reader thread stopped")

@app.route('/start_ENB', methods=['POST'])
def start_ENB():
    global  ENB_running,thread_enb,sp
    if not ENB_running:
        logger.info(f"start enb")
        try:

            # default settings if none stored yet
            current_settings = session.get('current_settings', {
                  'tx_gain': 80,
                  'country_name': 'belgique',
                  'mcc': 206,
                  'mnc': '01',
                  'earfcn': 1315,
                  'frequency': 1920,
                  'operator_name': 'DefaultOperator',
                  'bandwidth': 10,
                  'technology': 'LTE'
                })
            sp=execute_command_nonblocking('./srsenb','./enb.conf',current_settings)   
            
            if sp is None:
                logger.error(f"Failed to start subprocess enodeb")
                return jsonify({'status': 'Failed to start ENB'})
        
            thread_enb = Thread(target=read_terminal, args=(sp,))
            thread_enb.daemon = True
            thread_enb.start()
            logger.info(f"Thread started: {thread_enb.is_alive()}") 
            logger.info(f"Thread name: {thread_enb.name}")
            ENB_running = True
            socketio.emit('ENB_status', {'status': 'ENB started'})

            return jsonify({'status': 'ENB starting'})
        except Exception as e:
            logger.error(f"error while launching enb {str(e)}")
            return jsonify({'status': f'Error: {str(e)}'})
    else:
        return jsonify({'status': 'ENB is already running'})
    

@app.route('/events')
def events():
    """Server-Sent Events endpoint for console output"""
    def event_stream():
        last_sent = 0
        while True:
            # Send new console lines
            if last_sent < len(console_output_queue):
                for i in range(last_sent, len(console_output_queue)):
                    yield f"data: {json.dumps({'type': 'console', 'data': console_output_queue[i]})}\n\n"
                last_sent = len(console_output_queue)
            
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage
            
            # Break if ENB is not running
            if not ENB_running:
                break
    
    return Response(event_stream(), mimetype='text/event-stream')



@app.route('/stop_ENB', methods=['POST'])
def stop_ENB():
    
    global ENB_running, thread_enb, sp, stop_event
    
    if ENB_running:
        try:
            
            
            # Send quit command to the process
            if sp and sp.poll() is None:
                try:
                    sp.stdin.write('q\n')
                    sp.stdin.flush()
                    # Give it a moment to quit gracefully
                    time.sleep(1)
                    # Signal the thread to stop
                    if stop_event:
                        stop_event.set()
                    time.sleep(1)
                    if sp.poll() is None:
                        sp.terminate()  # Force terminate if still running
                except Exception as e:
                    logging.error(f"Error stopping process: {e}")
                    if sp:
                        sp.kill()  # Force kill as last resort
            
            # Wait for thread to finish
            if thread_enb and thread_enb.is_alive():
                thread_enb.join(timeout=2)
            
            ENB_running = False
            # clear flag to restart enodeb 
            stop_event.clear()
            socketio.emit('ENB_status', {'status': 'ENB stopped'})
            
            return jsonify({'status': 'ENB stopped'})
            
        except Exception as e:
            logging.error(f"Error stopping ENB: {e}")
            ENB_running = False
            return jsonify({'status': 'ENB stopped with errors'})
    else:
        return jsonify({'status': 'ENB is not running'})

@app.route('/ENB_status', methods=['GET'])
def ENB_status():
    global ENB_running
    return jsonify({'running': ENB_running})
#-----------------------------------------------------------------------
#
#   FLASK
#
#-----------------------------------------------------------------------

def run_flask():
    socketio.run(app, host='0.0.0.0', port=5000)

if __name__ == '__main__':

    tscm_logo.cli()
    stop_event = threading.Event()

    server_thread = threading.Thread(target=run_flask)
    server_thread.start()

    server_status_thread = threading.Thread(target=update_server_status)
    server_status_thread.start()


'''
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
    #app.run(host='0.0.0.0', port=5000)
    '''
